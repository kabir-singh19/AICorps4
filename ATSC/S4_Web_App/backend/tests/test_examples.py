import copy
import json
import math
import tempfile
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app.main import app
from app.examples import model, report, report_html


class ExampleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        environment = patch.dict(os.environ, {"ATSC_MODEL_RESULTS_DIR": self.directory.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        self.addAsyncCleanup(self.client.aclose)

    async def test_demo_is_available_but_never_published_as_real_data(self):
        response = await self.client.get("/api/v1/examples")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_demo"])
        self.assertTrue(data["model"]["is_demo"])
        self.assertEqual(len(data["sites"]), 4)
        self.assertEqual(data["model"]["training_records"], 400)
        self.assertEqual(data["model"]["holdout_records"], 100)
        self.assertIn("invented", data["disclaimer"])
        self.assertEqual((await self.client.get("/api/v1/runs")).json(), [])
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    async def test_scores_match_learned_artifact_and_report_ranks(self):
        data = (await self.client.get("/api/v1/examples")).json()
        scores = []
        for site in data["sites"]:
            spec = model()
            terms = [weight * (site["inputs"][feature["key"]] - feature["min"]) / (feature["max"] - feature["min"]) for feature, weight in zip(spec["features"], spec["weights"])]
            expected = 1 / (1 + math.exp(-(spec["intercept"] + sum(terms))))
            response = await self.client.post("/api/v1/examples/predict", json=site["inputs"])
            self.assertEqual(response.status_code, 200)
            prediction = response.json()
            self.assertAlmostEqual(prediction["score"], expected, places=5)
            self.assertEqual(prediction, site["prediction"])
            self.assertTrue(prediction["is_demo"])
            self.assertNotIn("fsi_rate", prediction)
            scores.append(prediction["score"])
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual([site["rank"] for site in data["sites"]], [1, 2, 3, 4])

    async def test_changed_inputs_change_model_result_and_invalid_inputs_rejected(self):
        low = {feature["key"]: feature["min"] for feature in model()["features"]}
        high = {feature["key"]: feature["max"] for feature in model()["features"]}
        first = (await self.client.post("/api/v1/examples/predict", json=low)).json()
        second = (await self.client.post("/api/v1/examples/predict", json=high)).json()
        self.assertLess(first["score"], second["score"])
        self.assertFalse(first["flagged"])
        self.assertTrue(second["flagged"])
        for body in ({**low, "speed_mph": 1000}, {**low, "lanes": 2.5}, {**low, "daily_vehicles": -1}, {**low, "model": "override"}, {}):
            with self.subTest(body=body):
                self.assertEqual((await self.client.post("/api/v1/examples/predict", json=body)).status_code, 422)

    async def test_report_contains_same_results_and_safe_download(self):
        data = report()
        response = await self.client.get("/api/v1/examples/report.html")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertNotIn("content-disposition", response.headers)
        self.assertIn("Synthetic demonstration only", response.text)
        self.assertNotIn("<script", response.text)
        for site in data["sites"]:
            self.assertIn(site["road_name"], response.text)
            self.assertIn(f'{site["prediction"]["score"]:.3f}', response.text)
        download = await self.client.get("/api/v1/examples/report.html?download=true")
        self.assertIn("attachment", download.headers["content-disposition"])
        self.assertEqual(response.text, download.text)
        malicious = copy.deepcopy(data)
        malicious["title"] = '<script>alert("x")</script>'
        self.assertNotIn("<script", report_html(malicious))
        self.assertIn("&lt;script&gt;", report_html(malicious))


if __name__ == "__main__":
    unittest.main()
