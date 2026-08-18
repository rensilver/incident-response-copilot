"""Application composition root.

The only module that constructs concrete connectors, providers and the graph. Everything
else receives its collaborators through an interface.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from incident_copilot.agents.graph import build_graph
from incident_copilot.api.routes import HealthCheck, build_router
from incident_copilot.config.settings import Settings, get_settings
from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.services.incident_service import IncidentService
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools
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
    """Build the FastAPI application with every collaborator wired in.

    Connectors, the LLM provider and the graph are built once here, not per request:
    both connectors hold pooled clients, and rebuilding them per request would discard
    every connection. The lifespan below releases them on shutdown.

    Args:
        settings: Application settings; read from the environment when omitted.

    Returns:
        The configured application.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    metrics_source = PrometheusConnector.from_settings(settings)
    log_source = ElasticsearchConnector.from_settings(settings)
    provider = build_llm_provider(settings)

    graph = build_graph(
        provider,
        build_metrics_tools(metrics_source),
        build_log_tools(log_source),
        settings,
    )
    service = IncidentService(graph)

    health_checks: dict[str, HealthCheck] = {
        "prometheus": _reachable(f"{settings.prometheus_url}/-/ready"),
        "elasticsearch": _reachable(f"{settings.elasticsearch_url}/_cluster/health"),
        "llm": _reachable(f"{settings.ollama_base_url}/api/tags"),
    }

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Release the pooled clients when the application stops."""
        yield
        await app.state.prometheus_connector.aclose()
        await app.state.elasticsearch_connector.aclose()
        logger.info("connectors_closed")

    app = FastAPI(title="incident-response-copilot", version="0.1.0", lifespan=lifespan)
    # Held on app.state so the lifespan closes the same instances the graph is using.
    app.state.prometheus_connector = metrics_source
    app.state.elasticsearch_connector = log_source
    app.include_router(build_router(service, health_checks))
    logger.info("app_created", provider=settings.llm_provider.value)
    return app


app = create_app()
