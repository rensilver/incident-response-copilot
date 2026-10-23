"""Environment-driven application settings."""

import os
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from incident_copilot.models.enums import LLMProviderName

DEFAULT_INVESTIGATION_TIMEOUT_SECONDS = 240.0


def _default_env_file() -> Path | None:
    """Select dotenv at import time without searching the caller's directory."""
    configured = os.environ.get("INCIDENT_COPILOT_ENV_FILE")
    if configured is not None:
        if not configured:
            return None
        path = Path(configured)
        if not path.is_absolute():
            raise ValueError("INCIDENT_COPILOT_ENV_FILE must be an absolute path")
        return path

    package = Path(__file__).resolve().parent.parent
    backend = package.parent.parent
    # Only the source checkout has a repository dotenv. Wheels and containers
    # receive process variables or an explicitly selected external file.
    if (
        package.parent.name == "src"
        and backend.name == "backend"
        and (backend / "pyproject.toml").is_file()
    ):
        return backend.parent / ".env"
    return None


class Settings(BaseSettings):
    """Application settings; process variables override the selected dotenv file."""

    model_config = SettingsConfigDict(
        env_file=_default_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    llm_provider: LLMProviderName = LLMProviderName.OPENAI
    openai_api_key: SecretStr | None = None
    openai_model: Literal["gpt-6-luna"] = "gpt-6-luna"
    llm_operation_timeout_seconds: float = Field(default=60.0, gt=0, le=180, allow_inf_nan=False)
    llm_max_output_tokens: int = Field(default=4096, ge=16, le=16384)
    llm_max_structured_attempts: int = Field(default=3, ge=1, le=5)
    investigation_timeout_seconds: float = Field(
        default=DEFAULT_INVESTIGATION_TIMEOUT_SECONDS,
        gt=0,
        le=DEFAULT_INVESTIGATION_TIMEOUT_SECONDS,
        allow_inf_nan=False,
    )

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
    def _validate_openai_configuration(self) -> Self:
        """Require the selected OpenAI credential."""
        if self.llm_provider is LLMProviderName.OPENAI and (
            self.openai_api_key is None or not self.openai_api_key.get_secret_value().strip()
        ):
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return self

    @model_validator(mode="after")
    def _require_key_for_langsmith(self) -> Self:
        """Fail fast when tracing is enabled without an API key."""
        if self.langsmith_tracing and not self.langsmith_api_key:
            raise ValueError("LANGSMITH_API_KEY is required when LANGSMITH_TRACING=true")
        return self


def get_settings() -> Settings:
    """Build settings using process variables and the startup dotenv selection."""
    return Settings()
