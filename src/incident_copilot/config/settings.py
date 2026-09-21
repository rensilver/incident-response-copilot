"""Environment-driven application settings."""

from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from incident_copilot.models.enums import LLMProviderName


class Settings(BaseSettings):
    """Application settings, populated from environment variables and ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: LLMProviderName = LLMProviderName.GROQ
    llm_fallback_provider: Literal["ollama", "none"] = "ollama"
    groq_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout_seconds: float = Field(default=60.0, gt=0, le=180)
    ollama_num_ctx: int = Field(default=4096, ge=1024, le=32768)
    ollama_min_available_memory_mb: int = Field(default=4096, ge=0)
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"

    prometheus_url: str = "http://localhost:9090"
    grafana_url: str = "http://localhost:3000"
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_log_index: str = "app-logs"

    app_env: str = "dev"
    log_level: str = "INFO"
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "incident-copilot"

    max_tool_rounds: int = Field(default=2, ge=1, le=5)
    max_supervisor_iterations: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def _require_key_for_groq(self) -> Self:
        """Fail fast when Groq is selected without an API key."""
        if self.llm_provider is LLMProviderName.GROQ and not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        return self

    @model_validator(mode="after")
    def _require_key_for_langsmith(self) -> Self:
        """Fail fast when tracing is enabled without an API key."""
        if self.langsmith_tracing and not self.langsmith_api_key:
            raise ValueError("LANGSMITH_API_KEY is required when LANGSMITH_TRACING=true")
        return self


def get_settings() -> Settings:
    """Build settings from the environment."""
    return Settings()
