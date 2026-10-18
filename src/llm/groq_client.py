"""VLM client backed by Groq's OpenAI-compatible Chat Completions API.

Model is configured via GROQ_MODEL in .env (default: qwen/qwen3.8-27b, a
multimodal preview model with JSON mode and up to 3 images/request).

encode_image(pil_image) → base64 string
answer_json(b64_string, prompt, system_prompt) → dict   (one Groq API call,
    JSON mode enforced server-side via response_format)
"""

import logging
import time

import httpx
from PIL import Image

from src.config import settings
from src.llm.image_utils import encode_image_b64
from src.llm.json_utils import parse_json_lenient

logger = logging.getLogger(__name__)

_TIMEOUT = 60  # seconds per Groq call
_MAX_RETRIES = 3  # total attempts (2 retries) — cloud calls see occasional transient SSL/network blips
_RETRY_BACKOFF = 2.0  # seconds


class GroqVLMClient:
    """Singleton Groq VLM client."""

    _instance: "GroqVLMClient | None" = None

    def __init__(self) -> None:
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Add it to your .env file "
                "(get one at https://console.groq.com/keys)."
            )
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.base_url = settings.groq_base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encode_image(self, image: Image.Image) -> str:
        return encode_image_b64(image)

    def answer_json(
        self,
        encoded_b64: str,
        prompt: str,
        system_prompt: str = "",
    ) -> dict:
        """Send an image + prompt to Groq and return the parsed JSON response.

        Retries once on network error, 5xx, or 429 (rate limit).
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded_b64}"},
                    },
                ],
            }
        )
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 500,
        }

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                logger.debug("Querying Groq model=%s (attempt %d)", self.model, attempt + 1)
                response = httpx.post(url, headers=headers, json=payload, timeout=_TIMEOUT)
                if response.status_code == 429 and attempt < _MAX_RETRIES - 1:
                    retry_after = float(response.headers.get("Retry-After", _RETRY_BACKOFF))
                    logger.warning("Groq rate limited; retrying in %.1fs", retry_after)
                    time.sleep(retry_after)
                    continue
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return parse_json_lenient(content)
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    logger.warning("Groq call failed (%s); retrying...", exc)
                    time.sleep(_RETRY_BACKOFF)
                    continue

        raise RuntimeError(f"Groq VLM call failed after {_MAX_RETRIES} attempts: {last_exc}")

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get(cls) -> "GroqVLMClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Release the singleton (for testing)."""
        cls._instance = None
