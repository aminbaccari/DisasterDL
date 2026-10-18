"""Does the RAG-query agent retrieve better than a direct query?  (comparison named in prompts/rag_query/v1.md)

    python scripts/rag_query_vs_direct.py --chain groq:openai/gpt-oss-120b --runs 3

For each case of rag/eval/incident_cases_v1.json (pre-registered, 12 witness reports with the NEEDS a good result must cover):
  1. the real Incident Understanding agent (the workflow's default prompt) turns the text into incident JSON, once per case, one pinned model;
  2. three conditions retrieve passages exactly as the workflow does (strategy section, topic filter from the incident type, final list = best 8 by score):
       agent        the RAG-query agent (prompts/rag_query/v1.md) writes 3 queries from the incident JSON; k=4 per query, merged like MERGE_PASSAGES.  --runs runs.
       direct_facts ONE query built from incident_type and reported_facts (what the prompt names as the comparison); k=8
       direct_text  ONE query = the raw report text; k=8   (no model call at all)
  3. a need is met when one of the final 8 passages carries one of its any_of entry ids. Measures: share of needs met, cases with every need met.
The topic filter uses the type found by the incident agent, so a wrong type hurts all three conditions equally; it is reported.
Only the query writing differs between conditions. No result here says anything about the quality of the final report.

Output: eval/results/rag_query_vs_direct/<stamp>/ (incidents.json, one JSON per case, summary.csv).
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

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import build_workflow as bw  # noqa: E402
from backend import llm_chain  # noqa: E402
from rag import embedder, store  # noqa: E402

TOPIC_OF = {"forest_fire": "fire", "flood": "flood", "structural_emergency": "structural"}
PLACE = re.compile(r"nabeul|tunis|sfax|sousse|gabès|gabes|monastir|bizerte|kairouan", re.I)


BALANCE = False


def search(query, topic, k):
    return store.search(embedder.embed_queries([query])[0], "section", k=k, topic=topic, balance_languages=BALANCE)


def merged_agent(queries, topic):
    """Same as MERGE_PASSAGES in scripts/build_workflow.py: best score per chunk, top 8."""
    best = {}
    for q in queries:
        for r in search(q, topic, 4):
            if r["chunk_id"] not in best or r["score"] > best[r["chunk_id"]]["score"]:
                best[r["chunk_id"]] = r
    return sorted(best.values(), key=lambda r: -r["score"])[:8]


def needs_met(case, passages):
    ids = {i for p in passages for i in p.get("entry_ids", [])}
    met = [bool(ids & set(n["any_of"])) for n in case["needs"]]
    return met, sorted(ids)


def call_json(system, user, chain, tries=5, wait=30):
    """One pinned model on a free tier hits per-minute and daily limits; wait and ask again, and say why in the end."""
    reason = ""
    for attempt in range(tries):
        answer = llm_chain.complete(system, user, json_mode=True, chain=chain)
        if "error" not in answer:
            try:
                return json.loads(answer["candidates"][0]["content"]["parts"][0]["text"]), ""
            except ValueError:
                reason = "not JSON"
        else:
            att = (answer.get("x_llm") or {}).get("attempts") or []
            reason = (att[-1].get("reason") or att[-1].get("status", "error")) if att else "error"
        time.sleep(wait)
    return None, reason


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chain", required=True, help="one provider:model for the incident and query agents")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--balance-languages", action="store_true", help="keep at least k // 2 results per language (D12), as the workflow now does")
    parser.add_argument("--incident-prompt", default="incident_understanding/v2.md", help="the workflow default")
    parser.add_argument("--query-prompt", default="rag_query/v1.md")
    parser.add_argument("--pace-seconds", type=int, default=2)
    parser.add_argument("--cases", default=str(ROOT / "rag" / "eval" / "incident_cases_v1.json"))
    args = parser.parse_args()
    global BALANCE
    BALANCE = args.balance_languages
    chain = llm_chain.parse_chain(args.chain)
    if len(chain) != 1:
        sys.exit("--chain must be one provider:model")
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    bw.PROMPTS["incident"] = args.incident_prompt
    isys, itemplate = bw.read_prompt("incident")
    bw.PROMPTS["rag_queries"] = args.query_prompt
    qsys, qtemplate = bw.read_prompt("rag_queries")
    out = ROOT / "eval" / "results" / "rag_query_vs_direct" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    rows, incidents = [], {}
    for case in cases:
        user = re.sub(r"\{\{incident_text\}\}", lambda m: case["text"], itemplate)
        inc, err = call_json(isys, user, chain)
        if not inc:
            print(case["id"], "incident agent failed:", err)
            continue
        incidents[case["id"]] = inc
        topic = TOPIC_OF.get(inc.get("incident_type"))
        facts = inc.get("reported_facts") or []
        slim = {k: v for k, v in inc.items() if not k.startswith("_")}
        runs = []
        conditions = {"direct_facts": [f"{inc.get('incident_type')}: " + ". ".join(facts)], "direct_text": [case["text"]]}
        for name, qs in conditions.items():
            passages = search(qs[0], topic, 8) if topic else []
            runs.append((name, 1, qs, passages))
        for run in range(1, args.runs + 1):
            res, err = call_json(qsys, re.sub(r"\{\{incident_json\}\}", lambda m: json.dumps(slim, ensure_ascii=False), qtemplate), chain)
            queries = [q["text"] for q in (res or {}).get("queries", []) if isinstance(q, dict) and isinstance(q.get("text"), str) and len(q["text"]) > 2][:3]
            if not queries:
                queries = [". ".join(facts)[:200]]  # the workflow's own fallback
            runs.append(("agent", run, queries, merged_agent(queries, topic) if topic else []))
            time.sleep(args.pace_seconds)
        for name, run, qs, passages in runs:
            met, ids = needs_met(case, passages)
            rows.append({"case": case["id"], "language": case["language"], "expected_topic": case["topic"], "found_topic": topic or "", "topic_ok": topic == case["topic"],
                         "condition": name, "run": run, "n_needs": len(met), "n_met": sum(met), "all_met": all(met), "queries": " | ".join(qs),
                         "place_in_query": any(PLACE.search(q) for q in qs), "entry_ids": " ".join(ids)})
        print(case["id"], "topic", topic, {n: [r["n_met"] for r in rows if r["case"] == case["id"] and r["condition"] == n] for n in ("direct_facts", "direct_text", "agent")}, flush=True)
    (out / "incidents.json").write_text(json.dumps(incidents, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    report(rows)
    print("saved in", out)


def report(rows):
    print("\ncondition      rows  needs met   cases with all needs met   topic ok   place name in query")
    for name in ("direct_text", "direct_facts", "agent"):
        r = [x for x in rows if x["condition"] == name]
        if not r:
            continue
        print(f"{name:<14} {len(r):<5} {sum(x['n_met'] for x in r)}/{sum(x['n_needs'] for x in r):<8} {sum(x['all_met'] for x in r)}/{len(r):<22} {sum(x['topic_ok'] for x in r)}/{len(r):<9} {sum(x['place_in_query'] for x in r)}")
    print("\nby language (needs met):")
    for lang in ("en", "fr"):
        parts = []
        for name in ("direct_text", "direct_facts", "agent"):
            r = [x for x in rows if x["condition"] == name and x["language"] == lang]
            if r:
                parts.append(f"{name} {sum(x['n_met'] for x in r)}/{sum(x['n_needs'] for x in r)}")
        print(" ", lang, " | ".join(parts))
    cases = sorted({x["case"] for x in rows})
    better = worse = same = 0
    for c in cases:
        a = [x["n_met"] for x in rows if x["case"] == c and x["condition"] == "agent"]
        d = [x["n_met"] for x in rows if x["case"] == c and x["condition"] == "direct_facts"]
        if not a or not d:
            continue
        mean = sum(a) / len(a)
        better += mean > d[0]
        worse += mean < d[0]
        same += mean == d[0]
    print(f"\nagent (mean of its runs) against direct_facts, per case: better {better}, same {same}, worse {worse}")


if __name__ == "__main__":
    main()
