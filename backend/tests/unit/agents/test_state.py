import operator
from typing import Annotated, get_args, get_origin, get_type_hints

from incident_copilot.agents.state import InvestigationState, initial_state
from incident_copilot.models.enums import AgentName
from incident_copilot.models.metrics import TimeWindow


def _annotation(field: str) -> object:
    return get_type_hints(InvestigationState, include_extras=True)[field]


def test_accumulating_fields_use_the_add_reducer() -> None:
    """Parallel specialists both write findings; without a reducer one would clobber the other."""
    for field in ("metrics_findings", "log_findings", "errors"):
        annotation = _annotation(field)
        assert get_origin(annotation) is Annotated, field
        assert operator.add in get_args(annotation), field


def test_scalar_fields_do_not_accumulate() -> None:
    for field in ("correlation_id", "query", "route", "iterations", "report"):
        assert get_origin(_annotation(field)) is not Annotated, field


def test_initial_state_starts_empty_and_unrouted() -> None:
    state = initial_state(
        correlation_id="abc-123",
        query="why is cart-service failing?",
        time_window=TimeWindow.from_minutes_back(60),
        target_service="cart-service",
    )
    assert state["correlation_id"] == "abc-123"
    assert state["route"] == []
    assert state["iterations"] == 0
    assert state["metrics_findings"] == []
    assert state["log_findings"] == []
    assert state["errors"] == []
    assert state["report"] is None


def test_initial_state_allows_no_target_service() -> None:
    state = initial_state(
        correlation_id="x",
        query="something is wrong",
        time_window=TimeWindow.from_minutes_back(30),
        target_service=None,
    )
    assert state["target_service"] is None
    assert AgentName.SUPERVISOR not in state["route"]
