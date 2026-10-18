"""Relevance judging of the pooled retrieval results by a panel of LLM judges ("LLM jury").

Purpose: build the relevance labels (qrels) used to evaluate *retrieval*. For each test query, the
pages returned by the main retrieval configurations are pooled (TREC-style), and every
(query, page) pair is graded 0/1/2 by judges from three model families that play no role in the
system itself (Verga et al., 2024, "Replacing Judges with Juries"):

    judge1      openai/gpt-oss-120b (reasoning, effort high) on Groq    all items
    judge2      qwen/qwen3.8-27b on Groq                                all items
    tiebreaker  llama3.1:8b (Meta, 4-bit, local Ollama)                 disputed items only

An item is disputed when judge1 and judge2 give different scores, or when a positive score comes
with a quote that does not appear in the page (an invented quote invalidates that vote). The
final score is the median of the valid votes; lenient labels count a score >= 1 as relevant,
strict labels only a score of 2.

Blinding: judges see only the query, the document title, the page number and the page text, in a
shuffled order; configuration names and the earlier keyword labels stay in key.csv.

Subcommands (files in evaluation/judging/):
    prepare                         items.jsonl (blinded, shuffled) + key.csv (hidden)
    judge --judge judge1|judge2     verdicts for all items (resumable); --limit N for a pilot
    judge --judge tiebreaker        verdicts for the disputed items only
    analyse                         agreement report + disputed.json
    merge                           final labels -> evaluation/retrieval_judgments.csv (lenient)
                                    and retrieval_judgments_strict.csv, report completed

Usage:
    python -m src.rag.judging prepare
    python -m src.rag.judging judge --judge judge1 --limit 25 --out pilot_judge1.jsonl
    python -m src.rag.judging judge --judge judge1
    python -m src.rag.judging judge --judge judge2
    python -m src.rag.judging analyse
    python -m src.rag.judging judge --judge tiebreaker
    python -m src.rag.judging merge
"""

import argparse
import csv
import json
import random
import statistics
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

from src.config import PROJECT_ROOT, get_settings
from src.utils.text_match import quote_found
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

EVAL_DIR = PROJECT_ROOT / "evaluation"
JUDGING_DIR = EVAL_DIR / "judging"
POOL = EVAL_DIR / "retrieval_judgments.csv"
STRICT = EVAL_DIR / "retrieval_judgments_strict.csv"
ITEMS = JUDGING_DIR / "items.jsonl"
KEY = JUDGING_DIR / "key.csv"
DISPUTED = JUDGING_DIR / "disputed.json"
REPORT = JUDGING_DIR / "agreement.md"
PAGE_CHARS = 2500
SEED = 42
PROMPT_VERSION = 3


class Verdict(BaseModel):
    """One judge's decision for one item."""

    reason: str = Field(default="", description="One sentence on what the page is about")
    score: int = Field(ge=0, le=2, description="0 not relevant, 1 partially relevant, 2 relevant")
    quote: str = Field(default="", description="Verbatim sentence from the page justifying the score")


@dataclass
class Judge:
    """One member of the judging panel and how to call it."""

    name: str
    model: str
    base_url: str
    api_key: str
    temperature: float
    extra: dict = field(default_factory=dict)

    @property
    def output(self) -> Path:
        return JUDGING_DIR / f"{self.name}.jsonl"


def panel() -> dict[str, Judge]:
    """The three judges, with each provider's recommended sampling settings."""
    s = get_settings()
    return {
        "judge1": Judge("judge1", s.judge1_model, s.judge_base_url, s.judge_api_key, 1.0,
                        {"reasoning_effort": "high"}),
        "judge2": Judge("judge2", s.judge2_model, s.judge_base_url, s.judge_api_key, 0.7),
        "tiebreaker": Judge("tiebreaker", s.tiebreaker_model, s.tiebreaker_base_url, s.tiebreaker_api_key, 0.1),
    }


# ---------------------------------------------------------------- prepare


def _page_texts(filename: str) -> dict[int, str]:
    from src.rag.extract import extract_pdf

    settings = get_settings()
    pages: dict[int, list[str]] = {}
    for block in extract_pdf(settings.resolve(settings.raw_dir) / filename).blocks:
        pages.setdefault(block.page, []).append(block.text)
    return {page: "\n".join(texts) for page, texts in pages.items()}


def prepare() -> None:
    """Write blinded, shuffled items and the hidden key from the pooled judging sheet."""
    from src.rag.ingest import load_sources

    settings = get_settings()
    sources = {s.source_id: s for s in load_sources(settings.resolve(settings.sources_csv), settings.resolve(settings.raw_dir))}
    with POOL.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    random.Random(SEED).shuffle(rows)

    texts: dict[str, dict[int, str]] = {}
    items, key = [], []
    for i, row in enumerate(rows, 1):
        source = sources[row["source_id"]]
        if source.source_id not in texts:
            texts[source.source_id] = _page_texts(source.filename)
        page = int(row["page"])
        item_id = f"J{i:03d}"
        items.append({"item_id": item_id, "query": row["query"], "title": source.title, "page": page,
                      "text": texts[source.source_id].get(page, "")[:PAGE_CHARS]})
        key.append({"item_id": item_id, "query_id": row["query_id"], "source_id": row["source_id"],
                    "page": page, "keyword_label": row["keyword_label"], "retrieved_by": row["retrieved_by"]})

    JUDGING_DIR.mkdir(parents=True, exist_ok=True)
    _write_jsonl(ITEMS, items)
    with KEY.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(key[0]))
        writer.writeheader()
        writer.writerows(key)
    logger.info("Prepared %d blinded items (%d empty pages)", len(items), sum(not it["text"] for it in items))


# ---------------------------------------------------------------- judging


def run_judge(name: str, limit: int | None = None, out: Path | None = None) -> Path:
    """Run one judge on all items (tie-breaker: disputed items only); resumes from its output file."""
    from src.llm import client
    from src.llm.prompt_loader import build_messages, load_prompt

    judge = panel()[name]
    if not judge.api_key:
        raise SystemExit(f"No API key for {name}: set {'TIEBREAKER' if name == 'tiebreaker' else 'JUDGE'}_API_KEY in .env")
    out = JUDGING_DIR / out if out is not None else judge.output
    items = _read_jsonl(ITEMS)
    if name == "tiebreaker":
        disputed = set(json.loads(DISPUTED.read_text(encoding="utf-8"))["disputed"])
        items = [it for it in items if it["item_id"] in disputed]
    if limit is not None:
        items = items[:limit]
    # Resume: keep successful verdicts, retry failed ones (e.g. quota errors)
    previous = [r for r in _read_jsonl(out) if r.get("score") is not None] if out.is_file() else []
    _write_jsonl(out, previous)
    done = {r["item_id"] for r in previous}
    todo = [it for it in items if it["item_id"] not in done]
    logger.info("%s (%s): %d items to judge, %d already done", name, judge.model, len(todo), len(done))

    prompt = load_prompt("relevance_judge", PROMPT_VERSION)
    with out.open("a", encoding="utf-8") as f:
        for n, item in enumerate(todo, 1):
            messages = build_messages(prompt, query=item["query"], title=item["title"], page=item["page"], text=item["text"])
            try:
                v = client.chat_json(messages, Verdict, model=judge.model, temperature=judge.temperature,
                                     base_url=judge.base_url, api_key=judge.api_key, extra=judge.extra)
                record = {"item_id": item["item_id"], "score": v.score, "quote": v.quote, "reason": v.reason}
            except (client.LLMError, client.LLMOutputError) as exc:
                record = {"item_id": item["item_id"], "score": None, "quote": "", "reason": "", "error": str(exc)[:300]}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            if n % 25 == 0:
                logger.info("%s: %d/%d", name, n, len(todo))
    return out


# ---------------------------------------------------------------- checks and statistics


def cohen_kappa(a: list, b: list) -> float:
    """Cohen's kappa between two label lists (chance-corrected agreement)."""
    n = len(a)
    if n == 0:
        return float("nan")
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[label] * cb[label] for label in set(a) | set(b)) / (n * n)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def valid_votes(path: Path, items: dict[str, dict]) -> dict[str, int | None]:
    """Score per item, or None when the verdict is missing, failed, or cites a quote not in the page."""
    votes: dict[str, int | None] = {}
    if not path.is_file():
        return votes
    for r in _read_jsonl(path):
        score = r.get("score")
        if score not in (0, 1, 2):
            votes[r["item_id"]] = None
        elif score > 0 and not quote_found(r.get("quote", ""), items[r["item_id"]]["text"]):
            votes[r["item_id"]] = None
        else:
            votes[r["item_id"]] = score
    return votes


def final_score(votes: list[int | None]) -> int | None:
    """Median of the valid votes; with two valid votes that differ, the lower one (conservative)."""
    valid = sorted(v for v in votes if v is not None)
    if not valid:
        return None
    if len(valid) == 2 and valid[0] != valid[1]:
        return valid[0]
    return int(statistics.median_low(valid))


def is_disputed(s1: int | None, s2: int | None) -> bool:
    """The tie-breaker is needed when a vote is invalid or the two judges' scores differ."""
    return s1 is None or s2 is None or s1 != s2


# ---------------------------------------------------------------- analysis and merge


def analyse() -> None:
    """Agreement between judge1 and judge2, and the list of disputed items for the tie-breaker."""
    items = {it["item_id"]: it for it in _read_jsonl(ITEMS)}
    judges = panel()
    v1, v2 = valid_votes(judges["judge1"].output, items), valid_votes(judges["judge2"].output, items)
    missing = [i for i in items if i not in v1 or i not in v2]
    if missing:
        raise SystemExit(f"{len(missing)} items lack a verdict from judge1 or judge2 (e.g. {missing[:3]})")
    disputed = [i for i in items if is_disputed(v1[i], v2[i])]
    DISPUTED.write_text(json.dumps({"disputed": disputed}, indent=2), encoding="utf-8")

    both = [i for i in items if v1[i] is not None and v2[i] is not None]
    a, b = [v1[i] for i in both], [v2[i] for i in both]
    raw1 = Counter(r.get("score") for r in _read_jsonl(judges["judge1"].output))
    raw2 = Counter(r.get("score") for r in _read_jsonl(judges["judge2"].output))
    lines = [
        "# Relevance judging: LLM panel",
        "",
        f"- Items: {len(items)} pooled (query, document, page) pairs, prompt relevance_judge v{PROMPT_VERSION}",
        f"- judge1 = {judges['judge1'].model}; judge2 = {judges['judge2'].model}; tie-breaker = {judges['tiebreaker'].model}",
        f"- judge1 raw score distribution: {dict(sorted(raw1.items(), key=str))}; invalid votes (failed or invented quote): {sum(v is None for v in v1.values())}",
        f"- judge2 raw score distribution: {dict(sorted(raw2.items(), key=str))}; invalid votes: {sum(v is None for v in v2.values())}",
        f"- Items with two valid votes: {len(both)}",
        f"- Cohen's kappa judge1 vs judge2, 3 levels: {cohen_kappa(a, b):.3f}",
        f"- Cohen's kappa, binary lenient (score >= 1): {cohen_kappa([x >= 1 for x in a], [y >= 1 for y in b]):.3f}",
        f"- Cohen's kappa, binary strict (score = 2): {cohen_kappa([x == 2 for x in a], [y == 2 for y in b]):.3f}",
        f"- Raw agreement: exact score {sum(x == y for x, y in zip(a, b)) / max(len(both), 1):.1%}, "
        f"lenient {sum((x >= 1) == (y >= 1) for x, y in zip(a, b)) / max(len(both), 1):.1%}",
        f"- Disputed items sent to the tie-breaker: {len(disputed)}",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def merge() -> None:
    """Final labels from the panel, written back to the judging sheets; report completed."""
    items = {it["item_id"]: it for it in _read_jsonl(ITEMS)}
    judges = panel()
    v1 = valid_votes(judges["judge1"].output, items)
    v2 = valid_votes(judges["judge2"].output, items)
    v3 = valid_votes(judges["tiebreaker"].output, items)
    disputed = json.loads(DISPUTED.read_text(encoding="utf-8"))["disputed"]
    pending = [i for i in disputed if i not in v3]
    if pending:
        raise SystemExit(f"{len(pending)} disputed items still need a tie-breaker verdict")
    final = {i: final_score([v1[i], v2[i], v3.get(i)] if i in disputed else [v1[i], v2[i]]) for i in items}
    unresolved = [i for i, s in final.items() if s is None]

    with KEY.open(encoding="utf-8", newline="") as f:
        key = {r["item_id"]: r for r in csv.DictReader(f)}
    with POOL.open(encoding="utf-8", newline="") as f:
        pool_rows = list(csv.DictReader(f))
        fields = list(pool_rows[0])
    by_page = {(key[i]["query_id"], key[i]["source_id"], int(key[i]["page"])): final[i] for i in items}
    for path, threshold in ((POOL, 1), (STRICT, 2)):
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for row in pool_rows:
                score = by_page[(row["query_id"], row["source_id"], int(row["page"]))]
                writer.writerow({**row, "relevant": "" if score is None else int(score >= threshold)})

    tb = [i for i in disputed if v3.get(i) is not None]
    keyword = [int(key[i]["keyword_label"]) for i in items if final[i] is not None]
    lenient = [int(final[i] >= 1) for i in items if final[i] is not None]
    lines = [
        "",
        "## Final labels",
        "",
        f"- Tie-breaker valid votes: {len(tb)}/{len(disputed)}; it sided with judge1 on "
        f"{sum(v3[i] == v1[i] for i in tb)} and with judge2 on {sum(v3[i] == v2[i] for i in tb)} items",
        f"- Final score distribution: {dict(sorted(Counter(s for s in final.values() if s is not None).items()))}; "
        f"unresolved (no valid vote): {len(unresolved)}",
        f"- Relevant items: lenient (score >= 1) {sum(lenient)}, strict (score = 2) {sum(final[i] == 2 for i in items)}",
        f"- Agreement of the earlier keyword labels with the final lenient labels: "
        f"{sum(k == l for k, l in zip(keyword, lenient)) / max(len(lenient), 1):.1%} (kappa {cohen_kappa(keyword, lenient):.3f})",
    ]
    with REPORT.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


# ---------------------------------------------------------------- utilities


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Relevance judging with a panel of LLM judges.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    j = sub.add_parser("judge")
    j.add_argument("--judge", required=True, choices=["judge1", "judge2", "tiebreaker"])
    j.add_argument("--limit", type=int, default=None, help="judge only the first N items (pilot)")
    j.add_argument("--out", type=Path, default=None, help="output file name inside evaluation/judging/")
    sub.add_parser("analyse")
    sub.add_parser("merge")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "judge":
        run_judge(args.judge, args.limit, args.out)
    elif args.command == "analyse":
        analyse()
    else:
        merge()


if __name__ == "__main__":
    main()
