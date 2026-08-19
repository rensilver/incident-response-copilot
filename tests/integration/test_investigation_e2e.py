import httpx
import pytest

from incident_copilot.config.settings import Settings
from incident_copilot.main import create_app
from incident_copilot.models.enums import LLMProviderName

pytestmark = pytest.mark.integration

SCENARIOS = [
    ("cart-service", "cart-service is returning 5xx errors after a deploy"),
    ("checkout-service", "checkout-service memory keeps climbing"),
    ("payment-service", "payment-service latency has degraded"),
]


def _client() -> httpx.AsyncClient:
    settings = Settings(_env_file=None, llm_provider=LLMProviderName.OLLAMA)
    app = create_app(settings)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=300.0
    )


async def test_health_reports_every_dependency_up(require_ollama: None) -> None:
    async with _client() as client:
        body = (await client.get("/health")).json()
    assert body["dependencies"]["prometheus"] is True
    assert body["dependencies"]["elasticsearch"] is True
    assert body["dependencies"]["llm"] is True
    assert body["status"] == "ok"


@pytest.mark.parametrize(("service", "query"), SCENARIOS)
async def test_investigation_produces_an_evidenced_report(
    require_ollama: None, service: str, query: str
) -> None:
    """The pipeline must produce a valid report citing real evidence for each scenario."""
    async with _client() as client:
        response = await client.post(
            "/api/v1/investigations",
            json={"query": query, "service": service, "minutes_back": 180},
        )

    assert response.status_code == 200, response.text
    report = response.json()

    assert report["summary"]
    assert report["likely_causes"], "a report with no causes is useless"
    for cause in report["likely_causes"]:
        assert cause["supporting_evidence"], f"unevidenced cause survived: {cause['title']}"

    confidences = [c["confidence"] for c in report["likely_causes"]]
    assert confidences == sorted(confidences, reverse=True), "causes must be ranked"

    print(f"\n[{service}] {report['summary']}")
    for cause in report["likely_causes"]:
        print(f"  - {cause['confidence']:.2f} {cause['title']}")
