import pytest

from incident_copilot.connectors.promql import build_promql
from incident_copilot.models.enums import MetricKind
from incident_copilot.utils.exceptions import MetricsSourceError


def test_latency_uses_histogram_quantile() -> None:
    query = build_promql(MetricKind.LATENCY_P95, "cart-service")
    assert query == (
        "histogram_quantile(0.95, sum by (le) (rate("
        'http_request_duration_seconds_bucket{service="cart-service"}[5m])))'
    )


def test_error_rate_is_a_ratio_of_rates() -> None:
    query = build_promql(MetricKind.ERROR_RATE, "cart-service")
    assert query.startswith('sum(rate(http_requests_total{service="cart-service",status=~"5.."}')
    assert "/" in query


def test_every_metric_kind_has_a_template() -> None:
    for kind in MetricKind:
        assert build_promql(kind, "svc")


@pytest.mark.parametrize("bad", ['cart"} or up{', "svc; drop", "svc name", ""])
def test_service_names_are_validated(bad: str) -> None:
    """Service names are interpolated into PromQL, so they must be constrained."""
    with pytest.raises(MetricsSourceError, match="invalid service name"):
        build_promql(MetricKind.CPU, bad)
