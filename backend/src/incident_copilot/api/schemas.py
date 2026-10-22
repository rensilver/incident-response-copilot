"""Response models specific to the HTTP layer."""

from pydantic import BaseModel


class InvestigationErrorResponse(BaseModel):
    """Sanitized response when an investigation cannot produce a usable report."""

    detail: str


class HealthResponse(BaseModel):
    """Liveness plus reachability of each downstream dependency."""

    status: str
    dependencies: dict[str, bool]
