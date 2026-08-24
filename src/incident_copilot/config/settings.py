"""Environment-driven application settings."""

from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from incident_copilot.models.enums import LLMProviderName


class Settings(BaseSettings):
    """Application settings, populated from environment variables and ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: LLMProviderName = LLMProviderName.OLLAMA
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    google_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"

    prometheus_url: str = "http://localhost:9090"
    grafana_url: str = "http://localhost:3000"
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_log_index: str = "app-logs"

    app_env: str = "dev"
    log_level: str = "INFO"
    langsmith_tracing: bool = False

    max_tool_rounds: int = Field(default=2, ge=1, le=5)
    max_supervisor_iterations: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def _require_key_for_gemini(self) -> Self:
        """Fail fast when Gemini is selected without an API key."""
        if self.llm_provider is LLMProviderName.GEMINI and not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini")
        return self


def get_settings() -> Settings:
    """Build settings from the environment."""
    return Settings()
