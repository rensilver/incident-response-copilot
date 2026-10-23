import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

import httpx
import pytest
from fastapi import FastAPI

from incident_copilot.api.routes import build_router
from incident_copilot.models.report import EvidenceRef, IncidentReport, LikelyCause
from incident_copilot.services.incident_service import InvestigationRequest
from incident_copilot.utils.exceptions import (
    InvestigationError,
    LLMProviderError,
    StructuredOutputError,
)

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


@pytest.mark.parametrize("minutes", [0, 1441])
async def test_invalid_window_is_rejected_before_investigation(minutes: int) -> None:
    service = StubService()
    async with _client(service) as client:
        response = await client.post(
            "/api/v1/investigations", json={"query": "q", "minutes_back": minutes}
        )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "minutes_back"]
    assert service.seen is None


@pytest.mark.parametrize("minutes", [None, 1, 1440])
async def test_default_and_boundary_windows_reach_investigation(minutes: int | None) -> None:
    service = StubService()
    payload: dict[str, str | int] = {"query": "q"}
    if minutes is not None:
        payload["minutes_back"] = minutes
    async with _client(service) as client:
        response = await client.post("/api/v1/investigations", json=payload)

    assert response.status_code == 200
    assert service.seen is not None
    assert service.seen.minutes_back == (60 if minutes is None else minutes)
    assert service.seen.service is None


async def test_response_filters_internal_report_and_evidence_fields() -> None:
    class InternalEvidence(EvidenceRef):
        connector_debug: str

    class InternalReport(IncidentReport):
        provider_debug: str

    class InternalService(StubService):
        async def investigate(self, request: InvestigationRequest) -> IncidentReport:
            return InternalReport(
                summary="cart-service regression",
                likely_causes=(
                    LikelyCause(
                        title="bad deploy",
                        rationale="5xx stepped up",
                        confidence=0.9,
                        supporting_evidence=(
                            InternalEvidence(
                                source="metrics",
                                detail="error rate rose",
                                connector_debug="private-connector-canary",
                            ),
                        ),
                    ),
                ),
                next_steps=("roll back",),
                confidence=0.9,
                provider_debug="private-provider-canary",
            )

    async with _client(InternalService()) as client:
        response = await client.post("/api/v1/investigations", json={"query": "q"})

    assert response.status_code == 200
    assert response.json() == {
        "summary": "cart-service regression",
        "likely_causes": [
            {
                "title": "bad deploy",
                "rationale": "5xx stepped up",
                "confidence": 0.9,
                "supporting_evidence": [{"source": "metrics", "detail": "error rate rose"}],
            }
        ],
        "next_steps": ["roll back"],
        "confidence": 0.9,
        "investigation_window": None,
    }


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
async def test_invalid_service_payload_cannot_be_sent_as_a_success(confidence: float) -> None:
    class InvalidService(StubService):
        async def investigate(self, request: InvestigationRequest) -> IncidentReport:
            # Deliberately violate the service contract to exercise HTTP validation.
            return cast(IncidentReport, {**REPORT.model_dump(), "confidence": confidence})

    app = FastAPI()
    app.include_router(build_router(InvalidService(), {}))  # type: ignore[arg-type]  # stub
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/investigations", json={"query": "q"})

    assert response.status_code == 500
    assert response.text == "Internal Server Error"


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


@pytest.mark.parametrize(
    "error",
    [
        InvestigationError("private-error-canary"),
        LLMProviderError("private-error-canary"),
        StructuredOutputError("private-error-canary", "private-output"),
    ],
)
async def test_failed_investigation_maps_to_sanitized_503(error: Exception) -> None:
    service = StubService(error=error)
    async with _client(service) as client:
        response = await client.post("/api/v1/investigations", json={"query": "q"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Investigation unavailable; no usable report was produced."
    }


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
