"""Structured logging configuration."""

import logging

import structlog
from structlog.stdlib import BoundLogger

CORRELATION_ID_KEY = "correlation_id"


def configure_logging(level: str) -> None:
    """Configure structlog to emit JSON lines to stdout.

    Args:
        level: Log level name, e.g. ``"INFO"``.
    """
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper()))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> BoundLogger:
    """Return a bound logger for the given module name."""
    logger: BoundLogger = structlog.get_logger(name)
    return logger


def bind_correlation_id(correlation_id: str) -> None:
    """Bind a correlation ID onto every subsequent log line in this context."""
    structlog.contextvars.bind_contextvars(**{CORRELATION_ID_KEY: correlation_id})
