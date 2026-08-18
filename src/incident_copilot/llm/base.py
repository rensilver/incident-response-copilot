"""Provider-agnostic LLM interface."""

import json
import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Literal

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from incident_copilot.utils.exceptions import LLMProviderError, StructuredOutputError

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class ChatMessage(BaseModel):
    """One message in a chat exchange."""

    role: Literal["system", "user", "assistant"]
    content: str


class LLMProvider(ABC):
    """Interface every LLM backend must satisfy.

    Implementations are fully interchangeable: nothing above this layer may depend on
    which concrete provider it received.
    """

    @abstractmethod
    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return a free-text completion."""

    @abstractmethod
    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Return raw text that is expected to contain JSON."""

    @abstractmethod
    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        """Return a runnable with the given tools bound."""

    async def complete_structured[T: BaseModel](
        self,
        messages: Sequence[ChatMessage],
        schema: type[T],
        max_attempts: int = 3,
    ) -> T:
        """Coerce the model into ``schema``, repairing malformed output.

        Small local models emit invalid JSON a meaningful fraction of the time, so the
        validation error is fed back as a repair instruction rather than surfacing as a
        crash. The loop lives here so no caller reimplements it.

        Args:
            messages: The conversation so far.
            schema: The Pydantic model to produce.
            max_attempts: Total attempts, including the first.

        Returns:
            A validated instance of ``schema``.

        Raises:
            StructuredOutputError: If no attempt produced valid output.
            LLMProviderError: If the backend could not be reached at all.
        """
        conversation = list(messages)
        raw = ""
        for _ in range(max_attempts):
            # This is the adapter boundary: concrete providers fail with whatever their
            # client library raises (httpx, google-genai, grpc). Callers handle
            # LLMProviderError, so anything else has to be translated here or it escapes
            # the graph entirely and becomes a 500.
            try:
                raw = await self._generate_json(conversation)
            except LLMProviderError:
                raise
            except Exception as exc:  # noqa: BLE001 - deliberate third-party translation
                raise LLMProviderError(f"LLM call failed: {exc}") from exc
            try:
                return schema.model_validate_json(_extract_json(raw))
            except (ValidationError, ValueError) as exc:
                conversation = [
                    *conversation,
                    ChatMessage(role="assistant", content=raw),
                    ChatMessage(
                        role="user",
                        content=(
                            "That output was not valid for the required schema. "
                            f"Error: {exc}. Reply with JSON only, matching this schema: "
                            f"{json.dumps(schema.model_json_schema())}"
                        ),
                    ),
                ]
        raise StructuredOutputError(
            f"could not obtain valid {schema.__name__} after {max_attempts} attempts",
            raw_output=raw,
        )


def _extract_json(raw: str) -> str:
    """Strip markdown fences and surrounding prose from a JSON payload."""
    fenced = _FENCE.search(raw)
    candidate = fenced.group(1) if fenced else raw
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model output")
    return candidate[start : end + 1]
