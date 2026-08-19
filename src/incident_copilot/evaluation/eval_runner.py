"""Scores the seeded scenarios against their expected root cause on the live stack.

Not part of `make test` - the whole point is measuring real model behaviour, which
needs a real Prometheus, Elasticsearch and LLM. Run manually via `make eval`.
"""

from dataclasses import dataclass
from typing import Protocol

from incident_copilot.demo.scenarios import ScenarioName
from incident_copilot.evaluation.scenarios import EvalScenario
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError


class _Investigator(Protocol):
    """The part of IncidentService this module depends on - lets tests pass a stub."""

    async def investigate(self, request: InvestigationRequest) -> IncidentReport: ...


@dataclass(frozen=True)
class RunResult:
    """The outcome of one scenario run.

    Attributes:
        scenario: Which seeded scenario this run was.
        correct: Whether the top-ranked cause named the expected culprit.
        detail: The top cause's title, or the error, for the printed transcript.
    """

    scenario: ScenarioName
    correct: bool
    detail: str


def score_run(report: IncidentReport, expected_culprit: str) -> bool:
    """Whether the top-ranked cause mentions the expected culprit.

    Args:
        report: The structured report to score.
        expected_culprit: Ground-truth service name to look for.

    Returns:
        Whether ``expected_culprit`` appears in the top cause's title, rationale, or
        supporting evidence, case-insensitively.
    """
    if not report.likely_causes:
        return False
    top = report.likely_causes[0]
    haystack = " ".join(
        [top.title, top.rationale, *(e.detail for e in top.supporting_evidence)]
    ).lower()
    return expected_culprit.lower() in haystack


async def run_scenario(service: _Investigator, scenario: EvalScenario) -> RunResult:
    """Run one scenario once and score it.

    A raised InvestigationError is caught and scored as incorrect rather than
    propagated: one bad run must not abort the other 8 in a full eval pass.

    Args:
        service: The investigation orchestrator to run against.
        scenario: The scenario to run.

    Returns:
        The scored outcome.
    """
    request = InvestigationRequest(
        query=scenario.query, service=scenario.target_service, minutes_back=180
    )
    try:
        report = await service.investigate(request)
    except InvestigationError as exc:
        return RunResult(scenario.name, correct=False, detail=f"error: {exc}")

    correct = score_run(report, scenario.expected_culprit)
    detail = report.likely_causes[0].title if report.likely_causes else "(no causes)"
    return RunResult(scenario.name, correct=correct, detail=detail)
