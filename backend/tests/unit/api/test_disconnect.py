"""HTTP cancellation differs from an ASGI disconnect on a synchronous report route."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from starlette.types import Message, Scope

from incident_copilot.config.settings import Settings
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.main import create_app
from incident_copilot.models.report import IncidentReport


class WaitingGraph:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def ainvoke(self, state: Any, /) -> dict[str, Any]:
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        return {
            "report": IncidentReport(
                summary="finished", likely_causes=(), next_steps=(), confidence=0
            )
        }


@asynccontextmanager
async def serving_app(
    monkeypatch: pytest.MonkeyPatch, graph: WaitingGraph, seconds: float
) -> AsyncIterator[FastAPI]:
    async def provider(settings: Settings) -> FakeLLMProvider:
        return FakeLLMProvider(["unused"])

    monkeypatch.setattr("incident_copilot.composition.build_graph", lambda *args: graph)
    monkeypatch.setattr("incident_copilot.composition.build_llm_provider", provider)
    app = create_app(Settings(_env_file=None, investigation_timeout_seconds=seconds))
    async with app.router.lifespan_context(app):
        yield app


async def test_serving_settings_enforce_a_real_http_504(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = WaitingGraph()
    async with serving_app(monkeypatch, graph, 0.01) as app:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await asyncio.wait_for(
                client.post("/api/v1/investigations", json={"query": "q"}), timeout=2
            )
        assert response.status_code == 504
        assert response.json() == {"detail": "Investigation deadline exceeded."}
        assert graph.cancelled.is_set()
        # The deadline ends a request; serving resources remain alive until shutdown.
        assert hasattr(app.state, "service")
    assert not hasattr(app.state, "service")


@pytest.mark.parametrize("outcome", ["complete", "deadline", "cancel"])
async def test_disconnect_alone_keeps_work_but_task_cancellation_stops_it(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    graph = WaitingGraph()
    seconds = 0.05 if outcome == "deadline" else 2
    async with serving_app(monkeypatch, graph, seconds) as app:
        messages: list[Message] = []
        incoming: asyncio.Queue[Message] = asyncio.Queue()
        incoming.put_nowait({"type": "http.request", "body": b'{"query":"q"}', "more_body": False})
        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/investigations",
            "raw_path": b"/api/v1/investigations",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("test", 1),
            "server": ("test", 80),
            "root_path": "",
        }

        async def send(message: Message) -> None:
            messages.append(message)

        task = asyncio.create_task(app(scope, incoming.get, send))
        try:
            await asyncio.wait_for(graph.started.wait(), timeout=2)
            incoming.put_nowait({"type": "http.disconnect"})
            await asyncio.sleep(0)  # Yield only; no wall-clock delay.
            assert not task.done()
            assert not graph.cancelled.is_set()
            if outcome == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=2)
                assert graph.cancelled.is_set()
                assert messages == []
            else:
                if outcome == "complete":
                    graph.release.set()
                await asyncio.wait_for(task, timeout=2)
                assert messages[0]["status"] == (200 if outcome == "complete" else 504)
                assert graph.cancelled.is_set() is (outcome == "deadline")
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
