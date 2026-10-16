"""PDF text extraction for the knowledge base.

Turns a PDF into a list of text blocks (roughly paragraphs) that keep their page
number and typography (font size, boldness). Typography is what the structure-aware
chunker uses to detect headings when the PDF has no bookmarks.

Cleaning steps:
- Unicode NFKC normalisation (splits typographic ligatures such as "ﬁ"), removal of
  soft hyphens and zero-width characters, whitespace collapsing.
- Dehyphenation of words split across lines (PyMuPDF ``TEXT_DEHYPHENATE``).
- Removal of running headers/footers: short lines located in the top or bottom margin
  that repeat on many pages.
- Removal of page-number-only lines and table-of-contents dot leaders.
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

_MARGIN_RATIO = 0.08  # top/bottom share of the page where running headers/footers live
_REPEAT_RATIO = 0.3  # a margin line repeated on >= 30% of pages is a header/footer
_MIN_PAGES_FOR_REPEAT = 4
_BOLD_FLAG = 16  # PyMuPDF span flag bit for bold text
_BASELINE_TOLERANCE = 2.0  # points: two line boxes on the same baseline
_SEAM_TOLERANCE = 12.0  # points: max gap/overlap between two halves of a split line
_TOUCHING = 1.5  # points: halves this close (or overlapping) are always the same line
_SPLIT_LAYOUT_RATIO = 0.25  # share of overlapping seams that marks a clipped-box layout

_PAGE_NUMBER = re.compile(r"^(page\s*)?\d{1,4}(\s*(/|of|sur)\s*\d{1,4})?$", re.IGNORECASE)
_DOT_LEADER = re.compile(r"(\.\s?){4,}\s*\d*\s*$")
_INVISIBLE = dict.fromkeys(map(ord, "­​‌‍﻿"), None)


@dataclass
class Block:
    """A paragraph-like block of text from one page.

    Attributes:
        text: Cleaned text of the block.
        page: 1-based page number.
        size: Dominant font size in the block (weighted by character count).
        bold: True when most of the block's characters are bold.
    """

    text: str
    page: int
    size: float
    bold: bool


@dataclass
class ExtractedDoc:
    """Result of extracting one PDF.

    Attributes:
        blocks: Text blocks in reading order.
        toc: PDF bookmarks as (level, title, page) tuples; empty when the PDF has none.
        body_size: Most common font size, taken as the body-text size.
        page_count: Number of pages in the PDF.
    """

    blocks: list[Block]
    toc: list[tuple[int, str, int]] = field(default_factory=list)
    body_size: float = 0.0
    page_count: int = 0


def clean_text(text: str) -> str:
    """Normalise unicode, drop invisible characters and collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    text = "".join(c for c in text if unicodedata.category(c) != "Co")  # private-use glyphs (icon bullets)
    return re.sub(r"\s+", " ", text).strip()


def _signature(text: str) -> str:
    """Key used to recognise repeated headers/footers (digits ignored, e.g. page numbers)."""
    return re.sub(r"\d+", "#", text.lower()).strip()


def _is_noise(text: str) -> bool:
    return not text or bool(_PAGE_NUMBER.match(text)) or bool(_DOT_LEADER.search(text))


def extract_pdf(path: Path) -> ExtractedDoc:
    """Extract cleaned text blocks, bookmarks and body font size from a PDF."""
    doc = pymupdf.open(path)
    flags = pymupdf.TEXTFLAGS_TEXT | pymupdf.TEXT_DEHYPHENATE

    # Pass 1: collect lines with their position and typography.
    pages: list[list[dict]] = []
    for page in doc:
        height = page.rect.height
        lines = []
        for block_no, block in enumerate(page.get_text("dict", flags=flags)["blocks"]):
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = clean_text(" ".join(s["text"] for s in spans))
                y0, y1 = line["bbox"][1], line["bbox"][3]
                lines.append(
                    {
                        "block": block_no,
                        "text": text,
                        "spans": spans,
                        "bbox": line["bbox"],
                        "in_margin": y1 < height * _MARGIN_RATIO or y0 > height * (1 - _MARGIN_RATIO),
                    }
                )
        pages.append(lines)

    # Documents laid out as clipped side-by-side boxes have many overlapping seams; only there
    # are wider seams (word spaces) merged too. Real column gutters never overlap.
    gaps = [g for lines in pages for g in _seam_gaps(lines)]
    split_layout = bool(gaps) and sum(g < -0.5 for g in gaps) / len(gaps) >= _SPLIT_LAYOUT_RATIO
    pages = [merge_split_lines(lines, allow_gaps=split_layout) for lines in pages]

    repeated = _repeated_margin_lines(pages)

    # Pass 2: rebuild blocks without noise, headers and footers.
    blocks: list[Block] = []
    size_chars: Counter[float] = Counter()
    for page_no, lines in enumerate(pages, start=1):
        current: list[dict] = []
        for line in lines:
            if _is_noise(line["text"]) or (line["in_margin"] and _signature(line["text"]) in repeated):
                continue
            if current and line["block"] != current[-1]["block"]:
                blocks.append(_make_block(current, page_no))
                current = []
            current.append(line)
        if current:
            blocks.append(_make_block(current, page_no))
    for block in blocks:
        size_chars[block.size] += len(block.text)

    body_size = size_chars.most_common(1)[0][0] if size_chars else 0.0
    toc = [(level, clean_text(title), page) for level, title, page in doc.get_toc()]
    logger.info(
        "Extracted %s: %d pages, %d blocks, %d bookmarks, %d header/footer patterns removed",
        path.name, doc.page_count, len(blocks), len(toc), len(repeated),
    )
    return ExtractedDoc(blocks=blocks, toc=toc, body_size=body_size, page_count=doc.page_count)


def _left_neighbour(line: dict, previous: list[dict]) -> dict | None:
    """Closest earlier line on the same baseline whose right edge is within the seam tolerance."""
    x0, y0, _, y1 = line["bbox"]
    return next(
        (
            p for p in reversed(previous)
            if abs(p["bbox"][1] - y0) < _BASELINE_TOLERANCE
            and abs(p["bbox"][3] - y1) < _BASELINE_TOLERANCE
            and -_SEAM_TOLERANCE <= x0 - p["bbox"][2] <= _SEAM_TOLERANCE
        ),
        None,
    )


def _seam_gaps(lines: list[dict]) -> list[float]:
    """Horizontal gaps (negative = overlap) between lines and their same-baseline left neighbour."""
    gaps = []
    for i, line in enumerate(lines):
        left = _left_neighbour(line, lines[:i])
        if left is not None:
            gaps.append(line["bbox"][0] - left["bbox"][2])
    return gaps


def merge_split_lines(lines: list[dict], allow_gaps: bool = False) -> list[dict]:
    """Re-join text lines that the PDF splits across side-by-side text boxes.

    Some layouts (e.g. the Nouvelle-Calédonie fire guide) cut every line of a paragraph into a
    left and a right text box, often mid-word, so reading block by block yields truncated lines
    ("Chaque cible a ses part" ... "icularités"). A line is merged into an earlier line on the
    same baseline when the two boxes overlap or touch (gap <= 1.5 pt); with ``allow_gaps`` (set
    for documents detected as split layouts) seams up to ``_SEAM_TOLERANCE`` points are merged
    too. When overlapping boxes repeat the seam character ("PR" + "RÉVENTION"), the duplicate
    is dropped.
    """
    kept: list[dict] = []
    for line in lines:
        left = _left_neighbour(line, kept)
        gap = line["bbox"][0] - left["bbox"][2] if left is not None else None
        if left is None or (gap > _TOUCHING and not allow_gaps):
            kept.append(line)
            continue
        right_text = line["text"]
        if gap < 0 and left["text"] and right_text and left["text"][-1] == right_text[0]:
            right_text = right_text[1:]  # overlapping boxes repeat the seam character
        joiner = " " if gap > _TOUCHING else ""
        left["text"] = clean_text(left["text"] + joiner + right_text)
        left["spans"] = left["spans"] + line["spans"]
        left["bbox"] = (left["bbox"][0], left["bbox"][1], line["bbox"][2], left["bbox"][3])
    return kept


def _repeated_margin_lines(pages: list[list[dict]]) -> set[str]:
    """Signatures of margin lines repeated on enough pages to be running headers/footers."""
    if len(pages) < _MIN_PAGES_FOR_REPEAT:
        return set()
    counts: Counter[str] = Counter()
    for lines in pages:
        counts.update({_signature(line["text"]) for line in lines if line["in_margin"]})
    threshold = max(2, int(len(pages) * _REPEAT_RATIO))
    return {sig for sig, n in counts.items() if n >= threshold}


def _make_block(lines: list[dict], page: int) -> Block:
    """Merge consecutive lines of one PyMuPDF block into a Block with dominant typography."""
    sizes: Counter[float] = Counter()
    bold_chars = total_chars = 0
    for line in lines:
        for span in line["spans"]:
            n = len(span["text"].strip())
            sizes[round(span["size"], 1)] += n
            total_chars += n
            if span["flags"] & _BOLD_FLAG or "bold" in span["font"].lower():
                bold_chars += n
    return Block(
        text=" ".join(line["text"] for line in lines),
        page=page,
        size=sizes.most_common(1)[0][0],
        bold=bold_chars > total_chars / 2,
    )
