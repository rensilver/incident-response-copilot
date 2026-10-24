"""Same-origin browser routing requires no direct cross-origin API grants."""

import httpx
import pytest

from incident_copilot.main import create_app


@pytest.mark.parametrize(
    "origin", ["http://localhost:3001", "http://127.0.0.1:3001", "https://other.example.test"]
)
async def test_backend_does_not_grant_cross_origin_browser_access(origin: str) -> None:
    app = create_app()
    app.state.health_checks = {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://backend"
    ) as client:
        preflight = await client.options(
            "/api/v1/investigations",
            headers={
                "origin": origin,
                "access-control-request-method": "POST",
                "access-control-request-headers": "content-type",
            },
        )
        health = await client.get("/health", headers={"origin": origin})

    assert preflight.status_code == 405
    assert health.status_code == 200
    for response in (preflight, health):
        assert "access-control-allow-origin" not in response.headers
        assert "access-control-allow-credentials" not in response.headers
