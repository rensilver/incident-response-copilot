"""Declarative definitions of the three seeded incident scenarios.

These are pure data. Rendering them into OpenMetrics text or Elasticsearch documents
happens in :mod:`incident_copilot.demo.metrics_render` and
:mod:`incident_copilot.demo.logs_render`, so the shapes here stay testable with no I/O.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from incident_copilot.models.enums import LogLevel


class ScenarioName(StrEnum):
    """Identifier for each seeded scenario."""

    MEMORY_LEAK = "memory_leak"
    SLOW_DEPENDENCY = "slow_dependency"
    BAD_DEPLOY = "bad_deploy"


class MetricShape(StrEnum):
    """How a service's metrics evolve across the incident window."""

    STEADY = "steady"
    RAMP = "ramp"
    SAWTOOTH = "sawtooth"
    STEP = "step"


@dataclass(frozen=True)
class LogTemplate:
    """A log line emitted during a phase of the incident.

    Attributes:
        level: Severity of the emitted document.
        message: Message body.
        phase_start: Fraction of the window (0.0-1.0) at which this starts appearing.
        per_hour: Rough emission rate while active.
        use_version_after: Tag the document with the post-deploy version.
    """

    level: LogLevel
    message: str
    phase_start: float = 0.0
    per_hour: int = 6
    use_version_after: bool = False


@dataclass(frozen=True)
class ServiceProfile:
    """How one service behaves during one scenario.

    Attributes:
        service: Service name, used as the ``service`` label everywhere.
        latency_shape: Shape of p95 latency across the window.
        latency_base: Baseline p95 latency in seconds.
        latency_peak: Peak p95 latency in seconds at the end of the window.
        error_ratio_base: Baseline fraction of requests returning 5xx.
        error_ratio_peak: Peak fraction of requests returning 5xx.
        memory_shape: Shape of resident memory across the window.
        memory_base_mib: Baseline resident memory in MiB.
        memory_peak_mib: Peak resident memory in MiB.
        cpu_base: Baseline CPU cores consumed.
        cpu_peak: Peak CPU cores consumed.
        anomaly_start: Fraction of the window at which this service degrades.
        version_before: ``version`` label before the deploy.
        version_after: ``version`` label after the deploy.
        logs: Log templates emitted by this service.
    """

    service: str
    latency_shape: MetricShape = MetricShape.STEADY
    latency_base: float = 0.12
    latency_peak: float = 0.12
    error_ratio_base: float = 0.002
    error_ratio_peak: float = 0.002
    memory_shape: MetricShape = MetricShape.STEADY
    memory_base_mib: float = 512.0
    memory_peak_mib: float = 512.0
    cpu_base: float = 0.25
    cpu_peak: float = 0.25
    anomaly_start: float = 0.5
    version_before: str = "v1.4.2"
    version_after: str = "v1.4.2"
    logs: tuple[LogTemplate, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Scenario:
    """One seeded incident: services, their behaviour, and the answer.

    Service names must be unique across scenarios. All three are seeded into the same
    Prometheus, so a name reused between scenarios produces two writes to the identical
    series at identical timestamps, silently blending the two curves.
    """

    name: ScenarioName
    title: str
    ground_truth: str
    culprit: str
    services: tuple[ServiceProfile, ...]


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name=ScenarioName.MEMORY_LEAK,
        title="checkout-service memory leak",
        ground_truth=(
            "checkout-service leaks memory until it is OOM-killed and restarted; "
            "latency drifts up with GC pressure"
        ),
        culprit="checkout-service",
        services=(
            ServiceProfile(
                service="checkout-service",
                latency_shape=MetricShape.RAMP,
                latency_base=0.11,
                latency_peak=0.48,
                memory_shape=MetricShape.SAWTOOTH,
                memory_base_mib=380.0,
                memory_peak_mib=1900.0,
                cpu_base=0.30,
                cpu_peak=0.85,
                anomaly_start=0.1,
                logs=(
                    LogTemplate(
                        level=LogLevel.WARN,
                        message="GC overhead limit approaching; heap usage 92%",
                        phase_start=0.55,
                        per_hour=12,
                    ),
                    LogTemplate(
                        level=LogLevel.ERROR,
                        message="java.lang.OutOfMemoryError: Java heap space",
                        phase_start=0.85,
                        per_hour=8,
                    ),
                    LogTemplate(
                        level=LogLevel.INFO,
                        message="Container restarted after OOM-kill (exit code 137)",
                        phase_start=0.92,
                        per_hour=3,
                    ),
                ),
            ),
            ServiceProfile(service="inventory-service"),
        ),
    ),
    Scenario(
        name=ScenarioName.SLOW_DEPENDENCY,
        title="fraud-api latency degrades payment-service",
        ground_truth=(
            "fraud-api latency degradation propagates to payment-service; "
            "fraud-api p95 rises first"
        ),
        culprit="fraud-api",
        services=(
            ServiceProfile(
                service="fraud-api",
                latency_shape=MetricShape.RAMP,
                latency_base=0.08,
                latency_peak=1.90,
                anomaly_start=0.30,
                cpu_base=0.20,
                cpu_peak=0.55,
            ),
            ServiceProfile(
                service="payment-service",
                latency_shape=MetricShape.RAMP,
                latency_base=0.14,
                latency_peak=0.82,
                error_ratio_base=0.003,
                error_ratio_peak=0.025,
                anomaly_start=0.45,
                logs=(
                    LogTemplate(
                        level=LogLevel.WARN,
                        message="upstream timeout calling fraud-api after 2000ms",
                        phase_start=0.48,
                        per_hour=30,
                    ),
                    LogTemplate(
                        level=LogLevel.ERROR,
                        message="PaymentAuthorizationException: fraud check unavailable",
                        phase_start=0.65,
                        per_hour=10,
                    ),
                ),
            ),
        ),
    ),
    Scenario(
        name=ScenarioName.BAD_DEPLOY,
        title="cart-service v1.5.0 regression",
        ground_truth="cart-service release v1.5.0 introduced a 5xx regression",
        culprit="cart-service",
        services=(
            ServiceProfile(
                service="cart-service",
                latency_shape=MetricShape.STEP,
                latency_base=0.13,
                latency_peak=0.21,
                error_ratio_base=0.0,
                error_ratio_peak=0.15,
                anomaly_start=0.6,
                version_before="v1.4.2",
                version_after="v1.5.0",
                logs=(
                    LogTemplate(
                        level=LogLevel.ERROR,
                        message=(
                            "NullPointerException at "
                            "com.shop.cart.PromotionEngine.applyDiscount(PromotionEngine.java:88)"
                        ),
                        phase_start=0.6,
                        per_hour=45,
                        use_version_after=True,
                    ),
                    LogTemplate(
                        level=LogLevel.INFO,
                        message="Deployment complete: cart-service v1.5.0",
                        phase_start=0.6,
                        per_hour=2,
                        use_version_after=True,
                    ),
                ),
            ),
            ServiceProfile(service="shipping-service"),
        ),
    ),
)

_BY_NAME = {s.name: s for s in SCENARIOS}


def get_scenario(name: ScenarioName) -> Scenario:
    """Return the scenario with the given name.

    Args:
        name: Scenario identifier.

    Returns:
        The matching :class:`Scenario`.

    Raises:
        KeyError: If no scenario has that name.
    """
    try:
        return _BY_NAME[name]
    except KeyError as exc:
        raise KeyError(f"unknown scenario: {name!r}") from exc
