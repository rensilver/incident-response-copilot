import pytest

from incident_copilot.config.settings import Settings
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.llm.fallback_provider import FallbackProvider
from incident_copilot.llm.groq_provider import GroqProvider
from incident_copilot.llm.ollama_provider import OllamaProvider
from incident_copilot.models.enums import LLMProviderName
from incident_copilot.utils.exceptions import ConfigurationError


def test_fake_provider_is_rejected_by_the_factory() -> None:
    """The fake is test-only; it must never be reachable from configuration."""
    settings = Settings(_env_file=None, llm_provider=LLMProviderName.FAKE)
    with pytest.raises(ConfigurationError, match="test-only"):
        build_llm_provider(settings)


def test_default_factory_builds_groq_with_ollama_fallback() -> None:
    provider = build_llm_provider(Settings(_env_file=None))
    assert isinstance(provider, FallbackProvider)
    assert isinstance(provider.primary, GroqProvider)
    assert isinstance(provider.fallback, OllamaProvider)


def test_fallback_can_be_disabled() -> None:
    provider = build_llm_provider(Settings(_env_file=None, llm_fallback_provider="none"))
    assert isinstance(provider, GroqProvider)


def test_manual_ollama_remains_available() -> None:
    provider = build_llm_provider(Settings(_env_file=None, llm_provider="ollama"))
    assert isinstance(provider, OllamaProvider)
