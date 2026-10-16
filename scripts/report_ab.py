"""Paired agent-level test of two report prompts (default v3 and v4) on identical inputs.

    python scripts/report_ab.py --runs 3 --chain groq:qwen/qwen3.8-27b [--a report/v3.md --b report/v4.md]

The inputs of the report agent (incident, vision, knowledge, risk JSON, image_status) are built ONCE per incident with the MOCK agents
(backend/mock_gemini.py, canned) and the real retrieval, so both prompts see exactly the same text. Only the report agent is a real model call
(through the model chain). This isolates the prompt change. It is NOT an end-to-end test: the upstream agents are MOCK. For image incidents the
image_status is analysis_failed, which is what the Vision step produced on the days of the real runs (no vision model had quota).

Per call it records: schema valid, /validate verdict, image_status correct, required fields present, whether the example of v4 was copied
(its words 'tree' or 'fallen' appearing in an unrelated incident), and which model answered. Variants are interleaved. Stops after 3 consecutive
chain failures. Output: eval/results/report_ab/<stamp>/.
"""
import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend import llm_chain, validate as guard  # noqa: E402
import build_workflow as bw  # noqa: E402
import replay_mock  # noqa: E402


def fill(template, values):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(values[m.group(1)]), template)


def contexts():
    """One paired input per incident that has a topic (the vague incident exits before the report agent)."""
    out = {}
    for path in sorted((ROOT / "eval" / "incidents").glob("*.json")):
        incident = json.loads(path.read_text(encoding="utf-8"))
        result = replay_mock.run_incident(incident)
        steps = result["steps"]
        if steps["incident"]["incident_type"] == "unclear":
            continue
        has_image = bool(incident.get("image"))
        out[incident["id"]] = {
            "incident": incident, "steps": steps, "retrieval": result["retrieval"], "passages": result["payload"]["retrieval"],
            "image_status": "analysis_failed" if has_image else "not_provided", "vision": None}
    return out


def request_for(prompt_file, ctx):
    bw.PROMPTS["report"] = prompt_file
    system, template = bw.read_prompt("report")
    steps, incident = ctx["steps"], ctx["incident"]
    values = {"output_language": incident.get("output_language", "en"), "generated_at": "2026-10-16T12:00:00Z",
              "incident_json": json.dumps(steps["incident"], ensure_ascii=False), "vision_json_or_null": "null",
              "image_status": ctx["image_status"], "knowledge_json": json.dumps(steps["knowledge"], ensure_ascii=False),
              "risk_json": json.dumps(steps["risk"], ensure_ascii=False)}
    return system, fill(template, values)


def score(ctx, report):
    row = {"schema_ok": False, "validate_ok": False, "checks": "", "image_ok": "", "fields_missing": "", "copied_example": ""}
    if not isinstance(report, dict):
        return row
    schema = guard.check_schema(report)
    required = guard.REPORT_SCHEMA["required"]
    row["fields_missing"] = ",".join(f for f in required if f not in report)
    row["schema_ok"] = not schema
    row["image_ok"] = report.get("image_status") == ctx["image_status"]
    text = json.dumps(report, ensure_ascii=False).lower()
    row["copied_example"] = ("fallen across a road" in text) or ("tree" in text and "tree" not in ctx["incident"]["text"].lower())
    if row["schema_ok"]:
        verdict = guard.validate({"report": report, "retrieval": ctx["passages"], "incident_text": ctx["incident"]["text"], "incident": ctx["steps"]["incident"],
                                  "vision": None, "image_status": ctx["image_status"]})
        row["validate_ok"] = verdict["status"] == "pass"
        row["checks"] = ",".join(sorted({v["check"] for v in verdict["violations"]}))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--a", default="report/v3.md")
    parser.add_argument("--b", default="report/v4.md")
    parser.add_argument("--chain", required=True, help="models to use, for example groq:qwen/qwen3.8-27b. Pin ONE model: if the chain picks a different model for A and B the comparison is confounded.")
    parser.add_argument("--pace-seconds", type=int, default=0, help="pause after every call (free tiers limit tokens per minute: 2026-10-16 qwen3.8-27b allowed about one call of this size per minute)")
    args = parser.parse_args()
    chain = llm_chain.parse_chain(args.chain)
    ctxs = contexts()
    out = ROOT / "eval" / "results" / "report_ab" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    variants = {"A": args.a, "B": args.b}
    rows, streak, stopped = [], 0, "completed all rounds"
    for rnd in range(1, args.runs + 1):
        order = ["A", "B"] if rnd % 2 else ["B", "A"]
        for iid, ctx in ctxs.items():
            for v in order:
                system, user = request_for(variants[v], ctx)
                started = time.time()
                answer = llm_chain.complete(system, user, json_mode=True, chain=chain)
                seconds = round(time.time() - started, 1)
                used = answer["x_llm"]
                label = f"{used['provider']}:{used['model']}" if used.get("model") else ""
                report = None
                if "error" not in answer:
                    try:
                        report = json.loads(answer["candidates"][0]["content"]["parts"][0]["text"])
                    except ValueError:
                        report = None
                row = {"variant": v, "prompt": variants[v], "incident": iid, "run": rnd, "seconds": seconds, "answered_by": label, "chain_error": "error" in answer, **score(ctx, report)}
                rows.append(row)
                (out / f"{v}_{iid}_run{rnd}.json").write_text(json.dumps({"row": row, "report": report, "error": answer.get("error")}, ensure_ascii=False, indent=1), encoding="utf-8")
                print({k: row[k] for k in ("variant", "incident", "run", "seconds", "answered_by", "schema_ok", "validate_ok", "checks", "image_ok", "fields_missing", "copied_example")}, flush=True)
                streak = streak + 1 if row["chain_error"] else 0
                time.sleep(args.pace_seconds)
                if streak >= 3:
                    stopped = f"stopped after 3 consecutive chain failures (round {rnd}, {iid})"
                    break
            if streak >= 3:
                break
        if streak >= 3:
            break
    (out / "STOPPED.txt").write_text(stopped, encoding="utf-8")
    if rows:
        with open(out / "summary.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(stopped, "| saved in", out)
    for v in ("A", "B"):
        r = [x for x in rows if x["variant"] == v and not x["chain_error"]]
        print(f"{v} {variants[v]}: answered {len(r)}/{len([x for x in rows if x['variant'] == v])}, schema_ok {sum(x['schema_ok'] for x in r)}, validate_ok {sum(x['validate_ok'] for x in r)}, "
              f"image_ok {sum(1 for x in r if x['image_ok'] is True)}, copied_example {sum(1 for x in r if x['copied_example'] is True)}")


if __name__ == "__main__":
    main()
