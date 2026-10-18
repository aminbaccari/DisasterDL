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


    def test_three_view_condition_merges_three_calls(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (32, 32), (10, 20, 30)).save(buf, format="JPEG")
        good = json.dumps({"image_usable": True, "quality_issues": [], "scene_summary": "s", "observations": [{"category": "smoke", "description": "d", "confidence": "high"}],
                           "visible_text": [], "not_determinable": []})
        calls = []

        def fake(system, user, json_mode, image, chain, timeout, rotate, trusted=False):
            calls.append(image)
            return {"candidates": [{"content": {"parts": [{"text": good}]}}], "x_llm": {"attempts": []}}

        original = vb.llm_chain._complete_once
        vb.llm_chain._complete_once = fake
        try:
            merged, seconds, views_ok, error = vb.analyse_tta(buf.getvalue(), "image/jpeg", "sys", "user", [("ollama", "m")])
        finally:
            vb.llm_chain._complete_once = original
        self.assertEqual((len(calls), views_ok, error), (3, 3, ""))
        self.assertEqual(merged["reliability"]["category_agreement_score"], 1.0)

    def test_three_view_condition_survives_a_failed_view(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (32, 32), (10, 20, 30)).save(buf, format="JPEG")
        good = json.dumps({"image_usable": True, "quality_issues": [], "scene_summary": "s", "observations": [], "visible_text": [], "not_determinable": []})
        state = {"n": 0}

        def fake(system, user, json_mode, image, chain, timeout, rotate, trusted=False):
            state["n"] += 1
            if state["n"] == 2:
                return {"error": {"message": "x"}, "x_llm": {"attempts": [{"reason": "ReadTimeout"}]}}
            return {"candidates": [{"content": {"parts": [{"text": good}]}}], "x_llm": {"attempts": []}}

        original = vb.llm_chain._complete_once
        vb.llm_chain._complete_once = fake
        try:
            merged, seconds, views_ok, error = vb.analyse_tta(buf.getvalue(), "image/jpeg", "sys", "user", [("ollama", "m")])
        finally:
            vb.llm_chain._complete_once = original
        self.assertEqual((views_ok, error), (2, "ReadTimeout"))
        self.assertEqual(merged["reliability"]["variants_used"], 2)


    def test_paired_conditions_share_the_three_model_calls(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (32, 32), (10, 20, 30)).save(buf, format="JPEG")
        views = iter([("smoke", "high"), ("smoke", "high"), ("smoke", "high")])
        calls = []

        def fake(system, user, json_mode, image, chain, timeout, rotate, trusted=False):
            calls.append(1)
            cats = [{"category": "smoke", "description": "d", "confidence": "high"}]
            if len(calls) == 2:      # the second view alone sees flames, with high confidence
                cats.append({"category": "flames", "description": "f", "confidence": "high"})
            text = json.dumps({"image_usable": True, "quality_issues": [], "scene_summary": "s", "observations": cats, "visible_text": [], "not_determinable": []})
            return {"candidates": [{"content": {"parts": [{"text": text}]}}], "x_llm": {"attempts": []}}

        original = vb.llm_chain._complete_once
        vb.llm_chain._complete_once = fake
        try:
            shared = {}
            maj, s1, ok1, e1 = vb.analyse_tta(buf.getvalue(), "image/jpeg", "sys", "user", [("ollama", "m")], policy="majority", answers_out=shared)
            high, s2, ok2, e2 = vb.analyse_tta(buf.getvalue(), "image/jpeg", "sys", "user", [("ollama", "m")], policy="keep_high", answers_out=shared)
        finally:
            vb.llm_chain._complete_once = original
        self.assertEqual(len(calls), 3)                                   # not six: the second condition reused the answers
        self.assertEqual([o["category"] for o in maj["observations"]], ["smoke"])
        self.assertEqual({o["category"] for o in high["observations"]}, {"smoke", "flames"})
        self.assertEqual((s1, ok1), (s2, ok2))


if __name__ == "__main__":
    unittest.main()
