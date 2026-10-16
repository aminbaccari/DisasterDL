"""Read the node outputs and timings of an n8n execution from the n8n SQLite database (copied out of the container).

    docker cp n8n-disasterai-test:/home/node/.n8n/database.sqlite <dir>/database.sqlite
    python scripts/export_n8n_execution.py <dir>/database.sqlite --list
    python scripts/export_n8n_execution.py <dir>/database.sqlite --execution 12 --out eval/results/real/exec12.json

n8n stores run data in the 'flatted' format (a JSON array in which objects point to each other by index). This script decodes it
and writes {node: [{seconds, error, output}]}. Seconds come from n8n's own executionTime per node run (milliseconds / 1000).
"""
import argparse
import json
import sqlite3
from pathlib import Path


def unflatted(text):
    """Decode the 'flatted' format: items[0] is the root, strings that are indexes refer to other items."""
    items = json.loads(text)
    cache = {}

    def resolve(index):
        if index in cache:
            return cache[index]
        value = items[index]
        if isinstance(value, list):
            out = []
            cache[index] = out
            out.extend(resolve_ref(v) for v in value)
        elif isinstance(value, dict):
            out = {}
            cache[index] = out
            for k, v in value.items():
                out[k] = resolve_ref(v)
        else:
            out = value
            cache[index] = out
        return out

    def resolve_ref(v):
        # in flatted every child that is a container or a string is stored as the string form of an index
        if isinstance(v, str) and v.isdigit() and int(v) < len(items):
            return resolve(int(v))
        return v

    return resolve(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("db")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--execution", type=int)
    parser.add_argument("--out")
    args = parser.parse_args()
    con = sqlite3.connect(args.db)
    if args.list:
        for row in con.execute("select id, workflowId, status, startedAt, stoppedAt from execution_entity order by id"):
            print(row)
        return
    row = con.execute("select data from execution_data where executionId = ?", (args.execution,)).fetchone()
    data = unflatted(row[0])
    run_data = data["resultData"]["runData"]
    result = {}
    for node, runs in run_data.items():
        result[node] = []
        for run in runs:
            main_out = (run.get("data") or {}).get("main") or [[]]
            items = [{k: v for k, v in i["json"].items() if k != "system"} for out in main_out if out for i in out]  # the long system prompts are in prompts/
            result[node].append({"seconds": round(run.get("executionTime", 0) / 1000, 2), "error": run.get("error"), "output": items})
    text = json.dumps(result, ensure_ascii=False, indent=1, default=str)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote", args.out, "nodes:", len(result))
    else:
        print(text[:3000])


if __name__ == "__main__":
    main()
