"""Application composition root.

Builds the FastAPI application around the collaborators from composition.py, and owns
what is HTTP-specific: routes, health-check probes, and the lifespan that closes the
connectors on shutdown.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from incident_copilot.api.routes import HealthCheck, build_router
from incident_copilot.composition import build_collaborators
from incident_copilot.config.settings import Settings, get_settings
from incident_copilot.models.enums import LLMProviderName
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

    collaborators = build_collaborators(settings)
    service = IncidentService(collaborators.graph)

    health_checks: dict[str, HealthCheck] = {
        "prometheus": _reachable(f"{settings.prometheus_url}/-/ready"),
        "elasticsearch": _reachable(f"{settings.elasticsearch_url}/_cluster/health"),
        "llm": _llm_health(settings),
    }

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Release the pooled clients when the application stops."""
        yield
        await app.state.prometheus_connector.aclose()
        await app.state.elasticsearch_connector.aclose()
        logger.info("connectors_closed")

    app = FastAPI(title="incident-response-copilot", version="0.1.0", lifespan=lifespan)
    # Held on app.state so the lifespan closes the same instances the graph is using.
    app.state.prometheus_connector = collaborators.metrics_source
    app.state.elasticsearch_connector = collaborators.log_source
    app.include_router(build_router(service, health_checks))
    logger.info("app_created", provider=settings.llm_provider.value)
    return app


def _llm_health(settings: Settings) -> HealthCheck:
    """Check configured model availability without generating tokens or loading Ollama."""

    async def check() -> bool:
        async with httpx.AsyncClient(timeout=3.0) as client:
            if settings.llm_provider is LLMProviderName.GROQ:
                try:
                    response = await client.get(
                        "https://api.groq.com/openai/v1/models",
                        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    )
                    if response.is_success and any(
                        model.get("id") == settings.groq_model
                        for model in response.json().get("data", [])
                    ):
                        return True
                except (httpx.HTTPError, ValueError):
                    pass
                if settings.llm_fallback_provider == "none":
                    return False
            try:
                response = await client.get(f"{settings.ollama_base_url}/api/tags")
                return response.is_success and any(
                    model.get("name") == settings.ollama_model
                    for model in response.json().get("models", [])
                )
            except (httpx.HTTPError, ValueError):
                return False

    return check


app = create_app()
