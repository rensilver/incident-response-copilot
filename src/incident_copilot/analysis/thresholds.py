"""Deterministic trend classification and anomaly thresholds.

The LLM never does this arithmetic. A 3b model is poor at reasoning over long arrays of
numbers and adequate at reasoning over a stated delta, so the numbers are reduced here and
handed over pre-digested.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from incident_copilot.models.enums import MetricKind, TrendKind


@dataclass(frozen=True)
class ThresholdConfig:
    """Bars a change must clear to count as an anomaly, for one metric kind.

    Attributes:
        min_relative: Minimum ratio of change, e.g. ``1.5`` for a 50% move.
        min_absolute: Minimum absolute delta, in the metric's native units.
        zero_epsilon: Values at or below this count as zero.
        unit: Display unit suffix.
        scale: Multiplier applied before display, e.g. ``100`` for a ratio shown as pp.
    """

    min_relative: float
    min_absolute: float
    zero_epsilon: float
    unit: str
    scale: float = 1.0


THRESHOLDS: Mapping[MetricKind, ThresholdConfig] = {
    MetricKind.LATENCY_P95: ThresholdConfig(1.5, 0.050, 0.001, "s"),
    MetricKind.ERROR_RATE: ThresholdConfig(2.0, 0.01, 0.001, "pp", scale=100.0),
    MetricKind.MEMORY: ThresholdConfig(1.3, 50 * 1024**2, 1024**2, "MiB", scale=1 / 1024**2),
    MetricKind.CPU: ThresholdConfig(1.5, 0.1, 0.01, "cores"),
}


@dataclass(frozen=True)
class TrendAnalysis:
    """Result of comparing a window's baseline against its current value."""

    trend: TrendKind
    baseline_value: float
    current_value: float
    absolute_delta: float
    pct_change: float | None
    anomaly_detected: bool


def quartile_means(values: Sequence[float]) -> tuple[float, float]:
    """Return the mean of the first quartile and the mean of the last quartile.

    Args:
        values: Sample values in chronological order.

    Returns:
        A ``(baseline, current)`` pair.

    Raises:
        ValueError: If ``values`` is empty.
    """
    if not values:
        raise ValueError("need at least one sample to compute quartile means")
    quarter = max(1, len(values) // 4)
    first = values[:quarter]
    last = values[-quarter:]
    return sum(first) / len(first), sum(last) / len(last)


def analyse(baseline: float, current: float, config: ThresholdConfig) -> TrendAnalysis:
    """Classify a change and decide whether it clears the configured bars.

    Both a relative and an absolute bar must clear, except when the baseline is within
    ``zero_epsilon`` of zero: there the ratio is undefined, so the absolute bar alone
    decides. The absolute bar is never skipped.

    Args:
        baseline: Representative value from the start of the window.
        current: Representative value from the end of the window.
        config: Bars and units for this metric kind.

    Returns:
        The classified :class:`TrendAnalysis`.
    """
    delta = current - baseline
    baseline_is_zero = abs(baseline) <= config.zero_epsilon
    current_is_zero = abs(current) <= config.zero_epsilon

    if baseline_is_zero and current_is_zero:
        return TrendAnalysis(TrendKind.FLAT, baseline, current, delta, 0.0, False)

    if baseline_is_zero:
        # Ratio is undefined; the absolute bar alone decides.
        return TrendAnalysis(
            TrendKind.FROM_ZERO,
            baseline,
            current,
            delta,
            None,
            abs(delta) >= config.min_absolute,
        )

    pct_change = (delta / baseline) * 100.0

    if abs(delta) < config.min_absolute:
        # Below the absolute bar: treat as steady regardless of how large the ratio is.
        return TrendAnalysis(TrendKind.FLAT, baseline, current, delta, pct_change, False)

    ratio = current / baseline
    relative_clears = ratio >= config.min_relative or ratio <= 1.0 / config.min_relative
    trend = TrendKind.ROSE if delta > 0 else TrendKind.DROPPED
    return TrendAnalysis(trend, baseline, current, delta, pct_change, relative_clears)
