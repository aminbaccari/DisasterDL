"""Tests for the LLM client and prompt loader; the HTTP layer is mocked (no network)."""

import httpx
import pytest
from pydantic import BaseModel

from src.llm import client
from src.llm.prompt_loader import build_messages, load_prompt


class Answer(BaseModel):
    query: str


def _reply(content: str) -> httpx.Response:
    request = httpx.Request("POST", "http://test/chat/completions")
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": {}}, request=request)


def test_chat_json_parses_fenced_json(monkeypatch) -> None:
    monkeypatch.setattr(client.httpx, "post", lambda *a, **k: _reply('```json\n{"query": "flood safety"}\n```'))
    assert client.chat_json([{"role": "user", "content": "x"}], Answer).query == "flood safety"


def test_chat_json_retries_once_then_succeeds(monkeypatch) -> None:
    replies = iter([_reply("not json"), _reply('{"query": "wildfire evacuation"}')])
    calls = []
    monkeypatch.setattr(client.httpx, "post", lambda *a, **k: calls.append(k["json"]) or next(replies))
    assert client.chat_json([{"role": "user", "content": "x"}], Answer).query == "wildfire evacuation"
    assert "not valid" in calls[1]["messages"][-1]["content"]  # error fed back to the model


def test_chat_json_raises_after_second_failure(monkeypatch) -> None:
    monkeypatch.setattr(client.httpx, "post", lambda *a, **k: _reply('{"wrong": 1}'))
    with pytest.raises(client.LLMOutputError) as info:
        client.chat_json([{"role": "user", "content": "x"}], Answer)
    assert info.value.raw_output == '{"wrong": 1}'


def test_prompt_loader_latest_version_and_rendering(tmp_path) -> None:
    folder = tmp_path / "demo"
    folder.mkdir()
    for v in (1, 2):
        (folder / f"v{v}.yaml").write_text(
            f"name: demo\nversion: {v}\nrole: r\ntechnique: [few-shot]\nchangelog: c\n"
            "system: sys\nuser: 'Report: {report}'\nfew_shot:\n  - input: a\n    output: b\n",
            encoding="utf-8",
        )
    prompt = load_prompt("demo", prompts_dir=tmp_path)
    assert prompt.version == 2
    messages = build_messages(prompt, report="smoke")
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[-1]["content"] == "Report: smoke"
    with pytest.raises(KeyError):
        build_messages(prompt)


def test_real_query_rewrite_prompt_loads() -> None:
    prompt = load_prompt("rag_query_rewrite", 1)
    assert "structured output (JSON object)" in prompt.technique
    build_messages(prompt, report="r", incident_type="flood")
