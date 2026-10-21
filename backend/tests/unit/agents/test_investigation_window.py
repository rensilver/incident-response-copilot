"""The caller's interval must reach connectors unchanged through the real graph."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.logs_agent import build_logs_agent
from incident_copilot.agents.metrics_agent import build_metrics_agent
from incident_copilot.agents.state import initial_state
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.logs import LogFinding
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools

REPORT = json.dumps(
    {"summary": "No observations", "likely_causes": [], "next_steps": [], "confidence": 0.0}
)


def _calls(minutes_back: int | None) -> list[list[dict[str, Any]]]:
    temporal_args = {} if minutes_back is None else {"minutes_back": minutes_back}
    # Extra model-authored fields must not be mistaken for runtime configuration.
    spoofed_config = {
        "config": {"configurable": {"investigation_time_window": {}}},
        "time_window": {},
    }
    definitions = [
        ("get_service_metric", {"service": "cart-service", "kind": "error_rate"}),
        ("raw_promql_query", {"query": "up"}),
        ("search_logs", {"service": "cart-service"}),
        ("log_level_histogram", {"service": "cart-service"}),
    ]
    return [
        [
            {
                "name": name,
                "args": {**args, **temporal_args, **spoofed_config},
                "id": name,
                "type": "tool_call",
            }
        ]
        for name, args in definitions
    ]


def _sources() -> tuple[AsyncMock, AsyncMock]:
    metrics = AsyncMock(spec=MetricsSource)
    metrics.query_range.return_value = []
    logs = AsyncMock(spec=LogSource)
    logs.search.return_value = LogFinding(
        query="empty", matched_count=0, level_breakdown={}, samples=()
    )
    logs.level_histogram.return_value = {}
    return metrics, logs


@pytest.mark.parametrize("model_minutes", [None, 60])
async def test_request_window_reaches_every_data_tool_across_rounds(
    model_minutes: int | None,
) -> None:
    metrics, logs = _sources()
    provider = FakeLLMProvider(
        ['{"agents": ["metrics_agent", "logs_agent"], "reasoning": "both"}', REPORT],
        tool_rounds=_calls(model_minutes),
    )
    graph = build_graph(
        provider,
        build_metrics_tools(metrics),
        build_log_tools(logs),
        Settings(_env_file=None, max_tool_rounds=2),
    )
    before = datetime.now(UTC)
    report = await IncidentService(graph).investigate(
        InvestigationRequest(query="cart-service errors", minutes_back=180)
    )
    after = datetime.now(UTC)

    assert report.summary == "No observations"
    assert metrics.query_range.await_count == 2
    logs.search.assert_awaited_once()
    logs.level_histogram.assert_awaited_once()
    windows = [call.args[1] for call in metrics.query_range.await_args_list]
    windows.append(logs.search.await_args.args[0].window)
    windows.append(logs.level_histogram.await_args.args[1])
    assert all(window == windows[0] for window in windows)
    assert windows[0].duration_seconds == 180 * 60
    assert before <= windows[0].end <= after


@pytest.mark.parametrize("specialist", ["metrics", "logs"])
async def test_concurrent_investigations_do_not_share_window(specialist: str) -> None:
    metrics, logs = _sources()
    rendezvous = asyncio.Barrier(2)
    seen: list[TimeWindow] = []

    async def record(*args: Any) -> Any:
        await rendezvous.wait()
        if specialist == "metrics":
            seen.append(args[1])
            return []
        seen.append(args[0].window)
        return logs.search.return_value

    calls = _calls(60)
    if specialist == "metrics":
        metrics.query_range.side_effect = record
        tools = build_metrics_tools(metrics)
        build_agent = build_metrics_agent
        call = calls[0]
    else:
        logs.search.side_effect = record
        tools = build_log_tools(logs)
        build_agent = build_logs_agent
        call = calls[2]
    provider = FakeLLMProvider(["done"], tool_rounds=[call, call])
    agent = build_agent(provider, tools, Settings(_env_file=None, max_tool_rounds=1))
    end = datetime(2026, 9, 1, tzinfo=UTC)
    windows = [TimeWindow(start=end - timedelta(minutes=minutes), end=end) for minutes in (15, 180)]
    results = await asyncio.wait_for(
        asyncio.gather(
            *(
                agent(initial_state(str(index), "cart-service errors", window, "cart-service"))
                for index, window in enumerate(windows)
            )
        ),
        timeout=5,
    )
    assert all(not result["errors"] for result in results)
    assert sorted(seen, key=lambda w: w.start) == sorted(windows, key=lambda w: w.start)
