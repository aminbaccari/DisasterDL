import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
from rag import embedder, store  # noqa: E402

EQ = {"FL-27": "FL-04", "FL-28": "FL-12", "FL-29": "FL-16", "FL-30": "FL-17", "FL-31": "FL-18", "FL-32": "FL-19", "FL-33": "FL-21",
      "ST-27": "ST-05", "ST-28": "ST-03", "ST-29": "ST-07", "ST-30": "ST-01", "ST-31": "ST-17", "ST-32": "ST-12",
      "FI-21": "FI-09", "FI-22": "FI-10", "FI-23": "FI-11", "FI-24": "FI-13", "FI-25": "FI-18", "FI-26": "FI-19"}
REV = {}
for k, v in EQ.items():
    REV.setdefault(v, set()).add(k)


def expand(ids):
    out = set(ids)
    for i in list(ids):
        out |= REV.get(i, set())
        if i in EQ:
            out.add(EQ[i])
    return out


def run(path, label):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    hit_strict = hit_equiv = 0
    detail = []
    for r in rows:
        exp = [x for x in r["expected_entry_id"].split("|") if x]
        res = store.search(embedder.embed_queries([r["query"]])[0], "section", k=5, topic=r["disaster_type"])
        ids_by_rank = [set(x["entry_ids"]) for x in res]
        strict = next((i + 1 for i, s in enumerate(ids_by_rank) if s & set(exp)), None)
        equiv = next((i + 1 for i, s in enumerate(ids_by_rank) if s & expand(exp)), None)
        hit_strict += strict is not None
        hit_equiv += equiv is not None
        detail.append((r["query_id"], r["language"], strict, equiv, [sorted(s) for s in ids_by_rank][:3]))
    print(label, "n=%d" % len(rows), "hit@5 strict %d, with translation ids counted as equivalent %d" % (hit_strict, hit_equiv))
    for d in detail:
        if d[2] != d[3]:
            print("   strict miss but equivalent hit:", d)
    return detail


if __name__ == "__main__":
    run("rag/eval/queries_v2.csv", "v2")
    run("rag/eval/queries_v3.csv", "v3")
