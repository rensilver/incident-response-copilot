"""Per-operation fallback without replaying executed tools or entire investigations."""

from collections.abc import Awaitable, Callable, Sequence

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.utils.exceptions import LLMProviderError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


class FallbackProvider(LLMProvider):
    """Try Groq first, then Ollama once after a provider or structured-output failure."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        """Store providers; no backend is contacted during construction."""
        self.primary = primary
        self.fallback = fallback

    async def _run[T](
        self, primary: Callable[[], Awaitable[T]], fallback: Callable[[], Awaitable[T]]
    ) -> T:
        """Switch on expected provider failures; propagate cancellation and coding errors."""
        try:
            return await primary()
        except LLMProviderError as exc:
            logger.warning("llm_fallback", primary="groq", fallback="ollama", reason=str(exc))
        try:
            return await fallback()
        except LLMProviderError as exc:
            raise LLMProviderError(f"Groq failed; Ollama fallback unavailable: {exc}") from exc

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Complete using the primary, falling back on failure."""
        return await self._run(
            lambda: self.primary.complete(messages), lambda: self.fallback.complete(messages)
        )

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Generate JSON with transport fallback."""
        return await self._run(
            lambda: self.primary._generate_json(messages),
            lambda: self.fallback._generate_json(messages),
        )

    async def complete_structured[T: BaseModel](
        self, messages: Sequence[ChatMessage], schema: type[T], max_attempts: int = 3
    ) -> T:
        """Also switch when the primary exhausts its schema-repair attempts."""
        return await self._run(
            lambda: self.primary.complete_structured(messages, schema, max_attempts),
            lambda: self.fallback.complete_structured(messages, schema, max_attempts),
        )

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        """Keep the complete tool conversation and tracing config when switching."""
        primary = self.primary.bind_tools(tools)
        fallback = self.fallback.bind_tools(tools)

        async def invoke(messages: LanguageModelInput, config: RunnableConfig) -> BaseMessage:
            return await self._run(
                lambda: primary.ainvoke(messages, config=config),
                lambda: fallback.ainvoke(messages, config=config),
            )

        return RunnableLambda(invoke)
