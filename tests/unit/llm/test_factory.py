import pytest

from incident_copilot.config.settings import Settings
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.models.enums import LLMProviderName
from incident_copilot.utils.exceptions import ConfigurationError


def test_fake_provider_is_rejected_by_the_factory() -> None:
    """The fake is test-only; it must never be reachable from configuration."""
    settings = Settings(_env_file=None, llm_provider=LLMProviderName.FAKE)
    with pytest.raises(ConfigurationError, match="test-only"):
        build_llm_provider(settings)
