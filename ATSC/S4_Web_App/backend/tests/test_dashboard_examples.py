import json
import unittest
from pathlib import Path
from unittest.mock import patch
import os

import httpx
from pydantic import ValidationError
from app.main import app
from app.model_results import PublishedRun, load_runs

FIXTURES = Path(__file__).resolve().parents[1] / "data/published"


class DashboardExampleTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_complete_examples_and_run_scoped_memos(self):
        with patch.dict(os.environ, {"ATSC_MODEL_RESULTS_DIR": str(FIXTURES)}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                runs = (await client.get("/api/v1/runs")).json()
                examples = [run for run in runs if run["run_id"].startswith("example-dashboard-")]
                self.assertEqual(len(examples), 2)
                for run in examples:
                    self.assertTrue(run["is_demo"])
                    self.assertEqual(run["site_count"], 4)
                    sites = (await client.get("/api/v1/sites", params={"run_id": run["run_id"]})).json()["features"]
                    self.assertEqual({site["properties"]["road_name"] for site in sites}, {"University Drive", "Harvey Road", "Texas Avenue", "Wellborn Road"})
                    backtest = (await client.get("/api/v1/backtest", params={"run_id": run["run_id"]})).json()
                    self.assertEqual(len(backtest["backtest"]["methods"]), 3)
                    for feature in sites:
                        response = (await client.get(f'/api/v1/sites/{feature["properties"]["site_id"]}/memo', params={"run_id": run["run_id"]})).json()
                        memo = response["memo"]
                        self.assertTrue(memo["is_example"])
                        self.assertFalse(memo["grounding_passed"])
                        self.assertIn(run["run_id"], memo["text"])
                        self.assertIn("invented", memo["text"])

    def test_examples_cannot_be_relabelled_as_real_grounded_memos(self):
        for file in FIXTURES.glob("example-dashboard-*.json"):
            data = json.loads(file.read_text())
            PublishedRun.model_validate(data)
            data["is_demo"] = False
            with self.assertRaises(ValidationError):
                PublishedRun.model_validate(data)
        geometry = json.loads((FIXTURES.parents[2] / "frontend/src/data/corridors.geojson.json").read_text())
        mappings = {feature["id"]: feature["geometry"] for feature in geometry["features"]}
        runs, _ = load_runs(FIXTURES)
        for example in runs:
            if example.run_id.startswith("example-dashboard-"):
                for site in example.sites:
                    self.assertEqual(site.geometry.model_dump(mode="json"), mappings[site.properties.map_segment_id])


if __name__ == "__main__":
    unittest.main()
