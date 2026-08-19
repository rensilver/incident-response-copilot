"""HTTP routes.

Collaborators are injected into :func:`build_router` rather than read from module state,
so tests construct a router over stubs and ``main.py`` remains the only place real
objects are built.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping

from fastapi import APIRouter, HTTPException, status

from incident_copilot.api.schemas import HealthResponse
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)

HealthCheck = Callable[[], Awaitable[bool]]


async def _probe(name: str, check: HealthCheck) -> bool:
    """Run one health probe, treating any failure as unreachable.

    Args:
        name: Dependency name, for the log line.
        check: The probe to run.

    Returns:
        Whether the dependency answered.
    """
    try:
        return await check()
    except Exception as exc:  # noqa: BLE001 - a probe failure is a health signal, not a bug
        logger.warning("health_probe_failed", dependency=name, error=str(exc))
        return False


def build_router(service: IncidentService, health_checks: Mapping[str, HealthCheck]) -> APIRouter:
    """Build the API router.

    Args:
        service: Use-case orchestrator.
        health_checks: Named reachability probes for downstream systems.

    Returns:
        A router exposing the investigation and health endpoints.
    """
    router = APIRouter()

    @router.post("/api/v1/investigations", response_model=IncidentReport)
    async def create_investigation(request: InvestigationRequest) -> IncidentReport:
        """Run an investigation and return the structured report."""
        try:
            return await service.investigate(request)
        except InvestigationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc

    @router.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Report liveness and downstream reachability.

        Probes run concurrently: each carries its own timeout, so awaiting them one
        after another would let ``/health`` outlast the timeout of whatever polls it.
        """
        names = list(health_checks)
        results = await asyncio.gather(*(_probe(n, health_checks[n]) for n in names))
        dependencies = dict(zip(names, results, strict=True))
        healthy = all(dependencies.values())
        return HealthResponse(status="ok" if healthy else "degraded", dependencies=dependencies)

    return router
