"""Builder for the compiled investigation graph.

The graph is acyclic: ``START -> supervisor -> {specialists} -> correlation -> END``.
Termination therefore does not depend on model behaviour. The supervisor's conditional
edge returns a list of node names, which LangGraph fans out to; the correlation node runs
once the routed branches finish, even if only one was routed.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from incident_copilot.agents.correlation_agent import build_correlation_agent
from incident_copilot.agents.logs_agent import build_logs_agent
from incident_copilot.agents.metrics_agent import build_metrics_agent
from incident_copilot.agents.state import InvestigationState
from incident_copilot.agents.supervisor import build_supervisor
from incident_copilot.config.settings import Settings
from incident_copilot.llm.base import LLMProvider
from incident_copilot.models.enums import AgentName

GraphNode = Callable[[InvestigationState], Awaitable[Mapping[str, Any]]]


def _add_node(builder: StateGraph[Any, Any, Any, Any], name: str, node: GraphNode) -> None:
    """Attach one node to the builder.

    LangGraph 1.2's ``add_node`` overloads do not admit a ``Callable`` produced by a
    factory — they expect a directly declared coroutine function — so every node this
    package builds trips the overload resolver. The runtime contract is satisfied
    (verified by the graph tests), so the mismatch is suppressed once here rather than
    at all four call sites.

    Args:
        builder: The graph under construction.
        name: Node name.
        node: The async node function.
    """
    builder.add_node(name, node)  # type: ignore[call-overload]  # see docstring


def build_graph(
    provider: LLMProvider,
    metrics_tools: Sequence[BaseTool],
    log_tools: Sequence[BaseTool],
    settings: Settings,
) -> CompiledStateGraph:  # type: ignore[type-arg]  # langgraph's generics vary by version
    """Assemble and compile the investigation graph.

    Args:
        provider: LLM shared by every node.
        metrics_tools: Tools for the metrics specialist.
        log_tools: Tools for the logs specialist.
        settings: Supplies the iteration and tool-round caps.

    Returns:
        The compiled graph, ready for ``ainvoke``.
    """
    builder: StateGraph[Any, Any, Any, Any] = StateGraph(InvestigationState)

    _add_node(builder, AgentName.SUPERVISOR.value, build_supervisor(provider, settings))
    _add_node(
        builder, AgentName.METRICS.value, build_metrics_agent(provider, metrics_tools, settings)
    )
    _add_node(builder, AgentName.LOGS.value, build_logs_agent(provider, log_tools, settings))
    _add_node(builder, AgentName.CORRELATION.value, build_correlation_agent(provider))

    builder.add_edge(START, AgentName.SUPERVISOR.value)
    builder.add_conditional_edges(
        AgentName.SUPERVISOR.value,
        _route,
        {
            AgentName.METRICS.value: AgentName.METRICS.value,
            AgentName.LOGS.value: AgentName.LOGS.value,
        },
    )
    builder.add_edge(AgentName.METRICS.value, AgentName.CORRELATION.value)
    builder.add_edge(AgentName.LOGS.value, AgentName.CORRELATION.value)
    builder.add_edge(AgentName.CORRELATION.value, END)

    return builder.compile()


def _route(state: InvestigationState) -> list[str]:
    """Return the node names the supervisor selected."""
    return [agent.value for agent in state["route"]]
