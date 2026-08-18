from typing import Any

import pytest

from incident_copilot.models.report import EvidenceRef, IncidentReport, LikelyCause
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationError

REPORT = IncidentReport(
    summary="cart-service regression",
    likely_causes=(
        LikelyCause(
            title="bad deploy",
            rationale="5xx stepped up",
            confidence=0.9,
            supporting_evidence=(EvidenceRef(source="metrics", detail="error rate rose"),),
        ),
    ),
    next_steps=("roll back",),
    confidence=0.9,
)


class StubGraph:
    def __init__(self, final: dict[str, Any]) -> None:
        self.final = final
        self.seen: dict[str, Any] | None = None

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        self.seen = state
        return self.final


async def test_returns_the_report_from_the_graph() -> None:
    graph = StubGraph({"report": REPORT, "errors": []})
    service = IncidentService(graph)

    report = await service.investigate(
        InvestigationRequest(query="why is cart-service failing?", service="cart-service")
    )

    assert report.summary == "cart-service regression"


async def test_generates_a_correlation_id_per_investigation() -> None:
    graph = StubGraph({"report": REPORT, "errors": []})
    service = IncidentService(graph)

    await service.investigate(InvestigationRequest(query="q"))
    first = graph.seen["correlation_id"]  # type: ignore[index]
    await service.investigate(InvestigationRequest(query="q"))
    second = graph.seen["correlation_id"]  # type: ignore[index]

    assert first and second and first != second


async def test_request_window_reaches_the_graph() -> None:
    graph = StubGraph({"report": REPORT, "errors": []})
    service = IncidentService(graph)

    await service.investigate(InvestigationRequest(query="q", minutes_back=120))

    window = graph.seen["time_window"]  # type: ignore[index]
    assert 7100 <= window.duration_seconds <= 7300


async def test_missing_report_raises_a_domain_error_carrying_the_graph_errors() -> None:
    graph = StubGraph({"report": None, "errors": ["correlation failed: bad json"]})
    service = IncidentService(graph)

    with pytest.raises(InvestigationError, match="bad json"):
        await service.investigate(InvestigationRequest(query="q"))


async def test_missing_report_with_no_errors_still_raises() -> None:
    """The graph can return no report and no explanation; the service must not hand
    None back to the API layer regardless."""
    graph = StubGraph({"report": None, "errors": []})
    service = IncidentService(graph)

    with pytest.raises(InvestigationError, match="no report produced"):
        await service.investigate(InvestigationRequest(query="q"))


async def test_a_wrong_typed_report_is_rejected_like_a_missing_one() -> None:
    """The graph returns an untyped mapping, so the service is the boundary that
    proves the report is a report before the API layer serialises it."""
    graph = StubGraph({"report": {"summary": "not a model"}, "errors": []})
    service = IncidentService(graph)

    with pytest.raises(InvestigationError):
        await service.investigate(InvestigationRequest(query="q"))


def test_request_rejects_an_out_of_range_window() -> None:
    with pytest.raises(ValueError):
        InvestigationRequest(query="q", minutes_back=100_000)


def test_request_rejects_an_empty_query() -> None:
    with pytest.raises(ValueError):
        InvestigationRequest(query="")
