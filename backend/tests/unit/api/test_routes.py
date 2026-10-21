import asyncio
from collections.abc import Awaitable, Callable

import httpx
from fastapi import FastAPI

from incident_copilot.api.routes import build_router
from incident_copilot.models.report import EvidenceRef, IncidentReport, LikelyCause
from incident_copilot.services.incident_service import InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError

REPORT = IncidentReport(
    summary="cart-service regression",
    likely_causes=(
        LikelyCause(
            title="bad deploy",
            rationale="5xx stepped up",
            confidence=0.9,
            supporting_evidence=(EvidenceRef(source="metrics", detail="error rate rose"),),
        ),
    ),
    next_steps=("roll back",),
    confidence=0.9,
)


class StubService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.seen: InvestigationRequest | None = None

    async def investigate(self, request: InvestigationRequest) -> IncidentReport:
        self.seen = request
        if self.error:
            raise self.error
        return REPORT


def _client(
    service: StubService,
    checks: dict[str, Callable[[], Awaitable[bool]]] | None = None,
) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(build_router(service, checks or {}))  # type: ignore[arg-type]  # stub
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_investigation_returns_the_report() -> None:
    async with _client(StubService()) as client:
        response = await client.post(
            "/api/v1/investigations", json={"query": "why is cart-service failing?"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "cart-service regression"
    assert body["likely_causes"][0]["title"] == "bad deploy"


async def test_request_body_is_validated() -> None:
    async with _client(StubService()) as client:
        response = await client.post("/api/v1/investigations", json={"query": ""})
    assert response.status_code == 422


async def test_request_reaches_the_service_intact() -> None:
    service = StubService()
    async with _client(service) as client:
        await client.post(
            "/api/v1/investigations",
            json={"query": "q", "service": "cart-service", "minutes_back": 120},
        )

    assert service.seen is not None
    assert service.seen.service == "cart-service"
    assert service.seen.minutes_back == 120


async def test_failed_investigation_maps_to_503() -> None:
    service = StubService(error=InvestigationError("no report produced"))
    async with _client(service) as client:
        response = await client.post("/api/v1/investigations", json={"query": "q"})

    assert response.status_code == 503
    assert "no report produced" in response.json()["detail"]


async def test_health_reports_each_dependency() -> None:
    async def up() -> bool:
        return True

    async def down() -> bool:
        return False

    async with _client(StubService(), {"prometheus": up, "elasticsearch": down}) as client:
        response = await client.get("/health")

    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"] == {"prometheus": True, "elasticsearch": False}


async def test_health_is_ok_when_everything_is_reachable() -> None:
    async def up() -> bool:
        return True

    async with _client(StubService(), {"prometheus": up}) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_health_probes_run_concurrently() -> None:
    """Probes have a per-request timeout each, so running them one after another puts
    /health past a load balancer's patience. Both probes here wait on a barrier of two:
    concurrent execution releases it, sequential execution cannot and times out.
    """
    barrier = asyncio.Barrier(2)

    async def probe() -> bool:
        await asyncio.wait_for(barrier.wait(), timeout=2.0)
        return True

    async with _client(StubService(), {"prometheus": probe, "elasticsearch": probe}) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_health_is_degraded_when_a_probe_raises() -> None:
    """A probe that raises means the dependency is not reachable; it must not turn
    /health itself into a 500."""

    async def boom() -> bool:
        raise RuntimeError("connection refused")

    async with _client(StubService(), {"prometheus": boom}) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "dependencies": {"prometheus": False}}
