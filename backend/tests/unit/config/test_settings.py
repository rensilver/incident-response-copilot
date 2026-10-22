import pytest
from pydantic import ValidationError

from incident_copilot.config.settings import Settings
from incident_copilot.models.enums import LLMProviderName


def test_defaults_select_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_provider is LLMProviderName.OPENAI
    assert settings.max_tool_rounds == 2


@pytest.mark.parametrize("provider", ["groq", "ollama", "fallback", "invalid"])
def test_retired_provider_cannot_be_selected_from_environment(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", provider)
    # Valid synthetic credentials ensure rejection is for the selection itself.
    monkeypatch.setenv("GROQ_API_KEY", "test-retired-key")
    with pytest.raises(ValidationError, match="llm_provider"):
        Settings(_env_file=None)


def test_langsmith_tracing_without_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LANGSMITH_API_KEY"):
        Settings(_env_file=None, langsmith_tracing=True)
