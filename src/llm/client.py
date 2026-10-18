"""VLM client backed by Ollama (llava-phi3 by default).

Ollama must be running locally (it starts automatically on Windows as a service).
Model is configured via VLM_MODEL in .env (default: llava-phi3).

encode_image(pil_image) → base64 string   (cheap, reusable across questions)
answer(b64_string, question) → str         (one Ollama API call)
"""

import logging

import httpx
from PIL import Image

from src.config import settings
from src.llm.image_utils import encode_image_b64
from src.llm.json_utils import parse_json_lenient

logger = logging.getLogger(__name__)

_TIMEOUT = 120  # seconds per Ollama call


class VLMClient:
    """Singleton Ollama VLM client."""

    _instance: "VLMClient | None" = None

    # ------------------------------------------------------------------
    # Public API  (same interface as before — no changes in vision_agent)
    # ------------------------------------------------------------------

    def encode_image(self, image: Image.Image) -> str:
        """Convert a PIL image to a base64 JPEG string for Ollama."""
        return encode_image_b64(image)

    def answer(self, encoded_b64: str, question: str) -> str:
        """Send an image + question to Ollama and return the text answer.

        Legacy single-question interface (prompt v1). Kept for backward
        compatibility; the main pipeline now uses answer_json (prompt v2).
        """
        logger.debug("Querying Ollama model=%s", settings.vlm_model)
        response = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.vlm_model,
                "prompt": question,
                "images": [encoded_b64],
                "stream": False,
                "options": {"num_predict": 150, "temperature": 0},
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    def answer_json(
        self,
        encoded_b64: str,
        prompt: str,
        system_prompt: str = "",
    ) -> dict:
        """Send an image + prompt to Ollama via /api/chat and return parsed JSON.

        Uses Ollama's "format": "json" constraint plus a lenient parser as a
        safety net for older models that occasionally wrap JSON in prose.
        """
        logger.debug("Querying Ollama (chat) model=%s", settings.vlm_model)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt, "images": [encoded_b64]})

        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.vlm_model,
                "messages": messages,
                "format": "json",
                "stream": False,
                "options": {"num_predict": 400, "temperature": 0},
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        return parse_json_lenient(content)

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get(cls) -> "VLMClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Release the singleton (for testing)."""
        cls._instance = None
