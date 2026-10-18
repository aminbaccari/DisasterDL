"""The stateless tools of the three-view vision path: variants, merge, and their HTTP endpoints. Offline, no model."""
import base64
import io
import json
import unittest
from pathlib import Path

import jsonschema
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageChops

from backend import vision_tools as vt

ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA = json.loads((ROOT / "backend" / "schemas" / "vision.schema.json").read_text(encoding="utf-8"))


def jpeg(size=(64, 48), color=(120, 60, 30)):
    img = Image.new("RGB", size, color)
    for x in range(size[0] // 2):          # left half brighter, so that a mirror is detectable
        for y in range(size[1]):
            img.putpixel((x, y), (250, 250, 250))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=95)
    return out.getvalue()


def obs(category, confidence="high", description=None):
    return {"category": category, "description": description or f"{category} seen", "confidence": confidence}


def answer(observations, usable=True, text=None, quality=None, nd=None):
    return {"image_usable": usable, "quality_issues": quality or [], "scene_summary": "a scene", "observations": observations,
            "visible_text": text or [], "not_determinable": nd or []}


class TestVariants(unittest.TestCase):
    def test_three_views_with_the_original_untouched(self):
        data = jpeg()
        v = vt.make_variants(data, "image/jpeg")
        self.assertEqual([x["name"] for x in v], ["original", "flip", "contrast"])
        self.assertEqual(base64.b64decode(v[0]["image_b64"]), data)
        self.assertTrue(all(x["image_mime"] == "image/jpeg" for x in v))

    def test_flip_is_a_mirror_and_contrast_changes_pixels(self):
        data = jpeg()
        v = vt.make_variants(data)
        original = Image.open(io.BytesIO(data)).convert("RGB")
        flipped = Image.open(io.BytesIO(base64.b64decode(v[1]["image_b64"]))).convert("RGB")
        contrast = Image.open(io.BytesIO(base64.b64decode(v[2]["image_b64"]))).convert("RGB")
        self.assertEqual(flipped.size, original.size)
        self.assertLess(sum(flipped.getpixel((2, 5))) , sum(original.getpixel((2, 5))))      # the bright left half moved to the right
        self.assertIsNotNone(ImageChops.difference(original, contrast).getbbox())

    def test_png_and_webp_keep_their_format(self):
        for fmt, mime in (("PNG", "image/png"), ("WEBP", "image/webp")):
            out = io.BytesIO()
            Image.new("RGBA" if fmt == "PNG" else "RGB", (20, 20), (1, 2, 3, 255) if fmt == "PNG" else (1, 2, 3)).save(out, format=fmt)
            v = vt.make_variants(out.getvalue(), mime)
            self.assertEqual(Image.open(io.BytesIO(base64.b64decode(v[1]["image_b64"]))).format, fmt)

    def test_garbage_is_refused_with_a_message(self):
        with self.assertRaises(vt.ImageError) as cm:
            vt.make_variants(b"this is not an image")
        self.assertIn("could not read the image", str(cm.exception))

    def test_huge_images_are_refused(self):
        old = vt.MAX_PIXELS
        vt.MAX_PIXELS = 100
        try:
            with self.assertRaises(vt.ImageError):
                vt.make_variants(jpeg((64, 48)))
        finally:
            vt.MAX_PIXELS = old


class TestMerge(unittest.TestCase):
    def three(self, a, b, c, **kw):
        return vt.merge([{"name": "original", "result": a}, {"name": "flip", "result": b}, {"name": "contrast", "result": c}], **kw)

    def test_agreement_keeps_the_observation(self):
        r = answer([obs("smoke"), obs("flames")])
        m = self.three(r, r, r)
        self.assertEqual({o["category"] for o in m["observations"]}, {"smoke", "flames"})
        self.assertEqual(m["reliability"]["category_agreement_score"], 1.0)
        self.assertEqual(m["reliability"]["unstable_categories"], [])
        self.assertEqual(m["reliability"]["usable_votes"], "3/3")

    def test_a_category_seen_by_one_view_is_dropped_and_reported(self):
        m = self.three(answer([obs("smoke")]), answer([obs("smoke"), obs("flood_water")]), answer([obs("smoke")]))
        self.assertEqual([o["category"] for o in m["observations"]], ["smoke"])
        self.assertIn({"category": "flood_water", "support": 1}, m["reliability"]["unstable_categories"])
        self.assertEqual(m["reliability"]["category_agreement_score"], round((1 + 1 / 3) / 2, 3))

    def test_two_of_three_is_kept_with_confidence_capped_at_medium(self):
        m = self.three(answer([obs("flames", "high")]), answer([obs("flames", "high")]), answer([]))
        self.assertEqual(m["observations"][0]["confidence"], "medium")
        self.assertIn({"category": "flames", "support": 2}, m["reliability"]["unstable_categories"])

    def test_full_agreement_keeps_the_highest_confidence(self):
        m = self.three(answer([obs("smoke", "low")]), answer([obs("smoke", "high")]), answer([obs("smoke", "medium")]))
        self.assertEqual(m["observations"][0]["confidence"], "high")

    def test_description_comes_from_the_original_not_the_mirror(self):
        m = self.three(answer([obs("people", description="a person on the right")]), answer([obs("people", description="a person on the left")]),
                       answer([obs("people", description="someone at the right edge")]))
        self.assertEqual(m["observations"][0]["description"], "a person on the right")

    def test_one_answer_only_cannot_be_compared_so_everything_is_kept(self):
        m = vt.merge([{"name": "contrast", "result": answer([obs("smoke"), obs("people", "low")])}], requested=3)
        self.assertEqual(len(m["observations"]), 2)
        self.assertIsNone(m["reliability"]["category_agreement_score"])
        self.assertEqual((m["reliability"]["variants_used"], m["reliability"]["variants_requested"]), (1, 3))

    def test_two_answers_keep_only_what_both_saw(self):
        m = vt.merge([answer([obs("smoke"), obs("people")]), answer([obs("smoke")])])
        self.assertEqual([o["category"] for o in m["observations"]], ["smoke"])

    def test_unusable_by_majority_empties_the_observations(self):
        bad = answer([], usable=False, quality=["blurred"])
        m = self.three(bad, bad, answer([obs("smoke")]))
        self.assertFalse(m["image_usable"])
        self.assertEqual(m["observations"], [])
        self.assertEqual(m["quality_issues"], ["blurred"])
        self.assertEqual(m["reliability"]["usable_votes"], "1/3")

    def test_visible_text_needs_two_views(self):
        m = self.three(answer([], text=["STOP", "AT"]), answer([], text=["stop"]), answer([], text=["STOP"]))
        self.assertEqual([t.lower() for t in m["visible_text"]], ["stop"])

    def test_unions_are_deduplicated(self):
        m = self.three(answer([], nd=["Water depth"], quality=["dark"]), answer([], nd=["water  depth", "cause"], quality=["Dark"]), answer([], nd=[]))
        self.assertEqual(m["not_determinable"], ["Water depth", "cause"])
        self.assertEqual(m["quality_issues"], ["dark"])

    def test_nothing_to_merge_is_an_error(self):
        with self.assertRaises(ValueError):
            vt.merge([])

    def test_merged_answer_validates_against_the_schema(self):
        r = answer([obs("smoke")], text=["x"])
        m = self.three(r, r, answer([obs("smoke"), obs("flames", "low")]))
        self.assertEqual(list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(m)), [])

    def test_the_comparison_fields_are_not_merged(self):
        r = {**answer([obs("smoke")]), "consistent_with_report": "yes", "inconsistencies": ["x"]}
        m = self.three(r, r, r)
        self.assertNotIn("consistent_with_report", m)
        self.assertNotIn("inconsistencies", m)


class TestEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(vt.router)
        cls.client = TestClient(app)

    def test_variants_endpoint(self):
        r = self.client.post("/vision/variants", json={"image_b64": base64.b64encode(jpeg()).decode(), "image_mime": "image/jpeg"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["variants"]), 3)

    def test_garbage_image_gets_a_400_with_a_message_and_the_next_call_works(self):
        r = self.client.post("/vision/variants", json={"image_b64": base64.b64encode(b"garbage").decode(), "image_mime": "image/jpeg"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("could not read the image", r.json()["error"])
        r = self.client.post("/vision/variants", json={"image_b64": "!!!not base64!!!", "image_mime": "image/jpeg"})
        self.assertEqual(r.status_code, 400)
        ok = self.client.post("/vision/variants", json={"image_b64": base64.b64encode(jpeg()).decode()})
        self.assertEqual(ok.status_code, 200)

    def test_merge_endpoint(self):
        a = answer([obs("smoke")])
        r = self.client.post("/vision/merge", json={"answers": [{"name": "original", "result": a}, {"name": "flip", "result": a}, {"name": "contrast", "result": a}], "requested": 3})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["merged"]["reliability"]["variants_used"], 3)
        self.assertEqual(self.client.post("/vision/merge", json={"answers": []}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
