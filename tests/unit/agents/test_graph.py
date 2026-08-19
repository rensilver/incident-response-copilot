import json
from datetime import UTC, datetime, timedelta
from typing import Any

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.state import initial_state
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import LogLevel, MetricKind
from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools

REPORT = json.dumps(
    {
        "summary": "cart-service regression",
        "likely_causes": [
            {
                "title": "bad deploy",
                "rationale": "5xx stepped up",
                "confidence": 0.9,
                "supporting_evidence": [{"source": "metrics", "detail": "error rate rose"}],
            }
        ],
        "next_steps": ["roll back"],
        "confidence": 0.9,
    }
)


class StubMetrics(MetricsSource):
    async def query_range(
        self, query: str, window: TimeWindow, step: str = "30s"
    ) -> list[MetricSeries]:
        base = datetime.now(UTC) - timedelta(minutes=8)
        values = [0.12] * 4 + [0.63] * 4
        return [
            MetricSeries(
                labels={"service": "cart-service"},
                samples=tuple(
                    MetricSample(timestamp=base + timedelta(minutes=i), value=v)
                    for i, v in enumerate(values)
                ),
            )
        ]

    async def list_services(self) -> list[str]:
        return ["cart-service"]


class StubLogs(LogSource):
    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        return LogFinding(
            query="stub", matched_count=42, level_breakdown={LogLevel.ERROR: 42}, samples=()
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        return {"ERROR": 42}


def _metric_call() -> dict[str, Any]:
    return {
        "name": "get_service_metric",
        "args": {"service": "cart-service", "kind": MetricKind.ERROR_RATE, "minutes_back": 60},
        "id": "m1",
        "type": "tool_call",
    }


def _log_call() -> dict[str, Any]:
    return {
        "name": "search_logs",
        "args": {"service": "cart-service", "minutes_back": 60},
        "id": "l1",
        "type": "tool_call",
    }


def _graph(provider: FakeLLMProvider):  # type: ignore[no-untyped-def]  # test helper
    return build_graph(
        provider,
        build_metrics_tools(StubMetrics()),
        build_log_tools(StubLogs()),
        Settings(_env_file=None),
    )


def _state():  # type: ignore[no-untyped-def]  # test helper
    return initial_state(
        correlation_id="cid",
        query="why is cart-service returning 5xx?",
        time_window=TimeWindow.from_minutes_back(60),
        target_service="cart-service",
    )


async def test_full_fan_out_produces_a_report_citing_both_sources() -> None:
    provider = FakeLLMProvider(
        ['{"agents": ["metrics_agent", "logs_agent"], "reasoning": "both"}', REPORT],
        tool_rounds=[[_metric_call()], [_log_call()]],
    )
    final = await _graph(provider).ainvoke(_state())

    assert final["report"] is not None
    assert final["report"].summary == "cart-service regression"
    assert len(final["metrics_findings"]) == 1
    assert len(final["log_findings"]) == 1


async def test_single_specialist_route_still_reaches_correlation() -> None:
    """Probed behaviour: correlation must not block on an unrouted branch."""
    provider = FakeLLMProvider(
        ['{"agents": ["metrics_agent"], "reasoning": "metrics only"}', REPORT],
        tool_rounds=[[_metric_call()]],
    )
    final = await _graph(provider).ainvoke(_state())

    assert final["report"] is not None
    assert final["log_findings"] == []


async def test_unroutable_decision_falls_back_to_both_specialists() -> None:
    provider = FakeLLMProvider(
        ["garbage", "garbage", "garbage", REPORT],
        tool_rounds=[[_metric_call()], [_log_call()]],
    )
    final = await _graph(provider).ainvoke(_state())

    assert len(final["metrics_findings"]) == 1
    assert len(final["log_findings"]) == 1
    assert any("fallback" in e for e in final["errors"])


async def test_graph_terminates_and_records_iterations() -> None:
    provider = FakeLLMProvider(
        ['{"agents": ["logs_agent"], "reasoning": "logs"}', REPORT], tool_rounds=[[_log_call()]]
    )
    final = await _graph(provider).ainvoke(_state())
    assert final["iterations"] == 1
