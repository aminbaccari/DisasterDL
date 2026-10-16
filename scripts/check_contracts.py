"""Validate outputs shaped as the v1 prompts document them against the contract schemas.

Run from the project root: python scripts/check_contracts.py
It uses the hand-written examples in backend/schemas/examples, not model outputs.
"""
import copy
import json
import sys

import jsonschema

sys.path.insert(0, ".")
S = "backend/schemas/"


def load(n):
    return json.load(open(S + n, encoding="utf-8"))


def ex(n):
    return json.load(open(S + "examples/" + n + ".example.json", encoding="utf-8"))["output"]


def show(label, schema, inst):
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(inst), key=lambda e: list(e.path))
    print(label)
    for e in errs:
        print("  -", "/".join(map(str, e.path)) or "(root)", ":", e.message)
    if not errs:
        print("  (no errors)")


k = copy.deepcopy(ex("knowledge"))
for g in k["relevant_guidance"]:
    del g["citation"]["entry_id"]
show("knowledge, output shaped as prompts/rag_query/v1_synthesis.md documents it", load("knowledge.schema.json"), k)

r = copy.deepcopy(ex("risk"))
for c in r["considerations"]:
    del c["citation"]["entry_id"]
show("risk, output shaped as prompts/risk_assessment/v1.md documents it", load("risk.schema.json"), r)

md = "# Preliminary incident assessment\nGenerated: 2026-10-16\n..."
show("report, Markdown string as prompts/report/v1.md and v2.md return it", load("report.schema.json"), md)

show("knowledge, v2 shape", load("knowledge.schema.json"), ex("knowledge"))
show("risk, v2 shape", load("risk.schema.json"), ex("risk"))
show("report, v3 shape", load("report.schema.json"), ex("report"))
