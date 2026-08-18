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
        case LLMProviderName.GEMINI:
            from incident_copilot.llm.gemini_provider import GeminiProvider

            return GeminiProvider.from_settings(settings)
        case LLMProviderName.FAKE:
            raise ConfigurationError(
                "the fake provider is test-only and cannot be selected by configuration"
            )
