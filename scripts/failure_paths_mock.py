"""Trigger the workflow failure paths on purpose with the MOCK Gemini (n8n and the RAG service must be running).

    python scripts/failure_paths_mock.py --url http://localhost:5679/webhook/incident

Cases (each is one call; every result is MOCK, it proves the n8n branches, not model behaviour):
  too_short            text of one character          -> HTTP 400
  gemini_unreachable   mock not running             -> retry, then degraded response listing the error
  normal_vague         the edge_01 report             -> needs_more_information, nothing guessed
  mock gemini modes    http500, invalid_json          -> one retry, then degraded (never silent)
                       bad_report                     -> /validate fails, one repair pass fixes it
                       bad_report_always              -> repair fails too, response flagged
Stop the RAG service yourself to test the "RAG service down" branch, see docs/N8N_WORKFLOW_PLAN.md.
"""
import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
FIRE = "Smoke is rising from the hills behind the village and flames are visible near the first houses. A strong wind is blowing toward the village."
VAGUE = "Il y a un problème grave près du port, venez vite."


def wait_port(port, seconds=20):
    end = time.time() + seconds
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


def call(url, text, lang="en"):
    started = time.time()
    r = requests.post(url, files={"incident_text": (None, text), "output_language": (None, lang)}, timeout=240)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:200]}
    return r.status_code, body, round(time.time() - started, 1)


def summary(code, body, seconds):
    keep = {k: body.get(k) for k in ("status", "incident_type", "severity", "knowledge_coverage") if k in body}
    if "validation" in body and body["validation"]:
        keep["validation"] = {"status": body["validation"]["status"], "repaired": body["validation"]["repaired"], "checks": sorted({v["check"] for v in body["validation"]["violations"]})}
    keep["degraded"] = [f"{d['step']}: {d['reason'][:70]}" for d in body.get("degraded_steps", [])]
    return {"label": "MOCK", "http": code, "seconds": seconds, **keep}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--mock-port", type=int, default=8020)
    parser.add_argument("--out", default=str(ROOT / "eval" / "results" / "n8n_mock" / "failure_paths.json"))
    args = parser.parse_args()
    results = {}
    results["too_short"] = summary(*call(args.url, "x"))
    results["gemini_unreachable"] = summary(*call(args.url, FIRE))  # nothing listens on the mock port yet
    for mode in ("normal_vague", "http500", "invalid_json", "bad_report", "bad_report_always"):
        proc = subprocess.Popen([sys.executable, "-m", "backend.mock_gemini", "--port", str(args.mock_port), "--mode", "normal" if mode == "normal_vague" else mode], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            if not wait_port(args.mock_port):
                results[mode] = {"error": "mock did not start"}
                continue
            results[mode] = summary(*call(args.url, VAGUE, "fr")) if mode == "normal_vague" else summary(*call(args.url, FIRE))
        finally:
            proc.terminate()
            proc.wait()
            time.sleep(1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
