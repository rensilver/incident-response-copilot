"""Rendering of scenarios into OpenMetrics text for ``promtool`` backfill.

Timestamps are emitted in **seconds**. OpenMetrics defines them that way, and passing
milliseconds makes ``promtool`` scatter each sample into its own one-millisecond block.

Counters (``http_requests_total``, ``http_request_duration_seconds_bucket``,
``process_cpu_seconds_total``) accumulate monotonically across the window, because
``rate()`` and ``histogram_quantile()`` are meaningless over a counter that resets.
"""

from incident_copilot.demo.curves import time_grid, value_at
from incident_copilot.demo.scenarios import MetricShape, Scenario, ServiceProfile

LATENCY_BUCKETS: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

_MIB = 1024 * 1024
_REQUESTS_PER_STEP = 600.0

_HEADER = """\
# HELP http_requests_total Total HTTP requests.
# TYPE http_requests_total counter
# HELP http_request_duration_seconds Request duration.
# TYPE http_request_duration_seconds histogram
# HELP process_resident_memory_bytes Resident memory.
# TYPE process_resident_memory_bytes gauge
# HELP process_cpu_seconds_total CPU seconds consumed.
# TYPE process_cpu_seconds_total counter
"""


def _bucket_share(latency: float, upper: float) -> float:
    """Fraction of requests landing at or below ``upper`` for a given p95 latency.

    Modelled so that roughly 95% of requests fall below the current p95 value.
    """
    if upper >= latency:
        return 1.0
    return min(0.95, max(0.0, (upper / latency) ** 2 * 0.95))


def _render_service(profile: ServiceProfile, grid: list[int]) -> list[str]:
    """Render every metric line for one service across the whole grid."""
    lines: list[str] = []
    total_requests = 0.0
    total_errors = 0.0
    cpu_seconds = 0.0
    bucket_totals = dict.fromkeys(LATENCY_BUCKETS, 0.0)
    inf_total = 0.0
    last = len(grid) - 1

    for index, timestamp in enumerate(grid):
        progress = index / last if last else 1.0
        version = (
            profile.version_after if progress >= profile.anomaly_start else profile.version_before
        )

        latency = value_at(
            profile.latency_shape,
            profile.latency_base,
            profile.latency_peak,
            progress,
            profile.anomaly_start,
        )
        error_ratio = value_at(
            MetricShape.STEP if profile.latency_shape is MetricShape.STEP else MetricShape.RAMP,
            profile.error_ratio_base,
            profile.error_ratio_peak,
            progress,
            profile.anomaly_start,
        )
        memory = value_at(
            profile.memory_shape,
            profile.memory_base_mib,
            profile.memory_peak_mib,
            progress,
            profile.anomaly_start,
        )
        cpu = value_at(
            MetricShape.RAMP if profile.cpu_peak != profile.cpu_base else MetricShape.STEADY,
            profile.cpu_base,
            profile.cpu_peak,
            progress,
            profile.anomaly_start,
        )

        errors_now = _REQUESTS_PER_STEP * error_ratio
        total_requests += _REQUESTS_PER_STEP
        total_errors += errors_now
        cpu_seconds += cpu * 60.0
        inf_total += _REQUESTS_PER_STEP

        service = profile.service
        common = f'service="{service}",version="{version}"'

        lines.append(
            f'http_requests_total{{{common},status="200"}} '
            f"{total_requests - total_errors:.2f} {timestamp}"
        )
        lines.append(f'http_requests_total{{{common},status="500"}} {total_errors:.2f} {timestamp}')

        for upper in LATENCY_BUCKETS:
            bucket_totals[upper] += _REQUESTS_PER_STEP * _bucket_share(latency, upper)
            lines.append(
                f'http_request_duration_seconds_bucket{{{common},le="{upper}"}} '
                f"{bucket_totals[upper]:.2f} {timestamp}"
            )
        lines.append(
            f'http_request_duration_seconds_bucket{{{common},le="+Inf"}} '
            f"{inf_total:.2f} {timestamp}"
        )

        lines.append(f"process_resident_memory_bytes{{{common}}} {memory * _MIB:.0f} {timestamp}")
        lines.append(f"process_cpu_seconds_total{{{common}}} {cpu_seconds:.2f} {timestamp}")

    return lines


def render_openmetrics(scenario: Scenario, hours: int = 3, step_seconds: int = 60) -> str:
    """Render a scenario as OpenMetrics text ready for ``promtool`` backfill.

    Args:
        scenario: The scenario to render.
        hours: Length of the historical window.
        step_seconds: Spacing between samples.

    Returns:
        OpenMetrics text, terminated by ``# EOF``.
    """
    grid = time_grid(hours, step_seconds)
    lines = [_HEADER.rstrip("\n")]
    for profile in scenario.services:
        lines.extend(_render_service(profile, grid))
    lines.append("# EOF")
    return "\n".join(lines) + "\n"
