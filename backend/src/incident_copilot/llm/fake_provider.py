"""Deterministic in-memory provider used by tests.

This exists so the whole graph is testable with no Docker and no model. It is
deliberately unreachable from configuration — see :func:`build_llm_provider`.
"""

import threading
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool

from incident_copilot.llm.base import ChatMessage, LLMProvider


class FakeLLMProvider(LLMProvider):
    """Replays a scripted list of responses and records the calls it received.

    Args:
        responses: Responses to return, in order. The final response repeats once
            exhausted, so tests need not pad the script.
    """

    def __init__(
        self,
        responses: Sequence[str],
        tool_rounds: Sequence[Sequence[dict[str, Any]]] | None = None,
    ) -> None:
        """Store the scripted responses and any scripted tool-call rounds.

        Args:
            responses: Responses to return, in order.
            tool_rounds: Tool calls to emit from ``bind_tools``, one entry per round.
                A round is served only to a caller that bound every tool it names. Once
                no round matches, the runnable returns a plain message, which is what
                terminates a specialist's tool loop.

        Raises:
            ValueError: If no responses were supplied.
        """
        if not responses:
            raise ValueError("FakeLLMProvider needs at least one scripted response")
        self._responses = list(responses)
        self._index = 0
        self._tool_rounds = [list(round_) for round_ in (tool_rounds or [])]
        self._script_lock = threading.Lock()
        self.calls: list[list[ChatMessage]] = []

    def _claim_round(self, available: set[str]) -> list[dict[str, Any]] | None:
        """Atomically take the first scripted round this toolset can satisfy.

        The lock is not optional. LangGraph runs the specialists concurrently and
        LangChain executes a sync ``RunnableLambda`` body in a worker thread, so an
        unguarded scan-then-``pop`` can hand a caller a round that slid into the matched
        index after it matched — silently serving one specialist another's round.
        """
        with self._script_lock:
            for index, round_ in enumerate(self._tool_rounds):
                if all(str(call.get("name", "")) in available for call in round_):
                    return self._tool_rounds.pop(index)
        return None

    def _next(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(list(messages))
        response = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        return response

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return the next scripted response."""
        return self._next(messages)

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Return the next scripted response verbatim."""
        return self._next(messages)

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        """Return a runnable serving the scripted rounds this toolset can satisfy.

        One provider is shared by every specialist in the graph, so a round is served
        only to a caller that actually bound the tools it names. Matching scans from the
        start of the script, which keeps a single agent's rounds in order while staying
        independent of the order the parallel specialists happen to run in.
        """
        available = {tool.name for tool in tools}

        def _respond(_: LanguageModelInput) -> BaseMessage:
            claimed = self._claim_round(available)
            if claimed is not None:
                return AIMessage(content="", tool_calls=claimed)
            return AIMessage(content=self._responses[min(self._index, len(self._responses) - 1)])

        return RunnableLambda(_respond)
