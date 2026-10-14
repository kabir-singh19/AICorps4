import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from artifacts import canonical_json, file_hash, json_hash, validate_run_id, verify_bundle, write_json
from backtest import bootstrap_capture
from hin_baseline import hin_membership, overlap_membership
from bit import check_predictions


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.events = [{"crash_id": str(i), "site_id": site, "in_analysis_area": True, "severity": "K"}
                       for i, site in enumerate(["a", "a", "b", "c", None])]

    def test_unmatched_denominator_and_same_method_paired_ci(self):
        report = bootstrap_capture(self.events, {"A": {"a"}, "B": {"a"}, "C": {"b"}}, seed=3)
        self.assertEqual(report["methods"]["A"]["capture"], .4)
        self.assertEqual(report["unmatched_crashes"], 1)
        self.assertEqual(report["differences"]["B-A"], {"difference": 0., "ci_low": 0., "ci_high": 0.})
        self.assertGreaterEqual(report["methods"]["C"]["ci_high"], .2)

    def test_reproducible_bootstrap(self):
        a = bootstrap_capture(self.events, {"C": {"a"}}, seed=5)
        self.assertEqual(a, bootstrap_capture(self.events, {"C": {"a"}}, seed=5))

    def test_out_of_area_and_non_fsi_excluded(self):
        self.events[0]["in_analysis_area"] = False
        self.events[1]["severity"] = "O"
        self.assertEqual(bootstrap_capture(self.events, {"A": {"a"}})["n_test_fsi"], 3)
        self.assertEqual(bootstrap_capture(self.events, {"A": {"a"}}, fsi_only=False)["n_test_fsi"], 4)

    def test_duplicate_and_insufficient_resamples_blocked(self):
        with self.assertRaises(ValueError):
            bootstrap_capture(self.events, {"A": []}, resamples=999)
        with self.assertRaises(ValueError):
            bootstrap_capture(self.events+self.events[:1], {"A": []})

    def test_no_events_is_undefined(self):
        self.assertEqual(bootstrap_capture([], {"A": []})["methods"], {})

    def test_no_match_cannot_be_flagged(self):
        with self.assertRaises(ValueError):
            bootstrap_capture(self.events, {"A": [None]})


class ArtifactAndHinTests(unittest.TestCase):
    def test_canonical_hash_ignores_dictionary_order(self):
        self.assertEqual(json_hash({"a": 2, "b": 1}), json_hash({"b": 1, "a": 2}))
        with self.assertRaises(ValueError):
            canonical_json({"bad": float("nan")})

    def test_unsafe_run_ids_blocked(self):
        for name in ("../x", "/tmp/x", "", "two words"):
            with self.assertRaises(ValueError):
                validate_run_id(name)

    def test_hash_mismatch_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root/"complete.json", {"run_id": "test"})
            write_json(root/"manifest.json", {"run_id": "test", "files": {"complete.json": file_hash(root/"complete.json")}})
            verify_bundle(root)
            (root/"complete.json").write_text("changed")
            with self.assertRaises(ValueError):
                verify_bundle(root)

    def test_incomplete_bundle_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_json(Path(tmp)/"manifest.json", {"run_id": "test", "files": {}})
            with self.assertRaises(ValueError):
                verify_bundle(tmp)

    def test_overlap_rule_exact_boundary(self):
        self.assertTrue(overlap_membership(5,10))
        self.assertFalse(overlap_membership(4.99,10))
        with self.assertRaises(ValueError):
            overlap_membership(11,10)

    def test_hin_missing_and_partial(self):
        self.assertIsNone(hin_membership([{"site_id": "1"}]))
        with self.assertRaises(ValueError):
            hin_membership([{"site_id": "1", "in_hin": True}, {"site_id": "2"}])

    def test_output_faults_blocked(self):
        rows = [{"site_id": str(i), "mu": 2., "k": .5, "eb_weight": .5, "n_eb": 2., "p_fsi": .1,
                 "fsi_rate": .25, "rank": i+1, "flagged": i<11, "annual_total": .25,
                 "annual_fsi": .025, "risk_length_mi": .1, "network_length_mi": .1} for i in range(100)]
        ids = [r["site_id"] for r in rows]
        check_predictions(rows, ids)
        rows[0]["eb_weight"] = 1.2
        with self.assertRaises(ValueError):
            check_predictions(rows, ids)


if __name__ == "__main__":
    unittest.main()
