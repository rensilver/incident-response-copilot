"""Exercise configured construction through the real factory and serializers."""

import json
import logging
import socket
from typing import Any

import pytest
import respx
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.load import dumpd
from openai import AuthenticationError

from incident_copilot.config.settings import Settings
from incident_copilot.llm.factory import build_llm_provider
from incident_copilot.llm.openai_provider import OpenAIProvider
from incident_copilot.main import _llm_health


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


@respx.mock
async def test_factory_uses_configured_key_without_inference_or_fallback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    sentinel = "synthetic-request-secret"
    monkeypatch.setenv("OPENAI_API_KEY", sentinel)
    route = respx.post("https://api.openai.com/v1/responses").respond(
        401, json={"error": {"message": "Invalid synthetic credential", "type": "invalid_api_key"}}
    )
    provider = build_llm_provider(Settings(_env_file=None))
    assert isinstance(provider, OpenAIProvider)
    assert not route.called
    trace = TraceCapture()
    try:
        with pytest.raises(AuthenticationError) as error:
            await provider.bind_tools([]).ainvoke("Offline request", config={"callbacks": [trace]})
        assert route.call_count == 1
        request = route.calls[0].request
        assert request.headers["Authorization"] == f"Bearer {sentinel}"
        body = json.loads(request.content)
        assert body["model"] == "gpt-6-luna"
        assert body["reasoning"] == {"effort": "none"}
        assert trace.events
        surfaces = [
            repr(provider),
            repr(provider._chat),
            json.dumps(dumpd(provider._chat)),
            repr(trace.events),
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
    assert await _llm_health(Settings(_env_file=None))() is False
    assert not respx.calls
