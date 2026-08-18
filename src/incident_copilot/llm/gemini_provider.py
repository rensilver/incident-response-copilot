"""Gemini-backed LLM provider."""

from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.llm.ollama_provider import to_langchain_messages
from incident_copilot.utils.exceptions import ConfigurationError


class GeminiProvider(LLMProvider):
    """Talks to the Gemini API.

    Args:
        chat: Chat model used for all calls.
    """

    def __init__(self, chat: BaseChatModel) -> None:
        """Store the injected chat model.

        Args:
            chat: Chat model used for all calls.
        """
        self._chat = chat

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiProvider":
        """Build a provider from application settings.

        Raises:
            ConfigurationError: If no API key is configured.
        """
        if not settings.google_api_key:
            raise ConfigurationError("GOOGLE_API_KEY is required for the gemini provider")
        return cls(
            chat=ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.google_api_key,
                temperature=0.0,
            )
        )

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return a free-text completion."""
        response = await self._chat.ainvoke(to_langchain_messages(messages))
        return response.text

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Return raw JSON text.

        Gemini has no ``format=json`` switch equivalent, so the base-class repair loop
        does the enforcement.
        """
        response = await self._chat.ainvoke(to_langchain_messages(messages))
        return response.text

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        """Return a runnable with the given tools bound."""
        return self._chat.bind_tools(list(tools))
