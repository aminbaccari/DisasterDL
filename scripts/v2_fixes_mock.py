"""MOCK check of the workflow changes of 2026-10-16 (vision failure status, early-exit text). Not a model test.

Needs: n8n with the workflow built for the RAG service on port 8011, and that RAG service started with
    LLM_CHAIN=gemini:mock GEMINI_API_KEY=mock GEMINI_BASE_URL=http://localhost:8020
This script starts the MOCK Gemini itself (modes normal and vision_fail).

    python scripts/v2_fixes_mock.py --url http://localhost:5679/webhook/incident
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from failure_paths_mock import FIRE, VAGUE, wait_port  # noqa: E402


def post(url, text, lang, image=None):
    files = {"incident_text": (None, text), "output_language": (None, lang)}
    handle = None
    if image:
        handle = open(ROOT / "vision" / "test_images" / image, "rb")
        files["image"] = (image, handle, "image/jpeg")
    try:
        body = requests.post(url, files=files, timeout=300).json()
    finally:
        if handle:
            handle.close()
    return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", default=str(ROOT / "eval" / "results" / "n8n_mock" / "v2_fixes.json"))
    args = parser.parse_args()
    results = {}
    for mode in ("normal", "vision_fail"):
        proc = subprocess.Popen([sys.executable, "-m", "backend.mock_gemini", "--port", "8020", "--mode", mode], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            assert wait_port(8020), "mock did not start"
            for name, text, lang, image in (("fire_with_image", FIRE, "en", "fire_01.jpg"), ("vague_no_image", VAGUE, "fr", None), ("vague_with_image", VAGUE, "fr", "edge_02_conflict.jpg")):
                if mode == "vision_fail" and name != "fire_with_image":
                    continue
                b = post(args.url, text, lang, image)
                rep = b.get("report") or {}
                results[f"{mode}/{name}"] = {
                    "label": "MOCK", "status": b.get("status"), "image_status": rep.get("image_status"), "validation": (b.get("validation") or {}).get("status"),
                    "violations": [v["check"] for v in (b.get("validation") or {}).get("violations", [])],
                    "degraded": [d["step"] + ": " + d["reason"][:60] for d in b.get("degraded_steps", [])],
                    "markdown_head": b.get("report_markdown", "")[:420]}
        finally:
            proc.terminate()
            proc.wait()
            time.sleep(1)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
