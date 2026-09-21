from datetime import UTC, datetime, timedelta

import pytest

from incident_copilot.connectors.base import MetricsSource
from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.findings import RAW_FINDING_CAVEAT
from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow
from incident_copilot.tools.prometheus_tools import build_metrics_tools


class StubMetrics(MetricsSource):
    def __init__(self, values: list[float]) -> None:
        self.values = values
        self.last_query: str | None = None
        self.last_window: TimeWindow | None = None

    async def query_range(
        self, query: str, window: TimeWindow, step: str = "30s"
    ) -> list[MetricSeries]:
        self.last_query = query
        self.last_window = window
        base = datetime.now(UTC) - timedelta(minutes=len(self.values))
        return [
            MetricSeries(
                labels={"service": "cart-service"},
                samples=tuple(
                    MetricSample(timestamp=base + timedelta(minutes=i), value=v)
                    for i, v in enumerate(self.values)
                ),
            )
        ]

    async def list_services(self) -> list[str]:
        return ["cart-service", "payment-service"]


def _tool(source: MetricsSource, name: str):  # type: ignore[no-untyped-def]  # test helper
    return next(t for t in build_metrics_tools(source) if t.name == name)


async def test_get_service_metric_returns_typed_threshold_validated_finding() -> None:
    source = StubMetrics([0.12] * 4 + [0.63] * 4)
    finding = await _tool(source, "get_service_metric").ainvoke(
        {"service": "cart-service", "kind": MetricKind.LATENCY_P95, "minutes_back": 60}
    )

    assert finding.threshold_validated is True
    assert finding.metric_kind is MetricKind.LATENCY_P95
    assert finding.trend is TrendKind.ROSE
    assert finding.anomaly_detected is True
    assert "rose" in finding.summary
    assert "histogram_quantile" in (source.last_query or "")


async def test_raw_query_returns_unvalidated_finding_with_caveat() -> None:
    source = StubMetrics([1.0, 1.0, 5.0, 5.0])
    finding = await _tool(source, "raw_promql_query").ainvoke({"query": "up", "minutes_back": 30})

    assert finding.threshold_validated is False
    assert finding.anomaly_detected is False
    assert finding.summary.startswith(RAW_FINDING_CAVEAT)
    assert not hasattr(finding, "metric_kind")


async def test_list_services_tool() -> None:
    result = await _tool(StubMetrics([1.0]), "list_services").ainvoke({})
    assert result == ["cart-service", "payment-service"]


async def test_empty_series_yields_flat_non_anomalous_finding() -> None:
    source = StubMetrics([])
    finding = await _tool(source, "get_service_metric").ainvoke(
        {"service": "cart-service", "kind": MetricKind.CPU, "minutes_back": 30}
    )
    assert finding.trend is TrendKind.FLAT
    assert finding.anomaly_detected is False
    assert "no data" in finding.summary.lower()


@pytest.mark.parametrize("name", ["get_service_metric", "raw_promql_query"])
@pytest.mark.parametrize("minutes_back", [None, 30])
async def test_standalone_metric_tools_keep_relative_windows(
    name: str, minutes_back: int | None
) -> None:
    source = StubMetrics([])
    args = (
        {"service": "cart-service", "kind": MetricKind.CPU}
        if name == "get_service_metric"
        else {"query": "up"}
    )
    if minutes_back is not None:
        args["minutes_back"] = minutes_back
    before = datetime.now(UTC)
    await _tool(source, name).ainvoke(args)
    after = datetime.now(UTC)
    assert source.last_window is not None
    assert source.last_window.duration_seconds == (minutes_back or 60) * 60
    assert before <= source.last_window.end <= after
