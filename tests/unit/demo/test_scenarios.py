import pytest

from incident_copilot.demo.scenarios import SCENARIOS, ScenarioName, get_scenario


def test_three_scenarios_are_defined() -> None:
    assert {s.name for s in SCENARIOS} == {
        ScenarioName.MEMORY_LEAK,
        ScenarioName.SLOW_DEPENDENCY,
        ScenarioName.BAD_DEPLOY,
    }


def test_every_scenario_has_ground_truth_and_a_culprit_service() -> None:
    for scenario in SCENARIOS:
        assert scenario.ground_truth
        assert scenario.culprit in {p.service for p in scenario.services}


def test_slow_dependency_culprit_is_the_upstream_not_the_loud_service() -> None:
    """The point of this scenario: fraud-api degrades first, payment-service is loud."""
    scenario = get_scenario(ScenarioName.SLOW_DEPENDENCY)
    assert scenario.culprit == "fraud-api"
    assert "payment-service" in {p.service for p in scenario.services}


def test_bad_deploy_flips_version_label() -> None:
    scenario = get_scenario(ScenarioName.BAD_DEPLOY)
    cart = next(p for p in scenario.services if p.service == "cart-service")
    assert cart.version_before == "v1.4.2"
    assert cart.version_after == "v1.5.0"


def test_scenarios_do_not_share_service_names() -> None:
    """All three seed into one Prometheus; a shared name blends two curves into one series."""
    seen: set[str] = set()
    for scenario in SCENARIOS:
        names = {p.service for p in scenario.services}
        assert not (names & seen), f"{scenario.name} reuses {names & seen}"
        seen |= names


def test_get_scenario_rejects_unknown_name() -> None:
    with pytest.raises(KeyError, match="unknown scenario"):
        get_scenario("not-a-scenario")  # type: ignore[arg-type]  # deliberate
