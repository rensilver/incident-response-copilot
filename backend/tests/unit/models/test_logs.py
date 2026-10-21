from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogEntry, LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow


def test_log_entry_requires_known_level() -> None:
    with pytest.raises(ValidationError):
        LogEntry(timestamp=datetime.now(UTC), service="cart-service", level="LOUD", message="x")


def test_search_criteria_defaults_limit() -> None:
    criteria = LogSearchCriteria(service="cart-service", window=TimeWindow.from_minutes_back(30))
    assert criteria.limit == 20
    assert criteria.level is None


def test_finding_reports_matched_count_independent_of_samples() -> None:
    finding = LogFinding(
        query="service:cart-service AND level:ERROR",
        matched_count=1043,
        level_breakdown={LogLevel.ERROR: 1043},
        samples=[],
    )
    assert finding.matched_count == 1043
    assert finding.samples == ()
