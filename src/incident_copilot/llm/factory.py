"""Construction of the configured LLM provider."""

from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import LLMProvider
from incident_copilot.models.enums import LLMProviderName
from incident_copilot.utils.exceptions import ConfigurationError


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Build the provider named in settings.

    This is the only place a provider name maps to a class.

    Args:
        settings: Application settings.

    Returns:
        The configured provider.

    Raises:
        ConfigurationError: If the named provider cannot be built.
    """
    match settings.llm_provider:
        case LLMProviderName.OLLAMA:
            from incident_copilot.llm.ollama_provider import OllamaProvider

            return OllamaProvider.from_settings(settings)
        case LLMProviderName.GROQ:
            from incident_copilot.llm.fallback_provider import FallbackProvider
            from incident_copilot.llm.groq_provider import GroqProvider
            from incident_copilot.llm.ollama_provider import OllamaProvider

            primary = GroqProvider.from_settings(settings)
            if settings.llm_fallback_provider == "ollama":
                return FallbackProvider(primary, OllamaProvider.from_settings(settings))
            return primary
        case LLMProviderName.FAKE:
            raise ConfigurationError(
                "the fake provider is test-only and cannot be selected by configuration"
            )
