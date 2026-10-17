"""Run the Vision agent prompt on the test images with one pinned model and save the raw answers for a person to read.

    python scripts/vision_bench.py --model ollama:qwen3-vl:4b --runs 2
    python scripts/vision_bench.py --model ollama:qwen3-vl:4b --prompt vision/v1.md --only fire_01

Uses the vision prompt file as the n8n workflow does (system prompt and user template of prompts/vision/*.md) and the model chain code with a
pinned model, so a result is attributable to one model. It measures what a machine can: JSON valid, schema valid (backend/schemas/vision.schema.json),
latency per call, the first (cold) call separately. Whether the observations are TRUE needs a person looking at the image: the output file lists
the observations next to the image name for that. Nothing here scores image understanding.

Output: eval/results/vision_bench/<stamp>/<model>_<incident>_run<n>.json and summary.csv.
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

import jsonschema  # noqa: E402

import build_workflow as bw  # noqa: E402
from backend import llm_chain  # noqa: E402

SCHEMA = json.loads((ROOT / "backend" / "schemas" / "vision.schema.json").read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="provider:model, one model")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--prompt", default="vision/v1.md")
    parser.add_argument("--only", nargs="+")
    args = parser.parse_args()
    chain = llm_chain.parse_chain(args.model)
    if len(chain) != 1:
        sys.exit("--model must be one provider:model")
    bw.PROMPTS["vision"] = args.prompt
    system, template = bw.read_prompt("vision")
    out = ROOT / "eval" / "results" / "vision_bench" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    rows = []
    incidents = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval" / "incidents").glob("*.json"))]
    for inc in incidents:
        if not inc.get("image") or (args.only and inc["id"] not in args.only):
            continue
        image_path = ROOT / "vision" / "test_images" / inc["image"]
        if not image_path.exists():
            print("missing image", inc["image"])
            continue
        image = llm_chain.encode_image(image_path.read_bytes(), "image/jpeg")
        user = re.sub(r"\{\{incident_text\}\}", inc["text"], template)
        for run in range(1, args.runs + 1):
            started = time.time()
            answer = llm_chain._complete_once(system, user, True, image, chain, llm_chain.TIMEOUT_LOCAL, False, trusted=True)
            seconds = round(time.time() - started, 1)
            row = {"model": args.model, "prompt": args.prompt, "incident": inc["id"], "image": inc["image"], "run": run, "seconds": seconds,
                   "answered": "error" not in answer, "json_valid": False, "schema_valid": False, "n_observations": "", "consistent_with_report": "", "image_usable": ""}
            result = None
            if "error" in answer:
                row["error"] = answer["x_llm"]["attempts"][-1].get("reason", "") if answer["x_llm"]["attempts"] else answer["error"]["message"][:100]
            else:
                try:
                    result = json.loads(answer["candidates"][0]["content"]["parts"][0]["text"])
                    row["json_valid"] = True
                    errors = list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(result))
                    row["schema_valid"] = not errors
                    row["schema_errors"] = "; ".join(e.message[:80] for e in errors[:3])
                    row["n_observations"] = len(result.get("observations", []))
                    row["consistent_with_report"] = result.get("consistent_with_report", "")
                    row["image_usable"] = result.get("image_usable", "")
                except ValueError:
                    pass
            rows.append(row)
            name = args.model.replace("/", "_").replace(":", "_")
            (out / f"{name}_{inc['id']}_run{run}.json").write_text(json.dumps({"row": row, "incident_text": inc["text"], "result": result}, ensure_ascii=False, indent=1), encoding="utf-8")
            print({k: row[k] for k in ("incident", "run", "seconds", "answered", "json_valid", "schema_valid", "n_observations", "consistent_with_report")}, flush=True)
    if rows:
        fields = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
        with open(out / "summary.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    print("saved in", out)


if __name__ == "__main__":
    main()
