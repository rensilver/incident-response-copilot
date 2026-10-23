"""HTTP routes.

Collaborators are injected into :func:`build_router` rather than read from module state,
so tests construct a router over stubs and ``main.py`` remains the only place real
objects are built.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from incident_copilot.api.schemas import HealthResponse, InvestigationErrorResponse
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError, LLMProviderError
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


def build_router(
    service: IncidentService | None = None,
    health_checks: Mapping[str, HealthCheck] | None = None,
) -> APIRouter:
    """Build the API router.

    Args:
        service: Injected use-case orchestrator; otherwise resolve lifespan state.
        health_checks: Injected dependency probes; otherwise resolve lifespan state.

    Returns:
        A router exposing the investigation and health endpoints.
    """
    # The health endpoint intentionally stays outside the versioned API prefix.
    router = APIRouter(tags=["incident-copilot"])

    async def resolve_service(request: Request) -> IncidentService:
        resolved: IncidentService = service if service is not None else request.app.state.service
        return resolved

    async def resolve_checks(request: Request) -> Mapping[str, HealthCheck]:
        resolved: Mapping[str, HealthCheck] = (
            health_checks if health_checks is not None else request.app.state.health_checks
        )
        return resolved

    @router.post(
        "/api/v1/investigations",
        summary="Investigate an incident",
        responses={
            503: {
                "model": InvestigationErrorResponse,
                "description": "Investigation unavailable: no usable report was produced.",
            }
        },
    )
    async def create_investigation(
        request: InvestigationRequest,
        investigator: Annotated[IncidentService, Depends(resolve_service)],
    ) -> IncidentReport:
        """Run an investigation and return the structured report."""
        try:
            return await investigator.investigate(request)
        except (InvestigationError, LLMProviderError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Investigation unavailable; no usable report was produced.",
            ) from exc

    @router.get("/health", summary="Check application and dependency health")
    async def health(
        checks: Annotated[Mapping[str, HealthCheck], Depends(resolve_checks)],
    ) -> HealthResponse:
        """Report liveness and downstream reachability.

        Probes run concurrently: each carries its own timeout, so awaiting them one
        after another would let ``/health`` outlast the timeout of whatever polls it.
        """
        names = list(checks)
        results = await asyncio.gather(*(_probe(n, checks[n]) for n in names))
        dependencies = dict(zip(names, results, strict=True))
        healthy = all(dependencies.values())
        return HealthResponse(status="ok" if healthy else "degraded", dependencies=dependencies)

    return router
