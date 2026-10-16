"""Retrieval evaluation over evaluation/retrieval_testset.csv.

Relevance is labelled at document + page level (not chunk id), so the same labels are valid
for every chunking strategy: a retrieved chunk is relevant when its source is listed for the
query and its page range overlaps the listed pages (any page counts when none are listed).

Metrics on positive queries: Hit@k (k = 1, 3, 5, 10), MRR@10 and source precision@5
(share of the top 5 chunks coming from a relevant document). On negative (out-of-scope)
queries we look at the top-1 score to calibrate the "nothing relevant" threshold.

Experiments (each is a configuration of the same retriever; collections that do not exist are skipped):
    E1  fixed vs structure-aware chunking, no metadata filter
    E2  the same with the disaster_type filter (incident type + "general")
    E3  structure-aware with vs without contextual header (kb_structure_noheader)
    E4  query: raw text vs LLM rewrite (rw<N>) vs fusion of both (fusion<N>, reciprocal rank fusion)
    E5  per-source cap (cap2: at most 2 chunks per document) and cross-encoder reranking
    E6  embedding model: multilingual-e5-base vs multilingual-e5-small

Relevance labels come from two places:
    1. ``relevant`` column of the test set: pages found by keyword search in the documents.
    2. ``retrieval_judgments.csv``: pooled human judgments. The union of the top-5 pages
       retrieved by all configurations is judged relevant (1) or not (0) by a reviewer; a
       judgment overrides the keyword label, a blank keeps it. Pooling the results of every
       configuration (TREC-style) avoids favouring the strategy the labels were built from.

Usage:
    python -m src.rag.evaluate                          # raw-query configurations
    python -m src.rag.evaluate --rewrite 3              # + rewrite / fusion configurations (prompt v3)
    python -m src.rag.evaluate --make-pool --rewrite 3  # (re)build the judging sheet for the main configurations
"""

import argparse
import csv
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.config import PROJECT_ROOT, get_settings
from src.rag.embeddings import get_embedder
from src.rag.ingest import collection_name
from src.rag.retriever import search
from src.schemas import RetrievedChunk
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

TESTSET = PROJECT_ROOT / "evaluation" / "retrieval_testset.csv"
JUDGMENTS = PROJECT_ROOT / "evaluation" / "retrieval_judgments.csv"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
K_VALUES = (1, 3, 5, 10)
K_MAX = max(K_VALUES)
POOL_DEPTH = 5
JUDGMENT_FIELDS = ["query_id", "query", "source_id", "page", "keyword_label", "relevant", "retrieved_by", "snippet"]


@dataclass
class LabelledQuery:
    """One labelled test query."""

    query_id: str
    query: str
    language: str
    disaster_type: str | None
    style: str
    relevant: dict[str, set[int]] = field(default_factory=dict)
    is_negative: bool = False


@dataclass
class Config:
    """One retrieval configuration under evaluation.

    ``query`` is "raw" (test query as written), "rw<N>" (LLM rewrite with prompt v<N>) or
    "fusion<N>" (raw + rewrite, merged with reciprocal rank fusion).
    """

    name: str
    strategy: str
    use_filter: bool
    contextual_header: bool = True
    model: str | None = None
    max_per_source: int | None = None
    rerank: bool = False
    query: str = "raw"


SMALL_MODEL = "intfloat/multilingual-e5-small"
# Configurations pooled for human judging by default: the main comparison plus the candidates
# for the final system (keeps the judging sheet small enough to finish).
MAIN_POOL = ["fixed+filter", "structure+filter", "structure+filter+cap2", "structure+filter+rerank"]


def parse_relevant(spec: str) -> dict[str, set[int]]:
    """Parse "FIRE-01:2;FIRE-02:3-4 8" into {"FIRE-01": {2}, "FIRE-02": {3, 4, 8}}."""
    relevant: dict[str, set[int]] = {}
    for part in filter(None, (p.strip() for p in spec.split(";"))):
        source, _, pages = part.partition(":")
        page_set: set[int] = set()
        for token in pages.split():
            start, _, end = token.partition("-")
            page_set.update(range(int(start), int(end or start) + 1))
        relevant[source.strip()] = page_set
    return relevant


def load_testset(path: Path = TESTSET) -> list[LabelledQuery]:
    """Read the labelled test queries."""
    with path.open(encoding="utf-8", newline="") as f:
        return [
            LabelledQuery(
                query_id=row["query_id"],
                query=row["query"],
                language=row["language"],
                disaster_type=row["disaster_type"] or None,
                style=row["style"],
                relevant=parse_relevant(row["relevant"]),
                is_negative=row["is_negative"].strip().lower() == "true",
            )
            for row in csv.DictReader(f)
        ]


def load_judgments(path: Path = JUDGMENTS) -> dict[str, dict[tuple[str, int], bool]]:
    """Read filled-in judgments: query_id -> {(source_id, page): relevant}. Blank cells are skipped."""
    if not path.is_file():
        return {}
    judgments: dict[str, dict[tuple[str, int], bool]] = defaultdict(dict)
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            value = row["relevant"].strip()
            if value in {"0", "1"}:
                judgments[row["query_id"]][(row["source_id"], int(row["page"]))] = value == "1"
    return dict(judgments)


def apply_judgments(queries: list[LabelledQuery], judgments: dict[str, dict[tuple[str, int], bool]]) -> int:
    """Merge judgments into the queries' relevant pages (judgments win); return how many were applied."""
    applied = 0
    for q in queries:
        for (source, page), relevant in judgments.get(q.query_id, {}).items():
            applied += 1
            if relevant:
                q.relevant.setdefault(source, set()).add(page)
            elif source in q.relevant:
                q.relevant[source].discard(page)
                if not q.relevant[source]:
                    del q.relevant[source]  # an empty set would mean "any page counts"
    return applied


def is_relevant(chunk: RetrievedChunk, relevant: dict[str, set[int]]) -> bool:
    """True when the chunk's source is relevant and its page range overlaps the labelled pages."""
    pages = relevant.get(chunk.source_id)
    if pages is None:
        return False
    if not pages or chunk.page is None:
        return True
    return any(p in pages for p in range(chunk.page, (chunk.page_end or chunk.page) + 1))


def score_query(query: LabelledQuery, chunks: list[RetrievedChunk]) -> dict:
    """Per-query metrics for one ranked list of chunks."""
    rank = next((i for i, c in enumerate(chunks, 1) if is_relevant(c, query.relevant)), None)
    row = {
        "query_id": query.query_id,
        "language": query.language,
        "disaster_type": query.disaster_type or "none",
        "style": query.style,
        "is_negative": query.is_negative,
        "first_relevant_rank": rank,
        "first_relevant_score": chunks[rank - 1].score if rank else None,
        "top1_score": chunks[0].score if chunks else None,
        "top1": f"{chunks[0].source_id} p.{chunks[0].page}" if chunks else "",
        "rr": 1 / rank if rank else 0.0,
        "source_precision@5": (
            sum(c.source_id in query.relevant for c in chunks[:5]) / min(5, len(chunks)) if chunks else 0.0
        ),
    }
    for k in K_VALUES:
        row[f"hit@{k}"] = int(rank is not None and rank <= k)
    return row


def summarise(rows: list[dict]) -> dict:
    """Aggregate metrics over positive queries."""
    positives = [r for r in rows if not r["is_negative"]]
    summary = {f"hit@{k}": statistics.mean(r[f"hit@{k}"] for r in positives) for k in K_VALUES}
    summary["mrr@10"] = statistics.mean(r["rr"] for r in positives)
    summary["source_precision@5"] = statistics.mean(r["source_precision@5"] for r in positives)
    summary["n"] = len(positives)
    return summary


def breakdown(rows: list[dict], key: str) -> dict[str, dict]:
    """Hit@5 and MRR per value of ``key`` (language, disaster_type, style)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if not r["is_negative"]:
            groups[r[key]].append(r)
    return {
        value: {
            "n": len(g),
            "hit@5": statistics.mean(r["hit@5"] for r in g),
            "mrr@10": statistics.mean(r["rr"] for r in g),
        }
        for value, g in sorted(groups.items())
    }


def threshold_table(rows: list[dict], grid: list[float]) -> list[dict]:
    """For each threshold: share of negatives rejected vs share of positives whose hit@5 survives."""
    positives = [r for r in rows if not r["is_negative"] and r["hit@5"]]
    negatives = [r for r in rows if r["is_negative"]]
    table = []
    for t in grid:
        kept = sum(r["first_relevant_score"] >= t for r in positives) / max(len(positives), 1)
        rejected = sum((r["top1_score"] or 0) < t for r in negatives) / max(len(negatives), 1)
        table.append({"threshold": t, "positives_kept": kept, "negatives_rejected": rejected,
                      "balanced": (kept + rejected) / 2})
    return table


def _available_configs(rewrite_version: int | None = None) -> list[Config]:
    import chromadb

    settings = get_settings()
    client = chromadb.PersistentClient(path=str(settings.resolve(settings.chroma_path)))
    existing = {c.name for c in client.list_collections()}
    configs = [
        Config("fixed", "fixed", False),
        Config("fixed+filter", "fixed", True),
        Config("structure", "structure", False),
        Config("structure+filter", "structure", True),
        Config("structure-noheader+filter", "structure", True, contextual_header=False),
        Config("structure+filter[e5-small]", "structure", True, model=SMALL_MODEL),
        Config("fixed+filter+cap2", "fixed", True, max_per_source=2),
        Config("structure+filter+cap2", "structure", True, max_per_source=2),
        Config("structure+filter+rerank", "structure", True, rerank=True),
        Config("structure+filter+rerank+cap2", "structure", True, max_per_source=2, rerank=True),
    ]
    if rewrite_version:
        v = rewrite_version
        configs += [
            Config(f"fixed+filter+rw{v}", "fixed", True, query=f"rw{v}"),
            Config(f"structure+filter+rw{v}", "structure", True, query=f"rw{v}"),
            Config(f"structure+filter+fusion{v}", "structure", True, query=f"fusion{v}"),
            Config(f"structure+filter+fusion{v}+cap2", "structure", True, max_per_source=2, query=f"fusion{v}"),
            Config(f"structure+filter+fusion{v}+rerank", "structure", True, rerank=True, query=f"fusion{v}"),
        ]
    return [c for c in configs if collection_name(c.strategy, c.contextual_header, c.model) in existing]


def _fmt(x: float) -> str:
    return f"{x:.3f}"


def rewrite_queries(queries: list[LabelledQuery], version: int) -> dict[str, str]:
    """LLM-rewritten query per test query, cached in evaluation/results/rewrites_v<N>.json."""
    from src.agents.knowledge_agent import rewrite_query

    cache_path = RESULTS_DIR / f"rewrites_v{version}.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    for q in queries:
        if q.query_id not in cache:
            cache[q.query_id] = rewrite_query(q.query, q.disaster_type, version)
            logger.info("%s -> %s", q.query_id, cache[q.query_id])
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    return cache


def _query_texts(config: Config, q: LabelledQuery, rewrites: dict[int, dict[str, str]]) -> list[str]:
    if config.query == "raw":
        return [q.query]
    version = int(config.query.removeprefix("rw").removeprefix("fusion"))
    rewritten = rewrites[version][q.query_id]
    return [rewritten] if config.query.startswith("rw") else [q.query, rewritten]


def _retrieve_all(
    queries: list[LabelledQuery], configs: list[Config], rewrites: dict[int, dict[str, str]] | None = None
) -> dict[str, dict[str, list[RetrievedChunk]]]:
    """Top-K_MAX chunks for every (config, query); each (model, text) pair is embedded once."""
    rewrites = rewrites or {}
    vectors: dict[tuple[str | None, str], list[float]] = {}

    def vector(model: str | None, text: str) -> list[float]:
        if (model, text) not in vectors:
            vectors[(model, text)] = get_embedder(model).embed_query(text)
        return vectors[(model, text)]

    retrieved: dict[str, dict[str, list[RetrievedChunk]]] = {}
    for config in configs:
        retrieved[config.name] = {
            q.query_id: search(
                [vector(config.model, t) for t in _query_texts(config, q, rewrites)],
                K_MAX, config.strategy, q.disaster_type if config.use_filter else None,
                contextual_header=config.contextual_header, model=config.model,
                max_per_source=config.max_per_source, rerank_query=q.query if config.rerank else None,
            )
            for q in queries
        }
        logger.info("Retrieved %s", config.name)
    return retrieved


def make_pool(
    path: Path = JUDGMENTS, rewrite_version: int | None = None, config_names: list[str] | None = None,
    depth: int = POOL_DEPTH,
) -> Path:
    """Write the judging sheet: every page in the top-``depth`` of the pooled configurations.

    By default the pool is ``MAIN_POOL`` plus, with ``rewrite_version``, the fusion configuration.
    Existing judgments in ``path`` are kept, so the sheet can be regenerated after adding a
    configuration and only the new pages need judging.
    """
    queries = [q for q in load_testset() if not q.is_negative]
    previous: dict[tuple[str, str, int], str] = {}
    if path.is_file():
        with path.open(encoding="utf-8", newline="") as f:
            previous = {(r["query_id"], r["source_id"], int(r["page"])): r["relevant"] for r in csv.DictReader(f)}

    names = config_names or MAIN_POOL + ([f"structure+filter+fusion{rewrite_version}"] if rewrite_version else [])
    configs = [c for c in _available_configs(rewrite_version) if c.name in names]
    rewrites = {rewrite_version: rewrite_queries(queries, rewrite_version)} if rewrite_version else {}
    retrieved = _retrieve_all(queries, configs, rewrites)
    pool: dict[tuple[str, str, int], dict] = {}
    for config_name, lists in retrieved.items():
        for q in queries:
            for chunk in lists[q.query_id][:depth]:
                for page in range(chunk.page, (chunk.page_end or chunk.page) + 1):
                    key = (q.query_id, chunk.source_id, page)
                    entry = pool.setdefault(key, {
                        "query_id": q.query_id,
                        "query": q.query,
                        "source_id": chunk.source_id,
                        "page": page,
                        "keyword_label": int(page in q.relevant.get(chunk.source_id, set())),
                        "relevant": previous.get(key, ""),
                        "retrieved_by": set(),
                        "snippet": chunk.text[:400].replace("\n", " "),
                    })
                    entry["retrieved_by"].add(config_name)

    order = {q.query_id: i for i, q in enumerate(queries)}
    rows = sorted(pool.values(), key=lambda r: (order[r["query_id"]], r["source_id"], r["page"]))
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=JUDGMENT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "retrieved_by": " ".join(sorted(row["retrieved_by"]))})
    pending = sum(not r["relevant"] for r in rows)
    logger.info("Judging sheet %s: %d pooled pages, %d still to judge", path.name, len(rows), pending)
    return path


def run(rewrite_version: int | None = None) -> Path:
    """Run every available configuration, write CSV + Markdown reports, return the Markdown path.

    With ``rewrite_version``, the rewrite and fusion configurations (prompt ``rag_query_rewrite``
    v<N>) are added.
    """
    queries = load_testset()
    n_judged = apply_judgments(queries, load_judgments())
    configs = _available_configs(rewrite_version)
    rewrites_by_version = {rewrite_version: rewrite_queries(queries, rewrite_version)} if rewrite_version else {}
    rewrites = rewrites_by_version.get(rewrite_version, {})
    retrieved = _retrieve_all(queries, configs, rewrites_by_version)

    all_rows: dict[str, list[dict]] = {}
    by_id = {q.query_id: q for q in queries}
    for name, lists in retrieved.items():
        rows = [{"config": name, **score_query(by_id[qid], chunks)} for qid, chunks in lists.items()]
        all_rows[name] = rows
        logger.info("%s: %s", name, summarise(rows))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    csv_path = RESULTS_DIR / f"retrieval_{stamp}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        flat = [r for rows in all_rows.values() for r in rows]
        writer = csv.DictWriter(f, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)

    md_path = RESULTS_DIR / f"retrieval_{stamp}.md"
    report = _report(queries, all_rows, retrieved, csv_path, n_judged)
    if rewrites:
        report += f"\n## Rewritten queries (prompt rag_query_rewrite v{rewrite_version})\n\n"
        report += "| query | original | rewritten |\n|---|---|---|\n"
        report += "".join(f"| {q.query_id} | {q.query} | {rewrites[q.query_id]} |\n" for q in queries)
    md_path.write_text(report, encoding="utf-8")
    (RESULTS_DIR / f"retrieval_{stamp}_summary.json").write_text(
        json.dumps({name: summarise(rows) for name, rows in all_rows.items()}, indent=2), encoding="utf-8"
    )
    logger.info("Wrote %s and %s", csv_path.name, md_path.name)
    return md_path


def _report(
    queries: list[LabelledQuery],
    all_rows: dict[str, list[dict]],
    retrieved: dict[str, dict[str, list[RetrievedChunk]]],
    csv_path: Path,
    n_judged: int,
) -> str:
    settings = get_settings()
    n_pos = sum(not q.is_negative for q in queries)
    lines = [
        f"# Retrieval evaluation ({datetime.now():%Y-%m-%d %H:%M})",
        "",
        f"- Test set: {len(queries)} queries ({n_pos} positive, {len(queries) - n_pos} out-of-scope)",
        f"- Labels: keyword page labels + {n_judged} pooled human judgments"
        + ("" if n_judged else " (none yet: run `--make-pool` and fill `retrieval_judgments.csv`)"),
        f"- Embedding model: `{settings.embedding_model}`; chunk size {settings.chunk_size}, "
        f"overlap {settings.chunk_overlap}; per-query results in `{csv_path.name}`",
        "",
        "## Overall (positive queries)",
        "",
        "| config | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 | Source P@5 |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, rows in all_rows.items():
        s = summarise(rows)
        lines.append(
            f"| {name} | {_fmt(s['hit@1'])} | {_fmt(s['hit@3'])} | {_fmt(s['hit@5'])} | {_fmt(s['hit@10'])} "
            f"| {_fmt(s['mrr@10'])} | {_fmt(s['source_precision@5'])} |"
        )

    for key in ("disaster_type", "language", "style"):
        lines += ["", f"## Hit@5 / MRR@10 by {key}", ""]
        values = sorted({v for rows in all_rows.values() for v in breakdown(rows, key)})
        lines.append("| config | " + " | ".join(values) + " |")
        lines.append("|---" * (len(values) + 1) + "|")
        for name, rows in all_rows.items():
            b = breakdown(rows, key)
            cells = [f"{_fmt(b[v]['hit@5'])} / {_fmt(b[v]['mrr@10'])} (n={b[v]['n']})" if v in b else "-" for v in values]
            lines.append(f"| {name} | " + " | ".join(cells) + " |")

    # Head-to-head on the main comparison (E1/E2 with filter).
    if "fixed+filter" in all_rows and "structure+filter" in all_rows:
        fixed = {r["query_id"]: r for r in all_rows["fixed+filter"]}
        better = worse = same = 0
        for r in all_rows["structure+filter"]:
            if r["is_negative"]:
                continue
            a, b = fixed[r["query_id"]]["rr"], r["rr"]
            better += b > a
            worse += b < a
            same += b == a
        lines += ["", "## Head-to-head: structure+filter vs fixed+filter (reciprocal rank per query)", "",
                  f"structure better on {better} queries, worse on {worse}, tied on {same}."]

    best = max(all_rows, key=lambda name: summarise(all_rows[name])["mrr@10"])
    rows = all_rows[best]
    pos_scores = [r["first_relevant_score"] for r in rows if r["first_relevant_score"] is not None]
    neg_scores = [r["top1_score"] for r in rows if r["is_negative"] and r["top1_score"] is not None]
    lines += [
        "",
        f"## Threshold calibration (best config by MRR: `{best}`)",
        "",
        f"- Score of the first relevant chunk (positives): min {min(pos_scores):.3f}, "
        f"median {statistics.median(pos_scores):.3f}, max {max(pos_scores):.3f}",
        f"- Top-1 score on out-of-scope queries: min {min(neg_scores):.3f}, "
        f"median {statistics.median(neg_scores):.3f}, max {max(neg_scores):.3f}",
        "",
        "| threshold | positives kept (hit@5) | negatives rejected | balanced |",
        "|---|---|---|---|",
    ]
    grid = [round(0.78 + 0.005 * i, 3) for i in range(25)]
    table = threshold_table(rows, grid)
    for t in table:
        lines.append(f"| {t['threshold']:.3f} | {_fmt(t['positives_kept'])} | {_fmt(t['negatives_rejected'])} "
                     f"| {_fmt(t['balanced'])} |")
    top = max(table, key=lambda t: (t["balanced"], t["positives_kept"]))
    lines += ["", f"Best balanced threshold: **{top['threshold']:.3f}** "
              f"(keeps {top['positives_kept']:.0%} of positive hits, rejects {top['negatives_rejected']:.0%} of out-of-scope queries)."]

    lines += ["", f"## Failed queries (no relevant chunk in top 5, `{best}`)", ""]
    by_id = {q.query_id: q for q in queries}
    for r in rows:
        if r["is_negative"] or r["hit@5"]:
            continue
        q = by_id[r["query_id"]]
        lines.append(f"- **{q.query_id}** ({q.language}, {q.disaster_type}): {q.query}")
        lines.append(f"  - expected: {', '.join(sorted(q.relevant))}; first relevant rank: {r['first_relevant_rank']}")
        for c in retrieved[best][q.query_id][:3]:
            lines.append(f"  - got {c.score:.3f} {c.source_id} p.{c.page} [{c.heading[-60:]}]: {c.text[:120]!r}")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Evaluate DisasterAI retrieval.")
    parser.add_argument("--make-pool", action="store_true", help="build the judging sheet instead of evaluating")
    parser.add_argument("--rewrite", type=int, metavar="N", help="also evaluate LLM-rewritten queries (prompt v<N>)")
    parser.add_argument("--pool-configs", help="comma-separated configurations to pool (default: main ones)")
    parser.add_argument("--pool-depth", type=int, default=POOL_DEPTH, help="top-n results pooled per configuration")
    args = parser.parse_args()
    if args.make_pool:
        names = args.pool_configs.split(",") if args.pool_configs else None
        print(f"Judging sheet written to {make_pool(rewrite_version=args.rewrite, config_names=names, depth=args.pool_depth)}")
    else:
        print(run(args.rewrite).read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
