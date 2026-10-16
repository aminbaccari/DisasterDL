"""Run the fixed test incidents against the n8n webhook and save the raw outputs.

Examples, from the project root:
    python scripts/run_incidents.py --url http://localhost:5678/webhook-test/incident
    python scripts/run_incidents.py --url <url> --runs 2 --only fire_01 flood_01

The workflow is expected to answer with JSON containing:
    incident_type, severity, report_markdown, degraded_steps (list), prompt_versions
Fields that are missing are recorded as empty, not guessed.

Automatic checks cover incident type and severity only. The manual_checks in each
incident file are for a human to score.
"""
import argparse
import csv
import json
import mimetypes
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def load_incidents(incidents_dir, only=None):
    incidents = []
    for path in sorted(Path(incidents_dir).glob("*.json")):
        incident = json.loads(path.read_text(encoding="utf-8"))
        if only and incident["id"] not in only:
            continue
        incidents.append(incident)
    return incidents


def check_expected(incident, body):
    expected = incident.get("expected", {})
    checks = {}
    if "incident_type" in expected:
        checks["incident_type_ok"] = body.get("incident_type") == expected["incident_type"]
    if "severity_acceptable" in expected:
        checks["severity_ok"] = body.get("severity") in expected["severity_acceptable"]
    checks["has_report"] = bool(body.get("report_markdown"))
    return checks


def run_one(url, incident, images_dir, timeout, allow_missing_images):
    """Return (record, skipped_reason). record is None when skipped."""
    # Every field goes in the multipart body (a None file name makes a plain text field),
    # so requests without an image have the same shape as requests with one.
    files = {
        "incident_text": (None, incident["text"]),
        "output_language": (None, incident.get("output_language", "en")),
    }
    image_status = "none"
    image_name = incident.get("image")
    handle = None
    if image_name:
        image_path = Path(images_dir) / image_name
        if image_path.exists():
            handle = open(image_path, "rb")
            # The part needs its own Content-Type: without it n8n 2.43 delivered the JPEG as a garbled text field
            # (body.image) and the Vision branch was skipped silently in the run of 2026-10-16.
            mime = mimetypes.guess_type(image_name)[0] or "application/octet-stream"
            files["image"] = (image_name, handle, mime)
            image_status = "sent"
        elif allow_missing_images:
            image_status = "missing_text_only"
        else:
            return None, f"image {image_name} not found in {images_dir}"

    started = time.time()
    record = {"incident_id": incident["id"], "image_status": image_status}
    try:
        response = requests.post(url, files=files, timeout=timeout)
        record["status_code"] = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = {}
            record["error"] = "response was not JSON"
        record["raw_response"] = body if body else response.text[:2000]
    except requests.RequestException as exc:
        body = {}
        record["status_code"] = None
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["raw_response"] = None
    finally:
        if handle:
            handle.close()
    record["seconds"] = round(time.time() - started, 1)
    if not isinstance(body, dict):
        body = {}
    record["incident_type"] = body.get("incident_type", "")
    record["severity"] = body.get("severity", "")
    record["degraded_steps"] = body.get("degraded_steps", [])
    record["prompt_versions"] = body.get("prompt_versions", "")
    record["checks"] = check_expected(incident, body)
    return record, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="n8n webhook URL (test or production)")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--only", nargs="+", help="incident ids to run")
    parser.add_argument("--timeout", type=int, default=600, help="seconds per request")
    parser.add_argument("--allow-missing-images", action="store_true")
    parser.add_argument("--incidents-dir", default=str(ROOT / "eval" / "incidents"))
    parser.add_argument("--images-dir", default=str(ROOT / "vision" / "test_images"))
    parser.add_argument("--results-dir", default=str(ROOT / "eval" / "results"))
    args = parser.parse_args()

    incidents = load_incidents(args.incidents_dir, args.only)
    if not incidents:
        sys.exit("No incidents found.")

    out_dir = Path(args.results_dir) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    skipped = []

    for incident in incidents:
        for run in range(1, args.runs + 1):
            record, reason = run_one(
                args.url, incident, args.images_dir, args.timeout, args.allow_missing_images
            )
            if record is None:
                skipped.append((incident["id"], reason))
                print(f"SKIP  {incident['id']}: {reason}")
                break
            record["run"] = run
            (out_dir / f"{incident['id']}_run{run}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            checks = record["checks"]
            print(
                f"{incident['id']:<20} run {run}  http={record['status_code']}  "
                f"{record['seconds']}s  type={record['incident_type'] or '-'}  "
                f"severity={record['severity'] or '-'}  "
                f"type_ok={checks.get('incident_type_ok')}  severity_ok={checks.get('severity_ok')}"
            )
            rows.append(
                {
                    "incident_id": incident["id"],
                    "run": run,
                    "image_status": record["image_status"],
                    "status_code": record["status_code"],
                    "seconds": record["seconds"],
                    "incident_type": record["incident_type"],
                    "severity": record["severity"],
                    "incident_type_ok": checks.get("incident_type_ok", ""),
                    "severity_ok": checks.get("severity_ok", ""),
                    "has_report": checks.get("has_report", ""),
                    "status": (record.get("raw_response") or {}).get("status", "") if isinstance(record.get("raw_response"), dict) else "",
                    "validation": ((record.get("raw_response") or {}).get("validation") or {}).get("status", "") if isinstance(record.get("raw_response"), dict) else "",
                    "models_used": ";".join(
                        f"{m.get('step')}={m.get('provider')}:{m.get('model')}"
                        for m in ((record.get("raw_response") or {}).get("models_used") or [])
                    ) if isinstance(record.get("raw_response"), dict) else "",
                    "degraded_steps": ";".join(
                        d if isinstance(d, str) else f"{d.get('step')}: {str(d.get('reason'))[:90]}" for d in record["degraded_steps"]
                    )
                    if isinstance(record["degraded_steps"], list)
                    else record["degraded_steps"],
                    "prompt_versions": json.dumps(record["prompt_versions"], ensure_ascii=False)
                    if not isinstance(record["prompt_versions"], str)
                    else record["prompt_versions"],
                    "error": record.get("error", ""),
                }
            )

    if rows:
        with open(out_dir / "summary.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        ok = sum(1 for r in rows if r["incident_type_ok"] is True)
        typed = sum(1 for r in rows if r["incident_type_ok"] != "")
        print(f"\nSaved {len(rows)} runs to {out_dir}")
        print(f"Incident type matched expected in {ok} of {typed} runs.")
    if skipped:
        print(f"{len(skipped)} incident(s) skipped. See messages above.")


if __name__ == "__main__":
    main()
