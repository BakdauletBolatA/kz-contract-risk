"""Настройки из окружения. Все необязательны: без них система работает
офлайн — правила + ML, корпус в памяти, LLM выключен."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KZCR_", env_file=".env", extra="ignore")

    data_dir: Path = ROOT / "data"
    models_dir: Path = ROOT / "models"
    cache_dir: Path = ROOT / ".cache"

    database_url: str | None = None
    embedder: str = "hashing"

    detector: str = "hybrid"
    llm_model: str = "claude-opus-5"
    llm_backend: str = "langchain"
    llm_effort: str = "medium"
    llm_workers: int = 4
    llm_enabled: bool = True
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    ollama_host: str = "http://127.0.0.1:11434"
    extract_model: str = "ollama:qwen2.5:7b"
    extract_concurrency: int = 4

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    grok_api_key: str | None = Field(default=None, validation_alias="GROK_API_KEY")
    grok_base_url: str = Field(default="https://api.x.ai/v1", validation_alias="GROK_BASE_URL")
    deepseek_api_key: str | None = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL"
    )

    max_upload_mb: int = 10
    ocr_enabled: bool = False
    api_url: str | None = None

    @property
    def llm_available(self) -> bool:
        return self.llm_enabled and bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
