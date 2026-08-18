"""Primitive metric value objects."""

from datetime import UTC, datetime, timedelta
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class TimeWindow(BaseModel):
    """A closed time interval to investigate."""

    model_config = ConfigDict(frozen=True)

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _end_after_start(self) -> Self:
        """Reject windows that are empty or inverted."""
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self

    @property
    def duration_seconds(self) -> float:
        """Length of the window in seconds."""
        return (self.end - self.start).total_seconds()

    @classmethod
    def from_minutes_back(cls, minutes: int) -> "TimeWindow":
        """Build a window spanning the last ``minutes`` minutes ending now."""
        end = datetime.now(UTC)
        return cls(start=end - timedelta(minutes=minutes), end=end)


class MetricSample(BaseModel):
    """A single timestamped metric value."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    value: float


class MetricSeries(BaseModel):
    """One labelled time series."""

    model_config = ConfigDict(frozen=True)

    labels: dict[str, str]
    samples: tuple[MetricSample, ...]

    @property
    def values(self) -> list[float]:
        """All sample values in order."""
        return [s.value for s in self.samples]
