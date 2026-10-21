"""Exercise real provider adapters with simulated HTTP responses, without inference."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
import respx
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.utils.exceptions import LLMProviderError

GROQ = "https://api.groq.com/openai/v1/chat/completions"
OLLAMA = "http://localhost:11434"
MESSAGES = [ChatMessage(role="user", content="Reply OK")]


class Answer(BaseModel):
    answer: str


def cloud_reply(content):
    return httpx.Response(
        200,
        json={
            "id": "test",
            "model": "openai/gpt-oss-20b",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def local_reply(content="local"):
    message = {"role": "assistant", "content": content}
    return httpx.Response(
        200,
        content=json.dumps({"model": "qwen3:4b", "message": message, "done": True}) + "\n",
        headers={"Content-Type": "application/x-ndjson"},
    )


@pytest.fixture
def local_capacity(monkeypatch):
    # This simulates capacity only in offline tests; no local model is contacted.
    monkeypatch.setattr(
        "incident_copilot.llm.ollama_provider.psutil.virtual_memory",
        lambda: SimpleNamespace(available=5000 * 1024**2),
    )


@pytest.mark.parametrize("failure", [401, 429, 503, "connection", "timeout"])
@respx.mock
async def test_transport_failures_fall_back_and_next_operation_retries_groq(
    local_capacity, failure
):
    attempts = []

    async def fail(request):
        attempts.append("failure")
        if failure == "connection":
            raise httpx.ConnectError("offline test", request=request)
        if failure == "timeout":
            await asyncio.Event().wait()
        return httpx.Response(failure, json={"error": {"message": "deliberate test failure"}})

    cloud = respx.post(GROQ).mock(side_effect=fail)
    status = respx.get(f"{OLLAMA}/api/ps").respond(200, json={"models": []})
    local = respx.post(f"{OLLAMA}/api/chat").mock(return_value=local_reply())
    provider = build_llm_provider(Settings(_env_file=None, groq_timeout_seconds=0.1))
    assert await provider.complete(MESSAGES) == "local"
    assert attempts == ["failure"]
    assert status.call_count == local.call_count == 1

    def recover(request):
        attempts.append("recovery")
        return cloud_reply("cloud recovered")

    cloud.mock(side_effect=recover)
    assert await provider.complete(MESSAGES) == "cloud recovered"
    assert attempts == ["failure", "recovery"]
    assert local.call_count == 1


@respx.mock
async def test_structured_repair_exhaustion_falls_back_through_real_adapters(local_capacity):
    cloud = respx.post(GROQ).mock(return_value=cloud_reply("not JSON"))
    respx.get(f"{OLLAMA}/api/ps").respond(200, json={"models": []})
    local = respx.post(f"{OLLAMA}/api/chat").mock(return_value=local_reply('{"answer":"local"}'))
    provider = build_llm_provider(Settings(_env_file=None))
    assert (await provider.complete_structured(MESSAGES, Answer, max_attempts=2)).answer == "local"
    assert cloud.call_count == 2
    assert local.call_count == 1


@pytest.mark.parametrize("failure", ["connection", "timeout", "missing_model", "memory"])
@respx.mock(assert_all_called=False)
async def test_both_provider_failures_are_bounded_and_normalized(
    local_capacity, monkeypatch, failure, respx_mock
):
    respx_mock.post(GROQ).respond(503, json={"error": {"message": "cloud unavailable"}})

    async def status_response(request):
        if failure == "connection":
            raise httpx.ConnectError("offline test", request=request)
        if failure == "timeout":
            await asyncio.Event().wait()
        return httpx.Response(200, json={"models": []})

    respx_mock.get(f"{OLLAMA}/api/ps").mock(side_effect=status_response)
    local = respx_mock.post(f"{OLLAMA}/api/chat").respond(404, json={"error": "model not found"})
    if failure == "memory":
        monkeypatch.setattr(
            "incident_copilot.llm.ollama_provider.psutil.virtual_memory",
            lambda: SimpleNamespace(available=1000 * 1024**2),
        )
    provider = build_llm_provider(Settings(_env_file=None, ollama_timeout_seconds=0.1))
    expected = {
        "connection": "ConnectError",
        "timeout": "TimeoutError",
        "missing_model": "ResponseError",
        "memory": "Ollama skipped",
    }[failure]
    with pytest.raises(LLMProviderError, match=f"Groq failed; Ollama.*{expected}"):
        await asyncio.wait_for(provider.complete(MESSAGES), timeout=2)
    assert local.call_count == (1 if failure == "missing_model" else 0)


@respx.mock
async def test_tool_history_survives_real_adapter_serialization(local_capacity):
    respx.post(GROQ).respond(429, json={"error": {"message": "quota"}})
    respx.get(f"{OLLAMA}/api/ps").respond(200, json={"models": []})
    local = respx.post(f"{OLLAMA}/api/chat").mock(return_value=local_reply("done"))
    calls = []

    def observe() -> str:
        """Return an observation."""
        calls.append(1)
        return "latency increased"

    tool = StructuredTool.from_function(observe)
    history = [
        HumanMessage(content="Investigate"),
        AIMessage(content="", tool_calls=[{"name": "observe", "args": {}, "id": "observation-1"}]),
        ToolMessage(content=tool.invoke({}), tool_call_id="observation-1", name="observe"),
    ]
    provider = build_llm_provider(Settings(_env_file=None))
    assert (await provider.bind_tools([tool]).ainvoke(history)).content == "done"
    body = json.loads(local.calls[0].request.content)
    assert body["messages"][-1]["role"] == "tool"
    assert body["messages"][-1]["content"] == "latency increased"
    assert body["messages"][-2]["tool_calls"][0]["function"]["name"] == "observe"
    assert calls == [1]
