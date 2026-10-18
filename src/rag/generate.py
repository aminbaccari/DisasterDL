"""Generation step of the RAG: a grounded answer from the retrieved passages.

Steps 5 and 6 of the RAG pipeline:
    5. prompt construction: the retrieved passages are numbered [S1]..[Sn], each labelled with its
       source ID, page and section, and inserted with the incident into prompt ``rag_answer``;
    6. generation: the system LLM (gemma3:4b through Ollama) writes a JSON answer whose every
       statement cites passage tags and quotes one sentence verbatim.

Post-processing makes the answer checkable: tags are mapped back to "SOURCE-ID p.N" citations,
citations to passages that were not provided are removed and counted, every quote is verified
against the passages it cites (``quote_verified``), and statements with an unverified quote are
set aside (``unverified_guidance``). When retrieval returned nothing, no
LLM call is made and the answer states that the knowledge base does not cover the incident.
"""

from pydantic import BaseModel, Field

from src.llm import client
from src.llm.prompt_loader import build_messages, load_prompt
from src.schemas import GroundedAnswer, GuidanceItem, RetrievedChunk
from src.utils.logging_utils import get_logger
from src.utils.text_match import quote_found

logger = get_logger(__name__)

PASSAGE_CHARS = 1800  # cap per passage so that 5 passages + prompt + answer fit a 4k-token context
NO_PASSAGES = "The knowledge base contains no passage relevant enough to this incident."


class _LLMItem(BaseModel):
    statement: str = Field(min_length=3)
    sources: list[str] = Field(default_factory=list)
    quote: str = ""


class _LLMAnswer(BaseModel):
    answer: str = ""
    guidance: list[_LLMItem] = Field(default_factory=list)
    not_covered: list[str] = Field(default_factory=list)


def citation(chunk: RetrievedChunk) -> str:
    """Human-readable citation of a chunk, e.g. 'FLOOD-01 p.2' or 'GEN-01 p.198-199'."""
    if chunk.page is None:
        return chunk.source_id
    pages = f"{chunk.page}" if not chunk.page_end or chunk.page_end == chunk.page else f"{chunk.page}-{chunk.page_end}"
    return f"{chunk.source_id} p.{pages}"


def format_passages(chunks: list[RetrievedChunk]) -> tuple[str, dict[str, RetrievedChunk]]:
    """Number the passages [S1]..[Sn] with their provenance; return the prompt text and the tag map."""
    tags: dict[str, RetrievedChunk] = {}
    blocks = []
    for i, chunk in enumerate(chunks, 1):
        tag = f"S{i}"
        tags[tag] = chunk
        section = f", section: {chunk.heading}" if chunk.heading else ""
        text = chunk.text if len(chunk.text) <= PASSAGE_CHARS else chunk.text[:PASSAGE_CHARS] + " [...]"
        blocks.append(f"[{tag}] {citation(chunk)}, {chunk.title}{section}\n{text}")
    return "\n\n".join(blocks), tags


def _normalise_tag(tag: str) -> str:
    return tag.strip().strip("[]").upper()


def generate_answer(
    report: str,
    chunks: list[RetrievedChunk],
    incident_type: str | None = None,
    version: int | None = None,
    model: str | None = None,
    verified_only: bool = True,
) -> GroundedAnswer:
    """Generate a grounded answer for an incident from its retrieved passages.

    With ``verified_only`` (default), statements whose quote is not found in a cited passage are
    moved to ``unverified_guidance``: in the generation evaluation 43% of those were judged
    unsupported, against 2% of statements with a verified quote.
    """
    if not chunks:
        return GroundedAnswer(answer=NO_PASSAGES, guidance=[], not_covered=["the whole incident"])

    passages, tags = format_passages(chunks)
    prompt = load_prompt("rag_answer", version)
    messages = build_messages(prompt, report=report, incident_type=incident_type or "unknown", passages=passages)
    raw = client.chat_json(messages, _LLMAnswer, model=model)

    items: list[GuidanceItem] = []
    invalid = 0
    for item in raw.guidance:
        cited = [tags[t] for t in map(_normalise_tag, item.sources) if t in tags]
        invalid += len(item.sources) - len(cited)
        if not cited:
            continue  # a statement citing no provided passage is not grounded: dropped
        items.append(
            GuidanceItem(
                statement=item.statement.strip(),
                citations=list(dict.fromkeys(citation(c) for c in cited)),
                quote=item.quote.strip(),
                quote_verified=any(quote_found(item.quote, c.text) for c in cited),
            )
        )
    if invalid:
        logger.warning("Removed %d citation(s) to passages that were not provided", invalid)
    verified = [g for g in items if g.quote_verified] if verified_only else items
    unverified = [g for g in items if not g.quote_verified] if verified_only else []
    return GroundedAnswer(
        answer=raw.answer.strip(), guidance=verified, unverified_guidance=unverified,
        not_covered=raw.not_covered, invalid_citations=invalid,
    )
