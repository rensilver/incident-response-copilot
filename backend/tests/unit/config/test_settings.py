import pytest

from incident_copilot.config.settings import Settings
from incident_copilot.models.enums import LLMProviderName


def test_defaults_select_groq_with_ollama_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_provider is LLMProviderName.GROQ
    assert settings.llm_fallback_provider == "ollama"
    assert settings.groq_model == "openai/gpt-oss-20b"
    assert settings.ollama_model == "qwen3:4b"
    assert settings.max_tool_rounds == 2


def test_ollama_does_not_require_cloud_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert Settings(_env_file=None, llm_provider="ollama").llm_provider is LLMProviderName.OLLAMA


@pytest.mark.parametrize("fallback", ["groq", "fake", "invalid"])
def test_invalid_fallback_is_rejected(fallback: str) -> None:
    with pytest.raises(ValueError, match="llm_fallback_provider"):
        Settings(_env_file=None, llm_fallback_provider=fallback)


def test_env_overrides_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    settings = Settings(_env_file=None)
    assert settings.llm_provider is LLMProviderName.GROQ
    assert settings.groq_api_key == "test-key"


def test_groq_without_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        Settings(_env_file=None)


def test_langsmith_tracing_without_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LANGSMITH_API_KEY"):
        Settings(_env_file=None, langsmith_tracing=True)
