"""Versioned YAML prompt loader.

Prompts live at  prompts/<name>/v<N>.yaml  relative to the project root.
Each YAML file is a plain dict whose keys the calling agent accesses directly.
"""

import logging
from functools import lru_cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str, version: int = 1) -> dict:
    """Return the parsed YAML dict for prompts/<name>/v<version>.yaml."""
    path = _PROMPTS_DIR / name / f"v{version}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    logger.debug("Loading prompt %s v%d from %s", name, version, path)
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
