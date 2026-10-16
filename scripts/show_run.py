"""Print one saved pipeline run next to the manual_checks of its incident, for a person to score.

    python scripts/show_run.py eval/results/real_chain2/<stamp> fire_01 1

Prints the facts a reader needs for each check: models used and seconds per step, the vision answer, the report's location,
conflicts, coverage, recommendations (with entry ids), uncertainties and the report text. It scores nothing: scoring is a human
judgement, recorded in docs/EVIDENCE_LOG.md.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(folder, incident_id, run):
    record = json.loads((Path(folder) / f"{incident_id}_run{run}.json").read_text(encoding="utf-8"))
    incident = json.loads((ROOT / "eval" / "incidents" / f"{incident_id}.json").read_text(encoding="utf-8"))
    body = record.get("raw_response")
    print(f"=== {incident_id} run {run}: {record['seconds']} s, http {record.get('status_code')}, image {record['image_status']}")
    print("TEXT:", incident["text"])
    print("MANUAL CHECKS:")
    for check in incident["manual_checks"]:
        print("  -", check)
    if not isinstance(body, dict):
        print("NO RESPONSE:", record.get("error"))
        return
    print("status:", body.get("status"), "| severity:", body.get("severity"), "| coverage:", body.get("knowledge_coverage"))
    print("steps:", [(m["step"], str(m["model"]).split("/")[-1][:18], m.get("seconds")) for m in body.get("models_used", [])])
    print("validation:", body.get("validation"))
    print("degraded:", body.get("degraded_steps"))
    report = body.get("report") or {}
    risk = body.get("risk") or {}
    print("image_status:", report.get("image_status"), "| location:", report.get("location"))
    print("observed:", [(o["text"][:90], o["confidence"]) for o in report.get("observed", [])])
    print("conflicts:", report.get("assessment", {}).get("conflicts"))
    print("risk.conflicts:", risk.get("conflicts_between_sources"))
    print("reported:", [r["text"][:80] for r in report.get("reported", [])])
    print("recommendations:", [(r["entry_id"], r["text"][:90]) for r in report.get("recommendations", [])])
    print("no_guidance:", (report.get("knowledge") or {}).get("no_guidance_statement"))
    print("uncertainties:", report.get("uncertainties"))
    print("information_needed:", report.get("information_needed"))
    print("--- report_markdown ---")
    print(body.get("report_markdown", "")[:2600])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
