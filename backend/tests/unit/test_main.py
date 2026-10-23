from unittest.mock import Mock

import httpx
import pytest
import respx
from pydantic import ValidationError

from incident_copilot.config.settings import Settings
from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.main import create_app


@pytest.mark.parametrize("key", [None, "", " \t\n"])
async def test_missing_configuration_fails_before_collaborator_construction(
    monkeypatch: pytest.MonkeyPatch, key: str | None
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    if key is not None:
        monkeypatch.setenv("OPENAI_API_KEY", key)
    construct = Mock(side_effect=AssertionError("Invalid startup must not construct clients"))
    monkeypatch.setattr("incident_copilot.main.build_collaborators", construct)
    app = create_app()
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        async with app.router.lifespan_context(app):
            pytest.fail("Invalid settings must prevent startup")
    construct.assert_not_called()


@respx.mock
async def test_health_uses_the_provider_built_for_the_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HealthyProvider(FakeLLMProvider):
        async def _probe_health(self) -> bool:
            return True

    provider = HealthyProvider(["unused"])

    async def build_provider(_: Settings) -> FakeLLMProvider:
        return provider

    monkeypatch.setattr("incident_copilot.composition.build_llm_provider", build_provider)
    app = create_app(Settings(_env_file=None))
    respx.get("http://localhost:9090/-/ready").respond(200)
    respx.get("http://localhost:9200/_cluster/health").respond(200)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/health")
    assert response.json() == {
        "status": "ok",
        "dependencies": {"prometheus": True, "elasticsearch": True, "llm": True},
    }
    assert len(respx.calls) == 2


def test_app_exposes_both_routes() -> None:
    # Asserted through the OpenAPI schema rather than app.routes: FastAPI wraps an
    # included router in an object with no .path, and the schema is the surface
    # clients actually see.
    app = create_app(Settings(_env_file=None))
    paths = set(app.openapi()["paths"])
    assert "/api/v1/investigations" in paths
    assert "/health" in paths


@respx.mock
async def test_health_endpoint_answers_without_any_backend_running() -> None:
    """Every dependency is down in unit tests; health must still respond, as degraded."""
    app = create_app(Settings(_env_file=None))
    respx.route().mock(side_effect=httpx.ConnectError("offline"))
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert set(body["dependencies"]) == {"prometheus", "elasticsearch", "llm"}


async def test_shutdown_closes_both_connectors(monkeypatch: pytest.MonkeyPatch) -> None:
    """The connectors are built once at startup and hold long-lived clients; the
    lifespan has to hand them back or the app leaks a socket per reload."""
    closed: list[str] = []

    # Install before acquisition: composition registers bound cleanup callbacks.
    metrics_close = PrometheusConnector.aclose
    logs_close = ElasticsearchConnector.aclose

    async def close_metrics(connector: PrometheusConnector) -> None:
        await metrics_close(connector)
        closed.append("prometheus")

    async def close_logs(connector: ElasticsearchConnector) -> None:
        await logs_close(connector)
        closed.append("elasticsearch")

    monkeypatch.setattr(PrometheusConnector, "aclose", close_metrics)
    monkeypatch.setattr(ElasticsearchConnector, "aclose", close_logs)
    app = create_app(Settings(_env_file=None))

    # Driven directly: ASGITransport never emits lifespan events, so going through an
    # HTTP client here would assert nothing.
    async with app.router.lifespan_context(app):
        assert closed == []

    assert sorted(closed) == ["elasticsearch", "prometheus"]
