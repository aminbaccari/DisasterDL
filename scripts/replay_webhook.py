"""A stand-in for the n8n webhook that REPLAYS answers saved from real runs. For trying the test console without spending model quota.

    python scripts/replay_webhook.py --port 5690
    # then in the console: target "Custom URL" = http://localhost:5690/webhook/incident?mode=degraded&delay=4

Every answer is a saved output of an earlier real run (eval/results/vision_chain_e2e), or a copy of it with one field changed to show a failure path.
It is NOT the workflow: tick "This n8n uses MOCK agents" in the console so the results are labelled. Query parameters of the URL:
    mode   saved (default: the saved fire_01 answer exactly as it was, its real status is "degraded") | ok (a copy made clean: status ok, no degraded steps)
           | conflict | degraded | flagged | repaired | repair_discarded | rejected | notjson | empty | error500 | notfound
    delay  seconds to wait before answering (default 3)
"""
import argparse
import copy
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
SAVED = ROOT / "eval" / "results" / "vision_chain_e2e"


def load(name):
    path = sorted(SAVED.glob(f"*/{name}.json"))[-1]
    raw = json.loads(path.read_text(encoding="utf-8"))["raw_response"]
    return json.loads(raw) if isinstance(raw, str) else raw


def answer(mode):
    """(http status, content type, body text)."""
    ok = load("fire_01_run1")
    if mode == "conflict":
        body = load("edge_02_conflict_run1")
    elif mode == "ok":
        body = copy.deepcopy(ok)
        body["status"] = "ok"
        body["degraded_steps"] = []
        body["validation"] = {"status": "pass", "repaired": False, "violations": []}
    elif mode == "degraded":
        body = copy.deepcopy(ok)
        body["status"] = "degraded"
        body["report"]["image_status"] = "analysis_failed"
        body["report"]["observed"] = []
        body["degraded_steps"] = [{"step": "vision", "reason": "all vision models failed or are cooling down: the report uses the text only"}] + body.get("degraded_steps", [])
    elif mode == "flagged":
        body = copy.deepcopy(ok)
        body["status"] = "flagged"
        body["validation"] = {"status": "fail", "repaired": True, "violations": [{"check": "scope", "message": "the report tells people to enter a damaged building"}],
                              "first_violations": [{"check": "scope", "message": "the report tells people to enter a damaged building"}, {"check": "citations", "message": "entry FI-99 was not retrieved"}]}
    elif mode == "repair_discarded":
        body = copy.deepcopy(ok)
        body["status"] = "flagged"
        original = [{"check": "no_guidance", "message": "coverage is 'good' although FI-01 (fire scope note) was retrieved"}]
        body["validation"] = {"status": "fail", "repaired": True, "repair_discarded": True, "violations": original, "first_violations": original,
                              "repair_violations": [{"check": "schema", "message": f"(root): '{k}' is a required property"} for k in ("uncertainties", "information_needed", "disclaimer", "report_markdown")]}
        body["degraded_steps"] = [{"step": "repair", "reason": "the repaired report failed 4 check(s) against 1 for the original, so the original report is returned"}]
    elif mode == "repaired":
        body = copy.deepcopy(ok)
        body["validation"] = {"status": "pass", "repaired": True, "violations": [], "first_violations": [{"check": "location", "message": "location 'the hills' is not a named place"}]}
    elif mode == "rejected":
        body = {"status": "rejected", "error": "incident_text is missing or too short", "incident_type": None, "severity": None, "report_markdown": "", "degraded_steps": []}
    elif mode == "notjson":
        return 200, "text/html", "<html><body>Workflow could not be started</body></html>"
    elif mode == "empty":
        return 200, "application/json", ""
    elif mode == "error500":
        return 500, "application/json", json.dumps({"message": "Workflow execution failed"})
    elif mode == "notfound":
        return 404, "application/json", json.dumps({"code": 404, "message": "The requested webhook \"POST incident\" is not registered."})
    else:
        body = ok
    return 200, "application/json", json.dumps(body, ensure_ascii=False)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("replay:", fmt % args)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        q = parse_qs(urlparse(self.path).query)
        mode = q.get("mode", ["ok"])[0]
        time.sleep(float(q.get("delay", ["3"])[0]))
        code, ctype, text = answer(mode)
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=5690)
    args = parser.parse_args()
    print(f"Replaying saved answers on http://localhost:{args.port}/webhook/incident (REPLAY, not the workflow)")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()  # threaded: a browser keeps idle connections open


if __name__ == "__main__":
    main()
