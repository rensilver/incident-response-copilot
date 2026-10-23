"""Provider health uses metadata only, with bounded and cancellable I/O."""

import asyncio
import logging
import socket
from typing import Any

import httpx
import pytest
import respx
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from incident_copilot.agents.graph import build_graph
from incident_copilot.api.routes import build_router
from incident_copilot.config.settings import Settings
from incident_copilot.llm import base
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.llm.openai_provider import OpenAIProvider
from incident_copilot.services.incident_service import IncidentService
from incident_copilot.utils.exceptions import LLMProviderError
from incident_copilot.utils.logging import configure_logging

MODEL = {"id": "gpt-6-luna", "object": "model", "created": 0, "owned_by": "openai"}
HEALTH_CANARY = "synthetic-health-payload-secret"


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(
            httpx.Response(status, json={"error": {"message": HEALTH_CANARY}}), id=f"http-{status}"
        )
        for status in (401, 403, 404, 429, 500)
    ]
    + [
        pytest.param(httpx.ConnectError(HEALTH_CANARY), id="connection"),
        pytest.param(httpx.ReadTimeout(HEALTH_CANARY), id="timeout"),
        pytest.param(httpx.Response(200, json={}), id="empty-object"),
        pytest.param(
            httpx.Response(200, content="null", headers={"content-type": "application/json"}),
            id="null",
        ),
        pytest.param(httpx.Response(200, json=[]), id="array"),
        pytest.param(httpx.Response(200, json=HEALTH_CANARY), id="string"),
        pytest.param(httpx.Response(200, json={"object": "model"}), id="missing-id"),
        pytest.param(httpx.Response(200, json={"id": "gpt-6-luna"}), id="missing-object"),
        pytest.param(httpx.Response(200, json={**MODEL, "id": "other-model"}), id="wrong-model"),
        pytest.param(
            httpx.Response(200, json={**MODEL, "id": ["gpt-6-luna"]}), id="invalid-id-type"
        ),
        pytest.param(httpx.Response(200, json={**MODEL, "object": "list"}), id="wrong-object"),
        pytest.param(httpx.Response(200, json={**MODEL, "object": None}), id="null-object"),
        pytest.param(
            httpx.Response(
                200, content=HEALTH_CANARY, headers={"content-type": "application/json"}
            ),
            id="invalid-json",
        ),
        pytest.param(httpx.Response(200, text=f"<html>{HEALTH_CANARY}</html>"), id="html"),
    ],
)
@respx.mock
async def test_health_failure_is_redacted_and_recovers_on_later_poll(
    failure: httpx.Response | httpx.HTTPError,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Use the same provider/router through failure, recovery, and another poll."""
    caplog.set_level(logging.DEBUG)
    configure_logging("DEBUG")
    key = "synthetic-health-auth-secret"
    route = respx.get("https://api.openai.com/v1/models/gpt-6-luna").mock(
        side_effect=[failure, httpx.Response(200, json=MODEL), httpx.Response(200, json=MODEL)]
    )
    provider = await OpenAIProvider.from_api_key(SecretStr(key))
    settings = Settings(_env_file=None)
    app = FastAPI()
    app.include_router(
        build_router(
            IncidentService(build_graph(provider, [], [], settings)), {"llm": provider.health_check}
        )
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for count, healthy in enumerate((False, True, True), start=1):
                response = await client.get("/health")
                assert response.status_code == 200
                assert response.json() == {
                    "status": "ok" if healthy else "degraded",
                    "dependencies": {"llm": healthy},
                }
                assert route.call_count == len(respx.calls) == count
        captured = capsys.readouterr()
        surfaces = caplog.text + captured.out + captured.err + repr(provider)
        assert HEALTH_CANARY not in surfaces
        assert key not in surfaces
        assert all(call.request.method == "GET" for call in respx.calls)
    finally:
        await provider.aclose()


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Health tests must never use the network")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)


@respx.mock
async def test_openai_health_reads_model_metadata_without_inference() -> None:
    route = respx.get("https://api.openai.com/v1/models/gpt-6-luna").respond(200, json=MODEL)
    provider = await OpenAIProvider.from_api_key(SecretStr("offline-health-key"))
    try:
        assert not respx.calls
        assert await provider.health_check() is True
        assert route.call_count == 1
        assert len(respx.calls) == 1
        request = route.calls[0].request
        assert request.headers["Authorization"] == "Bearer offline-health-key"
        assert not request.content
        assert request.extensions["timeout"] == {
            "connect": 3.0,
            "read": 3.0,
            "write": 3.0,
            "pool": 3.0,
        }
    finally:
        await provider.aclose()


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
@respx.mock
async def test_openai_health_failure_does_not_retry_or_generate(status: int) -> None:
    route = respx.get("https://api.openai.com/v1/models/gpt-6-luna").respond(
        status, json={"error": {"message": "offline failure", "type": "api_error"}}
    )
    provider = await OpenAIProvider.from_api_key(SecretStr("offline-health-key"))
    try:
        assert await provider.health_check() is False
        assert route.call_count == 1
        assert len(respx.calls) == 1
    finally:
        await provider.aclose()


@respx.mock
async def test_metadata_access_does_not_claim_successful_inference() -> None:
    respx.get("https://api.openai.com/v1/models/gpt-6-luna").respond(200, json=MODEL)
    inference = respx.post("https://api.openai.com/v1/responses").respond(
        429, json={"error": {"message": "quota", "code": "insufficient_quota"}}
    )
    provider = await OpenAIProvider.from_api_key(SecretStr("offline-health-key"))
    try:
        assert await provider.health_check() is True
        assert not inference.called
        with pytest.raises(LLMProviderError):
            await provider.complete([ChatMessage(role="user", content="Offline request")])
        assert inference.call_count == 1
        assert await provider.health_check() is True
    finally:
        await provider.aclose()


async def test_provider_without_probe_is_unavailable_without_generating() -> None:
    provider = FakeLLMProvider(["unused"])
    assert await provider.health_check() is False
    assert await provider.complete([]) == "unused"


async def test_openai_probe_is_injectable_without_using_the_borrowed_chat() -> None:
    async def metadata_access() -> bool:
        return True

    chat = FakeMessagesListChatModel(responses=[AIMessage(content="unused")])
    provider = OpenAIProvider(chat, health_probe=metadata_access)
    assert await provider.health_check() is True
    await provider.aclose()
    assert await provider.complete([]) == "unused"
    assert await OpenAIProvider(chat).health_check() is False


async def test_probe_deadline_cancels_inflight_work(monkeypatch: pytest.MonkeyPatch) -> None:
    cancelled = asyncio.Event()

    class StalledProvider(FakeLLMProvider):
        async def _probe_health(self) -> bool:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
            return True

    monkeypatch.setattr(base, "PROVIDER_HEALTH_TIMEOUT_SECONDS", 0.02)
    provider = StalledProvider(["unused"])
    assert await asyncio.wait_for(provider.health_check(), timeout=1.0) is False
    assert cancelled.is_set()


async def test_external_probe_cancellation_propagates() -> None:
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    class StalledProvider(FakeLLMProvider):
        async def _probe_health(self) -> bool:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
            return True

    task = asyncio.create_task(StalledProvider(["unused"]).health_check())
    await asyncio.wait_for(entered.wait(), timeout=1.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


@respx.mock
async def test_deadline_bounds_real_openai_metadata_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled = asyncio.Event()
    requests: list[httpx.Request] = []

    async def stalled(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        return httpx.Response(200, json=MODEL)

    respx.get("https://api.openai.com/v1/models/gpt-6-luna").mock(side_effect=stalled)
    provider = await OpenAIProvider.from_api_key(SecretStr("offline-health-key"))
    monkeypatch.setattr(base, "PROVIDER_HEALTH_TIMEOUT_SECONDS", 0.02)
    try:
        assert await asyncio.wait_for(provider.health_check(), timeout=1.0) is False
        assert cancelled.is_set()
        # RESpx records completed calls; count entry for a cancelled request.
        assert len(requests) == 1
    finally:
        await provider.aclose()
