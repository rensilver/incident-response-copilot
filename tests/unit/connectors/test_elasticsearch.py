from typing import Any

import pytest

from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.utils.exceptions import LogSourceError


class StubES:
    """Minimal stand-in for AsyncElasticsearch."""

    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.last_body: dict[str, Any] | None = None

    async def search(self, *, index: str, body: dict[str, Any]) -> dict[str, Any]:
        self.last_body = body
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _hit(message: str, level: str = "ERROR") -> dict[str, Any]:
    return {
        "_source": {
            "@timestamp": "2026-08-17T10:00:00Z",
            "service": "cart-service",
            "level": level,
            "message": message,
            "version": "v1.5.0",
        }
    }


async def test_search_maps_hits_and_total() -> None:
    stub = StubES({"hits": {"total": {"value": 1043}, "hits": [_hit("NullPointerException")]}})
    connector = ElasticsearchConnector(client=stub, index="app-logs")  # type: ignore[arg-type]  # stub

    finding = await connector.search(
        LogSearchCriteria(
            service="cart-service",
            window=TimeWindow.from_minutes_back(30),
            level=LogLevel.ERROR,
        )
    )

    assert finding.matched_count == 1043
    assert len(finding.samples) == 1
    assert finding.samples[0].message == "NullPointerException"
    assert finding.samples[0].version == "v1.5.0"


async def test_level_filter_is_applied_to_the_query() -> None:
    stub = StubES({"hits": {"total": {"value": 0}, "hits": []}})
    connector = ElasticsearchConnector(client=stub, index="app-logs")  # type: ignore[arg-type]  # stub

    await connector.search(
        LogSearchCriteria(
            service="cart-service",
            window=TimeWindow.from_minutes_back(30),
            level=LogLevel.ERROR,
            keyword="timeout",
        )
    )

    assert stub.last_body is not None
    filters = str(stub.last_body["query"]["bool"]["filter"])
    assert "ERROR" in filters
    assert "timeout" in str(stub.last_body["query"]["bool"])


async def test_backend_failure_is_wrapped() -> None:
    stub = StubES(RuntimeError("connection refused"))
    connector = ElasticsearchConnector(client=stub, index="app-logs")  # type: ignore[arg-type]  # stub

    with pytest.raises(LogSourceError, match="connection refused"):
        await connector.search(
            LogSearchCriteria(service="cart-service", window=TimeWindow.from_minutes_back(30))
        )
