import asyncio
from unittest.mock import MagicMock

import httpx
import pytest
from groq import APIConnectionError, APIStatusError
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from incident_copilot.config.settings import Settings
from incident_copilot.llm.groq_provider import GroqProvider
from incident_copilot.utils.exceptions import LLMProviderError


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 503])
async def test_groq_api_errors_are_normalized_without_leaking_body(status):
    async def fail(messages):
        raise APIStatusError(
            "secret body",
            response=httpx.Response(status, request=httpx.Request("POST", "https://api.groq.com")),
            body=None,
        )

    provider = GroqProvider(RunnableLambda(fail))
    with pytest.raises(LLMProviderError, match=f"status={status}") as error:
        await provider.complete([])
    assert "secret body" not in str(error.value)


async def test_connection_failure_is_normalized():
    async def fail(messages):
        raise APIConnectionError(request=httpx.Request("POST", "https://api.groq.com"))

    with pytest.raises(LLMProviderError, match="APIConnectionError"):
        await GroqProvider(RunnableLambda(fail)).complete([])


async def test_request_has_wall_clock_deadline():
    async def hang(messages):
        await asyncio.Event().wait()

    with pytest.raises(LLMProviderError, match="TimeoutError"):
        await GroqProvider(RunnableLambda(hang), timeout_seconds=0.02).complete([])


async def test_json_mode_and_serial_tool_calls():
    async def reply(messages):
        return AIMessage(content='{"ok":true}')

    chat = MagicMock()
    chat.bind.return_value = RunnableLambda(reply)
    chat.bind_tools.return_value = RunnableLambda(reply)
    provider = GroqProvider(chat)
    assert await provider._generate_json([]) == '{"ok":true}'
    chat.bind.assert_called_once_with(response_format={"type": "json_object"})
    await provider.bind_tools([]).ainvoke([])
    chat.bind_tools.assert_called_once_with([], parallel_tool_calls=False)


def test_client_uses_configured_model_key_and_no_sdk_retries():
    provider = GroqProvider.from_settings(Settings(_env_file=None, groq_model="openai/gpt-oss-20b"))
    assert provider._chat.model_name == "openai/gpt-oss-20b"
    assert provider._chat.max_retries == 0
    assert provider._chat.request_timeout == 30
