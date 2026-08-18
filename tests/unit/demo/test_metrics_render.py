from incident_copilot.demo.metrics_render import LATENCY_BUCKETS, render_openmetrics
from incident_copilot.demo.scenarios import ScenarioName, get_scenario


def _samples(text: str, metric: str) -> list[tuple[str, float, int]]:
    """Return (labels, value, timestamp) triples for one metric name."""
    out = []
    for line in text.splitlines():
        if line.startswith(f"{metric}{{"):
            head, _, tail = line.partition("} ")
            value, _, ts = tail.partition(" ")
            out.append((head + "}", float(value), int(ts)))
    return out


def test_output_is_openmetrics_with_eof_terminator() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    assert text.endswith("# EOF\n")
    assert "# TYPE http_requests_total counter" in text


def test_timestamps_are_epoch_seconds_not_milliseconds() -> None:
    """promtool reads OpenMetrics timestamps as seconds; ms yields one block per sample."""
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    _, _, ts = _samples(text, "process_resident_memory_bytes")[0]
    assert 1_000_000_000 < ts < 10_000_000_000


def test_emits_every_metric_the_promql_templates_query() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.MEMORY_LEAK))
    for metric in (
        "http_request_duration_seconds_bucket",
        "http_requests_total",
        "process_resident_memory_bytes",
        "process_cpu_seconds_total",
    ):
        assert f"{metric}{{" in text, metric


def test_latency_histogram_has_every_bucket_including_inf() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.SLOW_DEPENDENCY))
    first_ts = _samples(text, "http_request_duration_seconds_bucket")[0][2]
    at_first = [
        labels
        for labels, _, ts in _samples(text, "http_request_duration_seconds_bucket")
        if ts == first_ts and 'service="fraud-api"' in labels
    ]
    assert len(at_first) == len(LATENCY_BUCKETS) + 1
    assert any('le="+Inf"' in labels for labels in at_first)


def test_histogram_buckets_are_cumulative_and_monotonic_over_time() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    inf = [
        (ts, value)
        for labels, value, ts in _samples(text, "http_request_duration_seconds_bucket")
        if 'le="+Inf"' in labels and 'service="cart-service"' in labels
    ]
    inf.sort()
    values = [v for _, v in inf]
    assert values == sorted(values), "counters must never decrease"
    assert values[-1] > values[0]


def test_counters_never_decrease_for_error_requests() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    errors = [
        (ts, value)
        for labels, value, ts in _samples(text, "http_requests_total")
        if 'status="500"' in labels and 'service="cart-service"' in labels
    ]
    errors.sort()
    values = [v for _, v in errors]
    assert values == sorted(values)


def test_bad_deploy_error_counter_accelerates_after_the_deploy() -> None:
    """~0 5xx before the deploy, a clear climb after it."""
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    errors = sorted(
        (ts, value)
        for labels, value, ts in _samples(text, "http_requests_total")
        if 'status="500"' in labels and 'service="cart-service"' in labels
    )
    values = [v for _, v in errors]
    mid = len(values) // 2
    growth_before = values[mid] - values[0]
    growth_after = values[-1] - values[mid]
    assert growth_after > growth_before * 5


def test_version_label_flips_for_the_bad_deploy() -> None:
    text = render_openmetrics(get_scenario(ScenarioName.BAD_DEPLOY))
    assert 'version="v1.4.2"' in text
    assert 'version="v1.5.0"' in text
