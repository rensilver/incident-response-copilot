import pytest

from incident_copilot.config.settings import Settings
from incident_copilot.models.enums import LLMProviderName


def test_defaults_select_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_provider is LLMProviderName.OLLAMA
    assert settings.ollama_model == "qwen3:4b"
    assert settings.max_tool_rounds == 2


def test_env_overrides_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    settings = Settings(_env_file=None)
    assert settings.llm_provider is LLMProviderName.GEMINI
    assert settings.google_api_key == "test-key"


def test_gemini_without_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        Settings(_env_file=None)
