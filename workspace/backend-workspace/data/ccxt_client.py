"""
CCXT Client with Retry Logic
==============================
Wraps ccxt REST calls with exponential backoff retry.
Raises DataFetchError after all retries are exhausted.

Satisfies: Requirement 2.6
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class DataFetchError(RuntimeError):
    """
    Raised when a ccxt API call fails after all retries.
    Satisfies: Requirement 2.6
    """
    def __init__(self, operation: str, attempts: int, last_error: Exception) -> None:
        super().__init__(
            f"Data fetch failed for '{operation}' after {attempts} attempts. "
            f"Last error: {last_error}"
        )
        self.operation = operation
        self.attempts = attempts
        self.last_error = last_error


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """
    Decorator: retry a function on failure with exponential backoff.

    Delays: base_delay, base_delay*factor, base_delay*factor^2, ...
    Default: 1s, 2s, 4s

    Args:
        max_retries:    Maximum number of retry attempts (default 3)
        base_delay:     Initial delay in seconds (default 1.0)
        backoff_factor: Multiplier for each subsequent delay (default 2.0)
        exceptions:     Exception types to catch and retry on

    Raises:
        DataFetchError: after all retries are exhausted

    Satisfies: Requirement 2.6
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        delay = base_delay * (backoff_factor ** (attempt - 1))
                        logger.warning(
                            "%s attempt %d/%d failed: %s — retrying in %.1fs",
                            fn.__name__, attempt, max_retries, exc, delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            fn.__name__, max_retries, exc,
                        )
            raise DataFetchError(fn.__name__, max_retries, last_exc)

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        delay = base_delay * (backoff_factor ** (attempt - 1))
                        logger.warning(
                            "%s attempt %d/%d failed: %s — retrying in %.1fs",
                            fn.__name__, attempt, max_retries, exc, delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            fn.__name__, max_retries, exc,
                        )
            raise DataFetchError(fn.__name__, max_retries, last_exc)

        # Return the appropriate wrapper based on whether fn is async
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator  # type: ignore[return-value]
