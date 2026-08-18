"""Correlation node: turns gathered findings into a structured incident report."""

from collections.abc import Awaitable, Callable

from incident_copilot.agents.prompts import CORRELATION_SYSTEM, render_evidence
from incident_copilot.agents.state import CorrelationUpdate, InvestigationState
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.models.report import IncidentReport
from incident_copilot.utils.exceptions import LLMProviderError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


def build_correlation_agent(
    provider: LLMProvider,
) -> Callable[[InvestigationState], Awaitable[CorrelationUpdate]]:
    """Build the correlation node bound to a provider.

    Args:
        provider: LLM used to produce the report.

    Returns:
        An async graph node contributing ``report``.
    """

    async def correlation_agent(state: InvestigationState) -> CorrelationUpdate:
        """Correlate all findings into an :class:`IncidentReport`."""
        evidence = render_evidence(state["metrics_findings"], state["log_findings"])
        messages = [
            ChatMessage(role="system", content=CORRELATION_SYSTEM),
            ChatMessage(
                role="user",
                content=f"Incident question: {state['query']}\n\n{evidence}",
            ),
        ]

        try:
            report = await provider.complete_structured(messages, IncidentReport)
        except LLMProviderError as exc:
            logger.warning("correlation_failed", error=str(exc))
            return {"report": None, "errors": [f"correlation failed: {exc}"]}

        logger.info("correlation_complete", causes=len(report.likely_causes))
        return {"report": report, "errors": []}

    return correlation_agent
