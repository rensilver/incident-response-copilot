"""Run real FastAPI/service boundaries with a deterministic graph and no external I/O."""

import asyncio

from incident_copilot.agents.state import InvestigationState
from incident_copilot.main import create_app
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import IncidentService
from incident_copilot.utils.exceptions import LLMProviderError


class Graph:
    """Supply controlled graph outcomes behind the real investigation service."""

    async def ainvoke(self, state: InvestigationState, /) -> dict[str, IncidentReport]:
        """Produce a report, provider failure, bug, or real service deadline."""
        match state["query"]:
            case "deadline":
                await asyncio.sleep(60)
            case "unavailable":
                raise LLMProviderError("private-canary")
            case "bug":
                raise RuntimeError("private-canary")
        return {
            "report": IncidentReport(
                summary=f"{state['query']}:{state['target_service']}",
                likely_causes=(),
                next_steps=(),
                confidence=0,
            )
        }


async def up() -> bool:
    """Supply deterministic healthy dependency state."""
    return True


app = create_app()
# The probe disables lifespan: no settings, credentials, connectors, or SDK clients.
# Exceed Next's 30-second default to exercise the configured proxy budget as well
# as delivery of an actual service deadline. No model or remote dependency runs.
app.state.service = IncidentService(Graph(), timeout_seconds=31)
app.state.health_checks = {"probe": up}
