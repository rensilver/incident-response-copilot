"""Exercise the adapter through real LangChain/SDK serialization, without a network."""

import json
import socket
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
import respx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.openai_provider import OpenAIProvider
from incident_copilot.models.report import IncidentReport

REPORT = {
    "summary": "Checkout has dependency timeouts.",
    "likely_causes": [],
    "next_steps": ["Inspect inventory latency."],
    "confidence": 0.7,
}
MESSAGES = [ChatMessage(role="user", content="Investigate checkout.")]


def text_output(text: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "message",
            "id": "msg_offline",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }
    ]


@dataclass
class Wire:
    outputs: list[list[dict[str, Any]]] = field(default_factory=list)
    bodies: list[dict[str, Any]] = field(default_factory=list)

    def respond(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/responses"
        self.bodies.append(json.loads(request.content))
        assert self.outputs, "Unexpected extra inference request"
        return httpx.Response(
            200,
            json={
                "id": f"resp_offline_{len(self.bodies)}",
                "object": "response",
                "created_at": 0,
                "model": "gpt-6-luna",
                "status": "completed",
                "error": None,
                "incomplete_details": None,
                "output": self.outputs.pop(0),
                "parallel_tool_calls": True,
                "tool_choice": "auto",
                "tools": [],
                "usage": {
                    "input_tokens": 20,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens": 5,
                    "output_tokens_details": {"reasoning_tokens": 0},
                    "total_tokens": 25,
                },
            },
        )


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("OpenAI adapter unit tests must never access the network")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)


@pytest.fixture
async def wire(respx_mock: respx.MockRouter) -> AsyncIterator[tuple[OpenAIProvider, Wire]]:
    exchange = Wire()
    respx_mock.post("https://api.openai.com/v1/responses").mock(side_effect=exchange.respond)
    provider = OpenAIProvider.from_api_key(SecretStr("offline-key"))
    assert exchange.bodies == []  # Construction must not make a model request.
    try:
        yield provider, exchange
    finally:
        await provider.aclose()


def assert_inference_policy(bodies: list[dict[str, Any]], count: int) -> None:
    assert len(bodies) == count
    for body in bodies:
        assert body["model"] == "gpt-6-luna"
        assert body["reasoning"] == {"effort": "none"}
        assert "messages" not in body  # Responses input, never Chat Completions.
        assert "previous_response_id" not in body  # Send the complete local history.


async def test_text_uses_responses_and_the_explicit_inference_policy(
    wire: tuple[OpenAIProvider, Wire],
) -> None:
    provider, exchange = wire
    exchange.outputs = [text_output("Checkout needs investigation.")]

    assert await provider.complete(MESSAGES) == "Checkout needs investigation."
    assert_inference_policy(exchange.bodies, 1)
    assert exchange.bodies[0]["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": "Investigate checkout.",
        }
    ]
    assert "text" not in exchange.bodies[0]


async def test_structured_generation_and_repairs_keep_json_mode_and_policy(
    wire: tuple[OpenAIProvider, Wire],
) -> None:
    provider, exchange = wire
    invalid = json.dumps({**REPORT, "confidence": 2.0})
    exchange.outputs = [text_output(invalid), text_output(json.dumps(REPORT))]

    report = await provider.complete_structured(MESSAGES, IncidentReport, max_attempts=2)

    assert report.summary == "Checkout has dependency timeouts."
    assert report.confidence == 0.7
    assert report.next_steps == ("Inspect inventory latency.",)
    assert_inference_policy(exchange.bodies, 2)
    for body in exchange.bodies:
        assert body["text"]["format"] == {"type": "json_object"}
        assert any(
            message.get("role") == "system" and "json" in message["content"].lower()
            for message in body["input"]
        )  # JSON mode requires an explicit JSON instruction, even on the first call.
    repaired = exchange.bodies[1]["input"]
    assert repaired[0] == exchange.bodies[0]["input"][0]
    assert repaired[-2]["role"] == "assistant"
    assert repaired[-2]["content"] == [{"type": "output_text", "text": invalid, "annotations": []}]
    assert repaired[-1]["role"] == "user"
    assert "confidence" in repaired[-1]["content"]
    assert "IncidentReport" in repaired[-1]["content"]


async def test_tool_round_and_continuation_keep_policy_and_call_results(
    wire: tuple[OpenAIProvider, Wire],
) -> None:
    provider, exchange = wire

    async def lookup(service: str) -> str:
        return f"{service}: timeout calling inventory"

    tool = StructuredTool.from_function(
        coroutine=lookup, name="lookup_logs", description="Read service logs."
    )
    exchange.outputs = [
        [
            {
                "type": "function_call",
                "id": "fc_offline",
                "call_id": "call_logs_1",
                "name": "lookup_logs",
                "arguments": '{"service":"checkout"}',
                "status": "completed",
            }
        ],
        text_output("Inspect inventory after the checkout timeout."),
    ]
    runnable = provider.bind_tools([tool])
    opening = HumanMessage(content="Inspect checkout logs")
    reply = await runnable.ainvoke([opening])
    assert isinstance(reply, AIMessage)
    assert reply.tool_calls == [
        {
            "type": "tool_call",
            "name": "lookup_logs",
            "args": {"service": "checkout"},
            "id": "call_logs_1",
        }
    ]
    history: list[BaseMessage] = [
        opening,
        reply,
        await tool.ainvoke(reply.tool_calls[0]),
    ]
    assert isinstance(history[-1], ToolMessage)
    assert (await runnable.ainvoke(history)).text == (
        "Inspect inventory after the checkout timeout."
    )
    assert_inference_policy(exchange.bodies, 2)
    for body in exchange.bodies:
        assert body["tools"][0]["type"] == "function"
        assert body["tools"][0]["name"] == "lookup_logs"
        assert "text" not in body
    continuation = exchange.bodies[1]["input"]
    assert continuation[0] == {
        "type": "message",
        "role": "user",
        "content": "Inspect checkout logs",
    }
    assert continuation[1]["type"] == "function_call"
    assert continuation[1]["call_id"] == "call_logs_1"
    assert json.loads(continuation[1]["arguments"]) == {"service": "checkout"}
    assert continuation[2] == {
        "type": "function_call_output",
        "call_id": "call_logs_1",
        "output": "checkout: timeout calling inventory",
    }


async def test_owned_clients_close_without_closing_another_provider(
    respx_mock: respx.MockRouter,
) -> None:
    exchange = Wire(outputs=[text_output("second provider remains usable")])
    respx_mock.post("https://api.openai.com/v1/responses").mock(side_effect=exchange.respond)
    first = OpenAIProvider.from_api_key(SecretStr("offline-key"))
    second = OpenAIProvider.from_api_key(SecretStr("offline-key"))
    try:
        await first.aclose()
        await first.aclose()
        assert await second.complete(MESSAGES) == "second provider remains usable"
    finally:
        await first.aclose()
        await second.aclose()


async def test_cleanup_closes_both_owned_sdk_clients(
    wire: tuple[OpenAIProvider, Wire],
) -> None:
    provider, _ = wire
    assert isinstance(provider._chat, ChatOpenAI)
    sync_client = provider._chat.root_client
    async_client = provider._chat.root_async_client
    assert not sync_client.is_closed()
    assert not async_client.is_closed()

    await provider.aclose()

    assert sync_client.is_closed()
    assert async_client.is_closed()


async def test_borrowed_chat_remains_usable_after_adapter_cleanup(
    wire: tuple[OpenAIProvider, Wire],
) -> None:
    owner, exchange = wire
    # The owner is the only provider responsible for these SDK clients.
    borrowed = OpenAIProvider(owner._chat)
    await borrowed.aclose()
    exchange.outputs = [text_output("caller retains its client")]
    assert await owner.complete(MESSAGES) == "caller retains its client"
