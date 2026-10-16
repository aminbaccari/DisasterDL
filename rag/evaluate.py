"""Retrieval evaluation on the test queries.

Run from the project root:
    python -m rag.evaluate --strategy both
    python -m rag.evaluate --strategy fixed --use-topic-filter

Query file columns: query_id, query, language, disaster_type,
expected_source_document, expected_phrase, expected_entry_id.
expected_phrase is optional. When it is given, a result only counts as a hit if
the chunk contains that phrase, which is stricter than matching the source alone.
expected_entry_id (optional, several ids separated by |) is the strict form: a hit means the chunk holds
that entry's heading, for example FL-04. When it is given, expected_source_document is not needed.
Rows with an empty query, or with neither expected_source_document nor expected_entry_id, are skipped.
"""
import argparse
import csv
from datetime import datetime
from pathlib import Path

from rag import embedder, metrics, store

EVAL_DIR = Path(__file__).resolve().parent / "eval"


def load_queries(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    usable = [
        r for r in rows
        if r.get("query", "").strip()
        and (r.get("expected_source_document", "").strip() or r.get("expected_entry_id", "").strip())
    ]
    return usable, len(rows) - len(usable)


def evaluate(strategy, rows, ks, use_topic_filter):
    top = max(ks)
    ranks, details = [], []
    for row in rows:
        topic = row.get("disaster_type") if use_topic_filter else None
        topic = topic if topic in ("fire", "flood", "structural", "general") else None
        results = store.search(embedder.embed_queries([row["query"]])[0], strategy, k=top, topic=topic)
        entry_ids = [x.strip() for x in (row.get("expected_entry_id") or "").split("|") if x.strip()]
        rank = metrics.first_hit_rank(
            results,
            (row.get("expected_source_document") or "").strip(),
            (row.get("expected_phrase") or "").strip(),
            entry_ids,
        )
        ranks.append(rank)
        details.append(
            {
                "query_id": row["query_id"],
                "language": row.get("language", ""),
                "rank_of_first_hit": rank if rank is not None else "",
                "top1_source": results[0]["source"] if results else "",
                "top1_score": results[0]["score"] if results else "",
            }
        )
    return ranks, details


def print_summary(label, ranks, ks):
    s = metrics.summarize(ranks, ks)
    cols = "  ".join(f"hit@{k}={s[f'hit@{k}']:.2f}" for k in ks)
    print(f"  {label:<8} n={s['n_queries']:<3} {cols}  mrr={s['mrr']:.2f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", default=str(EVAL_DIR / "queries.csv"))
    parser.add_argument("--strategy", choices=["fixed", "section", "both"], default="both")
    parser.add_argument("--ks", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--use-topic-filter", action="store_true", help="filter by disaster_type column")
    args = parser.parse_args()

    rows, skipped = load_queries(args.queries)
    if not rows:
        raise SystemExit(f"No usable queries in {args.queries}. Fill query and expected_source_document.")
    if skipped:
        print(f"Skipped {skipped} incomplete rows.")

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    for strategy in (["fixed", "section"] if args.strategy == "both" else [args.strategy]):
        ranks, details = evaluate(strategy, rows, args.ks, args.use_topic_filter)
        print(f"Strategy {strategy} (topic filter: {args.use_topic_filter})")
        print_summary("all", ranks, args.ks)
        for lang in sorted({d["language"] for d in details if d["language"]}):
            lang_ranks = [r for r, d in zip(ranks, details) if d["language"] == lang]
            print_summary(lang, lang_ranks, args.ks)

        label = Path(args.queries).stem + ("_topic" if args.use_topic_filter else "")
        out = EVAL_DIR / f"results_{label}_{strategy}_{stamp}.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(details[0].keys()))
            writer.writeheader()
            writer.writerows(details)
        print(f"  per-query results saved to {out}")


if __name__ == "__main__":
    main()
