"""The scoring of the narrow vision check is computed from saved checks. Offline, no model."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("vision_check_test", ROOT / "scripts" / "vision_check_test.py")
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)


def check(question, answer):
    return {"claim": "x", "question": question, "answer": answer, "evidence": ""}


class TestScore(unittest.TestCase):
    def test_true_conflict_found_and_no_false_alarm(self):
        row = vc.score("fire_01", [check("Is smoke visible in the image?", "yes"), check("Are houses visible in the image?", "no")])
        self.assertTrue(row["expected_conflict_found"])
        self.assertEqual(row["false_alarms"], 0)

    def test_any_other_no_is_a_false_alarm(self):
        row = vc.score("fire_01", [check("Are flames visible in the image?", "no"), check("Are houses visible in the image?", "no")])
        self.assertEqual(row["false_alarms"], 1)

    def test_every_no_on_a_consistent_incident_is_a_false_alarm(self):
        row = vc.score("flood_01", [check("Is floodwater visible in the image?", "yes"), check("Are roads visible in the image?", "no")])
        self.assertEqual(row["false_alarms"], 1)
        self.assertEqual(row["expected_conflict_found"], "")

    def test_unclear_is_never_a_conflict(self):
        row = vc.score("edge_02_conflict", [check("Is floodwater visible in the image?", "unclear")])
        self.assertFalse(row["expected_conflict_found"])
        self.assertEqual(row["n_no"], 0)

    def test_unscored_incident(self):
        self.assertEqual(vc.score("structural_01", [check("Is dust visible in the image?", "no")])["false_alarms"], "")

    def test_the_v2_question_prompt_bans_abstract_words(self):
        import build_workflow as bw
        bw.PROMPTS["vision"] = "vision_questions/v2.md"
        system, _ = bw.read_prompt("vision")
        self.assertIn("blocked", system)
        self.assertIn("Never use those words", system)


if __name__ == "__main__":
    unittest.main()
