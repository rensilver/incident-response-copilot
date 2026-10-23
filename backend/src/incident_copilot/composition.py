"""Shared construction of connectors, the LLM provider, and the compiled graph.

The one place a provider name or connector class is chosen from settings. main.py and
evaluation/eval_runner.py both depend on this function, never on a concrete connector
or provider directly, keeping application entrypoints independent of concrete clients.
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.state import InvestigationState
from incident_copilot.config.settings import Settings
from incident_copilot.connectors.base import LogSource, MetricsSource
from incident_copilot.connectors.elasticsearch_connector import ElasticsearchConnector
from incident_copilot.connectors.prometheus_connector import PrometheusConnector
from incident_copilot.llm.base import LLMProvider
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.tools.elasticsearch_tools import build_log_tools
from incident_copilot.tools.prometheus_tools import build_metrics_tools
from incident_copilot.utils.tracing import configure_tracing


@dataclass(frozen=True)
class Collaborators:
    """Everything an entrypoint needs to run investigations.

    Attributes:
        graph: The compiled investigation graph, ready for ``ainvoke``.
        metrics_source: The metrics connector, borrowed for the context lifetime.
        log_source: The log connector, borrowed for the context lifetime.
        provider: The same provider used by the graph, retained for health probing.
    """

    graph: CompiledStateGraph[InvestigationState, None, InvestigationState, InvestigationState]
    metrics_source: MetricsSource
    log_source: LogSource
    provider: LLMProvider


@asynccontextmanager
async def build_collaborators(settings: Settings) -> AsyncIterator[Collaborators]:
    """Construct collaborators and close all acquired resources on context exit.

    Register cleanup immediately after each acquisition so partial construction,
    body failures, and cancellation release earlier resources. The exit stack
    attempts every close in reverse acquisition order even if a close raises.

    Args:
        settings: Application settings.

    Yields:
        The graph and its borrowed connectors/provider. Finish graph work before
        leaving the context; callers must not close these resources separately.
    """
    configure_tracing(settings)
    async with AsyncExitStack() as cleanup:
        metrics_source = PrometheusConnector.from_settings(settings)
        cleanup.push_async_callback(metrics_source.aclose)
        log_source = ElasticsearchConnector.from_settings(settings)
        cleanup.push_async_callback(log_source.aclose)
        provider = await build_llm_provider(settings)
        cleanup.push_async_callback(provider.aclose)
        graph = build_graph(
            provider, build_metrics_tools(metrics_source), build_log_tools(log_source), settings
        )
        yield Collaborators(
            graph=graph, metrics_source=metrics_source, log_source=log_source, provider=provider
        )
