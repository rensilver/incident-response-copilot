"""Correlation node: turns gathered findings into a structured incident report."""

from incident_copilot.agents.prompts import (
    CORRELATION_SYSTEM,
    render_evidence,
    render_investigation_window,
)
from incident_copilot.agents.state import CorrelationUpdate, InvestigationNode, InvestigationState
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.models.report import IncidentReport
from incident_copilot.utils.exceptions import LLMProviderError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


def build_correlation_agent(
    provider: LLMProvider,
) -> InvestigationNode[CorrelationUpdate]:
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
                content=(
                    f"Incident question: {state['query']}\n"
                    f"Service of interest: {state['target_service'] or 'unspecified'}\n"
                    f"{render_investigation_window(state['time_window'])}\n"
                    f"Collection errors: {state['errors']}\n\n{evidence}"
                ),
            ),
        ]

        try:
            # This is a caller ceiling for schema repair, not a transport retry.
            # The production provider also applies its configured attempt cap and
            # shares one operation deadline across all generation/repair attempts.
            report = await provider.complete_structured(messages, IncidentReport, max_attempts=5)
        except LLMProviderError as exc:
            logger.warning("correlation_failed", error=str(exc))
            return {"report": None, "errors": [f"correlation failed: {exc}"]}

        logger.info("correlation_complete", causes=len(report.likely_causes))
        return {"report": report, "errors": []}

    return correlation_agent
