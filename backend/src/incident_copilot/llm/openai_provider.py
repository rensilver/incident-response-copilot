"""Async OpenAI Responses adapter."""

import asyncio
from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, SecretStr

from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.llm.messages import to_langchain_messages
from incident_copilot.llm.openai_errors import invoke_openai
from incident_copilot.models.enums import LLMFailureKind
from incident_copilot.utils.exceptions import (
    ConfigurationError,
    LLMUpstreamError,
    StructuredOutputError,
)


class _SanitizedChatOpenAI(ChatOpenAI):
    """Normalize before BaseChatModel reports errors to tracing callbacks.

    A wrapper around ainvoke alone runs after the chat model's error callbacks.
    This async generation hook keeps the real serializer and tracing integration.
    """

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate asynchronously with a sanitized failure boundary."""
        return await invoke_openai(super()._agenerate(messages, stop, run_manager, **kwargs))


class OpenAIProvider(LLMProvider):
    """Adapt OpenAI Responses to the shared provider contract."""

    def __init__(
        self,
        chat: BaseChatModel,
        *,
        timeout_seconds: float = 60.0,
        max_structured_attempts: int = 3,
    ) -> None:
        """Borrow an injected chat model with operation and repair limits."""
        self._chat = chat
        self._timeout_seconds = timeout_seconds
        self._max_structured_attempts = max_structured_attempts
        self._owned_clients: tuple[OpenAI, AsyncOpenAI] | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAIProvider":
        """Build from validated settings without inference or credential logging."""
        if (
            settings.openai_api_key is None
            or not settings.openai_api_key.get_secret_value().strip()
        ):
            raise ConfigurationError("OPENAI_API_KEY is required for the openai provider")
        # Settings accepts exactly gpt-6-luna; every operation shares that policy.
        return cls.from_api_key(
            settings.openai_api_key,
            timeout_seconds=settings.llm_operation_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
            max_structured_attempts=settings.llm_max_structured_attempts,
        )

    @classmethod
    def from_api_key(
        cls,
        api_key: SecretStr,
        *,
        timeout_seconds: float = 60.0,
        max_output_tokens: int = 4096,
        max_structured_attempts: int = 3,
    ) -> "OpenAIProvider":
        """Construct owned clients with settings-supplied limits, without inference."""
        # Explicit SDK clients avoid LangChain's shared HTTP-client cache: closing
        # one provider must not close another provider's transport.
        sync_client = OpenAI(
            api_key=api_key.get_secret_value(), max_retries=0, timeout=timeout_seconds
        )
        async_client = AsyncOpenAI(
            api_key=api_key.get_secret_value(), max_retries=0, timeout=timeout_seconds
        )
        chat = _SanitizedChatOpenAI(
            model="gpt-6-luna",
            api_key=api_key,
            use_responses_api=True,
            use_previous_response_id=False,
            output_version="responses/v1",
            reasoning={"effort": "none"},
            max_tokens=max_output_tokens,
            timeout=timeout_seconds,
            max_retries=0,
            root_client=sync_client,
            client=sync_client.chat.completions,
            root_async_client=async_client,
            async_client=async_client.chat.completions,
        )
        provider = cls(
            chat, timeout_seconds=timeout_seconds, max_structured_attempts=max_structured_attempts
        )
        provider._owned_clients = (sync_client, async_client)
        return provider

    async def aclose(self) -> None:
        """Close both owned SDK clients; leave injected collaborators open.

        The owning application calls this after all in-flight work has finished.
        Repeated calls are safe, as both SDK close operations are idempotent.
        """
        if self._owned_clients is not None:
            sync_client, async_client = self._owned_clients
            try:
                sync_client.close()
            finally:
                await async_client.close()

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return a text completion."""
        return (await self._bounded(self._chat).ainvoke(to_langchain_messages(messages))).text

    async def complete_structured[T: BaseModel](
        self,
        messages: Sequence[ChatMessage],
        schema: type[T],
        max_attempts: int = 3,
    ) -> T:
        """Share one deadline across generation and the centrally capped repairs."""
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await super().complete_structured(
                    messages, schema, max_attempts=min(max_attempts, self._max_structured_attempts)
                )
        except TimeoutError:
            pass
        raise LLMUpstreamError(LLMFailureKind.TIMEOUT)

    def _bounded(
        self, runnable: Runnable[LanguageModelInput, BaseMessage]
    ) -> Runnable[LanguageModelInput, BaseMessage]:
        """Bound async model I/O without retrying or intercepting cancellation."""

        async def invoke(messages: LanguageModelInput, config: RunnableConfig) -> BaseMessage:
            try:
                async with asyncio.timeout(self._timeout_seconds):
                    return await invoke_openai(runnable.ainvoke(messages, config=config))
            except TimeoutError:
                pass
            raise LLMUpstreamError(LLMFailureKind.TIMEOUT)

        return RunnableLambda(invoke)

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Request JSON for shared validation and repair."""
        chat = self._chat.bind(response_format={"type": "json_object"})
        conversation = [
            SystemMessage(content="Return a JSON object."),
            *to_langchain_messages(messages),
        ]
        response = await self._bounded(chat).ainvoke(conversation)
        # Inspect metadata before extracting text: a refusal or truncated response
        # may also contain JSON that would otherwise validate as a report.
        if isinstance(response.content, list) and any(
            isinstance(block, dict) and block.get("type") == "refusal" for block in response.content
        ):
            raise StructuredOutputError("OpenAI refused structured output", raw_output="")
        if response.response_metadata.get("status") == "incomplete":
            raise StructuredOutputError("OpenAI structured response was incomplete", raw_output="")
        # Injected chat models need not have Responses metadata. Real Responses
        # expose status; pending, failed, and cancelled responses are never reports.
        if response.response_metadata.get("status") not in (None, "completed"):
            raise StructuredOutputError(
                "OpenAI structured response was not completed", raw_output=""
            )
        return response.text

    def _validate_json_output[T: BaseModel](self, raw: str, schema: type[T]) -> T:
        """Validate the entire JSON-mode response without salvaging substrings."""
        return schema.model_validate_json(raw)

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        """Bind tools for an async conversation."""
        # Keep optional arguments/defaults intact rather than letting Responses
        # normalize them into required strict-schema fields. Tools validate locally.
        return self._bounded(self._chat.bind_tools(list(tools), strict=False))
