"""Log domain models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from incident_copilot.models.enums import LogLevel
from incident_copilot.models.metrics import TimeWindow


class LogEntry(BaseModel):
    """A single log document."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    service: str
    level: LogLevel
    message: str
    version: str | None = None
    trace_id: str | None = None


class LogSearchCriteria(BaseModel):
    """Narrow, validated inputs for a log search."""

    model_config = ConfigDict(frozen=True)

    service: str
    window: TimeWindow
    level: LogLevel | None = None
    keyword: str | None = None
    limit: int = Field(default=20, ge=1, le=200)


class LogFinding(BaseModel):
    """Result of a log search.

    ``matched_count`` is the total number of matching documents, which is deliberately
    independent of ``samples``: the agent needs to know that 1043 errors occurred even
    though only 20 are shown.
    """

    model_config = ConfigDict(frozen=True)

    query: str
    matched_count: int = Field(ge=0)
    level_breakdown: dict[LogLevel, int]
    samples: tuple[LogEntry, ...]
