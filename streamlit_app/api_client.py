"""Thin HTTP client over the incident-copilot FastAPI API.

The UI models deliberately remain independent of the incident_copilot package.
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

import httpx
from pydantic import Field, TypeAdapter, ValidationError

DEFAULT_API_URL = "http://localhost:8000"
INVESTIGATION_TIMEOUT_SECONDS = 300.0
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class InvestigationError(Exception):
    """Raised when the API is unreachable or returns an unusable response."""


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
    confidence: Confidence
    supporting_evidence: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class InvestigationWindow:
    """Authoritative API timestamps, independent of generated report prose."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class IncidentReport:
    """The structured report returned by POST /api/v1/investigations."""

    summary: str
    likely_causes: tuple[LikelyCause, ...]
    next_steps: tuple[str, ...]
    confidence: Confidence
    investigation_window: InvestigationWindow | None = None


_REPORT_ADAPTER = TypeAdapter(IncidentReport)


def _api_url() -> str:
    return os.environ.get("INCIDENT_COPILOT_API_URL", DEFAULT_API_URL)


def fetch_health() -> dict[str, object]:
    """Return the API's health payload, or an unreachable placeholder."""
    try:
        response = httpx.get(f"{_api_url()}/health", timeout=5.0)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Health response must be an object")
        return dict(payload)
    except (httpx.HTTPError, ValueError):
        return {"status": "unreachable", "dependencies": {}}


def run_investigation(query: str, service: str | None, minutes_back: int) -> IncidentReport:
    """POST an investigation, validating the response before rendering it.

    HTTPX's timeout limits network inactivity per operation, not total wall time.
    A client timeout does not cancel the server's investigation.
    """
    payload = {"query": query, "service": service, "minutes_back": minutes_back}
    try:
        response = httpx.post(
            f"{_api_url()}/api/v1/investigations",
            json=payload,
            timeout=INVESTIGATION_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        raise InvestigationError(
            "The API timed out after 300 seconds without network progress. "
            "The investigation may still be running on the server."
        ) from exc
    except httpx.HTTPError as exc:
        raise InvestigationError(f"can't reach the API at {_api_url()}") from exc

    if response.status_code >= 400:
        detail = response.text
        try:
            error = response.json()
            if isinstance(error, dict):
                detail = str(error.get("detail", detail))
        except ValueError:
            pass
        raise InvestigationError(f"API error {response.status_code}: {detail[:1000]}")

    try:
        return _REPORT_ADAPTER.validate_json(response.content)
    except ValidationError as exc:
        raise InvestigationError("The API returned an invalid investigation report.") from exc
