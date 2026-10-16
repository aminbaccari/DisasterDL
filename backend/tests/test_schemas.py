"""The agent output schemas accept the hand-written examples and reject typical mistakes."""
import copy
import json
import unittest
from pathlib import Path

import jsonschema

SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"
EXAMPLES = SCHEMAS / "examples"
AGENTS = ["incident", "vision", "rag_queries", "knowledge", "risk", "report"]


def load(agent):
    schema = json.loads((SCHEMAS / f"{agent}.schema.json").read_text(encoding="utf-8"))
    example = json.loads((EXAMPLES / f"{agent}.example.json").read_text(encoding="utf-8"))
    return schema, example


def errors(schema, instance):
    return list(jsonschema.Draft202012Validator(schema).iter_errors(instance))


class TestSchemas(unittest.TestCase):
    def test_schemas_are_valid_json_schema(self):
        for agent in AGENTS:
            schema, _ = load(agent)
            jsonschema.Draft202012Validator.check_schema(schema)

    def test_examples_validate(self):
        for agent in AGENTS:
            schema, example = load(agent)
            self.assertEqual(errors(schema, example["output"]), [], agent)

    def test_incident_rejects_unknown_type(self):
        schema, example = load("incident")
        bad = copy.deepcopy(example["output"])
        bad["incident_type"] = "earthquake"
        self.assertTrue(errors(schema, bad))

    def test_knowledge_citation_needs_entry_id(self):
        schema, example = load("knowledge")
        bad = copy.deepcopy(example["output"])
        del bad["relevant_guidance"][0]["citation"]["entry_id"]
        self.assertTrue(errors(schema, bad))

    def test_risk_source_tag_must_be_known(self):
        schema, example = load("risk")
        bad = copy.deepcopy(example["output"])
        bad["severity_basis"][0]["source"] = "common knowledge"
        self.assertTrue(errors(schema, bad))

    def test_report_recommendation_needs_entry_id(self):
        schema, example = load("report")
        bad = copy.deepcopy(example["output"])
        del bad["recommendations"][0]["entry_id"]
        self.assertTrue(errors(schema, bad))

    def test_report_observed_must_be_tagged_image(self):
        schema, example = load("report")
        bad = copy.deepcopy(example["output"])
        bad["observed"][0]["source"] = "report"
        self.assertTrue(errors(schema, bad))



class TestPromptExamples(unittest.TestCase):
    """The complete format example inside report prompt v4 must itself satisfy the report schema and the guardrails."""

    def example(self):
        import re
        text = (SCHEMAS.parent.parent / "prompts" / "report" / "v4.md").read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if l.startswith('{"language"'))
        return json.loads(line)

    def test_report_v4_example_validates(self):
        schema, _ = load("report")
        self.assertEqual(errors(schema, self.example()), [])

    def test_report_v4_example_passes_the_guardrails(self):
        from backend import validate
        verdict = validate.validate({"report": self.example(), "retrieval": {"topic": "general", "results": []},
                                     "incident_text": "A tree has fallen across a road. Nobody is hurt.", "image_status": "not_provided"},
                                    fire_entries=set())
        self.assertEqual(verdict, {"status": "pass", "violations": []})

    def test_report_v4_names_every_required_field(self):
        schema, _ = load("report")
        text = (SCHEMAS.parent.parent / "prompts" / "report" / "v4.md").read_text(encoding="utf-8")
        for field in schema["required"]:
            self.assertIn(f'"{field}"', text, field)

    def test_incident_v2_example_locations_follow_rule_4(self):
        text = (SCHEMAS.parent.parent / "prompts" / "incident_understanding" / "v2.md").read_text(encoding="utf-8")
        self.assertNotIn('"text": "downtown"', text)


if __name__ == "__main__":
    unittest.main()
