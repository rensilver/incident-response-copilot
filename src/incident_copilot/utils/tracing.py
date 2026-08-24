"""LangSmith tracing configuration.

LangChain and LangGraph pick up tracing entirely from environment variables, so
enabling it is a matter of setting those before any graph or LLM call runs - no
per-agent code needs to know tracing exists.
"""

import os

from incident_copilot.config.settings import Settings


def configure_tracing(settings: Settings) -> None:
    """Set the LangChain environment variables that enable LangSmith tracing.

    Args:
        settings: Application settings. A no-op when tracing is disabled.
    """
    if not settings.langsmith_tracing:
        return
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key or ""
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
