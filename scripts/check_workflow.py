"""Static checks of the generated n8n workflow. This does NOT run n8n.

    python scripts/check_workflow.py [n8n/workflows/disasterai.json]

Checks: JSON parses, every connection points to an existing node, every node is reachable from the webhook,
every $('Node name') reference in an expression or Code node names an existing node, the JavaScript of every Code node
and every {{ expression }} is syntactically valid (checked with node --check), no API key text is present.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def js_syntax_error(source):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    result = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    Path(path).unlink()
    return result.stderr.strip().splitlines()[:4] if result.returncode else None


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def check(path):
    wf = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = []
    names = {n["name"] for n in wf["nodes"]}
    if len(names) != len(wf["nodes"]):
        problems.append("duplicate node names")
    edges = {}
    for a, c in wf["connections"].items():
        if a not in names:
            problems.append(f"connection from unknown node {a!r}")
        for outs in c["main"]:
            for t in outs:
                if t["node"] not in names:
                    problems.append(f"{a!r} connects to unknown node {t['node']!r}")
                edges.setdefault(a, set()).add(t["node"])
    start = [n["name"] for n in wf["nodes"] if n["type"].endswith(".webhook")]
    seen, todo = set(start), list(start)
    while todo:
        for nxt in edges.get(todo.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    problems += [f"node {n!r} is not reachable from the webhook" for n in sorted(names - seen)]
    refs = 0
    for node in wf["nodes"]:
        for text in strings(node["parameters"]):
            for ref in re.findall(r"\$\('([^']+)'\)", text):
                refs += 1
                if ref not in names:
                    problems.append(f"{node['name']!r} refers to unknown node {ref!r}")
    code_nodes = expr = 0
    for node in wf["nodes"]:
        if node["type"].endswith(".code"):
            code_nodes += 1
            err = js_syntax_error("(async function () {\n" + node["parameters"]["jsCode"] + "\n})");
            if err:
                problems.append(f"JavaScript error in Code node {node['name']!r}: {err}")
        for text in strings({k: v for k, v in node["parameters"].items() if k != "jsCode"}):
            if text.startswith("={{") and text.rstrip().endswith("}}"):
                expr += 1
                inner = text[3:].rstrip()[:-2]
                err = js_syntax_error("const $json = {}; const $ = () => ({ first: () => ({ json: {} }) });\n(function () { return (" + inner + "\n); })")
                if err:
                    problems.append(f"expression error in {node['name']!r}: {err}")
    raw = Path(path).read_text(encoding="utf-8")
    if re.search(r"AIza[0-9A-Za-z_-]{20,}", raw):
        problems.append("text that looks like a Google API key is present")
    return {"nodes": len(names), "connections": sum(len(o) for c in wf["connections"].values() for o in c["main"]), "code_nodes": code_nodes,
            "expressions": expr, "node_references": refs, "problems": problems}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "n8n" / "workflows" / "disasterai.json")
    result = check(target)
    print({k: v for k, v in result.items() if k != "problems"})
    for p in result["problems"]:
        print("PROBLEM:", p)
    print("STATIC CHECK:", "FAILED" if result["problems"] else "passed (n8n has not run this workflow)")
    sys.exit(1 if result["problems"] else 0)
