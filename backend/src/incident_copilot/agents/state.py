"""Shared state passed between graph nodes.

``metrics_findings``, ``log_findings`` and ``errors`` carry ``operator.add`` reducers
so partial updates append to existing evidence. The specialists both write ``errors``
in one parallel step; without a reducer those simultaneous writes would raise an
``InvalidUpdateError``. Each findings list currently has one specialist writer, but
still needs its reducer to retain findings collected before that specialist runs.
"""

import operator
from collections.abc import Awaitable
from typing import Annotated, Protocol, TypedDict

from incident_copilot.models.enums import AgentName
from incident_copilot.models.findings import MetricFinding
from incident_copilot.models.logs import LogFinding
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.models.report import IncidentReport


class InvestigationState(TypedDict):
    """Everything one investigation accumulates as it moves through the graph."""

    correlation_id: str
    query: str
    time_window: TimeWindow
    target_service: str | None
    route: list[AgentName]
    iterations: int
    metrics_findings: Annotated[list[MetricFinding], operator.add]
    log_findings: Annotated[list[LogFinding], operator.add]
    report: IncidentReport | None
    errors: Annotated[list[str], operator.add]


class InvestigationNode[UpdateT](Protocol):
    """An async node preserving its partial update type.

    Naming the ``state`` argument matches LangGraph's callable protocol. A plain
    ``Callable[[InvestigationState], Awaitable[UpdateT]]`` loses that parameter
    name and fails its node-registration overloads in strict mypy.
    """

    def __call__(self, state: InvestigationState) -> Awaitable[UpdateT]:
        """Read one investigation state and return a partial update."""
        ...


def initial_state(
    correlation_id: str,
    query: str,
    time_window: TimeWindow,
    target_service: str | None,
) -> InvestigationState:
    """Build the starting state for one investigation.

    Args:
        correlation_id: Identifier bound to every log line for this investigation.
        query: The engineer's question.
        time_window: Window to investigate.
        target_service: Service to focus on, if the caller named one.

    Returns:
        A state with no findings, no route and no report.
    """
    return InvestigationState(
        correlation_id=correlation_id,
        query=query,
        time_window=time_window,
        target_service=target_service,
        route=[],
        iterations=0,
        metrics_findings=[],
        log_findings=[],
        report=None,
        errors=[],
    )


class SupervisorUpdate(TypedDict):
    """What the supervisor writes back into the state."""

    route: list[AgentName]
    iterations: int
    errors: list[str]


class MetricsUpdate(TypedDict):
    """What the metrics specialist writes back into the state."""

    metrics_findings: list[MetricFinding]
    errors: list[str]


class LogsUpdate(TypedDict):
    """What the logs specialist writes back into the state."""

    log_findings: list[LogFinding]
    errors: list[str]


class CorrelationUpdate(TypedDict):
    """What the correlation node writes back into the state."""

    report: IncidentReport | None
    errors: list[str]
