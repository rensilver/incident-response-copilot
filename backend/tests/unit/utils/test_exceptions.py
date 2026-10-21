import pytest

from incident_copilot.utils.exceptions import (
    ConfigurationError,
    IncidentCopilotError,
    LLMProviderError,
    MetricsSourceError,
    StructuredOutputError,
)


@pytest.mark.parametrize(
    "exc",
    [ConfigurationError, MetricsSourceError, LLMProviderError, StructuredOutputError],
)
def test_all_errors_derive_from_root(exc: type[Exception]) -> None:
    assert issubclass(exc, IncidentCopilotError)


def test_structured_output_error_carries_raw_payload() -> None:
    err = StructuredOutputError("bad json", raw_output="{not json")
    assert err.raw_output == "{not json"
    assert "bad json" in str(err)
