"""Versioned prompt library loader.

Prompts are never hard-coded: each lives in ``prompts/<name>/v<N>.yaml`` with the fields

    name, version
    role        what the prompt does in the system
    technique   list of prompting techniques used (role prompting, few-shot, structured output...)
    changelog   what changed compared to the previous version, and which observed failure it fixes
    system      system message
    user        user message template (Python ``str.format`` placeholders)
    few_shot    optional list of {input, output} examples, sent as user/assistant turns

The latest version is used by default; ``PROMPT_<NAME>_VERSION`` (e.g. ``PROMPT_RAG_QUERY_REWRITE_VERSION=1``)
pins an older one, which is how before/after comparisons are run.
"""

import os
import re
import string
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.config import PROJECT_ROOT

PROMPTS_DIR = PROJECT_ROOT / "prompts"
_VERSION_FILE = re.compile(r"^v(\d+)\.ya?ml$")


@dataclass
class Prompt:
    """One version of a prompt."""

    name: str
    version: int
    role: str
    technique: list[str]
    changelog: str
    system: str
    user: str
    few_shot: list[dict[str, str]] = field(default_factory=list)


def available_versions(name: str, prompts_dir: Path = PROMPTS_DIR) -> list[int]:
    """Sorted versions available for prompt ``name``."""
    folder = prompts_dir / name
    if not folder.is_dir():
        return []
    return sorted(int(m.group(1)) for f in folder.iterdir() if (m := _VERSION_FILE.match(f.name)))


def load_prompt(name: str, version: int | None = None, prompts_dir: Path = PROMPTS_DIR) -> Prompt:
    """Load ``prompts/<name>/v<version>.yaml`` (latest, or the env-pinned version, by default)."""
    versions = available_versions(name, prompts_dir)
    if not versions:
        raise FileNotFoundError(f"No prompt versions found in {prompts_dir / name}")
    pinned = os.environ.get(f"PROMPT_{name.upper()}_VERSION")
    version = version or (int(pinned) if pinned else versions[-1])
    if version not in versions:
        raise FileNotFoundError(f"Prompt {name} has no version {version} (available: {versions})")
    path = next(p for p in (prompts_dir / name).iterdir() if _VERSION_FILE.match(p.name)
                and int(_VERSION_FILE.match(p.name).group(1)) == version)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Prompt(
        name=data.get("name", name),
        version=int(data.get("version", version)),
        role=data["role"],
        technique=list(data.get("technique", [])),
        changelog=data.get("changelog", ""),
        system=data["system"],
        user=data["user"],
        few_shot=list(data.get("few_shot") or []),
    )


def build_messages(prompt: Prompt, **variables: object) -> list[dict[str, str]]:
    """Render the prompt into chat messages, failing clearly on a missing template variable."""
    required = {f for _, f, _, _ in string.Formatter().parse(prompt.user) if f}
    missing = required - variables.keys()
    if missing:
        raise KeyError(f"Prompt {prompt.name} v{prompt.version} is missing variables: {sorted(missing)}")
    messages = [{"role": "system", "content": prompt.system}]
    for example in prompt.few_shot:
        messages.append({"role": "user", "content": example["input"]})
        messages.append({"role": "assistant", "content": example["output"]})
    messages.append({"role": "user", "content": prompt.user.format(**variables)})
    return messages
