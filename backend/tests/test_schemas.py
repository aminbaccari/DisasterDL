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


if __name__ == "__main__":
    unittest.main()
