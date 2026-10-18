"""Provider-agnostic LLM and VLM client.

All model calls go through this module. It speaks the OpenAI ``/chat/completions`` protocol,
which local Ollama and most hosted providers (Groq, Gemini, OpenRouter, OpenAI...) expose, so
switching provider is a configuration change only (``LLM_BASE_URL``, ``LLM_API_KEY``, ``LLM_MODEL``).

``chat_json`` enforces structured output: the reply is parsed and validated with a Pydantic
model; on failure the validation error is sent back to the model for one retry, and a second
failure raises ``LLMOutputError`` carrying the raw output.
"""

import base64
import json
import mimetypes
import re
import time
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from src.config import get_settings
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)
Message = dict[str, object]

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class LLMError(RuntimeError):
    """The provider could not be reached or returned an error."""


class LLMOutputError(ValueError):
    """The model's output could not be validated against the expected schema."""

    def __init__(self, message: str, raw_output: str) -> None:
        super().__init__(message)
        self.raw_output = raw_output


_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 6


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """Seconds to wait before retrying: the provider's Retry-After header, else exponential backoff."""
    header = response.headers.get("retry-after")
    try:
        return min(float(header), 120.0) if header else min(2.0 ** attempt, 60.0)
    except ValueError:
        return min(2.0 ** attempt, 60.0)


def chat(
    messages: list[Message],
    model: str | None = None,
    temperature: float | None = None,
    json_mode: bool = False,
    base_url: str | None = None,
    api_key: str | None = None,
    extra: dict[str, object] | None = None,
) -> str:
    """Send a chat completion request and return the assistant's text.

    ``base_url`` / ``api_key`` override the configured provider for this call (used by the
    offline relevance judges); ``extra`` adds provider-specific fields such as
    ``reasoning_effort``. Rate-limit (429) and transient server errors are retried with the
    provider's Retry-After delay or exponential backoff.
    """
    settings = get_settings()
    base_url = (base_url or settings.llm_base_url).rstrip("/")
    payload: dict[str, object] = {
        "model": model or settings.llm_model,
        "messages": messages,
        **(extra or {}),
    }
    if temperature is not None or "temperature" not in payload:
        payload["temperature"] = settings.llm_temperature if temperature is None else temperature
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    start = time.perf_counter()
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = httpx.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key or settings.llm_api_key}"},
                timeout=settings.llm_timeout_s,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request to {base_url} failed: {exc}") from exc
        if response.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES:
            delay = _retry_delay(response, attempt)
            logger.warning("LLM %s returned %d, retrying in %.0f s", payload["model"], response.status_code, delay)
            time.sleep(delay)
            continue
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request to {base_url} failed: {exc}; {response.text[:300]}") from exc
        break
    body = response.json()
    usage = body.get("usage", {})
    logger.info(
        "LLM %s: %.0f ms, %s prompt + %s completion tokens",
        payload["model"], (time.perf_counter() - start) * 1000,
        usage.get("prompt_tokens", "?"), usage.get("completion_tokens", "?"),
    )
    return body["choices"][0]["message"]["content"] or ""


def parse_json(text: str) -> object:
    """Parse JSON from a model reply, tolerating Markdown code fences and surrounding prose."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def chat_json(
    messages: list[Message],
    schema: type[T],
    model: str | None = None,
    temperature: float | None = None,
    **provider: object,
) -> T:
    """Chat and validate the reply against ``schema``, retrying once with the validation error.

    ``provider`` (``base_url``, ``api_key``, ``extra``) is passed through to ``chat``.
    """
    raw = chat(messages, model, temperature, json_mode=True, **provider)
    try:
        return schema.model_validate(parse_json(raw))
    except (json.JSONDecodeError, ValidationError) as first_error:
        logger.warning("Invalid JSON from LLM, retrying once: %s", str(first_error)[:200])
        retry_messages = [
            *messages,
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "Your previous answer was not valid. Error:\n"
                    f"{first_error}\n"
                    "Reply again with only a JSON object that matches the requested format."
                ),
            },
        ]
        raw = chat(retry_messages, model, temperature, json_mode=True, **provider)
        try:
            return schema.model_validate(parse_json(raw))
        except (json.JSONDecodeError, ValidationError) as second_error:
            raise LLMOutputError(f"LLM output failed validation twice: {second_error}", raw) from second_error


def image_message(prompt: str, image_path: Path) -> Message:
    """Build a user message carrying ``prompt`` and an inline base64 image."""
    mime = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
        ],
    }


def vision(prompt: str, image_path: Path, system: str | None = None, model: str | None = None) -> str:
    """Ask the vision-language model about one image."""
    messages: list[Message] = [{"role": "system", "content": system}] if system else []
    messages.append(image_message(prompt, image_path))
    return chat(messages, model or get_settings().vlm_model)
