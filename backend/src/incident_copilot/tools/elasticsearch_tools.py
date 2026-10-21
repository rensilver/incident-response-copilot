"""LangChain tools over the log connector."""

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool

from incident_copilot.connectors.base import LogSource
from incident_copilot.models.enums import LogLevel
from incident_copilot.models.logs import LogFinding, LogSearchCriteria
from incident_copilot.tools.schemas import LogHistogramArgs, LogSearchArgs
from incident_copilot.tools.window import resolve_window


def build_log_tools(source: LogSource) -> list[BaseTool]:
    """Build the log toolset bound to a connector.

    Args:
        source: The log backend to query.

    Returns:
        Tools ready to bind to a model.
    """

    async def search_logs(
        service: str,
        config: RunnableConfig,
        minutes_back: int = 60,
        level: LogLevel | None = None,
        keyword: str | None = None,
    ) -> LogFinding:
        """Search a service's logs, optionally filtered by level and keyword."""
        return await source.search(
            LogSearchCriteria(
                service=service,
                window=resolve_window(config, minutes_back),
                level=level,
                keyword=keyword,
            )
        )

    async def log_level_histogram(
        service: str, config: RunnableConfig, minutes_back: int = 60
    ) -> dict[str, int]:
        """Count a service's log documents per severity level."""
        return await source.level_histogram(service, resolve_window(config, minutes_back))

    return [
        StructuredTool.from_function(
            coroutine=search_logs,
            name="search_logs",
            description="Search a service's logs by level and keyword over a time window.",
            args_schema=LogSearchArgs,
        ),
        StructuredTool.from_function(
            coroutine=log_level_histogram,
            name="log_level_histogram",
            description="Count a service's log entries per severity level.",
            args_schema=LogHistogramArgs,
        ),
    ]
