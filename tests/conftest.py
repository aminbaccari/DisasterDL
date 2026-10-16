"""Shared test fixtures: an offline token counter and a small generated PDF."""

import re
from pathlib import Path

import pymupdf
import pytest


class WhitespaceCounter:
    """Token counter where one token = one whitespace-separated word (no model download)."""

    def count(self, text: str) -> int:
        return len(text.split())

    def offsets(self, text: str) -> list[tuple[int, int]]:
        return [m.span() for m in re.finditer(r"\S+", text)]


@pytest.fixture
def counter() -> WhitespaceCounter:
    return WhitespaceCounter()


BODY = (
    "Floodwater can hide debris and open drains. Never walk or drive through moving water. "
    "Six inches of moving water can knock you down and one foot can sweep a vehicle away."
)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Five-page PDF with a title, section headings, body text and a running footer."""
    doc = pymupdf.open()
    for page_no in range(1, 6):
        page = doc.new_page()
        y = 72
        if page_no == 1:
            page.insert_text((72, y), "Flood Safety Guide", fontsize=24)
            y += 50
        page.insert_text((72, y), f"Section {page_no} During a flood", fontsize=16)
        y += 40
        page.insert_textbox(pymupdf.Rect(72, y, 520, y + 120), BODY, fontsize=11)
        page.insert_text((72, page.rect.height - 20), f"DisasterAI test document - page {page_no}", fontsize=8)
        page.insert_text((300, page.rect.height - 20), str(page_no), fontsize=8)
    path = tmp_path / "sample.pdf"
    doc.save(path)
    return path
