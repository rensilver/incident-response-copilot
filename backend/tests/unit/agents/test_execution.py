"""Exercise failures, cancellation, and overlapping calls through the real graph/service."""

import asyncio
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import pytest
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, convert_to_messages
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool
from structlog.contextvars import get_contextvars

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.prompts import SUPERVISOR_SYSTEM
from incident_copilot.agents.state import InvestigationState
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogEntry, LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools
from incident_copilot.utils.exceptions import (
    InvestigationError,
    InvestigationTimeoutError,
    LLMProviderError,
    LogSourceError,
    MetricsSourceError,
)

Stage = Literal[
    "supervisor", "metrics_model", "logs_model", "metrics_tool", "logs_tool", "correlation"
]
STAGES: tuple[Stage, ...] = (
    "supervisor",
    "metrics_model",
    "logs_model",
    "metrics_tool",
    "logs_tool",
    "correlation",
)


@dataclass
class Execution:
    blocked: set[tuple[str, Stage]] = field(default_factory=set)
    failures: set[tuple[str, Stage]] = field(default_factory=set)
    entered: dict[tuple[str, Stage], asyncio.Event] = field(default_factory=dict)
    cancelled: set[tuple[str, Stage]] = field(default_factory=set)
    visits: list[tuple[str, Stage, str]] = field(default_factory=list)
    release: asyncio.Event = field(default_factory=asyncio.Event)

    def event(self, service: str, stage: Stage) -> asyncio.Event:
        return self.entered.setdefault((service, stage), asyncio.Event())

    async def visit(self, service: str, stage: Stage) -> None:
        self.visits.append((service, stage, str(get_contextvars().get("correlation_id"))))
        self.event(service, stage).set()
        if (service, stage) in self.blocked:
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancelled.add((service, stage))
                raise


def _identity(text: str) -> str:
    match = re.search(r"request-(alpha|beta)", text)
    assert match is not None, text
    return match[1]


class ExecutionProvider(FakeLLMProvider):
    """Select fake responses by request content, independently of scheduling order."""

    def __init__(self, execution: Execution) -> None:
        super().__init__(["unused"])
        self.execution = execution
        self.prompts: dict[tuple[str, Stage], list[str]] = {}
        self.histories: dict[tuple[str, Stage], list[list[BaseMessage]]] = {}

    async def _generate_json(self, messages: Sequence[ChatMessage]) -> str:
        stage: Stage = "supervisor" if messages[0].content == SUPERVISOR_SYSTEM else "correlation"
        prompt = messages[-1].content
        service = _identity(prompt)
        self.prompts.setdefault((service, stage), []).append(prompt)
        await self.execution.visit(service, stage)
        if (service, stage) in self.execution.failures:
            raise LLMProviderError(f"{service}-{stage}-unavailable")
        if stage == "supervisor":
            return json.dumps({"agents": ["metrics_agent", "logs_agent"], "reasoning": "both"})
        return json.dumps(
            {"summary": f"report-{service}", "likely_causes": [], "next_steps": [], "confidence": 0}
        )

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        metrics = any(tool.name == "get_service_metric" for tool in tools)
        stage: Stage = "metrics_model" if metrics else "logs_model"

        async def respond(messages: LanguageModelInput) -> BaseMessage:
            conversation = convert_to_messages(messages)
            service = _identity(str(conversation[1].content))
            self.histories.setdefault((service, stage), []).append(conversation)
            await self.execution.visit(service, stage)
            if (service, stage) in self.execution.failures:
                raise LLMProviderError(f"{service}-{stage}-unavailable")
            if any(isinstance(message, AIMessage) for message in conversation):
                return AIMessage(content="collection complete")
            args = {"service": service, **({"kind": "error_rate"} if metrics else {})}
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_service_metric" if metrics else "search_logs",
                        "args": args,
                        "id": f"{service}-{stage}",
                        "type": "tool_call",
                    }
                ],
            )

        return RunnableLambda(respond)


class ExecutionMetrics(MetricsSource):
    def __init__(self, execution: Execution) -> None:
        self.execution = execution

    async def query_range(
        self, query: str, window: TimeWindow, step: str = "30s"
    ) -> list[MetricSeries]:
        service = "alpha" if 'service="alpha"' in query else "beta"
        await self.execution.visit(service, "metrics_tool")
        if (service, "metrics_tool") in self.execution.failures:
            raise MetricsSourceError(f"{service}-metrics_tool-unavailable")
        return [
            MetricSeries(
                labels={"service": service},
                samples=(
                    MetricSample(timestamp=window.end, value=0.25 if service == "alpha" else 0.5),
                ),
            )
        ]

    async def list_services(self) -> list[str]:
        raise AssertionError("No service discovery expected")


class ExecutionLogs(LogSource):
    def __init__(self, execution: Execution) -> None:
        self.execution = execution

    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        service = criteria.service
        await self.execution.visit(service, "logs_tool")
        if (service, "logs_tool") in self.execution.failures:
            raise LogSourceError(f"{service}-logs_tool-unavailable")
        return LogFinding(
            query=f"service:{service}",
            matched_count=1,
            level_breakdown={LogLevel.ERROR: 1},
            samples=(
                LogEntry(
                    timestamp=criteria.window.end,
                    service=service,
                    level=LogLevel.ERROR,
                    message=f"evidence-{service}",
                ),
            ),
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        raise AssertionError("No histogram expected")


class InvestigationHarness:
    def __init__(self, execution: Execution) -> None:
        self.provider = ExecutionProvider(execution)
        self.graph = build_graph(
            self.provider,
            build_metrics_tools(ExecutionMetrics(execution)),
            build_log_tools(ExecutionLogs(execution)),
            Settings(_env_file=None, max_tool_rounds=2),
        )
        self.initials: dict[str, InvestigationState] = {}
        self.finals: dict[str, Mapping[str, Any]] = {}
        self.service = IncidentService(self)

    async def ainvoke(self, state: InvestigationState, /) -> Mapping[str, Any]:
        self.initials[state["query"]] = state
        final = await self.graph.ainvoke(state)
        self.finals[state["query"]] = final
        return final


def _request(service: str) -> InvestigationRequest:
    return InvestigationRequest(query=f"request-{service}", service=service)


@pytest.mark.parametrize("stage", STAGES)
async def test_graph_failures_degrade_collection_or_raise_when_no_report(stage: Stage) -> None:
    execution = Execution(failures={("alpha", stage)})
    harness = InvestigationHarness(execution)
    if stage == "correlation":
        with pytest.raises(InvestigationError, match="alpha-correlation-unavailable"):
            await asyncio.wait_for(harness.service.investigate(_request("alpha")), timeout=5)
    else:
        report = await asyncio.wait_for(harness.service.investigate(_request("alpha")), timeout=5)
        assert report.summary == "report-alpha"
    final = harness.finals["request-alpha"]
    assert len(final["errors"]) == 1
    assert f"alpha-{stage}-unavailable" in final["errors"][0]
    assert len(final["metrics_findings"]) == (0 if stage.startswith("metrics") else 1)
    assert len(final["log_findings"]) == (0 if stage.startswith("logs") else 1)
    assert final["iterations"] == 1
    assert (final["report"] is None) is (stage == "correlation")
    assert sum(visit[1] == stage for visit in execution.visits) == 1
    if stage != "correlation":
        assert f"alpha-{stage}-unavailable" in harness.provider.prompts[("alpha", "correlation")][0]


@pytest.mark.parametrize("stage", STAGES)
async def test_cancellation_reaches_inflight_work_without_becoming_a_report(stage: Stage) -> None:
    execution = Execution(blocked={("alpha", stage)})
    harness = InvestigationHarness(execution)
    task = asyncio.create_task(harness.service.investigate(_request("alpha")))
    try:
        await asyncio.wait_for(execution.event("alpha", stage).wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)
        assert ("alpha", stage) in execution.cancelled
        assert harness.finals == {}
        if stage != "correlation":
            assert ("alpha", "correlation") not in harness.provider.prompts
        assert sum(visit[1] == stage for visit in execution.visits) == 1
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_cancelling_fan_out_cancels_both_pending_connectors() -> None:
    blocked: set[tuple[str, Stage]] = {("alpha", "metrics_tool"), ("alpha", "logs_tool")}
    execution = Execution(blocked=blocked)
    harness = InvestigationHarness(execution)
    task = asyncio.create_task(harness.service.investigate(_request("alpha")))
    try:
        await asyncio.wait_for(
            asyncio.gather(*(execution.event(service, stage).wait() for service, stage in blocked)),
            timeout=5,
        )
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)
        assert execution.cancelled == blocked
        assert harness.finals == {}
        assert ("alpha", "correlation") not in harness.provider.prompts
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("stage", STAGES)
async def test_total_deadline_cancels_each_graph_stage(stage: Stage) -> None:
    execution = Execution(blocked={("alpha", stage)})
    harness = InvestigationHarness(execution)
    service = IncidentService(harness, timeout_seconds=0.2)
    with pytest.raises(InvestigationTimeoutError):
        await asyncio.wait_for(service.investigate(_request("alpha")), timeout=5)
    assert ("alpha", stage) in execution.cancelled
    assert harness.finals == {}
    if stage != "correlation":
        assert ("alpha", "correlation") not in harness.provider.prompts


async def test_expiry_cancels_fan_out_without_poisoning_shared_graph() -> None:
    blocked: set[tuple[str, Stage]] = {("alpha", "metrics_tool"), ("alpha", "logs_tool")}
    execution = Execution(blocked=blocked)
    harness = InvestigationHarness(execution)
    service = IncidentService(harness, timeout_seconds=0.3)
    task = asyncio.create_task(service.investigate(_request("alpha")))
    try:
        await asyncio.wait_for(
            asyncio.gather(*(execution.event(name, stage).wait() for name, stage in blocked)),
            timeout=5,
        )
        report = await asyncio.wait_for(service.investigate(_request("beta")), timeout=5)
        assert report.summary == "report-beta"
        with pytest.raises(InvestigationTimeoutError):
            await asyncio.wait_for(task, timeout=5)
        assert execution.cancelled == blocked
        assert "request-alpha" not in harness.finals
        assert ("alpha", "correlation") not in harness.provider.prompts
        # The same service and compiled graph accept a later successful request.
        execution.blocked.clear()
        recovered = await asyncio.wait_for(service.investigate(_request("alpha")), timeout=5)
        assert recovered.summary == "report-alpha"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("cancel_alpha", [False, True])
async def test_shared_graph_isolates_overlapping_investigations(cancel_alpha: bool) -> None:
    execution = Execution(blocked={("alpha", "metrics_tool")}, failures={("alpha", "logs_tool")})
    if cancel_alpha:
        execution.blocked.add(("beta", "logs_tool"))
    harness = InvestigationHarness(execution)
    alpha = asyncio.create_task(harness.service.investigate(_request("alpha")))
    tasks = [alpha]
    try:
        await asyncio.wait_for(execution.event("alpha", "metrics_tool").wait(), timeout=5)
        beta_task = asyncio.create_task(harness.service.investigate(_request("beta")))
        tasks.append(beta_task)
        if cancel_alpha:
            await asyncio.wait_for(execution.event("beta", "logs_tool").wait(), timeout=5)
            alpha.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(alpha, timeout=5)
            assert "request-alpha" not in harness.finals
            assert not beta_task.done()
            assert ("beta", "logs_tool") not in execution.cancelled
            execution.release.set()
            beta = await asyncio.wait_for(beta_task, timeout=5)
        else:
            # Beta finishes while Alpha is still inside the same compiled graph and tools.
            beta = await asyncio.wait_for(beta_task, timeout=5)
            assert not alpha.done()
            execution.release.set()
            report = await asyncio.wait_for(alpha, timeout=5)
            assert report.summary == "report-alpha"
            final_alpha = harness.finals["request-alpha"]
            assert len(final_alpha["errors"]) == 1
            assert "alpha-logs_tool-unavailable" in final_alpha["errors"][0]
            assert final_alpha["metrics_findings"][0].service == "alpha"
            assert final_alpha["log_findings"] == []
            prompt_alpha = harness.provider.prompts[("alpha", "correlation")][0]
            assert "beta" not in prompt_alpha

        assert beta.summary == "report-beta"
        final_beta = harness.finals["request-beta"]
        assert final_beta["errors"] == []
        assert final_beta["metrics_findings"][0].service == "beta"
        assert final_beta["metrics_findings"][0].current_value == 0.5
        assert final_beta["log_findings"][0].samples[0].message == "evidence-beta"
        assert final_beta["iterations"] == 1
        prompt_beta = harness.provider.prompts[("beta", "correlation")][0]
        assert "alpha" not in prompt_beta
        for (service, _), histories in harness.provider.histories.items():
            other = "beta" if service == "alpha" else "alpha"
            assert all(
                other not in str(message.content) for history in histories for message in history
            )
        alpha_id = harness.initials["request-alpha"]["correlation_id"]
        beta_id = harness.initials["request-beta"]["correlation_id"]
        assert alpha_id and beta_id and alpha_id != beta_id
        assert all(
            cid == (alpha_id if service == "alpha" else beta_id)
            for service, _, cid in execution.visits
        )
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
