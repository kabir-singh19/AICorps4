import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from leakage import validate_snapshot
from make_demo import demo_snapshot

FEATURES = ["speed_limit", "num_lanes", "aadt", "func_class", "median_type"]


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = demo_snapshot(n_sites=10)

    def test_good_input(self):
        self.assertEqual(validate_snapshot(self.snapshot, FEATURES)["sites"], 10)

    def test_twenty_known_good_runs_without_false_alarms(self):
        for seed in range(20):
            validate_snapshot(demo_snapshot(seed=seed, n_sites=10), FEATURES)

    def test_twenty_seeded_s2_contract_faults(self):
        mutations = [
            lambda s: s["features"][0].update(as_of_date="2023-01-01"),
            lambda s: s["metadata"]["sources"][0].update(available_as_of="2024-01-01"),
            lambda s: s["metadata"].update(analysis_scope="three_corridors"),
            lambda s: s["metadata"].update(feature_set="current"),
            lambda s: s["sites"][0].update(risk_length_mi=0),
            lambda s: s["sites"][0].update(network_length_mi=-1),
            lambda s: s["sites"].append(copy.deepcopy(s["sites"][0])),
            lambda s: s["features"].append(copy.deepcopy(s["features"][0])),
            lambda s: s["features"].pop(0),
            lambda s: s["features"][0].update(source="unknown"),
            lambda s: s["metadata"].pop("length_policy"),
            lambda s: s["metadata"].update(history_years_loaded=[2022]),
            lambda s: s["metadata"].update(test_years_loaded=[2023,2024]),
            lambda s: s["history"][0].update(year=2023),
            lambda s: s["history"][0].update(fsi_crashes=10000),
            lambda s: s["history"][0].update(crashes=1.5),
            lambda s: s["test_crashes"].append(copy.deepcopy(s["test_crashes"][0])),
            lambda s: s["test_crashes"][0].update(crash_date="2022-01-01"),
            lambda s: s["test_crashes"][0].update(severity="fatal"),
            lambda s: s["sites"][0].update(in_hin=None),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(fault=index):
                bad = copy.deepcopy(self.snapshot)
                mutate(bad)
                with self.assertRaises(ValueError):
                    validate_snapshot(bad, FEATURES)

    def test_hin_unavailable_is_explicit(self):
        for site in self.snapshot["sites"]:
            site.pop("in_hin")
        self.assertFalse(validate_snapshot(self.snapshot, FEATURES)["hin_available"])

    def test_zero_crash_sites_are_valid_contract_inputs(self):
        self.snapshot["history"] = []
        validate_snapshot(self.snapshot, FEATURES)

    def test_null_is_an_explicit_missing_value(self):
        self.snapshot["features"][0]["value"] = None
        validate_snapshot(self.snapshot, FEATURES)

    def test_hin_and_future_feature_names_blocked(self):
        for name in ("in_hin", "crashes", "fsi_rate", "future_speed", "count_2025"):
            with self.assertRaises(ValueError):
                validate_snapshot(self.snapshot, [*FEATURES[:-1], name])

    def test_intersection_needs_explicit_exposure(self):
        self.snapshot["sites"][0].update(site_type="intersection", risk_length_mi=None)
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, FEATURES)

    def test_unresolved_policy_blocks_production(self):
        self.snapshot["metadata"]["length_policy"] = "REPLACE_WITH_APPROVED_POLICY"
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, FEATURES)


if __name__ == "__main__":
    unittest.main()
