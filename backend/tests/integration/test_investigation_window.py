"""Verify fixed investigation windows against the live seeded data backends."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from elasticsearch import AsyncElasticsearch
from pytest_mock import MockerFixture

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.state import initial_state
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("minutes", [17, 180])
async def test_fixed_window_reaches_live_backends(minutes: int, mocker: MockerFixture) -> None:
    """Use scripted tool calls to cover all four tools, with real backend responses."""
    requests: list[httpx.Request] = []

    async def record(request: httpx.Request) -> None:
        requests.append(request)

    end = datetime.now(UTC) - timedelta(minutes=2)
    window = TimeWindow(start=end - timedelta(minutes=minutes), end=end)
    definitions = [
        ("get_service_metric", {"service": "cart-service", "kind": "error_rate"}),
        (
            "raw_promql_query",
            {"query": 'process_resident_memory_bytes{service="checkout-service"}'},
        ),
        ("search_logs", {"service": "cart-service"}),
        ("log_level_histogram", {"service": "cart-service"}),
    ]
    provider = FakeLLMProvider(
        [
            '{"agents": ["metrics_agent", "logs_agent"], "reasoning": "window validation"}',
            json.dumps(
                {"summary": "Window check", "likely_causes": [], "next_steps": [], "confidence": 0}
            ),
        ],
        tool_rounds=[
            [{"name": name, "args": {**args, "minutes_back": 60}, "id": name, "type": "tool_call"}]
            for name, args in definitions
        ],
    )
    async with (
        httpx.AsyncClient(timeout=30, event_hooks={"request": [record]}) as metrics_client,
        AsyncElasticsearch("http://localhost:9200") as logs_client,
    ):
        metrics = PrometheusConnector(metrics_client, "http://localhost:9090")
        logs = ElasticsearchConnector(logs_client, "app-logs")
        searches = mocker.spy(logs_client, "perform_request")
        graph = build_graph(
            provider,
            build_metrics_tools(metrics),
            build_log_tools(logs),
            Settings(_env_file=None, llm_provider="ollama", max_tool_rounds=2),
        )
        result = await graph.ainvoke(
            initial_state("live-window", "cart errors", window, "cart-service")
        )

    assert not result["errors"], result["errors"]
    assert len(requests) == 2
    for request in requests:
        assert request.url.path == "/api/v1/query_range"
        assert float(request.url.params["start"]) == window.start.timestamp()
        assert float(request.url.params["end"]) == window.end.timestamp()
    assert searches.call_count == 2
    for call in searches.call_args_list:
        filters = call.kwargs["body"]["query"]["bool"]["filter"]
        interval = next(item["range"]["@timestamp"] for item in filters if "range" in item)
        assert interval == {"gte": window.start.isoformat(), "lte": window.end.isoformat()}

    assert len(result["metrics_findings"]) == 2
    for finding in result["metrics_findings"]:
        samples = [sample for series in finding.series for sample in series.samples]
        assert samples, "freshly seed the stack before testing investigation windows"
        # Prometheus rounds evaluation timestamps to milliseconds; outgoing request
        # boundaries above must still match the original window exactly.
        precision = timedelta(milliseconds=1)
        assert all(
            window.start - precision <= sample.timestamp <= window.end + precision
            for sample in samples
        )
    assert len(result["log_findings"]) == 1
    log_finding = result["log_findings"][0]
    assert log_finding.matched_count > 0
    assert log_finding.samples
    assert all(window.start <= sample.timestamp <= window.end for sample in log_finding.samples)
    print(f"\nLive window: {window.model_dump_json()}; all four tools preserved it")
