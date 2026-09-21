import asyncio
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel

from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.llm.fallback_provider import FallbackProvider
from incident_copilot.utils.exceptions import LLMProviderError


class Answer(BaseModel):
    answer: str


def providers():
    primary = FakeLLMProvider(["unused"])
    fallback = FakeLLMProvider(["unused"])
    return primary, fallback, FallbackProvider(primary, fallback)


async def test_success_does_not_contact_fallback():
    primary, fallback, provider = providers()
    primary.complete = AsyncMock(return_value="cloud")
    fallback.complete = AsyncMock()
    assert await provider.complete([]) == "cloud"
    fallback.complete.assert_not_awaited()


async def test_text_failure_switches_once():
    primary, fallback, provider = providers()
    primary.complete = AsyncMock(side_effect=LLMProviderError("unavailable"))
    fallback.complete = AsyncMock(return_value="local")
    messages = [ChatMessage(role="user", content="hello")]
    assert await provider.complete(messages) == "local"
    fallback.complete.assert_awaited_once_with(messages)


async def test_invalid_structured_output_exhausts_repairs_then_switches():
    primary = FakeLLMProvider(["bad JSON", "bad again"])
    fallback = FakeLLMProvider(['{"answer":"local"}'])
    result = await FallbackProvider(primary, fallback).complete_structured([], Answer, 2)
    assert result.answer == "local"


async def test_tool_fallback_preserves_history_ids_and_config():
    primary, fallback, provider = providers()
    seen = []

    async def fail(messages, config):
        raise LLMProviderError("rate limit")

    async def recover(messages, config):
        seen.append((messages, config))
        return AIMessage(content="done")

    primary.bind_tools = lambda tools: RunnableLambda(fail)
    fallback.bind_tools = lambda tools: RunnableLambda(recover)
    conversation = [
        HumanMessage(content="investigate"),
        AIMessage(content="", tool_calls=[{"id": "m1", "name": "metric", "args": {}}]),
        ToolMessage(content="latency rose", tool_call_id="m1"),
    ]
    result = await provider.bind_tools([]).ainvoke(conversation, config={"tags": ["incident"]})
    assert result.content == "done"
    assert seen[0][0] == conversation
    assert seen[0][0][-1].tool_call_id == "m1"
    assert "incident" in seen[0][1]["tags"]


async def test_both_providers_fail_with_clear_error():
    primary, fallback, provider = providers()
    primary.complete = AsyncMock(side_effect=LLMProviderError("cloud down"))
    fallback.complete = AsyncMock(side_effect=LLMProviderError("insufficient RAM"))
    with pytest.raises(LLMProviderError, match="Groq failed; Ollama.*insufficient RAM"):
        await provider.complete([])
    primary.complete.assert_awaited_once()
    fallback.complete.assert_awaited_once()


@pytest.mark.parametrize("error", [asyncio.CancelledError(), ValueError("coding error")])
async def test_cancellation_and_unexpected_errors_do_not_trigger_fallback(error):
    primary, fallback, provider = providers()
    primary.complete = AsyncMock(side_effect=error)
    fallback.complete = AsyncMock()
    with pytest.raises(type(error)):
        await provider.complete([])
    fallback.complete.assert_not_awaited()
