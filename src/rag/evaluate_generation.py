"""Evaluation of the RAG generation step (step 7, generation half).

For every test query, the final retrieval configuration (structure-aware chunks, type filter,
threshold 0.785, cross-encoder reranking, top 5) feeds the grounded-answer generator
(prompt ``rag_answer``, gemma3:4b). The answers are then measured in two ways:

Automatic (no model involved)
    - abstention: out-of-scope queries must get no guidance; relevant queries should get some
    - citation validity: share of citations pointing to a passage that was really provided
    - quote grounding: share of statements whose quote appears verbatim in a cited passage
    - JSON validity and latency
Judged by two models independent from the generator (judge panel of src/rag/judging.py,
prompt ``generation_judge``), claim by claim:
    - faithfulness: share of statements "supported" by the passages they cite
    - answer relevance: 0/1/2 per answer
    - agreement between the two judges (Cohen's kappa on statement verdicts)

Phases are cached so an interruption (e.g. API quota) never forces regenerating:
    python -m src.rag.evaluate_generation generate        # -> evaluation/results/generation_answers.jsonl
    python -m src.rag.evaluate_generation judge            # -> generation_judgments_<judge>.jsonl
    python -m src.rag.evaluate_generation report           # -> generation_<timestamp>.md
"""

import argparse
import json
import statistics
import time
from collections import Counter
from datetime import datetime

from pydantic import BaseModel, Field

from src.config import PROJECT_ROOT
from src.rag.evaluate import load_testset
from src.rag.generate import citation, format_passages, generate_answer
from src.rag.judging import cohen_kappa, panel
from src.rag.retriever import retrieve
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
ANSWERS = RESULTS_DIR / "generation_answers.jsonl"
GENERATION_PROMPT_VERSION = 3
JUDGE_PROMPT_VERSION = 1
THRESHOLD = 0.785
TOP_K = 5
JUDGES = ("judge1", "judge2")
VERDICTS = ("supported", "partial", "unsupported")


class _StatementVerdict(BaseModel):
    id: int
    verdict: str = Field(pattern="^(supported|partial|unsupported)$")
    reason: str = ""


class _AnswerVerdict(BaseModel):
    statements: list[_StatementVerdict] = Field(default_factory=list)
    relevance: int = Field(ge=0, le=2)


# ---------------------------------------------------------------- phase 1: generate


def generate_all() -> None:
    """Retrieve and generate an answer for every test query; resumes from the cache."""
    done = {r["query_id"] for r in _read(ANSWERS)} if ANSWERS.is_file() else set()
    queries = [q for q in load_testset() if q.query_id not in done]
    logger.info("Generating %d answers (%d cached)", len(queries), len(done))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with ANSWERS.open("a", encoding="utf-8") as f:
        for q in queries:
            chunks = retrieve(q.query, TOP_K, "structure", q.disaster_type, THRESHOLD, rerank=True)
            passages, tags = format_passages(chunks)
            start = time.perf_counter()
            record = {"query_id": q.query_id, "query": q.query, "language": q.language,
                      "disaster_type": q.disaster_type, "is_negative": q.is_negative,
                      "passages": passages, "tag_citations": {t: citation(c) for t, c in tags.items()}}
            try:
                answer = generate_answer(q.query, chunks, q.disaster_type, GENERATION_PROMPT_VERSION, verified_only=False)
                record.update(answer=answer.model_dump(), error=None)
            except Exception as exc:  # JSON failure after one retry, or provider error
                record.update(answer=None, error=str(exc)[:300])
            record["latency_s"] = round(time.perf_counter() - start, 1)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            logger.info("%s: %s statements, %.0f s", q.query_id,
                        len(record["answer"]["guidance"]) if record["answer"] else "error", record["latency_s"])


# ---------------------------------------------------------------- phase 2: judge


def _statements_block(record: dict) -> str:
    cit_to_tags: dict[str, list[str]] = {}
    for tag, cit in record["tag_citations"].items():
        cit_to_tags.setdefault(cit, []).append(tag)
    lines = []
    for i, g in enumerate(record["answer"]["guidance"], 1):
        tags = [t for cit in g["citations"] for t in cit_to_tags.get(cit, [])]
        lines.append(f"{i}. {g['statement']} [cites: {', '.join(dict.fromkeys(tags))}]")
    return "\n".join(lines)


def judge_all() -> None:
    """Both judges assess every answer that contains statements; resumable per judge."""
    from src.llm import client
    from src.llm.prompt_loader import build_messages, load_prompt

    prompt = load_prompt("generation_judge", JUDGE_PROMPT_VERSION)
    records = [r for r in _read(ANSWERS) if r["answer"] and r["answer"]["guidance"]]
    for name in JUDGES:
        judge = panel()[name]
        out = RESULTS_DIR / f"generation_judgments_{name}.jsonl"
        previous = [r for r in _read(out) if r.get("verdict")] if out.is_file() else []
        done = {r["query_id"] for r in previous}
        _write(out, previous)
        todo = [r for r in records if r["query_id"] not in done]
        logger.info("%s (%s): %d answers to judge", name, judge.model, len(todo))
        with out.open("a", encoding="utf-8") as f:
            for r in todo:
                messages = build_messages(prompt, incident=r["query"], passages=r["passages"],
                                          statements=_statements_block(r))
                try:
                    v = client.chat_json(messages, _AnswerVerdict, model=judge.model, temperature=judge.temperature,
                                         base_url=judge.base_url, api_key=judge.api_key, extra=judge.extra)
                    row = {"query_id": r["query_id"], "verdict": v.model_dump()}
                except (client.LLMError, client.LLMOutputError) as exc:
                    row = {"query_id": r["query_id"], "verdict": None, "error": str(exc)[:300]}
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()


# ---------------------------------------------------------------- phase 3: report


def _verdict_lists(records: list[dict], judgments: dict[str, dict]) -> dict[tuple[str, int], str]:
    """(query_id, statement id) -> verdict, keeping only well-formed verdicts."""
    out = {}
    for r in records:
        v = judgments.get(r["query_id"])
        if not v:
            continue
        n = len(r["answer"]["guidance"])
        for s in v["statements"]:
            if 1 <= s["id"] <= n:
                out[(r["query_id"], s["id"])] = s["verdict"]
    return out


def report() -> str:
    """Compute all generation metrics and write the Markdown report."""
    records = _read(ANSWERS)
    positives = [r for r in records if not r["is_negative"]]
    negatives = [r for r in records if r["is_negative"]]
    ok = [r for r in records if r["answer"]]
    answered = [r for r in positives if r["answer"] and r["answer"]["guidance"]]
    statements = [g for r in ok for g in r["answer"]["guidance"]]
    n_citations = sum(len(g["citations"]) for g in statements)
    n_invalid = sum(r["answer"]["invalid_citations"] for r in ok)

    judged = {}
    for name in JUDGES:
        path = RESULTS_DIR / f"generation_judgments_{name}.jsonl"
        judged[name] = {r["query_id"]: r["verdict"] for r in _read(path) if r.get("verdict")} if path.is_file() else {}

    lines = [
        f"# RAG generation evaluation ({datetime.now():%Y-%m-%d %H:%M})",
        "",
        f"- Pipeline: structure-aware chunks, type filter, threshold {THRESHOLD}, reranking, top {TOP_K} "
        f"-> prompt rag_answer v{GENERATION_PROMPT_VERSION} (gemma3:4b)",
        f"- Test set: {len(records)} queries ({len(positives)} relevant, {len(negatives)} out-of-scope)",
        f"- Judges: {', '.join(f'{n} = {panel()[n].model}' for n in JUDGES)}; prompt generation_judge v{JUDGE_PROMPT_VERSION}",
        "",
        "## Automatic metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Valid JSON answers | {len(ok)}/{len(records)} |",
        f"| Relevant queries answered with guidance | {len(answered)}/{len(positives)} |",
        f"| Relevant queries with no passage retrieved (threshold) | {sum(not r['tag_citations'] for r in positives)} |",
        f"| False abstentions (passages retrieved, no guidance) | {sum(bool(r['tag_citations']) and r['answer'] is not None and not r['answer']['guidance'] for r in positives)} |",
        f"| Out-of-scope queries correctly answered with no guidance | {sum(r['answer'] is not None and not r['answer']['guidance'] for r in negatives)}/{len(negatives)} |",
        f"| Statements generated (mean per answered query) | {len(statements)} ({len(statements) / max(len(answered), 1):.1f}) |",
        f"| Citation validity (citations to provided passages) | {n_citations}/{n_citations + n_invalid} ({n_citations / max(n_citations + n_invalid, 1):.1%}) |",
        f"| Quote grounding (quote found verbatim in a cited passage) | {sum(g['quote_verified'] for g in statements)}/{len(statements)} ({sum(g['quote_verified'] for g in statements) / max(len(statements), 1):.1%}) |",
        f"| Latency per answer (median / max) | {statistics.median(r['latency_s'] for r in records):.0f} s / {max(r['latency_s'] for r in records):.0f} s |",
        "",
        "## Judged metrics (claim level)",
        "",
        "| Judge | Answers judged | Statements judged | Supported | Partial | Unsupported | Faithfulness (supported) | Mean relevance (0-2) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    by_judge = {}
    for name in JUDGES:
        verdicts = _verdict_lists(answered, judged[name])
        by_judge[name] = verdicts
        c = Counter(verdicts.values())
        rel = [judged[name][r["query_id"]]["relevance"] for r in answered if r["query_id"] in judged[name]]
        lines.append(f"| {name} ({panel()[name].model}) | {len(rel)} | {len(verdicts)} | {c['supported']} | {c['partial']} | "
                     f"{c['unsupported']} | {c['supported'] / max(len(verdicts), 1):.1%} | {statistics.mean(rel) if rel else float('nan'):.2f} |")

    common = sorted(set(by_judge["judge1"]) & set(by_judge["judge2"]))
    if common:
        a = [by_judge["judge1"][k] for k in common]
        b = [by_judge["judge2"][k] for k in common]
        both_supported = sum(x == y == "supported" for x, y in zip(a, b))
        any_unsupported = sum("unsupported" in (x, y) for x, y in zip(a, b))
        lines += [
            "",
            f"- Statements judged by both: {len(common)}; agreement {sum(x == y for x, y in zip(a, b)) / len(common):.1%}, "
            f"Cohen's kappa (3 verdicts) {cohen_kappa(a, b):.3f}, kappa supported vs not {cohen_kappa([x == 'supported' for x in a], [y == 'supported' for y in b]):.3f}",
            f"- **Faithfulness, consensus (both judges: supported): {both_supported}/{len(common)} ({both_supported / len(common):.1%})**",
            f"- Statements judged unsupported by at least one judge: {any_unsupported} ({any_unsupported / len(common):.1%})",
        ]
        flagged = [(k, x, y) for k, x, y in zip(common, a, b) if "unsupported" in (x, y)]
        if flagged:
            lines += ["", "## Statements judged unsupported by at least one judge", ""]
            rec = {r["query_id"]: r for r in answered}
            for (qid, sid), x, y in flagged:
                g = rec[qid]["answer"]["guidance"][sid - 1]
                lines.append(f"- {qid} #{sid} ({x} / {y}): {g['statement']} {g['citations']}")

    lines += ["", "## Per-query overview", "", "| Query | Lang | Passages | Statements | Quotes verified | Relevance (j1/j2) | Answer |", "|---|---|---|---|---|---|---|"]
    for r in records:
        a = r["answer"]
        if a is None:
            lines.append(f"| {r['query_id']} | {r['language']} | {len(r['tag_citations'])} | error | - | - | {r['error'][:80]} |")
            continue
        rel = "/".join(str(judged[n].get(r["query_id"], {}).get("relevance", "-")) for n in JUDGES)
        text = a["answer"].replace("|", "/")[:140]
        lines.append(f"| {r['query_id']} | {r['language']} | {len(r['tag_citations'])} | {len(a['guidance'])} | "
                     f"{sum(g['quote_verified'] for g in a['guidance'])} | {rel} | {text} |")

    path = RESULTS_DIR / f"generation_{datetime.now():%Y%m%d_%H%M}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s", path.name)
    return "\n".join(lines)


# ---------------------------------------------------------------- utilities


def _read(path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write(path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Evaluate the RAG generation step.")
    parser.add_argument("phase", choices=["generate", "judge", "report", "all"])
    args = parser.parse_args()
    if args.phase in ("generate", "all"):
        generate_all()
    if args.phase in ("judge", "all"):
        judge_all()
    if args.phase in ("report", "all"):
        print(report())


if __name__ == "__main__":
    main()
