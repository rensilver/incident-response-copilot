"""Thin HTTP client over the incident-copilot FastAPI API.

Deliberately independent of the incident_copilot package - this app only ever talks to
the API over HTTP, per CLAUDE.md's rule that the UI is a client of the API, not a
consumer of the agents/connectors/llm library code.
"""

import os
from dataclasses import dataclass

import httpx

DEFAULT_API_URL = "http://localhost:8000"


class InvestigationError(Exception):
    """Raised when the API is unreachable or rejects an investigation request."""


@dataclass(frozen=True)
class EvidenceRef:
    """A pointer to the observation that supports a claim."""

    source: str
    detail: str


@dataclass(frozen=True)
class LikelyCause:
    """One candidate root cause, as returned by the API."""

    title: str
    rationale: str
    confidence: float
    supporting_evidence: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class IncidentReport:
    """The structured report returned by POST /api/v1/investigations."""

    summary: str
    likely_causes: tuple[LikelyCause, ...]
    next_steps: tuple[str, ...]
    confidence: float


def _api_url() -> str:
    return os.environ.get("INCIDENT_COPILOT_API_URL", DEFAULT_API_URL)


def fetch_health() -> dict[str, object]:
    """Return the API's /health payload, or an unreachable placeholder."""
    try:
        response = httpx.get(f"{_api_url()}/health", timeout=5.0)
        response.raise_for_status()
        payload: dict[str, object] = response.json()
        return payload
    except httpx.HTTPError:
        return {"status": "unreachable", "dependencies": {}}


def run_investigation(query: str, service: str | None, minutes_back: int) -> IncidentReport:
    """Call POST /api/v1/investigations and parse the structured report.

    Args:
        query: The incident question.
        service: Service to focus on, if any.
        minutes_back: Length of the window to investigate.

    Returns:
        The structured report.

    Raises:
        InvestigationError: If the API is unreachable or rejects the request.
    """
    payload = {"query": query, "service": service, "minutes_back": minutes_back}
    try:
        response = httpx.post(f"{_api_url()}/api/v1/investigations", json=payload, timeout=300.0)
    except httpx.HTTPError as exc:
        raise InvestigationError(f"can't reach the API at {_api_url()}") from exc

    if response.status_code >= 400:
        detail = response.json().get("detail", response.text)
        raise InvestigationError(str(detail))

    data = response.json()
    causes = tuple(
        LikelyCause(
            title=c["title"],
            rationale=c["rationale"],
            confidence=c["confidence"],
            supporting_evidence=tuple(
                EvidenceRef(source=e["source"], detail=e["detail"])
                for e in c["supporting_evidence"]
            ),
        )
        for c in data["likely_causes"]
    )
    return IncidentReport(
        summary=data["summary"],
        likely_causes=causes,
        next_steps=tuple(data["next_steps"]),
        confidence=data["confidence"],
    )
