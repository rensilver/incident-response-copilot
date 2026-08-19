from incident_copilot.demo.scenarios import ScenarioName
from incident_copilot.evaluation.scenarios import SCENARIOS


def test_every_scenario_name_is_covered_exactly_once() -> None:
    assert {s.name for s in SCENARIOS} == set(ScenarioName)
    assert len(SCENARIOS) == len(set(ScenarioName))


def test_slow_dependency_culprit_is_the_upstream_not_the_target() -> None:
    """The one scenario that actually tests correlation rather than the model just
    repeating back the service name it was asked about."""
    slow_dep = next(s for s in SCENARIOS if s.name == ScenarioName.SLOW_DEPENDENCY)
    assert slow_dep.target_service == "payment-service"
    assert slow_dep.expected_culprit == "fraud-api"


def test_bad_deploy_and_memory_leak_culprit_is_their_own_target_service() -> None:
    for name in (ScenarioName.BAD_DEPLOY, ScenarioName.MEMORY_LEAK):
        scenario = next(s for s in SCENARIOS if s.name == name)
        assert scenario.expected_culprit == scenario.target_service
