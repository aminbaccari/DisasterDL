"""Runs the JavaScript of workflow nodes under Node with stubbed n8n inputs: the decisions inside the workflow, tested offline.

Node code comes from the generated n8n/workflows/disasterai.json, so what is tested is what n8n runs. Skipped when node is not installed.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOW = json.loads((ROOT / "n8n" / "workflows" / "disasterai.json").read_text(encoding="utf-8"))
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs');
const spec = JSON.parse(fs.readFileSync(0, 'utf8'));
const $ = (name) => {
  if (!(name in spec.nodes)) throw new Error('node not executed: ' + name);
  return { first: () => ({ json: spec.nodes[name] }), all: () => [{ json: spec.nodes[name] }], isExecuted: true };
};
const $input = { first: () => ({ json: spec.input }), all: () => [{ json: spec.input }] };
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
new AsyncFunction('$', '$input', spec.code)($, $input).then(out => { console.log(JSON.stringify(out)); }, e => { console.error(String(e)); process.exit(1); });
"""


def node_code(name):
    return next(n for n in WORKFLOW["nodes"] if n["name"] == name)["parameters"]["jsCode"]


def run_node(name, nodes, input_json):
    spec = {"code": node_code(name), "nodes": nodes, "input": input_json}
    p = subprocess.run([NODE, "-e", HARNESS], input=json.dumps(spec), capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise AssertionError(p.stderr)
    return json.loads(p.stdout)[0]["json"]


def full_report(coverage="partial"):
    return {"language": "en", "severity": "high", "summary": "s", "reported": [], "image_status": "not_provided", "observed": [], "knowledge": {"coverage": coverage, "guidance": []},
            "assessment": {"basis": [], "risks": [], "possibly_affected": [], "conflicts": []}, "recommendations": [], "uncertainties": ["u"], "information_needed": ["i"],
            "disclaimer": "d", "report_markdown": "# Full report"}


def build_nodes(original_violations, original_report):
    return {
        "Assemble context": {"incident": {"incident_type": "forest_fire"}, "degraded": [], "knowledge": {"coverage": "partial"}, "retrieval": {"results": [{"entry_ids": ["FI-01"]}]}},
        "Risk ready": {"risk": {"severity": "high"}, "degraded_c": []},
        "Report ready": {"report": original_report, "_llm": {"step": "report", "model": "a"}},
        "Repaired report ready": {"report": None, "_llm": {"step": "repaired report", "model": "b"}},
        "Validate report": {"status": "fail" if original_violations else "pass", "violations": original_violations},
    }


@unittest.skipIf(NODE is None, "node is not installed")
class TestRepairNeverMakesItWorse(unittest.TestCase):
    NAME = "Build response (after repair)"
    NO_GUIDANCE = {"check": "no_guidance", "message": "coverage is 'good' although FI-01 was retrieved"}

    def run_repair(self, repaired_report, repaired_validation, original_violations=None):
        nodes = build_nodes(original_violations if original_violations is not None else [self.NO_GUIDANCE], full_report("good"))
        nodes["Repaired report ready"] = {"report": repaired_report, "_llm": {"step": "repaired report", "model": "b"}}
        return run_node(self.NAME, nodes, repaired_validation)

    def test_truncated_repair_is_discarded_and_the_original_is_returned(self):
        truncated = {k: v for k, v in full_report().items() if k not in ("uncertainties", "information_needed", "disclaimer", "report_markdown")}
        schema = [{"check": "schema", "message": f"(root): '{k}' is a required property"} for k in ("uncertainties", "information_needed", "disclaimer", "report_markdown")]
        out = self.run_repair(truncated, {"status": "fail", "violations": schema})
        self.assertEqual(out["report_markdown"], "# Full report")  # the complete original
        self.assertTrue(out["validation"]["repair_discarded"])
        self.assertEqual(out["validation"]["violations"][0]["check"], "no_guidance")
        self.assertEqual(len(out["validation"]["repair_violations"]), 4)
        self.assertEqual(out["status"], "flagged")
        self.assertTrue(any(d["step"] == "repair" for d in out["degraded_steps"]))

    def test_a_repair_that_passes_is_returned(self):
        out = self.run_repair(full_report("partial"), {"status": "pass", "violations": []})
        self.assertEqual(out["status"], "ok")
        self.assertFalse(out["validation"].get("repair_discarded", False))
        self.assertEqual(out["report"]["knowledge"]["coverage"], "partial")
        self.assertEqual(out["validation"]["first_violations"][0]["check"], "no_guidance")

    def test_a_repair_that_fixes_some_checks_is_kept(self):
        two = [{"check": "scope", "message": "a"}, {"check": "citations", "message": "b"}]
        one = [{"check": "citations", "message": "b"}]
        out = self.run_repair(full_report("partial"), {"status": "fail", "violations": one}, original_violations=two)
        self.assertFalse(out["validation"].get("repair_discarded", False))
        self.assertEqual(len(out["validation"]["violations"]), 1)

    def test_a_repair_with_more_failures_is_discarded(self):
        one = [{"check": "scope", "message": "a"}]
        three = [{"check": "scope", "message": "a"}, {"check": "citations", "message": "b"}, {"check": "location", "message": "c"}]
        out = self.run_repair(full_report("partial"), {"status": "fail", "violations": three}, original_violations=one)
        self.assertTrue(out["validation"]["repair_discarded"])

    def test_no_original_report_means_nothing_to_fall_back_to(self):
        nodes = build_nodes([self.NO_GUIDANCE], None)
        nodes["Repaired report ready"] = {"report": {"severity": "high"}, "_llm": {}}
        out = run_node(self.NAME, nodes, {"status": "fail", "violations": [{"check": "schema", "message": "x"}] * 4})
        self.assertFalse(out["validation"].get("repair_discarded", False))

    def test_the_normal_path_without_repair_is_unchanged(self):
        nodes = build_nodes([], full_report("partial"))
        out = run_node("Build response", nodes, {"status": "pass", "violations": []})
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["report_markdown"], "# Full report")


@unittest.skipIf(NODE is None, "node is not installed")
class TestFireCoverageIsCappedInTheWorkflow(unittest.TestCase):
    NAME = next(n["name"] for n in WORKFLOW["nodes"] if n["name"].startswith("Knowledge ready") or n["name"] == "Parse knowledge")

    def run_parse(self, topic, entry_ids, coverage="good"):
        k = {"relevant_guidance": [{"text": "t", "citation": {"chunk_id": "c1", "entry_id": entry_ids[0]}}], "ignored_chunks": [], "coverage": coverage, "gaps": []}
        nodes = {"Merge passages": {"passages": [{"chunk_id": "c1", "entry_ids": entry_ids}], "retrieval": {"topic": topic, "results": []}, "degraded_b": []},
                 "Incident ready": {"rag_topic": topic}}
        model_answer = {"candidates": [{"content": {"parts": [{"text": json.dumps(k)}]}}], "x_llm": {}}
        return run_node(self.NAME, nodes, model_answer)

    def test_good_coverage_with_the_scope_note_becomes_partial(self):
        out = self.run_parse("fire", ["FI-01", "FI-09"])
        self.assertEqual(out["knowledge"]["coverage"], "partial")
        self.assertTrue(any("FI-01" in g for g in out["knowledge"]["gaps"]))

    def test_without_the_scope_note_good_stays_good(self):
        self.assertEqual(self.run_parse("fire", ["FI-09", "FI-10"])["knowledge"]["coverage"], "good")

    def test_other_topics_are_not_capped(self):
        self.assertEqual(self.run_parse("flood", ["FI-01", "FL-04"])["knowledge"]["coverage"], "good")

    def test_partial_stays_partial(self):
        self.assertEqual(self.run_parse("fire", ["FI-01"], coverage="partial")["knowledge"]["coverage"], "partial")


if __name__ == "__main__":
    unittest.main()
