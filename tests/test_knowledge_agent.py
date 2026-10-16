"""Tests for the knowledge agent's query strategy (retriever and LLM are mocked)."""

from src.agents import knowledge_agent
from src.llm import client
from src.schemas import IncidentInfo


def _incident(language: str) -> IncidentInfo:
    return IncidentInfo(incident_type="flood", language=language, reported_observations=["water entering homes"])


def _capture(monkeypatch) -> dict:
    calls: dict = {}

    def fake_retrieve(query, **kwargs):
        calls.update(query=query, **kwargs)
        return []

    monkeypatch.setattr(knowledge_agent, "retrieve", fake_retrieve)
    return calls


def test_corpus_language_uses_raw_report_without_llm(monkeypatch) -> None:
    calls = _capture(monkeypatch)
    monkeypatch.setattr(knowledge_agent, "rewrite_query", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    result = knowledge_agent.run(_incident("fr"))
    assert calls["extra_queries"] == [] and calls["rerank"] is True
    assert calls["disaster_type"] == "flood" and result.query_used == "water entering homes"


def test_other_language_fuses_rewrite(monkeypatch) -> None:
    calls = _capture(monkeypatch)
    monkeypatch.setattr(knowledge_agent, "rewrite_query", lambda *a, **k: "flooded homes")
    result = knowledge_agent.run(_incident("ar"))
    assert calls["extra_queries"] == ["flooded homes"]
    assert result.query_used == "water entering homes || flooded homes"


def test_rewrite_failure_falls_back_to_raw(monkeypatch) -> None:
    calls = _capture(monkeypatch)

    def failing(*a, **k):
        raise client.LLMError("down")

    monkeypatch.setattr(knowledge_agent, "rewrite_query", failing)
    knowledge_agent.run(_incident("ar"))
    assert calls["extra_queries"] == []
