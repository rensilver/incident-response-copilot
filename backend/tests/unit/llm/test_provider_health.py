"""Provider health uses metadata only, with bounded and cancellable I/O."""

import asyncio
import socket
from typing import Any

import httpx
import pytest
import respx
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from incident_copilot.llm import base
from incident_copilot.llm.base import ChatMessage
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.llm.openai_provider import OpenAIProvider
from incident_copilot.utils.exceptions import LLMProviderError

MODEL = {"id": "gpt-6-luna", "object": "model", "created": 0, "owned_by": "openai"}


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
    provider = OpenAIProvider.from_api_key(SecretStr("offline-health-key"))
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
    provider = OpenAIProvider.from_api_key(SecretStr("offline-health-key"))
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
    provider = OpenAIProvider.from_api_key(SecretStr("offline-health-key"))
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
    provider = OpenAIProvider.from_api_key(SecretStr("offline-health-key"))
    monkeypatch.setattr(base, "PROVIDER_HEALTH_TIMEOUT_SECONDS", 0.02)
    try:
        assert await asyncio.wait_for(provider.health_check(), timeout=1.0) is False
        assert cancelled.is_set()
        # RESpx records completed calls; count entry for a cancelled request.
        assert len(requests) == 1
    finally:
        await provider.aclose()
