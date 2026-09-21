"""Shared construction of connectors, the LLM provider, and the compiled graph.

The one place a provider name or connector class is chosen from settings. main.py and
evaluation/eval_runner.py both depend on this function, never on a concrete connector
or provider directly (CLAUDE.md's Dependency Inversion rule).
"""

from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph

from incident_copilot.agents.graph import build_graph
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools
from incident_copilot.utils.tracing import configure_tracing


@dataclass(frozen=True)
class Collaborators:
    """Everything an entrypoint needs to run investigations.

    Attributes:
        graph: The compiled investigation graph, ready for ``ainvoke``.
        metrics_source: The metrics connector, held so a caller can close it on shutdown.
        log_source: The log connector, held so a caller can close it on shutdown.
    """

    graph: CompiledStateGraph  # type: ignore[type-arg]  # langgraph's generics vary by version
    metrics_source: MetricsSource
    log_source: LogSource


def build_collaborators(settings: Settings) -> Collaborators:
    """Construct every concrete connector, the LLM provider, and the compiled graph.

    Args:
        settings: Application settings.

    Returns:
        The graph and the connectors it was built from.
    """
    configure_tracing(settings)
    metrics_source = PrometheusConnector.from_settings(settings)
    log_source = ElasticsearchConnector.from_settings(settings)
    provider = build_llm_provider(settings)
    graph = build_graph(
        provider, build_metrics_tools(metrics_source), build_log_tools(log_source), settings
    )
    return Collaborators(graph=graph, metrics_source=metrics_source, log_source=log_source)
