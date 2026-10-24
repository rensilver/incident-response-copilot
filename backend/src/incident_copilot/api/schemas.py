"""Response models specific to the HTTP layer."""

from typing import Literal

from pydantic import BaseModel


class InvestigationErrorResponse(BaseModel):
    """Sanitized response when an investigation cannot produce a usable report."""

    detail: str


class HealthResponse(BaseModel):
    """Liveness plus reachability of each downstream dependency."""

    status: Literal["ok", "degraded"]
    dependencies: dict[str, bool]


class ValidationIssue(BaseModel):
    """A rejected field without its input, context, or parser diagnostics."""

    loc: list[str | int]
    msg: str
    type: str


class RequestErrorResponse(BaseModel):
    """Sanitized validation errors using FastAPI's field-location convention."""

    detail: list[ValidationIssue]
