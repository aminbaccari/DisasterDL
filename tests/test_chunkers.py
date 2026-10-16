"""Tests for the two chunking strategies (src/rag/chunkers.py)."""

from src.rag.chunkers import ChunkingConfig, fixed_size, structure_aware
from src.rag.extract import Block, ExtractedDoc


def _words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}." if i % 10 == 9 else f"{prefix}{i}" for i in range(n))


def _doc(blocks: list[Block], toc: list[tuple[int, str, int]] | None = None) -> ExtractedDoc:
    return ExtractedDoc(blocks=blocks, toc=toc or [], body_size=11, page_count=max(b.page for b in blocks))


def _structured_doc() -> ExtractedDoc:
    return _doc(
        [
            Block("Wildfire Guide", 1, 24, False),
            Block("Before a wildfire", 1, 16, True),
            Block(_words(60, "a"), 1, 11, False),
            Block("During a wildfire", 2, 16, True),
            Block("Evacuation", 2, 13, True),
            Block(_words(150, "b"), 2, 11, False),
            Block(_words(150, "c"), 3, 11, False),
        ]
    )


def test_fixed_size_respects_size_overlap_and_pages(counter) -> None:
    doc = _doc([Block(_words(250, "p1"), 1, 11, False), Block(_words(250, "p2"), 2, 11, False)])
    config = ChunkingConfig(chunk_size=100, chunk_overlap=20, contextual_header=False)
    chunks = fixed_size(doc, "Title", counter, config)
    assert all(c.n_tokens <= 100 for c in chunks)
    assert chunks[0].page == 1 and chunks[-1].page_end == 2
    first, second = chunks[0].text.split(), chunks[1].text.split()
    assert first[-20:] == second[:20]  # 20-token overlap
    assert all(c.heading == "" and c.context == "" for c in chunks)


def test_fixed_size_contextual_header_counts_toward_budget(counter) -> None:
    doc = _doc([Block(_words(300), 1, 11, False)])
    chunks = fixed_size(doc, "Flood Guide", counter, ChunkingConfig(chunk_size=100, chunk_overlap=0))
    assert all(c.embed_text.startswith("Flood Guide\n") and c.n_tokens <= 100 for c in chunks)


def test_structure_aware_uses_font_headings_as_paths(counter) -> None:
    config = ChunkingConfig(chunk_size=120, chunk_overlap=0, min_chunk_tokens=10)
    chunks = structure_aware(_structured_doc(), "Wildfire Guide", counter, config)
    headings = [c.heading for c in chunks]
    assert "Before a wildfire" in headings  # cover-page title is not kept as a parent
    assert "During a wildfire > Evacuation" in headings
    assert all(c.n_tokens <= 120 for c in chunks)
    before = next(c for c in chunks if c.heading.endswith("Before a wildfire"))
    assert "b0" not in before.text  # sections are never mixed
    assert before.embed_text.startswith("Wildfire Guide > Before a wildfire\n")  # title not repeated


def test_front_matter_heading_does_not_become_parent(counter) -> None:
    doc = _doc(
        [
            Block("Contents", 2, 20, True),
            Block(_words(30, "toc"), 2, 11, False),
            Block("1. Introduction", 3, 16, True),
            Block(_words(30, "intro"), 3, 11, False),
        ]
    )
    config = ChunkingConfig(chunk_size=200, chunk_overlap=0, min_chunk_tokens=5, contextual_header=False)
    assert [c.heading for c in structure_aware(doc, "Doc", counter, config)] == ["Contents", "1. Introduction"]


def test_structure_aware_merges_tiny_sections(counter) -> None:
    doc = _doc(
        [
            Block("Tiny section", 1, 16, True),
            Block("Just a few words.", 1, 11, False),
            Block("Big section", 1, 16, True),
            Block(_words(50), 1, 11, False),
        ]
    )
    config = ChunkingConfig(chunk_size=200, chunk_overlap=0, min_chunk_tokens=20, contextual_header=False)
    chunks = structure_aware(doc, "Doc", counter, config)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("Just a few words.")


def test_structure_aware_splits_long_paragraph_by_sentence(counter) -> None:
    doc = _doc([Block("Section", 1, 16, True), Block(_words(300), 1, 11, False)])
    config = ChunkingConfig(chunk_size=100, chunk_overlap=0, min_chunk_tokens=5, contextual_header=False)
    chunks = structure_aware(doc, "Doc", counter, config)
    assert len(chunks) >= 3
    assert all(c.n_tokens <= 100 and c.text.rstrip().endswith(".") for c in chunks[:-1])


def test_structure_aware_prefers_pdf_bookmarks(counter) -> None:
    blocks = [Block(f"Chapter {i} Response", i, 11, False) for i in range(1, 6)]
    blocks = [b for i, h in enumerate(blocks, 1) for b in (h, Block(_words(40, f"t{i}_"), i, 11, False))]
    toc = [(1, f"Chapter {i} Response", i) for i in range(1, 6)]
    config = ChunkingConfig(chunk_size=200, chunk_overlap=0, min_chunk_tokens=5, contextual_header=False)
    chunks = structure_aware(_doc(blocks, toc), "Doc", counter, config)
    assert [c.heading for c in chunks] == [f"Chapter {i} Response" for i in range(1, 6)]
