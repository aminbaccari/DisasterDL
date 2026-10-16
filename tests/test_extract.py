"""Tests for PDF extraction and cleaning (src/rag/extract.py)."""

from src.rag.extract import clean_text, extract_pdf


def test_clean_text_normalises_ligatures_and_whitespace() -> None:
    assert clean_text("   ﬁre­  safety\n\tplan ") == "fire safety plan"


def test_extract_keeps_pages_and_typography(sample_pdf) -> None:
    doc = extract_pdf(sample_pdf)
    assert doc.page_count == 5
    assert doc.body_size == 11
    title = next(b for b in doc.blocks if b.text == "Flood Safety Guide")
    assert title.page == 1 and title.size == 24
    assert {b.page for b in doc.blocks} == {1, 2, 3, 4, 5}


def test_extract_removes_running_footer_and_page_numbers(sample_pdf) -> None:
    texts = [b.text for b in extract_pdf(sample_pdf).blocks]
    assert not any("DisasterAI test document" in t for t in texts)
    assert not any(t.isdigit() for t in texts)
