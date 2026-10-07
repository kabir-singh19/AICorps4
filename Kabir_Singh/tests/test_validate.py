"""Tests for the crash-file validator. No database needed.

    python -m unittest discover -s tests -v
"""
import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ingest  # noqa: E402

HEADER = ["Crash_ID", "Crash_Date", "Crash_Sev_ID", "Latitude", "Longitude", "Light_Cond_ID"]


def write_csv(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    w = csv.writer(f)
    w.writerow(HEADER)
    w.writerows(rows)
    f.close()
    return f.name


def good_rows(n, start=1):
    return [[start + i, "03/14/2021", "2", "30.6280", "-96.3344", "1"] for i in range(n)]


class ValidateTests(unittest.TestCase):
    def run_file(self, rows):
        path = write_csv(rows)
        try:
            return ingest.validate_crash_file(path)
        finally:
            os.unlink(path)

    def test_clean_file_passes(self):
        good, rejects, total = self.run_file(good_rows(100))
        self.assertEqual((len(good), len(rejects), total), (100, 0, 100))
        self.assertFalse(ingest.exceeds_limit(len(rejects), total))

    def test_over_two_percent_bad_stops(self):
        rows = good_rows(97) + [[1000 + i, "not a date", "2", "30.6", "-96.3", "1"] for i in range(3)]
        good, rejects, total = self.run_file(rows)
        self.assertEqual(len(rejects), 3)
        self.assertTrue(ingest.exceeds_limit(len(rejects), total))

    def test_exactly_two_percent_loads(self):
        rows = good_rows(98) + [[1000 + i, "not a date", "2", "30.6", "-96.3", "1"] for i in range(2)]
        good, rejects, total = self.run_file(rows)
        self.assertFalse(ingest.exceeds_limit(len(rejects), total))
        self.assertEqual(len(good), 98)

    def test_each_bad_reason(self):
        rows = [
            ["", "03/14/2021", "2", "30.6", "-96.3", "1"],          # no id
            [1, "03/14/2021", "2", "30.6", "-96.3", "1"],
            [1, "03/14/2021", "2", "30.6", "-96.3", "1"],           # duplicate
            [2, "03/14/2009", "2", "30.6", "-96.3", "1"],           # year out of range
            [3, "03/14/2021", "9", "30.6", "-96.3", "1"],           # unknown severity code
            [4, "03/14/2021", "2", "abc", "-96.3", "1"],            # non-numeric coordinate
            [5, "03/14/2021", "2", "48.0", "-96.3", "1"],           # outside Texas
        ]
        good, rejects, _ = self.run_file(rows)
        self.assertEqual(len(good), 1)
        self.assertEqual(len(rejects), 6)

    def test_missing_coordinates_is_not_bad(self):
        good, rejects, _ = self.run_file([
            [1, "03/14/2021", "4", "", "", "1"],
            [2, "03/14/2021", "1", "0", "0", "1"],
            [3, "03/14/2021", "2", "No Data", "No Data", "1"],      # CRIS Query export style
            [4, "03/14/2021", "2", "no data", "NA", "1"],
        ])
        self.assertEqual(len(rejects), 0)
        self.assertEqual(len(good), 4)
        self.assertTrue(all(r["lat"] is None and r["lon"] is None for r in good))

    def test_severity_codes_and_labels(self):
        self.assertEqual(ingest.parse_severity("4"), "K")
        self.assertEqual(ingest.parse_severity("1"), "A")
        self.assertEqual(ingest.parse_severity("K - FATAL INJURY"), "K")
        self.assertEqual(ingest.parse_severity("A - SUSPECTED SERIOUS INJURY"), "A")
        self.assertEqual(ingest.parse_severity("N - NOT INJURED"), "O")
        self.assertEqual(ingest.parse_severity("Non-Incapacitating Injury"), "B")
        self.assertIsNone(ingest.parse_severity("banana"))

    def test_header_style_does_not_matter(self):
        cols = ingest.resolve_columns(["Crash ID", "Crash Date", "Crash Severity", "Latitude", "Longitude"])
        self.assertEqual(cols["crash_id"], "Crash ID")
        self.assertEqual(cols["severity"], "Crash Severity")

    def test_missing_required_column_is_reported(self):
        with self.assertRaises(ValueError):
            ingest.resolve_columns(["Crash ID", "Latitude", "Longitude"])


if __name__ == "__main__":
    unittest.main()
