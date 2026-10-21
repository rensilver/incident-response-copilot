"""Ground-truth scenario data the evaluation harness scores against.

Reuses demo.scenarios.ScenarioName so a scenario can never drift between the seeded
demo data and the eval harness scoring it.
"""

from dataclasses import dataclass

from incident_copilot.demo.scenarios import ScenarioName


@dataclass(frozen=True)
class EvalScenario:
    """One scenario the harness runs and scores.

    Attributes:
        name: Which seeded scenario this is.
        query: The incident question sent to the investigation endpoint.
        target_service: The ``service`` field of the investigation request.
        expected_culprit: Substring to look for in the top-ranked cause, matched
            case-insensitively. Not always equal to ``target_service`` - see
            ``SLOW_DEPENDENCY`` below.
    """

    name: ScenarioName
    query: str
    target_service: str
    expected_culprit: str


SCENARIOS: tuple[EvalScenario, ...] = (
    EvalScenario(
        name=ScenarioName.BAD_DEPLOY,
        query="cart-service is returning 5xx errors after a deploy",
        target_service="cart-service",
        expected_culprit="cart-service",
    ),
    EvalScenario(
        name=ScenarioName.MEMORY_LEAK,
        query="checkout-service memory keeps climbing",
        target_service="checkout-service",
        expected_culprit="checkout-service",
    ),
    EvalScenario(
        name=ScenarioName.SLOW_DEPENDENCY,
        query="payment-service latency has degraded",
        target_service="payment-service",
        expected_culprit="fraud-api",
    ),
)
