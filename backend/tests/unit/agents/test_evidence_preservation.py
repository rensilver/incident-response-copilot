"""Protect evidence at the specialist follow-up and correlation boundaries."""

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage, convert_to_messages
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.prompts import render_evidence, render_log_finding
from incident_copilot.agents.state import initial_state
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogEntry, LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.utils.exceptions import LogSourceError

END = datetime(2026, 10, 23, 12, tzinfo=UTC)
DEPENDENCY_MESSAGE = "upstream timeout calling fraud-api after 2000ms"
ERROR_MESSAGE = "PaymentAuthorizationException: fraud check unavailable"


def _entry(message: str, level: LogLevel = LogLevel.WARN) -> LogEntry:
    return LogEntry(
        timestamp=END - timedelta(minutes=1),
        service="payment-service",
        level=level,
        message=message,
        version="v1.4.2",
    )


def test_repeated_searches_keep_distinct_samples_in_a_stable_evidence_block() -> None:
    """Equal query/count searches must retain late clues without arrival-order bias."""
    first = LogFinding(
        query="service:payment-service",
        matched_count=100,
        level_breakdown={LogLevel.WARN: 1},
        samples=(_entry("request timed out calling inventory-api"),),
    )
    second = first.model_copy(update={"samples": (_entry(DEPENDENCY_MESSAGE),)})
    text = render_evidence([], [first, second])
    assert "inventory-api" in text and DEPENDENCY_MESSAGE in text
    assert text.count("100 documents matched") == 2
    assert render_evidence([], [second, first]) == text


def test_severity_insertion_order_does_not_change_the_evidence_block() -> None:
    """Equivalent sample histograms must not reorder an otherwise identical prompt."""
    first = LogFinding(
        query="service:payment-service",
        matched_count=100,
        level_breakdown={LogLevel.WARN: 1, LogLevel.ERROR: 1},
        samples=(_entry(DEPENDENCY_MESSAGE), _entry(ERROR_MESSAGE, LogLevel.ERROR)),
    )
    second = first.model_copy(update={"level_breakdown": {LogLevel.ERROR: 1, LogLevel.WARN: 1}})
    assert render_evidence([], [first]) == render_evidence([], [second])


@pytest.mark.parametrize("dimension", ["service", "level", "message", "version"])
def test_log_grouping_keeps_observations_that_differ_in_one_dimension(dimension: str) -> None:
    """Grouping by message alone must not erase the service, severity, or release."""
    values = {
        "service": "fraud-api",
        "level": LogLevel.ERROR,
        "message": "upstream timeout calling inventory-api after 2000ms",
        "version": "v1.5.0",
    }
    original = _entry(DEPENDENCY_MESSAGE)
    other = original.model_copy(update={dimension: values[dimension]})
    finding = LogFinding(
        query="timeouts", matched_count=200, level_breakdown={}, samples=(original, other)
    )
    text = render_log_finding(finding)
    assert text.count("sampled occurrences=1") == 2
    assert DEPENDENCY_MESSAGE in text
    assert str(values[dimension]) in text
    assert render_log_finding(finding.model_copy(update={"samples": (other, original)})) == text


class EvidenceLogs(LogSource):
    """Return a full sample whose last message is the only named dependency clue."""

    def __init__(self, reverse: bool, fail_followup: bool) -> None:
        self.reverse = reverse
        self.fail_followup = fail_followup
        self.criteria: list[LogSearchCriteria] = []

    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        self.criteria.append(criteria)
        samples: tuple[LogEntry, ...]
        if criteria.service == "fraud-api":
            if self.fail_followup:
                raise LogSourceError("dependency logs unavailable")
            samples = ()
        else:
            samples = (
                *(_entry(ERROR_MESSAGE, LogLevel.ERROR) for _ in range(19)),
                _entry(DEPENDENCY_MESSAGE),
            )
        if self.reverse:
            samples = samples[::-1]
        return LogFinding(
            query=f"service:{criteria.service}",
            matched_count=1000 if samples else 0,
            level_breakdown={LogLevel.ERROR: 19, LogLevel.WARN: 1} if samples else {},
            samples=samples,
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        raise AssertionError("No histogram expected")


class EvidenceProvider(FakeLLMProvider):
    """Record tool replies while replaying a dependency follow-up, without live reasoning."""

    def __init__(self) -> None:
        super().__init__(
            [
                '{"agents": ["logs_agent"], "reasoning": "logs only"}',
                json.dumps(
                    {
                        "summary": "Dependency timeout observed; mechanism unconfirmed",
                        "likely_causes": [],
                        "next_steps": ["Measure fraud-api latency"],
                        "confidence": 0.1,
                    }
                ),
            ]
        )
        self.followups: list[list[ToolMessage]] = []

    def bind_tools(self, tools: Sequence[BaseTool]) -> Runnable[LanguageModelInput, BaseMessage]:
        async def respond(messages: LanguageModelInput) -> BaseMessage:
            history = convert_to_messages(messages)
            replies = [message for message in history if isinstance(message, ToolMessage)]
            if replies:
                self.followups.append(replies)
            if len(replies) == 2:
                return AIMessage(content="collection complete")
            args: dict[str, Any] = {"service": "fraud-api" if replies else "payment-service"}
            return AIMessage(
                content="",
                tool_calls=[{"name": "search_logs", "args": args, "id": f"search-{len(replies)}"}],
            )

        return RunnableLambda(respond)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("fail_followup", [False, True])
async def test_late_dependency_clue_reaches_followup_and_correlation(
    reverse: bool, fail_followup: bool
) -> None:
    """Truncation, reducer replacement, or discarded findings would lose the clue."""
    provider = EvidenceProvider()
    logs = EvidenceLogs(reverse, fail_followup)
    graph = build_graph(
        provider, [], build_log_tools(logs), Settings(_env_file=None, max_tool_rounds=3)
    )
    window = TimeWindow(start=END - timedelta(minutes=17), end=END)
    state = initial_state(
        correlation_id="evidence-case",
        query="Why is payment-service slow?",
        time_window=window,
        target_service="payment-service",
    )
    final = await graph.ainvoke(state)

    followup = provider.followups[0][0].content
    assert isinstance(followup, str)
    assert DEPENDENCY_MESSAGE in followup and ERROR_MESSAGE in followup
    assert "sampled occurrences=19" in followup
    assert "20 samples retrieved" in followup
    assert "1000 documents matched" in followup
    prompt = provider.calls[-1][-1].content
    assert followup in prompt
    assert "Service of interest: payment-service" in prompt
    assert "2026-10-23T11:43:00+00:00 to 2026-10-23T12:00:00+00:00 (17 minutes)" in prompt
    assert len(final["log_findings"]) == (1 if fail_followup else 2)
    assert ("dependency logs unavailable" in prompt) is fail_followup
    assert ("- 0 documents matched `service:fraud-api`" in prompt) is (not fail_followup)
    assert [criteria.service for criteria in logs.criteria] == ["payment-service", "fraud-api"]
    assert all(criteria.window == window for criteria in logs.criteria)
