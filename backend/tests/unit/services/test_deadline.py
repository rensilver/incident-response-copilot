"""Total budgets cancel work, preserve unrelated errors, and reject late reports."""

import asyncio
from typing import Any

import pytest
from pydantic import ValidationError

from incident_copilot.config.settings import Settings
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import IncidentService, InvestigationRequest
from incident_copilot.utils.exceptions import InvestigationTimeoutError

REPORT = IncidentReport(summary="s", likely_causes=(), next_steps=(), confidence=0)


@pytest.mark.parametrize("seconds", [0, -1, 241, float("inf"), float("nan")])
def test_settings_reject_unusable_total_deadlines(seconds: float) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, investigation_timeout_seconds=seconds)


@pytest.mark.parametrize("swallow_cancellation", [False, True])
async def test_total_expiry_cancels_work_and_rejects_late_reports(
    swallow_cancellation: bool,
) -> None:
    cancelled = asyncio.Event()

    class Graph:
        async def ainvoke(self, state: Any, /) -> dict[str, Any]:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                if not swallow_cancellation:
                    raise
            return {"report": REPORT}

    service = IncidentService(Graph(), timeout_seconds=0.01)
    with pytest.raises(InvestigationTimeoutError):
        await asyncio.wait_for(service.investigate(InvestigationRequest(query="q")), timeout=2)
    assert cancelled.is_set()


async def test_unclassified_inner_timeout_is_not_mistaken_for_total_expiry() -> None:
    error = TimeoutError("unclassified collaborator failure")

    class Graph:
        async def ainvoke(self, state: Any, /) -> dict[str, Any]:
            raise error

    with pytest.raises(TimeoutError) as caught:
        await IncidentService(Graph(), timeout_seconds=1).investigate(
            InvestigationRequest(query="q")
        )
    assert caught.value is error


async def test_cancellation_cleanup_is_awaited_even_when_it_outlasts_the_budget() -> None:
    cleaning = asyncio.Event()
    release = asyncio.Event()

    class Graph:
        async def ainvoke(self, state: Any, /) -> dict[str, Any]:
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
            return {"report": REPORT}

    service = IncidentService(Graph(), timeout_seconds=0.01)
    task = asyncio.create_task(service.investigate(InvestigationRequest(query="q")))
    try:
        await asyncio.wait_for(cleaning.wait(), timeout=2)
        assert not task.done()
        release.set()
        with pytest.raises(InvestigationTimeoutError):
            await asyncio.wait_for(task, timeout=2)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
