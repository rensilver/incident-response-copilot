import asyncio
from types import SimpleNamespace

import httpx
import pytest
import respx
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from incident_copilot.config.settings import Settings
from incident_copilot.llm.ollama_provider import OllamaProvider
from incident_copilot.utils.exceptions import LLMProviderError


@pytest.mark.parametrize(
    "loaded,available,allowed",
    [(False, 2900, False), (False, 5000, True), (True, 1500, True), (True, 500, False)],
)
@respx.mock
async def test_memory_guard_handles_cold_and_loaded_models(monkeypatch, loaded, available, allowed):
    monkeypatch.setattr(
        "incident_copilot.llm.ollama_provider.psutil.virtual_memory",
        lambda: SimpleNamespace(available=available * 1024**2),
    )
    respx.get("http://localhost:11434/api/ps").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "qwen3:4b"}] if loaded else []})
    )
    calls = []

    async def reply(messages):
        calls.append(messages)
        return AIMessage(content="local")

    chat = RunnableLambda(reply)
    provider = OllamaProvider(chat, chat, Settings(_env_file=None))
    if allowed:
        assert await provider.complete([]) == "local"
        assert len(calls) == 1
    else:
        with pytest.raises(LLMProviderError, match="Ollama skipped"):
            await provider.complete([])
        assert calls == []


async def test_local_calls_are_serialized_and_timeout_releases_lock():
    active = 0
    peak = 0

    async def reply(messages):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            return AIMessage(content="ok")
        finally:
            active -= 1

    chat = RunnableLambda(reply)
    settings = Settings(_env_file=None, ollama_min_available_memory_mb=0, ollama_timeout_seconds=1)
    provider = OllamaProvider(chat, chat, settings)
    assert await asyncio.gather(provider.complete([]), provider.complete([])) == ["ok", "ok"]
    assert peak == 1
    settings.ollama_timeout_seconds = 0.001
    with pytest.raises(LLMProviderError, match="TimeoutError"):
        await provider.complete([])
    settings.ollama_timeout_seconds = 1
    assert await provider.complete([]) == "ok"


def test_ollama_has_bounded_context_and_no_thinking():
    provider = OllamaProvider.from_settings(Settings(_env_file=None))
    assert provider._chat.num_ctx == 4096
    assert provider._chat.reasoning is False
    assert provider._chat.keep_alive == "1m"
