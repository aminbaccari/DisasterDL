"""Tests for retrieval post-processing (fusion, per-source cap), collection naming and split-line merging."""

from src.config import get_settings
from src.rag.extract import merge_split_lines
from src.rag.ingest import collection_name
from src.rag.retriever import cap_per_source, rrf_fuse
from src.schemas import RetrievedChunk


def _chunk(chunk_id: str, source_id: str, score: float = 0.8) -> RetrievedChunk:
    return RetrievedChunk(
        text=chunk_id, chunk_id=chunk_id, source_id=source_id, title="T", page=1,
        disaster_type="flood", language="en", reliability="high", score=score,
    )


def test_rrf_rewards_chunks_ranked_well_in_both_lists() -> None:
    raw = [_chunk("a", "S1", 0.85), _chunk("b", "S1"), _chunk("c", "S2")]
    rewritten = [_chunk("c", "S2", 0.88), _chunk("a", "S1", 0.80), _chunk("d", "S3")]
    fused = rrf_fuse([raw, rewritten])
    assert [c.chunk_id for c in fused][:2] == ["a", "c"]  # in both lists, near the top
    assert next(c for c in fused if c.chunk_id == "a").score == 0.85  # best cosine is kept


def test_cap_per_source_keeps_order() -> None:
    chunks = [_chunk("a", "BIG"), _chunk("b", "BIG"), _chunk("c", "BIG"), _chunk("d", "SMALL")]
    assert [c.chunk_id for c in cap_per_source(chunks, 2)] == ["a", "b", "d"]


def test_collection_name_suffixes_non_default_model() -> None:
    assert collection_name("structure", True, get_settings().embedding_model) == "kb_structure"
    assert collection_name("structure", True, "intfloat/multilingual-e5-small") == "kb_structure_multilingual-e5-small"


def _line(text: str, x0: float, x1: float, y0: float = 100.0) -> dict:
    return {"text": text, "spans": [{"text": text}], "bbox": (x0, y0, x1, y0 + 12), "block": 0}


def test_merge_split_lines_rejoins_clipped_boxes_and_drops_seam_duplicate() -> None:
    lines = [_line("calme, souriante et no", 65, 222), _line("on agressive,", 214, 307)]
    merged = merge_split_lines(lines)
    assert [l["text"] for l in merged] == ["calme, souriante et non agressive,"]


def test_merge_split_lines_keeps_columns_apart_unless_split_layout() -> None:
    lines = [_line("left column text", 50, 250), _line("right column text", 258, 450)]
    assert len(merge_split_lines([dict(l) for l in lines])) == 2  # 8 pt gutter: separate columns
    assert len(merge_split_lines([dict(l) for l in lines], allow_gaps=True)) == 1  # split-layout document
