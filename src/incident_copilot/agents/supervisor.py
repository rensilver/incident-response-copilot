"""Supervisor node: decides which specialists run.

The decision is made by the model but never trusted blindly. It is validated against
:class:`RouteDecision` and then against the set of routable specialists; either failure
falls back to running both. A small model that emits junk therefore degrades to a
fan-out rather than dead-ending the investigation (spec §2).
"""

from collections.abc import Awaitable, Callable
from typing import Any

from incident_copilot.agents.prompts import SUPERVISOR_SYSTEM
from incident_copilot.agents.state import InvestigationState
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.models.enums import AgentName
from incident_copilot.models.report import RouteDecision
from incident_copilot.utils.exceptions import LLMProviderError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)

SPECIALISTS: tuple[AgentName, ...] = (AgentName.METRICS, AgentName.LOGS)


def build_supervisor(
    provider: LLMProvider, settings: Settings
) -> Callable[[InvestigationState], Awaitable[dict[str, Any]]]:
    """Build the supervisor node bound to a provider.

    Args:
        provider: The LLM used to choose a route.
        settings: Supplies the iteration ceiling.

    Returns:
        An async graph node returning the ``route``, ``iterations`` and any ``errors``.
    """

    async def supervisor(state: InvestigationState) -> dict[str, Any]:
        """Choose which specialists to run."""
        iterations = state["iterations"] + 1

        if state["iterations"] >= settings.max_supervisor_iterations:
            logger.warning("supervisor_ceiling_reached", iterations=state["iterations"])
            return {
                "route": list(SPECIALISTS),
                "iterations": iterations,
                "errors": ["supervisor iteration ceiling reached; fallback fan-out"],
            }

        target = state["target_service"] or "unknown"
        messages = [
            ChatMessage(role="system", content=SUPERVISOR_SYSTEM),
            ChatMessage(
                role="user",
                content=f"Incident question: {state['query']}\nTarget service: {target}",
            ),
        ]

        try:
            decision = await provider.complete_structured(messages, RouteDecision, max_attempts=2)
        except LLMProviderError as exc:
            logger.warning("supervisor_route_unparsable", error=str(exc))
            return {
                "route": list(SPECIALISTS),
                "iterations": iterations,
                "errors": [f"routing fallback: {exc}"],
            }

        routable = [agent for agent in decision.agents if agent in SPECIALISTS]
        if not routable:
            logger.warning("supervisor_route_not_routable", agents=list(decision.agents))
            return {
                "route": list(SPECIALISTS),
                "iterations": iterations,
                "errors": ["routing fallback: no routable specialist named"],
            }

        logger.info("supervisor_routed", agents=[a.value for a in routable])
        return {"route": routable, "iterations": iterations, "errors": []}

    return supervisor
