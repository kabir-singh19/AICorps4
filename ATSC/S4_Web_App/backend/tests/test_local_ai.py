import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.main import app
from app.assistant import call_provider, provider_config


class LocalAITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        environment = patch.dict(os.environ, {"ATSC_ENV": "development", "ATSC_AI_ENABLED": "true", "ATSC_AI_PROVIDER": "ollama", "ATSC_LOCAL_AI": "true", "ATSC_AI_MODEL": "qwen2.5:1.5b", "ATSC_AI_API_KEY": "", "ATSC_SESSION_SECRET": "", "ATSC_ASSISTANT_PASSWORD": "", "ATSC_AI_REQUESTS_PER_HOUR": "60"})
        environment.start()
        self.addCleanup(environment.stop)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 123)), base_url="http://127.0.0.1:8010")
        self.addAsyncCleanup(self.client.aclose)

    async def test_local_session_and_chat_need_no_provider_key(self):
        session = (await self.client.get("/api/v1/auth/session")).json()
        self.assertTrue(session["authenticated"])
        self.assertEqual(session["mode"], "local")
        with patch("app.assistant.call_provider", new_callable=AsyncMock, return_value="A local AI answer"):
            response = await self.client.post("/api/v1/assistant/chat", json={"question": "Explain the project workflow"}, headers={"Origin": "http://127.0.0.1:8010"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["answer"], "A local AI answer")
            self.assertEqual(response.json()["model"], "qwen2.5:1.5b")

    async def test_loopback_mode_does_not_authorize_remote_or_production_requests(self):
        for host, client_ip in [("example.edu", "127.0.0.1"), ("127.0.0.1", "203.0.113.1")]:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(client_ip, 123)), base_url=f"http://{host}") as client:
                self.assertFalse((await client.get("/api/v1/auth/session")).json()["authenticated"])
                self.assertEqual((await client.post("/api/v1/assistant/chat", json={"question": "Explain"})).status_code, 401)
        with patch.dict(os.environ, {"ATSC_ENV": "production"}):
            self.assertFalse(provider_config()["configured"])
            self.assertFalse((await self.client.get("/api/v1/auth/session")).json()["authenticated"])
            self.assertEqual((await self.client.post("/api/v1/assistant/chat", json={"question": "Explain"})).status_code, 401)
        self.assertEqual((await self.client.post("/api/v1/assistant/chat", json={"question": "Explain"}, headers={"Origin": "https://unrelated.test"})).status_code, 403)

    async def test_runtime_status_checks_actual_model_and_does_not_fake_connection(self):
        real_client = httpx.AsyncClient
        for installed, expected in [(True, True), (False, False)]:
            data = {"models": [{"name": "qwen2.5:1.5b"}] if installed else []}
            with patch("app.assistant.httpx.AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=data)))):
                status = (await self.client.get("/api/v1/assistant/status")).json()
            self.assertEqual(status["available"], expected)
            self.assertEqual(status["runtime_ready"], expected)

    async def test_local_provider_uses_fixed_native_endpoint_without_credentials(self):
        requests = []
        real_client = httpx.AsyncClient
        def handle(request):
            requests.append(request)
            return httpx.Response(200, json={"message": {"content": "Live format test"}})
        with patch.dict(os.environ, {"ATSC_AI_CHAT_URL": "https://untrusted.example/chat"}):
            config = provider_config()
        self.assertEqual(config["url"], "http://127.0.0.1:11434/api/chat")
        with patch("app.assistant.httpx.AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handle))):
            self.assertEqual(await call_provider(config, "Explain", {}), "Live format test")
        payload = json.loads(requests[0].content)
        self.assertNotIn("Authorization", requests[0].headers)
        self.assertEqual(payload["options"]["num_predict"], 400)
        self.assertFalse(payload["stream"])

    async def test_local_inference_busy_is_bounded(self):
        with patch("app.assistant.local_inference.acquire", new_callable=AsyncMock, side_effect=asyncio.TimeoutError):
            response = await self.client.post("/api/v1/assistant/chat", json={"question": "Explain"})
            self.assertEqual(response.status_code, 429)
            self.assertIn("another question", response.json()["message"])


if __name__ == "__main__":
    unittest.main()
