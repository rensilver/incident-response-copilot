import pytest
from pydantic import ValidationError

from incident_copilot.models.enums import AgentName, EvidenceSource
from incident_copilot.models.report import (
    EvidenceRef,
    IncidentReport,
    LikelyCause,
    RouteDecision,
)


def _cause(title: str, confidence: float, with_evidence: bool = True) -> LikelyCause:
    return LikelyCause(
        title=title,
        rationale="because the numbers say so",
        confidence=confidence,
        supporting_evidence=(
            [EvidenceRef(source=EvidenceSource.METRICS, detail="p95 rose 5.2x")]
            if with_evidence
            else []
        ),
    )


def test_causes_are_sorted_by_descending_confidence() -> None:
    report = IncidentReport(
        summary="s",
        likely_causes=[_cause("low", 0.2), _cause("high", 0.9), _cause("mid", 0.5)],
        next_steps=["roll back"],
        confidence=0.7,
    )
    assert [c.title for c in report.likely_causes] == ["high", "mid", "low"]


def test_causes_without_evidence_are_dropped() -> None:
    report = IncidentReport(
        summary="s",
        likely_causes=[_cause("grounded", 0.4), _cause("invented", 0.99, with_evidence=False)],
        next_steps=[],
        confidence=0.4,
    )
    assert [c.title for c in report.likely_causes] == ["grounded"]


def test_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        _cause("x", 1.4)


def test_route_decision_accepts_specialist_agents() -> None:
    decision = RouteDecision(agents=[AgentName.METRICS, AgentName.LOGS], reasoning="both")
    assert AgentName.METRICS in decision.agents


def test_route_decision_rejects_empty_route() -> None:
    with pytest.raises(ValidationError):
        RouteDecision(agents=[], reasoning="none")
