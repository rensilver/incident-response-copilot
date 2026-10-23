"""Entrypoints must release acquired resources on every exit path."""

import asyncio
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from openai import AsyncOpenAI, OpenAI
from pydantic import SecretStr

from incident_copilot.config.settings import Settings
from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.llm.base import LLMProvider
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.llm.openai_provider import OpenAIProvider
from incident_copilot.main import create_app
from incident_copilot.models.report import IncidentReport


def test_import_and_openapi_need_neither_settings_nor_clients() -> None:
    """Import and schema inspection must never acquire process-lifetime resources."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from unittest.mock import patch
with (
    patch('incident_copilot.config.settings.get_settings', side_effect=AssertionError('settings')),
    patch('incident_copilot.composition.build_collaborators',
          side_effect=AssertionError('clients')),
):
    from incident_copilot.main import app, create_app
    assert set(app.openapi()['paths']) == {'/health', '/api/v1/investigations'}
    assert create_app().openapi() == app.openapi()
""",
        ],
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "INCIDENT_COPILOT_ENV_FILE": "",
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def resources(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], FakeLLMProvider]:
    """Track real connector closure and a test-only provider through composition."""
    events: list[str] = []

    class Provider(FakeLLMProvider):
        async def aclose(self) -> None:
            events.append("provider")

    provider = Provider(["unused"])

    async def build_provider(_: Settings) -> FakeLLMProvider:
        return provider

    monkeypatch.setattr("incident_copilot.composition.build_llm_provider", build_provider)
    for cls, name in (
        (PrometheusConnector, "metrics"),
        (ElasticsearchConnector, "logs"),
    ):
        close = cls.aclose

        async def record(self: Any, _close: Callable[..., Any] = close, _name: str = name) -> None:
            await _close(self)
            events.append(_name)

        monkeypatch.setattr(cls, "aclose", record)
    return events, provider


async def test_lifespan_closes_provider_and_connectors_on_normal_exit(
    resources: tuple[list[str], FakeLLMProvider],
) -> None:
    events, _ = resources
    app = create_app(Settings(_env_file=None))
    async with app.router.lifespan_context(app):
        assert events == []
    assert events == ["provider", "logs", "metrics"]


@pytest.mark.parametrize("error", [RuntimeError("body failed"), asyncio.CancelledError()])
async def test_lifespan_closes_resources_when_body_raises(
    resources: tuple[list[str], FakeLLMProvider], error: BaseException
) -> None:
    events, _ = resources
    app = create_app(Settings(_env_file=None))
    with pytest.raises(type(error)) as caught:
        async with app.router.lifespan_context(app):
            raise error
    assert caught.value is error
    assert events == ["provider", "logs", "metrics"]


@pytest.mark.parametrize("failed", ["provider", "logs", "metrics"])
async def test_one_close_failure_does_not_skip_other_resources(
    resources: tuple[list[str], FakeLLMProvider], monkeypatch: pytest.MonkeyPatch, failed: str
) -> None:
    events, provider = resources
    error = RuntimeError("close failed")
    targets: dict[
        str, type[LLMProvider] | type[ElasticsearchConnector] | type[PrometheusConnector]
    ] = {
        "provider": type(provider),
        "logs": ElasticsearchConnector,
        "metrics": PrometheusConnector,
    }
    target = targets[failed]
    original = target.aclose

    async def fail(self: Any) -> None:
        await original(self)
        raise error

    monkeypatch.setattr(target, "aclose", fail)
    with pytest.raises(RuntimeError) as caught:
        app = create_app(Settings(_env_file=None))
        async with app.router.lifespan_context(app):
            pass
    assert caught.value is error
    assert events == ["provider", "logs", "metrics"]


@pytest.mark.parametrize(
    ("failed", "closed"),
    [
        ("logs", ["metrics"]),
        ("provider", ["logs", "metrics"]),
        ("graph", ["provider", "logs", "metrics"]),
        ("service", ["provider", "logs", "metrics"]),
    ],
)
async def test_partial_startup_releases_previously_acquired_resources(
    resources: tuple[list[str], FakeLLMProvider],
    monkeypatch: pytest.MonkeyPatch,
    failed: str,
    closed: list[str],
) -> None:
    events, _ = resources
    error = RuntimeError("construction failed")

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise error

    targets = {
        "logs": "incident_copilot.composition.ElasticsearchConnector.from_settings",
        "provider": "incident_copilot.composition.build_llm_provider",
        "graph": "incident_copilot.composition.build_graph",
        "service": "incident_copilot.main.IncidentService",
    }
    monkeypatch.setattr(targets[failed], fail)
    with pytest.raises(RuntimeError) as caught:
        app = create_app(Settings(_env_file=None))
        async with app.router.lifespan_context(app):
            pytest.fail("Startup failure must prevent serving")
    assert caught.value is error
    assert events == closed


@pytest.mark.parametrize("failed", ["async_client", "chat", "provider"])
async def test_openai_partial_construction_closes_owned_transports(
    monkeypatch: pytest.MonkeyPatch, failed: str
) -> None:
    sync_clients: list[OpenAI] = []
    async_clients: list[AsyncOpenAI] = []
    error = RuntimeError("SDK construction failed")

    def sync_client(**kwargs: Any) -> OpenAI:
        client = OpenAI(**kwargs)
        sync_clients.append(client)
        return client

    def async_client(**kwargs: Any) -> AsyncOpenAI:
        if failed == "async_client":
            raise error
        client = AsyncOpenAI(**kwargs)
        async_clients.append(client)
        return client

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise error

    monkeypatch.setattr("incident_copilot.llm.openai_provider.OpenAI", sync_client)
    monkeypatch.setattr("incident_copilot.llm.openai_provider.AsyncOpenAI", async_client)
    if failed == "chat":
        monkeypatch.setattr("incident_copilot.llm.openai_provider._SanitizedChatOpenAI", fail)
    elif failed == "provider":
        monkeypatch.setattr(OpenAIProvider, "__init__", fail)
    with pytest.raises(RuntimeError) as caught:
        await OpenAIProvider.from_api_key(SecretStr("offline-key"))
    assert caught.value is error
    assert len(sync_clients) == 1
    assert all(client.is_closed() for client in sync_clients)
    assert all(client.is_closed() for client in async_clients)


async def test_resource_free_provider_cleanup_is_safe() -> None:
    provider = FakeLLMProvider(["unused"])
    await provider.aclose()
    await provider.aclose()


async def test_startup_cancellation_releases_acquired_connectors(
    resources: tuple[list[str], FakeLLMProvider], monkeypatch: pytest.MonkeyPatch
) -> None:
    events, _ = resources
    started = asyncio.Event()

    async def blocked_provider(_: Settings) -> FakeLLMProvider:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("Provider construction should have been cancelled")

    monkeypatch.setattr("incident_copilot.composition.build_llm_provider", blocked_provider)
    app = create_app(Settings(_env_file=None))

    async def startup() -> None:
        async with app.router.lifespan_context(app):
            pytest.fail("Cancelled startup must never serve requests")

    task = asyncio.create_task(startup())
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert events == ["logs", "metrics"]
    assert not hasattr(app.state, "service")


async def test_restarting_lifespan_replaces_resources_without_duplicating_routes(
    resources: tuple[list[str], FakeLLMProvider],
) -> None:
    events, _ = resources
    app = create_app(Settings(_env_file=None))
    previous: object = None
    route_count = len(app.routes)
    for _ in range(2):
        async with app.router.lifespan_context(app):
            assert app.state.service is not previous
            previous = app.state.service
            assert len(app.routes) == route_count
        assert not hasattr(app.state, "service")
        assert not hasattr(app.state, "health_checks")
        assert not hasattr(app.state, "prometheus_connector")
        assert not hasattr(app.state, "elasticsearch_connector")
    assert events == ["provider", "logs", "metrics"] * 2


@respx.mock
async def test_apps_resolve_their_own_service_and_health_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Provider(FakeLLMProvider):
        def __init__(self, label: str) -> None:
            super().__init__(["unused"])
            self.label = label

        async def _probe_health(self) -> bool:
            return self.label == "first"

    async def build_provider(settings: Settings) -> Provider:
        return Provider(settings.langsmith_project)

    class Graph:
        def __init__(self, provider: Provider) -> None:
            self.provider = provider

        async def ainvoke(self, state: Any, /) -> dict[str, IncidentReport]:
            return {
                "report": IncidentReport(
                    summary=self.provider.label, likely_causes=(), next_steps=(), confidence=0
                )
            }

    monkeypatch.setattr("incident_copilot.composition.build_llm_provider", build_provider)
    monkeypatch.setattr("incident_copilot.composition.build_graph", lambda p, *args: Graph(p))
    first = create_app(Settings(_env_file=None, langsmith_project="first"))
    second = create_app(Settings(_env_file=None, langsmith_project="second"))
    respx.get("http://localhost:9090/-/ready").respond(200)
    respx.get("http://localhost:9200/_cluster/health").respond(200)
    async with first.router.lifespan_context(first), second.router.lifespan_context(second):
        for app, summary, llm in ((first, "first", True), (second, "second", False)):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                report = await client.post("/api/v1/investigations", json={"query": "incident"})
                health = await client.get("/health")
            assert report.status_code == 200
            assert report.json()["summary"] == summary
            assert health.json()["dependencies"]["llm"] is llm


async def test_api_shutdown_reaches_owned_sdk_transports(monkeypatch: pytest.MonkeyPatch) -> None:
    from incident_copilot.llm.factory import build_llm_provider

    providers: list[OpenAIProvider] = []

    async def capture(settings: Settings) -> OpenAIProvider:
        provider = await build_llm_provider(settings)
        assert isinstance(provider, OpenAIProvider)
        providers.append(provider)
        return provider

    monkeypatch.setattr("incident_copilot.composition.build_llm_provider", capture)
    app = create_app(Settings(_env_file=None))
    assert providers == []
    async with app.router.lifespan_context(app):
        assert len(providers) == 1
        clients = providers[0]._owned_clients
        assert clients is not None
        assert all(not client.is_closed() for client in clients)
        metrics = app.state.prometheus_connector
        assert not metrics._client.is_closed
    assert all(client.is_closed() for client in clients)
    assert metrics._client.is_closed


@pytest.mark.parametrize("error", [None, RuntimeError("graph failed"), asyncio.CancelledError()])
async def test_evaluation_uses_the_same_managed_resource_lifetime(
    resources: tuple[list[str], FakeLLMProvider],
    monkeypatch: pytest.MonkeyPatch,
    error: BaseException | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from incident_copilot.evaluation import eval_runner

    events, _ = resources

    class Graph:
        async def ainvoke(self, state: Any, /) -> dict[str, IncidentReport]:
            assert events == []
            if error is not None:
                raise error
            return {
                "report": IncidentReport(
                    summary="offline", likely_causes=(), next_steps=(), confidence=0
                )
            }

    monkeypatch.setattr("incident_copilot.composition.build_graph", lambda *args: Graph())
    if error is None:
        await eval_runner.main()
        assert "Overall: 0/9" in capsys.readouterr().out
    else:
        with pytest.raises(type(error)) as caught:
            await eval_runner.main()
        assert caught.value is error
    assert events == ["provider", "logs", "metrics"]
