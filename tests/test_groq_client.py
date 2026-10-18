"""Unit tests for GroqVLMClient — all HTTP calls mocked, no real API hit."""

import httpx
import pytest
from PIL import Image
from unittest.mock import MagicMock, patch


def _fake_groq_response(content: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestGroqVLMClient:

    def setup_method(self):
        from src.llm.groq_client import GroqVLMClient
        GroqVLMClient.reset()

    def teardown_method(self):
        from src.llm.groq_client import GroqVLMClient
        GroqVLMClient.reset()

    def test_missing_api_key_raises(self):
        from src.llm.groq_client import GroqVLMClient
        with patch("src.llm.groq_client.settings") as mock_settings:
            mock_settings.groq_api_key = ""
            with pytest.raises(ValueError, match="GROQ_API_KEY"):
                GroqVLMClient()

    def test_answer_json_success(self):
        from src.llm.groq_client import GroqVLMClient
        with patch("src.llm.groq_client.settings") as mock_settings:
            mock_settings.groq_api_key = "fake-key"
            mock_settings.groq_model = "qwen/qwen3.8-27b"
            mock_settings.groq_base_url = "https://api.groq.com/openai/v1"
            client = GroqVLMClient()

        content = '{"class": "fire", "description": "x", "evidence": ["flames"]}'
        with patch("src.llm.groq_client.httpx.post", return_value=_fake_groq_response(content)):
            result = client.answer_json("b64data", "classify this")

        assert result["class"] == "fire"

    def test_answer_json_retries_on_failure_then_succeeds(self):
        from src.llm.groq_client import GroqVLMClient
        with patch("src.llm.groq_client.settings") as mock_settings:
            mock_settings.groq_api_key = "fake-key"
            mock_settings.groq_model = "qwen/qwen3.8-27b"
            mock_settings.groq_base_url = "https://api.groq.com/openai/v1"
            client = GroqVLMClient()

        good = _fake_groq_response('{"class": "flood", "description": "x", "evidence": []}')
        with patch(
            "src.llm.groq_client.httpx.post",
            side_effect=[httpx.ConnectError("network down"), good],
        ):
            with patch("src.llm.groq_client.time.sleep"):  # skip real backoff delay
                result = client.answer_json("b64data", "classify this")

        assert result["class"] == "flood"

    def test_answer_json_raises_after_exhausting_retries(self):
        from src.llm.groq_client import GroqVLMClient
        with patch("src.llm.groq_client.settings") as mock_settings:
            mock_settings.groq_api_key = "fake-key"
            mock_settings.groq_model = "qwen/qwen3.8-27b"
            mock_settings.groq_base_url = "https://api.groq.com/openai/v1"
            client = GroqVLMClient()

        with patch(
            "src.llm.groq_client.httpx.post",
            side_effect=httpx.ConnectError("network down"),
        ):
            with patch("src.llm.groq_client.time.sleep"):
                with pytest.raises(RuntimeError, match="Groq VLM call failed"):
                    client.answer_json("b64data", "classify this")

    def test_singleton_get_returns_same_instance(self):
        from src.llm.groq_client import GroqVLMClient
        with patch("src.llm.groq_client.settings") as mock_settings:
            mock_settings.groq_api_key = "fake-key"
            mock_settings.groq_model = "qwen/qwen3.8-27b"
            mock_settings.groq_base_url = "https://api.groq.com/openai/v1"
            first = GroqVLMClient.get()
            second = GroqVLMClient.get()
        assert first is second

    def test_encode_image_returns_string(self):
        from src.llm.groq_client import GroqVLMClient
        with patch("src.llm.groq_client.settings") as mock_settings:
            mock_settings.groq_api_key = "fake-key"
            mock_settings.groq_model = "qwen/qwen3.8-27b"
            mock_settings.groq_base_url = "https://api.groq.com/openai/v1"
            client = GroqVLMClient()
        encoded = client.encode_image(Image.new("RGB", (32, 32)))
        assert isinstance(encoded, str)
        assert len(encoded) > 0
