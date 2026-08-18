from incident_copilot.models.enums import LLMProviderName, MetricKind, TrendKind


def test_metric_kind_contains_only_requestable_kinds() -> None:
    """MetricKind is an input vocabulary shown to the LLM; RAW must not appear."""
    assert {k.value for k in MetricKind} == {"latency_p95", "error_rate", "memory", "cpu"}


def test_trend_kind_members() -> None:
    assert {t.value for t in TrendKind} == {"rose", "dropped", "flat", "from_zero"}


def test_provider_names() -> None:
    assert LLMProviderName.OLLAMA.value == "ollama"
