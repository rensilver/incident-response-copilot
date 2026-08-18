"""Ollama-backed LLM provider."""

from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama

from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider


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

    def __init__(self, chat: BaseChatModel, json_chat: BaseChatModel) -> None:
        """Store the injected chat models.

        Args:
            chat: Chat model used for free-text completions.
            json_chat: Chat model configured to emit JSON.
        """
        self._chat = chat
        self._json_chat = json_chat

    @classmethod
    def from_settings(cls, settings: Settings) -> "OllamaProvider":
        """Build a provider from application settings."""
        common = {
            "model": settings.ollama_model,
            "base_url": settings.ollama_base_url,
            "temperature": 0.0,
        }
        return cls(chat=ChatOllama(**common), json_chat=ChatOllama(**common, format="json"))

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return a free-text completion."""
        response = await self._chat.ainvoke(to_langchain_messages(messages))
        return response.text

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Return raw JSON text using the JSON-constrained client."""
        response = await self._json_chat.ainvoke(to_langchain_messages(messages))
        return response.text

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        """Return a runnable with the given tools bound."""
        return self._chat.bind_tools(list(tools))
