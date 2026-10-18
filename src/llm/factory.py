"""VLM provider factory — selects Groq (cloud) or Ollama (local) by config.

VLM_PROVIDER=groq (default) uses the Groq-hosted Qwen VL model for
classification quality; VLM_PROVIDER=ollama falls back to the local
LLaVA-Phi3 model for offline work. Both clients expose the same
encode_image / answer_json interface, so vision_agent.py doesn't need
to know which one it's talking to.
"""

from src.config import settings


def get_vlm_client():
    """Return the configured VLM client singleton."""
    provider = settings.vlm_provider.lower()
    if provider == "groq":
        from src.llm.groq_client import GroqVLMClient
        return GroqVLMClient.get()
    if provider == "ollama":
        from src.llm.client import VLMClient
        return VLMClient.get()
    raise ValueError(f"Unknown VLM_PROVIDER: {provider!r} (expected 'groq' or 'ollama')")
