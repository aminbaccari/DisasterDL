"""The Streamlit screen end to end, with Streamlit's own test runner and the replay server of scripts/replay_webhook.py. Offline."""
import threading
import unittest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None

import importlib.util
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location("replay_webhook", ROOT / "scripts" / "replay_webhook.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


@unittest.skipIf(AppTest is None, "streamlit is not installed")
class TestScreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), replay.Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/webhook/incident"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_mode(self, mode, text="Smoke is rising from the hills behind the village.", save=False):
        at = AppTest.from_file(str(ROOT / "ui" / "app.py"), default_timeout=60).run()
        at.sidebar.selectbox(key="profile").select("Custom URL")
        at.run()
        at.sidebar.text_input(key="custom_url").set_value(f"{self.base}?mode={mode}&delay=0")
        if not save:
            at.sidebar.toggle[0].set_value(False)
        at.run()
        at.text_area(key="text").set_value(text)
        at.run()
        at.button(key="run").click()
        at.run()
        return at

    def texts(self, at):
        parts = [e.value for e in at.error] + [e.value for e in at.warning] + [e.value for e in at.success] + [e.value for e in at.info] + [m.value for m in at.markdown]
        return "\n".join(parts)

    def test_first_screen_has_no_error(self):
        at = AppTest.from_file(str(ROOT / "ui" / "app.py"), default_timeout=60).run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.error), 0)
        self.assertTrue(at.button(key="run").disabled)

    def test_ok_run_shows_a_report(self):
        at = self.run_mode("ok")
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertIn("all automatic checks passed", self.texts(at))
        self.assertIn("Recommended actions", self.texts(at))

    def test_degraded_run_says_the_image_failed_not_unusable(self):
        at = self.run_mode("degraded")
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        text = self.texts(at)
        self.assertIn("degraded steps", text)
        self.assertIn("image analysis failed", text)
        self.assertNotIn("too dark", text)

    def test_flagged_run_lists_the_problems(self):
        at = self.run_mode("flagged")
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        text = self.texts(at)
        self.assertIn("automatic check", text)
        self.assertIn("enter a damaged building", text)
        self.assertIn("FI-99", text)  # the first violations, before the repair pass

    def test_conflict_run_shows_the_disagreement(self):
        at = self.run_mode("conflict")
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertIn("sources disagree", self.texts(at))

    def test_failure_paths_show_a_message_and_what_to_do(self):
        for mode, expected in [("error500", "HTTP 500"), ("notfound", "not active"), ("notjson", "not JSON"), ("empty", "Empty answer")]:
            at = self.run_mode(mode)
            self.assertEqual(len(at.exception), 0, (mode, [e.value for e in at.exception]))
            text = self.texts(at)
            self.assertIn("did not complete", text, mode)
            self.assertIn(expected, text, mode)

    def test_rejected_run(self):
        at = self.run_mode("rejected")
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertIn("rejected", self.texts(at))

    def test_mock_label_is_shown_when_ticked(self):
        at = AppTest.from_file(str(ROOT / "ui" / "app.py"), default_timeout=60).run()
        at.sidebar.selectbox(key="profile").select("Custom URL")
        at.run()
        at.sidebar.text_input(key="custom_url").set_value(f"{self.base}?delay=0")
        at.sidebar.checkbox[0].check()
        at.sidebar.toggle[0].set_value(False)
        at.run()
        at.text_area(key="text").set_value("A fire near the village")
        at.run()
        at.button(key="run").click()
        at.run()
        self.assertIn("MOCK run", self.texts(at))


    def test_history_tab_lists_saved_runs_and_compares_them(self):
        import tempfile
        from ui import history
        with tempfile.TemporaryDirectory() as d:
            old = history.RUNS_DIR
            history.RUNS_DIR = Path(d)
            try:
                for mode in ("ok", "degraded"):
                    at = self.run_mode(mode, save=True)
                self.assertEqual(len(history.list_runs()), 2)
                at = AppTest.from_file(str(ROOT / "ui" / "app.py"), default_timeout=60).run()
                self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
                self.assertEqual(len(at.selectbox(key="hist_pick").options), 2)
                self.assertEqual(len(at.selectbox(key="hist_other").options), 1)
                self.assertTrue(any("Severity" in str(df.value) or "Kind" in str(df.value) for df in at.dataframe))
            finally:
                history.RUNS_DIR = old


if __name__ == "__main__":
    unittest.main()
