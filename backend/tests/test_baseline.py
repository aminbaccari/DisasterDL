"""The baseline script builds the request and scores answers offline. It calls no model."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location("baseline", ROOT / "scripts" / "baseline_single_prompt.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

EXAMPLES = ROOT / "backend" / "schemas" / "examples"
INCIDENT = {"id": "fire_01", "text": "Smoke is rising from the hills behind the village and flames are visible near the first houses. A strong wind is blowing toward the village.",
            "output_language": "en", "expected": {"rag_topic": "fire", "severity_acceptable": ["high", "critical"]}}


def passages():
    return json.loads((EXAMPLES / "retrieval.example.json").read_text(encoding="utf-8"))["results"]


class TestBaseline(unittest.TestCase):
    def test_request_has_the_incident_and_the_passages(self):
        system, user = baseline.build_request(INCIDENT, passages())
        self.assertIn("<incident_report>", user)
        self.assertIn("FI-09", user)
        self.assertIn("ONE JSON object", system)

    def test_example_report_scores_clean(self):
        report = json.loads((EXAMPLES / "report.example.json").read_text(encoding="utf-8"))["output"]
        row = baseline.score(INCIDENT, report, passages())
        self.assertTrue(row["schema_ok"] and row["validate_ok"] and row["severity_ok"] and row["cites_entries"])
        self.assertFalse(row["invented_location"])

    def test_invented_location_and_missing_citation_are_scored(self):
        report = json.loads((EXAMPLES / "report.example.json").read_text(encoding="utf-8"))["output"]
        report["location"] = "Nabeul"
        report["recommendations"][0]["entry_id"] = "FL-99"
        row = baseline.score(INCIDENT, report, passages())
        self.assertTrue(row["invented_location"])
        self.assertFalse(row["cites_entries"])
        self.assertFalse(row["validate_ok"])

    def test_unusable_answer_scores_false(self):
        row = baseline.score(INCIDENT, None, [])
        self.assertFalse(row["schema_ok"])
        self.assertIsNone(row["type_ok"])


if __name__ == "__main__":
    unittest.main()
