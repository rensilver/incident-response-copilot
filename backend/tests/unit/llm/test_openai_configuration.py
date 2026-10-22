"""Exercise configured construction through the real factory and serializers."""

import json
import logging
import socket
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.load import dumpd
from langchain_core.tracers.context import collect_runs
from langsmith import Client, tracing_context

from incident_copilot.config.settings import Settings
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.llm.openai_provider import OpenAIProvider
from incident_copilot.utils.exceptions import LLMProviderError


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Configuration tests must never access the network")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)


class TraceCapture(BaseCallbackHandler):
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def on_chat_model_start(self, serialized: dict[str, Any], messages: Any, **kwargs: Any) -> None:
        self.events.append({"serialized": serialized, **kwargs})

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self.events.append({"error": repr(error), **kwargs})


@respx.mock
@pytest.mark.parametrize("tracing_enabled", [False, True])
async def test_factory_uses_configured_key_without_inference_or_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tracing_enabled: bool,
) -> None:
    caplog.set_level(logging.DEBUG)
    sentinel = "synthetic-request-secret"
    monkeypatch.setenv("OPENAI_API_KEY", sentinel)
    # Stale deployment variables must not reactivate a second provider on failure.
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-retired-secret")
    route = respx.post("https://api.openai.com/v1/responses").respond(
        401, json={"error": {"message": sentinel, "type": "invalid_api_key"}}
    )
    provider = build_llm_provider(Settings(_env_file=None))
    assert isinstance(provider, OpenAIProvider)
    assert not route.called
    trace = TraceCapture()
    trace_client = MagicMock(spec=Client)
    monkeypatch.setattr("langchain_core.tracers.langchain.get_client", lambda: trace_client)
    try:
        with (
            tracing_context(enabled=tracing_enabled, client=trace_client),
            collect_runs() as runs,
            pytest.raises(LLMProviderError) as error,
        ):
            await provider.bind_tools([]).ainvoke("Offline request", config={"callbacks": [trace]})
        assert route.call_count == len(respx.calls) == 1
        request = route.calls[0].request
        assert request.headers["Authorization"] == f"Bearer {sentinel}"
        body = json.loads(request.content)
        assert body["model"] == "gpt-6-luna"
        assert body["reasoning"] == {"effort": "none"}
        assert trace.events
        assert any("error" in event for event in trace.events)
        if tracing_enabled:
            assert trace_client.update_run.called
            assert "authentication" in repr(trace_client.update_run.call_args_list)
        else:
            assert not trace_client.update_run.called
        surfaces = [
            repr(provider),
            repr(provider._chat),
            json.dumps(dumpd(provider._chat)),
            repr(trace.events),
            repr(runs.traced_runs),
            repr(trace_client.create_run.call_args_list),
            repr(trace_client.update_run.call_args_list),
            caplog.text,
            str(error.value),
            repr(error.value),
        ]
        assert all(sentinel not in surface for surface in surfaces)
        assert sentinel not in request.content.decode()
    finally:
        await provider.aclose()


@respx.mock
async def test_openai_health_does_not_probe_legacy_services() -> None:
    route = respx.get("https://api.openai.com/v1/models/gpt-6-luna").mock(
        return_value=httpx.Response(401, json={"error": {"message": "offline"}})
    )
    provider = OpenAIProvider.from_settings(Settings(_env_file=None))
    try:
        assert await provider.health_check() is False
        assert route.call_count == len(respx.calls) == 1
    finally:
        await provider.aclose()
