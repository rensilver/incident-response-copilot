import asyncio
import json
import os
from time import perf_counter

import httpx
import pytest

pytestmark = pytest.mark.integration

SCENARIOS = [
    ("cart-service", "cart-service is returning 5xx errors after a deploy"),
    ("checkout-service", "checkout-service memory keeps climbing"),
    ("payment-service", "payment-service latency has degraded"),
]


def _client() -> httpx.AsyncClient:
    # Exercise the running API and its configured provider, including Docker wiring.
    # Start it with `make docker-app-up` or `make serve` before running these tests.
    return httpx.AsyncClient(
        base_url=os.getenv("INCIDENT_COPILOT_API_URL", "http://localhost:8000"), timeout=300.0
    )


async def test_health_reports_every_dependency_up() -> None:
    async with _client() as client:
        response = await client.get("/health")
        assert response.status_code == 200, response.text
        body = response.json()
    assert body["dependencies"]["prometheus"] is True
    assert body["dependencies"]["elasticsearch"] is True
    assert body["dependencies"]["llm"] is True
    assert body["status"] == "ok"


@pytest.mark.parametrize(("service", "query"), SCENARIOS)
async def test_investigation_produces_an_evidenced_report(service: str, query: str) -> None:
    """Require a structured report with evidence entries; their accuracy is not scored."""
    # Optional pacing for cloud quotas. Failures are never retried or skipped.
    await asyncio.sleep(float(os.getenv("INCIDENT_COPILOT_SCENARIO_DELAY_SECONDS", "0")))
    payload = {"query": query, "service": service, "minutes_back": 180}
    started = perf_counter()
    async with _client() as client:
        response = await client.post(
            "/api/v1/investigations",
            json=payload,
        )
    elapsed = perf_counter() - started

    report = response.json()
    print(
        json.dumps(
            {
                "request": payload,
                "status_code": response.status_code,
                "elapsed_seconds": elapsed,
                "report": report,
            },
            ensure_ascii=False,
        )
    )
    assert response.status_code == 200, response.text

    assert report["summary"]
    assert report["likely_causes"], "a report with no causes is useless"
    for cause in report["likely_causes"]:
        assert cause["supporting_evidence"], f"unevidenced cause survived: {cause['title']}"

    confidences = [c["confidence"] for c in report["likely_causes"]]
    assert confidences == sorted(confidences, reverse=True), "causes must be ranked"
