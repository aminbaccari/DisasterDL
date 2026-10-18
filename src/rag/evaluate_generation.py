"""Evaluation of the RAG generation step (step 7, generation half).

For every test query, the final retrieval configuration (structure-aware chunks, type filter,
threshold 0.785, cross-encoder reranking, top 5) feeds the grounded-answer generator
(prompt ``rag_answer`` v<N>, gemma3:4b). The answers are then measured in two ways:

Automatic (no model involved)
    - abstention: out-of-scope queries must get no guidance (with the model's own scope decision
      alone, and with the scope gate added); relevant queries should get some
    - citation validity, quote grounding, entailment check (NLI), retries, JSON validity, latency
Judged by two models independent from the generator (judge panel of src/rag/judging.py,
prompt ``generation_judge``), claim by claim:
    - faithfulness: share of statements "supported" by the passages they cite, overall and
      separately for statements kept vs set aside by the quote and entailment checks
    - answer relevance: 0/1/2 per answer; agreement between the judges (Cohen's kappa)

Answers are generated with every statement kept and the scope gate not applied (its decision is
recorded), so that each safeguard's effect can be measured separately.

Phases are cached per prompt version so an interruption never forces regenerating:
    python -m src.rag.evaluate_generation generate --version 4
    python -m src.rag.evaluate_generation judge --version 4
    python -m src.rag.evaluate_generation report --version 4
"""

import argparse
import json
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from src.config import PROJECT_ROOT
from src.rag.evaluate import load_testset
from src.rag.generate import citation, format_passages, generate_answer, scope_gate
from src.rag.judging import cohen_kappa, panel
from src.rag.nli import ENTAILMENT_THRESHOLD
from src.rag.retriever import retrieve
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
DEFAULT_VERSION = 4
JUDGE_PROMPT_VERSION = 1
THRESHOLD = 0.785
TOP_K = 5
JUDGES = ("judge1", "judge2")


def answers_path(version: int) -> Path:
    return RESULTS_DIR / f"generation_answers_v{version}.jsonl"


def judgments_path(version: int, judge: str) -> Path:
    return RESULTS_DIR / f"generation_judgments_v{version}_{judge}.jsonl"


class _StatementVerdict(BaseModel):
    id: int
    verdict: str = Field(pattern="^(supported|partial|unsupported)$")
    reason: str = ""


class _AnswerVerdict(BaseModel):
    statements: list[_StatementVerdict] = Field(default_factory=list)
    relevance: int = Field(ge=0, le=2)


# ---------------------------------------------------------------- phase 1: generate


def generate_all(version: int) -> None:
    """Retrieve and generate an answer for every test query; resumes from the cache."""
    path = answers_path(version)
    done = {r["query_id"] for r in _read(path)} if path.is_file() else set()
    queries = [q for q in load_testset() if q.query_id not in done]
    logger.info("Generating %d answers with rag_answer v%d (%d cached)", len(queries), version, len(done))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for q in queries:
            chunks = retrieve(q.query, TOP_K, "structure", q.disaster_type, THRESHOLD, rerank=True)
            passages, tags = format_passages(chunks)
            start = time.perf_counter()
            record = {"query_id": q.query_id, "query": q.query, "language": q.language,
                      "disaster_type": q.disaster_type, "is_negative": q.is_negative,
                      "passages": passages, "tag_citations": {t: citation(c) for t, c in tags.items()},
                      "gate_would_abstain": bool(chunks) and scope_gate(q.disaster_type, chunks)}
            try:
                answer = generate_answer(q.query, chunks, q.disaster_type, version,
                                         verified_only=False, use_gate=False)
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


def judge_all(version: int) -> None:
    """Both judges assess every answer that contains statements; resumable per judge."""
    from src.llm import client
    from src.llm.prompt_loader import build_messages, load_prompt

    prompt = load_prompt("generation_judge", JUDGE_PROMPT_VERSION)
    records = [r for r in _read(answers_path(version)) if r["answer"] and r["answer"]["guidance"]]
    for name in JUDGES:
        judge = panel()[name]
        out = judgments_path(version, name)
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


def _kept(g: dict) -> bool:
    """Would the runtime filter keep this statement (quote verified and, if checked, entailed)?"""
    entailment = g.get("entailment")
    return g["quote_verified"] and (entailment is None or entailment >= ENTAILMENT_THRESHOLD)


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.1%})" if d else "0/0"


def report(version: int) -> str:
    """Compute all generation metrics and write the Markdown report."""
    records = _read(answers_path(version))
    positives = [r for r in records if not r["is_negative"]]
    negatives = [r for r in records if r["is_negative"]]
    ok = [r for r in records if r["answer"]]

    def has_guidance(r: dict, gate: bool) -> bool:
        if not r["answer"] or not r["answer"]["guidance"]:
            return False
        return not (gate and r.get("gate_would_abstain"))

    answered = [r for r in positives if has_guidance(r, gate=False)]
    statements = [(r, g) for r in ok if not r["is_negative"] for g in r["answer"]["guidance"]]
    all_statements = [g for r in ok for g in r["answer"]["guidance"]]
    n_cit = sum(len(g["citations"]) for g in all_statements)
    n_invalid = sum(r["answer"]["invalid_citations"] for r in ok)
    nli_checked = [g for g in all_statements if g.get("entailment") is not None]

    judged = {}
    for name in JUDGES:
        path = judgments_path(version, name)
        judged[name] = {r["query_id"]: r["verdict"] for r in _read(path) if r.get("verdict")} if path.is_file() else {}

    lines = [
        f"# RAG generation evaluation, rag_answer v{version} ({datetime.now():%Y-%m-%d %H:%M})",
        "",
        f"- Pipeline: structure-aware chunks, type filter, threshold {THRESHOLD}, reranking, top {TOP_K} "
        f"-> prompt rag_answer v{version} (gemma3:4b)",
        f"- Test set: {len(records)} queries ({len(positives)} relevant, {len(negatives)} out-of-scope)",
        f"- Judges: {', '.join(f'{n} = {panel()[n].model}' for n in JUDGES)}; prompt generation_judge v{JUDGE_PROMPT_VERSION}",
        f"- Runtime filter: quote found verbatim in a cited passage and NLI entailment >= {ENTAILMENT_THRESHOLD}",
        "",
        "## Automatic metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Valid JSON answers | {len(ok)}/{len(records)} |",
        f"| Relevant queries answered with guidance | {len(answered)}/{len(positives)} |",
        f"| Relevant queries with no passage retrieved (threshold) | {sum(not r['tag_citations'] for r in positives)} |",
        f"| False abstentions (passages retrieved, no guidance) | {sum(bool(r['tag_citations']) and r['answer'] is not None and not r['answer']['guidance'] for r in positives)} |",
        f"| Relevant queries stopped by the scope gate | {sum(bool(r.get('gate_would_abstain')) for r in positives)} |",
        f"| Out-of-scope queries refused: model's own decision | {sum(not has_guidance(r, gate=False) for r in negatives)}/{len(negatives)} |",
        f"| Out-of-scope queries refused: model + scope gate | {sum(not has_guidance(r, gate=True) for r in negatives)}/{len(negatives)} |",
        f"| Retries (strong passages, no guidance) | {sum(bool(r['answer'] and r['answer'].get('retried')) for r in records)} |",
        f"| Statements generated (mean per answered query) | {len(statements)} ({len(statements) / max(len(answered), 1):.1f}) |",
        f"| Citation validity | {_pct(n_cit, n_cit + n_invalid)} |",
        f"| Quote grounding (verbatim in a cited passage) | {_pct(sum(g['quote_verified'] for g in all_statements), len(all_statements))} |",
        f"| Entailed by quote or cited passage (NLI >= {ENTAILMENT_THRESHOLD}) | {_pct(sum(g['entailment'] >= ENTAILMENT_THRESHOLD for g in nli_checked), len(nli_checked))} |",
        f"| Kept by the runtime filter (quote and entailment) | {_pct(sum(_kept(g) for g in all_statements), len(all_statements))} |",
        f"| Latency per answer (median / max) | {statistics.median(r['latency_s'] for r in records):.0f} s / {max(r['latency_s'] for r in records):.0f} s |",
        "",
        "## Judged metrics (claim level)",
        "",
        "| Judge | Answers judged | Statements judged | Supported | Partial | Unsupported | Faithfulness (supported) | Mean relevance (0-2) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    rec = {r["query_id"]: r for r in answered}
    by_judge: dict[str, dict[tuple[str, int], str]] = {}
    for name in JUDGES:
        verdicts = {}
        for r in answered:
            v = judged[name].get(r["query_id"])
            for s in (v or {}).get("statements", []):
                if 1 <= s["id"] <= len(r["answer"]["guidance"]):
                    verdicts[(r["query_id"], s["id"])] = s["verdict"]
        by_judge[name] = verdicts
        c = Counter(verdicts.values())
        rel = [judged[name][r["query_id"]]["relevance"] for r in answered if r["query_id"] in judged[name]]
        lines.append(f"| {name} ({panel()[name].model}) | {len(rel)} | {len(verdicts)} | {c['supported']} | {c['partial']} | "
                     f"{c['unsupported']} | {c['supported'] / max(len(verdicts), 1):.1%} | {statistics.mean(rel) if rel else float('nan'):.2f} |")

    common = sorted(set(by_judge["judge1"]) & set(by_judge["judge2"]))
    if common:
        a = [by_judge["judge1"][k] for k in common]
        b = [by_judge["judge2"][k] for k in common]
        lines += [
            "",
            f"- Statements judged by both: {len(common)}; agreement {sum(x == y for x, y in zip(a, b)) / len(common):.1%}, "
            f"Cohen's kappa (3 verdicts) {cohen_kappa(a, b):.3f}, kappa supported vs not "
            f"{cohen_kappa([x == 'supported' for x in a], [y == 'supported' for y in b]):.3f}",
            "",
            "## Faithfulness of the statements passed on vs set aside by the runtime filter",
            "",
            "| Statements | Count | Both judges: supported | At least one: unsupported |",
            "|---|---|---|---|",
        ]
        for label, keep in (("All statements", None), ("Kept (quote verified and entailed)", True), ("Set aside", False)):
            keys = [k for k in common if keep is None or _kept(rec[k[0]]["answer"]["guidance"][k[1] - 1]) == keep]
            sup = sum(by_judge["judge1"][k] == by_judge["judge2"][k] == "supported" for k in keys)
            uns = sum("unsupported" in (by_judge["judge1"][k], by_judge["judge2"][k]) for k in keys)
            lines.append(f"| {label} | {len(keys)} | {_pct(sup, len(keys))} | {_pct(uns, len(keys))} |")
        flagged = [k for k in common if "unsupported" in (by_judge["judge1"][k], by_judge["judge2"][k])]
        if flagged:
            lines += ["", "## Statements judged unsupported by at least one judge", ""]
            for qid, sid in flagged:
                g = rec[qid]["answer"]["guidance"][sid - 1]
                lines.append(f"- {qid} #{sid} ({by_judge['judge1'][(qid, sid)]} / {by_judge['judge2'][(qid, sid)]}; "
                             f"{'kept' if _kept(g) else 'set aside'}, quote {'ok' if g['quote_verified'] else 'not found'}, "
                             f"NLI {g.get('entailment')}): {g['statement']} {g['citations']}")

    lines += ["", "## Per-query overview", "",
              "| Query | Lang | Passages | Statements | Kept | Gate | Relevance (j1/j2) | Answer |", "|---|---|---|---|---|---|---|---|"]
    for r in records:
        a = r["answer"]
        if a is None:
            lines.append(f"| {r['query_id']} | {r['language']} | {len(r['tag_citations'])} | error | - | - | - | {r['error'][:80]} |")
            continue
        rel = "/".join(str(judged[n].get(r["query_id"], {}).get("relevance", "-")) for n in JUDGES)
        gate = "stop" if r.get("gate_would_abstain") else ""
        text = a["answer"].replace("|", "/")[:120]
        lines.append(f"| {r['query_id']} | {r['language']} | {len(r['tag_citations'])} | {len(a['guidance'])} | "
                     f"{sum(_kept(g) for g in a['guidance'])} | {gate} | {rel} | {text} |")

    path = RESULTS_DIR / f"generation_v{version}_{datetime.now():%Y%m%d_%H%M}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s", path.name)
    return "\n".join(lines)


# ---------------------------------------------------------------- utilities


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Evaluate the RAG generation step.")
    parser.add_argument("phase", choices=["generate", "judge", "report", "all"])
    parser.add_argument("--version", type=int, default=DEFAULT_VERSION, help="rag_answer prompt version")
    args = parser.parse_args()
    if args.phase in ("generate", "all"):
        generate_all(args.version)
    if args.phase in ("judge", "all"):
        judge_all(args.version)
    if args.phase in ("report", "all"):
        print(report(args.version))


if __name__ == "__main__":
    main()
