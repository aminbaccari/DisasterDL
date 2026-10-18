"""The test UI's non-visual parts: client error classes against a fake webhook, rendering helpers, saved runs. Offline."""
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from ui import client, history, render

OK_BODY = {"status": "ok", "incident_type": "forest_fire", "severity": "high", "report_markdown": "# r", "knowledge_coverage": "partial",
           "report": {"severity": "high", "image_status": "analysed", "observed": [], "recommendations": [{"text": "t", "entry_id": "FI-09", "source": "knowledge_base"}]},
           "validation": {"status": "pass", "violations": [], "repaired": False}, "degraded_steps": [], "retrieved_entry_ids": ["FI-09"],
           "models_used": [{"step": "incident", "provider": "groq", "model": "openai/gpt-oss-120b", "seconds": 1.4, "failed_attempts": []},
                           {"step": "report", "provider": "groq", "model": "qwen/qwen3.8-27b", "seconds": 5.0, "failed_attempts": ["groq:x rate limit"]}],
           "prompt_versions": {"incident": "v3"}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        path = self.path
        if path == "/slow":
            time.sleep(2)
        code, body, ctype = 200, json.dumps(OK_BODY), "application/json"
        if path == "/degraded":
            body = json.dumps({**OK_BODY, "status": "degraded", "degraded_steps": [{"step": "vision", "reason": "failed"}]})
        elif path == "/flagged":
            body = json.dumps({**OK_BODY, "status": "flagged"})
        elif path == "/rejected":
            body = json.dumps({"status": "rejected", "error": "incident_text is missing or too short"})
        elif path == "/notjson":
            body, ctype = "<html>oops</html>", "text/html"
        elif path == "/empty":
            body = ""
        elif path == "/500":
            code, body = 500, "boom"
        elif path == "/404":
            code, body = 404, json.dumps({"message": "not registered"})
        elif path == "/400json":
            code, body = 400, json.dumps({"message": "bad"})
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class TestClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_path(self, path, text="A fire near the village", **kw):
        return client.post_incident(self.base + path, text, **kw)

    def test_ok(self):
        r = self.run_path("/ok")
        self.assertEqual((r.kind, r.http_status), ("ok", 200))
        self.assertTrue(r.has_report)

    def test_status_kinds(self):
        self.assertEqual(self.run_path("/degraded").kind, "degraded")
        self.assertEqual(self.run_path("/flagged").kind, "flagged")
        r = self.run_path("/rejected")
        self.assertEqual(r.kind, "rejected")
        self.assertIn("too short", r.message)

    def test_error_kinds_have_a_hint(self):
        for path, kind in [("/notjson", "not_json"), ("/empty", "empty"), ("/500", "server_error"), ("/404", "not_listening"), ("/400json", "bad_request")]:
            r = self.run_path(path)
            self.assertEqual(r.kind, kind, path)
            self.assertTrue(r.hint, path)

    def test_timeout(self):
        r = self.run_path("/slow", timeout=1)
        self.assertEqual(r.kind, "timeout")

    def test_unreachable(self):
        r = client.post_incident("http://127.0.0.1:1/webhook/incident", "A fire near the village", timeout=2)
        self.assertEqual(r.kind, "unreachable")
        self.assertIn("docker compose", r.hint)

    def test_input_is_checked_before_sending(self):
        r = self.run_path("/ok", text="  ")
        self.assertEqual(r.kind, "bad_request")
        self.assertEqual(self.run_path("/ok", image=(b"x", "a.gif", "image/gif")).kind, "bad_request")
        self.assertEqual(self.run_path("/ok", image=(b"x" * (9 * 1024 * 1024), "a.png", "image/png")).kind, "bad_request")

    def test_image_is_sent(self):
        r = self.run_path("/ok", image=(b"\x89PNG", "a.png", "image/png"))
        self.assertEqual(r.kind, "ok")


class TestRender(unittest.TestCase):
    def test_banners(self):
        self.assertEqual(render.status_banner(OK_BODY)[0], "success")
        self.assertEqual(render.status_banner({**OK_BODY, "status": "degraded", "degraded_steps": [{"step": "vision"}]})[0], "warning")
        flagged = render.status_banner({**OK_BODY, "status": "flagged", "validation": {"violations": [{"check": "scope"}], "repaired": True}})
        self.assertEqual(flagged[0], "warning")
        self.assertIn("1 automatic check failed", flagged[1])
        self.assertEqual(render.status_banner({"status": "rejected", "error": "x"})[0], "error")
        self.assertEqual(render.status_banner({"status": "degraded"})[0], "warning")

    def test_failed_image_step_is_not_called_unusable(self):
        level, text, status = render.image_message({"image_status": "analysis_failed"}, True)
        self.assertEqual(level, "warning")
        self.assertNotIn("too dark", text)
        self.assertEqual(status, "analysis_failed")

    def test_timeline_and_slowest(self):
        rows = render.timeline_rows(OK_BODY["models_used"])
        self.assertEqual(rows[1]["failed attempts"], 1)
        self.assertEqual(render.slowest_step(rows)["step"], "report")
        self.assertIsNone(render.slowest_step([]))

    def test_entries_are_read_from_the_corpus(self):
        e = render.entry("FI-09")
        self.assertIsNotNone(e)
        self.assertTrue(e["text"])
        self.assertNotIn("Source:", e["text"])
        self.assertIsNotNone(render.entry("FL-27"))
        self.assertIsNone(render.entry("XX-99"))

    def test_expected_checks(self):
        out = render.check_expected({"incident_type": "forest_fire", "severity_acceptable": ["low"]}, OK_BODY)
        self.assertEqual([ok for _, ok in out], [True, False, True])
        self.assertEqual(render.check_expected(None, OK_BODY), [])

    def test_validation_view_shows_first_violations(self):
        status, repaired, now, first = render.validation_view({"status": "pass", "repaired": True, "violations": [], "first_violations": [{"check": "scope", "message": "m"}]})
        self.assertEqual((status, repaired, now, first), ("pass", True, [], [("scope", "m")]))

    def test_typical_seconds(self):
        self.assertIsNone(render.typical_seconds([]))
        self.assertEqual(render.typical_seconds([{"kind": "ok", "seconds": 10}, {"kind": "ok", "seconds": 30}, {"kind": "timeout", "seconds": 300}]), 30)


class TestHistory(unittest.TestCase):
    def test_save_list_and_compare(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a = client.RunResult("ok", 12.3, 200, OK_BODY)
            b = client.RunResult("degraded", 40.0, 200, {**OK_BODY, "severity": "moderate", "status": "degraded"})
            pa = history.save_run(a, "http://x/webhook/incident", "Test", False, "A fire", "en", image=(b"123", "p.png", "image/png"), sample_id="fire_01", runs_dir=d)
            history.save_run(b, "http://x/webhook/incident", "Test", False, "A fire", "en", runs_dir=d)
            runs = history.list_runs(d)
            self.assertEqual(len(runs), 2)
            self.assertEqual(history.image_bytes(next(r for r in runs if r["sample_id"] == "fire_01"), d), b"123")
            labels = {x[0] for x in history.compare(runs[1], runs[0])}
            self.assertIn("Severity", labels)
            self.assertIn("Kind", labels)
            self.assertTrue(pa.exists())

    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(history.list_runs(Path(d) / "none"), [])


class TestHealth(unittest.TestCase):
    def test_ollama_address_is_not_rewritten_but_the_others_are(self):
        seen = {}
        original = client._get

        def fake(url, timeout=2, rewrite=True):
            seen[url] = rewrite
            return (200, {"models": [{"name": "m"}], "chain": [], "vision_chain": []}) if "api/tags" in url else (200, {})

        client._get = fake
        try:
            rows = client.check_services("http://localhost:5680/webhook/incident", "http://localhost:8010", "http://localhost:11434")
        finally:
            client._get = original
        self.assertFalse(seen["http://localhost:11434/api/tags"])  # two Ollama servers can share this port; ask the configured address
        self.assertTrue(seen["http://localhost:5680/healthz"])
        self.assertEqual([r for r in rows if "Ollama" in r[0]][0][1], "ok")


if __name__ == "__main__":
    unittest.main()
