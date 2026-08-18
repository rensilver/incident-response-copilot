"""Enumerations used across the package."""

from enum import StrEnum


class AgentName(StrEnum):
    """Names of graph nodes that act as agents."""

    SUPERVISOR = "supervisor"
    METRICS = "metrics_agent"
    LOGS = "logs_agent"
    CORRELATION = "correlation_agent"


class MetricKind(StrEnum):
    """Semantic metric kinds an agent may request.

    This is strictly an *input* vocabulary: it is serialized into the
    ``get_service_metric`` tool schema and shown to the model, so it must contain only
    values that are legal to request. Raw-PromQL findings are modelled by a separate
    type rather than by a ``RAW`` member here.
    """

    LATENCY_P95 = "latency_p95"
    ERROR_RATE = "error_rate"
    MEMORY = "memory"
    CPU = "cpu"


class TrendKind(StrEnum):
    """Direction of change across an analysed window."""

    ROSE = "rose"
    DROPPED = "dropped"
    FLAT = "flat"
    FROM_ZERO = "from_zero"


class LogLevel(StrEnum):
    """Log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class EvidenceSource(StrEnum):
    """Which subsystem a piece of evidence came from."""

    METRICS = "metrics"
    LOGS = "logs"


class LLMProviderName(StrEnum):
    """Selectable LLM provider implementations."""

    OLLAMA = "ollama"
    GEMINI = "gemini"
    FAKE = "fake"
