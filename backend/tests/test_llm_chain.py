"""The fallback chain with a fake HTTP layer: no network, no key, no model."""
import json
import os
import unittest
from unittest import mock

from backend import llm_chain as chain

CHAIN = [("gemini", "g-1"), ("groq", "q-1"), ("openrouter", "o-1:free")]
KEYS = {"GEMINI_API_KEY": "k1", "GROQ_API_KEY": "k2", "OPENROUTER_API_KEY": "k3"}


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None, text=""):
        self.status_code, self._payload, self.headers, self.text = status, payload, headers or {}, text or json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def gemini_ok(text):
    return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})


def openai_ok(text):
    return FakeResponse(200, {"choices": [{"message": {"content": text}}]})


class Base(unittest.TestCase):
    def setUp(self):
        chain.reset_cooldowns()
        self.env = mock.patch.dict(os.environ, KEYS, clear=False)
        self.env.start()
        self.calls = []

    def tearDown(self):
        self.env.stop()

    def run_chain(self, answers, **kwargs):
        """answers: list of responses or exceptions, one per HTTP call in order."""
        queue = list(answers)

        def fake_post(url, headers, body, timeout):
            self.calls.append(url)
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with mock.patch.object(chain, "http_post", fake_post):
            return chain.complete("system JSON", "user", chain=kwargs.pop("chain", CHAIN), **kwargs)


class TestChain(Base):
    def test_parse_chain_keeps_colons_in_model_names(self):
        self.assertEqual(chain.parse_chain("gemini:g-1, openrouter:meta/llama:free ,bad,unknown:x"), [("gemini", "g-1"), ("openrouter", "meta/llama:free")])

    def test_first_model_answers(self):
        out = self.run_chain([gemini_ok('{"a": 1}')])
        self.assertEqual(out["x_llm"]["model"], "g-1")
        self.assertEqual(out["candidates"][0]["content"]["parts"][0]["text"], '{"a": 1}')
        self.assertEqual(len(self.calls), 1)

    def test_rate_limit_falls_back_and_cools_down(self):
        out = self.run_chain([FakeResponse(429, {"error": {}}), openai_ok('{"b": 2}')])
        self.assertEqual((out["x_llm"]["provider"], out["x_llm"]["model"]), ("groq", "q-1"))
        self.assertEqual(out["x_llm"]["attempts"][0]["reason"], "rate limit")
        self.assertTrue(chain.cooling("gemini", "g-1"))
        # next call skips the cooling model without calling it
        out2 = self.run_chain([openai_ok('{"c": 3}')])
        self.assertEqual(out2["x_llm"]["attempts"][0]["reason"], "cooling down")
        self.assertEqual(len(self.calls), 3)  # 2 in the first run, 1 in the second: the cooling model was not called again

    def test_daily_quota_cools_down_for_hours(self):
        daily = FakeResponse(429, {"error": {"details": [{"retryDelay": "29705s"}]}}, text="GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        self.run_chain([daily, openai_ok('{"x": 1}')])
        self.assertGreater(chain._COOLDOWN["gemini:g-1"] - __import__("time").time(), 3600)

    def test_server_error_and_timeout_fall_back(self):
        import requests
        out = self.run_chain([FakeResponse(503, {"error": {}}), requests.Timeout("slow"), openai_ok('{"z": 1}')])
        self.assertEqual(out["x_llm"]["model"], "o-1:free")
        self.assertEqual([a["reason"] for a in out["x_llm"]["attempts"][:2]], ["server error 503", "Timeout"])

    def test_invalid_json_moves_to_the_next_model(self):
        out = self.run_chain([gemini_ok("Sorry, I cannot."), openai_ok('```json\n{"ok": true}\n```')])
        self.assertEqual(out["x_llm"]["model"], "q-1")
        self.assertEqual(out["candidates"][0]["content"]["parts"][0]["text"], '{"ok": true}')

    def test_markdown_answers_are_accepted_when_json_is_not_requested(self):
        out = self.run_chain([gemini_ok("# Title")], json_mode=False)
        self.assertEqual(out["candidates"][0]["content"]["parts"][0]["text"], "# Title")

    def test_missing_key_is_skipped(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            out = self.run_chain([openai_ok('{"k": 1}')])
        self.assertEqual(out["x_llm"]["attempts"][0]["reason"], "no key")
        self.assertEqual(out["x_llm"]["provider"], "groq")

    def test_everything_failing_returns_an_error_with_the_attempts(self):
        out = self.run_chain([FakeResponse(503, {}), FakeResponse(429, {}), FakeResponse(500, {})])
        self.assertIn("error", out)
        self.assertEqual(len(out["x_llm"]["attempts"]), 3)
        self.assertIn("every model in the chain failed", out["error"]["message"])

    def test_retry_does_not_start_with_the_first_model_again(self):
        out = self.run_chain([openai_ok('{"r": 1}')], rotate=True)
        self.assertEqual(out["x_llm"]["provider"], "groq")
        self.assertEqual(out["x_llm"]["attempts"][0]["reason"], "retry: not the first choice again")

    def test_image_requests_skip_models_without_vision(self):
        out = self.run_chain([gemini_ok('{"v": 1}')], chain=[("groq", "llama-3.3-70b-versatile"), ("gemini", "g-1")], image={"mime": "image/png", "b64": "AAAA"})
        self.assertEqual(out["x_llm"]["attempts"][0]["reason"], "no image support")
        self.assertEqual(out["x_llm"]["provider"], "gemini")

    def test_request_formats(self):
        seen = {}

        def fake_post(url, headers, body, timeout):
            seen[url] = (headers, body)
            return openai_ok('{"a": 1}') if "chat/completions" in url else gemini_ok('{"a": 1}')

        with mock.patch.object(chain, "http_post", fake_post):
            chain.complete("sys", "usr", chain=[("groq", "llama-4-scout")], image={"mime": "image/png", "b64": "QQ=="})
            chain.complete("sys", "usr", chain=[("gemini", "g")], image={"mime": "image/png", "b64": "QQ=="}, json_mode=True)
        headers, body = seen["https://api.groq.com/openai/v1/chat/completions"]
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["messages"][1]["content"][1]["image_url"]["url"], "data:image/png;base64,QQ==")
        self.assertTrue(headers["Authorization"].startswith("Bearer "))
        gheaders, gbody = seen[chain.GEMINI_URL.format(base=chain.GEMINI_BASE, model="g")]
        self.assertEqual(gbody["generationConfig"], {"response_mime_type": "application/json"})
        self.assertEqual(gbody["contents"][0]["parts"][1]["inline_data"]["mime_type"], "image/png")

    def test_status_never_contains_a_key(self):
        with mock.patch.dict(os.environ, {"LLM_CHAIN": "gemini:g-1,groq:q-1"}):
            text = json.dumps(chain.status())
        for secret in KEYS.values():
            self.assertNotIn(secret, text)
        self.assertIn('"key": true', text)


class TestRouter(Base):
    def test_llm_endpoint_returns_the_chain_answer(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.llm_router import router
        app = FastAPI()
        app.include_router(router)
        with mock.patch.dict(os.environ, {"LLM_CHAIN": "gemini:g-1"}), mock.patch.object(chain, "http_post", lambda *a, **k: gemini_ok('{"hello": 1}')):
            answer = TestClient(app).post("/llm", json={"system": "s", "user": "u"}).json()
        self.assertEqual(answer["x_llm"]["model"], "g-1")
        self.assertEqual(json.loads(answer["candidates"][0]["content"]["parts"][0]["text"]), {"hello": 1})


if __name__ == "__main__":
    unittest.main()
