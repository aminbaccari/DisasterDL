"""Before and after test of two prompt sets on the same incidents, same model chain, interleaved so quota or load hits both alike.

    python scripts/before_after.py run --before-url http://localhost:5679/webhook/incident_before --after-url http://localhost:5679/webhook/incident_after --runs 3
    python scripts/before_after.py analyse eval/results/before_after/<stamp>

BEFORE = incident prompt v1 and report prompt v3, AFTER = incident v2 and report v4 (workflows built with scripts/build_workflow.py --prompt,
see docs/EVIDENCE_LOG.md). Each round runs every fixed incident through both workflows (the order of the two variants swaps every round).
The run stops by itself after STOP_AFTER consecutive runs that failed only because every model of the chain was out of quota, and says so.

Measures (all computed from the saved responses, nothing is scored by hand):
  completed      a report object came back
  schema_fail    /validate reported a schema violation on the final report (after the repair pass)
  repaired       the repair pass was used
  image_ok       report.image_status matches what happened (not_provided without image, analysis_failed when the Vision step failed, else analysed)
  location_ok    report location is null where the incident file expects not stated, or contains the expected name
  language_ok    for French incidents, the free-text lists are mostly French (word-list heuristic, see french_share)
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
sys.path.insert(0, str(ROOT / "scripts"))

from run_incidents import load_incidents, run_one  # noqa: E402

STOP_AFTER = 3
FR_WORDS = set("le la les des du de et est un une pour nombre lieu type personnes danger sur dans qui que ne pas au aux en d l a ou été état".split())
EN_WORDS = set("the of and is a an for number location type people danger on in that not to whether any status been".split())


def french_share(texts):
    """Share of French words among the French and English words found in the texts (None when there is nothing to judge)."""
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", " ".join(texts).lower())
    fr = sum(1 for w in words if w in FR_WORDS or "'" in w and w.split("'")[0] in FR_WORDS)
    en = sum(1 for w in words if w in EN_WORDS)
    return None if fr + en == 0 else fr / (fr + en)


def exhausted(record):
    body = record.get("raw_response")
    if not isinstance(body, dict):
        return False
    reasons = " ".join(str(d.get("reason")) for d in body.get("degraded_steps", []) if isinstance(d, dict))
    return "every model in the chain failed" in reasons and body.get("status") in ("degraded", "rejected") and not body.get("report")


def run(args):
    incidents = load_incidents(ROOT / "eval" / "incidents")
    out = ROOT / "eval" / "results" / "before_after" / datetime.now().strftime("%Y%m%d-%H%M%S")
    (out / "before").mkdir(parents=True)
    (out / "after").mkdir(parents=True)
    urls = {"before": args.before_url, "after": args.after_url}
    streak, stopped = 0, ""
    for rnd in range(1, args.runs + 1):
        order = ["before", "after"] if rnd % 2 else ["after", "before"]
        for incident in incidents:
            for variant in order:
                record, reason = run_one(urls[variant], incident, str(ROOT / "vision" / "test_images"), args.timeout, True)
                if record is None:
                    print("SKIP", incident["id"], reason)
                    continue
                record["run"], record["variant"] = rnd, variant
                (out / variant / f"{incident['id']}_run{rnd}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
                body = record.get("raw_response") if isinstance(record.get("raw_response"), dict) else {}
                print(f"round {rnd} {variant:<6} {incident['id']:<18} {record['seconds']:>6}s status={body.get('status')} val={(body.get('validation') or {}).get('status')}", flush=True)
                streak = streak + 1 if exhausted(record) else 0
                if streak >= STOP_AFTER:
                    stopped = f"stopped after {streak} consecutive runs with every model out of quota (round {rnd}, {variant}, {incident['id']})"
                    break
            if stopped:
                break
        if stopped:
            break
    (out / "STOPPED.txt").write_text(stopped or "completed all rounds", encoding="utf-8")
    print(stopped or "completed all rounds", "\nSaved in", out)
    analyse_dir(out)


def metrics(incident, record):
    body = record.get("raw_response") if isinstance(record.get("raw_response"), dict) else {}
    report = body.get("report") or {}
    expected = incident.get("expected", {})
    degraded = [d for d in body.get("degraded_steps", []) if isinstance(d, dict)]
    exhausted_run = exhausted(record) or any("every model in the chain failed" in str(d.get("reason")) for d in degraded if d.get("step") == "incident understanding")
    sent_image = record.get("image_status") == "sent"
    vision_failed = any(d["step"] == "vision" for d in degraded)
    expect_status = "not_provided" if not sent_image else ("analysis_failed" if vision_failed else "analysed")
    row = {"variant": record["variant"], "incident": incident["id"], "run": record["run"], "seconds": record["seconds"], "status": body.get("status", ""),
           "quota_failure": exhausted_run, "completed": bool(report), "schema_fail": "", "repaired": "", "image_ok": "", "location": "", "location_ok": "", "language_share": "", "language_ok": ""}
    if report:
        violations = (body.get("validation") or {}).get("violations", [])
        row["schema_fail"] = any(v["check"] == "schema" for v in violations)
        row["repaired"] = bool((body.get("validation") or {}).get("repaired"))
        row["image_ok"] = report.get("image_status") == expect_status
        location = report.get("location")
        row["location"] = location or ""
        if "location_text_contains" in expected:
            row["location_ok"] = bool(location) and expected["location_text_contains"].lower() in location.lower()
        else:
            row["location_ok"] = location in (None, "")
    if incident.get("output_language") == "fr":
        texts = (report.get("uncertainties", []) + report.get("information_needed", [])) if report else body.get("missing_information", [])
        share = french_share(texts)
        row["language_share"] = "" if share is None else round(share, 2)
        row["language_ok"] = "" if share is None else share >= 0.5
    return row


def analyse_dir(folder):
    folder = Path(folder)
    incidents = {i["id"]: i for i in load_incidents(ROOT / "eval" / "incidents")}
    rows = []
    for variant in ("before", "after"):
        for f in sorted((folder / variant).glob("*_run*.json")):
            record = json.loads(f.read_text(encoding="utf-8"))
            rows.append(metrics(incidents[record["incident_id"]], record))
    if not rows:
        return
    with open(folder / "summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\nvariant  runs  quota_fail  completed  schema_fail  repaired  image_ok  location_ok  language_ok   (counts, only runs that were not lost to quota are in the rates)")
    for variant in ("before", "after"):
        v = [r for r in rows if r["variant"] == variant]
        valid = [r for r in v if not r["quota_failure"]]
        done = [r for r in valid if r["completed"]]

        def count(key, pool):
            judged = [r for r in pool if r[key] != ""]
            return f"{sum(1 for r in judged if r[key] is True)}/{len(judged)}"

        print(f"{variant:<8} {len(v):<5} {len(v) - len(valid):<11} {len(done)}/{len(valid):<8} {count('schema_fail', done):<12} {count('repaired', done):<9} {count('image_ok', done):<9} {count('location_ok', done):<12} {count('language_ok', valid)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--before-url", required=True)
    r.add_argument("--after-url", required=True)
    r.add_argument("--runs", type=int, default=3)
    r.add_argument("--timeout", type=int, default=900)
    a = sub.add_parser("analyse")
    a.add_argument("folder")
    args = parser.parse_args()
    run(args) if args.cmd == "run" else analyse_dir(args.folder)


if __name__ == "__main__":
    main()
