import json

from incident_copilot.agents.correlation_agent import build_correlation_agent
from incident_copilot.agents.state import initial_state
from incident_copilot.llm.fake_provider import FakeLLMProvider
from incident_copilot.models.enums import MetricKind, TrendKind
from incident_copilot.models.findings import RawMetricFinding, TypedMetricFinding
from incident_copilot.models.metrics import TimeWindow

REPORT = json.dumps(
    {
        "summary": "cart-service regression after v1.5.0",
        "likely_causes": [
            {
                "title": "bad deploy",
                "rationale": "5xx stepped up at the deploy",
                "confidence": 0.8,
                "supporting_evidence": [{"source": "metrics", "detail": "error rate rose"}],
            }
        ],
        "next_steps": ["roll back v1.5.0"],
        "confidence": 0.8,
    }
)


def _typed(anomaly: bool, summary: str) -> TypedMetricFinding:
    return TypedMetricFinding(
        service="cart-service",
        query="rate(...)",
        metric_kind=MetricKind.ERROR_RATE,
        series=(),
        summary=summary,
        trend=TrendKind.ROSE,
        baseline_value=0.01,
        current_value=0.15,
        absolute_delta=0.14,
        pct_change=1400.0,
        anomaly_detected=anomaly,
    )


def _raw(summary: str) -> RawMetricFinding:
    return RawMetricFinding(
        service="",
        query="up",
        series=(),
        summary=summary,
        trend=TrendKind.FLAT,
        baseline_value=1.0,
        current_value=1.0,
        absolute_delta=0.0,
        pct_change=0.0,
        anomaly_detected=False,
    )


def _state(metrics: list[object]):  # type: ignore[no-untyped-def]  # test helper
    state = initial_state(
        correlation_id="cid",
        query="why is cart-service failing?",
        time_window=TimeWindow.from_minutes_back(60),
        target_service="cart-service",
    )
    state["metrics_findings"] = metrics  # type: ignore[typeddict-item]  # test fixture
    return state


async def test_produces_a_structured_report() -> None:
    provider = FakeLLMProvider([REPORT])
    result = await build_correlation_agent(provider)(_state([_typed(True, "rose")]))
    report = result["report"]
    assert report is not None
    assert report.likely_causes[0].title == "bad deploy"


async def test_every_finding_reaches_the_prompt_including_non_anomalous_and_raw() -> None:
    """Spec §6: guards against a future filter-on-anomaly_detected optimisation."""
    provider = FakeLLMProvider([REPORT])
    findings = [
        _typed(True, "ANOMALOUS-MARKER"),
        _typed(False, "QUIET-MARKER"),
        _raw("RAW-MARKER"),
    ]
    await build_correlation_agent(provider)(_state(findings))

    prompt = provider.calls[0][-1].content
    assert "ANOMALOUS-MARKER" in prompt
    assert "QUIET-MARKER" in prompt
    assert "RAW-MARKER" in prompt


async def test_malformed_model_output_is_recorded_not_raised() -> None:
    """A dead correlation step must return a state, not explode the graph."""
    provider = FakeLLMProvider(["not json", "still not", "nope"])
    result = await build_correlation_agent(provider)(_state([_typed(True, "rose")]))
    assert result["report"] is None
    assert result["errors"]
