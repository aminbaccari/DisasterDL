"""Tests for the ingestion helpers (src/rag/ingest.py); no embedding model is loaded."""

from pathlib import Path

from src.rag.chunkers import ChunkingConfig
from src.rag.ingest import build_chunks, chunk_records, chunk_stats, collection_name, load_sources

HEADER = "source_id,title,publisher,year,language,disaster_type,reliability,url,licence,filename\n"


def _write_sources(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "sources.csv"
    path.write_text(HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_load_sources_skips_missing_files(tmp_path, sample_pdf) -> None:
    csv_path = _write_sources(
        tmp_path,
        [
            "FLOOD-01,Flood Safety Guide,FEMA,2024,en,flood,high,https://x,public domain,sample.pdf",
            "FIRE-01,Missing,FEMA,,en,fire,high,https://y,public domain,missing.pdf",
        ],
    )
    sources = load_sources(csv_path, sample_pdf.parent)
    assert [s.source_id for s in sources] == ["FLOOD-01"]
    assert sources[0].year == "2024"


def test_build_chunks_and_records_end_to_end(tmp_path, sample_pdf, counter) -> None:
    csv_path = _write_sources(
        tmp_path, ["FLOOD-01,Flood Safety Guide,FEMA,2024,en,flood,high,https://x,public domain,sample.pdf"]
    )
    source = load_sources(csv_path, sample_pdf.parent)[0]
    config = ChunkingConfig(chunk_size=60, chunk_overlap=0, min_chunk_tokens=5)
    chunks = build_chunks(source, sample_pdf.parent, "structure", counter, config)
    records = chunk_records(source, chunks, "structure")

    assert records and records[0]["id"] == "FLOOD-01:structure:0000"
    assert any("Section 3 During a flood" in r["metadata"]["heading"] for r in records)
    for r in records:
        meta = r["metadata"]
        assert all(isinstance(v, (str, int, float, bool)) for v in meta.values())  # Chroma-compatible
        assert meta["disaster_type"] == "flood" and 1 <= meta["page"] <= 5
        assert "DisasterAI test document" not in r["text"]

    stats = chunk_stats(records, config)
    assert stats["n_chunks"] == len(records) and stats["n_over_chunk_size"] == 0


def test_collection_name_encodes_header_ablation() -> None:
    assert collection_name("structure", True) == "kb_structure"
    assert collection_name("fixed", False) == "kb_fixed_noheader"
