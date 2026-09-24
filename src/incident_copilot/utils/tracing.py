"""LangSmith tracing configuration.

LangChain and LangGraph pick up tracing entirely from environment variables, so
enabling it is a matter of setting those before any graph or LLM call runs - no
per-agent code needs to know tracing exists.
"""

import os

from langsmith.utils import get_env_var, get_tracer_project

from incident_copilot.config.settings import Settings


def configure_tracing(settings: Settings) -> None:
    """Set the LangChain environment variables that enable LangSmith tracing.

    Args:
        settings: Application settings. The tracing flag overrides inherited SDK flags.
    """
    enabled = str(settings.langsmith_tracing).lower()
    # The SDK checks TRACING_V2 before TRACING and accepts both namespaces.
    # Explicitly disable every spelling, including values left by an earlier build.
    for namespace in ("LANGSMITH", "LANGCHAIN"):
        os.environ[f"{namespace}_TRACING"] = enabled
        os.environ[f"{namespace}_TRACING_V2"] = enabled
    if settings.langsmith_tracing:
        for namespace in ("LANGSMITH", "LANGCHAIN"):
            os.environ[f"{namespace}_API_KEY"] = settings.langsmith_api_key or ""
            os.environ[f"{namespace}_PROJECT"] = settings.langsmith_project
    # Recent SDK versions cache environment lookups. Rebuilding collaborators with
    # tracing disabled must not reuse a previous enabled value.
    for lookup in (get_env_var, get_tracer_project):
        clear_cache = getattr(lookup, "cache_clear", None)
        if clear_cache is not None:
            clear_cache()
