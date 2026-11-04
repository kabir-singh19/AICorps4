"""Hosted boundaries and AI contracts. All provider calls are mocked; no real AI key."""
import copy
import csv
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI, HTTPException

from app import access, assistant
from app.exports import csv_value
from app.main import app
from app.web import mount_frontend, security_headers

EXAMPLE = Path(__file__).resolve().parents[2] / "docs" / "example-model-run.json"


class HostingAssistantTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = patch.dict(os.environ, {
            "ATSC_MODEL_RESULTS_DIR": self.directory.name,
            "ATSC_ENV": "production",
            "ATSC_FRONTEND_DIST": self.directory.name,
            "ATSC_SESSION_SECRET": "test-session-secret-at-least-32-characters",
            "ATSC_ASSISTANT_PASSWORD": "test-project-access-password",
            "ATSC_AI_ENABLED": "true",
            "ATSC_AI_CHAT_URL": "https://provider.example.test/v1/chat/completions",
            "ATSC_AI_API_KEY": "test-placeholder-key-never-used-on-network",
            "ATSC_AI_MODEL": "test-provider-model",
            "ATSC_AI_REQUESTS_PER_HOUR": "30",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        for target in ("app.access.login_limit", "app.assistant.ai_limit"):
            patcher = patch(target, access.RateLimit())
            patcher.start()
            self.addCleanup(patcher.stop)
        self.example = json.loads(EXAMPLE.read_text())
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://project.test")
        self.addAsyncCleanup(self.client.aclose)

    def publish(self, value=None, filename="run.json"):
        Path(self.directory.name, filename).write_text(json.dumps(value or self.example))

    async def login(self):
        response = await self.client.post("/api/v1/auth/login", json={"password": os.environ["ATSC_ASSISTANT_PASSWORD"]}, headers={"Origin": "https://project.test"})
        self.assertEqual(response.status_code, 200)
        return response

    async def test_access_cookie_origin_logout_and_tampering(self):
        self.assertFalse((await self.client.get("/api/v1/auth/session")).json()["authenticated"])
        bad_origin = await self.client.post("/api/v1/auth/login", json={"password": "wrong"}, headers={"Origin": "https://unrelated.test"})
        self.assertEqual(bad_origin.status_code, 403)
        self.assertEqual((await self.client.post("/api/v1/auth/login", json={"password": "wrong"})).status_code, 401)
        response = await self.login()
        cookie = response.headers["set-cookie"].lower()
        for flag in ("httponly", "secure", "samesite=strict", "max-age=3600"):
            self.assertIn(flag, cookie)
        self.assertTrue((await self.client.get("/api/v1/auth/session")).json()["authenticated"])
        self.assertEqual((await self.client.post("/api/v1/auth/logout", json={})).status_code, 200)
        self.assertFalse((await self.client.get("/api/v1/auth/session")).json()["authenticated"])
        self.client.cookies.set(access.COOKIE, "tampered-value")
        self.assertFalse((await self.client.get("/api/v1/auth/session")).json()["authenticated"])

    async def test_login_throttle_and_unconfigured_access(self):
        for _ in range(8):
            self.assertEqual((await self.client.post("/api/v1/auth/login", json={"password": "wrong"})).status_code, 401)
        self.assertEqual((await self.client.post("/api/v1/auth/login", json={"password": "wrong"})).status_code, 429)
        with patch.dict(os.environ, {"ATSC_SESSION_SECRET": "short"}):
            self.assertFalse((await self.client.get("/api/v1/auth/session")).json()["configured"])
            self.assertFalse((await self.client.get("/api/v1/assistant/status")).json()["available"])

    async def test_chat_requires_access_and_explicit_provider_enablement(self):
        with patch("app.assistant.call_provider", new_callable=AsyncMock) as provider:
            self.assertEqual((await self.client.post("/api/v1/assistant/chat", json={"question": "Explain the project"})).status_code, 401)
            await self.login()
            with patch.dict(os.environ, {"ATSC_AI_ENABLED": "false"}):
                self.assertEqual((await self.client.post("/api/v1/assistant/chat", json={"question": "Explain"})).status_code, 503)
            self.assertEqual((await self.client.post("/api/v1/assistant/chat", json={"question": "Explain", "model": "client-chosen-model"})).status_code, 422)
            self.assertEqual((await self.client.post("/api/v1/assistant/chat", json={"question": " "})).status_code, 422)
            self.assertEqual((await self.client.post("/api/v1/assistant/chat", json={"question": "Explain"}, headers={"Origin": "https://unrelated.test"})).status_code, 403)
            provider.assert_not_awaited()

    async def test_chat_published_evidence_isolation_and_draft_label(self):
        self.publish()
        second = copy.deepcopy(self.example)
        second.update(run_id="second-run", sites=[], memos={}, backtest=None)
        self.publish(second, "second.json")
        await self.login()
        with patch("app.assistant.call_provider", new_callable=AsyncMock, return_value="A draft [site:example-site-1]") as provider:
            for body in ({"run_id": "missing"}, {"run_id": "second-run", "site_id": "example-site-1"}, {"site_id": "example-site-1"}):
                result = await self.client.post("/api/v1/assistant/chat", json={"question": "Explain", **body})
                self.assertIn(result.status_code, (404, 422))
            provider.assert_not_awaited()
            response = await self.client.post("/api/v1/assistant/chat", json={"question": "Explain", "run_id": self.example["run_id"], "site_id": "example-site-1"})
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertEqual(result["status"], "draft")
            self.assertTrue(result["is_demo"])
            self.assertEqual(result["site_id"], "example-site-1")
            self.assertIn("site:example-site-1", [source["id"] for source in result["sources"]])
            config, question, evidence = provider.await_args.args
            self.assertEqual(config["model"], "test-provider-model")
            self.assertEqual(evidence["site"]["site_id"], "example-site-1")
            self.assertIn("published_memo", evidence)
            self.assertNotIn("geometry", evidence["site"])

    async def test_project_chat_rate_limit_and_no_secret_exposure(self):
        await self.login()
        with patch.dict(os.environ, {"ATSC_AI_REQUESTS_PER_HOUR": "1"}), patch("app.assistant.call_provider", new_callable=AsyncMock, return_value="Workflow draft"):
            response = await self.client.post("/api/v1/assistant/chat", json={"question": "Explain the workflow"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual((await self.client.post("/api/v1/assistant/chat", json={"question": "Explain"})).status_code, 429)
        status = (await self.client.get("/api/v1/assistant/status")).text
        self.assertNotIn(os.environ["ATSC_AI_API_KEY"], status)
        self.assertNotIn(os.environ["ATSC_AI_CHAT_URL"], status)

    async def test_exports_retain_zero_false_and_selected_run(self):
        self.example["sites"][0]["properties"]["road_name"] = "=FORMULA()"
        self.publish()
        response = await self.client.get("/api/v1/runs/example-run-001/exports/sites.csv")
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.text)))
        self.assertEqual(rows[0]["road_name"], "'=FORMULA()")
        self.assertEqual(rows[1]["fsi_rate"], "0.0")
        self.assertEqual(rows[1]["flagged"], "False")
        self.assertIn("attachment", response.headers["content-disposition"])
        response = await self.client.get("/api/v1/runs/example-run-001/exports/sites.geojson")
        self.assertEqual(response.json()["run_id"], "example-run-001")
        self.assertTrue(response.json()["is_demo"])
        self.assertEqual(len(response.json()["features"]), 2)
        self.assertEqual((await self.client.get("/api/v1/runs/missing/exports/sites.csv")).status_code, 404)
        self.assertEqual(csv_value(0), 0)
        self.assertEqual(csv_value(False), False)
        self.assertEqual(csv_value("  @command"), "'  @command")

    async def test_single_origin_static_api_and_readiness(self):
        self.assertEqual((await self.client.get("/api/v1/ready")).status_code, 503)
        Path(self.directory.name, "index.html").write_text("<!doctype html><title>Traffic project</title>")
        Path(self.directory.name, "app.js").write_text("console.log('test')")
        hosted = FastAPI()
        hosted.middleware("http")(security_headers)

        @hosted.get("/api/v1/runs")
        def runs():
            return []

        mount_frontend(hosted, self.directory.name)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=hosted), base_url="https://project.test") as client:
            page = await client.get("/")
            self.assertIn("Traffic project", page.text)
            self.assertEqual((await client.get("/app.js")).status_code, 200)
            self.assertEqual((await client.get("/api/v1/runs")).json(), [])
            self.assertEqual((await client.get("/api/v1/missing")).status_code, 404)
            self.assertIn("script-src 'self'", page.headers["content-security-policy"])
            self.assertEqual(page.headers["x-content-type-options"], "nosniff")
            self.assertIn("max-age=", page.headers["strict-transport-security"])
        self.assertEqual((await self.client.get("/api/v1/ready")).status_code, 200)

    async def test_provider_payload_and_failure_mapping(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"choices": [{"message": {"content": "Draft [project:workflow]"}}]})

        # Keep the real client constructor before patching the connector's constructor.
        client_type = httpx.AsyncClient

        def mock_client(handler):
            return client_type(transport=httpx.MockTransport(handler))

        config = assistant.provider_config()
        with patch("app.assistant.httpx.AsyncClient", side_effect=lambda **kwargs: mock_client(respond)):
            answer = await assistant.call_provider(config, "Explain", {"project": {"id": "project:workflow"}})
        self.assertIn("Draft", answer)
        payload = json.loads(requests[0].content)
        self.assertEqual(payload["model"], "test-provider-model")
        self.assertEqual(requests[0].headers["Authorization"], "Bearer " + os.environ["ATSC_AI_API_KEY"])
        self.assertEqual(payload["messages"][0]["role"], "system")
        cases = [(429, {}, 429), (500, {}, 502), (200, {"choices": []}, 502), (200, {"choices": [{"message": {"content": None}}]}, 502)]
        for upstream, body, expected in cases:
            with self.subTest(upstream=upstream, body=body):
                with patch("app.assistant.httpx.AsyncClient", side_effect=lambda **kwargs: mock_client(lambda request: httpx.Response(upstream, json=body))):
                    with self.assertRaises(HTTPException) as caught:
                        await assistant.call_provider(config, "Explain", {})
                    self.assertEqual(caught.exception.status_code, expected)
        with self.assertRaises(HTTPException) as caught:
            await assistant.call_provider(config, "Explain", {"huge": "x" * 25000})
        self.assertEqual(caught.exception.status_code, 422)

    def test_provider_rejects_insecure_or_invalid_endpoint(self):
        for url in ("http://provider.test/chat", "https://user:pass@provider.test/chat", "https://provider.test:bad/chat", "https://provider.test/chat?key=secret", ""):
            with self.subTest(url=url), patch.dict(os.environ, {"ATSC_AI_CHAT_URL": url}):
                self.assertFalse(assistant.provider_config()["configured"])


if __name__ == "__main__":
    unittest.main()
