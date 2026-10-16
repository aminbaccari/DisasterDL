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


def chat(
    messages: list[Message],
    model: str | None = None,
    temperature: float | None = None,
    json_mode: bool = False,
) -> str:
    """Send a chat completion request and return the assistant's text."""
    settings = get_settings()
    payload: dict[str, object] = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature if temperature is None else temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    start = time.perf_counter()
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=settings.llm_timeout_s,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM request to {settings.llm_base_url} failed: {exc}") from exc
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
) -> T:
    """Chat and validate the reply against ``schema``, retrying once with the validation error."""
    raw = chat(messages, model, temperature, json_mode=True)
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
        raw = chat(retry_messages, model, temperature, json_mode=True)
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
