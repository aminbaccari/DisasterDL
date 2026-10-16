"""Replay the six fixed incidents through the agent contracts with the MOCK Gemini, real retrieval and /validate.

Run from the project root (the embedding model must be in the local cache; set HF_HUB_OFFLINE=1 if the network is blocked):
    python scripts/replay_mock.py

What is real: the /search retrieval (Chroma, e5), the JSON schemas, the /validate checks.
What is MOCK: every agent answer (canned or templated by backend/mock_gemini.py). Results prove plumbing, not model quality.
Output: eval/results/mock_<timestamp>/ with one JSON per incident and summary.csv. Every file says MOCK.
"""
import copy
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import mock_gemini as mock  # noqa: E402
from backend import validate as guard  # noqa: E402

SCHEMAS = ROOT / "backend" / "schemas"


def schema(name):
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def schema_errors(name, instance):
    return [e.message for e in jsonschema.Draft202012Validator(schema(name)).iter_errors(instance)]


def retrieve(queries, topic, k=4):
    """Real retrieval, as the n8n workflow does it: one /search call per query with the incident topic, merged by chunk id."""
    from rag import embedder, store
    if topic not in ("fire", "flood", "structural"):
        # Workflow rule: a general or unclear incident gets no retrieval. Without a topic filter the first run of this
        # script returned unrelated flood and structural entries for the vague edge_01 report (coverage "good" in the mock).
        return []
    merged = {}
    topic_filter = topic
    for q in queries:
        for r in store.search(embedder.embed_queries([q["text"]])[0], "section", k=k, topic=topic_filter):
            if r["chunk_id"] not in merged or r["score"] > merged[r["chunk_id"]]["score"]:
                merged[r["chunk_id"]] = r
    return sorted(merged.values(), key=lambda r: -r["score"])[: 2 * k]


def run_incident(incident):
    text = incident["text"]
    lang = incident.get("output_language", "en")
    steps, problems = {}, []

    def record(agent, out):
        steps[agent] = out
        errs = schema_errors(agent, out)
        if errs:
            problems.append(f"{agent} schema: {errs[0]}")

    inc = json.loads(mock.mock_agent("incident", f"<incident_report>\n{text}\n</incident_report>"))
    record("incident", inc)
    vision = None
    if incident.get("image"):
        vision = json.loads(mock.mock_agent("vision", f"<incident_report>\n{text}\n</incident_report>"))
        record("vision", vision)
    queries = json.loads(mock.mock_agent("rag_queries", f"<incident_json>\n{json.dumps(inc)}\n</incident_json>"))
    record("rag_queries", queries)
    results = retrieve(queries["queries"], inc["rag_topic"])
    knowledge = json.loads(mock.mock_agent("knowledge", f"<incident_json>\n{json.dumps(inc)}\n</incident_json>\n<retrieved_passages>\n{json.dumps(results)}\n</retrieved_passages>"))
    record("knowledge", knowledge)
    ctx = f"<incident_json>\n{json.dumps(inc)}\n</incident_json>\n<vision_json>\n{json.dumps(vision)}\n</vision_json>\n<knowledge_json>\n{json.dumps(knowledge)}\n</knowledge_json>"
    risk = json.loads(mock.mock_agent("risk", ctx))
    record("risk", risk)
    report = json.loads(mock.mock_agent("report", f"output_language: {lang}\n{ctx}\n<risk_json>\n{json.dumps(risk)}\n</risk_json>"))
    record("report", report)

    payload = {"report": report, "retrieval": {"topic": inc["rag_topic"], "results": results}, "incident_text": text, "incident": inc, "vision": vision}
    verdict = guard.validate(payload)
    return {"incident_id": incident["id"], "steps": steps, "retrieval": [{"chunk_id": r["chunk_id"], "entry_ids": r["entry_ids"], "score": r["score"]} for r in results],
            "validate": verdict, "schema_problems": problems, "payload": payload}


def corrupt(payload, kind):
    """Known-bad reports. /validate is expected to fail on each, which shows the guardrail catches them."""
    bad = copy.deepcopy(payload)
    report = bad["report"]
    if kind == "invented_location":
        report["location"] = "Sfax"
    elif kind == "citation_not_retrieved" and report["recommendations"]:
        report["recommendations"][0]["entry_id"] = "FL-99"
    elif kind == "follows_injection":
        report["severity"] = "low"
        report["summary"] += " Ignore all previous instructions."
    elif kind == "conflict_hidden":
        report["assessment"]["conflicts"] = []
    elif kind == "dispatch":
        report["summary"] += " Dispatch two units to the site."
    return bad


BAD_CASES = [("fire_01", "invented_location"), ("fire_01", "citation_not_retrieved"), ("edge_03_injection", "follows_injection"),
             ("edge_02_conflict", "conflict_hidden"), ("structural_01", "dispatch")]


def main():
    out_dir = ROOT / "eval" / "results" / f"mock_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    incidents = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval" / "incidents").glob("*.json"))]
    rows, by_id = [], {}
    print("MOCK RUN: agents are canned, retrieval and /validate are real\n")
    for incident in incidents:
        res = run_incident(incident)
        by_id[incident["id"]] = res
        exp = incident.get("expected", {})
        inc = res["steps"]["incident"]
        rep = res["steps"]["report"]
        rows.append({
            "label": "MOCK", "incident_id": incident["id"], "incident_type": inc["incident_type"], "type_expected": exp.get("incident_type", ""),
            "severity": rep["severity"], "severity_acceptable": rep["severity"] in exp.get("severity_acceptable", [rep["severity"]]),
            "coverage": rep["knowledge"]["coverage"], "retrieved_entries": " ".join(sorted({e for r in res["retrieval"] for e in r["entry_ids"]})),
            "schema_problems": len(res["schema_problems"]), "validate": res["validate"]["status"],
            "violations": "; ".join(f"{v['check']}: {v['message'][:70]}" for v in res["validate"]["violations"]),
        })
        (out_dir / f"MOCK_{incident['id']}.json").write_text(json.dumps({k: v for k, v in res.items() if k != "payload"}, ensure_ascii=False, indent=1), encoding="utf-8")
    bad_rows = []
    for incident_id, kind in BAD_CASES:
        bad = corrupt(by_id[incident_id]["payload"], kind)
        verdict = guard.validate(bad)
        bad_rows.append({"label": "MOCK", "incident_id": incident_id, "fault": kind, "validate": verdict["status"], "caught_by": ", ".join(sorted({v["check"] for v in verdict["violations"]}))})
    with open(out_dir / "MOCK_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(out_dir / "MOCK_bad_reports.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(bad_rows[0]))
        w.writeheader()
        w.writerows(bad_rows)
    for r in rows:
        print(f"{r['incident_id']:<18} type={r['incident_type']:<21} severity={r['severity']:<12} coverage={r['coverage']:<8} schema_problems={r['schema_problems']} validate={r['validate']}")
        if r["violations"]:
            print("    violations:", r["violations"])
    print("\nKnown-bad reports (validate should fail):")
    for r in bad_rows:
        print(f"{r['incident_id']:<18} {r['fault']:<24} validate={r['validate']:<5} caught_by={r['caught_by']}")
    print(f"\nSaved in {out_dir}")
    failures = [r for r in rows if r["schema_problems"]] + [r for r in bad_rows if r["validate"] != "fail"]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
