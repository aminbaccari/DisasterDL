"""Ready-made inputs for the test console: the six fixed incidents, plus the test images that carry an invented report text."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "vision" / "test_images"
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def load_samples():
    """Ordered dict label -> sample. A sample has: id, text, language (output language), image (path or None), expected, note, manual_checks."""
    samples = {}
    for path in sorted((ROOT / "eval" / "incidents").glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        image = IMAGES / d["image"] if d.get("image") and (IMAGES / d["image"]).exists() else None
        samples[f"Fixed incident: {d['id']}"] = {"id": d["id"], "text": d["text"], "language": d.get("output_language", "en"), "image": image,
                                                 "expected": d.get("expected"), "note": d.get("designed_to_test", ""), "manual_checks": d.get("manual_checks", [])}
    truth_path = IMAGES / "GROUND_TRUTH.json"
    if truth_path.exists():
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        used = {s["image"].name for s in samples.values() if s["image"]}
        for name, t in truth.items():
            if name.endswith(".jpg") and name not in used and t.get("report_text") and (IMAGES / name).exists():
                samples[f"Test image: {name.rsplit('.', 1)[0]}"] = {"id": name.rsplit(".", 1)[0], "text": t["report_text"], "language": "en", "image": IMAGES / name,
                                                                    "expected": None, "note": t.get("comment", ""), "manual_checks": []}
    return samples


def image_tuple(path):
    """(bytes, filename, mime) as the client expects, or None."""
    if not path:
        return None
    p = Path(path)
    return p.read_bytes(), p.name, MIME.get(p.suffix.lower(), "application/octet-stream")
