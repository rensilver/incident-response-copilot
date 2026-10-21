import httpx
import respx

from incident_copilot.config.settings import Settings
from incident_copilot.main import create_app


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
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert set(body["dependencies"]) == {"prometheus", "elasticsearch", "llm"}


async def test_shutdown_closes_both_connectors() -> None:
    """The connectors are built once at startup and hold long-lived clients; the
    lifespan has to hand them back or the app leaks a socket per reload."""
    app = create_app(Settings(_env_file=None))
    closed: list[str] = []

    for name in ("prometheus", "elasticsearch"):
        connector = getattr(app.state, f"{name}_connector")

        async def record(_name: str = name) -> None:
            closed.append(_name)

        connector.aclose = record

    # Driven directly: ASGITransport never emits lifespan events, so going through an
    # HTTP client here would assert nothing.
    async with app.router.lifespan_context(app):
        assert closed == []

    assert sorted(closed) == ["elasticsearch", "prometheus"]
