"""Central configuration for DisasterAI, read from environment variables and .env.

Every tunable value (models, paths, RAG parameters) lives here so that experiments
can be reproduced by changing configuration only, never code.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings. Relative paths are resolved against the project root."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # an empty value in .env falls back to the default
        extra="ignore",
    )

    # LLM / VLM provider (any OpenAI-compatible endpoint; default: local Ollama)
    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"  # Ollama ignores the key; hosted providers need a real one
    llm_model: str = "gemma3:4b"
    vlm_model: str = "gemma3:4b"
    llm_temperature: float = 0.1
    llm_timeout_s: float = 180.0

    # Embeddings and vector store
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_batch_size: int = 32
    chroma_path: Path = Path("chroma_db")

    # Corpus locations
    sources_csv: Path = Path("data/sources.csv")
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")

    # Chunking (token counts use the embedding model's tokenizer)
    chunk_size: int = 400
    chunk_overlap: int = 60
    min_chunk_tokens: int = 80

    # Retrieval
    top_k: int = 5

    def resolve(self, path: Path) -> Path:
        """Return ``path`` as an absolute path, relative paths being taken from the project root."""
        return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
