"""Exercise the adapter through real LangChain/SDK serialization, without a network."""

import json
import socket
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr, ValidationError

from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.openai_provider import OpenAIProvider
from incident_copilot.models.enums import AgentName, EvidenceSource
from incident_copilot.models.report import IncidentReport, RouteDecision
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools
from incident_copilot.utils.exceptions import StructuredOutputError

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
    response_fields: list[dict[str, Any]] = field(default_factory=list)

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
                **(self.response_fields.pop(0) if self.response_fields else {}),
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


@pytest.mark.parametrize("with_text", [False, True])
async def test_structured_refusal_is_terminal_even_with_a_valid_report(
    wire: tuple[OpenAIProvider, Wire], with_text: bool
) -> None:
    provider, exchange = wire
    refusal = text_output(json.dumps(REPORT) if with_text else "")
    refusal[0]["content"].append({"type": "refusal", "refusal": "Synthetic refusal text"})
    exchange.outputs = [refusal, text_output(json.dumps(REPORT))]

    with pytest.raises(StructuredOutputError, match="refus") as caught:
        await provider.complete_structured(MESSAGES, IncidentReport)

    assert "Synthetic refusal text" not in str(caught.value)
    assert_inference_policy(exchange.bodies, 1)  # Never repair a refusal into a report.


@pytest.mark.parametrize("reason", ["max_output_tokens", "content_filter"])
@pytest.mark.parametrize("with_text", [False, True])
async def test_incomplete_response_is_terminal_even_if_its_json_validates(
    wire: tuple[OpenAIProvider, Wire], reason: str, with_text: bool
) -> None:
    provider, exchange = wire
    exchange.outputs = [
        text_output(json.dumps(REPORT) if with_text else '{"summary":'),
        text_output(json.dumps(REPORT)),
    ]
    exchange.response_fields = [{"status": "incomplete", "incomplete_details": {"reason": reason}}]

    with pytest.raises(StructuredOutputError, match="incomplete"):
        await provider.complete_structured(MESSAGES, IncidentReport)

    assert_inference_policy(exchange.bodies, 1)


@pytest.mark.parametrize("status", ["failed", "cancelled", "queued", "in_progress"])
async def test_noncompleted_response_cannot_become_a_report(
    wire: tuple[OpenAIProvider, Wire], status: str
) -> None:
    provider, exchange = wire
    exchange.outputs = [text_output(json.dumps(REPORT))]
    exchange.response_fields = [{"status": status}]

    with pytest.raises(StructuredOutputError, match="not completed"):
        await provider.complete_structured(MESSAGES, IncidentReport)

    assert_inference_policy(exchange.bodies, 1)


@pytest.mark.parametrize(
    "invalid",
    [
        "not json",
        '{"summary":',
        "[" + json.dumps(REPORT) + "]",
        "```json\n" + json.dumps(REPORT) + "\n```",
        json.dumps(REPORT) + " trailing garbage",
        json.dumps(REPORT) + "\n" + json.dumps(REPORT),
        "{}",
        json.dumps({**REPORT, "confidence": -0.1}),
        json.dumps({**REPORT, "likely_causes": [{"title": "Missing rationale/evidence"}]}),
        json.dumps({**REPORT, "investigation_window": {"start": "bad", "end": "bad"}}),
    ],
    ids=[
        "not-json",
        "truncated-json",
        "array-root",
        "fenced-json",
        "trailing-garbage",
        "multiple-objects",
        "missing-fields",
        "confidence-bound",
        "nested-cause",
        "window",
    ],
)
async def test_invalid_report_exhausts_repairs_without_returning_a_report(
    wire: tuple[OpenAIProvider, Wire], invalid: str
) -> None:
    provider, exchange = wire
    exchange.outputs = [text_output(invalid), text_output(invalid)]

    with pytest.raises(StructuredOutputError, match="after 2 attempts") as caught:
        await provider.complete_structured(MESSAGES, IncidentReport, max_attempts=2)

    assert caught.value.raw_output == invalid
    assert_inference_policy(exchange.bodies, 2)
    assert "required schema" in exchange.bodies[1]["input"][-1]["content"]


async def test_malformed_json_repairs_to_a_report_with_validated_nested_evidence(
    wire: tuple[OpenAIProvider, Wire],
) -> None:
    provider, exchange = wire
    report = {
        **REPORT,
        "likely_causes": [
            {
                "title": "Inventory latency",
                "rationale": "Candidate supported by retrieved dependency timeouts.",
                "confidence": 0.8,
                "supporting_evidence": [{"source": "logs", "detail": "café → inventory timeout"}],
            }
        ],
    }
    exchange.outputs = [text_output('{"summary":'), text_output(json.dumps(report))]

    result = await provider.complete_structured(MESSAGES, IncidentReport, max_attempts=2)

    assert result.investigation_window is None  # The service supplies the authoritative window.
    cause = result.likely_causes[0]
    assert cause.confidence == 0.8
    assert cause.supporting_evidence[0].source == EvidenceSource.LOGS
    assert cause.supporting_evidence[0].detail == "café → inventory timeout"
    assert_inference_policy(exchange.bodies, 2)


@pytest.mark.parametrize(
    "invalid",
    [
        {"agents": [], "reasoning": "No specialist"},
        {"agents": ["unknown"], "reasoning": "Invalid vocabulary"},
        {"agents": ["logs_agent"]},
    ],
)
async def test_route_schema_is_validated_and_repaired(
    wire: tuple[OpenAIProvider, Wire], invalid: dict[str, Any]
) -> None:
    provider, exchange = wire
    exchange.outputs = [
        text_output(json.dumps(invalid)),
        text_output('{"agents":["logs_agent","metrics_agent"],"reasoning":"Inspect both"}'),
    ]

    result = await provider.complete_structured(MESSAGES, RouteDecision, max_attempts=2)

    assert result.agents == (AgentName.LOGS, AgentName.METRICS)
    assert result.reasoning == "Inspect both"
    assert_inference_policy(exchange.bodies, 2)
    assert "RouteDecision" in exchange.bodies[1]["input"][-1]["content"]


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


async def test_application_tool_schemas_preserve_optional_defaults_and_validation(
    wire: tuple[OpenAIProvider, Wire],
) -> None:
    provider, exchange = wire
    metrics = AsyncMock(spec=MetricsSource)
    logs = AsyncMock(spec=LogSource)
    tools = [*build_metrics_tools(metrics), *build_log_tools(logs)]
    exchange.outputs = [text_output("No tools needed.")]

    await provider.bind_tools(tools).ainvoke([HumanMessage(content="Inspect checkout")])

    assert_inference_policy(exchange.bodies, 1)
    schemas = {tool["name"]: tool for tool in exchange.bodies[0]["tools"]}
    assert set(schemas) == {
        "get_service_metric",
        "raw_promql_query",
        "list_services",
        "search_logs",
        "log_level_histogram",
    }
    for schema in schemas.values():
        assert schema["type"] == "function"
        assert schema["description"]
        # Responses may normalize omitted strictness and make optional fields required.
        assert schema.get("strict") is False
        assert "function" not in schema
        assert "$defs" not in schema["parameters"]
        assert "config" not in schema["parameters"]["properties"]
    required = {
        "get_service_metric": ["service", "kind"],
        "raw_promql_query": ["query"],
        "list_services": [],
        "search_logs": ["service"],
        "log_level_histogram": ["service"],
    }
    for name, fields in required.items():
        parameters = schemas[name]["parameters"]
        assert parameters.get("required", []) == fields
        if name == "list_services":
            assert parameters["properties"] == {}
            continue
        window = parameters["properties"]["minutes_back"]
        assert window["type"] == "integer"
        assert window["default"] == 60
        assert window["minimum"] == 1
        assert window["maximum"] == 1440
    assert schemas["get_service_metric"]["parameters"]["properties"]["kind"]["enum"] == [
        "latency_p95",
        "error_rate",
        "memory",
        "cpu",
    ]
    filters = schemas["search_logs"]["parameters"]["properties"]
    assert filters["level"]["default"] is None
    severity, nullable = filters["level"]["anyOf"]
    assert severity["type"] == "string"
    assert severity["enum"] == ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
    assert nullable == {"type": "null"}
    assert filters["keyword"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
    assert filters["keyword"]["default"] is None


@pytest.mark.parametrize(
    "arguments",
    [
        {"service": "checkout", "kind": "raw"},
        {"service": "checkout", "kind": "cpu", "minutes_back": 0},
        {"service": "checkout", "kind": "cpu", "minutes_back": 1441},
        {"kind": "cpu"},
    ],
)
async def test_serialized_tool_arguments_still_require_local_validation(
    wire: tuple[OpenAIProvider, Wire],
    arguments: dict[str, Any],
) -> None:
    provider, exchange = wire
    metrics = AsyncMock(spec=MetricsSource)
    tool = build_metrics_tools(metrics)[0]
    exchange.outputs = [[function_call("metric_bad", tool.name, arguments)]]

    reply = await provider.bind_tools([tool]).ainvoke([HumanMessage(content="Inspect checkout")])

    assert isinstance(reply, AIMessage)
    assert reply.tool_calls[0]["args"] == arguments
    with pytest.raises(ValidationError):
        await tool.ainvoke(reply.tool_calls[0])
    metrics.query_range.assert_not_awaited()


def function_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function_call",
        "id": f"fc_{call_id}",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(arguments, ensure_ascii=False),
        "status": "completed",
    }


async def test_multiple_calls_and_content_blocks_survive_every_continuation(
    wire: tuple[OpenAIProvider, Wire],
) -> None:
    provider, exchange = wire

    async def lookup(service: str) -> str:
        return f"{service}: timeout calling inventory"

    async def histogram(service: str) -> list[dict[str, str]]:
        return [{"type": "text", "text": f"{service}: ERROR=2"}]

    lookup_tool = StructuredTool.from_function(
        coroutine=lookup, name="lookup_logs", description="Read logs."
    )
    histogram_tool = StructuredTool.from_function(
        coroutine=histogram, name="histogram", description="Count logs."
    )
    reasoning = {
        "type": "reasoning",
        "id": "rs_offline",
        "summary": [
            {"type": "summary_text", "text": "Inspect both services."},
        ],
    }
    first_text = text_output("Checking checkout and café.")
    first_calls = [
        function_call("logs_1", "lookup_logs", {"service": "checkout"}),
        function_call("logs_2", "lookup_logs", {"service": "café"}),
    ]
    second_call = function_call("hist_1", "histogram", {"service": "inventory"})
    exchange.outputs = [
        [reasoning, *first_text, *first_calls],
        [second_call],
        text_output("Inventory needs investigation."),
    ]
    runnable = provider.bind_tools([lookup_tool, histogram_tool])
    history: list[BaseMessage] = [HumanMessage(content="Inspect checkout and café")]

    reply = await runnable.ainvoke(history)
    assert isinstance(reply, AIMessage)
    assert reply.text == "Checking checkout and café."
    assert reply.tool_calls == [
        {
            "type": "tool_call",
            "id": "logs_1",
            "name": "lookup_logs",
            "args": {"service": "checkout"},
        },
        {"type": "tool_call", "id": "logs_2", "name": "lookup_logs", "args": {"service": "café"}},
    ]
    assert isinstance(reply.content, list)
    assert reply.content[0] == reasoning
    # Return same-name calls in reverse order: results must correlate by ID.
    history.extend(
        [
            reply,
            await lookup_tool.ainvoke(reply.tool_calls[1]),
            await lookup_tool.ainvoke(reply.tool_calls[0]),
        ]
    )
    second = await runnable.ainvoke(history)
    assert isinstance(second, AIMessage)
    assert second.text == ""
    assert second.tool_calls == [
        {
            "type": "tool_call",
            "id": "hist_1",
            "name": "histogram",
            "args": {"service": "inventory"},
        },
    ]
    history.extend([second, await histogram_tool.ainvoke(second.tool_calls[0])])
    final = await runnable.ainvoke(history)
    assert final.text == "Inventory needs investigation."
    assert_inference_policy(exchange.bodies, 3)
    continuation = exchange.bodies[1]["input"]
    assert continuation == [
        {"type": "message", "role": "user", "content": "Inspect checkout and café"},
        reasoning,
        {
            "type": "message",
            "role": "assistant",
            "id": "msg_offline",
            "content": first_text[0]["content"],
        },
        *first_calls,
        {
            "type": "function_call_output",
            "call_id": "logs_2",
            "output": "café: timeout calling inventory",
        },
        {
            "type": "function_call_output",
            "call_id": "logs_1",
            "output": "checkout: timeout calling inventory",
        },
    ]
    assert exchange.bodies[2]["input"] == [
        *continuation,
        second_call,
        {
            "type": "function_call_output",
            "call_id": "hist_1",
            "output": [{"type": "input_text", "text": "inventory: ERROR=2"}],
        },
    ]
    for body in exchange.bodies:
        assert [tool["name"] for tool in body["tools"]] == ["lookup_logs", "histogram"]


async def test_text_completion_normalizes_multiple_blocks_without_reasoning(
    wire: tuple[OpenAIProvider, Wire],
) -> None:
    provider, exchange = wire
    output = text_output("Checkout: ")
    output[0]["content"].append(
        {"type": "output_text", "text": "café → inventory.", "annotations": []}
    )
    exchange.outputs = [
        [
            {
                "type": "reasoning",
                "id": "rs_text",
                "summary": [
                    {"type": "summary_text", "text": "Internal summary."},
                ],
            },
            *output,
        ]
    ]

    assert await provider.complete(MESSAGES) == "Checkout: café → inventory."


async def test_malformed_tool_json_retains_its_call_id_and_raw_arguments(
    wire: tuple[OpenAIProvider, Wire],
) -> None:
    provider, exchange = wire
    tool = build_metrics_tools(AsyncMock(spec=MetricsSource))[0]
    invalid = function_call("bad_json", tool.name, {})
    invalid["arguments"] = '{"service":'
    exchange.outputs = [
        [
            invalid,
            function_call("valid_json", tool.name, {"service": "checkout", "kind": "cpu"}),
        ]
    ]

    reply = await provider.bind_tools([tool]).ainvoke([HumanMessage(content="Inspect checkout")])

    assert isinstance(reply, AIMessage)
    assert reply.tool_calls == [
        {
            "type": "tool_call",
            "id": "valid_json",
            "name": "get_service_metric",
            "args": {"service": "checkout", "kind": "cpu"},
        }
    ]
    assert len(reply.invalid_tool_calls) == 1
    rejected = reply.invalid_tool_calls[0]
    assert rejected["id"] == "bad_json"
    assert rejected["name"] == "get_service_metric"
    assert rejected["args"] == '{"service":'
    assert rejected["error"]
    assert isinstance(reply.content, list)
    assert reply.content[0] == invalid
    assert len(exchange.bodies) == 1  # No silent repair request or discarded call.
