"""Orchestration of one incident investigation.

Owns the correlation ID and the mapping from graph output to domain errors. Contains no
HTTP and no LLM code: it invokes the compiled graph and interprets the result.
"""

import asyncio
import uuid
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel, Field

from incident_copilot.agents.state import initial_state
from incident_copilot.config.settings import DEFAULT_INVESTIGATION_TIMEOUT_SECONDS
from incident_copilot.models.metrics import TimeWindow
from incident_copilot.models.report import IncidentReport
from incident_copilot.utils.exceptions import InvestigationError, InvestigationTimeoutError
from incident_copilot.utils.logging import bind_correlation_id, get_logger

logger = get_logger(__name__)


class InvestigationRequest(BaseModel):
    """What an engineer asks the copilot to look into."""

    query: str = Field(min_length=1, description="The incident question")
    service: str | None = Field(default=None, description="Service to focus on")
    minutes_back: int = Field(default=60, ge=1, le=1440, description="Window length")


class _Graph(Protocol):
    """The part of a compiled LangGraph this service depends on.

    The state argument is positional-only: the real ``CompiledStateGraph`` calls it
    ``input``, and the parameter name is not part of what this service relies on.
    """

    async def ainvoke(self, state: Any, /) -> Mapping[str, Any]: ...


class IncidentService:
    """Runs investigations through the compiled graph.

    Args:
        graph: The compiled investigation graph.
        timeout_seconds: Total cooperative graph execution budget, shared by all nodes.
    """

    def __init__(
        self, graph: _Graph, *, timeout_seconds: float = DEFAULT_INVESTIGATION_TIMEOUT_SECONDS
    ) -> None:
        """Store the compiled graph.

        Args:
            graph: The compiled investigation graph.
            timeout_seconds: Total execution budget; serving callers inject validated settings.
        """
        self._graph = graph
        self._timeout_seconds = timeout_seconds

    async def investigate(self, request: InvestigationRequest) -> IncidentReport:
        """Run one investigation.

        Args:
            request: The incident question and window.

        Returns:
            The structured report.

        Raises:
            InvestigationError: If the graph produced no report.
            InvestigationTimeoutError: If the total execution deadline expired.
        """
        correlation_id = str(uuid.uuid4())
        bind_correlation_id(correlation_id)
        logger.info("investigation_started", query=request.query, service=request.service)

        state = initial_state(
            correlation_id=correlation_id,
            query=request.query,
            time_window=TimeWindow.from_minutes_back(request.minutes_back),
            target_service=request.service,
        )
        deadline = asyncio.timeout(self._timeout_seconds)
        try:
            async with deadline:
                final = await self._graph.ainvoke(state)
        except TimeoutError as exc:
            if not deadline.expired():
                # An unclassified collaborator TimeoutError is not our total deadline.
                raise
            logger.warning("investigation_deadline_exceeded", seconds=self._timeout_seconds)
            raise InvestigationTimeoutError("Investigation deadline exceeded.") from exc
        if deadline.expired():
            # A collaborator may swallow cancellation and return late. Never publish it.
            logger.warning("investigation_deadline_exceeded", seconds=self._timeout_seconds)
            raise InvestigationTimeoutError("Investigation deadline exceeded.")

        # isinstance rather than `is None`: the graph hands back an untyped mapping, so
        # this is the boundary where the report stops being Any. A wrong-typed value in
        # the slot is as unusable as a missing one and must not reach the API layer.
        report = final.get("report")
        if not isinstance(report, IncidentReport):
            errors = "; ".join(final.get("errors", [])) or "no report produced"
            logger.error("investigation_failed", errors=errors)
            raise InvestigationError(f"investigation produced no report: {errors}")

        logger.info("investigation_complete", causes=len(report.likely_causes))
        # Query scope is application metadata. Never trust a model-authored interval.
        return report.model_copy(update={"investigation_window": state["time_window"]})
