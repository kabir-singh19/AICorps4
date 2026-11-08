"""Validator tests for site_agent.py on a fixed evidence record (no database or API needed).

FSR 3.2.1.14: 20 seeded invented-number memos must be blocked.
FSR 3.2.1.15: seeded fake or missing citations must be blocked.
FSR 3.2.1.13: incomplete memos must be blocked; good memos must pass.
"""
import copy
import json
import unittest
from pathlib import Path

import site_agent as sa
from countermeasure_matcher import load_library

ROOT = Path(__file__).resolve().parent


def evidence_fixture():
    library = load_library(ROOT / "countermeasure_library.csv")
    profile = {"site_id": "16964", "run_id": "test-run", "site_type": "intersection", "road_name": "FM2818 & Wellborn Rd",
               "jurisdiction": "TxDOT", "signalized": True, "length_mi": 0.0473, "rank": 1, "rank_city_actionable": None,
               "flagged": True, "in_hin": True, "fsi_rate": 23.91182, "annual_fsi": 1.132188, "annual_kabc": 8.840183,
               "eb_weight": 0.083386, "aadt": 77520.0, "aadt_imputed": False, "speed_limit": None, "num_lanes": None,
               "legs": 4.0, "median_type": None,
               "top_factors": [{"rank": 1, "text": "traffic exposure (77,520 vehicles/day)", "direction": "raises risk"}],
               "model": "S2 method C (ML-EB), forecast year 2026"}
    crashes = {"total": 55, "k": 0, "a": 3, "b": 9, "c": 13, "o": 28, "u": 2, "angle": 13, "rear_end": 20,
               "run_off_road": 4, "opposite_direction": 9, "head_on": 1, "left_turn_opposing": 8, "sideswipe": 2, "night": 15, "wet": 3,
               "years": "2023-2025", "ka": 3, "kabc": 25, "pedestrian": None, "bicycle": None, "notes": []}
    match = sa.match_countermeasures(profile, crashes, library)
    benefits = [sa.compute_benefit(profile, e, library) for e in match["candidates"] + match["engineering_review"]]
    calls = [{"tool": "get_site_profile", "args": {}, "output": profile},
             {"tool": "get_crash_breakdown", "args": {}, "output": crashes},
             {"tool": "match_countermeasures", "args": {}, "output": match},
             {"tool": "compute_benefit", "args": {}, "output": benefits}]
    numbers = {"ka_3y": 3, "kabc_3y": 25, "total_3y": 55, "k_3y": 0, "a_3y": 3, "b_3y": 9, "c_3y": 13, "o_3y": 28,
               "angle_3y": 13, "rear_end_3y": 20, "run_off_road_3y": 4, "head_on_3y": 1, "left_turn_opposing_3y": 8, "sideswipe_3y": 2,
               "night_3y": 15, "wet_3y": 3, "rank": 1, "fsi_rate": 23.91182, "annual_fsi": 1.132188,
               "annual_kabc": 8.840183, "eb_weight": 0.083386, "length_mi": 0.0473, "aadt": 77520.0, "legs": 4.0}
    entries = match["candidates"] + match["engineering_review"]
    citations = {e["evidence"]["cmf_id"]: {"cm_id": e["cm_id"], "cmf": e["evidence"]["cmf"],
                                           "source_url": e["evidence"]["source_url"], "treatment": e["treatment"],
                                           "study_reference": e["evidence"]["study_reference"]} for e in entries}
    return {"site_id": "16964", "run_id": "test-run", "tool_order": list(sa.TOOLS), "tool_results": calls,
            "numbers": numbers, "citations": citations, "allowed_cm_ids": [e["cm_id"] for e in entries],
            "candidate_cm_ids": [e["cm_id"] for e in match["candidates"]]}


def passed(checks):
    return all(c["pass"] for c in checks.values())


class SiteAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = evidence_fixture()
        assert cls.ev["allowed_cm_ids"], "fixture must match at least one countermeasure"
        cls.good = sa.offline_draft(cls.ev)

    def draft(self):
        return copy.deepcopy(self.good)

    def test_production_library_matches_intersection(self):
        self.assertGreaterEqual(len(self.ev["allowed_cm_ids"]), 1)
        self.assertEqual(sa.matcher_input(self.ev["tool_results"][0]["output"], self.ev["tool_results"][1]["output"])
                         ["site_type"], "signalized intersection")

    def test_good_memos_pass_and_render(self):
        drafts = [self.draft()]
        d = self.draft()
        d["countermeasures"] = d["countermeasures"][:1]
        d["why_flagged"] = "The site ranks {{rank}} citywide with {{ annual_fsi }} expected fatal or serious crashes per year."
        drafts.append(d)
        d = self.draft()
        d["crash_profile"] = ("Of {{total_3y}} crashes, {{ka_3y}} were fatal or serious; angle ({{angle_3y}}) and rear-end "
                              "({{rear_end_3y}}) crashes were the most common at this two-way approach.")
        drafts.append(d)
        for d in drafts:
            with self.subTest(d=d["why_flagged"][:30]):
                checks = sa.validate(d, self.ev)
                self.assertTrue(passed(checks), checks)
                memo = sa.render(d, self.ev, {"created": "2026-11-08T00:00:00+00:00", "model": "test"})
                self.assertEqual(sa.rendered_numbers_ok(memo, self.ev, "2026-11-08"), [])
                for c in d["countermeasures"]:
                    cid = next(k for k, v in self.ev["citations"].items() if v["cm_id"] == c["cm_id"])
                    self.assertIn(self.ev["citations"][cid]["source_url"], memo)

    def test_twenty_invented_number_memos_blocked(self):
        cases = []

        def add(field, text):
            d = self.draft()
            if field == "rationale":
                d["countermeasures"][0]["rationale"] += " " + text
            else:
                d[field] = d[field] + " " + text
            cases.append(d)
        add("crash_profile", "There were 12 crashes.")
        add("crash_profile", "About 40% of crashes were at night.")
        add("crash_profile", "twelve crashes involved turning vehicles.")
        add("why_flagged", "It ranks 1st in the city.")
        add("why_flagged", "The rate is 3.5 per mile.")
        add("why_flagged", "Traffic is 77,520 vehicles per day.")
        add("why_flagged", "Risk is twice the city average.")
        add("benefit_cost", "The ratio is about 4:1.")
        add("benefit_cost", "It would cost $250,000.")
        add("benefit_cost", "It saves a hundred thousand dollars.")
        add("next_steps", "Start in 2027.")
        add("next_steps", "Study the next three years.")
        add("next_steps", "Allow half a year for design.")
        add("rationale", "It reduces crashes by 25 percent.")
        add("rationale", "Expect seven fewer crashes.")
        add("rationale", "CMF 0.80 applies.")
        add("crash_profile", "The count was {{ka_5y}}.")          # placeholder not in tool results
        add("why_flagged", "The estimate is {{annual_fsi_x2}}.")   # invented placeholder
        add("crash_profile", "Injury crashes: {{kabc_3y}  .")      # malformed placeholder
        add("next_steps", "Revisit after one dozen months.")
        self.assertEqual(len(cases), 20)
        for i, d in enumerate(cases):
            with self.subTest(case=i + 1):
                checks = sa.validate(d, self.ev)
                self.assertFalse(checks["numeric_grounding_3_2_1_14"]["pass"], checks)
                self.assertFalse(passed(checks))

    def test_fake_and_missing_citations_blocked(self):
        cid0 = next(k for k, v in self.ev["citations"].items() if v["cm_id"] == self.good["countermeasures"][0]["cm_id"])
        cases = []

        def add(fn):
            d = self.draft()
            fn(d)
            cases.append(d)
        add(lambda d: d["countermeasures"][0].update(rationale="A suitable option for review."))                 # missing
        add(lambda d: d["countermeasures"][0].update(rationale="See {{cmf:99999}} for evidence."))              # fake ID
        add(lambda d: d["countermeasures"][0].update(cm_id="CM999"))                                            # not matched
        add(lambda d: d["countermeasures"][0].update(cm_id="CM022"))                                            # excluded entry
        add(lambda d: d["countermeasures"][0].update(rationale=d["countermeasures"][0]["rationale"] +
                                                     " Source https://cmfclearinghouse.example/fake"))           # URL
        add(lambda d: d["countermeasures"].append(dict(d["countermeasures"][0])))                              # duplicate
        add(lambda d: d["why_flagged"].__len__() and d.update(why_flagged=d["why_flagged"] + " {{cmf:12345}}"))  # fake in prose
        if len(self.good["countermeasures"]) > 1:
            other = self.good["countermeasures"][1]
            cid1 = next(k for k, v in self.ev["citations"].items() if v["cm_id"] == other["cm_id"])
            add(lambda d: d["countermeasures"][0].update(rationale=f"Listed with {{{{cmf:{cid1}}}}}."))      # wrong entry's CMF
        add(lambda d: d["countermeasures"][0].update(rationale="Listed with {{cmf:" + cid0 + "}} and {{cmf:00000}}."))
        add(lambda d: d["countermeasures"][0].update(extra="field"))
        for i, d in enumerate(cases):
            with self.subTest(case=i + 1):
                checks = sa.validate(d, self.ev)
                self.assertFalse(passed(checks), checks)
                self.assertFalse(checks["citation_grounding_3_2_1_15"]["pass"], checks)

    def test_incomplete_memos_blocked(self):
        cases = []
        for key in sa.SECTIONS:
            d = self.draft()
            d.pop(key)
            cases.append(d)
        d = self.draft(); d["countermeasures"] = []; cases.append(d)
        d = self.draft(); d["crash_profile"] = "Crashes occurred here."; cases.append(d)
        d = self.draft(); d["why_flagged"] = "The model ranks it high."; cases.append(d)
        d = self.draft(); d["next_steps"] = ""; cases.append(d)
        d = self.draft(); d["site_id"] = "99"; cases.append(d)
        for i, d in enumerate(cases):
            with self.subTest(case=i + 1):
                checks = sa.validate(d, self.ev)
                self.assertFalse(checks["completeness_3_2_1_13"]["pass"], checks)

    def test_rendered_number_check_catches_untraced_number(self):
        memo = sa.render(self.good, self.ev, {"created": "2026-11-08T00:00:00+00:00", "model": "test"})
        self.assertEqual(sa.rendered_numbers_ok(memo, self.ev, "2026-11-08"), [])
        self.assertEqual(sa.rendered_numbers_ok(memo + "\nExtra 98765 crashes.", self.ev, "2026-11-08"), ["98765"])

    def test_benefit_is_qualitative_without_audit_approval(self):
        for b in self.ev["tool_results"][3]["output"]:
            self.assertEqual(b["mode"], "qualitative")
            self.assertTrue(b["reasons"])

    def test_cost_uses_configured_price(self):
        self.assertAlmostEqual(1000 * sa.DEFAULT_PRICE_IN / 1e6 + 500 * sa.DEFAULT_PRICE_OUT / 1e6, 0.006)

    def test_llm_view_has_no_key_or_urls_needed(self):
        view = json.dumps(sa.llm_view(self.ev))
        self.assertNotIn("MEMO_API_KEY", view)
        self.assertIn("ka_3y", view)


if __name__ == "__main__":
    unittest.main()
