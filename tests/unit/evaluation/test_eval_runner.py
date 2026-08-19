import pytest

from incident_copilot.demo.scenarios import ScenarioName
from incident_copilot.evaluation.eval_runner import (
    RunResult,
    _print_results,
    run_scenario,
    score_run,
)
from incident_copilot.evaluation.scenarios import EvalScenario
from incident_copilot.models.enums import EvidenceSource
from incident_copilot.models.report import EvidenceRef, IncidentReport, LikelyCause
from incident_copilot.services.incident_service import InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError

SCENARIO = EvalScenario(
    name=ScenarioName.BAD_DEPLOY,
    query="cart-service is returning 5xx errors after a deploy",
    target_service="cart-service",
    expected_culprit="cart-service",
)


def _report(title: str = "", rationale: str = "", detail: str = "") -> IncidentReport:
    return IncidentReport(
        summary="s",
        likely_causes=(
            LikelyCause(
                title=title or "x",
                rationale=rationale or "because",
                confidence=0.8,
                supporting_evidence=(
                    EvidenceRef(source=EvidenceSource.METRICS, detail=detail or "x"),
                ),
            ),
        ),
        next_steps=(),
        confidence=0.8,
    )


def test_culprit_in_title_scores_correct() -> None:
    assert score_run(_report(title="cart-service bad deploy"), "cart-service") is True


def test_culprit_in_rationale_scores_correct() -> None:
    report = _report(title="x", rationale="cart-service rolled a bad version")
    assert score_run(report, "cart-service") is True


def test_culprit_in_evidence_detail_scores_correct() -> None:
    report = _report(title="x", detail="cart-service error rate rose")
    assert score_run(report, "cart-service") is True


def test_match_is_case_insensitive() -> None:
    assert score_run(_report(title="CART-SERVICE issue"), "cart-service") is True


def test_culprit_absent_scores_incorrect() -> None:
    assert score_run(_report(title="fraud-api issue"), "cart-service") is False


def test_empty_likely_causes_scores_incorrect() -> None:
    report = IncidentReport(summary="s", likely_causes=(), next_steps=(), confidence=0.0)
    assert score_run(report, "cart-service") is False


class _StubService:
    def __init__(
        self, report: IncidentReport | None = None, error: Exception | None = None
    ) -> None:
        self._report = report
        self._error = error
        self.seen: InvestigationRequest | None = None

    async def investigate(self, request: InvestigationRequest) -> IncidentReport:
        self.seen = request
        if self._error:
            raise self._error
        assert self._report is not None
        return self._report


async def test_run_scenario_scores_a_successful_investigation() -> None:
    service = _StubService(report=_report(title="cart-service bad deploy"))
    result = await run_scenario(service, SCENARIO)

    assert result == RunResult(
        scenario=ScenarioName.BAD_DEPLOY, correct=True, detail="cart-service bad deploy"
    )
    assert service.seen is not None
    assert service.seen.service == "cart-service"
    assert service.seen.minutes_back == 180


async def test_run_scenario_records_an_investigation_error_as_incorrect() -> None:
    service = _StubService(error=InvestigationError("no report produced"))
    result = await run_scenario(service, SCENARIO)

    assert result.scenario == ScenarioName.BAD_DEPLOY
    assert result.correct is False
    assert "no report produced" in result.detail


async def test_run_scenario_reports_no_causes_when_the_report_is_empty() -> None:
    empty = IncidentReport(summary="s", likely_causes=(), next_steps=(), confidence=0.0)
    service = _StubService(report=empty)
    result = await run_scenario(service, SCENARIO)

    assert result.correct is False
    assert result.detail == "(no causes)"


def test_print_results_reports_per_run_per_scenario_and_overall(
    capsys: pytest.CaptureFixture[str],
) -> None:
    results = [
        RunResult(ScenarioName.BAD_DEPLOY, correct=True, detail="cart-service bad deploy"),
        RunResult(ScenarioName.BAD_DEPLOY, correct=False, detail="(no causes)"),
    ]
    _print_results(results)
    out = capsys.readouterr().out

    assert "[PASS] bad_deploy: cart-service bad deploy" in out
    assert "[FAIL] bad_deploy: (no causes)" in out
    assert "bad_deploy: 1/2" in out
    assert "Overall: 1/2" in out
