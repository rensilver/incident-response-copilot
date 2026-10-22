"""Async OpenAI Responses adapter."""

from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, SecretStr

from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.llm.messages import to_langchain_messages
from incident_copilot.utils.exceptions import StructuredOutputError


class OpenAIProvider(LLMProvider):
    """Adapt OpenAI Responses to the shared provider contract."""

    def __init__(self, chat: BaseChatModel) -> None:
        """Borrow an injected chat model."""
        self._chat = chat
        self._owned_clients: tuple[OpenAI, AsyncOpenAI] | None = None

    @classmethod
    def from_api_key(cls, api_key: SecretStr) -> "OpenAIProvider":
        """Construct owned clients without inference."""
        # Explicit SDK clients avoid LangChain's shared HTTP-client cache: closing
        # one provider must not close another provider's transport.
        sync_client = OpenAI(api_key=api_key.get_secret_value(), max_retries=0)
        async_client = AsyncOpenAI(api_key=api_key.get_secret_value(), max_retries=0)
        chat = ChatOpenAI(
            model="gpt-6-luna",
            api_key=api_key,
            use_responses_api=True,
            use_previous_response_id=False,
            output_version="responses/v1",
            reasoning={"effort": "none"},
            max_retries=0,
            root_client=sync_client,
            client=sync_client.chat.completions,
            root_async_client=async_client,
            async_client=async_client.chat.completions,
        )
        provider = cls(chat)
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
        return (await self._chat.ainvoke(to_langchain_messages(messages))).text

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        """Request JSON for shared validation and repair."""
        chat = self._chat.bind(response_format={"type": "json_object"})
        conversation = [
            SystemMessage(content="Return a JSON object."),
            *to_langchain_messages(messages),
        ]
        response = await chat.ainvoke(conversation)
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
        return self._chat.bind_tools(list(tools), strict=False)
