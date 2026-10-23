"""Static contracts for graph factories; run with strict mypy, not pytest."""

from typing import assert_type

from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from incident_copilot.agents.correlation_agent import build_correlation_agent
from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.logs_agent import build_logs_agent
from incident_copilot.agents.metrics_agent import build_metrics_agent
from incident_copilot.agents.state import (
    CorrelationUpdate,
    InvestigationState,
    LogsUpdate,
    MetricsUpdate,
    SupervisorUpdate,
)
from incident_copilot.agents.supervisor import build_supervisor
from incident_copilot.composition import Collaborators
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import LLMProvider


async def check_graph_contract(
    provider: LLMProvider,
    tools: list[BaseTool],
    settings: Settings,
    state: InvestigationState,
) -> None:
    """Reject erased graph types and node factories incompatible with add_node."""
    builder: StateGraph[InvestigationState, None, InvestigationState, InvestigationState]
    builder = StateGraph(InvestigationState)
    supervisor = build_supervisor(provider, settings)
    metrics = build_metrics_agent(provider, tools, settings)
    logs = build_logs_agent(provider, tools, settings)
    correlation = build_correlation_agent(provider)
    builder.add_node("supervisor", supervisor)
    builder.add_node("metrics", metrics)
    builder.add_node("logs", logs)
    builder.add_node("correlation", correlation)

    assert_type(await supervisor(state), SupervisorUpdate)
    assert_type(await metrics(state), MetricsUpdate)
    assert_type(await logs(state), LogsUpdate)
    assert_type(await correlation(state), CorrelationUpdate)
    graph = build_graph(provider, tools, tools, settings)
    assert_type(
        graph, CompiledStateGraph[InvestigationState, None, InvestigationState, InvestigationState]
    )


def check_composition_contract(collaborators: Collaborators) -> None:
    """Keep the compiled graph's types through the shared composition boundary."""
    assert_type(
        collaborators.graph,
        CompiledStateGraph[InvestigationState, None, InvestigationState, InvestigationState],
    )
