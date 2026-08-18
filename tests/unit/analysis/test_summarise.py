from incident_copilot.analysis.summarise import render_summary
from incident_copilot.analysis.thresholds import THRESHOLDS, analyse
from incident_copilot.models.enums import MetricKind

ERROR_RATE = THRESHOLDS[MetricKind.ERROR_RATE]
LATENCY = THRESHOLDS[MetricKind.LATENCY_P95]
MEMORY = THRESHOLDS[MetricKind.MEMORY]


def test_rose_states_ratio_and_endpoints() -> None:
    text = render_summary("p95 latency", analyse(0.12, 0.63, LATENCY), LATENCY)
    assert text == "p95 latency rose 5.2x, from 0.12s to 0.63s"


def test_dropped_states_percentage() -> None:
    text = render_summary("p95 latency", analyse(0.60, 0.15, LATENCY), LATENCY)
    assert text == "p95 latency fell 75%, from 0.60s to 0.15s"


def test_flat_avoids_any_ratio() -> None:
    text = render_summary("resident memory", analyse(512 * 1024**2, 513 * 1024**2, MEMORY), MEMORY)
    assert text == "resident memory held steady near 512.00MiB"
    assert "x," not in text


def test_from_zero_never_renders_a_ratio() -> None:
    text = render_summary("5xx error rate", analyse(0.0, 0.153, ERROR_RATE), ERROR_RATE)
    assert text == (
        "5xx error rate emerged from a near-zero baseline, reaching 15.30pp "
        "(no ratio is meaningful)"
    )
    assert "x," not in text
