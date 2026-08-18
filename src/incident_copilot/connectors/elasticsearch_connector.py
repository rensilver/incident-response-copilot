"""Adapter over Elasticsearch for application logs."""

from typing import Any

from elasticsearch import AsyncElasticsearch

from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogEntry, LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.utils.exceptions import LogSourceError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


class ElasticsearchConnector(LogSource):
    """Reads application logs from a single Elasticsearch index.

    Args:
        client: An Elasticsearch async client, injected for testability.
        index: Name of the log index.
    """

    def __init__(self, client: AsyncElasticsearch, index: str) -> None:
        """Store the injected client and index name.

        Args:
            client: An Elasticsearch async client, injected for testability.
            index: Name of the log index.
        """
        self._client = client
        self._index = index

    @classmethod
    def from_settings(cls, settings: Settings) -> "ElasticsearchConnector":
        """Build a connector from application settings."""
        return cls(
            client=AsyncElasticsearch(settings.elasticsearch_url),
            index=settings.elasticsearch_log_index,
        )

    async def aclose(self) -> None:
        """Release the underlying Elasticsearch client.

        The client is long-lived — built once at startup so connections are reused —
        so the application must close it on shutdown.
        """
        await self._client.close()

    @staticmethod
    def _build_query(criteria: LogSearchCriteria) -> dict[str, Any]:
        """Build the Elasticsearch bool query for the given criteria."""
        filters: list[dict[str, Any]] = [
            {"term": {"service": criteria.service}},
            {
                "range": {
                    "@timestamp": {
                        "gte": criteria.window.start.isoformat(),
                        "lte": criteria.window.end.isoformat(),
                    }
                }
            },
        ]
        if criteria.level is not None:
            filters.append({"term": {"level": criteria.level.value}})

        query: dict[str, Any] = {"bool": {"filter": filters}}
        if criteria.keyword:
            query["bool"]["must"] = [{"match": {"message": criteria.keyword}}]
        return query

    async def _search_raw(self, body: dict[str, Any]) -> dict[str, Any]:
        """Run a search, wrapping backend failures."""
        try:
            return dict(await self._client.search(index=self._index, body=body))
        except Exception as exc:  # noqa: BLE001 - deliberately wrapping any client error
            raise LogSourceError(f"elasticsearch search failed: {exc}") from exc

    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        """Search logs matching the criteria."""
        query = self._build_query(criteria)
        body = {
            "query": query,
            "size": criteria.limit,
            "sort": [{"@timestamp": "desc"}],
        }
        response = await self._search_raw(body)

        hits = response.get("hits", {})
        samples = tuple(self._to_entry(h["_source"]) for h in hits.get("hits", []))
        breakdown: dict[LogLevel, int] = {}
        for entry in samples:
            breakdown[entry.level] = breakdown.get(entry.level, 0) + 1

        logger.debug("log_search_executed", service=criteria.service, hits=len(samples))
        return LogFinding(
            query=str(query),
            matched_count=int(hits.get("total", {}).get("value", 0)),
            level_breakdown=breakdown,
            samples=samples,
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        """Return a count of log documents per level."""
        body = {
            "size": 0,
            "query": self._build_query(LogSearchCriteria(service=service, window=window)),
            "aggs": {"levels": {"terms": {"field": "level"}}},
        }
        response = await self._search_raw(body)
        buckets = response.get("aggregations", {}).get("levels", {}).get("buckets", [])
        return {str(b["key"]): int(b["doc_count"]) for b in buckets}

    @staticmethod
    def _to_entry(source: dict[str, Any]) -> LogEntry:
        """Map an Elasticsearch ``_source`` document to a :class:`LogEntry`."""
        return LogEntry(
            timestamp=source["@timestamp"],
            service=source["service"],
            level=LogLevel(source["level"]),
            message=source["message"],
            version=source.get("version"),
            trace_id=source.get("trace_id"),
        )
