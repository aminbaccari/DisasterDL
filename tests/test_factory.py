"""Unit tests for the VLM provider factory."""

import pytest
from unittest.mock import MagicMock, patch

from src.llm.factory import get_vlm_client


def test_factory_returns_groq_client_when_configured():
    with patch("src.llm.factory.settings") as mock_settings:
        mock_settings.vlm_provider = "groq"
        fake_groq = MagicMock()
        with patch("src.llm.groq_client.GroqVLMClient.get", return_value=fake_groq):
            result = get_vlm_client()
    assert result is fake_groq


def test_factory_returns_ollama_client_when_configured():
    with patch("src.llm.factory.settings") as mock_settings:
        mock_settings.vlm_provider = "ollama"
        fake_ollama = MagicMock()
        with patch("src.llm.client.VLMClient.get", return_value=fake_ollama):
            result = get_vlm_client()
    assert result is fake_ollama


def test_factory_is_case_insensitive():
    with patch("src.llm.factory.settings") as mock_settings:
        mock_settings.vlm_provider = "GROQ"
        fake_groq = MagicMock()
        with patch("src.llm.groq_client.GroqVLMClient.get", return_value=fake_groq):
            result = get_vlm_client()
    assert result is fake_groq


def test_factory_raises_on_unknown_provider():
    with patch("src.llm.factory.settings") as mock_settings:
        mock_settings.vlm_provider = "bogus"
        with pytest.raises(ValueError, match="Unknown VLM_PROVIDER"):
            get_vlm_client()
