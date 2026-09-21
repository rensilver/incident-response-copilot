import httpx
import pytest
import respx

from incident_copilot.config.settings import Settings
from incident_copilot.main import _llm_health


@respx.mock
async def test_groq_health_checks_configured_model_and_sends_auth():
    route = respx.get("https://api.groq.com/openai/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "openai/gpt-oss-20b"}]})
    )
    assert await _llm_health(Settings(_env_file=None))()
    assert route.calls[0].request.headers["Authorization"] == "Bearer test-key"


@pytest.mark.parametrize("fallback,expected", [("ollama", True), ("none", False)])
@respx.mock
async def test_auth_failure_uses_only_enabled_fallback(fallback, expected):
    respx.get("https://api.groq.com/openai/v1/models").mock(return_value=httpx.Response(401))
    if fallback == "ollama":
        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})
        )
    assert await _llm_health(Settings(_env_file=None, llm_fallback_provider=fallback))() is expected


@respx.mock
async def test_ollama_server_without_required_model_is_unhealthy():
    respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    assert not await _llm_health(Settings(_env_file=None, llm_provider="ollama"))()
