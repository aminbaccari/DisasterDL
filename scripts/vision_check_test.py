"""Test of a narrow second vision call: yes/no questions about objects the report names.

    python scripts/vision_check_test.py --vision ollama:qwen3-vl:4b-instruct --text groq:openai/gpt-oss-120b --runs 3

Design (prototype, not in the n8n workflow yet):
  1. A text agent (prompts/vision_questions/v1.md) turns the reported facts into at most 4 yes/no questions about things a photo can show.
  2. The vision model answers them from the image only (prompts/vision_check/v1.md). It never sees the report.
  3. Plain code turns every "no" into a conflict: "Report: <claim>. Image: <question> answered no (<evidence>)". "unclear" gives nothing.
This restores the check that vision v2 (image only) cannot do: "flames near the first houses" against an image without houses.

Inputs: the incident JSON is the canned MOCK one (backend/mock_gemini.py), the same text for every run. The text call and the vision calls are real.
Expectations written before the run (by one reader, from the incident texts and the images):
  fire_01           the claim about houses must give a conflict; the claims about flames and smoke must not
  edge_02_conflict  the claim about flooding on a road must give a conflict
  flood_01          report and image agree: every conflict is a false alarm unless a reader finds it right (listed for reading)
  structural_01     not scored, conflicts are listed for reading
Output: eval/results/vision_check/<stamp>/ (one JSON per incident and run, summary.csv).
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
from backend import llm_chain, mock_gemini as mock  # noqa: E402


# Written before the first run. 'expected_no': a question matching this should be answered "no" (the thing is not in the image): that is the true conflict.
# Every other "no" answer on that incident is a false alarm, unless a reader finds it right (structural_01 is only listed).
EXPECT = {
    "fire_01": {"expected_no": r"house|building"},
    "edge_02_conflict": {"expected_no": r"flood|water|road"},
    "flood_01": {"expected_no": None},
    "structural_01": None,
}
PLACE = re.compile(r"nabeul|tunis|tunisia|europ|ital(y|ian)|nepal|region|country|town of", re.I)


def score(incident_id, checks):
    """n_no, expected conflict found and false alarms from the saved checks and the expectations above."""
    exp = EXPECT.get(incident_id)
    nos = [c for c in checks if c["answer"] == "no"]
    row = {"n_no": len(nos), "expected_conflict_found": "", "false_alarms": ""}
    if exp is None:
        return row
    pattern = exp["expected_no"]
    true_conflicts = [c for c in nos if pattern and re.search(pattern, c["question"], re.I)]
    if pattern:
        row["expected_conflict_found"] = bool(true_conflicts)
    row["false_alarms"] = len([c for c in nos if c not in true_conflicts])
    return row


def call_json(system, user, chain, image=None, timeout=None):
    answer = llm_chain._complete_once(system, user, True, image, chain, timeout or llm_chain.TIMEOUT_LOCAL, False, trusted=bool(image))
    if "error" in answer:
        return None, answer["x_llm"]["attempts"][-1].get("reason", "error") if answer["x_llm"]["attempts"] else "error"
    try:
        return json.loads(answer["candidates"][0]["content"]["parts"][0]["text"]), ""
    except ValueError:
        return None, "not JSON"


def summarise(rows):
    for iid in sorted({r["incident"] for r in rows}):
        r = [x for x in rows if x["incident"] == iid]
        found = [x["expected_conflict_found"] for x in r if x["expected_conflict_found"] != ""]
        alarms = [x["false_alarms"] for x in r if x["false_alarms"] != ""]
        secs = sorted(x["seconds"] for x in r)
        print(f"{iid:<17} {len(r):<5} {str(sum(found)) + '/' + str(len(found)) if found else '-':<24} {str(sum(1 for a in alarms if a)) + '/' + str(len(alarms)) if alarms else '-':<13} {sum(x['place_question'] for x in r):<16} {secs[len(secs) // 2]}")


def rescore(folder):
    """Recompute the measures of a finished run from its saved checks (no model call)."""
    rows = []
    for f in sorted(Path(folder).glob("*_run*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        row = d["row"]
        row.update(score(row["incident"], d["checks"]))
        rows.append(row)
    print("incident          runs  expected conflict found  false alarms  place questions  median s")
    summarise(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rescore", metavar="FOLDER", help="recompute the measures of a finished run (no model call)")
    parser.add_argument("--vision", help="provider:model for the vision call")
    parser.add_argument("--text", help="provider:model for the question writer")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--questions", default="vision_questions/v1.md")
    parser.add_argument("--check", default="vision_check/v1.md")
    parser.add_argument("--pace-seconds", type=int, default=2)
    args = parser.parse_args()
    if args.rescore:
        rescore(args.rescore)
        return
    if not (args.vision and args.text):
        sys.exit("--vision and --text are required for a run")
    vchain, tchain = llm_chain.parse_chain(args.vision), llm_chain.parse_chain(args.text)
    if len(vchain) != 1 or len(tchain) != 1:
        sys.exit("--vision and --text must each be one provider:model")
    bw.PROMPTS["vision"] = args.questions
    qsys, qtemplate = bw.read_prompt("vision")
    bw.PROMPTS["vision"] = args.check
    csys, ctemplate = bw.read_prompt("vision")
    out = ROOT / "eval" / "results" / "vision_check" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    incidents = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval" / "incidents").glob("*.json"))]
    rows = []
    for run in range(1, args.runs + 1):
        for inc in incidents:
            if not inc.get("image"):
                continue
            image = llm_chain.encode_image((ROOT / "vision" / "test_images" / inc["image"]).read_bytes(), "image/jpeg")
            incident_json = mock.mock_incident(f"<incident_report>\n{inc['text']}\n</incident_report>")
            slim = {"reported_facts": incident_json["reported_facts"]}
            qs, err1 = call_json(qsys, re.sub(r"\{\{incident_json\}\}", lambda m: json.dumps(slim, ensure_ascii=False), qtemplate), tchain, timeout=60)
            questions = [q for q in (qs or {}).get("questions", []) if isinstance(q, dict) and q.get("question")][:4]
            numbered = "\n".join(f"{i}. {q['question']}" for i, q in enumerate(questions, 1))
            answers, err2, seconds = [], "", 0.0
            if questions:
                started = time.time()
                res, err2 = call_json(csys, re.sub(r"\{\{numbered_questions\}\}", lambda m: numbered, ctemplate), vchain, image=image)
                seconds = round(time.time() - started, 1)
                answers = (res or {}).get("answers", [])
            by_id = {a.get("id"): a for a in answers if isinstance(a, dict)}
            checks, conflicts = [], []
            for i, q in enumerate(questions, 1):
                a = by_id.get(i, {})
                verdict = a.get("answer", "missing")
                checks.append({"claim": q.get("claim", ""), "question": q["question"], "answer": verdict, "evidence": a.get("evidence", "")})
                if verdict == "no":
                    conflicts.append(f"Report: {q.get('claim', '')}. Image: not visible ({a.get('evidence', '')}).")
            row = score(inc["id"], checks)
            row.update({"incident": inc["id"], "run": run, "questions_prompt": args.questions, "check_prompt": args.check, "n_questions": len(questions),
                        "n_yes": sum(c["answer"] == "yes" for c in checks), "n_unclear": sum(c["answer"] in ("unclear", "missing") for c in checks),
                        "place_question": any(PLACE.search(c["question"]) for c in checks), "seconds": seconds, "error": err1 or err2})
            rows.append(row)
            (out / f"{inc['id']}_run{run}.json").write_text(json.dumps({"row": row, "checks": checks, "conflicts": conflicts}, ensure_ascii=False, indent=1), encoding="utf-8")
            print(row, flush=True)
            time.sleep(args.pace_seconds)
    with open(out / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\nincident          runs  expected conflict found  false alarms  place questions  median s")
    summarise(rows)
    print("saved in", out)


if __name__ == "__main__":
    main()
