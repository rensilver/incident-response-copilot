"""Metrics specialist node."""

from collections.abc import Awaitable, Callable, Sequence

from langchain_core.tools import BaseTool

from incident_copilot.agents.prompts import METRICS_SYSTEM
from incident_copilot.agents.state import InvestigationState
from incident_copilot.agents.tool_loop import run_tool_rounds
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.models.findings import MetricFindingBase
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


def build_metrics_agent(
    provider: LLMProvider, tools: Sequence[BaseTool], settings: Settings
) -> Callable[[InvestigationState], Awaitable[dict[str, object]]]:
    """Build the metrics specialist node.

    Args:
        provider: LLM used for tool calling.
        tools: Metric tools bound to a connector.
        settings: Supplies the tool-round cap.

    Returns:
        An async graph node contributing ``metrics_findings``.
    """

    async def metrics_agent(state: InvestigationState) -> dict[str, object]:
        """Gather metric findings for the investigation."""
        target = state["target_service"] or "unknown"
        messages = [
            ChatMessage(role="system", content=METRICS_SYSTEM),
            ChatMessage(
                role="user",
                content=f"Question: {state['query']}\nService of interest: {target}",
            ),
        ]
        outcome = await run_tool_rounds(provider, tools, messages, settings.max_tool_rounds)
        findings = [r for r in outcome.results if isinstance(r, MetricFindingBase)]
        logger.info("metrics_agent_complete", findings=len(findings), errors=len(outcome.errors))
        return {"metrics_findings": findings, "errors": outcome.errors}

    return metrics_agent
