"""Run the Vision agent prompt(s) on the test images with one pinned model and save the raw answers.

    python scripts/vision_bench.py --model ollama:qwen3-vl:4b-instruct --runs 3 --prompt vision/v1.md --prompt vision/v2.md

Uses the prompt files as the n8n workflow does (system prompt and user template of prompts/vision/*.md; v1 gets the incident text in the user
message, v2 does not) and the model chain code with a pinned model, so a result is attributable to one model. With several --prompt the calls are
interleaved (same image, same run, prompt after prompt) so the model state is the same for all.

Measures, all computed from the answers:
  json_valid, schema_valid   backend/schemas/vision.schema.json
  false_categories           observations whose category is listed as 'absent' for that image in vision/test_images/GROUND_TRUTH.json
  missing_required           'required' categories with no observation
  absence_observations       observations that only say something is not there ("No people are visible")
  place_words                the answer names a place or region (Nabeul, Tunisia, Europe, Italy, Nepal ...), which the prompt forbids
  quality_flagged            for images marked low_quality (blurred, dark): the answer sets image_usable false or lists quality_issues
  latency                    seconds per call, the first call after loading a model is cold
The ground truth was written by one reader (see that file). Whether an observation is TRUE beyond these tags needs a person looking at the image.

Output: eval/results/vision_bench/<stamp>/ with one JSON per call and summary.csv.
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
from backend import llm_chain, vision_tools  # noqa: E402

SCHEMA = json.loads((ROOT / "backend" / "schemas" / "vision.schema.json").read_text(encoding="utf-8"))
TRUTH = json.loads((ROOT / "vision" / "test_images" / "GROUND_TRUTH.json").read_text(encoding="utf-8"))
ABSENCE = re.compile(r"^\s*(no|none|not)\b|\bno (visible|clear|obvious|identifiable)\b|\bnot (visible|present)\b", re.I)
PLACES = re.compile(r"nabeul|tunis|tunisia|europ|ital(y|ian)|nepal|asia|africa|mediterranean|france|french", re.I)


def load_prompt(path):
    """path is a prompt file, or 'tta:<file>' for the three-view path with that prompt."""
    bw.PROMPTS["vision"] = path.removeprefix("tta+high:").removeprefix("tta:")
    return bw.read_prompt("vision")


def analyse_tta(image_bytes, mime, system, user, chain, policy="majority", answers_out=None):
    """The three-view path as n8n runs it, but in one process: three views, one call each, answers that fit the schema are merged.

    Returns (merged answer or None, total seconds, number of views that answered, last error). answers_out, a dict, receives the answers of the views so that
    another merge policy can be applied to the SAME answers (paired conditions)."""
    answers, total, error = [], 0.0, ""
    if answers_out is not None and "answers" in answers_out:   # the views of this image and run were already called by the sibling condition
        answers, total, error = answers_out["answers"], answers_out["seconds"], answers_out["error"]
        return (vision_tools.merge(answers, requested=3, policy=policy) if answers else None), round(total, 1), len(answers), error
    for view in vision_tools.make_variants(image_bytes, mime):
        llm_chain.reset_cooldowns()
        started = time.time()
        answer = llm_chain._complete_once(system, user, True, llm_chain.encode_image(__import__("base64").b64decode(view["image_b64"]), view["image_mime"]), chain,
                                          llm_chain.TIMEOUT_LOCAL, False, trusted=True)
        total += time.time() - started
        if "error" in answer:
            att = answer["x_llm"]["attempts"]
            error = att[-1].get("reason", "") if att else answer["error"]["message"][:100]
            continue
        try:
            parsed = json.loads(answer["candidates"][0]["content"]["parts"][0]["text"])
        except ValueError:
            error = "not JSON"
            continue
        if list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(parsed)):
            error = "schema"
            continue
        answers.append({"name": view["name"], "result": parsed})
    if answers_out is not None:
        answers_out.update({"answers": answers, "seconds": total, "error": error})
    return (vision_tools.merge(answers, requested=3, policy=policy) if answers else None), round(total, 1), len(answers), error


def measures(image_name, result):
    truth = TRUTH.get(image_name, {})
    # an observation that only says something is NOT there ("No visible standing water", category flood_water) is not a claim that it is there
    observed = [o.get("category") for o in result.get("observations", []) if isinstance(o, dict) and not ABSENCE.search(o.get("description", ""))]
    return {
        "false_categories": ",".join(sorted({c for c in observed if c in truth.get("absent", [])})),
        "missing_required": ",".join(c for c in truth.get("required", []) if c not in observed),
        "absence_observations": sum(1 for o in result.get("observations", []) if isinstance(o, dict) and ABSENCE.search(o.get("description", ""))),
        "place_words": bool(PLACES.search(json.dumps(result, ensure_ascii=False))),
        # only for images marked low_quality in GROUND_TRUTH.json: did the answer flag a problem (image_usable false or quality_issues listed)?
        "quality_flagged": (result.get("image_usable") is False or bool(result.get("quality_issues"))
                            or ((result.get("reliability") or {}).get("category_agreement_score") is not None and result["reliability"]["category_agreement_score"] < 0.5)) if truth.get("low_quality") else "",
        "agreement": (result.get("reliability") or {}).get("category_agreement_score", ""),
    }


def table_tta(rows, prompts):
    for prompt in prompts:
        if not prompt.startswith(("tta:", "tta+high:")):
            continue
        r = [x for x in rows if x["prompt"] == prompt]
        ok = [x for x in r if x["json_valid"]]
        ag = [float(x["agreement"]) for x in ok if x.get("agreement") not in ("", None)]
        low = [float(x["agreement"]) for x in ok if x.get("agreement") not in ("", None) and x.get("quality_flagged") not in ("", None)]
        normal = [float(x["agreement"]) for x in ok if x.get("agreement") not in ("", None) and x.get("quality_flagged") in ("", None)]
        print(f"{prompt}: calls with fewer than 3 views answering: {sum(1 for x in r if str(x.get('views_ok')) not in ('3',))}; mean agreement {sum(ag) / len(ag):.2f}" if ag else f"{prompt}: no agreement values",
              f"| ordinary images {sum(normal) / len(normal):.2f}" if normal else "", f"| low-quality images {sum(low) / len(low):.2f}" if low else "")


def table(rows, prompts):
    print("prompt         calls  json  schema  false_obs(calls)  missing_req(calls)  absence_obs(total)  place_words(calls)  quality_flagged  median_s")
    for prompt in prompts:
        r = [x for x in rows if x["prompt"] == prompt]
        ok = [x for x in r if x["json_valid"]]
        secs = sorted(x["seconds"] for x in r)
        print(f"{prompt:<14} {len(r):<6} {len(ok):<5} {sum(bool(x['schema_valid']) for x in r):<7} {sum(1 for x in ok if x['false_categories']):<17} "
              f"{sum(1 for x in ok if x['missing_required']):<19} {sum(x['absence_observations'] for x in ok):<19} {sum(1 for x in ok if x['place_words']):<19} "
              f"{sum(1 for x in ok if x.get('quality_flagged') in (True, 'True'))}/{sum(1 for x in ok if x.get('quality_flagged') not in ('', None)):<14} {secs[len(secs) // 2]}")


def rescore(folder):
    """Recompute the measures from the saved answers, for example after the rule of a measure changed. No model call."""
    rows = []
    for f in sorted(folder.glob("*_run*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        row = d["row"]
        if d.get("result"):
            row.update(measures(row["image"], d["result"]))
        rows.append(row)
    table(rows, sorted({r["prompt"] for r in rows}))
    table_tta(rows, sorted({r["prompt"] for r in rows}))
    for r in rows:
        if r["false_categories"]:
            print("  false observation:", r["prompt"], r["incident"], "run", r["run"], r["false_categories"])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rescore", metavar="FOLDER", help="recompute the measures of a finished run from its saved answers and print the table (no model call)")
    parser.add_argument("--model", help="provider:model, one model (required for a run)")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--prompt", action="append", help="prompt file under prompts/, repeatable (default vision/v1.md)")
    parser.add_argument("--only", nargs="+")
    args = parser.parse_args()
    if args.rescore:
        rescore(Path(args.rescore))
        return
    if not args.model:
        sys.exit("--model is required")
    chain = llm_chain.parse_chain(args.model)
    if len(chain) != 1:
        sys.exit("--model must be one provider:model")
    prompts = args.prompt or ["vision/v1.md"]
    loaded = {p: load_prompt(p) for p in prompts}
    out = ROOT / "eval" / "results" / "vision_bench" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    rows = []
    view_cache = {}
    incidents = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval" / "incidents").glob("*.json"))]
    # images that belong to no incident file carry an invented report text in GROUND_TRUTH.json
    used = {i.get("image") for i in incidents}
    incidents += [{"id": name.rsplit(".", 1)[0], "image": name, "text": t["report_text"]} for name, t in TRUTH.items() if name.endswith(".jpg") and name not in used and t.get("report_text")]
    for run in range(1, args.runs + 1):
        for inc in incidents:
            if not inc.get("image") or (args.only and inc["id"] not in args.only):
                continue
            image_path = ROOT / "vision" / "test_images" / inc["image"]
            if not image_path.exists():
                print("missing image", inc["image"])
                continue
            image = llm_chain.encode_image(image_path.read_bytes(), "image/jpeg")
            for prompt in prompts:
                system, template = loaded[prompt]
                user = re.sub(r"\{\{incident_text\}\}", lambda m: inc["text"], template)
                llm_chain.reset_cooldowns()  # a timeout on one call (a sleeping PC, a model reload) must not turn every later call into 'cooling down'
                views_ok = ""
                if prompt.startswith(("tta:", "tta+high:")):
                    # tta: and tta+high: share the three model answers per image and run; only the merge policy differs
                    shared = view_cache.setdefault((inc["id"], run), {})
                    tta_result, seconds, views_ok, tta_error = analyse_tta(image_path.read_bytes(), "image/jpeg", system, user, chain,
                                                                           policy="keep_high" if prompt.startswith("tta+high:") else "majority", answers_out=shared)
                    answer = {"error": {"message": tta_error or "no view answered"}, "x_llm": {"attempts": [{"reason": tta_error or "no view answered"}]}} if tta_result is None else \
                        {"candidates": [{"content": {"parts": [{"text": json.dumps(tta_result)}]}}]}
                else:
                    started = time.time()
                    answer = llm_chain._complete_once(system, user, True, image, chain, llm_chain.TIMEOUT_LOCAL, False, trusted=True)
                    seconds = round(time.time() - started, 1)
                row = {"model": args.model, "prompt": prompt, "incident": inc["id"], "image": inc["image"], "run": run, "seconds": seconds,
                       "answered": "error" not in answer, "json_valid": False, "schema_valid": False, "n_observations": "", "schema_errors": "",
                       "false_categories": "", "missing_required": "", "absence_observations": "", "place_words": "", "quality_flagged": "", "agreement": "", "views_ok": views_ok}
                result = None
                if "error" in answer:
                    att = answer["x_llm"]["attempts"]
                    row["schema_errors"] = (att[-1].get("reason", "") if att else answer["error"]["message"][:100])
                else:
                    try:
                        result = json.loads(answer["candidates"][0]["content"]["parts"][0]["text"])
                        row["json_valid"] = True
                        errors = list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(result))
                        row["schema_valid"] = not errors
                        row["schema_errors"] = "; ".join(e.message[:80] for e in errors[:3])
                        row["n_observations"] = len(result.get("observations", []))
                        row.update(measures(inc["image"], result))
                    except ValueError:
                        pass
                rows.append(row)
                name = args.model.replace("/", "_").replace(":", "_") + "_" + prompt.replace("/", "_").replace(":", "_").replace("+", "_").replace(".md", "")
                (out / f"{name}_{inc['id']}_run{run}.json").write_text(json.dumps({"row": row, "incident_text": inc["text"], "result": result}, ensure_ascii=False, indent=1), encoding="utf-8")
                print({k: row[k] for k in ("prompt", "incident", "run", "seconds", "json_valid", "schema_valid", "n_observations", "false_categories", "missing_required", "absence_observations", "place_words")}, flush=True)
    if rows:
        fields = list(rows[0])
        with open(out / "summary.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print()
        table(rows, prompts)
        table_tta(rows, prompts)
    print("saved in", out)


if __name__ == "__main__":
    main()
