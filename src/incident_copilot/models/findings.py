"""Metric findings produced by the metrics tooling.

A finding from a curated, threshold-checked metric and a finding from a raw PromQL
escape-hatch query are different things, so they are different types joined by a
discriminated union. Modelling the difference as ``metric_kind: MetricKind | None`` would
push a null check onto every consumer, and adding a ``RAW`` member to ``MetricKind`` would
make an invalid tool call representable by the model (see spec §3.4).
"""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, Field, TypeAdapter, computed_field, model_validator

from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.metrics import MetricSeries

RAW_FINDING_CAVEAT = "unclassified metric — not threshold-validated, review the numbers directly:"


class MetricFindingBase(BaseModel):
    """Fields shared by every metric finding.

    Consumers that do not care about ``metric_kind`` read this base and never narrow the
    union.
    """

    service: str
    query: str
    series: tuple[MetricSeries, ...]
    summary: str
    trend: TrendKind
    baseline_value: float
    current_value: float
    absolute_delta: float
    pct_change: float | None
    anomaly_detected: bool
    """Advisory only. No pipeline stage may exclude a finding because this is False."""

    _threshold_validated: ClassVar[bool]

    @computed_field  # type: ignore[prop-decorator]  # pydantic requires this order
    @property
    def threshold_validated(self) -> bool:
        """Whether this finding was checked against configured thresholds."""
        return self._threshold_validated

    @model_validator(mode="after")
    def _pct_change_matches_trend(self) -> Self:
        """``pct_change`` is absent exactly when the baseline was ~zero."""
        if (self.pct_change is None) != (self.trend is TrendKind.FROM_ZERO):
            raise ValueError("pct_change must be None iff trend is FROM_ZERO")
        return self


class TypedMetricFinding(MetricFindingBase):
    """A finding for a curated ``MetricKind``, checked against configured thresholds."""

    source: Literal["typed"] = "typed"
    metric_kind: MetricKind

    _threshold_validated: ClassVar[bool] = True


class RawMetricFinding(MetricFindingBase):
    """A finding from a raw PromQL query, with no thresholds to check against."""

    source: Literal["raw"] = "raw"

    _threshold_validated: ClassVar[bool] = False


MetricFinding = Annotated[TypedMetricFinding | RawMetricFinding, Field(discriminator="source")]

metric_finding_adapter: TypeAdapter[TypedMetricFinding | RawMetricFinding] = TypeAdapter(
    MetricFinding
)
