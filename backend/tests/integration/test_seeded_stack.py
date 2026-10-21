from collections.abc import AsyncIterator

import httpx
import pytest
from elasticsearch import AsyncElasticsearch

from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.models.enums import LogLevel, MetricKind
from incident_copilot.models.logs import LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.prometheus_tools import build_metrics_tools

pytestmark = pytest.mark.integration

PROMETHEUS = "http://localhost:9090"
ELASTICSEARCH = "http://localhost:9200"


def _metrics() -> PrometheusConnector:
    return PrometheusConnector(client=httpx.AsyncClient(timeout=30.0), base_url=PROMETHEUS)


def _tool(name: str):  # type: ignore[no-untyped-def]  # test helper
    return next(t for t in build_metrics_tools(_metrics()) if t.name == name)


@pytest.fixture
async def logs() -> AsyncIterator[ElasticsearchConnector]:
    """An ES connector whose transport is closed after the test."""
    client = AsyncElasticsearch(ELASTICSEARCH)
    try:
        yield ElasticsearchConnector(client=client, index="app-logs")
    finally:
        await client.close()


async def test_seeded_services_are_discoverable() -> None:
    services = await _metrics().list_services()
    assert {"cart-service", "checkout-service", "fraud-api", "payment-service"} <= set(services)


async def test_bad_deploy_error_rate_is_detected_as_an_anomaly() -> None:
    finding = await _tool("get_service_metric").ainvoke(
        {"service": "cart-service", "kind": MetricKind.ERROR_RATE, "minutes_back": 180}
    )
    assert finding.anomaly_detected is True
    assert finding.current_value > finding.baseline_value


async def test_memory_leak_shows_growth_on_the_culprit_service() -> None:
    finding = await _tool("get_service_metric").ainvoke(
        {"service": "checkout-service", "kind": MetricKind.MEMORY, "minutes_back": 180}
    )
    assert finding.current_value > finding.baseline_value
    assert "MiB" in finding.summary


async def test_slow_dependency_upstream_p95_exceeds_the_downstream() -> None:
    """fraud-api is the cause; payment-service is the symptom."""
    upstream = await _tool("get_service_metric").ainvoke(
        {"service": "fraud-api", "kind": MetricKind.LATENCY_P95, "minutes_back": 180}
    )
    downstream = await _tool("get_service_metric").ainvoke(
        {"service": "payment-service", "kind": MetricKind.LATENCY_P95, "minutes_back": 180}
    )
    assert upstream.current_value > downstream.current_value


async def test_term_filters_match_because_fields_are_keyword_typed(
    logs: ElasticsearchConnector,
) -> None:
    """Guards the dynamic-mapping trap: `text` fields would make this return zero."""
    finding = await logs.search(
        LogSearchCriteria(
            service="cart-service",
            window=TimeWindow.from_minutes_back(180),
            level=LogLevel.ERROR,
        )
    )
    assert finding.matched_count > 0
    assert all(entry.service == "cart-service" for entry in finding.samples)


async def test_bad_deploy_errors_are_tagged_with_the_new_version(
    logs: ElasticsearchConnector,
) -> None:
    finding = await logs.search(
        LogSearchCriteria(
            service="cart-service",
            window=TimeWindow.from_minutes_back(180),
            keyword="NullPointerException",
        )
    )
    assert finding.matched_count > 0
    assert any(entry.version == "v1.5.0" for entry in finding.samples)
