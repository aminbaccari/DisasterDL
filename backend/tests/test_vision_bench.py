"""The vision benchmark measures are computed correctly from answers. Offline, no model."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("vision_bench", ROOT / "scripts" / "vision_bench.py")
vb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vb)


def obs(category, description="x"):
    return {"category": category, "description": description, "confidence": "high"}


class TestMeasures(unittest.TestCase):
    def test_false_category_is_found(self):
        m = vb.measures("edge_02_conflict.jpg", {"observations": [obs("flood_water", "A field appears flooded"), obs("smoke")]})
        self.assertEqual(m["false_categories"], "flood_water")
        self.assertEqual(m["missing_required"], "")

    def test_a_statement_that_something_is_absent_is_not_a_false_observation(self):
        m = vb.measures("structural_01.jpg", {"observations": [obs("structural_damage"), obs("flood_water", "No visible standing water or flooding.")]})
        self.assertEqual(m["false_categories"], "")
        self.assertEqual(m["absence_observations"], 1)

    def test_missing_required_category(self):
        m = vb.measures("fire_01.jpg", {"observations": [obs("flames")]})
        self.assertEqual(m["missing_required"], "smoke")

    def test_absence_observations_counted(self):
        m = vb.measures("flood_01.jpg", {"observations": [obs("flood_water"), obs("people", "No people are visible"), obs("vehicles", "No visible vehicles"), obs("infrastructure", "Not visible: signs")]})
        self.assertEqual(m["absence_observations"], 3)

    def test_place_words(self):
        self.assertTrue(vb.measures("flood_01.jpg", {"observations": [], "scene_summary": "The architecture suggests a European town"})["place_words"])
        self.assertFalse(vb.measures("flood_01.jpg", {"observations": [obs("flood_water")]})["place_words"])

    def test_ground_truth_covers_every_test_image(self):
        truth = json.loads((ROOT / "vision" / "test_images" / "GROUND_TRUTH.json").read_text(encoding="utf-8"))
        for path in sorted((ROOT / "eval" / "incidents").glob("*.json")):
            image = json.loads(path.read_text(encoding="utf-8")).get("image")
            if image:
                self.assertIn(image, truth, image)
                self.assertTrue((ROOT / "vision" / "test_images" / image).exists())

    def test_v1_user_message_has_the_incident_text_and_v2_does_not(self):
        _, t1 = vb.load_prompt("vision/v1.md")
        _, t2 = vb.load_prompt("vision/v2.md")
        self.assertIn("{{incident_text}}", t1)
        self.assertNotIn("{{incident_text}}", t2)


    def test_every_image_in_the_folder_has_a_ground_truth_entry(self):
        truth = json.loads((ROOT / "vision" / "test_images" / "GROUND_TRUTH.json").read_text(encoding="utf-8"))
        for path in sorted((ROOT / "vision" / "test_images").glob("*.jpg")):
            self.assertIn(path.name, truth, path.name)

    def test_images_without_an_incident_file_have_a_report_text(self):
        truth = json.loads((ROOT / "vision" / "test_images" / "GROUND_TRUTH.json").read_text(encoding="utf-8"))
        used = {json.loads(p.read_text(encoding="utf-8")).get("image") for p in (ROOT / "eval" / "incidents").glob("*.json")}
        for name, t in truth.items():
            if name.endswith(".jpg") and name not in used:
                self.assertTrue(t.get("report_text"), name)

    def test_every_image_is_credited_in_sources(self):
        sources = (ROOT / "vision" / "test_images" / "SOURCES.md").read_text(encoding="utf-8")
        for path in sorted((ROOT / "vision" / "test_images").glob("*.jpg")):
            self.assertIn(path.name, sources, path.name)

    def test_quality_flag_is_only_scored_for_low_quality_images(self):
        self.assertEqual(vb.measures("fire_01.jpg", {"observations": [], "image_usable": False})["quality_flagged"], "")
        self.assertTrue(vb.measures("edge_04_blurred_water.jpg", {"observations": [], "image_usable": True, "quality_issues": ["blurred"]})["quality_flagged"])
        self.assertFalse(vb.measures("control_01_night.jpg", {"observations": [], "image_usable": True, "quality_issues": []})["quality_flagged"])


if __name__ == "__main__":
    unittest.main()
