"""OpenAI configuration boundaries use synthetic credentials and no inference."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from incident_copilot.config.settings import Settings


def test_defaults_select_openai_without_fallback() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_provider.value == "openai"
    assert settings.openai_model == "gpt-6-luna"
    assert settings.llm_fallback_provider == "none"


def test_default_operation_limits() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_operation_timeout_seconds == 60.0
    assert settings.llm_max_output_tokens == 4096
    assert settings.llm_max_structured_attempts == 3


@pytest.mark.parametrize(
    "name,value",
    [
        ("llm_operation_timeout_seconds", 0),
        ("llm_operation_timeout_seconds", 181),
        ("llm_operation_timeout_seconds", float("inf")),
        ("llm_operation_timeout_seconds", float("nan")),
        ("llm_max_output_tokens", 0),
        ("llm_max_output_tokens", 16385),
        ("llm_max_structured_attempts", 0),
        ("llm_max_structured_attempts", 6),
    ],
)
def test_rejects_unbounded_operation_settings(name: str, value: float) -> None:
    # The test deliberately supplies heterogeneous invalid settings at runtime.
    overrides: dict[str, Any] = {name: value}
    with pytest.raises(ValidationError, match=name):
        Settings(_env_file=None, **overrides)


def test_operation_limits_load_from_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_OPERATION_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "2048")
    monkeypatch.setenv("LLM_MAX_STRUCTURED_ATTEMPTS", "2")
    settings = Settings(_env_file=None)
    assert settings.llm_operation_timeout_seconds == 15.0
    assert settings.llm_max_output_tokens == 2048
    assert settings.llm_max_structured_attempts == 2


@pytest.mark.parametrize("key", [None, "", " \t\n"])
def test_openai_requires_nonblank_key(key: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(_env_file=None, openai_api_key=key)


@pytest.mark.parametrize("model", ["", "gpt-other", "gpt-6-luna "])
def test_openai_rejects_model_substitution(model: str) -> None:
    with pytest.raises(ValidationError, match="openai_model"):
        Settings(_env_file=None, openai_model=model)


def test_dotenv_openai_values_and_process_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = tmp_path / "selected.env"
    selected.write_text("OPENAI_API_KEY=synthetic-file-key\nOPENAI_MODEL=gpt-6-luna\n")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(_env_file=selected)
    assert isinstance(settings.openai_api_key, SecretStr)
    assert settings.openai_api_key.get_secret_value() == "synthetic-file-key"
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-process-key")
    process_settings = Settings(_env_file=selected)
    assert process_settings.openai_api_key is not None
    assert process_settings.openai_api_key.get_secret_value() == "synthetic-process-key"
    monkeypatch.setenv("OPENAI_MODEL", "gpt-other")
    with pytest.raises(ValidationError, match="openai_model"):
        Settings(_env_file=selected)


def test_openai_rejects_automatic_fallback() -> None:
    with pytest.raises(ValidationError, match="fallback"):
        Settings(_env_file=None, llm_fallback_provider="ollama")


def test_openai_key_is_redacted_from_settings_and_validation_errors() -> None:
    sentinel = "synthetic-config-secret"
    settings = Settings(_env_file=None, openai_api_key=sentinel)
    surfaces = [repr(settings), str(settings), settings.model_dump_json()]
    for invalid in (
        {"max_tool_rounds": 0},
        {"openai_model": sentinel},
        {"openai_api_key": [sentinel]},
    ):
        with pytest.raises(ValidationError) as error:
            # Raw, deliberately invalid settings inputs have heterogeneous values.
            overrides: dict[str, Any] = {"openai_api_key": sentinel, **invalid}
            Settings(_env_file=None, **overrides)
        surfaces.extend((str(error.value), repr(error.value)))
    assert all(sentinel not in surface for surface in surfaces)
    assert json.loads(settings.model_dump_json())["openai_api_key"] == "**********"


def test_legacy_ollama_selection_does_not_require_openai_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert Settings(_env_file=None, llm_provider="ollama").llm_provider.value == "ollama"


def test_safe_example_requires_owner_key_and_runs_after_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    example = Path(__file__).parents[4] / ".env.example"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(_env_file=example)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-owner-key")
    settings = Settings(_env_file=example)
    assert settings.llm_provider.value == "openai"
    assert settings.llm_fallback_provider == "none"
    assert settings.openai_model == "gpt-6-luna"
