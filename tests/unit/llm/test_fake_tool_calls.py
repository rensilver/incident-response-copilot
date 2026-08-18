import asyncio
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from incident_copilot.llm.fake_provider import FakeLLMProvider


class _Args(BaseModel):
    value: str = "v"


def _tool(name: str) -> BaseTool:
    async def run(value: str = "v") -> str:
        return f"{name}:{value}"

    return StructuredTool.from_function(
        coroutine=run, name=name, description=name, args_schema=_Args
    )


def _call(name: str) -> dict[str, Any]:
    return {"name": name, "args": {}, "id": f"call_{name}", "type": "tool_call"}


METRIC_TOOLS = [_tool("get_service_metric")]
LOG_TOOLS = [_tool("search_logs")]


async def test_each_toolset_receives_only_its_own_scripted_round() -> None:
    """One provider serves both specialists; neither may swallow the other's round."""
    provider = FakeLLMProvider(
        ["done"], tool_rounds=[[_call("get_service_metric")], [_call("search_logs")]]
    )

    metrics = await provider.bind_tools(METRIC_TOOLS).ainvoke([HumanMessage(content="go")])
    logs = await provider.bind_tools(LOG_TOOLS).ainvoke([HumanMessage(content="go")])

    assert [c["name"] for c in metrics.tool_calls] == ["get_service_metric"]
    assert [c["name"] for c in logs.tool_calls] == ["search_logs"]


async def test_matching_is_order_independent() -> None:
    """Specialists run in parallel, so the logs agent may reach the script first."""
    provider = FakeLLMProvider(
        ["done"], tool_rounds=[[_call("get_service_metric")], [_call("search_logs")]]
    )

    logs = await provider.bind_tools(LOG_TOOLS).ainvoke([HumanMessage(content="go")])
    metrics = await provider.bind_tools(METRIC_TOOLS).ainvoke([HumanMessage(content="go")])

    assert [c["name"] for c in logs.tool_calls] == ["search_logs"]
    assert [c["name"] for c in metrics.tool_calls] == ["get_service_metric"]


async def test_second_round_returns_a_plain_message_so_the_loop_terminates() -> None:
    provider = FakeLLMProvider(["all done"], tool_rounds=[[_call("get_service_metric")]])
    runnable = provider.bind_tools(METRIC_TOOLS)

    await runnable.ainvoke([HumanMessage(content="go")])
    final = await runnable.ainvoke([HumanMessage(content="go")])

    assert final.tool_calls == []
    assert final.text == "all done"


async def test_a_round_naming_an_unbound_tool_is_never_served() -> None:
    provider = FakeLLMProvider(["done"], tool_rounds=[[_call("search_logs")]])
    message = await provider.bind_tools(METRIC_TOOLS).ainvoke([HumanMessage(content="go")])
    assert message.tool_calls == []


async def test_bind_tools_without_a_script_never_requests_tools() -> None:
    provider = FakeLLMProvider(["nothing to do"])
    message = await provider.bind_tools(METRIC_TOOLS).ainvoke([HumanMessage(content="go")])
    assert message.tool_calls == []


async def test_one_agents_rounds_are_served_in_order_despite_interleaving() -> None:
    """A specialist needing two rounds must get round 1 first, even with another
    agent's round sitting between them in the script."""
    first = {"name": "get_service_metric", "args": {"n": 1}, "id": "1", "type": "tool_call"}
    second = {"name": "get_service_metric", "args": {"n": 2}, "id": "2", "type": "tool_call"}
    provider = FakeLLMProvider(["done"], tool_rounds=[[first], [_call("search_logs")], [second]])
    runnable = provider.bind_tools(METRIC_TOOLS)

    a = await runnable.ainvoke([HumanMessage(content="go")])
    b = await runnable.ainvoke([HumanMessage(content="go")])

    assert a.tool_calls[0]["args"] == {"n": 1}
    assert b.tool_calls[0]["args"] == {"n": 2}


async def test_concurrent_claims_never_serve_an_unbound_round() -> None:
    """Regression: specialists run concurrently and the lambda body runs in a worker
    thread, so an unguarded scan-then-pop can hand a caller another agent's round."""
    provider = FakeLLMProvider(
        ["done"], tool_rounds=[[_call("get_service_metric")], [_call("search_logs")]]
    )

    metrics, logs = await asyncio.gather(
        provider.bind_tools(METRIC_TOOLS).ainvoke([HumanMessage(content="go")]),
        provider.bind_tools(LOG_TOOLS).ainvoke([HumanMessage(content="go")]),
    )

    metric_names = {c["name"] for c in metrics.tool_calls}
    log_names = {c["name"] for c in logs.tool_calls}
    assert metric_names <= {"get_service_metric"}, metric_names
    assert log_names <= {"search_logs"}, log_names
