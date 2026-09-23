from datetime import UTC, datetime, timedelta

from incident_copilot.agents.prompts import (
    render_evidence,
    render_log_finding,
    render_metric_finding,
)
from incident_copilot.models.enums import LogLevel, MetricKind, TrendKind
from incident_copilot.models.findings import RawMetricFinding, TypedMetricFinding
from incident_copilot.models.logs import LogEntry, LogFinding


def _typed(anomaly: bool, summary: str = "5xx error rate rose 12.0x") -> TypedMetricFinding:
    return TypedMetricFinding(
        service="cart-service",
        query="rate(...)",
        metric_kind=MetricKind.ERROR_RATE,
        series=(),
        summary=summary,
        trend=TrendKind.ROSE,
        baseline_value=0.01,
        current_value=0.15,
        absolute_delta=0.14,
        pct_change=1400.0,
        anomaly_detected=anomaly,
    )


def _raw() -> RawMetricFinding:
    return RawMetricFinding(
        service="",
        query="up",
        series=(),
        summary="unclassified metric - value held steady near 1.0",
        trend=TrendKind.FLAT,
        baseline_value=1.0,
        current_value=1.0,
        absolute_delta=0.0,
        pct_change=0.0,
        anomaly_detected=False,
    )


def _log() -> LogFinding:
    return LogFinding(
        query="service:cart-service AND level:ERROR",
        matched_count=1043,
        level_breakdown={LogLevel.ERROR: 1043},
        samples=(),
    )


def test_no_findings_are_dropped_regardless_of_anomaly_flag() -> None:
    """anomaly_detected is advisory; filtering on it would silently hide raw findings."""
    anomalous = _typed(True, "anomalous marker")
    quiet = _typed(False, "non-anomalous marker")
    raw = _raw()

    text = render_evidence([anomalous, quiet, raw], [_log()])

    assert "anomalous marker" in text
    assert "non-anomalous marker" in text
    assert raw.summary in text


def test_metric_finding_states_its_trust_tag() -> None:
    assert "not threshold-validated" in render_metric_finding(_raw()).lower()
    assert "threshold-validated" in render_metric_finding(_typed(True)).lower()


def test_metric_finding_reports_the_advisory_flag_without_acting_on_it() -> None:
    assert "anomaly_detected=False" in render_metric_finding(_typed(False))


def test_log_finding_reports_total_matches_not_sample_count() -> None:
    text = render_log_finding(_log())
    assert "1043" in text


def test_render_evidence_marks_an_empty_section_explicitly() -> None:
    text = render_evidence([], [])
    assert "no metric findings" in text.lower()
    assert "no log findings" in text.lower()


def test_evidence_order_is_independent_of_the_order_findings_arrive_in() -> None:
    """Reducer merge order is not stable between runs. If it leaked into the prompt,
    identical evidence would produce different prompts - and LLMs weight earlier items
    more heavily, so the reasoning could drift for no real reason."""
    a = _typed(True, "alpha")
    b = _typed(False, "beta")
    c = _raw()

    assert render_evidence([a, b, c], []) == render_evidence([c, b, a], [])
    assert render_evidence([b, c, a], []) == render_evidence([a, b, c], [])


def test_threshold_validated_findings_are_rendered_first() -> None:
    text = render_evidence([_raw(), _typed(True, "validated marker")], [])
    assert text.index("validated marker") < text.index(_raw().summary)


def test_dependency_after_five_duplicate_errors_is_preserved() -> None:
    base = datetime(2026, 9, 23, tzinfo=UTC)
    samples = tuple(
        LogEntry(
            timestamp=base + timedelta(seconds=i),
            service="payment-service",
            level=LogLevel.ERROR,
            message="authorization failed",
        )
        for i in range(6)
    ) + (
        LogEntry(
            timestamp=base,
            service="payment-service",
            level=LogLevel.WARN,
            message="upstream timeout calling fraud-api after 2000ms",
            version="v2",
        ),
    )
    finding = LogFinding(
        query="service:payment-service",
        matched_count=200,
        level_breakdown={LogLevel.ERROR: 6, LogLevel.WARN: 1},
        samples=samples,
    )
    text = render_log_finding(finding)
    assert "fraud-api" in text
    assert "version=v2" in text
    assert text.count("authorization failed") == 1
    assert "sampled occurrences=6" in text
    assert "200 documents matched" in text
    assert "7 samples retrieved" in text
    assert base.isoformat() in text
    assert (base + timedelta(seconds=5)).isoformat() in text
    assert render_log_finding(finding.model_copy(update={"samples": samples[::-1]})) == text


def test_distinct_versions_of_the_same_message_are_not_merged() -> None:
    entries = tuple(
        LogEntry(
            timestamp=datetime(2026, 9, 23, tzinfo=UTC),
            service="cart-service",
            level=LogLevel.ERROR,
            message="exception",
            version=version,
        )
        for version in ("v1", "v2")
    )
    text = render_log_finding(
        LogFinding(query="q", matched_count=2, level_breakdown={}, samples=entries)
    )
    assert text.count("exception") == 2
    assert "version=v1" in text and "version=v2" in text
