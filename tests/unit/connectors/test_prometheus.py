import httpx
import pytest
import respx

from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.utils.exceptions import MetricsSourceError

BASE = "http://prometheus:9090"


def _connector() -> PrometheusConnector:
    return PrometheusConnector(client=httpx.AsyncClient(), base_url=BASE)


@respx.mock
async def test_query_range_parses_matrix_response() -> None:
    respx.get(f"{BASE}/api/v1/query_range").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {"service": "cart-service"},
                            "values": [[1700000000, "0.12"], [1700000030, "0.63"]],
                        }
                    ],
                },
            },
        )
    )
    series = await _connector().query_range("up", TimeWindow.from_minutes_back(30))

    assert len(series) == 1
    assert series[0].labels["service"] == "cart-service"
    assert series[0].values == [0.12, 0.63]


@respx.mock
async def test_prometheus_error_status_raises() -> None:
    respx.get(f"{BASE}/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={"status": "error", "error": "parse error"})
    )
    with pytest.raises(MetricsSourceError, match="parse error"):
        await _connector().query_range("bad{", TimeWindow.from_minutes_back(30))


@respx.mock
async def test_http_failure_is_wrapped() -> None:
    respx.get(f"{BASE}/api/v1/query_range").mock(return_value=httpx.Response(503))
    with pytest.raises(MetricsSourceError, match="503"):
        await _connector().query_range("up", TimeWindow.from_minutes_back(30))


@respx.mock
async def test_list_services_reads_label_values() -> None:
    respx.get(f"{BASE}/api/v1/label/service/values").mock(
        return_value=httpx.Response(
            200, json={"status": "success", "data": ["cart-service", "payment-service"]}
        )
    )
    assert await _connector().list_services() == ["cart-service", "payment-service"]


async def test_aclose_releases_the_underlying_client() -> None:
    """The app builds one connector at startup and must hand its socket back on
    shutdown; without this the client leaks on every reload."""
    client = httpx.AsyncClient()
    connector = PrometheusConnector(client=client, base_url=BASE)

    await connector.aclose()

    assert client.is_closed
