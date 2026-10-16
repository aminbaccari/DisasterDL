"""Document loading and the two chunking strategies.

Strategy "fixed": windows of N words with overlap.
Strategy "section": split on detected headings, keep the heading in each chunk,
merge very short sections, and cap the size with the fixed splitter.

Sizes are counted in words, not model tokens. As a rough guide, 300 words is
about 400 to 500 tokens in English or French. Chunks never cross page
boundaries, so every chunk has an exact page number for citation.
"""
import re
from dataclasses import dataclass
from pathlib import Path

TOPICS = {"fire", "flood", "structural", "general"}
LANGUAGES = {"en", "fr"}
SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md"}
# Documentation that lives in the corpus folder but must not be indexed as knowledge.
NON_CORPUS_FILES = {"README.md", "SOURCES.md"}

_NUMBERED = re.compile(r"^\d+(\.\d+)*[.)]?\s+\S")
_END_PUNCT = (".", ",", ";", ":", "!", "?")


@dataclass
class Chunk:
    text: str
    page: int
    section: str = ""


def chunk_fixed(text, size=300, overlap=40):
    """Split text into windows of `size` words with `overlap` words shared."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    words = text.split()
    if not words:
        return []
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
    return chunks


def is_heading(line):
    """Heuristic heading detector. It will make mistakes on some PDFs."""
    s = line.strip()
    if not s or len(s) > 80:
        return False
    if s.startswith("#"):
        return True
    if s.endswith(_END_PUNCT):
        return False
    if _NUMBERED.match(s):
        return True
    if sum(c.isalpha() for c in s) < 3:
        return False
    if s.isupper():
        return True
    words = s.split()
    long_words = [w for w in words if len(w) > 3 and w[0].isalpha()]
    return len(words) <= 8 and len(long_words) > 0 and all(w[0].isupper() for w in long_words)


def split_sections(text, current=""):
    """Return ([(heading, body)], last_heading). `current` carries over from the previous page."""
    sections = []
    body = []
    for line in text.splitlines():
        if is_heading(line):
            if body:
                sections.append((current, " ".join(body).strip()))
                body = []
            current = line.strip().lstrip("#").strip()
        elif line.strip():
            body.append(line.strip())
    if body:
        sections.append((current, " ".join(body).strip()))
    return sections, current


def chunk_sections(text, max_words=300, overlap=40, min_words=30, current=""):
    """Return ([(heading, chunk_text)], last_heading)."""
    sections, last = split_sections(text, current)
    chunks = []
    pending_heading, pending_text = "", ""

    def flush():
        parts = chunk_fixed(pending_text, max_words, overlap)
        for i, part in enumerate(parts):
            if i > 0 and pending_heading:
                part = f"{pending_heading}. {part}"
            chunks.append((pending_heading, part))

    for heading, body in sections:
        piece = f"{heading}. {body}" if heading else body
        if pending_text:
            pending_text += " " + piece
        else:
            pending_heading, pending_text = heading, piece
        if len(pending_text.split()) >= min_words:
            flush()
            pending_heading, pending_text = "", ""
    if pending_text:
        flush()
    return chunks, last


def chunk_document(pages, strategy, size=300, overlap=40, min_words=30):
    """pages is a list of (page_number, text). Returns a list of Chunk."""
    if strategy not in ("fixed", "section"):
        raise ValueError(f"unknown strategy: {strategy}")
    out = []
    current = ""
    for page_number, text in pages:
        if strategy == "fixed":
            for piece in chunk_fixed(text, size, overlap):
                out.append(Chunk(piece, page_number))
        else:
            pieces, current = chunk_sections(text, size, overlap, min_words, current)
            for heading, piece in pieces:
                out.append(Chunk(piece, page_number, heading))
    return out


def read_pages(path):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader#type: ignore

        reader = PdfReader(str(path))
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    return [(1, path.read_text(encoding="utf-8"))]


def load_documents(corpus_dir):
    """Read every supported file under corpus_dir.

    Language comes from the parent folder (en or fr). Topic comes from the file
    name prefix (fire_, flood_, structural_, general_), for example
    fire_fema_p2143.pdf has topic fire.
    """
    docs = []
    for path in sorted(Path(corpus_dir).rglob("*")):
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if path.name in NON_CORPUS_FILES:
            continue
        language = path.parent.name if path.parent.name in LANGUAGES else "unknown"
        topic = path.stem.split("_")[0].lower()
        if topic not in TOPICS:
            topic = "general"
        docs.append(
            {"source": path.name, "language": language, "topic": topic, "pages": read_pages(path)}
        )
    return docs
