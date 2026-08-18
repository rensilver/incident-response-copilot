from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from incident_copilot.agents.tool_loop import run_tool_rounds
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.utils.exceptions import MetricsSourceError


class EchoArgs(BaseModel):
    value: str


def _tools(calls: list[str], fail: bool = False) -> list[BaseTool]:
    async def echo(value: str) -> str:
        calls.append(value)
        if fail:
            raise MetricsSourceError("prometheus unreachable")
        return f"echoed:{value}"

    return [
        StructuredTool.from_function(
            coroutine=echo, name="echo", description="echo a value", args_schema=EchoArgs
        )
    ]


def _call(value: str) -> dict[str, Any]:
    return {"name": "echo", "args": {"value": value}, "id": f"c-{value}", "type": "tool_call"}


MESSAGES = [ChatMessage(role="user", content="go")]


async def test_results_are_collected_from_every_round() -> None:
    seen: list[str] = []
    provider = FakeLLMProvider(["done"], tool_rounds=[[_call("a")], [_call("b")]])
    outcome = await run_tool_rounds(provider, _tools(seen), MESSAGES, max_rounds=2)
    assert seen == ["a", "b"]
    assert outcome.results == ["echoed:a", "echoed:b"]


async def test_loop_is_bounded_even_when_the_model_keeps_asking() -> None:
    """Without the cap a small model can spiral indefinitely."""
    seen: list[str] = []
    provider = FakeLLMProvider(["done"], tool_rounds=[[_call(str(i))] for i in range(10)])
    await run_tool_rounds(provider, _tools(seen), MESSAGES, max_rounds=2)
    assert len(seen) == 2


async def test_loop_stops_early_when_the_model_asks_for_nothing() -> None:
    seen: list[str] = []
    provider = FakeLLMProvider(["nothing needed"])
    outcome = await run_tool_rounds(provider, _tools(seen), MESSAGES, max_rounds=2)
    assert seen == []
    assert outcome.results == []


async def test_connector_failure_is_recorded_not_raised() -> None:
    """One dead backend must not abort the whole investigation."""
    seen: list[str] = []
    provider = FakeLLMProvider(["done"], tool_rounds=[[_call("a")]])
    outcome = await run_tool_rounds(provider, _tools(seen, fail=True), MESSAGES, max_rounds=2)
    assert outcome.results == []
    assert any("prometheus unreachable" in e for e in outcome.errors)


async def test_unknown_tool_name_is_recorded() -> None:
    """A hallucinated tool name must be recorded, not raise.

    `FakeLLMProvider` deliberately cannot produce this: it only serves rounds whose tools
    are bound. So this one case uses a provider that emits an unbound name directly.
    """

    class RogueProvider(FakeLLMProvider):
        def bind_tools(self, tools: Any) -> Any:
            call = {"name": "no_such_tool", "args": {}, "id": "x", "type": "tool_call"}
            return RunnableLambda(lambda _: AIMessage(content="", tool_calls=[call]))

    seen: list[str] = []
    outcome = await run_tool_rounds(RogueProvider(["done"]), _tools(seen), MESSAGES, max_rounds=1)
    assert any("no_such_tool" in e for e in outcome.errors)
    assert seen == []
