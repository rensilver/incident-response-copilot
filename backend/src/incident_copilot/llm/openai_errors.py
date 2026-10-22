"""Translate SDK failures before they reach application or tracing callbacks."""

from collections.abc import Awaitable

from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError

from incident_copilot.models.enums import LLMFailureKind
from incident_copilot.utils.exceptions import LLMUpstreamError


def _failure_kind(error: APIError) -> LLMFailureKind:
    """Classify using SDK types/status/codes, never arbitrary error messages."""
    # APITimeoutError is a subclass of APIConnectionError.
    if isinstance(error, APITimeoutError):
        return LLMFailureKind.TIMEOUT
    if isinstance(error, APIConnectionError):
        return LLMFailureKind.CONNECTION
    if isinstance(error, APIStatusError):
        if error.status_code in (401, 403):
            return LLMFailureKind.AUTHENTICATION
        if error.status_code == 429:
            if error.code in ("insufficient_quota", "billing_hard_limit_reached"):
                return LLMFailureKind.QUOTA
            return LLMFailureKind.RATE_LIMIT
        if error.status_code == 408:
            return LLMFailureKind.TIMEOUT
        if error.status_code in (400, 404, 422):
            return LLMFailureKind.INVALID_REQUEST
    return LLMFailureKind.SERVICE


async def invoke_openai[T](operation: Awaitable[T]) -> T:
    """Raise domain failures without retaining raw SDK exceptions or responses.

    Raising after the except block avoids implicit exception context: simply
    suppressing its display with ``from None`` still retains credentials in memory.
    Cancellation and existing domain errors pass through unchanged.
    """
    try:
        return await operation
    except APIError as error:
        failure = LLMUpstreamError(_failure_kind(error))
    except ValueError:
        # LangChain raises ValueError for a Responses error payload. The string
        # can contain arbitrary upstream content, so use a generic service error.
        failure = LLMUpstreamError(LLMFailureKind.SERVICE)
    raise failure
