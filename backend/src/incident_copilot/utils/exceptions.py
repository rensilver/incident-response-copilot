"""Exception hierarchy for the incident copilot."""


class IncidentCopilotError(Exception):
    """Base class for every error raised by this package."""


class ConfigurationError(IncidentCopilotError):
    """Settings are missing or invalid."""


class ConnectorError(IncidentCopilotError):
    """A downstream observability system could not be reached or understood."""


class MetricsSourceError(ConnectorError):
    """The metrics backend failed or returned an unusable payload."""


class LogSourceError(ConnectorError):
    """The log backend failed or returned an unusable payload."""


class LLMProviderError(IncidentCopilotError):
    """The LLM provider failed to produce a usable response."""


class StructuredOutputError(LLMProviderError):
    """The model could not be coerced into the requested schema."""

    def __init__(self, message: str, raw_output: str) -> None:
        """Initialise the error.

        Args:
            message: Human-readable description of the failure.
            raw_output: The last raw model output, retained for debugging.
        """
        super().__init__(message)
        self.raw_output = raw_output


class InvestigationError(IncidentCopilotError):
    """The investigation graph did not produce a usable report."""
