"""Validated argument schemas for every tool exposed to the model."""

from pydantic import BaseModel, Field

from incident_copilot.models.enums import LogLevel, MetricKind


class MetricQueryArgs(BaseModel):
    """Arguments for a curated metric lookup."""

    service: str = Field(description="Service name, e.g. 'cart-service'")
    kind: MetricKind = Field(description="Which metric to fetch")
    minutes_back: int = Field(default=60, ge=1, le=1440, description="Window length")


class RawQueryArgs(BaseModel):
    """Arguments for the raw PromQL escape hatch."""

    query: str = Field(description="A complete PromQL expression")
    minutes_back: int = Field(default=60, ge=1, le=1440)


class LogSearchArgs(BaseModel):
    """Arguments for a log search."""

    service: str = Field(description="Service name")
    minutes_back: int = Field(default=60, ge=1, le=1440)
    level: LogLevel | None = Field(default=None, description="Optional severity filter")
    keyword: str | None = Field(default=None, description="Optional free-text match")


class LogHistogramArgs(BaseModel):
    """Arguments for a per-level log count."""

    service: str
    minutes_back: int = Field(default=60, ge=1, le=1440)
