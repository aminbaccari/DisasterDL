"""Does an incident prompt type aftermath and preparation reports correctly, without over-triggering? (D11)

    python scripts/incident_type_check.py --chain groq:openai/gpt-oss-120b --runs 3 --prompt incident_understanding/v2.md --prompt incident_understanding/v3.md

Cases: rag/eval/incident_types_heldout_v1.json (pre-registered, with its pass criteria) plus the six fixed incidents of eval/incidents (expected type from their
`expected` field). Only the Incident Understanding call is real; one pinned model; prompts interleaved per case and run.
Output: eval/results/incident_type_check/<stamp>/ (one JSON per call, summary.csv).
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

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import build_workflow as bw  # noqa: E402
from backend import llm_chain  # noqa: E402

DISASTER = {"forest_fire", "flood", "structural_emergency"}


def load_cases():
    held = json.loads((ROOT / "rag" / "eval" / "incident_types_heldout_v1.json").read_text(encoding="utf-8"))
    cases = [{"id": c["id"], "group": "positive", "text": c["text"], "ok": {c["expected_type"]}} for c in held["positives"]]
    cases += [{"id": c["id"], "group": "negative", "text": c["text"], "ok": set(c["allowed_types"])} for c in held["negatives"]]
    for p in sorted((ROOT / "eval" / "incidents").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        cases.append({"id": d["id"], "group": "fixed", "text": d["text"], "ok": {d["expected"]["incident_type"]}})
    return cases


def summarise(rows, prompts):
    """Calls that returned an error or no JSON are excluded from the counts and listed separately (quota failures are not wrong answers)."""
    print("\nprompt                          positives ok   negatives not typed as disaster   fixed incidents ok   errors (excluded)")
    for prompt in prompts:
        r = [x for x in rows if x["prompt"] == prompt]
        errors = [x for x in r if x["found_type"] in ("error", "not_json")]
        r = [x for x in r if x not in errors]
        pos = [x for x in r if x["group"] == "positive"]
        neg = [x for x in r if x["group"] == "negative"]
        fix = [x for x in r if x["group"] == "fixed"]
        print(f"{prompt:<31} {sum(x['correct'] for x in pos)}/{len(pos):<12} {sum(x['found_type'] not in DISASTER for x in neg)}/{len(neg):<30} {sum(x['correct'] for x in fix)}/{len(fix):<19} {len(errors)}")


def rescore(folder):
    with open(Path(folder) / "summary.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["correct"] = r["correct"] == "True"
    summarise(rows, sorted({r["prompt"] for r in rows}))
    for r in rows:
        if not r["correct"] and r["found_type"] not in ("error", "not_json"):
            print("  wrong:", r["prompt"], r["case"], r["group"], "run", r["run"], "->", r["found_type"], "(allowed", r["allowed"] + ")")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rescore", metavar="FOLDER", help="recompute the table of a finished run (no model call)")
    parser.add_argument("--chain")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--prompt", action="append")
    parser.add_argument("--pace-seconds", type=int, default=1)
    args = parser.parse_args()
    if args.rescore:
        rescore(args.rescore)
        return
    if not args.chain or not args.prompt:
        sys.exit("--chain and --prompt are required for a run")
    chain = llm_chain.parse_chain(args.chain)
    if len(chain) != 1:
        sys.exit("--chain must be one provider:model")
    loaded = {}
    for p in args.prompt:
        bw.PROMPTS["incident"] = p
        loaded[p] = bw.read_prompt("incident")
    out = ROOT / "eval" / "results" / "incident_type_check" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    rows = []
    for run in range(1, args.runs + 1):
        for case in load_cases():
            for prompt in args.prompt:
                system, template = loaded[prompt]
                user = re.sub(r"\{\{incident_text\}\}", lambda m: case["text"], template)
                answer = llm_chain.complete(system, user, json_mode=True, chain=chain)
                found, conf = "error", ""
                if "error" not in answer:
                    try:
                        j = json.loads(answer["candidates"][0]["content"]["parts"][0]["text"])
                        found, conf = j.get("incident_type", "missing"), j.get("type_confidence", "")
                    except ValueError:
                        found = "not_json"
                rows.append({"prompt": prompt, "case": case["id"], "group": case["group"], "run": run, "found_type": found, "confidence": conf,
                             "correct": found in case["ok"], "allowed": "|".join(sorted(case["ok"]))})
                time.sleep(args.pace_seconds)
        print("run", run, "done", flush=True)
    with open(out / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summarise(rows, args.prompt)
    for prompt in args.prompt:
        for r in rows:
            if r["prompt"] == prompt and not r["correct"] and r["found_type"] not in ("error", "not_json"):
                print("  wrong:", prompt, r["case"], r["group"], "run", r["run"], "->", r["found_type"], "(allowed", r["allowed"] + ")")
    print("saved in", out)


if __name__ == "__main__":
    main()
