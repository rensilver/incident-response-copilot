import os

import pytest

from incident_copilot.config.settings import Settings
from incident_copilot.utils.tracing import configure_tracing


def _clear_langchain_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"):
        monkeypatch.delenv(key, raising=False)


def test_disabled_tracing_leaves_environment_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_langchain_env(monkeypatch)
    settings = Settings(_env_file=None, langsmith_tracing=False)

    configure_tracing(settings)

    assert "LANGCHAIN_TRACING_V2" not in os.environ


def test_enabled_tracing_sets_langchain_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_langchain_env(monkeypatch)
    settings = Settings(
        _env_file=None,
        langsmith_tracing=True,
        langsmith_api_key="test-key",
        langsmith_project="my-project",
    )

    configure_tracing(settings)

    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_API_KEY"] == "test-key"
    assert os.environ["LANGCHAIN_PROJECT"] == "my-project"
