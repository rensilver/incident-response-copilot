import pytest

from incident_copilot.analysis.thresholds import THRESHOLDS, analyse, quartile_means
from incident_copilot.models.enums import MetricKind, TrendKind

ERROR_RATE = THRESHOLDS[MetricKind.ERROR_RATE]
LATENCY = THRESHOLDS[MetricKind.LATENCY_P95]


def test_bad_deploy_zero_to_fifteen_percent_fires() -> None:
    """The flagship demo scenario: 0 -> 15pp must flag despite an undefined ratio."""
    result = analyse(0.0, 0.15, ERROR_RATE)
    assert result.trend is TrendKind.FROM_ZERO
    assert result.pct_change is None
    assert result.anomaly_detected is True


def test_tiny_emergence_below_epsilon_is_flat_and_quiet() -> None:
    result = analyse(0.0001, 0.0003, ERROR_RATE)
    assert result.trend is TrendKind.FLAT
    assert result.anomaly_detected is False


def test_from_zero_still_respects_absolute_bar() -> None:
    """Above the zero epsilon but below the absolute bar: classified, not flagged."""
    result = analyse(0.0, 0.002, ERROR_RATE)
    assert result.trend is TrendKind.FROM_ZERO
    assert result.anomaly_detected is False


def test_relative_noise_on_near_zero_baseline_is_suppressed() -> None:
    """0.001s -> 0.005s is '5x' and meaningless."""
    result = analyse(0.001, 0.005, LATENCY)
    assert result.anomaly_detected is False


def test_genuine_latency_regression_fires() -> None:
    result = analyse(0.12, 0.63, LATENCY)
    assert result.trend is TrendKind.ROSE
    assert result.anomaly_detected is True
    assert result.pct_change == pytest.approx(425.0)


def test_both_values_zero_is_flat_with_zero_pct_change() -> None:
    result = analyse(0.0, 0.0, ERROR_RATE)
    assert result.trend is TrendKind.FLAT
    assert result.pct_change == 0.0


def test_dropped_to_zero_is_minus_one_hundred_percent() -> None:
    result = analyse(0.5, 0.0, LATENCY)
    assert result.trend is TrendKind.DROPPED
    assert result.pct_change == pytest.approx(-100.0)
    assert result.anomaly_detected is True


def test_quartile_means_uses_first_and_last_quarter() -> None:
    baseline, current = quartile_means([1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 9.0, 9.0])
    assert baseline == pytest.approx(1.0)
    assert current == pytest.approx(9.0)


def test_quartile_means_rejects_empty() -> None:
    with pytest.raises(ValueError, match="at least one sample"):
        quartile_means([])
