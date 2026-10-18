"""Tests for the RAG generation step (src/rag/generate.py); the LLM and the NLI model are mocked."""

import pytest

from src.rag import generate
from src.rag.generate import NO_PASSAGES, OUT_OF_SCOPE, citation, format_passages, generate_answer, scope_gate
from src.schemas import RetrievedChunk


def _chunk(source_id: str, page: int, text: str, page_end: int | None = None, score: float = 0.85) -> RetrievedChunk:
    return RetrievedChunk(
        text=text, chunk_id=f"{source_id}:{page}", source_id=source_id, title=f"Title {source_id}",
        page=page, page_end=page_end, heading="Before > During", disaster_type="flood",
        language="en", reliability="high", score=score,
    )


CHUNKS = [
    _chunk("FLOOD-01", 2, "Never walk or drive through flood waters. Turn around, don't drown."),
    _chunk("GEN-01", 198, "Heavy damage includes partial or total collapse.", page_end=199),
]


class FakeNLI:
    """Entailment = 1.0 unless the statement contains 'invented'."""

    def entailment(self, pairs):
        return [0.0 if "invented" in h.lower() else 1.0 for _, h in pairs]


@pytest.fixture(autouse=True)
def fake_nli(monkeypatch):
    monkeypatch.setattr(generate, "get_nli", lambda: FakeNLI())


def _llm(monkeypatch, *answers):
    """Make chat_json return the given answers in order; record the messages sent."""
    calls = []
    replies = iter(answers)

    def fake_chat_json(messages, schema, **kwargs):
        calls.append(messages)
        return schema(**next(replies))

    monkeypatch.setattr(generate.client, "chat_json", fake_chat_json)
    return calls


def test_citation_and_passage_formatting() -> None:
    assert citation(CHUNKS[0]) == "FLOOD-01 p.2"
    assert citation(CHUNKS[1]) == "GEN-01 p.198-199"
    text, tags = format_passages(CHUNKS)
    assert text.startswith("[S1] FLOOD-01 p.2, Title FLOOD-01, section: Before > During\nNever walk")
    assert set(tags) == {"S1", "S2"}


def test_no_passages_means_no_llm_call(monkeypatch) -> None:
    _llm(monkeypatch)  # any call would fail: no answer queued
    answer = generate_answer("water in the street", [])
    assert answer.answer == NO_PASSAGES and answer.guidance == []


def test_scope_gate_for_untyped_incidents(monkeypatch) -> None:
    weak = [_chunk("GEN-02", 7, "Keep emergency numbers.", score=0.80)]
    assert scope_gate(None, weak) and scope_gate("other", weak)
    assert not scope_gate("flood", weak)  # typed incidents are never gated
    assert not scope_gate(None, [_chunk("FLOOD-01", 2, "x", score=0.86)])
    _llm(monkeypatch)
    answer = generate_answer("How do I file my taxes?", weak, None)
    assert answer.abstained_by_gate and not answer.in_scope and answer.answer == OUT_OF_SCOPE


def test_model_scope_decision_is_enforced(monkeypatch) -> None:
    strong = [_chunk("GEN-02", 46, "Protect crops from drought.", score=0.86)]
    _llm(monkeypatch, {"in_scope": False, "answer": "x",
                       "guidance": [{"quote": "Protect crops from drought.", "statement": "Protect crops.", "sources": ["S1"]}]})
    answer = generate_answer("Locust swarms on my farm", strong, None)
    assert not answer.in_scope and answer.guidance == [] and not answer.abstained_by_gate


def test_retry_when_strong_passages_give_no_guidance(monkeypatch) -> None:
    good = {"quote": "Never walk or drive through flood waters.", "statement": "Do not drive through flood water.", "sources": ["S1"]}
    calls = _llm(monkeypatch, {"answer": "Nothing relevant.", "guidance": []}, {"answer": "Avoid floodwater.", "guidance": [good]})
    answer = generate_answer("flooded street", CHUNKS, "flood")
    assert answer.retried and len(calls) == 2 and [g.citations for g in answer.guidance] == [["FLOOD-01 p.2"]]
    assert "contains no guidance" in calls[1][-1]["content"]


def test_checks_and_filtering(monkeypatch) -> None:
    llm_answer = {
        "answer": "Avoid floodwater.",
        "guidance": [
            {"quote": "Never walk or drive through flood waters.", "statement": "Do not drive through flood water.", "sources": ["S1"]},
            {"quote": "x", "statement": "No provided passage.", "sources": ["S9"]},  # dropped: cites nothing provided
            {"quote": "Buildings always collapse.", "statement": "Collapse risk.", "sources": ["[s2]", "S7"]},  # bad quote
            {"quote": "Heavy damage includes partial or total collapse.", "statement": "Invented: evacuate within 5 minutes.", "sources": ["S2"]},  # not entailed
        ],
        "not_covered": ["water depth"],
    }
    _llm(monkeypatch, llm_answer, llm_answer)
    everything = generate_answer("flooded street", CHUNKS, "flood", verified_only=False, check_entailment=True)
    assert [g.citations for g in everything.guidance] == [["FLOOD-01 p.2"], ["GEN-01 p.198-199"], ["GEN-01 p.198-199"]]
    assert [g.quote_verified for g in everything.guidance] == [True, False, True]
    assert [g.entailment for g in everything.guidance] == [1.0, 1.0, 0.0]
    assert everything.invalid_citations == 2  # S9 and S7

    filtered = generate_answer("flooded street", CHUNKS, "flood", check_entailment=True)
    assert [g.statement for g in filtered.guidance] == ["Do not drive through flood water."]
    assert [g.statement for g in filtered.unverified_guidance] == ["Collapse risk.", "Invented: evacuate within 5 minutes."]
    assert filtered.not_covered == ["water depth"]
