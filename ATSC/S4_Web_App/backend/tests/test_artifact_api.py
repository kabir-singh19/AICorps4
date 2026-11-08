"""ICD Table 8 contract tests for the run-artifact adapter, on a three-site synthetic artifact.

A second class runs the same checks on the bundled real artifact when one is present.
"""
import csv
import gzip
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

TABLE9 = {"site_id", "site_type", "road_name", "length_mi", "fsi_rate", "rank", "flagged", "in_hin", "memo_status"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_fixture(root):
    run = Path(root) / "test-run-001"
    (run / "memos").mkdir(parents=True)
    rows = [
        dict(site_id="11", site_type="segment", road_name="Texas Ave", length_mi=0.1, fsi_rate=2.0, rank=1, flagged=True,
             in_hin=True, memo_status="none", annual_fsi=0.2, jurisdiction="City", rank_city_actionable=1, ka_3y=1,
             annual_kabc=1.0, mu=3.0, k=0.4, eb_weight=0.3, n_eb=2.5, p_fsi=0.08, route_name="", city_actionable=True,
             fsi_rate_spf_eb=1.5, rank_spf_eb=1, kabc_3y=3, tot_3y=8, aadt=20000, aadt_imputed=0, speed_limit=40,
             num_lanes=4, func_class=3, legs="", signalized=False, lon=-96.3, lat=30.6, why="raises risk: traffic"),
        dict(site_id="12", site_type="intersection", road_name="A & B", length_mi=0.0473, fsi_rate=1.0, rank=2,
             flagged=False, in_hin=False, memo_status="none", annual_fsi=0.0473, jurisdiction="TxDOT",
             rank_city_actionable="", ka_3y=0, annual_kabc=0.5, mu=1.0, k=0.1, eb_weight=0.5, n_eb=1.0, p_fsi=0.05,
             route_name="FM2818", city_actionable=False, fsi_rate_spf_eb=0.9, rank_spf_eb=2, kabc_3y=1, tot_3y=2,
             aadt=30000, aadt_imputed=0, speed_limit="", num_lanes="", func_class="", legs=4, signalized=True,
             lon=-96.31, lat=30.61, why=""),
        dict(site_id="13", site_type="segment", road_name="=cmd", length_mi=0.1, fsi_rate=0.1, rank=3, flagged=False,
             in_hin=False, memo_status="none", annual_fsi=0.01, jurisdiction="City", rank_city_actionable=2, ka_3y=0,
             annual_kabc=0.1, mu=0.2, k=0.4, eb_weight=0.9, n_eb=0.1, p_fsi=0.1, route_name="", city_actionable=True,
             fsi_rate_spf_eb=0.1, rank_spf_eb=3, kabc_3y=0, tot_3y=0, aadt=500, aadt_imputed=1, speed_limit=30,
             num_lanes=2, func_class=7, legs="", signalized=False, lon=-96.32, lat=30.62, why=""),
    ]
    with open(run / "ranking.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    geoms = {"11": {"type": "LineString", "coordinates": [[-96.3, 30.6], [-96.301, 30.601]]},
             "12": {"type": "Point", "coordinates": [-96.31, 30.61]},
             "13": {"type": "LineString", "coordinates": [[-96.32, 30.62], [-96.321, 30.621]]}}
    gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "id": r["site_id"], "geometry": geoms[r["site_id"]],
                                                     "properties": {k: r[k] for k in TABLE9}} for r in rows]}
    (run / "sites.geojson").write_text(json.dumps(gj))
    methods = {m: {"capture": c, "ci_low": c - 0.05, "ci_high": c + 0.05, "n_test_fsi": 100, "flagged_miles": 1.0,
                   "flagged_share": 0.11} for m, c in (("A", 0.7), ("B", 0.72), ("C", 0.75))}
    diffs = {"B-A": {"difference": 0.02, "ci_low": -0.01, "ci_high": 0.05}, "C-A": {"difference": 0.05, "ci_low": 0.01, "ci_high": 0.09}}
    sc = {"scenario": "11pct", "length_basis": "icd_250ft", "requested_share": 0.11, "methods": methods, "differences": diffs}
    bt = {"primary": {"target": "KA", "scenario": "11pct", "length_basis": "icd_250ft", "methods": methods,
                      "differences": diffs, "n_test_crashes": 100},
          "targets": {"KA": [sc], "KABC": [sc]}, "method_names": {"A": "HIN", "B": "SPF+EB", "C": "ML-EB"},
          "protocol": "test", "bootstrap": {"resamples": 1000}}
    (run / "backtest.json").write_text(json.dumps(bt))
    (run / "explanations.json").write_text(json.dumps([{"site_id": "11", "rank": i, "feature": f"f{i}", "value": i,
                                                        "shap_value": 0.1 * i, "direction": "raises risk", "text": f"factor {i}"}
                                                       for i in range(1, 6)]))
    (run / "site_history.json").write_text(json.dumps({"fields": ["total", "K", "A"], "years": [2023, 2025],
                                                        "sites": {"11": {"2024": [3, 0, 1]}}}))
    files = {p.name: sha(p) for p in run.iterdir() if p.is_file()}
    (run / "manifest.json").write_text(json.dumps({"run_id": "test-run-001", "created": "2026-11-08T00:00:00+00:00",
                                                   "commit": "abc", "data_versions": {"cris": "test"},
                                                   "methods": {"A": "HIN", "B": "SPF+EB", "C": "ML-EB"},
                                                   "as_of": {"forecast_year": 2026}, "files": files}))
    md = "# Safety memo: Texas Ave\n\nDraft. Site 11, run test-run-001.\n\n## Crash profile\n\n| K | A |\n|---|---|\n| 0 | 1 |\n"
    (run / "memos" / "11.md").write_text(md)
    (run / "memos" / "11.json").write_text(json.dumps({"memo_id": "test-run-001-11", "site_id": "11", "run_id": "test-run-001",
                                                       "status": "draft", "created": "2026-11-08T00:00:00+00:00",
                                                       "model": "test", "cost_usd": 0.01, "seconds": 2.0,
                                                       "tokens_in": 10, "tokens_out": 5, "grounding_check": {}}))
    (run / "memos" / "13.json").write_text(json.dumps({"memo_id": "x", "site_id": "13", "run_id": "test-run-001",
                                                       "status": "blocked", "created": "2026-11-08T00:00:00+00:00"}))
    return run


class ArtifactContract(unittest.TestCase):
    run_id = "test-run-001"
    site = "11"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        write_fixture(cls.tmp)
        cls.env = {"ATSC_ARTIFACTS_DIR": cls.tmp, "ATSC_MODEL_RESULTS_DIR": str(Path(cls.tmp) / "none")}
        cls.old = {k: os.environ.get(k) for k in cls.env}
        os.environ.update(cls.env)
        from app.main import app
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        for k, v in cls.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path, **kw):
        r = self.client.get(path, **kw)
        return r

    def test_health_and_runs(self):
        h = self.get("/api/v1/health").json()
        self.assertTrue({"status", "db", "llm", "version"} <= set(h))
        self.assertFalse(h["assistant_enabled"])
        runs = self.get("/api/v1/runs").json()
        r = next(x for x in runs if x["run_id"] == self.run_id)
        self.assertTrue({"run_id", "created", "code_version", "data_versions", "published"} <= set(r))

    def test_sites_geojson_table9(self):
        r = self.get(f"/api/v1/sites?run_id={self.run_id}", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(r.status_code, 200)
        fc = r.json()
        self.assertEqual(fc["type"], "FeatureCollection")
        for f in fc["features"]:
            self.assertTrue(TABLE9 <= set(f["properties"]))
            self.assertEqual(f["geometry"]["type"], "LineString" if f["properties"]["site_type"] == "segment" else "Point")
        self.assertEqual([f["properties"]["rank"] for f in fc["features"]], sorted(f["properties"]["rank"] for f in fc["features"]))
        flagged = self.get(f"/api/v1/sites?run_id={self.run_id}&flagged=true").json()["features"]
        self.assertTrue(flagged and all(f["properties"]["flagged"] for f in flagged))

    def test_bbox_and_errors(self):
        fc = self.get(f"/api/v1/sites?run_id={self.run_id}&bbox=-96.305,30.59,-96.29,30.605").json()
        self.assertTrue(all(f["properties"]["site_id"] for f in fc["features"]))
        self.assertEqual(self.get(f"/api/v1/sites?run_id={self.run_id}&bbox=1,2").status_code, 422)
        self.assertEqual(self.get("/api/v1/sites?run_id=nope").status_code, 404)
        e = self.get(f"/api/v1/sites/999999?run_id={self.run_id}")
        self.assertEqual(e.status_code, 404)
        self.assertEqual(set(e.json()), {"error", "message"})

    def test_site_detail(self):
        d = self.get(f"/api/v1/sites/{self.site}?run_id={self.run_id}").json()
        self.assertTrue({"attributes", "prediction", "crash_history", "shap_factors", "memo_status"} <= set(d))
        self.assertTrue(d["crash_history"]["by_year"])
        if d["prediction"]["flagged"]:
            self.assertEqual(len(d["shap_factors"]), 5)

    def test_memo_and_pdf(self):
        m = self.get(f"/api/v1/sites/{self.site}/memo?run_id={self.run_id}").json()
        self.assertIn(m["status"], {"draft", "blocked", "pending", "none"})
        if m["status"] == "draft":
            pdf = self.get(f"/api/v1/sites/{self.site}/memo.pdf?run_id={self.run_id}")
            self.assertEqual(pdf.status_code, 200)
            self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_backtest(self):
        b = self.get(f"/api/v1/backtest?run_id={self.run_id}").json()["backtest"]
        methods = {m["method"]: m for m in b["methods"]}
        self.assertTrue({"A", "B", "C"} <= set(methods))
        for m in methods.values():
            self.assertTrue({"capture", "ci_low", "ci_high", "n_test_fsi", "flagged_miles"} <= set(m))
            self.assertLessEqual(m["ci_low"], m["capture"])
            self.assertLessEqual(m["capture"], m["ci_high"])

    def test_exports(self):
        c = self.get(f"/api/v1/export/sites.csv?run_id={self.run_id}")
        self.assertEqual(c.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(c.text)))
        self.assertTrue(TABLE9 <= set(rows[0]))
        self.assertFalse(any(v.startswith(("=", "+", "@")) for r in rows for v in r.values()))
        g = self.get(f"/api/v1/export/sites.geojson?run_id={self.run_id}&flagged=true").json()
        self.assertTrue(all(f["properties"]["flagged"] for f in g["features"]))

    def test_no_key_in_responses(self):
        for path in ("/api/v1/health", "/api/v1/runs", f"/api/v1/sites/{self.site}?run_id={self.run_id}"):
            self.assertNotIn("MEMO_API_KEY", self.get(path).text)
            self.assertNotIn("sk-", self.get(path).text)

    def test_memo_post_not_on_web_host(self):
        self.assertEqual(self.client.post(f"/api/v1/sites/{self.site}/memo", json={"run_id": self.run_id}).status_code, 503)


class FixtureOnly(ArtifactContract):
    def test_blocked_memo_pdf_is_409(self):
        self.assertEqual(self.get(f"/api/v1/sites/13/memo.pdf?run_id={self.run_id}").status_code, 409)
        self.assertEqual(self.get(f"/api/v1/sites/12/memo.pdf?run_id={self.run_id}").status_code, 404)

    def test_tampered_artifact_is_ignored(self):
        p = Path(self.tmp) / self.run_id / "ranking.csv"
        original = p.read_text()
        try:
            p.write_text(original.replace("Texas Ave", "Tampered"))
            from app.artifact_runs import load_run
            with self.assertRaises(ValueError):
                load_run(p.parent)
        finally:
            p.write_text(original)


BUNDLED = Path(__file__).resolve().parents[1] / "data" / "artifacts"


@unittest.skipUnless(any(BUNDLED.glob("*/manifest.json")), "no bundled real artifact")
class BundledRealArtifact(ArtifactContract):
    @classmethod
    def setUpClass(cls):
        run = sorted(BUNDLED.glob("*/manifest.json"))[-1].parent
        cls.run_id = run.name
        memos = sorted((run / "memos").glob("*.md")) if (run / "memos").is_dir() else []
        flagged = next(r for r in csv.DictReader(open(run / "ranking.csv")) if r["flagged"] == "True")
        cls.site = memos[0].stem if memos else flagged["site_id"]
        cls.tmp = None
        cls.env = {"ATSC_ARTIFACTS_DIR": str(BUNDLED)}
        cls.old = {k: os.environ.get(k) for k in cls.env}
        os.environ.update(cls.env)
        from app.main import app
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        for k, v in cls.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


del ArtifactContract

if __name__ == "__main__":
    unittest.main()
