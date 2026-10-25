"""Server-owned intervals survive model spoofing, repeated tools, and serialization."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from elasticsearch import AsyncElasticsearch
from pydantic import ValidationError
from pytest_mock import MockerFixture

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.tool_loop import run_tool_rounds
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools
from incident_copilot.tools.window import INVESTIGATION_WINDOW_KEY

END = datetime(2026, 10, 23, 14, 31, 27, 123456, tzinfo=UTC)
SPOOFED_WINDOW = {"start": "2001-01-01T00:00:00Z", "end": "2001-01-02T00:00:00Z"}
DEFINITIONS = (
    ("get_service_metric", {"service": "cart-service", "kind": "error_rate"}),
    ("raw_promql_query", {"query": "up"}),
    ("search_logs", {"service": "cart-service"}),
    ("log_level_histogram", {"service": "cart-service"}),
)


def _call(name: str, args: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return {
        "name": name,
        "id": f"{name}-{index}",
        "type": "tool_call",
        "args": {
            **args,
            "minutes_back": 60 if index == 0 else 1440,
            "config": {"configurable": {INVESTIGATION_WINDOW_KEY: SPOOFED_WINDOW}},
            "configurable": {INVESTIGATION_WINDOW_KEY: SPOOFED_WINDOW},
            INVESTIGATION_WINDOW_KEY: SPOOFED_WINDOW,
            "time_window": SPOOFED_WINDOW,
            **SPOOFED_WINDOW,
        },
    }


def _logs_client() -> AsyncMock:
    client = AsyncMock(spec=AsyncElasticsearch)
    # SDK decorators hide the coroutine from Python 3.12's spec introspection.
    client.search = AsyncMock(
        return_value={
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {"levels": {"buckets": []}},
        }
    )
    return client


@pytest.mark.parametrize("minutes", [1, 17, 1440])
@pytest.mark.parametrize("model_window", [None, SPOOFED_WINDOW], ids=["absent", "spoofed"])
async def test_service_window_matches_all_outgoing_queries_and_report_metadata(
    minutes: int, model_window: dict[str, str] | None, mocker: MockerFixture
) -> None:
    # Advancing the clock exposes accidental per-tool recomputation of the window.
    clock = mocker.patch("incident_copilot.models.metrics.datetime", wraps=datetime)
    clock.now.side_effect = [END + timedelta(hours=index) for index in range(20)]
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    logs_client = _logs_client()
    provider = FakeLLMProvider(
        [
            '{"agents": ["metrics_agent", "logs_agent"], "reasoning": "both"}',
            json.dumps(
                {
                    "summary": "No observations",
                    "likely_causes": [],
                    "next_steps": [],
                    "confidence": 0,
                    "investigation_window": model_window,
                }
            ),
        ],
        tool_rounds=[
            [_call(name, args, index) for name, args in DEFINITIONS[offset : offset + 2]]
            for offset in (0, 2)
            for index in range(2)
        ],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        graph = build_graph(
            provider,
            build_metrics_tools(PrometheusConnector(client, "http://metrics.test")),
            build_log_tools(ElasticsearchConnector(logs_client, "test-logs")),
            Settings(_env_file=None, max_tool_rounds=2),
        )
        report = await IncidentService(graph).investigate(
            InvestigationRequest(query="cart errors", minutes_back=minutes)
        )

    start = END - timedelta(minutes=minutes)
    assert len(requests) == 4
    assert {request.url.params["query"] for request in requests} == {
        'sum(rate(http_requests_total{service="cart-service",status=~"5.."}[5m])) / '
        'sum(rate(http_requests_total{service="cart-service"}[5m]))',
        "up",
    }
    for request in requests:
        assert request.url.path == "/api/v1/query_range"
        assert float(request.url.params["start"]) == start.timestamp()
        assert float(request.url.params["end"]) == END.timestamp()
    assert logs_client.search.await_count == 4
    assert sorted(call.kwargs["body"]["size"] for call in logs_client.search.await_args_list) == [
        0,
        0,
        20,
        20,
    ]
    for call in logs_client.search.await_args_list:
        assert call.kwargs["index"] == "test-logs"
        filters = call.kwargs["body"]["query"]["bool"]["filter"]
        assert {"range": {"@timestamp": {"gte": start.isoformat(), "lte": END.isoformat()}}} in (
            filters
        )
    assert report.investigation_window == TimeWindow(start=start, end=END)
    assert report.model_dump(mode="json")["investigation_window"] == {
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": "2026-10-23T14:31:27.123456Z",
    }
    assert report.summary == "No observations"


@pytest.mark.parametrize(("name", "args"), DEFINITIONS)
async def test_model_cannot_create_runtime_window_for_standalone_tools(
    name: str, args: dict[str, Any]
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    logs_client = _logs_client()
    provider = FakeLLMProvider(["done"], tool_rounds=[[_call(name, args)]])
    before = datetime.now(UTC)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        tools = build_metrics_tools(PrometheusConnector(client, "http://metrics.test"))
        tools += build_log_tools(ElasticsearchConnector(logs_client, "test-logs"))
        outcome = await run_tool_rounds(provider, tools, [], max_rounds=1)
    after = datetime.now(UTC)

    assert not outcome.errors
    assert len(outcome.results) == 1
    if requests:
        start = float(requests[0].url.params["start"])
        end = float(requests[0].url.params["end"])
        assert end - start == 3600
        assert before.timestamp() <= end <= after.timestamp()
    else:
        filters = logs_client.search.await_args.kwargs["body"]["query"]["bool"]["filter"]
        interval = next(item["range"]["@timestamp"] for item in filters if "range" in item)
        start_at = datetime.fromisoformat(interval["gte"])
        end_at = datetime.fromisoformat(interval["lte"])
        assert (end_at - start_at).total_seconds() == 3600
        assert before <= end_at <= after


@pytest.mark.parametrize(("name", "args"), DEFINITIONS)
@pytest.mark.parametrize(
    "invalid_window",
    [{}, {"start": "2026-10-23T14:00:00Z", "end": "2026-10-23T13:00:00Z"}],
    ids=["missing-boundaries", "inverted"],
)
async def test_invalid_runtime_window_never_falls_back_to_model_duration(
    name: str, args: dict[str, Any], invalid_window: dict[str, str]
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    logs_client = _logs_client()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        tools = build_metrics_tools(PrometheusConnector(client, "http://metrics.test"))
        tools += build_log_tools(ElasticsearchConnector(logs_client, "test-logs"))
        tool = next(tool for tool in tools if tool.name == name)
        with pytest.raises(ValidationError):
            await tool.ainvoke(
                {**args, "minutes_back": 60},
                config={"configurable": {INVESTIGATION_WINDOW_KEY: invalid_window}},
            )
    assert not requests
    logs_client.search.assert_not_awaited()
