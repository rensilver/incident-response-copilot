import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from incident_copilot.agents.correlation_agent import build_correlation_agent
from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.logs_agent import build_logs_agent
from incident_copilot.agents.metrics_agent import build_metrics_agent
from incident_copilot.agents.state import InvestigationState, initial_state
from incident_copilot.agents.supervisor import build_supervisor
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import AgentName, LogLevel, MetricKind, TrendKind
from incident_copilot.models.findings import RawMetricFinding
from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow
from incident_copilot.models.report import IncidentReport
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools
from incident_copilot.utils.exceptions import LogSourceError, MetricsSourceError

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


def _graph(
    provider: FakeLLMProvider,
) -> CompiledStateGraph[InvestigationState, None, InvestigationState, InvestigationState]:
    return build_graph(
        provider,
        build_metrics_tools(StubMetrics()),
        build_log_tools(StubLogs()),
        Settings(_env_file=None),
    )


def _state() -> InvestigationState:
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


def _seeded_state() -> InvestigationState:
    state = _state()
    state["metrics_findings"] = [
        RawMetricFinding(
            service="cart-service",
            query="up",
            series=(),
            summary="prior-metric-evidence",
            trend=TrendKind.FLAT,
            baseline_value=1,
            current_value=1,
            absolute_delta=0,
            pct_change=0,
            anomaly_detected=False,
        )
    ]
    state["log_findings"] = [
        LogFinding(query="prior-log-evidence", matched_count=3, level_breakdown={}, samples=())
    ]
    state["errors"] = ["prior-collection-error"]
    return state


class RecordingProvider(FakeLLMProvider):
    def __init__(
        self,
        responses: Sequence[str],
        timeline: list[str],
        tool_rounds: Sequence[Sequence[dict[str, Any]]],
    ) -> None:
        super().__init__(responses, tool_rounds)
        self.timeline = timeline

    async def complete_structured[T: BaseModel](
        self, messages: Sequence[ChatMessage], schema: type[T], max_attempts: int = 3
    ) -> T:
        if schema is IncidentReport:
            self.timeline.append("correlation")
        return await super().complete_structured(messages, schema, max_attempts)


@pytest.mark.parametrize(
    ("decision", "selected", "completion_order", "schema_invalid", "fallback"),
    [
        pytest.param(
            ["metrics_agent"], {AgentName.METRICS}, ["metrics_agent"], False, False, id="metrics"
        ),
        pytest.param(["logs_agent"], {AgentName.LOGS}, ["logs_agent"], False, False, id="logs"),
        pytest.param(
            ["metrics_agent", "logs_agent"],
            {AgentName.METRICS, AgentName.LOGS},
            ["metrics_agent", "logs_agent"],
            False,
            False,
            id="metrics-finishes-first",
        ),
        pytest.param(
            ["metrics_agent", "logs_agent"],
            {AgentName.METRICS, AgentName.LOGS},
            ["logs_agent", "metrics_agent"],
            False,
            False,
            id="logs-finishes-first",
        ),
        pytest.param(
            ["logs_agent", "metrics_agent"],
            {AgentName.METRICS, AgentName.LOGS},
            ["metrics_agent", "logs_agent"],
            False,
            False,
            id="reversed-route",
        ),
        pytest.param(
            ["metrics_agent", "metrics_agent", "logs_agent"],
            {AgentName.METRICS, AgentName.LOGS},
            ["logs_agent", "metrics_agent"],
            False,
            False,
            id="duplicate-destination",
        ),
        pytest.param(
            [],
            {AgentName.METRICS, AgentName.LOGS},
            ["logs_agent", "metrics_agent"],
            True,
            True,
            id="empty-route",
        ),
        pytest.param(
            ["unknown_agent"],
            {AgentName.METRICS, AgentName.LOGS},
            ["metrics_agent", "logs_agent"],
            True,
            True,
            id="unknown-route",
        ),
        pytest.param(
            ["supervisor", "correlation_agent"],
            {AgentName.METRICS, AgentName.LOGS},
            ["logs_agent", "metrics_agent"],
            False,
            True,
            id="non-specialists",
        ),
        pytest.param(
            ["correlation_agent", "logs_agent"],
            {AgentName.LOGS},
            ["logs_agent"],
            False,
            False,
            id="mixed-route-keeps-specialist",
        ),
    ],
)
async def test_selected_branches_finish_before_one_correlation_with_all_evidence(
    decision: list[str],
    selected: set[AgentName],
    completion_order: list[str],
    schema_invalid: bool,
    fallback: bool,
) -> None:
    """Catch wrong branches, early joins, overwritten evidence, and duplicate correlation."""
    timeline: list[str] = []
    started = {agent: asyncio.Event() for agent in selected}
    first_finished = asyncio.Event()

    async def finish(agent: AgentName) -> None:
        started[agent].set()
        for event in started.values():
            await event.wait()
        if agent.value != completion_order[0]:
            await first_finished.wait()
        timeline.append(agent.value)
        first_finished.set()

    class OrderedMetrics(StubMetrics):
        async def query_range(
            self, query: str, window: TimeWindow, step: str = "30s"
        ) -> list[MetricSeries]:
            result = await super().query_range(query, window, step)
            await finish(AgentName.METRICS)
            return result

    class OrderedLogs(StubLogs):
        async def search(self, criteria: LogSearchCriteria) -> LogFinding:
            result = await super().search(criteria)
            await finish(AgentName.LOGS)
            return result

    route = json.dumps({"agents": decision, "reasoning": "scripted route"})
    provider = RecordingProvider(
        [*([route] * (2 if schema_invalid else 1)), REPORT],
        timeline,
        [[_metric_call()], [_log_call()]],
    )
    graph = build_graph(
        provider,
        build_metrics_tools(OrderedMetrics()),
        build_log_tools(OrderedLogs()),
        Settings(_env_file=None),
    )
    state = _seeded_state()
    before = deepcopy(state)
    final = await asyncio.wait_for(graph.ainvoke(state), timeout=5)

    assert timeline == [*completion_order, "correlation"]
    assert set(final["route"]) == selected
    assert len(final["metrics_findings"]) == (2 if AgentName.METRICS in selected else 1)
    assert len(final["log_findings"]) == (2 if AgentName.LOGS in selected else 1)
    assert final["metrics_findings"][0].summary == "prior-metric-evidence"
    assert final["log_findings"][0].query == "prior-log-evidence"
    assert final["errors"].count("prior-collection-error") == 1
    assert any("fallback" in error for error in final["errors"]) is fallback
    assert final["iterations"] == 1
    assert final["report"].summary == "cart-service regression"
    prompt = provider.calls[-1][-1].content
    assert "prior-metric-evidence" in prompt and "prior-log-evidence" in prompt
    assert "prior-collection-error" in prompt
    assert ("5xx error rate" in prompt) is (AgentName.METRICS in selected)
    assert ("42 documents matched" in prompt) is (AgentName.LOGS in selected)
    assert state == before
    for field in ("correlation_id", "query", "time_window", "target_service"):
        assert final[field] == before[field]


async def test_both_branch_errors_are_merged_with_existing_errors_before_correlation() -> None:
    """A missing errors reducer must not erase one branch or abort their shared step."""

    class FailedMetrics(StubMetrics):
        async def query_range(
            self, query: str, window: TimeWindow, step: str = "30s"
        ) -> list[MetricSeries]:
            raise MetricsSourceError("metrics-collection-unavailable")

    class FailedLogs(StubLogs):
        async def search(self, criteria: LogSearchCriteria) -> LogFinding:
            raise LogSourceError("logs-collection-unavailable")

    timeline: list[str] = []
    provider = RecordingProvider(
        ['{"agents": ["metrics_agent", "logs_agent"], "reasoning": "both"}', REPORT],
        timeline,
        [[_metric_call()], [_log_call()]],
    )
    graph = build_graph(
        provider,
        build_metrics_tools(FailedMetrics()),
        build_log_tools(FailedLogs()),
        Settings(_env_file=None),
    )
    final = await asyncio.wait_for(graph.ainvoke(_seeded_state()), timeout=5)

    assert timeline == ["correlation"]
    assert len(final["errors"]) == 3
    assert "prior-collection-error" in final["errors"]
    assert any("metrics-collection-unavailable" in error for error in final["errors"])
    assert any("logs-collection-unavailable" in error for error in final["errors"])
    prompt = provider.calls[-1][-1].content
    assert "metrics-collection-unavailable" in prompt
    assert "logs-collection-unavailable" in prompt
    assert final["report"] is not None


@pytest.mark.parametrize(
    ("agent", "fields"),
    [
        (AgentName.SUPERVISOR, {"route", "iterations", "errors"}),
        (AgentName.METRICS, {"metrics_findings", "errors"}),
        (AgentName.LOGS, {"log_findings", "errors"}),
        (AgentName.CORRELATION, {"report", "errors"}),
    ],
)
async def test_nodes_return_partial_updates_without_mutating_existing_state(
    agent: AgentName, fields: set[str]
) -> None:
    """Returning accumulated state would replay reducer values and duplicate prior evidence."""
    provider = FakeLLMProvider(
        [
            (
                REPORT
                if agent is AgentName.CORRELATION
                else '{"agents": ["metrics_agent"], "reasoning": "metrics"}'
            )
        ],
        tool_rounds=[[_metric_call()], [_log_call()]],
    )
    settings = Settings(_env_file=None)
    nodes: dict[AgentName, Callable[[InvestigationState], Awaitable[Mapping[str, object]]]] = {
        AgentName.SUPERVISOR: build_supervisor(provider, settings),
        AgentName.METRICS: build_metrics_agent(
            provider, build_metrics_tools(StubMetrics()), settings
        ),
        AgentName.LOGS: build_logs_agent(provider, build_log_tools(StubLogs()), settings),
        AgentName.CORRELATION: build_correlation_agent(provider),
    }
    state = _seeded_state()
    before = deepcopy(state)
    update = await nodes[agent](state)

    assert set(update) == fields
    assert update["errors"] == []
    if agent is AgentName.METRICS:
        findings = update["metrics_findings"]
        assert isinstance(findings, list) and len(findings) == 1
    if agent is AgentName.LOGS:
        findings = update["log_findings"]
        assert isinstance(findings, list) and len(findings) == 1
    assert state == before
