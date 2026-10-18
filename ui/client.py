"""Calls to the n8n webhook and to the services around it. No Streamlit here, so it is testable offline.

The webhook answers once, when the whole run ends (20 s to a few minutes), with one JSON object. Every way a call can fail is turned into
an error `kind` and a plain-language hint, so that the screen never shows a raw stack trace.
"""
import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent

# The team instance first (docker-compose.yml publishes 5678), then the test container used in this project. A custom URL can be typed in the sidebar.
PROFILES = {
    "Team n8n, port 5678": {"url": "http://localhost:5678/webhook/incident", "mock": False},
    "Test n8n, port 5680": {"url": "http://localhost:5680/webhook/incident", "mock": False},
    # saved real answers, no model call: python scripts/replay_webhook.py. Add ?mode=degraded&delay=5 in "Custom URL" to see a failure path.
    "Replay of saved answers, port 5690": {"url": "http://localhost:5690/webhook/incident?delay=3", "mock": True},
}
DEFAULT_PROFILE = "Team n8n, port 5678"
RAG_URL = os.getenv("RAG_URL", "http://localhost:8010")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

SUPPORTED_IMAGES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MIN_TEXT = 3

HINTS = {
    "unreachable": "Nothing answers at this address. Start n8n (`docker compose up -d`) or pick another target in the sidebar.",
    "timeout": "The run took longer than the timeout. The workflow may still be running in n8n; check its executions list, or raise the timeout in the sidebar.",
    "not_listening": "n8n answered 404: the workflow is not active at this path. Open the workflow in n8n and activate it (or press Execute workflow when you use the test URL).",
    "bad_request": "The workflow refused the request. Check the text and the image.",
    "server_error": "n8n or one of its nodes failed (HTTP 5xx). Open the execution in n8n to see which node.",
    "not_json": "The answer is not JSON. The workflow may have crashed before its response node, or the URL points to something else.",
    "empty": "The answer was empty. The workflow may have stopped before its response node.",
}


@dataclass
class RunResult:
    kind: str                       # ok | degraded | flagged | rejected | an error kind of HINTS
    seconds: float = 0.0
    http_status: int | None = None
    body: dict | None = None
    message: str = ""
    hint: str = ""
    problems: list = field(default_factory=list)

    @property
    def has_report(self):
        return bool(self.body and self.body.get("report"))


def check_input(text, image_bytes=None, image_mime=None):
    """Problems with the input, found before anything is sent. Empty list means fine."""
    problems = []
    if len((text or "").strip()) < MIN_TEXT:
        problems.append(f"Describe the incident in at least {MIN_TEXT} characters.")
    if image_bytes is not None:
        if image_mime not in SUPPORTED_IMAGES:
            problems.append(f"Image type {image_mime or 'unknown'} is not supported. Use PNG, JPEG or WebP.")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            problems.append(f"The image is {len(image_bytes) / 1e6:.1f} MB; the limit is {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    return problems


def classify_body(body):
    """kind for an answer that is valid JSON: the workflow's own status decides."""
    status = body.get("status")
    if status == "rejected":
        return "rejected"
    if status in ("ok", "degraded", "flagged"):
        return status
    return "degraded" if body.get("report") else "not_json"


def post_incident(url, text, language="en", image=None, timeout=300):
    """POST the incident. image is (bytes, filename, mime) or None. Returns a RunResult, never raises."""
    problems = check_input(text, image[0] if image else None, image[2] if image else None)
    if problems:
        return RunResult(kind="bad_request", message=" ".join(problems), hint="Fix the input and run again.", problems=problems)
    files = {"image": (image[1], image[0], image[2])} if image else None
    started = time.time()
    try:
        r = requests.post(_loopback(url), data={"incident_text": text, "output_language": language}, files=files, timeout=timeout)
    except requests.exceptions.ConnectionError:
        return RunResult("unreachable", time.time() - started, message=f"Could not connect to {url}.", hint=HINTS["unreachable"])
    except requests.exceptions.Timeout:
        return RunResult("timeout", time.time() - started, message=f"No answer after {timeout} s.", hint=HINTS["timeout"])
    except requests.exceptions.RequestException as exc:
        return RunResult("unreachable", time.time() - started, message=str(exc)[:200], hint=HINTS["unreachable"])
    seconds = time.time() - started
    if r.status_code == 404:
        return RunResult("not_listening", seconds, 404, message="HTTP 404 from n8n.", hint=HINTS["not_listening"])
    if r.status_code >= 500:
        return RunResult("server_error", seconds, r.status_code, message=f"HTTP {r.status_code}. {r.text[:200]}", hint=HINTS["server_error"])
    if not r.content.strip():
        return RunResult("empty", seconds, r.status_code, message="Empty answer.", hint=HINTS["empty"])
    try:
        body = r.json()
        if not isinstance(body, dict):
            raise ValueError("not an object")
    except ValueError:
        return RunResult("not_json", seconds, r.status_code, message=r.text[:200], hint=HINTS["not_json"])
    if r.status_code >= 400 and body.get("status") != "rejected":
        return RunResult("bad_request", seconds, r.status_code, body, message=str(body.get("error") or body.get("message") or r.text[:200]), hint=HINTS["bad_request"])
    kind = classify_body(body)
    message = str(body.get("error") or "") if kind == "rejected" else ""
    return RunResult(kind, seconds, r.status_code, body, message=message)


def _loopback(url):
    """On Windows 'localhost' is tried on IPv6 first and a closed port then costs seconds: use the IPv4 address."""
    return url.replace("://localhost", "://127.0.0.1")


def _get(url, timeout=2):
    try:
        r = requests.get(_loopback(url), timeout=timeout)
        return r.status_code, (r.json() if "json" in r.headers.get("content-type", "") else r.text)
    except (requests.exceptions.RequestException, ValueError):
        return None, None


def n8n_base(webhook_url):
    return webhook_url.split("/webhook")[0]


def check_services(webhook_url, rag_url=RAG_URL, ollama_url=OLLAMA_URL):
    """One row per thing the workflow depends on: name, state (ok | warn | down), detail. The checks run in parallel (about 2 s at worst)."""
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_n8n = pool.submit(_get, n8n_base(webhook_url) + "/healthz")
        f_rag = pool.submit(_get, rag_url + "/health")
        f_llm = pool.submit(_get, rag_url + "/llm/status")
        f_oll = pool.submit(_get, ollama_url + "/api/tags")
        code, _ = f_n8n.result()
        rows = [("n8n", "ok" if code == 200 else "down", "answers" if code == 200 else "no answer at " + n8n_base(webhook_url))]
        code, _ = f_rag.result()
        rows.append(("RAG and validation service", "ok" if code == 200 else "down", f"{rag_url}" if code == 200 else f"no answer at {rag_url}: start uvicorn rag.service:app --port 8010"))
        code, status = f_llm.result()
        if code == 200 and isinstance(status, dict):
            for label, key in (("Text models", "chain"), ("Vision models", "vision_chain")):
                chain = status.get(key) or []
                ready = [m for m in chain if m.get("key", True) and not m.get("cooling_seconds")]
                state = "ok" if ready else ("warn" if chain else "down")
                rows.append((label, state, f"{len(ready)} of {len(chain)} ready" + ("" if ready else " (cooling down or no key)")))
        else:
            rows.append(("Model chains", "down", "unknown: the RAG service did not answer"))
        code, tags = f_oll.result()
    models = [m.get("name") for m in (tags or {}).get("models", [])] if isinstance(tags, dict) else []
    rows.append(("Local vision model (Ollama)", "ok" if models else ("warn" if code == 200 else "down"),
                 ", ".join(models) if models else ("running, no model pulled" if code == 200 else "not running (image runs fall back to cloud models)")))
    free = shutil.disk_usage(str(ROOT)).free / 1e9
    rows.append(("Disk space", "ok" if free > 5 else ("warn" if free > 1 else "down"), f"{free:.1f} GB free"))
    return rows
