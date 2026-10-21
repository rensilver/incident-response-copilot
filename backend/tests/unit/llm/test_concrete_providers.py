from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.ollama_provider import OllamaProvider


class StubChat:
    """Minimal stand-in for a LangChain chat model."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.received: list[Sequence[BaseMessage]] = []

    async def ainvoke(self, messages: Sequence[BaseMessage], **_: Any) -> AIMessage:
        self.received.append(messages)
        return AIMessage(content=self.reply)

    def bind_tools(self, tools: Any) -> Any:
        return self


async def test_complete_returns_text_and_maps_roles() -> None:
    chat = StubChat("all good")
    provider = OllamaProvider(chat=chat, json_chat=chat)  # type: ignore[arg-type]  # stub

    result = await provider.complete(
        [ChatMessage(role="system", content="be terse"), ChatMessage(role="user", content="hi")]
    )

    assert result == "all good"
    sent = chat.received[0]
    assert [m.type for m in sent] == ["system", "human"]


async def test_generate_json_uses_the_json_configured_client() -> None:
    text_chat = StubChat("prose")
    json_chat = StubChat('{"ok": true}')
    provider = OllamaProvider(chat=text_chat, json_chat=json_chat)  # type: ignore[arg-type]  # stub

    raw = await provider._generate_json([ChatMessage(role="user", content="json please")])

    assert raw == '{"ok": true}'
    assert text_chat.received == []
