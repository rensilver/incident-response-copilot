import os
from collections.abc import Iterator

import pytest
from langsmith.utils import get_env_var, get_tracer_project, tracing_is_enabled

from incident_copilot.config.settings import Settings
from incident_copilot.utils.tracing import configure_tracing


@pytest.fixture(autouse=True)
def clear_sdk_cache() -> Iterator[None]:
    yield
    for lookup in (get_env_var, get_tracer_project):
        clear_cache = getattr(lookup, "cache_clear", None)
        if clear_cache is not None:
            clear_cache()


def _clear_langchain_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for namespace in ("LANGSMITH", "LANGCHAIN"):
        for suffix in ("TRACING", "TRACING_V2", "API_KEY", "PROJECT"):
            monkeypatch.delenv(f"{namespace}_{suffix}", raising=False)


def test_disabled_tracing_disables_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_langchain_env(monkeypatch)
    settings = Settings(_env_file=None, langsmith_tracing=False)

    configure_tracing(settings)

    assert tracing_is_enabled() is False


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
    assert tracing_is_enabled() is True


@pytest.mark.parametrize(
    "flag",
    ["LANGSMITH_TRACING", "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2"],
)
def test_disabled_tracing_overrides_inherited_flags(
    monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    _clear_langchain_env(monkeypatch)
    monkeypatch.setenv(flag, "true")

    configure_tracing(Settings(_env_file=None, langsmith_tracing=False))

    assert tracing_is_enabled() is False


def test_disabling_after_enabled_build_stops_sdk_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_langchain_env(monkeypatch)
    configure_tracing(
        Settings(_env_file=None, langsmith_tracing=True, langsmith_api_key="test-key")
    )
    assert tracing_is_enabled() is True

    configure_tracing(Settings(_env_file=None, langsmith_tracing=False))

    assert tracing_is_enabled() is False


def test_enabled_tracing_overrides_inherited_disabled_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_langchain_env(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "false")
    configure_tracing(
        Settings(_env_file=None, langsmith_tracing=True, langsmith_api_key="test-key")
    )

    assert tracing_is_enabled() is True
