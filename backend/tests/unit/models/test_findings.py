import pytest
from pydantic import ValidationError

from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.findings import (
    RAW_FINDING_CAVEAT,
    RawMetricFinding,
    TypedMetricFinding,
    metric_finding_adapter,
)


def _typed(**overrides: object) -> TypedMetricFinding:
    base: dict[str, object] = {
        "service": "cart-service",
        "query": 'rate(http_requests_total{service="cart-service"}[5m])',
        "metric_kind": MetricKind.ERROR_RATE,
        "series": [],
        "summary": "5xx error rate rose 12.0x, from 1.2pp to 15.0pp",
        "trend": TrendKind.ROSE,
        "baseline_value": 0.012,
        "current_value": 0.15,
        "absolute_delta": 0.138,
        "pct_change": 1150.0,
        "anomaly_detected": True,
    }
    return TypedMetricFinding(**(base | overrides))  # type: ignore[arg-type]  # test helper


def _raw(**overrides: object) -> RawMetricFinding:
    base: dict[str, object] = {
        "service": "cart-service",
        "query": "up",
        "series": [],
        "summary": f"{RAW_FINDING_CAVEAT} value held steady near 1.0",
        "trend": TrendKind.FLAT,
        "baseline_value": 1.0,
        "current_value": 1.0,
        "absolute_delta": 0.0,
        "pct_change": 0.0,
        "anomaly_detected": False,
    }
    return RawMetricFinding(**(base | overrides))  # type: ignore[arg-type]  # test helper


def test_typed_finding_is_threshold_validated() -> None:
    assert _typed().threshold_validated is True


def test_raw_finding_is_not_threshold_validated() -> None:
    assert _raw().threshold_validated is False


def test_threshold_validated_is_serialized() -> None:
    assert _typed().model_dump()["threshold_validated"] is True
    assert _raw().model_dump()["threshold_validated"] is False
    assert '"threshold_validated":false' in _raw().model_dump_json().replace(" ", "")


def test_round_trip_through_discriminator_preserves_flag() -> None:
    for finding, expected in ((_typed(), True), (_raw(), False)):
        restored = metric_finding_adapter.validate_python(finding.model_dump())
        assert restored.threshold_validated is expected
        assert type(restored) is type(finding)


def test_threshold_validated_cannot_be_overridden() -> None:
    assert _raw(threshold_validated=True).threshold_validated is False


def test_raw_summary_carries_caveat() -> None:
    assert _raw().summary.startswith(RAW_FINDING_CAVEAT)


def test_pct_change_must_be_none_for_from_zero() -> None:
    with pytest.raises(ValidationError, match="pct_change must be None iff"):
        _typed(trend=TrendKind.FROM_ZERO, pct_change=800.0)


def test_pct_change_required_when_not_from_zero() -> None:
    with pytest.raises(ValidationError, match="pct_change must be None iff"):
        _typed(trend=TrendKind.ROSE, pct_change=None)


def test_from_zero_with_none_pct_change_is_valid() -> None:
    finding = _typed(trend=TrendKind.FROM_ZERO, pct_change=None)
    assert finding.pct_change is None
