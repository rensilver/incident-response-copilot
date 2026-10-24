"""Application-wide sanitized HTTP errors; unexpected exceptions remain server bugs."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from incident_copilot.api.schemas import (
    InvestigationErrorResponse,
    RequestErrorResponse,
    ValidationIssue,
)
from incident_copilot.utils.logging import get_logger

logger = get_logger(__name__)


def install_error_handlers(app: FastAPI) -> None:
    """Register JSON validation and server-error boundaries on the application.

    Args:
        app: Application whose errors must follow the public contract.
    """

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Omit rejected input and parser/validator context from client responses."""
        body = RequestErrorResponse(
            detail=[
                ValidationIssue(
                    loc=list(error["loc"]), msg="Invalid request value.", type=error["type"]
                )
                for error in exc.errors()
            ]
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception) -> JSONResponse:
        """Return a fixed message without exception text, requests, or tracebacks."""
        logger.error("api_server_error", error_type=type(exc).__name__)
        body = InvestigationErrorResponse(detail="Internal server error.")
        return JSONResponse(status_code=500, content=body.model_dump(mode="json"))
