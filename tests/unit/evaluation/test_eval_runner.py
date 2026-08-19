from incident_copilot.evaluation.eval_runner import score_run
from incident_copilot.models.enums import EvidenceSource
from incident_copilot.models.report import EvidenceRef, IncidentReport, LikelyCause


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
