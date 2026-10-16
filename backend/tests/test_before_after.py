"""The before/after analysis computes its measures from saved responses. Offline."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("before_after", ROOT / "scripts" / "before_after.py")
ba = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ba)


def record(report=None, degraded=(), image="none", status="ok", violations=(), repaired=False, variant="after"):
    body = {"status": status, "report": report, "degraded_steps": list(degraded),
            "validation": {"status": "fail" if violations else "pass", "violations": [{"check": v, "message": ""} for v in violations], "repaired": repaired}}
    return {"variant": variant, "run": 1, "seconds": 1.0, "image_status": image, "incident_id": "x", "raw_response": body}


class TestMeasures(unittest.TestCase):
    def test_french_share(self):
        self.assertGreater(ba.french_share(["Nombre de personnes dans le quartier", "Hauteur de l'eau"]), 0.5)
        self.assertLess(ba.french_share(["Number of people in the area", "Whether the road is open"]), 0.5)
        self.assertIsNone(ba.french_share(["xyz"]))

    def test_location_and_image_status_for_a_text_only_run(self):
        inc = {"id": "fire_01", "expected": {"location_text": None}, "output_language": "en"}
        ok = ba.metrics(inc, record({"location": None, "image_status": "not_provided"}))
        self.assertTrue(ok["location_ok"] and ok["image_ok"])
        bad = ba.metrics(inc, record({"location": "hills behind the village", "image_status": "unusable"}))
        self.assertFalse(bad["location_ok"])
        self.assertFalse(bad["image_ok"])

    def test_failed_vision_step_expects_analysis_failed(self):
        inc = {"id": "fire_01", "expected": {}, "output_language": "en"}
        failed = [{"step": "vision", "reason": "x"}]
        self.assertTrue(ba.metrics(inc, record({"location": None, "image_status": "analysis_failed"}, degraded=failed, image="sent"))["image_ok"])
        self.assertFalse(ba.metrics(inc, record({"location": None, "image_status": "unusable"}, degraded=failed, image="sent"))["image_ok"])

    def test_named_location_expected(self):
        inc = {"id": "flood_01", "expected": {"location_text_contains": "Nabeul"}, "output_language": "fr"}
        self.assertTrue(ba.metrics(inc, record({"location": "Nabeul", "image_status": "not_provided", "uncertainties": [], "information_needed": ["Hauteur de l'eau"]}))["location_ok"])
        self.assertFalse(ba.metrics(inc, record({"location": None, "image_status": "not_provided"}))["location_ok"])

    def test_quota_failure_is_recognised(self):
        lost = record(None, degraded=[{"step": "incident understanding", "reason": "every model in the chain failed or was skipped"}], status="degraded")
        self.assertTrue(ba.exhausted(lost))
        self.assertTrue(ba.metrics({"id": "x", "expected": {}}, lost)["quota_failure"])

    def test_schema_failure_counted(self):
        inc = {"id": "x", "expected": {}, "output_language": "en"}
        self.assertTrue(ba.metrics(inc, record({"location": None, "image_status": "not_provided"}, violations=["schema"], status="flagged"))["schema_fail"])


if __name__ == "__main__":
    unittest.main()
