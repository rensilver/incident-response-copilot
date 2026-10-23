"""Exercise the adapter through real LangChain/SDK serialization, without a network."""

import asyncio
import json
import logging
import socket
import traceback
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from fastapi import FastAPI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr, ValidationError

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.state import initial_state
from incident_copilot.agents.tool_loop import run_tool_rounds
from incident_copilot.api.routes import build_router
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.openai_provider import OpenAIProvider
from incident_copilot.models.enums import AgentName, EvidenceSource
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.models.report import IncidentReport, RouteDecision
from incident_copilot.services.incident_service import IncidentService
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools
from incident_copilot.utils.exceptions import LLMProviderError, StructuredOutputError
from incident_copilot.utils.logging import configure_logging, get_logger

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
        assert body["max_output_tokens"] == 4096
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


@pytest.mark.parametrize("rejection", ["unknown", "malformed-only", "malformed-mixed", "schema"])
async def test_tool_loop_answers_rejected_calls_and_recovers_with_complete_history(
    wire: tuple[OpenAIProvider, Wire], rejection: str
) -> None:
    """Rejected calls need outputs too; otherwise the next Responses request is invalid."""
    provider, exchange = wire
    metrics = AsyncMock(spec=MetricsSource)
    metrics.query_range.return_value = []
    tools = build_metrics_tools(metrics)
    args = {"service": "checkout", "kind": "error_rate"}
    rejected = function_call("rejected", "get_service_metric", args)
    if rejection == "unknown":
        rejected["name"] = "unavailable_tool"
    elif rejection.startswith("malformed"):
        rejected["arguments"] = '{"service":'
    else:
        rejected["arguments"] = json.dumps({**args, "kind": "bogus"})
    first_round = [rejected]
    if rejection != "malformed-only":
        first_round.append(function_call("valid", "get_service_metric", args))
    exchange.outputs = [
        first_round,
        [function_call("recovered", "get_service_metric", args)],
        text_output("must not request a third round"),
    ]

    outcome = await run_tool_rounds(provider, tools, MESSAGES, max_rounds=2)

    assert len(outcome.errors) == 1
    expected_error = (
        "malformed"
        if rejection.startswith("malformed")
        else "failed" if rejection == "schema" else "unknown"
    )
    assert expected_error in outcome.errors[0]
    expected_results = 1 if rejection == "malformed-only" else 2
    assert len(outcome.results) == expected_results
    assert metrics.query_range.await_count == expected_results
    assert_inference_policy(exchange.bodies, 2)
    history = exchange.bodies[1]["input"]
    requests = [item for item in history if item["type"] == "function_call"]
    outputs = [item for item in history if item["type"] == "function_call_output"]
    assert {item["call_id"] for item in requests} == {item["call_id"] for item in outputs}
    assert len(outputs) == len(first_round)
    feedback = next(item["output"] for item in outputs if item["call_id"] == "rejected")
    assert ("validation error" if rejection == "schema" else expected_error) in feedback


type Operation = Literal["text", "structured", "tools"]


async def invoke_operation(provider: OpenAIProvider, operation: Operation) -> object:
    if operation == "text":
        return await provider.complete(MESSAGES)
    if operation == "structured":
        return await provider.complete_structured(MESSAGES, IncidentReport, max_attempts=100)
    return await provider.bind_tools([]).ainvoke([HumanMessage(content="Inspect checkout")])


@pytest.mark.parametrize("operation", ["text", "structured", "tools"])
async def test_deadline_cancels_inflight_http_without_retry(
    respx_mock: respx.MockRouter, operation: Operation
) -> None:
    cancelled = asyncio.Event()
    calls = 0

    async def blocked(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        raise AssertionError("Unreachable")

    respx_mock.post("https://api.openai.com/v1/responses").mock(side_effect=blocked)
    provider = OpenAIProvider.from_settings(
        Settings(_env_file=None, llm_operation_timeout_seconds=0.1)
    )
    try:
        with pytest.raises(LLMProviderError, match="timeout") as caught:
            await asyncio.wait_for(invoke_operation(provider, operation), timeout=1)
        assert getattr(caught.value, "kind", None) == "timeout"
        assert cancelled.is_set()
        assert calls == 1
    finally:
        await provider.aclose()


async def test_structured_repairs_share_one_deadline(respx_mock: respx.MockRouter) -> None:
    exchange = Wire(outputs=[text_output("invalid"), text_output(json.dumps(REPORT))])
    cancelled = asyncio.Event()
    calls = 0

    async def delayed(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        try:
            await asyncio.sleep(0.4)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return exchange.respond(request)

    respx_mock.post("https://api.openai.com/v1/responses").mock(side_effect=delayed)
    provider = OpenAIProvider.from_settings(
        Settings(_env_file=None, llm_operation_timeout_seconds=0.6)
    )
    try:
        with pytest.raises(LLMProviderError, match="timeout") as caught:
            await asyncio.wait_for(
                provider.complete_structured(MESSAGES, IncidentReport), timeout=2
            )
        assert getattr(caught.value, "kind", None) == "timeout"
        assert calls == 2  # First invalid response was repaired, second request was cancelled.
        assert cancelled.is_set()
    finally:
        await provider.aclose()


async def test_cancellation_during_repair_reaches_http(respx_mock: respx.MockRouter) -> None:
    exchange = Wire(outputs=[text_output("invalid")])
    repair_started = asyncio.Event()
    cancelled = asyncio.Event()
    calls = 0

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if not exchange.bodies:
            return exchange.respond(request)
        repair_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        raise AssertionError("Unreachable")

    respx_mock.post("https://api.openai.com/v1/responses").mock(side_effect=respond)
    provider = OpenAIProvider.from_settings(Settings(_env_file=None))
    task = asyncio.create_task(provider.complete_structured(MESSAGES, IncidentReport))
    try:
        await asyncio.wait_for(repair_started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)
        assert cancelled.is_set()
        assert calls == 2
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await provider.aclose()


@pytest.mark.parametrize("operation", ["text", "structured", "tools"])
@pytest.mark.parametrize(
    "status, upstream_code, kind",
    [
        (400, "invalid_request", "invalid_request"),
        (401, "invalid_api_key", "authentication"),
        (403, "access_denied", "authentication"),
        (404, "model_not_found", "invalid_request"),
        (408, "request_timeout", "timeout"),
        (409, "conflict", "service"),
        (422, "invalid_schema", "invalid_request"),
        (429, "rate_limit_exceeded", "rate_limit"),
        (429, "insufficient_quota", "quota"),
        (429, "billing_hard_limit_reached", "quota"),
        (429, "unknown_future_code", "rate_limit"),
        (500, "server_error", "service"),
        (502, "server_error", "service"),
        (503, "server_is_overloaded", "service"),
    ],
)
async def test_http_failures_never_retry_even_with_server_retry_headers(
    respx_mock: respx.MockRouter, operation: Operation, status: int, upstream_code: str, kind: str
) -> None:
    route = respx_mock.post("https://api.openai.com/v1/responses").respond(
        status,
        json={
            "error": {
                "message": "private-upstream-canary",
                "code": upstream_code,
                "type": "invalid_request_error",
            }
        },
        headers={"Retry-After": "0", "x-should-retry": "true"},
    )
    provider = OpenAIProvider.from_settings(Settings(_env_file=None))
    try:
        with pytest.raises(LLMProviderError) as caught:
            await invoke_operation(provider, operation)
        assert getattr(caught.value, "kind", None) == kind
        assert "private-upstream-canary" not in str(caught.value)
        assert "private-upstream-canary" not in repr(caught.value)
        assert "private-upstream-canary" not in "".join(traceback.format_exception(caught.value))
        assert caught.value.__context__ is None
        assert caught.value.__cause__ is None
        assert route.call_count == 1
    finally:
        await provider.aclose()


@pytest.mark.parametrize("operation", ["text", "structured", "tools"])
@pytest.mark.parametrize(
    "failure, kind", [(httpx.ConnectError, "connection"), (httpx.ReadTimeout, "timeout")]
)
async def test_transport_failures_never_retry(
    respx_mock: respx.MockRouter,
    operation: Operation,
    failure: type[httpx.TransportError],
    kind: str,
) -> None:
    route = respx_mock.post("https://api.openai.com/v1/responses").mock(
        side_effect=failure("Synthetic transport failure")
    )
    provider = OpenAIProvider.from_settings(Settings(_env_file=None))
    try:
        with pytest.raises(LLMProviderError) as caught:
            await invoke_operation(provider, operation)
        assert getattr(caught.value, "kind", None) == kind
        assert "Synthetic transport failure" not in "".join(
            traceback.format_exception(caught.value)
        )
        assert route.call_count == 1
    finally:
        await provider.aclose()


@pytest.mark.parametrize("operation", ["text", "structured", "tools"])
async def test_response_error_payload_is_a_safe_service_failure(
    wire: tuple[OpenAIProvider, Wire], operation: Operation
) -> None:
    provider, exchange = wire
    exchange.outputs = [text_output(json.dumps(REPORT))]
    exchange.response_fields = [
        {
            "status": "failed",
            "error": {"code": "server_error", "message": "private-response-error-canary"},
        }
    ]
    with pytest.raises(LLMProviderError) as caught:
        await invoke_operation(provider, operation)
    assert getattr(caught.value, "kind", None) == "service"
    assert "private-response-error-canary" not in "".join(traceback.format_exception(caught.value))
    assert len(exchange.bodies) == 1


@pytest.mark.parametrize("operation", ["text", "structured", "tools"])
@pytest.mark.parametrize(
    "failure, kind",
    [
        pytest.param(
            httpx.Response(401, json={"error": {"message": "private-recovery-canary"}}),
            "authentication",
            id="authentication",
        ),
        pytest.param(
            httpx.Response(
                429,
                json={
                    "error": {"message": "private-recovery-canary", "code": "insufficient_quota"}
                },
            ),
            "quota",
            id="quota",
        ),
        pytest.param(
            httpx.Response(
                429,
                json={
                    "error": {"message": "private-recovery-canary", "code": "rate_limit_exceeded"}
                },
            ),
            "rate_limit",
            id="rate-limit",
        ),
        pytest.param(
            httpx.Response(503, json={"error": {"message": "private-recovery-canary"}}),
            "service",
            id="service",
        ),
        pytest.param(httpx.ConnectError("private-recovery-canary"), "connection", id="connection"),
        pytest.param(httpx.ReadTimeout("private-recovery-canary"), "timeout", id="timeout"),
    ],
)
async def test_failed_operation_recovers_on_same_provider_without_hidden_retry(
    respx_mock: respx.MockRouter,
    operation: Operation,
    failure: httpx.Response | httpx.HTTPError,
    kind: str,
) -> None:
    exchange = Wire(outputs=[text_output(json.dumps(REPORT))])
    route = respx_mock.post("https://api.openai.com/v1/responses")
    if isinstance(failure, httpx.Response):
        route.mock(return_value=failure)
    else:
        route.mock(side_effect=failure)
    provider = OpenAIProvider.from_settings(Settings(_env_file=None))
    try:
        with pytest.raises(LLMProviderError) as caught:
            await invoke_operation(provider, operation)
        assert getattr(caught.value, "kind", None) == kind
        assert "private-recovery-canary" not in "".join(traceback.format_exception(caught.value))
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert route.call_count == len(respx_mock.calls) == 1

        route.mock(side_effect=exchange.respond)
        result = await invoke_operation(provider, operation)
        if operation == "structured":
            assert isinstance(result, IncidentReport)
            assert result.summary == REPORT["summary"]
        elif operation == "text":
            assert result == json.dumps(REPORT)
        else:
            assert isinstance(result, BaseMessage)
            assert result.text == json.dumps(REPORT)
        assert route.call_count == len(respx_mock.calls) == 2
        assert_inference_policy([json.loads(call.request.content) for call in route.calls], 2)
    finally:
        await provider.aclose()


async def test_http_failure_during_repair_stops_without_another_attempt(
    respx_mock: respx.MockRouter,
) -> None:
    exchange = Wire(outputs=[text_output("invalid")])

    def respond(request: httpx.Request) -> httpx.Response:
        if not exchange.bodies:
            return exchange.respond(request)
        return httpx.Response(503, json={"error": {"message": "private-repair-canary"}})

    route = respx_mock.post("https://api.openai.com/v1/responses").mock(side_effect=respond)
    provider = OpenAIProvider.from_settings(Settings(_env_file=None))
    try:
        with pytest.raises(LLMProviderError) as caught:
            await provider.complete_structured(MESSAGES, IncidentReport)
        assert getattr(caught.value, "kind", None) == "service"
        assert "private-repair-canary" not in "".join(traceback.format_exception(caught.value))
        assert route.call_count == 2
    finally:
        await provider.aclose()


@pytest.mark.parametrize("status", [401, 429, 503])
async def test_provider_failure_reaches_api_as_safe_503_then_recovers(
    respx_mock: respx.MockRouter,
    status: int,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    configure_logging("DEBUG")
    route = respx_mock.post("https://api.openai.com/v1/responses").respond(
        status, json={"error": {"message": "private-graph-error-canary"}}
    )
    settings = Settings(_env_file=None)
    provider = OpenAIProvider.from_settings(settings)
    graph = build_graph(provider, [], [], settings)
    app = FastAPI()
    app.include_router(build_router(IncidentService(graph), {}))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/investigations", json={"query": "initial-only question"}
            )
            assert response.status_code == 503
            assert response.json() == {
                "detail": "Investigation unavailable; no usable report was produced."
            }
            # Four distinct graph operations: supervisor, two specialists, correlation.
            # No validation repairs, transport retries, or other provider requests.
            assert route.call_count == len(respx_mock.calls) == 4

            exchange = Wire(
                outputs=[
                    text_output(
                        json.dumps({"agents": [AgentName.METRICS], "reasoning": "Inspect metrics."})
                    ),
                    text_output("No metric evidence retrieved."),
                    text_output(json.dumps(REPORT)),
                ]
            )
            route.mock(side_effect=exchange.respond)
            recovered = await client.post(
                "/api/v1/investigations",
                json={"query": "recovery-only question", "minutes_back": 17},
            )
            assert recovered.status_code == 200
            body = recovered.json()
            assert body["summary"] == REPORT["summary"]
            assert body["likely_causes"] == []
            assert body["investigation_window"]
            assert len(respx_mock.calls) == 7
            assert_inference_policy(exchange.bodies, 3)
            history = json.dumps(exchange.bodies)
            assert "recovery-only question" in history
            assert "initial-only question" not in history
            assert "routing fallback" not in history
        get_logger(__name__).debug("application_debug_remains_enabled")
        captured = capsys.readouterr()
        logs = captured.out + captured.err + caplog.text
        assert "application_debug_remains_enabled" in logs
        assert "private-graph-error-canary" not in logs
    finally:
        await provider.aclose()


@pytest.mark.parametrize("ceiling, requested", [(2, 100), (3, 1)])
async def test_repair_attempts_respect_provider_and_caller_caps(
    respx_mock: respx.MockRouter, ceiling: int, requested: int
) -> None:
    exchange = Wire(outputs=[text_output("invalid")] * 100)
    respx_mock.post("https://api.openai.com/v1/responses").mock(side_effect=exchange.respond)
    provider = OpenAIProvider.from_settings(
        Settings(_env_file=None, llm_max_structured_attempts=ceiling, llm_max_output_tokens=1234)
    )
    count = min(ceiling, requested)
    try:
        with pytest.raises(StructuredOutputError, match=f"after {count} attempts"):
            await provider.complete_structured(MESSAGES, IncidentReport, max_attempts=requested)
        assert len(exchange.bodies) == count
        assert all(body["max_output_tokens"] == 1234 for body in exchange.bodies)
        for client in provider._owned_clients or ():
            assert client.max_retries == 0
            assert client.timeout == 60.0
    finally:
        await provider.aclose()


async def test_graph_call_budget_has_no_node_retry_multiplier(respx_mock: respx.MockRouter) -> None:
    bodies: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        # Repeat a tool request to exercise the specialist round ceilings. Unknown
        # tools are recorded by the existing graph without any connector I/O.
        output = (
            [
                {
                    "type": "function_call",
                    "id": f"fc_{len(bodies)}",
                    "call_id": f"call_{len(bodies)}",
                    "name": "unknown_offline_tool",
                    "arguments": "{}",
                    "status": "completed",
                }
            ]
            if "tools" in body
            else text_output("invalid")
        )
        return Wire(outputs=[output]).respond(request)

    respx_mock.post("https://api.openai.com/v1/responses").mock(side_effect=respond)
    settings = Settings(_env_file=None)
    provider = OpenAIProvider.from_settings(settings)

    async def unused() -> str:
        """Return an offline placeholder."""
        return "unused"

    tool = StructuredTool.from_function(coroutine=unused)
    try:
        graph = build_graph(provider, [tool], [tool], settings)
        final = await graph.ainvoke(
            initial_state(
                correlation_id="offline-budget",
                query="Investigate checkout",
                time_window=TimeWindow.from_minutes_back(60),
                target_service="checkout",
            )
        )
        assert final["report"] is None
        assert final["iterations"] == 1
        assert len(bodies) == 9  # Supervisor 2 + two specialists * 2 + correlation 3.
        assert sum("tools" in body for body in bodies) == 4
        assert all(body["max_output_tokens"] == 4096 for body in bodies)
    finally:
        await provider.aclose()
