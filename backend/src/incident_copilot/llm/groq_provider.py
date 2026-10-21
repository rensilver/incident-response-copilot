"""Groq Cloud adapter with bounded requests and normalized backend errors."""

import asyncio
from collections.abc import Sequence

from groq import APIError
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from langchain_groq import ChatGroq
from pydantic import SecretStr

from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.llm.ollama_provider import to_langchain_messages
from incident_copilot.utils.exceptions import ConfigurationError, LLMProviderError


class GroqProvider(LLMProvider):
    """Use the same timeout/error boundary for text, JSON, and tool-bound calls."""

    def __init__(self, chat: BaseChatModel, timeout_seconds: float = 30.0) -> None:
        """Store the injected chat model and per-request deadline."""
        self._chat = chat
        self._timeout = timeout_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> "GroqProvider":
        """Build the Groq client without making a request."""
        if not settings.groq_api_key:
            raise ConfigurationError("GROQ_API_KEY is required for the groq provider")
        return cls(
            ChatGroq(
                model_name=settings.groq_model,
                api_key=SecretStr(settings.groq_api_key),
                temperature=0.0,
                timeout=settings.groq_timeout_seconds,
                max_retries=0,
            ),
            timeout_seconds=settings.groq_timeout_seconds,
        )

    def _bounded(
        self, runnable: Runnable[LanguageModelInput, BaseMessage]
    ) -> Runnable[LanguageModelInput, BaseMessage]:
        """Translate API failures without logging request bodies or credentials."""

        async def invoke(messages: LanguageModelInput, config: RunnableConfig) -> BaseMessage:
            try:
                async with asyncio.timeout(self._timeout):
                    return await runnable.ainvoke(messages, config=config)
            except (APIError, TimeoutError) as exc:
                status = getattr(exc, "status_code", None)
                raise LLMProviderError(
                    f"Groq request failed ({type(exc).__name__}, status={status})"
                ) from exc

        return RunnableLambda(invoke)

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return a free-text completion."""
        response = await self._bounded(self._chat).ainvoke(to_langchain_messages(messages))
        return response.text

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Request a JSON object; the shared repair loop validates the schema."""
        json_chat = self._chat.bind(response_format={"type": "json_object"})
        response = await self._bounded(json_chat).ainvoke(to_langchain_messages(messages))
        return response.text

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        """Bind local tools; GPT OSS does not support parallel tool calls."""
        return self._bounded(self._chat.bind_tools(list(tools), parallel_tool_calls=False))
