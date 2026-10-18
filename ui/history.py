"""Saved runs: one JSON file per run in eval/results/ui_runs/, with the input image next to it. The raw answer is kept as received."""
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "eval" / "results" / "ui_runs"


def save_run(result, url, profile, mock, text, language, image=None, sample_id=None, runs_dir=None):
    """Write the run. result is a ui.client.RunResult. Returns the path of the JSON file."""
    runs_dir = runs_dir or RUNS_DIR
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    slug = re.sub(r"[^a-z0-9_]+", "_", (sample_id or "free_text").lower())[:30]
    image_file = None
    if image:
        suffix = Path(image[1]).suffix or ".img"
        image_file = f"{stamp}_{slug}{suffix}"
        (runs_dir / image_file).write_bytes(image[0])
    record = {"saved_at": stamp, "sample_id": sample_id, "url": url, "profile": profile, "mock": bool(mock), "language": language, "text": text,
              "image_file": image_file, "kind": result.kind, "seconds": round(result.seconds, 1), "http_status": result.http_status,
              "message": result.message, "response": result.body}
    path = runs_dir / f"{stamp}_{slug}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def list_runs(runs_dir=None, limit=50):
    """Newest first. Each item is the saved record plus its path."""
    runs_dir = runs_dir or RUNS_DIR
    if not runs_dir.exists():
        return []
    items = []
    for p in sorted(runs_dir.glob("*.json"), reverse=True)[:limit]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        d["path"] = str(p)
        items.append(d)
    return items


def image_bytes(record, runs_dir=None):
    runs_dir = runs_dir or RUNS_DIR
    name = record.get("image_file")
    p = runs_dir / name if name else None
    return p.read_bytes() if p and p.exists() else None


def compare(a, b):
    """Differences between two saved runs, as (label, value in a, value in b) for the fields that matter."""
    ra, rb = a.get("response") or {}, b.get("response") or {}

    def models(r):
        return ", ".join(f"{m.get('step')}={(m.get('model') or '?').split('/')[-1]}" for m in r.get("models_used") or [])

    fields = [("Kind", a.get("kind"), b.get("kind")), ("Incident type", ra.get("incident_type"), rb.get("incident_type")), ("Severity", ra.get("severity"), rb.get("severity")),
              ("Coverage", ra.get("knowledge_coverage"), rb.get("knowledge_coverage")), ("Seconds", a.get("seconds"), b.get("seconds")),
              ("Validation", (ra.get("validation") or {}).get("status"), (rb.get("validation") or {}).get("status")),
              ("Degraded steps", len(ra.get("degraded_steps") or []), len(rb.get("degraded_steps") or [])),
              ("Entries", " ".join(ra.get("retrieved_entry_ids") or []), " ".join(rb.get("retrieved_entry_ids") or [])),
              ("Prompt versions", json.dumps(ra.get("prompt_versions") or {}), json.dumps(rb.get("prompt_versions") or {})), ("Models", models(ra), models(rb))]
    return [(label, x, y) for label, x, y in fields if x != y]
