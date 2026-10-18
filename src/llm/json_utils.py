"""Lenient JSON extraction for VLM responses.

Cloud VLMs in JSON mode return clean JSON, but local models (Ollama) sometimes
wrap it in markdown code fences or add stray text. This strips both.
"""

import json
import re


def parse_json_lenient(text: str) -> dict:
    """Parse a JSON object out of `text`, tolerating markdown fences and stray text.

    Raises json.JSONDecodeError if no valid JSON object can be found.
    """
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
