from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow


def test_time_window_rejects_non_positive_duration() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="end must be after start"):
        TimeWindow(start=now, end=now)


def test_time_window_duration_seconds() -> None:
    start = datetime.now(UTC)
    window = TimeWindow(start=start, end=start + timedelta(minutes=30))
    assert window.duration_seconds == 1800.0


def test_from_minutes_back_spans_requested_window() -> None:
    window = TimeWindow.from_minutes_back(60)
    assert 3599 <= window.duration_seconds <= 3601


def test_series_values_extracts_floats() -> None:
    now = datetime.now(UTC)
    series = MetricSeries(
        labels={"service": "cart-service"},
        samples=[MetricSample(timestamp=now, value=1.5), MetricSample(timestamp=now, value=2.5)],
    )
    assert series.values == [1.5, 2.5]
