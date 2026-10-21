from datetime import UTC, datetime, timedelta
from typing import Any

from incident_copilot.agents.logs_agent import build_logs_agent
from incident_copilot.agents.metrics_agent import build_metrics_agent
from incident_copilot.agents.state import initial_state
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import LogLevel, MetricKind
from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools


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
            query="stub", matched_count=7, level_breakdown={LogLevel.ERROR: 7}, samples=()
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        return {"ERROR": 7}


def _state():  # type: ignore[no-untyped-def]  # test helper
    return initial_state(
        correlation_id="cid",
        query="cart-service latency",
        time_window=TimeWindow.from_minutes_back(60),
        target_service="cart-service",
    )


def _metric_call() -> dict[str, Any]:
    return {
        "name": "get_service_metric",
        "args": {"service": "cart-service", "kind": MetricKind.LATENCY_P95, "minutes_back": 60},
        "id": "c1",
        "type": "tool_call",
    }


def _log_call() -> dict[str, Any]:
    return {
        "name": "search_logs",
        "args": {"service": "cart-service", "minutes_back": 60},
        "id": "c2",
        "type": "tool_call",
    }


async def test_metrics_agent_puts_typed_findings_into_state() -> None:
    provider = FakeLLMProvider(["done"], tool_rounds=[[_metric_call()]])
    agent = build_metrics_agent(
        provider, build_metrics_tools(StubMetrics()), Settings(_env_file=None)
    )
    result = await agent(_state())

    assert len(result["metrics_findings"]) == 1
    assert result["metrics_findings"][0].threshold_validated is True


async def test_logs_agent_puts_log_findings_into_state() -> None:
    provider = FakeLLMProvider(["done"], tool_rounds=[[_log_call()]])
    agent = build_logs_agent(provider, build_log_tools(StubLogs()), Settings(_env_file=None))
    result = await agent(_state())

    assert len(result["log_findings"]) == 1
    assert result["log_findings"][0].matched_count == 7


async def test_specialist_returning_nothing_still_returns_valid_state_keys() -> None:
    """A node must always return its reducer keys or the graph merge is a no-op."""
    provider = FakeLLMProvider(["nothing to do"])
    agent = build_metrics_agent(
        provider, build_metrics_tools(StubMetrics()), Settings(_env_file=None)
    )
    result = await agent(_state())

    assert result["metrics_findings"] == []
    assert "errors" in result
