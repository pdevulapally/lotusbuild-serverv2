"""Shared resilience primitives: timeout + retry/backoff + circuit breaking.

Every external client (LLM providers, e2b, Stripe, Firestore — added in
later phases) wraps its calls with `with_resilience(...)` instead of
re-implementing retry/backoff or circuit-breaking per client. See
docs/ARCHITECTURE.md §10.
"""
from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import TypeVar

import pybreaker
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

T = TypeVar("T")

_breakers: dict[str, pybreaker.CircuitBreaker] = {}


def get_breaker(name: str) -> pybreaker.CircuitBreaker:
    """Return the shared circuit breaker for an external system, creating it on first use."""
    if name not in _breakers:
        _breakers[name] = pybreaker.CircuitBreaker(
            fail_max=settings.circuit_breaker_fail_max,
            reset_timeout=settings.circuit_breaker_reset_timeout_seconds,
        )
    return _breakers[name]


def with_resilience(
    breaker_name: str,
    *,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
    max_attempts: int = 3,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator: wraps an async external call with retry/backoff and a named
    circuit breaker. A tripped breaker fails fast without being retried.
    """
    breaker = get_breaker(breaker_name)

    retryable = retry_if_exception_type(retry_exceptions) & retry_if_not_exception_type(
        pybreaker.CircuitBreakerError
    )

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=0.5, max=10),
            retry=retryable,
            reraise=True,
        )
        @functools.wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> T:
            async def _call() -> T:
                return await func(*args, **kwargs)

            return await breaker.call_async(_call)

        return wrapper

    return decorator
