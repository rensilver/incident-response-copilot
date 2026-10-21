"""Adapter over the Prometheus HTTP API."""

from datetime import datetime
from typing import Any

import httpx

from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import MetricsSource
from incident_copilot.models.metrics import MetricSample, MetricSeries, TimeWindow
from incident_copilot.utils.exceptions import MetricsSourceError
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


class PrometheusConnector(MetricsSource):
    """Reads metrics from Prometheus over its HTTP API.

    Args:
        client: An httpx client, injected so tests can mock the transport.
        base_url: Root URL of the Prometheus server.
    """

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        """Store the injected client and server root.

        Args:
            client: An httpx client, injected so tests can mock the transport.
            base_url: Root URL of the Prometheus server.
        """
        self._client = client
        self._base_url = base_url.rstrip("/")

    @classmethod
    def from_settings(cls, settings: Settings) -> "PrometheusConnector":
        """Build a connector from application settings."""
        return cls(client=httpx.AsyncClient(timeout=30.0), base_url=settings.prometheus_url)

    async def aclose(self) -> None:
        """Release the underlying HTTP client.

        The client is long-lived — built once at startup so connections are reused —
        so the application must close it on shutdown.
        """
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, str]) -> Any:
        """Issue a GET and return the ``data`` payload.

        Raises:
            MetricsSourceError: On transport failure or a non-success Prometheus status.
        """
        try:
            response = await self._client.get(f"{self._base_url}{path}", params=params)
        except httpx.HTTPError as exc:
            raise MetricsSourceError(f"prometheus request failed: {exc}") from exc

        if response.status_code != httpx.codes.OK:
            raise MetricsSourceError(f"prometheus returned HTTP {response.status_code} for {path}")

        payload = response.json()
        if payload.get("status") != "success":
            raise MetricsSourceError(
                f"prometheus query failed: {payload.get('error', 'unknown error')}"
            )
        return payload["data"]

    async def query_range(
        self, query: str, window: TimeWindow, step: str = "30s"
    ) -> list[MetricSeries]:
        """Evaluate a PromQL range query."""
        data = await self._get(
            "/api/v1/query_range",
            {
                "query": query,
                "start": str(window.start.timestamp()),
                "end": str(window.end.timestamp()),
                "step": step,
            },
        )
        series: list[MetricSeries] = []
        for entry in data.get("result", []):
            samples = tuple(
                MetricSample(
                    timestamp=datetime.fromtimestamp(float(ts), tz=window.start.tzinfo),
                    value=float(value),
                )
                for ts, value in entry.get("values", [])
            )
            series.append(MetricSeries(labels=entry.get("metric", {}), samples=samples))
        logger.debug("promql_executed", query=query, series_count=len(series))
        return series

    async def list_services(self) -> list[str]:
        """Return every value of the ``service`` label."""
        data = await self._get("/api/v1/label/service/values", {})
        return [str(v) for v in data]
