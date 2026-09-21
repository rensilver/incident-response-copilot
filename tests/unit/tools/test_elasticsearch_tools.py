from datetime import UTC, datetime

import pytest

from incident_copilot.connectors.base import LogSource
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.elasticsearch_tools import build_log_tools


class StubLogs(LogSource):
    def __init__(self) -> None:
        self.last: LogSearchCriteria | None = None
        self.last_window: TimeWindow | None = None

    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        self.last = criteria
        self.last_window = criteria.window
        return LogFinding(
            query="stub", matched_count=42, level_breakdown={LogLevel.ERROR: 42}, samples=()
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
        self.last_window = window
        return {"ERROR": 42, "INFO": 900}


def _tool(source: LogSource, name: str):  # type: ignore[no-untyped-def]  # test helper
    return next(t for t in build_log_tools(source) if t.name == name)


async def test_search_logs_passes_filters_through() -> None:
    source = StubLogs()
    finding = await _tool(source, "search_logs").ainvoke(
        {
            "service": "cart-service",
            "minutes_back": 30,
            "level": LogLevel.ERROR,
            "keyword": "NullPointer",
        }
    )

    assert finding.matched_count == 42
    assert source.last is not None
    assert source.last.service == "cart-service"
    assert source.last.level is LogLevel.ERROR
    assert source.last.keyword == "NullPointer"


async def test_log_level_histogram_tool() -> None:
    result = await _tool(StubLogs(), "log_level_histogram").ainvoke(
        {"service": "cart-service", "minutes_back": 30}
    )
    assert result == {"ERROR": 42, "INFO": 900}


@pytest.mark.parametrize("name", ["search_logs", "log_level_histogram"])
@pytest.mark.parametrize("minutes_back", [None, 30])
async def test_standalone_log_tools_keep_relative_windows(
    name: str, minutes_back: int | None
) -> None:
    source = StubLogs()
    args: dict[str, str | int] = {"service": "cart-service"}
    if minutes_back is not None:
        args["minutes_back"] = minutes_back
    before = datetime.now(UTC)
    await _tool(source, name).ainvoke(args)
    after = datetime.now(UTC)
    assert source.last_window is not None
    assert source.last_window.duration_seconds == (minutes_back or 60) * 60
    assert before <= source.last_window.end <= after
