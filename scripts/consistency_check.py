"""Does the comparison of image and report still work when the Vision agent no longer sees the report?

    python scripts/consistency_check.py --bench eval/results/vision_bench/<stamp> --chain groq:openai/gpt-oss-120b --pace-seconds 5

A = vision v1 output (it compared with the report itself) + risk v2.   B = vision v2 output (image only) + risk v3 (it compares).
The vision answers are the real ones saved by scripts/vision_bench.py (same images, same local model). The other inputs of the Risk agent
(incident JSON, knowledge JSON) are the canned MOCK ones of backend/mock_gemini.py, the same for A and B, so only the vision input and the Risk
prompt differ. Only the Risk call is a real model call (one pinned text model). This is not an end-to-end test.

Expectations written before the run (this is the reading of the incident files and of the images):
  edge_02_conflict  the report says flooding on a main road, the image shows a dry backyard: conflicts_between_sources must NOT be empty
  flood_01          report and image agree (flooded street): a conflict here is a false alarm, a place-name conflict ("Nabeul against European architecture") counts
  fire_01, structural_01  not scored: the report mentions things the image may not show (houses, five storeys), a reader decides. The conflicts are listed.
"""
import argparse
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
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import build_workflow as bw  # noqa: E402
from backend import llm_chain, mock_gemini as mock  # noqa: E402

RISK_SCHEMA = json.loads((ROOT / "backend" / "schemas" / "risk.schema.json").read_text(encoding="utf-8"))
PLACE = re.compile(r"nabeul|tunis|tunisia|europ|ital(y|ian)|architectur", re.I)


def fill(template, values):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(values[m.group(1)]), template)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bench", required=True, help="folder written by scripts/vision_bench.py with both vision/v1.md and vision/v2.md")
    parser.add_argument("--chain", required=True, help="one provider:model for the Risk agent")
    parser.add_argument("--pace-seconds", type=int, default=0)
    args = parser.parse_args()
    chain = llm_chain.parse_chain(args.chain)
    variants = {"A": ("vision_v1", "risk_assessment/v2.md"), "B": ("vision_v2", "risk_assessment/v3.md")}
    incidents = {json.loads(p.read_text(encoding="utf-8"))["id"]: json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval" / "incidents").glob("*.json"))}
    out = ROOT / "eval" / "results" / "consistency_check" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    rows = []
    for f in sorted(Path(args.bench).glob("*_run*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        row, vision = d["row"], d["result"]
        if not vision:
            continue
        variant = "A" if row["prompt"].endswith("v1.md") else "B"
        inc = incidents[row["incident"]]
        text = inc["text"]
        incident_json = mock.mock_incident(f"<incident_report>\n{text}\n</incident_report>")
        knowledge_json = {"relevant_guidance": [], "ignored_chunks": [], "coverage": "none", "gaps": ["canned: no passages in this test"]}
        bw.PROMPTS["risk"] = variants[variant][1]
        system, template = bw.read_prompt("risk")
        user = fill(template, {"incident_json": json.dumps(incident_json, ensure_ascii=False), "vision_json_or_null": json.dumps(vision, ensure_ascii=False),
                               "knowledge_json": json.dumps(knowledge_json)})
        started = time.time()
        answer = llm_chain.complete(system, user, json_mode=True, chain=chain)
        seconds = round(time.time() - started, 1)
        risk = None
        if "error" not in answer:
            try:
                risk = json.loads(answer["candidates"][0]["content"]["parts"][0]["text"])
            except ValueError:
                risk = None
        schema_ok = bool(risk) and not list(jsonschema.Draft202012Validator(RISK_SCHEMA).iter_errors(risk))
        conflicts = (risk or {}).get("conflicts_between_sources", []) if risk else None
        res = {"variant": variant, "vision_prompt": row["prompt"], "risk_prompt": variants[variant][1], "incident": row["incident"], "run": row["run"], "seconds": seconds,
               "answered": risk is not None, "schema_ok": schema_ok, "n_conflicts": None if conflicts is None else len(conflicts),
               "place_conflict": bool(conflicts) and any(PLACE.search(c) for c in conflicts)}
        rows.append(res)
        (out / f"{variant}_{row['incident']}_run{row['run']}.json").write_text(json.dumps({"row": res, "conflicts": conflicts, "error": answer.get("error")}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(res, flush=True)
        time.sleep(args.pace_seconds)
    print("\nvariant incident          calls answered  conflicts_non_empty  place_conflicts")
    for variant in ("A", "B"):
        for incident in sorted({r["incident"] for r in rows}):
            r = [x for x in rows if x["variant"] == variant and x["incident"] == incident]
            ok = [x for x in r if x["answered"]]
            print(f"{variant:<7} {incident:<17} {len(r):<5} {len(ok):<9} {sum(1 for x in ok if x['n_conflicts']):<20} {sum(1 for x in ok if x['place_conflict'])}")
    print("saved in", out)


if __name__ == "__main__":
    main()
