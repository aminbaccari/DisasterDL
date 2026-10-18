"""Generation step of the RAG: a grounded answer from the retrieved passages.

Steps 5 and 6 of the RAG pipeline:
    5. prompt construction: the retrieved passages are numbered [S1]..[Sn], each labelled with its
       source ID, page and section, and inserted with the incident into prompt ``rag_answer``;
    6. generation: the system LLM (gemma3:4b through Ollama) writes a JSON answer whose every
       statement rephrases a quoted sentence of a cited passage.

There is no verifier agent downstream, so the answer checks itself:
    - scope gate (before generation): an incident without a hazard type (other/unknown) is only
      answered if a passage reaches the stricter threshold ``UNTYPED_THRESHOLD``; otherwise no LLM
      call is made;
    - scope decision (in the answer): the model's explicit ``in_scope`` field is enforced in code;
    - refusal retry: when strong passages were retrieved for a typed incident but no guidance came
      back, generation is retried once with feedback;
    - citation check: tags are mapped to "SOURCE-ID p.N"; citations to passages that were not
      provided are removed and counted;
    - quote check: the quote must appear verbatim in a cited passage;
    - entailment check (optional, off by default): an NLI model must find that the quote or a cited
      passage entails the statement. Measured on judged statements it removed far more correct
      statements than unsupported ones, so the quote check is the filter used by default.
Statements that fail a check are moved to ``unverified_guidance``.
"""

from pydantic import BaseModel, Field

from src.llm import client
from src.llm.prompt_loader import build_messages, load_prompt
from src.rag.nli import ENTAILMENT_THRESHOLD, get_nli
from src.schemas import GroundedAnswer, GuidanceItem, RetrievedChunk
from src.utils.logging_utils import get_logger
from src.utils.text_match import quote_found

logger = get_logger(__name__)

PASSAGE_CHARS = 1800  # cap per passage so that 5 passages + prompt + answer fit a 4k-token context
TYPED_INCIDENTS = {"fire", "flood", "structural"}
UNTYPED_THRESHOLD = 0.83  # stricter similarity for incidents with no hazard type (see FAILURES.md GEN-03)
RETRY_SCORE = 0.82  # a passage this similar should yield some guidance for a typed incident
NO_PASSAGES = "The knowledge base contains no passage relevant enough to this incident."
OUT_OF_SCOPE = "The request is outside the scope of the knowledge base (fire, flood and building emergencies)."
RETRY_FEEDBACK = (
    "Your answer contains no guidance, but these passages were retrieved as relevant to this incident. "
    "Read them again and extract what they say that applies to this situation, including how the hazard "
    "behaves. Reply again with the same JSON format."
)


class _LLMItem(BaseModel):
    quote: str = ""
    statement: str = Field(min_length=3)
    sources: list[str] = Field(default_factory=list)


class _LLMAnswer(BaseModel):
    in_scope: bool = True
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


def scope_gate(incident_type: str | None, chunks: list[RetrievedChunk]) -> bool:
    """True when generation should be skipped: untyped incident and no sufficiently similar passage."""
    if str(incident_type) in TYPED_INCIDENTS:
        return False
    return not any(c.score >= UNTYPED_THRESHOLD for c in chunks)


def _normalise_tag(tag: str) -> str:
    return tag.strip().strip("[]").upper()


def _items(raw: _LLMAnswer, tags: dict[str, RetrievedChunk]) -> tuple[list[GuidanceItem], int, list[list[RetrievedChunk]]]:
    """Map tags to citations; drop statements citing no provided passage; check quotes."""
    items, cited_chunks, invalid = [], [], 0
    for item in raw.guidance:
        cited = [tags[t] for t in map(_normalise_tag, item.sources) if t in tags]
        invalid += len(item.sources) - len(cited)
        if not cited:
            continue  # a statement citing no provided passage is not grounded: dropped
        items.append(GuidanceItem(
            statement=item.statement.strip(),
            citations=list(dict.fromkeys(citation(c) for c in cited)),
            quote=item.quote.strip(),
            quote_verified=any(quote_found(item.quote, c.text) for c in cited),
        ))
        cited_chunks.append(cited)
    return items, invalid, cited_chunks


def _add_entailment(items: list[GuidanceItem], cited_chunks: list[list[RetrievedChunk]]) -> None:
    """Highest probability that the quote or one of the cited passages entails each statement."""
    pairs, owners = [], []
    for i, (item, cited) in enumerate(zip(items, cited_chunks)):
        premises = ([item.quote] if item.quote else []) + [c.text for c in cited]
        for premise in premises:
            pairs.append((premise, item.statement))
            owners.append(i)
    if not pairs:
        return
    scores = get_nli().entailment(pairs)
    for i, item in enumerate(items):
        item.entailment = round(max(s for o, s in zip(owners, scores) if o == i), 4)


def generate_answer(
    report: str,
    chunks: list[RetrievedChunk],
    incident_type: str | None = None,
    version: int | None = None,
    model: str | None = None,
    verified_only: bool = True,
    use_gate: bool = True,
    check_entailment: bool = False,
) -> GroundedAnswer:
    """Generate a grounded, self-checked answer for an incident from its retrieved passages.

    Args:
        report: Incident description (reported observations).
        chunks: Retrieved passages, best first.
        incident_type: Hazard type from the incident agent; None/other/unknown triggers the scope gate.
        version: Prompt version of ``rag_answer`` (default: latest).
        model: LLM override (default: configured system LLM).
        verified_only: Keep in ``guidance`` only statements that pass the quote and entailment checks;
            the others go to ``unverified_guidance``.
        use_gate: Apply the scope gate before generation.
        check_entailment: Run the NLI entailment check (off by default: on the judged v3
            statements it removed 32 statements, 81% of them correct, to catch a single
            unsupported one, and it adds about 60-70 s per answer on CPU; see FAILURES.md GEN-07).
    """
    if not chunks:
        return GroundedAnswer(answer=NO_PASSAGES, not_covered=["the whole incident"])
    if use_gate and scope_gate(incident_type, chunks):
        return GroundedAnswer(answer=OUT_OF_SCOPE, in_scope=False, abstained_by_gate=True)

    passages, tags = format_passages(chunks)
    prompt = load_prompt("rag_answer", version)
    messages = build_messages(prompt, report=report, incident_type=incident_type or "unknown", passages=passages)
    raw = client.chat_json(messages, _LLMAnswer, model=model)
    items, invalid, cited = _items(raw, tags)

    retried = False
    typed = str(incident_type) in TYPED_INCIDENTS
    if not items and typed and max(c.score for c in chunks) >= RETRY_SCORE:
        retried = True
        logger.info("No guidance from strong passages for a %s incident: retrying once", incident_type)
        retry_messages = [*messages, {"role": "assistant", "content": raw.model_dump_json()},
                          {"role": "user", "content": RETRY_FEEDBACK}]
        raw = client.chat_json(retry_messages, _LLMAnswer, model=model)
        items, invalid, cited = _items(raw, tags)

    in_scope = raw.in_scope or typed  # a typed incident is an emergency by definition
    if not in_scope:
        return GroundedAnswer(answer=OUT_OF_SCOPE, in_scope=False, retried=retried)
    if check_entailment and items:
        _add_entailment(items, cited)
    if invalid:
        logger.warning("Removed %d citation(s) to passages that were not provided", invalid)

    def passes(g: GuidanceItem) -> bool:
        entailed = g.entailment is None or g.entailment >= ENTAILMENT_THRESHOLD
        return g.quote_verified and entailed

    verified = [g for g in items if passes(g)] if verified_only else items
    unverified = [g for g in items if not passes(g)] if verified_only else []
    return GroundedAnswer(
        answer=raw.answer.strip(), guidance=verified, unverified_guidance=unverified,
        not_covered=raw.not_covered, invalid_citations=invalid, in_scope=True, retried=retried,
    )
