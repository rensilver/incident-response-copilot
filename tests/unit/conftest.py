"""Keep offline tests independent of local credentials and tracing configuration."""

import pytest

from incident_copilot.config.settings import Settings


def _set_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)


def pytest_configure(config: pytest.Config) -> None:
    # Runs before collection imports main.py and builds its module-level app.
    patch = pytest.MonkeyPatch()
    patch.setitem(Settings.model_config, "env_file", None)
    _set_test_environment(patch)
    config.add_cleanup(patch.undo)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_test_environment(monkeypatch)
