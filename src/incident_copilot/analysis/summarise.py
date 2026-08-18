"""Human-readable rendering of a trend analysis.

Each :class:`TrendKind` has its own template, so no code path ever divides by a
near-zero baseline and prints a nonsensical ratio.
"""

from incident_copilot.analysis.thresholds import ThresholdConfig, TrendAnalysis
from incident_copilot.models.enums import TrendKind


def _fmt(value: float, config: ThresholdConfig) -> str:
    """Format a value in its display unit."""
    return f"{value * config.scale:.2f}{config.unit}"


def render_summary(label: str, analysis: TrendAnalysis, config: ThresholdConfig) -> str:
    """Render a one-line description of a change.

    Args:
        label: Human name of the metric, e.g. ``"p95 latency"``.
        analysis: The classified change.
        config: Units for display.

    Returns:
        A sentence stating the direction and the endpoints.
    """
    start = _fmt(analysis.baseline_value, config)
    end = _fmt(analysis.current_value, config)

    if analysis.trend is TrendKind.FROM_ZERO:
        return f"{label} emerged from a near-zero baseline, reaching {end} (no ratio is meaningful)"
    if analysis.trend is TrendKind.FLAT:
        return f"{label} held steady near {start}"
    if analysis.trend is TrendKind.ROSE:
        ratio = analysis.current_value / analysis.baseline_value
        return f"{label} rose {ratio:.1f}x, from {start} to {end}"
    drop_pct = abs(analysis.pct_change or 0.0)
    return f"{label} fell {drop_pct:.0f}%, from {start} to {end}"
