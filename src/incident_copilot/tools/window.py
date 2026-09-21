"""Resolve query windows from application-owned tool execution configuration."""

from langchain_core.runnables import RunnableConfig

from incident_copilot.models.metrics import TimeWindow

INVESTIGATION_WINDOW_KEY = "investigation_time_window"


def resolve_window(config: RunnableConfig, minutes_back: int) -> TimeWindow:
    """Use the fixed investigation interval, or a relative window for standalone tools.

    Args:
        config: Runtime configuration injected by LangChain, outside model arguments.
        minutes_back: Relative duration used only without an investigation window.

    Returns:
        The validated interval to pass to the connector.
    """
    window = config.get("configurable", {}).get(INVESTIGATION_WINDOW_KEY)
    if window is None:
        return TimeWindow.from_minutes_back(minutes_back)
    return TimeWindow.model_validate(window)
