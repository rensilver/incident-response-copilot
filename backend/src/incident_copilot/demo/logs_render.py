"""Rendering of scenarios into Elasticsearch log documents.

Field names match what
:class:`~incident_copilot.connectors.elasticsearch_connector.ElasticsearchConnector`
reads back: ``@timestamp``, ``service``, ``level``, ``message``, ``version``, ``trace_id``.
Timestamps come from the same grid as the metrics, so a correlation across the two is
genuine rather than coincidental.
"""

from datetime import UTC, datetime

from incident_copilot.demo.curves import time_grid
from incident_copilot.demo.scenarios import Scenario

_BASELINE_INFO_PER_HOUR = 40


def _iso(epoch_seconds: int) -> str:
    """Format epoch seconds as an ISO-8601 UTC string."""
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).isoformat()


def render_log_documents(scenario: Scenario, hours: int = 3) -> list[dict[str, str]]:
    """Render every log document for a scenario.

    Args:
        scenario: The scenario to render.
        hours: Length of the historical window.

    Returns:
        Documents sorted by ascending timestamp.
    """
    grid = time_grid(hours, step_seconds=60)
    last = len(grid) - 1
    documents: list[dict[str, str]] = []

    for profile in scenario.services:
        baseline_every = max(1, len(grid) // max(1, _BASELINE_INFO_PER_HOUR * hours))
        for index, timestamp in enumerate(grid):
            progress = index / last if last else 1.0
            version = (
                profile.version_after
                if progress >= profile.anomaly_start
                else profile.version_before
            )

            if index % baseline_every == 0:
                documents.append(
                    {
                        "@timestamp": _iso(timestamp),
                        "service": profile.service,
                        "level": "INFO",
                        "message": "GET /api/v1/health 200",
                        "version": version,
                        "trace_id": f"{profile.service}-{timestamp}",
                    }
                )

            for template in profile.logs:
                if progress < template.phase_start:
                    continue
                every = max(1, len(grid) // max(1, template.per_hour * hours))
                if index % every:
                    continue
                documents.append(
                    {
                        "@timestamp": _iso(timestamp),
                        "service": profile.service,
                        "level": template.level.value,
                        "message": template.message,
                        "version": (
                            profile.version_after if template.use_version_after else version
                        ),
                        "trace_id": f"{profile.service}-{timestamp}",
                    }
                )

    documents.sort(key=lambda d: d["@timestamp"])
    return documents
