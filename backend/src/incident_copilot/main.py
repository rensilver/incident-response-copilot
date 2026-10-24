"""Application composition root.

Builds the FastAPI application around the collaborators from composition.py, and owns
what is HTTP-specific: routes, health-check probes, and the resource lifespan.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from incident_copilot.api.errors import install_error_handlers
from incident_copilot.api.routes import HealthCheck, build_router
from incident_copilot.composition import build_collaborators
from incident_copilot.config.settings import Settings, get_settings
from incident_copilot.services.incident_service import IncidentService
from incident_copilot.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


def _reachable(url: str) -> HealthCheck:
    """Build an async probe reporting whether ``url`` answers.

    Args:
        url: Endpoint to probe.

    Returns:
        A probe returning whether the endpoint answered without a server error.
    """

    async def check() -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                return (await client.get(url)).status_code < 500
        except httpx.HTTPError:
            return False

    return check


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build routes without reading settings or acquiring external resources.

    Lifespan startup validates settings and builds one collaborator set per serving
    lifetime. Import and OpenAPI inspection need no credentials. The composition
    context releases owned resources on shutdown or failed startup.

    Args:
        settings: Application settings; read at startup when omitted.

    Returns:
        The configured application.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Acquire serving resources and always release them through composition."""
        active_settings = settings if settings is not None else get_settings()
        configure_logging(active_settings.log_level)
        async with build_collaborators(active_settings) as collaborators:
            # Register routes once; their dependencies borrow these serving instances.
            try:
                app.state.service = IncidentService(
                    collaborators.graph,
                    timeout_seconds=active_settings.investigation_timeout_seconds,
                )
                app.state.health_checks = {
                    "prometheus": _reachable(f"{active_settings.prometheus_url}/-/ready"),
                    "elasticsearch": _reachable(
                        f"{active_settings.elasticsearch_url}/_cluster/health"
                    ),
                    "llm": collaborators.provider.health_check,
                }
                app.state.prometheus_connector = collaborators.metrics_source
                app.state.elasticsearch_connector = collaborators.log_source
                logger.info("app_started", provider=active_settings.llm_provider.value)
                yield
            finally:
                for name in (
                    "service",
                    "health_checks",
                    "prometheus_connector",
                    "elasticsearch_connector",
                ):
                    if hasattr(app.state, name):
                        delattr(app.state, name)
        logger.info("collaborators_closed")

    app = FastAPI(title="incident-response-copilot", version="0.1.0", lifespan=lifespan)
    install_error_handlers(app)
    app.include_router(build_router())
    return app


app = create_app()
