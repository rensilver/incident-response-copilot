"""Response models specific to the HTTP layer."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness plus reachability of each downstream dependency."""

    status: str
    dependencies: dict[str, bool]
