"""Narrow interfaces over external observability systems.

Interfaces stay segregated: a metrics backend and a log backend have nothing in common,
so there is no combined ``ObservabilitySource`` with unused methods.
"""

from abc import ABC, abstractmethod

from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import MetricSeries, TimeWindow


class MetricsSource(ABC):
    """A source of time-series metrics."""

    @abstractmethod
    async def query_range(
        self, query: str, window: TimeWindow, step: str = "30s"
    ) -> list[MetricSeries]:
        """Evaluate a range query over a window."""

    @abstractmethod
    async def list_services(self) -> list[str]:
        """Return every known service name."""


class LogSource(ABC):
    """A source of application logs."""

    @abstractmethod
    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        """Search logs matching the criteria."""

    @abstractmethod
    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        """Return a count of log documents per level."""
