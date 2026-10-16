"""The MOCK Gemini answers in the shapes the schemas expect and routes each prompt to the right agent. MOCK only, no model."""
import json
import re
import unittest
from pathlib import Path

import jsonschema

from backend import mock_gemini as mock

ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMAS = ROOT / "backend" / "schemas"


def errors(name, instance):
    schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
    return [e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(instance)]


def system_prompt(path):
    """First ~~~ block of a prompt file, which is what goes into the n8n node."""
    text = (ROOT / "prompts" / path).read_text(encoding="utf-8")
    return re.search(r"~~~\n(.*?)\n~~~", text, re.S).group(1)


def incidents():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval" / "incidents").glob("*.json"))]


class TestMockOutputs(unittest.TestCase):
    def test_incident_output_matches_schema_for_all_six_incidents(self):
        for inc in incidents():
            out = json.loads(mock.mock_agent("incident", f"<incident_report>\n{inc['text']}\n</incident_report>"))
            self.assertEqual(errors("incident", out), [], inc["id"])
            self.assertEqual(out["rag_topic"], inc["expected"]["rag_topic"], inc["id"])
            self.assertEqual(out["incident_type"], inc["expected"]["incident_type"], inc["id"])

    def test_vision_output_matches_schema_where_an_image_is_expected(self):
        for inc in incidents():
            if inc["image"]:
                out = json.loads(mock.mock_agent("vision", f"<incident_report>\n{inc['text']}\n</incident_report>"))
                self.assertEqual(errors("vision", out), [], inc["id"])

    def test_conflict_incident_gets_an_inconsistent_image(self):
        inc = next(i for i in incidents() if i["id"] == "edge_02_conflict")
        out = json.loads(mock.mock_agent("vision", f"<incident_report>\n{inc['text']}\n</incident_report>"))
        self.assertEqual(out["consistent_with_report"], "no")

    def test_queries_match_schema(self):
        for lang in ("en", "fr"):
            out = json.loads(mock.mock_agent("rag_queries", f"<incident_json>\n{json.dumps({'language': lang})}\n</incident_json>"))
            self.assertEqual(errors("rag_queries", out), [])

    def test_knowledge_without_passages_is_none(self):
        text = '<incident_json>\n{"rag_topic": "general"}\n</incident_json>\n<retrieved_passages>\n[]\n</retrieved_passages>'
        out = json.loads(mock.mock_agent("knowledge", text))
        self.assertEqual(out["coverage"], "none")
        self.assertEqual(errors("knowledge", out), [])

    def test_knowledge_cites_the_passage_entry_id(self):
        passage = {"chunk_id": "en/fire_kb.md::section::8", "source": "fire_kb.md", "page": 1, "entry_ids": ["FI-09"],
                   "text": "FI-09 Under a wildfire warning: get to safety right away. If you are under a wildfire warning, get to safety right away."}
        text = f'<incident_json>\n{{"rag_topic": "fire"}}\n</incident_json>\n<retrieved_passages>\n{json.dumps([passage])}\n</retrieved_passages>'
        out = json.loads(mock.mock_agent("knowledge", text))
        self.assertEqual(out["relevant_guidance"][0]["citation"]["entry_id"], "FI-09")
        self.assertEqual(errors("knowledge", out), [])


class TestRouting(unittest.TestCase):
    def test_each_prompt_file_is_routed_to_its_agent(self):
        expected = {
            "incident_understanding/v1.md": "incident", "vision/v1.md": "vision", "rag_query/v1.md": "rag_queries",
            "rag_query/v2_synthesis.md": "knowledge", "risk_assessment/v2.md": "risk", "report/v3.md": "report",
        }
        for path, agent in expected.items():
            self.assertEqual(mock.agent_for_system(system_prompt(path)), agent, path)

    def test_generate_content_body_like_the_n8n_nodes_send_it(self):
        body = {"system_instruction": {"parts": {"text": system_prompt("incident_understanding/v1.md")}},
                "contents": [{"role": "user", "parts": [{"text": "<incident_report>\nSmoke is rising from the hills behind the village and flames are visible near the first houses. A strong wind is blowing toward the village.\n</incident_report>"}]}],
                "generationConfig": {"response_mime_type": "application/json"}}
        answer = mock.handle_generate(body)
        out = json.loads(answer["candidates"][0]["content"]["parts"][0]["text"])
        self.assertEqual(out["incident_type"], "forest_fire")

    def test_unknown_system_prompt_is_an_error(self):
        self.assertIn("error", mock.handle_generate({"system_instruction": {"parts": {"text": "hello"}}, "contents": []}))


if __name__ == "__main__":
    unittest.main()
