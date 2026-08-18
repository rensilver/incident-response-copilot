"""Deterministic value curves for seeded metrics.

Pure functions of ``progress`` (0.0 at the start of the window, 1.0 at the end), so the
generated data is reproducible and unit-testable without touching Prometheus.
"""

import time

from incident_copilot.demo.scenarios import MetricShape

_SAWTOOTH_CYCLES = 3


def time_grid(hours: int, step_seconds: int) -> list[int]:
    """Build ascending epoch-second timestamps covering the last ``hours`` hours.

    The grid ends one step before "now" so every point is unambiguously historical.

    Args:
        hours: Length of the window in hours.
        step_seconds: Spacing between samples.

    Returns:
        Ascending epoch seconds.
    """
    end = int(time.time()) - step_seconds
    start = end - hours * 3600
    return list(range(start, end, step_seconds))


def value_at(
    shape: MetricShape,
    base: float,
    peak: float,
    progress: float,
    anomaly_start: float,
) -> float:
    """Return the metric value at a point in the window.

    Args:
        shape: Which curve to follow.
        base: Healthy baseline value.
        peak: Value at the worst point of the incident.
        progress: Position in the window, 0.0 to 1.0.
        anomaly_start: Progress at which degradation begins.

    Returns:
        The value at ``progress``.
    """
    if shape is MetricShape.STEADY or progress < anomaly_start:
        return base

    span = 1.0 - anomaly_start
    local = (progress - anomaly_start) / span if span > 0 else 1.0

    if shape is MetricShape.STEP:
        return peak
    if shape is MetricShape.RAMP:
        return base + (peak - base) * local

    # SAWTOOTH: climb toward peak, drop back to base on each restart.
    cycle = (local * _SAWTOOTH_CYCLES) % 1.0
    return base + (peak - base) * cycle
