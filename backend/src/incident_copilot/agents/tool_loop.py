"""Bounded tool-calling loop shared by the specialist agents.

The round cap bounds model invocations even when replies keep requesting tools.
Each reply may contain multiple calls; I/O deadlines belong to the collaborators.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from incident_copilot.agents.prompts import render_log_finding, render_metric_finding
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.models.findings import MetricFindingBase
from incident_copilot.models.logs import LogFinding
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.window import INVESTIGATION_WINDOW_KEY
from incident_copilot.utils.exceptions import IncidentCopilotError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)

_ROLE_TO_MESSAGE = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}


@dataclass
class ToolLoopResult:
    """What one specialist gathered.

    Attributes:
        results: Values returned by the tools, in call order.
        errors: Human-readable failures that did not abort the loop.
    """

    results: list[object] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def run_tool_rounds(
    provider: LLMProvider,
    tools: Sequence[BaseTool],
    messages: Sequence[ChatMessage],
    max_rounds: int,
    *,
    time_window: TimeWindow | None = None,
) -> ToolLoopResult:
    """Let the model call tools for at most ``max_rounds`` rounds.

    A tool that raises :class:`IncidentCopilotError`, or whose call args fail schema
    validation, is recorded and the loop continues: one unreachable backend or one
    hallucinated argument should degrade the report, not abort the investigation.
    Unknown tools and malformed JSON arguments also receive matching error replies,
    so a later round can recover without leaving unanswered calls in the history.
    External cancellation propagates; unexpected tool implementation errors escape.

    Args:
        provider: Supplies the tool-bound runnable.
        tools: Tools the model may call.
        messages: Opening conversation.
        max_rounds: Hard cap on tool rounds.
        time_window: Fixed investigation interval, passed outside model-controlled args.

    Returns:
        The gathered results and any recorded errors.
    """
    by_name = {tool.name: tool for tool in tools}
    runnable = provider.bind_tools(tools)
    conversation: list[BaseMessage] = [
        _ROLE_TO_MESSAGE[m.role](content=m.content) for m in messages
    ]
    outcome = ToolLoopResult()
    tool_config: RunnableConfig = {}
    if time_window is not None:
        tool_config["configurable"] = {INVESTIGATION_WINDOW_KEY: time_window}

    for round_index in range(max_rounds):
        # The tool-bound runnable comes from a third-party client, so an unreachable
        # model arrives as whatever that library raises. Recording it keeps one dead
        # backend from aborting the investigation, matching how tool failures are
        # handled below.
        try:
            reply = await runnable.ainvoke(conversation)
        except Exception as exc:  # noqa: BLE001 - deliberate third-party translation
            logger.warning("tool_round_llm_failed", round=round_index + 1, error=str(exc))
            outcome.errors.append(f"model call failed: {exc}")
            break

        calls = list(getattr(reply, "tool_calls", []) or [])
        invalid_calls = list(getattr(reply, "invalid_tool_calls", []) or [])
        if not calls and not invalid_calls:
            break

        conversation.append(reply)
        for invalid_call in invalid_calls:
            # The adapter retains malformed JSON separately from executable calls.
            # Do not execute it or echo raw arguments/parser diagnostics into errors.
            error = f"model supplied malformed arguments for tool: {invalid_call.get('name')!r}"
            outcome.errors.append(error)
            conversation.append(
                ToolMessage(
                    content=error,
                    tool_call_id=str(invalid_call.get("id") or ""),
                    status="error",
                )
            )
        for call in calls:
            name = str(call.get("name", ""))
            tool = by_name.get(name)
            if tool is None:
                error = f"model requested unknown tool: {name!r}"
                outcome.errors.append(error)
                conversation.append(
                    ToolMessage(
                        content=error,
                        tool_call_id=str(call.get("id", "")),
                        status="error",
                    )
                )
                continue
            try:
                result = await tool.ainvoke(call.get("args", {}), config=tool_config)
            except (IncidentCopilotError, ValidationError) as exc:
                # ValidationError covers a hallucinated argument (e.g. an invalid enum
                # value) that LangChain rejects before the tool body ever runs.
                outcome.errors.append(f"{name} failed: {exc}")
                conversation.append(
                    ToolMessage(content=str(exc), tool_call_id=str(call.get("id", "")))
                )
                continue

            outcome.results.append(result)
            if isinstance(result, LogFinding):
                summary = render_log_finding(result)
            elif isinstance(result, MetricFindingBase):
                summary = render_metric_finding(result)
            else:
                summary = getattr(result, "summary", None) or str(result)
            conversation.append(
                ToolMessage(content=str(summary), tool_call_id=str(call.get("id", "")))
            )
        logger.debug("tool_round_complete", round=round_index + 1, results=len(outcome.results))

    return outcome
