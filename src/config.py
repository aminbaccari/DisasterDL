"""Application configuration loaded from environment / .env file."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="", alias="LLM_MODEL")

    # Which VLM backend the Vision Agent uses: "groq" (cloud, default) or "ollama" (local fallback).
    vlm_provider: str = Field(default="groq", alias="VLM_PROVIDER")

    # Vision-language model served by Ollama (must be running locally)
    vlm_model: str = Field(default="llava-phi3", alias="VLM_MODEL")
    vlm_revision: str = Field(default="", alias="VLM_REVISION")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")

    # Groq cloud VLM — OpenAI-compatible Chat Completions API.
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="qwen/qwen3.8-27b", alias="GROQ_MODEL")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")

    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL"
    )
    chroma_path: str = Field(default="./data/chroma", alias="CHROMA_PATH")

    # DINOv2 visual encoder — off by default; set DINOV2_ENABLED=true to activate.
    dinov2_enabled: bool = Field(default=False, alias="DINOV2_ENABLED")
    # dinov2-small fits alongside llava-phi3 on a 6 GB GPU (~44 MB fp16).
    dinov2_model: str = Field(default="facebook/dinov2-small", alias="DINOV2_MODEL")
    # "shadow" — compute similarity, attach to output, do NOT change reliability.
    # "active" — additionally add a reliability note when mean similarity is very low.
    dinov2_integration_mode: str = Field(default="shadow", alias="DINOV2_INTEGRATION_MODE")
    # Path to a pre-built .npz embedding store (built with build_embedding_store.py).
    # Leave empty to skip nearest-neighbor lookup.
    dinov2_store_path: str = Field(default="", alias="DINOV2_STORE_PATH")

    model_config = {"env_file": ".env", "populate_by_name": True}


settings = Settings()
