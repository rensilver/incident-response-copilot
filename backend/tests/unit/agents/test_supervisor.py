import pytest

from incident_copilot.agents.state import initial_state
from incident_copilot.agents.supervisor import SPECIALISTS, build_supervisor
from incident_copilot.config.settings import Settings
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import AgentName
from incident_copilot.models.metrics import TimeWindow


def _state(iterations: int = 0):  # type: ignore[no-untyped-def]  # test helper
    state = initial_state(
        correlation_id="cid",
        query="cart-service is returning 5xx",
        time_window=TimeWindow.from_minutes_back(60),
        target_service="cart-service",
    )
    state["iterations"] = iterations
    return state


def _settings() -> Settings:
    return Settings(_env_file=None)


async def test_valid_route_is_honoured() -> None:
    provider = FakeLLMProvider(['{"agents": ["metrics_agent"], "reasoning": "metrics only"}'])
    result = await build_supervisor(provider, _settings())(_state())
    assert result["route"] == [AgentName.METRICS]


async def test_malformed_route_falls_back_to_both_specialists() -> None:
    """A 3b model emits junk often enough that this path is the difference between
    a working demo and a dead end."""
    provider = FakeLLMProvider(["not json", "still not json", "nope"])
    result = await build_supervisor(provider, _settings())(_state())
    assert set(result["route"]) == set(SPECIALISTS)
    assert any("fallback" in e for e in result["errors"])


async def test_route_naming_a_non_specialist_falls_back() -> None:
    """`correlation_agent` is a real AgentName, so this passes Pydantic but is not routable."""
    provider = FakeLLMProvider(['{"agents": ["correlation_agent"], "reasoning": "nope"}'])
    result = await build_supervisor(provider, _settings())(_state())
    assert set(result["route"]) == set(SPECIALISTS)


async def test_iteration_ceiling_skips_the_model_entirely() -> None:
    provider = FakeLLMProvider(['{"agents": ["metrics_agent"], "reasoning": "x"}'])
    settings = _settings()
    result = await build_supervisor(provider, settings)(
        _state(iterations=settings.max_supervisor_iterations)
    )
    assert set(result["route"]) == set(SPECIALISTS)
    assert provider.calls == []


async def test_supervisor_increments_iterations() -> None:
    provider = FakeLLMProvider(['{"agents": ["logs_agent"], "reasoning": "logs"}'])
    result = await build_supervisor(provider, _settings())(_state(iterations=1))
    assert result["iterations"] == 2


@pytest.mark.parametrize("agent", list(SPECIALISTS))
def test_specialists_are_exactly_the_two_data_agents(agent: AgentName) -> None:
    assert agent in {AgentName.METRICS, AgentName.LOGS}
