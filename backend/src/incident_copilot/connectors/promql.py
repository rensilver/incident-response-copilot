"""Translation from semantic metric kinds to PromQL.

Keeping this table in one place is what lets the tool layer expose a small enum to the
model instead of asking a 3b model to author PromQL.
"""

import re
from collections.abc import Mapping

from incident_copilot.models.enums import MetricKind
from incident_copilot.utils.exceptions import MetricsSourceError

_SERVICE_RE = re.compile(r"^[a-zA-Z0-9_-]{1,63}$")

_TEMPLATES: Mapping[MetricKind, str] = {
    MetricKind.LATENCY_P95: (
        "histogram_quantile(0.95, sum by (le) (rate("
        'http_request_duration_seconds_bucket{{service="{service}"}}[5m])))'
    ),
    MetricKind.ERROR_RATE: (
        'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m]))'
        ' / sum(rate(http_requests_total{{service="{service}"}}[5m]))'
    ),
    MetricKind.MEMORY: 'process_resident_memory_bytes{{service="{service}"}}',
    MetricKind.CPU: 'rate(process_cpu_seconds_total{{service="{service}"}}[5m])',
}

METRIC_LABELS: Mapping[MetricKind, str] = {
    MetricKind.LATENCY_P95: "p95 latency",
    MetricKind.ERROR_RATE: "5xx error rate",
    MetricKind.MEMORY: "resident memory",
    MetricKind.CPU: "CPU usage",
}


def build_promql(kind: MetricKind, service: str) -> str:
    """Build the PromQL expression for a metric kind and service.

    Args:
        kind: The semantic metric requested.
        service: Target service name.

    Returns:
        A PromQL expression.

    Raises:
        MetricsSourceError: If the service name is not a safe identifier.
    """
    if not _SERVICE_RE.match(service):
        raise MetricsSourceError(f"invalid service name: {service!r}")
    return _TEMPLATES[kind].format(service=service)
