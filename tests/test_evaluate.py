"""Tests for the retrieval metrics (src/rag/evaluate.py) and the retriever filter."""

from src.rag.evaluate import (
    LabelledQuery,
    apply_judgments,
    is_relevant,
    load_judgments,
    parse_relevant,
    score_query,
    summarise,
    threshold_table,
)
from src.rag.retriever import build_filter
from src.schemas import RetrievedChunk


def _chunk(source_id: str, page: int, score: float, page_end: int | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        text="t", source_id=source_id, title="T", page=page, page_end=page_end,
        disaster_type="flood", language="en", reliability="high", score=score,
    )


def test_parse_relevant_handles_ranges_and_lists() -> None:
    assert parse_relevant("FIRE-01:2;FIRE-02:3-5 8;GEN-01:") == {
        "FIRE-01": {2}, "FIRE-02": {3, 4, 5, 8}, "GEN-01": set()
    }


def test_is_relevant_uses_page_overlap() -> None:
    relevant = {"FLOOD-01": {5}, "GEN-01": set()}
    assert is_relevant(_chunk("FLOOD-01", 4, 0.9, page_end=5), relevant)
    assert not is_relevant(_chunk("FLOOD-01", 6, 0.9), relevant)
    assert is_relevant(_chunk("GEN-01", 99, 0.9), relevant)  # no pages listed: any page counts
    assert not is_relevant(_chunk("FIRE-01", 5, 0.9), relevant)


def test_score_query_and_summary() -> None:
    q = LabelledQuery("Q1", "q", "en", "flood", "question", {"FLOOD-01": {2}})
    row = score_query(q, [_chunk("GEN-01", 1, 0.9), _chunk("FLOOD-01", 2, 0.85), _chunk("FLOOD-01", 9, 0.8)])
    assert row["first_relevant_rank"] == 2 and row["rr"] == 0.5
    assert row["hit@1"] == 0 and row["hit@3"] == 1
    assert row["source_precision@5"] == 2 / 3
    assert summarise([row])["mrr@10"] == 0.5


def test_judgments_override_keyword_labels(tmp_path) -> None:
    sheet = tmp_path / "judgments.csv"
    sheet.write_text(
        "query_id,query,source_id,page,keyword_label,relevant,retrieved_by,snippet\n"
        "Q1,q,FLOOD-01,2,1,0,fixed,x\n"   # keyword label rejected by the judge
        "Q1,q,GEN-01,7,0,1,structure,x\n"  # new relevant page found by pooling
        "Q1,q,GEN-01,8,0,,structure,x\n",  # not judged yet: ignored
        encoding="utf-8",
    )
    q = LabelledQuery("Q1", "q", "en", "flood", "question", {"FLOOD-01": {2}})
    assert apply_judgments([q], load_judgments(sheet)) == 2
    assert q.relevant == {"GEN-01": {7}}


def test_threshold_table_trades_positives_for_negatives() -> None:
    pos = {"is_negative": False, "hit@5": 1, "first_relevant_score": 0.86, "top1_score": 0.86}
    neg = {"is_negative": True, "hit@5": 0, "first_relevant_score": None, "top1_score": 0.82}
    low, high = threshold_table([pos, neg], [0.80, 0.84])
    assert (low["positives_kept"], low["negatives_rejected"]) == (1.0, 0.0)
    assert (high["positives_kept"], high["negatives_rejected"]) == (1.0, 1.0)


def test_build_filter_includes_general_and_skips_unknown() -> None:
    assert build_filter("flood") == {"disaster_type": {"$in": ["flood", "general"]}}
    assert build_filter("unknown") is None and build_filter(None) is None
