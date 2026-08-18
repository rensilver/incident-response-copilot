"""Bounded tool-calling loop shared by the specialist agents.

The cap matters: `llama3.2:3b` will happily keep requesting tools forever. Two rounds is
enough to fetch a metric and follow up on it, and guarantees the node terminates.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from incident_copilot.llm.base import ChatMessage, LLMProvider
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
) -> ToolLoopResult:
    """Let the model call tools for at most ``max_rounds`` rounds.

    A tool that raises :class:`IncidentCopilotError` is recorded and the loop continues:
    one unreachable backend should degrade the report, not abort the investigation.

    Args:
        provider: Supplies the tool-bound runnable.
        tools: Tools the model may call.
        messages: Opening conversation.
        max_rounds: Hard cap on tool rounds.

    Returns:
        The gathered results and any recorded errors.
    """
    by_name = {tool.name: tool for tool in tools}
    runnable = provider.bind_tools(tools)
    conversation: list[BaseMessage] = [
        _ROLE_TO_MESSAGE[m.role](content=m.content) for m in messages
    ]
    outcome = ToolLoopResult()

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
        if not calls:
            break

        conversation.append(reply)
        for call in calls:
            name = str(call.get("name", ""))
            tool = by_name.get(name)
            if tool is None:
                outcome.errors.append(f"model requested unknown tool: {name!r}")
                continue
            try:
                result = await tool.ainvoke(call.get("args", {}))
            except IncidentCopilotError as exc:
                outcome.errors.append(f"{name} failed: {exc}")
                conversation.append(
                    ToolMessage(content=str(exc), tool_call_id=str(call.get("id", "")))
                )
                continue

            outcome.results.append(result)
            summary = getattr(result, "summary", None) or str(result)
            conversation.append(
                ToolMessage(content=str(summary), tool_call_id=str(call.get("id", "")))
            )
        logger.debug("tool_round_complete", round=round_index + 1, results=len(outcome.results))

    return outcome
