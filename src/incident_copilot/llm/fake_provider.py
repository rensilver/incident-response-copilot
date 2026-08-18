"""Deterministic in-memory provider used by tests.

This exists so the whole graph is testable with no Docker and no model. It is
deliberately unreachable from configuration — see :func:`build_llm_provider`.
"""

from collections.abc import Sequence

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

    def __init__(self, responses: Sequence[str]) -> None:
        """Store the scripted responses.

        Args:
            responses: Responses to return, in order.

        Raises:
            ValueError: If no responses were supplied.
        """
        if not responses:
            raise ValueError("FakeLLMProvider needs at least one scripted response")
        self._responses = list(responses)
        self._index = 0
        self.calls: list[list[ChatMessage]] = []

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
        """Return a runnable that ignores tools and replays the script."""
        return RunnableLambda(lambda _: AIMessage(content=self._responses[0]))
