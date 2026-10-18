"""The three-view vision branch of the workflow (--vision-mode tta): graph shape and the decisions in its JavaScript nodes, run under Node.

What matters most: n8n keeps the decisions (retry, what a failure means), a failed step is 'analysis_failed' and never 'unusable', and the default
build is untouched. Skipped when node is not installed.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.tests.test_workflow_js import HARNESS, NODE

ROOT = Path(__file__).resolve().parent.parent.parent


def build(*extra):
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_workflow.py"), "--out-dir", d, "--out-name", "w.json", *extra], check=True, capture_output=True, text=True)
        return json.loads((Path(d) / "w.json").read_text(encoding="utf-8"))


DEFAULT = build()
TTA = build("--vision-mode", "tta")


def names(wf):
    return {n["name"] for n in wf["nodes"]}


def run_node(name, nodes, input_json, wf=None):
    code = next(n for n in (wf or TTA)["nodes"] if n["name"] == name)["parameters"]["jsCode"]
    p = subprocess.run([NODE, "-e", HARNESS], input=json.dumps({"code": code, "nodes": nodes, "input": input_json}), capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise AssertionError(p.stderr)
    return json.loads(p.stdout)[0]["json"]


def answer(usable=True, categories=("smoke",)):
    return {"image_usable": usable, "quality_issues": [], "scene_summary": "s", "observations": [{"category": c, "description": c, "confidence": "high"} for c in categories],
            "visible_text": [], "not_determinable": []}


def ok_view(view):
    return {"view": view, "vision": answer(), "vision_status": "analysed", "degraded_a": [], "_failed": False}


def failed_view(view, reason="invalid JSON from the model"):
    return {"view": view, "vision": None, "vision_status": "analysis_failed", "degraded_a": [{"step": "vision", "reason": f"view {view}: {reason}"}], "_failed": True}


def llm(step, model="qwen3-vl:4b-instruct", seconds=10.0, failed=None):
    return {"step": step, "provider": "ollama", "model": model, "seconds": seconds, "failed_attempts": failed or []}


class TestGraph(unittest.TestCase):
    def test_the_default_build_still_has_the_single_call_vision_branch(self):
        n = names(DEFAULT)
        self.assertTrue({"Prompt vision v1", "LLM: vision", "Parse vision", "vision: answer usable?", "LLM: vision (retry)", "Vision ready"} <= n)
        self.assertFalse({"Make views", "Wait for views", "Merge views"} & n)
        self.assertEqual(len(DEFAULT["nodes"]), 78)

    def test_the_tta_build_has_three_view_chains_with_their_own_retry(self):
        n = names(TTA)
        for view in ("original", "flip", "contrast"):
            for node in (f"LLM: vision {view}", f"Parse vision {view}", f"vision {view}: answer usable?", f"LLM: vision {view} (retry)", f"Parse vision {view} (retry)", f"Vision {view} ready"):
                self.assertIn(node, n)
        self.assertTrue({"Make views", "Views ok?", "Wait for views", "Prepare merge", "Any view answered?", "Merge views", "Vision ready", "No image: vision skipped"} <= n)
        self.assertNotIn("LLM: vision", n)

    def test_tta_defaults_to_the_image_only_prompts(self):
        text = json.dumps(TTA)
        self.assertIn("Prompt vision v2", text)
        self.assertNotIn("Prompt vision v1", names(TTA))

    def test_the_orchestration_is_in_n8n_not_in_the_tools(self):
        urls = {n["parameters"].get("url", "") for n in TTA["nodes"] if n["type"] == "n8n-nodes-base.httpRequest"}
        joined = " ".join(urls)
        self.assertIn("/vision/variants", joined)
        self.assertIn("/vision/merge", joined)
        self.assertEqual(sum(1 for n in TTA["nodes"] if n["name"].startswith("LLM: vision") and "(retry)" not in n["name"]), 3)  # the three model calls are n8n nodes

    def test_every_way_the_vision_step_can_end_reaches_the_merge_with_the_knowledge_branch(self):
        incoming = {src for src, v in TTA["connections"].items() for out in v["main"] for o in out if o["node"] == "Wait for both branches"}
        self.assertTrue({"Vision ready", "No image: vision skipped", "Vision failed: no views", "Vision failed: no view answered"} <= incoming)

    def test_the_views_come_from_the_make_views_node(self):
        body = next(n for n in TTA["nodes"] if n["name"] == "LLM: vision flip")["parameters"]["jsonBody"]
        self.assertIn("$('Make views').first().json.variants[1].image_b64", body)
        self.assertIn("task: 'vision'", body)


@unittest.skipIf(NODE is None, "node is not installed")
class TestDecisions(unittest.TestCase):
    def test_a_view_that_fails_says_which_view_and_is_not_an_unusable_image(self):
        out = run_node("Parse vision flip", {}, {"candidates": [{"content": {"parts": [{"text": "this is not json"}]}}], "x_llm": {}})
        self.assertEqual(out["view"], "flip")
        self.assertIsNone(out["vision"])
        self.assertEqual(out["vision_status"], "analysis_failed")
        self.assertIn("view flip:", out["degraded_a"][0]["reason"])

    def test_a_good_view_is_tagged_with_its_name(self):
        text = json.dumps(answer())
        out = run_node("Parse vision contrast", {}, {"candidates": [{"content": {"parts": [{"text": text}]}}], "x_llm": {}})
        self.assertEqual(out["view"], "contrast")
        self.assertEqual(out["vision_status"], "analysed")

    def test_prepare_merge_keeps_the_good_views_and_names_the_failed_one(self):
        spec_input = [ok_view("original"), failed_view("flip"), ok_view("contrast")]
        code = next(n for n in TTA["nodes"] if n["name"] == "Prepare merge")["parameters"]["jsCode"]
        harness = HARNESS.replace("const $input = { first: () => ({ json: spec.input }), all: () => [{ json: spec.input }] };",
                                  "const $input = { first: () => ({ json: spec.input[0] }), all: () => spec.input.map(j => ({ json: j })) };")
        p = subprocess.run([NODE, "-e", harness], input=json.dumps({"code": code, "nodes": {}, "input": spec_input}), capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        j = json.loads(p.stdout)[0]["json"]
        self.assertEqual([a["name"] for a in j["answers"]], ["original", "contrast"])
        self.assertEqual(j["failed"][0]["view"], "flip")
        self.assertTrue(j["any_answer"])
        self.assertEqual(j["requested"], 3)

    def test_prepare_merge_with_no_good_view(self):
        spec_input = [failed_view("original"), failed_view("flip"), failed_view("contrast")]
        code = next(n for n in TTA["nodes"] if n["name"] == "Prepare merge")["parameters"]["jsCode"]
        harness = HARNESS.replace("const $input = { first: () => ({ json: spec.input }), all: () => [{ json: spec.input }] };",
                                  "const $input = { first: () => ({ json: spec.input[0] }), all: () => spec.input.map(j => ({ json: j })) };")
        p = subprocess.run([NODE, "-e", harness], input=json.dumps({"code": code, "nodes": {}, "input": spec_input}), capture_output=True, text=True, timeout=30)
        j = json.loads(p.stdout)[0]["json"]
        self.assertFalse(j["any_answer"])
        self.assertEqual(len(j["failed"]), 3)

    def test_no_view_answered_is_analysis_failed_with_the_reasons(self):
        prep = {"answers": [], "failed": [{"view": "original", "reasons": ["view original: invalid JSON"]}, {"view": "flip", "reasons": ["view flip: timeout"]}], "requested": 3, "any_answer": False}
        out = run_node("Vision failed: no view answered", {}, prep)
        self.assertIsNone(out["vision"])
        self.assertEqual(out["vision_status"], "analysis_failed")
        self.assertIn("timeout", out["degraded_a"][0]["reason"])

    def test_no_views_made_is_analysis_failed(self):
        out = run_node("Vision failed: no views", {}, {"error": {"message": "could not read the image: cannot identify image file"}})
        self.assertIsNone(out["vision"])
        self.assertEqual(out["vision_status"], "analysis_failed")
        self.assertIn("could not read the image", out["degraded_a"][0]["reason"])

    def nodes_for_ready(self, answers, failed=()):
        return {"Prepare merge": {"answers": answers, "failed": list(failed), "requested": 3, "any_answer": bool(answers)},
                "Vision original ready": {"_llm": llm("vision original", seconds=11.0)},
                "Vision flip ready": {"_llm": llm("vision flip", seconds=12.0, failed=["groq:x rate limit"])},
                "Vision contrast ready": {"_llm": llm("vision contrast", seconds=13.0)}}

    def merged(self, usable=True):
        a = answer(usable)
        a["reliability"] = {"variants_used": 3, "variants_requested": 3, "usable_votes": "3/3", "category_agreement_score": 1.0, "unstable_categories": []}
        return {"merged": a}

    def test_vision_ready_is_the_merged_answer_in_the_single_call_shape(self):
        answers = [{"name": n, "result": answer()} for n in ("original", "flip", "contrast")]
        out = run_node("Vision ready", self.nodes_for_ready(answers), self.merged())
        self.assertEqual(out["vision_status"], "analysed")
        self.assertEqual(out["degraded_a"], [])
        self.assertFalse(out["_failed"])
        self.assertEqual(out["vision"]["reliability"]["category_agreement_score"], 1.0)
        self.assertEqual((out["_llm"]["step"], out["_llm"]["views_called"], out["_llm"]["views_ok"]), ("vision", 3, 3))
        self.assertEqual(out["_llm"]["seconds"], 36.0)
        self.assertEqual(out["_llm"]["failed_attempts"], ["groq:x rate limit"])

    def test_a_merged_answer_that_says_unusable_is_unusable_not_failed(self):
        answers = [{"name": "original", "result": answer(False, ())}]
        out = run_node("Vision ready", self.nodes_for_ready(answers), self.merged(usable=False))
        self.assertEqual(out["vision_status"], "unusable")
        self.assertFalse(out["_failed"])

    def test_a_failed_view_makes_the_step_degraded_but_the_answer_is_kept(self):
        answers = [{"name": "original", "result": answer()}, {"name": "contrast", "result": answer()}]
        failed = [{"view": "flip", "reasons": ["view flip: invalid JSON"]}]
        out = run_node("Vision ready", self.nodes_for_ready(answers, failed), self.merged())
        self.assertEqual(out["vision_status"], "analysed")
        self.assertEqual(len(out["degraded_a"]), 1)
        self.assertIn("1 of 3 views failed", out["degraded_a"][0]["reason"])

    def test_when_the_merge_tool_fails_one_view_is_used_and_the_image_is_not_lost(self):
        answers = [{"name": "original", "result": answer(True, ("flames",))}]
        out = run_node("Vision ready", self.nodes_for_ready(answers), {"error": {"message": "connection refused"}})
        self.assertEqual(out["vision_status"], "analysed")
        self.assertEqual(out["vision"]["observations"][0]["category"], "flames")
        self.assertNotIn("reliability", out["vision"])
        self.assertTrue(any("merge tool failed" in d["reason"] for d in out["degraded_a"]))

    def test_a_merged_answer_that_breaks_the_contract_is_not_used(self):
        answers = [{"name": "original", "result": answer()}]
        bad = {"merged": {"image_usable": True, "observations": [{"category": "dust", "description": "x", "confidence": "high"}], "not_determinable": []}}
        out = run_node("Vision ready", self.nodes_for_ready(answers), bad)
        self.assertEqual(out["vision"]["observations"][0]["category"], "smoke")      # the view's own answer
        self.assertTrue(any("invalid category" in d["reason"] for d in out["degraded_a"]))


if __name__ == "__main__":
    unittest.main()
