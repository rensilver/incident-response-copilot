from incident_copilot.connectors.base import LogSource
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.tools.elasticsearch_tools import build_log_tools


class StubLogs(LogSource):
    def __init__(self) -> None:
        self.last: LogSearchCriteria | None = None

    async def search(self, criteria: LogSearchCriteria) -> LogFinding:
        self.last = criteria
        return LogFinding(
            query="stub", matched_count=42, level_breakdown={LogLevel.ERROR: 42}, samples=()
        )

    async def level_histogram(self, service: str, window: TimeWindow) -> dict[str, int]:
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
