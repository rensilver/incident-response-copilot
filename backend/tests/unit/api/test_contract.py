"""Public application errors stay typed and never echo private payloads."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import httpx
import pytest
from pydantic import ValidationError

from incident_copilot.api.schemas import HealthResponse
from incident_copilot.main import create_app
from incident_copilot.models.enums import LLMFailureKind
from incident_copilot.models.report import IncidentReport
from incident_copilot.services.incident_service import InvestigationRequest
from incident_copilot.utils.exceptions import (
    ConnectorError,
    InvestigationTimeoutError,
    LLMProviderError,
    LLMUpstreamError,
)


@asynccontextmanager
async def client_for(error: Exception | None = None) -> AsyncIterator[httpx.AsyncClient]:
    class Service:
        async def investigate(self, request: InvestigationRequest) -> IncidentReport:
            if error is not None:
                raise error
            return cast(IncidentReport, {"confidence": 2, "summary": "private-canary"})

    app = create_app()
    app.state.service = Service()
    app.state.health_checks = {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.parametrize("error", [RuntimeError("private-canary"), None])
async def test_server_bugs_and_invalid_outputs_are_sanitized_json(error: Exception | None) -> None:
    async with client_for(error) as client:
        response = await client.post("/api/v1/investigations", json={"query": "q"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}


@pytest.mark.parametrize(
    "error",
    [
        ConnectorError("private-canary"),
        LLMProviderError("private-canary"),
        LLMUpstreamError(LLMFailureKind.AUTHENTICATION),
        LLMUpstreamError(LLMFailureKind.QUOTA),
        LLMUpstreamError(LLMFailureKind.TIMEOUT),
    ],
)
async def test_unavailable_dependencies_have_a_stable_response(error: Exception) -> None:
    async with client_for(error) as client:
        response = await client.post("/api/v1/investigations", json={"query": "q"})
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Investigation unavailable; no usable report was produced."
    }


async def test_total_deadline_has_a_distinct_status() -> None:
    async with client_for(InvestigationTimeoutError("private-canary")) as client:
        response = await client.post("/api/v1/investigations", json={"query": "q"})
    assert response.status_code == 504
    assert response.json() == {"detail": "Investigation deadline exceeded."}


async def test_invalid_input_does_not_echo_the_rejected_value() -> None:
    async with client_for() as client:
        response = await client.post(
            "/api/v1/investigations", json={"query": "q", "minutes_back": "private-canary"}
        )
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "loc": ["body", "minutes_back"],
                "msg": "Invalid request value.",
                "type": "int_parsing",
            }
        ]
    }
    assert "private-canary" not in response.text


async def test_malformed_json_uses_the_same_validation_shape() -> None:
    async with client_for() as client:
        response = await client.post(
            "/api/v1/investigations",
            content='{"query": private-canary}',
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "json_invalid"
    assert set(response.json()["detail"][0]) == {"loc", "msg", "type"}
    assert "private-canary" not in response.text


def test_health_status_has_a_closed_vocabulary() -> None:
    with pytest.raises(ValidationError):
        HealthResponse(status="maybe", dependencies={})


def test_openapi_documents_application_error_and_health_contracts() -> None:
    schema = create_app().openapi()
    responses = schema["paths"]["/api/v1/investigations"]["post"]["responses"]
    for status in ("422", "500", "503", "504"):
        assert "application/json" in responses[status]["content"]
    assert schema["components"]["schemas"]["HealthResponse"]["properties"]["status"]["enum"] == [
        "ok",
        "degraded",
    ]
