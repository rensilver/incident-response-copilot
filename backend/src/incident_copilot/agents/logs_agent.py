"""Logs specialist node."""

from collections.abc import Awaitable, Callable, Sequence

from langchain_core.tools import BaseTool

from incident_copilot.agents.prompts import LOGS_SYSTEM
from incident_copilot.agents.state import InvestigationState, LogsUpdate
from incident_copilot.agents.tool_loop import run_tool_rounds
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.models.logs import LogFinding
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


def build_logs_agent(
    provider: LLMProvider, tools: Sequence[BaseTool], settings: Settings
) -> Callable[[InvestigationState], Awaitable[LogsUpdate]]:
    """Build the logs specialist node.

    Args:
        provider: LLM used for tool calling.
        tools: Log tools bound to a connector.
        settings: Supplies the tool-round cap.

    Returns:
        An async graph node contributing ``log_findings``.
    """

    async def logs_agent(state: InvestigationState) -> LogsUpdate:
        """Gather log findings for the investigation."""
        target = state["target_service"] or "unknown"
        window = state["time_window"]
        messages = [
            ChatMessage(role="system", content=LOGS_SYSTEM),
            ChatMessage(
                role="user",
                content=(
                    f"Question: {state['query']}\nService of interest: {target}\n"
                    f"Investigation window: {window.start.isoformat()} "
                    f"to {window.end.isoformat()}. "
                    "All data tools use this fixed interval; minutes_back cannot override it."
                ),
            ),
        ]
        outcome = await run_tool_rounds(
            provider, tools, messages, settings.max_tool_rounds, time_window=window
        )
        findings = [r for r in outcome.results if isinstance(r, LogFinding)]
        logger.info("logs_agent_complete", findings=len(findings), errors=len(outcome.errors))
        return {"log_findings": findings, "errors": outcome.errors}

    return logs_agent
