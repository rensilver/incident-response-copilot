"""Ollama-backed LLM provider."""

import asyncio
from collections.abc import Sequence

import httpx
import psutil
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from ollama import ResponseError

from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.utils.exceptions import LLMProviderError


def to_langchain_messages(messages: Sequence[ChatMessage]) -> list[BaseMessage]:
    """Convert internal chat messages to LangChain messages."""
    mapping = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    return [mapping[m.role](content=m.content) for m in messages]


class OllamaProvider(LLMProvider):
    """Talks to a local or containerised Ollama server.

    Args:
        chat: Chat model used for free-text completions.
        json_chat: Chat model configured to emit JSON, used for structured output.
    """

    def __init__(
        self, chat: BaseChatModel, json_chat: BaseChatModel, settings: Settings | None = None
    ) -> None:
        """Store the injected chat models.

        Args:
            chat: Chat model used for free-text completions.
            json_chat: Chat model configured to emit JSON.
            settings: Runtime limits and memory guard; omitted for injected test models.
        """
        self._chat = chat
        self._json_chat = json_chat
        self._settings = settings
        self._lock = asyncio.Lock()

    @classmethod
    def from_settings(cls, settings: Settings) -> "OllamaProvider":
        """Build a provider from application settings."""

        def chat(json_mode: bool) -> ChatOllama:
            return ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=0.0,
                num_ctx=settings.ollama_num_ctx,
                num_predict=2048,
                reasoning=False,
                keep_alive="1m",
                client_kwargs={"timeout": settings.ollama_timeout_seconds},
                format="json" if json_mode else "",
            )

        return cls(chat=chat(False), json_chat=chat(True), settings=settings)

    async def _check_memory(self) -> None:
        """Conservatively guard a co-located Ollama server before loading a model.

        Set the threshold to zero for a remote server: client RAM cannot describe it.
        The check is advisory, not a reservation or a guarantee against OOM.
        """
        settings = self._settings
        if settings is None or settings.ollama_min_available_memory_mb == 0:
            return
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/ps")
            response.raise_for_status()
        loaded = any(
            model.get("name") == settings.ollama_model
            for model in response.json().get("models", [])
        )
        required = (
            min(1024, settings.ollama_min_available_memory_mb)
            if loaded
            else settings.ollama_min_available_memory_mb
        )
        available = psutil.virtual_memory().available // (1024 * 1024)
        if available < required:
            raise LLMProviderError(
                f"Ollama skipped: {available} MiB RAM available; {required} MiB required. "
                "Free memory or configure Ollama on a larger machine."
            )

    def _bounded(
        self, runnable: Runnable[LanguageModelInput, BaseMessage]
    ) -> Runnable[LanguageModelInput, BaseMessage]:
        """Serialize local calls and bound queueing, memory checks, and inference."""

        async def invoke(messages: LanguageModelInput, config: RunnableConfig) -> BaseMessage:
            timeout = self._settings.ollama_timeout_seconds if self._settings else 60.0
            try:
                async with asyncio.timeout(timeout), self._lock:
                    await self._check_memory()
                    return await runnable.ainvoke(messages, config=config)
            except (httpx.HTTPError, ResponseError, ConnectionError, TimeoutError) as exc:
                raise LLMProviderError(f"Ollama request failed ({type(exc).__name__})") from exc

        return RunnableLambda(invoke)

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return a free-text completion."""
        response = await self._bounded(self._chat).ainvoke(to_langchain_messages(messages))
        return response.text

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Return raw JSON text using the JSON-constrained client."""
        response = await self._bounded(self._json_chat).ainvoke(to_langchain_messages(messages))
        return response.text

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        """Return a runnable with the given tools bound."""
        return self._bounded(self._chat.bind_tools(list(tools)))
