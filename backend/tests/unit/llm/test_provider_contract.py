"""Shared adapter contracts, using an async chat stub instead of a remote model.

Add future adapters to ``provider_factory`` with the same injected chat boundary.
Provider-specific wire formats belong in the adapter's own tests.
"""

import asyncio
import json
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

import pytest
from langchain_core.callbacks import (
    AsyncCallbackHandler,
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.runnables.config import ensure_config
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import PrivateAttr

from incident_copilot.llm.base import ChatMessage, LLMProvider
from incident_copilot.llm.groq_provider import GroqProvider
from incident_copilot.llm.ollama_provider import OllamaProvider
from incident_copilot.models.report import IncidentReport
from incident_copilot.utils.exceptions import StructuredOutputError

type Operation = Literal["text", "structured", "tools"]
type ProviderFactory = Callable[["ScriptedChat"], LLMProvider]

MESSAGES = (
    ChatMessage(role="system", content="Use observed evidence."),
    ChatMessage(role="user", content="Investigate checkout."),
    ChatMessage(role="assistant", content="I will inspect checkout logs."),
    ChatMessage(role="user", content="Include dependency failures."),
)
REPORT_JSON = json.dumps(
    {
        "summary": "Checkout logged dependency timeouts.",
        "likely_causes": [
            {
                "title": "Slow inventory dependency",
                "rationale": "Checkout logs name inventory timeouts; verify the dependency.",
                "confidence": 0.7,
                "supporting_evidence": [
                    {"source": "logs", "detail": "checkout: timeout calling inventory"}
                ],
            }
        ],
        "next_steps": ["Inspect inventory latency."],
        "confidence": 0.7,
    }
)


@dataclass(frozen=True)
class ModelCall:
    messages: list[BaseMessage]
    tools: list[BaseTool]


class ScriptedChat(BaseChatModel):
    """Replace only model I/O; retain LangChain binding and callback handling."""

    _replies: list[AIMessage] = PrivateAttr(default_factory=list)
    _calls: list[ModelCall] = PrivateAttr(default_factory=list)
    _configs: list[RunnableConfig] = PrivateAttr(default_factory=list)
    _started: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)
    _block: bool = PrivateAttr(default=False)
    _cancelled: bool = PrivateAttr(default=False)

    def __init__(self, replies: Sequence[AIMessage], *, block: bool = False) -> None:
        super().__init__()
        self._replies = list(replies)
        self._block = block

    @property
    def _llm_type(self) -> str:
        return "offline-contract-stub"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise AssertionError("Provider must use asynchronous model I/O")

    async def ainvoke(
        self,
        input: LanguageModelInput,  # noqa: A002 - preserve BaseChatModel's keyword argument
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AIMessage:
        self._configs.append(ensure_config(config))
        return await super().ainvoke(input, config=config, stop=stop, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._calls.append(ModelCall(list(messages), list(kwargs.get("tools", []))))
        self._started.set()
        if self._block:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self._cancelled = True
                raise
        if not self._replies:
            raise AssertionError("Unexpected extra model call")
        return ChatResult(generations=[ChatGeneration(message=self._replies.pop(0))])

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self.bind(tools=list(tools), **kwargs)


@dataclass(frozen=True)
class ModelTrace:
    run_id: UUID
    parent_run_id: UUID | None
    tags: list[str]
    metadata: dict[str, Any]


class TraceRecorder(AsyncCallbackHandler):
    """Capture local callback delivery without a tracing service or key."""

    def __init__(self) -> None:
        self.starts: list[ModelTrace] = []

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.starts.append(ModelTrace(run_id, parent_run_id, tags or [], metadata or {}))


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Provider contracts must never access the network")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)


@pytest.fixture(params=["groq", "ollama"])
def provider_factory(request: pytest.FixtureRequest) -> ProviderFactory:
    # Construct no SDK clients and read no Settings or private dotenv file.
    if request.param == "groq":
        return lambda chat: GroqProvider(chat)
    return lambda chat: OllamaProvider(chat=chat, json_chat=chat)


@pytest.fixture
def tools() -> list[BaseTool]:
    async def lookup(service: str) -> str:
        return f"{service}: dependency timeout"

    return [
        StructuredTool.from_function(
            coroutine=lookup, name=name, description=f"Retrieve {name} for a service."
        )
        for name in ("lookup_logs", "lookup_metrics")
    ]


async def invoke_operation(
    provider: LLMProvider, operation: Operation, tools: Sequence[BaseTool]
) -> str:
    if operation == "text":
        return await provider.complete(MESSAGES)
    if operation == "structured":
        return (await provider.complete_structured(MESSAGES, IncidentReport)).summary
    return (
        await provider.bind_tools(tools).ainvoke([HumanMessage(content="Inspect checkout")])
    ).text


async def test_text_preserves_role_content_order_and_input(
    provider_factory: ProviderFactory,
) -> None:
    chat = ScriptedChat([AIMessage(content="Checkout needs investigation.")])
    provider = provider_factory(chat)
    messages = [message.model_copy(deep=True) for message in MESSAGES]

    result = await provider.complete(messages)

    assert result == "Checkout needs investigation."
    assert len(chat._calls) == 1
    assert [(message.type, message.content) for message in chat._calls[0].messages] == [
        ("system", "Use observed evidence."),
        ("human", "Investigate checkout."),
        ("ai", "I will inspect checkout logs."),
        ("human", "Include dependency failures."),
    ]
    assert messages == list(MESSAGES)


async def test_structured_returns_a_validated_incident_report(
    provider_factory: ProviderFactory,
) -> None:
    chat = ScriptedChat([AIMessage(content=REPORT_JSON)])

    report = await provider_factory(chat).complete_structured(MESSAGES, IncidentReport)

    assert isinstance(report, IncidentReport)
    assert report.summary == "Checkout logged dependency timeouts."
    assert report.likely_causes[0].supporting_evidence[0].detail == (
        "checkout: timeout calling inventory"
    )
    assert report.confidence == 0.7
    assert report.next_steps == ("Inspect inventory latency.",)
    assert len(chat._calls) == 1


async def test_structured_repair_preserves_history_and_validates_report_fields(
    provider_factory: ProviderFactory,
) -> None:
    invalid = REPORT_JSON.replace('"confidence": 0.7', '"confidence": 2.0')
    chat = ScriptedChat([AIMessage(content=invalid), AIMessage(content=REPORT_JSON)])
    messages = [message.model_copy(deep=True) for message in MESSAGES]

    report = await provider_factory(chat).complete_structured(
        messages, IncidentReport, max_attempts=2
    )

    assert report.confidence == 0.7
    assert len(chat._calls) == 2
    first, repaired = (call.messages for call in chat._calls)
    assert repaired[:-2] == first
    assert repaired[-2].type == "ai"
    assert repaired[-2].content == invalid
    assert repaired[-1].type == "human"
    assert "confidence" in repaired[-1].text
    assert "IncidentReport" in repaired[-1].text
    assert messages == list(MESSAGES)


async def test_structured_exhaustion_is_a_failure_with_no_extra_call(
    provider_factory: ProviderFactory,
) -> None:
    chat = ScriptedChat([AIMessage(content="not JSON"), AIMessage(content="still not JSON")])

    with pytest.raises(StructuredOutputError) as error:
        await provider_factory(chat).complete_structured(MESSAGES, IncidentReport, max_attempts=2)

    assert error.value.raw_output == "still not JSON"
    assert len(chat._calls) == 2


async def test_tool_bindings_remain_independent_on_one_provider(
    provider_factory: ProviderFactory, tools: list[BaseTool]
) -> None:
    chat = ScriptedChat([AIMessage(content="logs"), AIMessage(content="metrics")])
    provider = provider_factory(chat)
    logs = provider.bind_tools([tools[0]])
    metrics = provider.bind_tools([tools[1]])

    assert (await logs.ainvoke([HumanMessage(content="Inspect checkout")])).text == "logs"
    assert (await metrics.ainvoke([HumanMessage(content="Inspect checkout")])).text == "metrics"
    assert [[tool.name for tool in call.tools] for call in chat._calls] == [
        ["lookup_logs"],
        ["lookup_metrics"],
    ]


async def test_tool_continuation_preserves_call_ids_arguments_and_all_results(
    provider_factory: ProviderFactory, tools: list[BaseTool]
) -> None:
    chat = ScriptedChat(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "lookup_logs", "args": {"service": "checkout"}, "id": "logs-1"},
                    {"name": "lookup_metrics", "args": {"service": "inventory"}, "id": "metrics-2"},
                ],
            ),
            AIMessage(content="Inspect inventory after checkout's dependency timeout."),
        ]
    )
    runnable = provider_factory(chat).bind_tools(tools)
    opening: list[BaseMessage] = [HumanMessage(content="Inspect checkout and inventory")]

    reply = await runnable.ainvoke(opening)
    assert isinstance(reply, AIMessage)
    assert reply.tool_calls == [
        {
            "name": "lookup_logs",
            "args": {"service": "checkout"},
            "id": "logs-1",
            "type": "tool_call",
        },
        {
            "name": "lookup_metrics",
            "args": {"service": "inventory"},
            "id": "metrics-2",
            "type": "tool_call",
        },
    ]
    history = [
        *opening,
        reply,
        ToolMessage(content="checkout: timeout calling inventory", tool_call_id="logs-1"),
        ToolMessage(content="inventory: latency 950 ms", tool_call_id="metrics-2"),
    ]
    final = await runnable.ainvoke(history)

    assert final.text == "Inspect inventory after checkout's dependency timeout."
    assert isinstance(final, AIMessage)
    assert final.tool_calls == []
    assert len(chat._calls) == 2
    assert chat._calls[1].messages == history
    assert len(opening) == 1


@pytest.mark.parametrize("operation", ["text", "structured", "tools"])
async def test_inherited_callbacks_tags_and_metadata_reach_every_model_call(
    provider_factory: ProviderFactory, tools: list[BaseTool], operation: Operation
) -> None:
    # Structured output deliberately repairs once: both calls must remain traceable.
    replies = (
        [AIMessage(content="invalid"), AIMessage(content=REPORT_JSON)]
        if operation == "structured"
        else [AIMessage(content="Observed dependency timeout.")]
    )
    chat = ScriptedChat(replies)
    provider = provider_factory(chat)
    recorder = TraceRecorder()

    async def investigate(_: str) -> str:
        return await invoke_operation(provider, operation, tools)

    config: RunnableConfig = {
        "callbacks": [recorder],
        "tags": ["provider-contract"],
        "metadata": {"investigation_id": "offline-investigation"},
        "configurable": {"contract_scope": "checkout"},
    }
    result = await RunnableLambda(investigate).ainvoke("investigate", config=config)

    assert result == (
        "Checkout logged dependency timeouts."
        if operation == "structured"
        else "Observed dependency timeout."
    )
    assert len(recorder.starts) == (2 if operation == "structured" else 1)
    assert len({trace.run_id for trace in recorder.starts}) == len(recorder.starts)
    for trace in recorder.starts:
        assert trace.parent_run_id is not None
        assert "provider-contract" in trace.tags
        assert trace.metadata["investigation_id"] == "offline-investigation"
    assert len(chat._configs) == len(recorder.starts)
    for model_config in chat._configs:
        assert model_config["configurable"]["contract_scope"] == "checkout"


@pytest.mark.parametrize("operation", ["text", "structured", "tools"])
async def test_cancellation_reaches_model_without_repair_or_wrapping(
    provider_factory: ProviderFactory, tools: list[BaseTool], operation: Operation
) -> None:
    chat = ScriptedChat([], block=True)
    task = asyncio.create_task(invoke_operation(provider_factory(chat), operation, tools))
    try:
        # Handshake proves cancellation occurs during model I/O, without timing sleeps.
        await asyncio.wait_for(chat._started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert chat._cancelled
        assert len(chat._calls) == 1
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
