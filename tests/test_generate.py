"""Tests for the RAG generation step (src/rag/generate.py); the LLM is mocked."""

from src.rag import generate
from src.rag.generate import NO_PASSAGES, citation, format_passages, generate_answer
from src.schemas import RetrievedChunk


def _chunk(source_id: str, page: int, text: str, page_end: int | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        text=text, chunk_id=f"{source_id}:{page}", source_id=source_id, title=f"Title {source_id}",
        page=page, page_end=page_end, heading="Before > During", disaster_type="flood",
        language="en", reliability="high", score=0.85,
    )


CHUNKS = [
    _chunk("FLOOD-01", 2, "Never walk or drive through flood waters. Turn around, don't drown."),
    _chunk("GEN-01", 198, "Heavy damage includes partial or total collapse.", page_end=199),
]


def test_citation_and_passage_formatting() -> None:
    assert citation(CHUNKS[0]) == "FLOOD-01 p.2"
    assert citation(CHUNKS[1]) == "GEN-01 p.198-199"
    text, tags = format_passages(CHUNKS)
    assert text.startswith("[S1] FLOOD-01 p.2, Title FLOOD-01, section: Before > During\nNever walk")
    assert set(tags) == {"S1", "S2"}


def test_no_passages_means_no_llm_call(monkeypatch) -> None:
    monkeypatch.setattr(generate.client, "chat_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    answer = generate_answer("water in the street", [])
    assert answer.answer == NO_PASSAGES and answer.guidance == []


def test_tags_mapped_invalid_citations_dropped_and_quotes_verified(monkeypatch) -> None:
    def fake_chat_json(messages, schema, **kwargs):
        assert "[S1] FLOOD-01 p.2" in messages[-1]["content"]
        return schema(
            answer="Avoid floodwater.",
            guidance=[
                {"statement": "Do not drive through flood water.", "sources": ["S1"], "quote": "Never walk or drive through flood waters."},
                {"statement": "Invented advice.", "sources": ["S9"], "quote": "x"},  # passage not provided
                {"statement": "Collapse risk.", "sources": ["[s2]", "S7"], "quote": "Buildings always collapse."},  # bad quote
            ],
            not_covered=["water depth"],
        )

    monkeypatch.setattr(generate.client, "chat_json", fake_chat_json)
    answer = generate_answer("flooded street", CHUNKS, "flood", verified_only=False)
    assert [g.citations for g in answer.guidance] == [["FLOOD-01 p.2"], ["GEN-01 p.198-199"]]
    assert [g.quote_verified for g in answer.guidance] == [True, False]

    filtered = generate_answer("flooded street", CHUNKS, "flood")  # default: verified statements only
    assert [g.statement for g in filtered.guidance] == ["Do not drive through flood water."]
    assert [g.statement for g in filtered.unverified_guidance] == ["Collapse risk."]
    assert answer.invalid_citations == 2  # S9 and S7
    assert answer.not_covered == ["water depth"]
