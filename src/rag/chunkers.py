"""Chunking strategies compared in the retrieval evaluation.

Both strategies share one interface: ``chunker(doc, title, counter, config) -> list[Chunk]``.
Sizes are counted in tokens of the embedding model (see ``embeddings.TokenCounter``),
including the contextual header, so every chunk fits the model's 512-token window.

- ``fixed_size`` (baseline): sliding token windows over the whole document, snapped to
  word boundaries, ignoring layout.
- ``structure_aware``: splits on headings, taken from PDF bookmarks when the PDF has them
  and from typography (font size, boldness) otherwise. Long sections are split by
  paragraph, then sentence, then token window; tiny sections are merged into the next one.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from src.rag.embeddings import TokenCounter
from src.rag.extract import Block, ExtractedDoc

_MIN_TOC_ENTRIES = 5  # fewer bookmarks than this is not a usable outline
_HEADING_SIZE_DELTA = 1.5  # points above body size for a line to count as a heading
_MAX_HEADING_WORDS = 15
_MAX_HEADING_LEVELS = 3
_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")


@dataclass
class ChunkingConfig:
    """Chunking parameters, all in tokens of the embedding model."""

    chunk_size: int = 400
    chunk_overlap: int = 60
    min_chunk_tokens: int = 80
    contextual_header: bool = True


@dataclass
class Chunk:
    """A piece of a document ready to be embedded.

    Attributes:
        text: Chunk body as it appears in the document (shown to the agents).
        context: Contextual header ("Title > Section > Subsection") prepended for embedding;
            empty when headers are disabled.
        heading: Section path the chunk belongs to; empty for fixed-size chunks.
        page: First page covered by the chunk (1-based).
        page_end: Last page covered by the chunk.
        n_tokens: Token count of ``embed_text``.
    """

    text: str
    context: str
    heading: str
    page: int
    page_end: int
    n_tokens: int = 0

    @property
    def embed_text(self) -> str:
        """Text that is actually embedded: header and body."""
        return f"{self.context}\n{self.text}" if self.context else self.text


Chunker = Callable[[ExtractedDoc, str, TokenCounter, ChunkingConfig], list[Chunk]]


# ---------------------------------------------------------------- token windows


def _is_word_start(text: str, offsets: list[tuple[int, int]], i: int) -> bool:
    start = offsets[i][0]
    return start == 0 or text[start - 1].isspace() or text[start].isspace()


def _token_windows(text: str, counter: TokenCounter, size: int, overlap: int) -> list[tuple[int, int]]:
    """Split ``text`` into (start_char, end_char) windows of at most ``size`` tokens.

    Window boundaries are moved back to the nearest word start (by at most half a window)
    so that words are not cut in the middle.
    """
    offsets = counter.offsets(text)
    n = len(offsets)
    windows: list[tuple[int, int]] = []
    i = 0
    while i < n:
        j = min(i + size, n)
        while j < n and j > i + size // 2 and not _is_word_start(text, offsets, j):
            j -= 1
        windows.append((offsets[i][0], offsets[j - 1][1]))
        if j >= n:
            break
        nxt = max(j - overlap, i + 1)
        while nxt < j and not _is_word_start(text, offsets, nxt):
            nxt += 1
        i = nxt
    return windows


# ---------------------------------------------------------------- strategy A: fixed size


def fixed_size(doc: ExtractedDoc, title: str, counter: TokenCounter, config: ChunkingConfig) -> list[Chunk]:
    """Baseline: fixed token windows with overlap over the whole document text."""
    context = title if config.contextual_header else ""
    budget = config.chunk_size - (counter.count(context) + 1 if context else 0)

    # Concatenate blocks and remember where each page starts in the text.
    parts: list[str] = []
    page_starts: list[tuple[int, int]] = []
    position = 0
    for block in doc.blocks:
        if not page_starts or page_starts[-1][1] != block.page:
            page_starts.append((position, block.page))
        parts.append(block.text)
        position += len(block.text) + 1
    text = "\n".join(parts)

    def page_at(char: int) -> int:
        page = page_starts[0][1]
        for start, p in page_starts:
            if start > char:
                break
            page = p
        return page

    chunks = []
    for start, end in _token_windows(text, counter, budget, config.chunk_overlap):
        body = text[start:end].strip()
        if body:
            chunks.append(Chunk(body, context, "", page_at(start), page_at(max(start, end - 1))))
    return _finalise(chunks, counter)


# ---------------------------------------------------------------- strategy B: structure aware


@dataclass
class _Section:
    path: str
    blocks: list[Block]


def _norm(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.lower()).strip()


def _looks_like_heading_text(text: str) -> bool:
    words = text.split()
    return (
        0 < len(words) <= _MAX_HEADING_WORDS
        and sum(c.isalpha() for c in text) >= 3
        and not text.rstrip().endswith((".", ",", ";"))
    )


_FRONT_MATTER = re.compile(
    r"^(table of )?contents?|^sommaire|^table des mati[eè]res|^foreword|^avant[- ]propos|^pr[eé]face"
    r"|^acknowledg|^remerciements|^abbreviations?|^abr[eé]viations?|^acronym|^sigles|^glossa"
)


def _is_front_matter(text: str) -> bool:
    return bool(_FRONT_MATTER.match(text.strip().lower()))


def _heading_levels_from_toc(doc: ExtractedDoc) -> dict[int, int]:
    """Map block index -> heading level, matching bookmark titles to blocks on their page."""
    by_page: dict[int, list[tuple[int, str]]] = {}
    for idx, block in enumerate(doc.blocks):
        by_page.setdefault(block.page, []).append((idx, _norm(block.text)))
    levels: dict[int, int] = {}
    for level, title, page in doc.toc:
        target = _norm(title)
        if len(target) < 3:
            continue
        nearby = [
            (idx, text)
            for idx, text in by_page.get(page, []) + by_page.get(page + 1, []) + by_page.get(page - 1, [])
            if idx not in levels
        ]
        exact = [idx for idx, text in nearby if text == target]
        prefix = [
            idx
            for idx, text in nearby
            if len(text) >= 8 and (text.startswith(target) or target.startswith(text))
        ]
        if exact or prefix:  # an exact match beats a prefix match (e.g. a contents-page line)
            levels[(exact or prefix)[0]] = min(level, _MAX_HEADING_LEVELS + 1)
    return levels


def _heading_levels_from_fonts(doc: ExtractedDoc) -> dict[int, int]:
    """Map block index -> heading level using font size (larger = higher) and boldness."""
    candidates: dict[int, float] = {}
    for idx, block in enumerate(doc.blocks):
        if not _looks_like_heading_text(block.text):
            continue
        if block.size >= doc.body_size + _HEADING_SIZE_DELTA:
            candidates[idx] = block.size
        elif block.bold and block.size >= doc.body_size - 0.5 and len(block.text.split()) <= 10:
            candidates[idx] = 0.0  # bold body-size line: lowest heading level
    sizes = sorted({s for s in candidates.values() if s > 0}, reverse=True)
    rank = {size: min(i + 1, _MAX_HEADING_LEVELS) for i, size in enumerate(sizes)}
    return {idx: rank.get(size, _MAX_HEADING_LEVELS + 1) for idx, size in candidates.items()}


def _sections(doc: ExtractedDoc) -> tuple[list[_Section], str]:
    """Group blocks into sections; also return which heading source was used."""
    use_toc = len(doc.toc) >= _MIN_TOC_ENTRIES
    levels = _heading_levels_from_toc(doc) if use_toc else _heading_levels_from_fonts(doc)
    stack: list[tuple[int, str]] = []
    sections: list[_Section] = [_Section("", [])]
    for idx, block in enumerate(doc.blocks):
        if idx in levels:
            level = levels[idx]
            if _is_front_matter(block.text) or (block.page == 1 and doc.page_count > 2):
                # Cover-page text and front-matter titles ("Contents", "Foreword"...) never
                # become parents of later sections: they get the deepest level so the next
                # real heading replaces them.
                level = _MAX_HEADING_LEVELS + 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, block.text))
            sections.append(_Section(" > ".join(text for _, text in stack), []))
        else:
            sections[-1].blocks.append(block)
    return [s for s in sections if s.blocks], "toc" if use_toc else "fonts"


def _units(block: Block, counter: TokenCounter, budget: int) -> list[tuple[str, int]]:
    """Split a block into (text, page) units that each fit ``budget`` tokens."""
    if counter.count(block.text) <= budget:
        return [(block.text, block.page)]
    units = []
    for sentence in _SENTENCE_END.split(block.text):
        if counter.count(sentence) <= budget:
            units.append((sentence, block.page))
        else:
            units.extend((sentence[s:e], block.page) for s, e in _token_windows(sentence, counter, budget, 0))
    return units


def structure_aware(doc: ExtractedDoc, title: str, counter: TokenCounter, config: ChunkingConfig) -> list[Chunk]:
    """Split on document headings, then pack paragraphs/sentences up to the token budget."""
    sections, _ = _sections(doc)
    chunks: list[Chunk] = []
    for section in sections:
        heading = section.path
        context = _context(title, heading) if config.contextual_header else ""
        budget = config.chunk_size - (counter.count(context) + 1 if context else 0)
        budget = max(budget, config.chunk_size // 2)  # very long headings must not starve the body

        units = [u for block in section.blocks for u in _units(block, counter, budget)]
        current: list[tuple[str, int, int]] = []  # (text, page, tokens)
        for text, page in units:
            tokens = counter.count(text)
            if current and sum(t for _, _, t in current) + tokens > budget:
                chunks.append(_pack(current, context, heading))
                current = _overlap_tail(current, config.chunk_overlap)
                if sum(t for _, _, t in current) + tokens > budget:
                    current = []
            current.append((text, page, tokens))
        if current:
            chunks.append(_pack(current, context, heading))
    return _finalise(_merge_small(chunks, counter, config), counter)


def _context(title: str, heading: str) -> str:
    """Contextual header "Title > Section > Subsection", without repeating the title."""
    parts = [p for p in heading.split(" > ") if p and _norm(p) != _norm(title)]
    return " > ".join([title, *parts])


def _pack(units: list[tuple[str, int, int]], context: str, heading: str) -> Chunk:
    return Chunk("\n".join(t for t, _, _ in units), context, heading, units[0][1], units[-1][1])


def _overlap_tail(units: list[tuple[str, int, int]], overlap: int) -> list[tuple[str, int, int]]:
    """Trailing whole units (sentences/paragraphs) of the previous chunk that fit in ``overlap`` tokens."""
    tail: list[tuple[str, int, int]] = []
    total = 0
    for unit in reversed(units):
        if total + unit[2] > overlap:
            break
        tail.insert(0, unit)
        total += unit[2]
    return tail


def _merge_small(chunks: list[Chunk], counter: TokenCounter, config: ChunkingConfig) -> list[Chunk]:
    """Merge chunks smaller than ``min_chunk_tokens`` into the following chunk when it fits."""
    merged: list[Chunk] = []
    pending: Chunk | None = None
    for chunk in chunks:
        if pending is not None:
            candidate = Chunk(
                f"{pending.text}\n{chunk.text}", chunk.context, chunk.heading, pending.page, chunk.page_end
            )
            if counter.count(candidate.embed_text) <= config.chunk_size:
                chunk = candidate
            else:
                merged.append(pending)
            pending = None
        if counter.count(chunk.embed_text) < config.min_chunk_tokens:
            pending = chunk
        else:
            merged.append(chunk)
    if pending is not None:
        merged.append(pending)
    return merged


def _finalise(chunks: list[Chunk], counter: TokenCounter) -> list[Chunk]:
    for chunk in chunks:
        chunk.n_tokens = counter.count(chunk.embed_text)
    return chunks


CHUNKERS: dict[str, Chunker] = {"fixed": fixed_size, "structure": structure_aware}
