# ABOUTME: Retry utilities with exponential backoff for resilient API calls.
# Provides decorators and functions for automatic error recovery.

"""
Retry utilities for OpenEO AI Assistant.

Provides exponential backoff, circuit breakers, and error recovery
strategies for resilient API operations.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import (
    Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union
)

import httpx

logger = logging.getLogger(__name__)

T = TypeVar('T')


# Default retryable exceptions
RETRYABLE_EXCEPTIONS: Set[Type[Exception]] = {
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    ConnectionError,
    TimeoutError,
}

# HTTP status codes that should trigger retry
RETRYABLE_STATUS_CODES: Set[int] = {
    408,  # Request Timeout
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Set[Type[Exception]] = field(
        default_factory=lambda: RETRYABLE_EXCEPTIONS.copy()
    )
    retryable_status_codes: Set[int] = field(
        default_factory=lambda: RETRYABLE_STATUS_CODES.copy()
    )


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    result: Any = None
    error: Optional[Exception] = None
    attempts: int = 0
    total_time: float = 0.0
    retries_exhausted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "attempts": self.attempts,
            "total_time": round(self.total_time, 2),
            "retries_exhausted": self.retries_exhausted,
            "error": str(self.error) if self.error else None,
        }


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by failing fast when error threshold is reached.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_requests: int = 1
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            half_open_requests: Requests allowed in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"  # closed, open, half-open
        self._half_open_count = 0

    @property
    def state(self) -> str:
        """Get current circuit state."""
        self._check_recovery()
        return self._state

    def _check_recovery(self):
        """Check if circuit should transition to half-open."""
        if self._state == "open" and self._last_failure_time:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = "half-open"
                self._half_open_count = 0
                logger.info("Circuit breaker transitioning to half-open")

    def record_success(self):
        """Record a successful operation."""
        if self._state == "half-open":
            self._half_open_count += 1
            if self._half_open_count >= self.half_open_requests:
                self._state = "closed"
                self._failure_count = 0
                logger.info("Circuit breaker closed after successful recovery")
        elif self._state == "closed":
            self._failure_count = 0

    def record_failure(self):
        """Record a failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == "half-open":
            self._state = "open"
            logger.warning("Circuit breaker reopened after half-open failure")
        elif self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )

    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        self._check_recovery()

        if self._state == "closed":
            return True
        elif self._state == "half-open":
            return self._half_open_count < self.half_open_requests
        else:  # open
            return False

    def reset(self):
        """Reset circuit breaker to initial state."""
        self._failure_count = 0
        self._last_failure_time = None
        self._state = "closed"
        self._half_open_count = 0


def calculate_delay(
    attempt: int,
    config: RetryConfig
) -> float:
    """
    Calculate delay for retry attempt with exponential backoff.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    import random

    delay = config.initial_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        delay = delay * (0.5 + random.random())

    return delay


def is_retryable_exception(
    exception: Exception,
    config: RetryConfig
) -> bool:
    """Check if exception should trigger retry."""
    return any(
        isinstance(exception, exc_type)
        for exc_type in config.retryable_exceptions
    )


def is_retryable_status(
    status_code: int,
    config: RetryConfig
) -> bool:
    """Check if HTTP status code should trigger retry."""
    return status_code in config.retryable_status_codes


async def retry_async(
    func: Callable[..., Any],
    *args,
    config: Optional[RetryConfig] = None,
    circuit_breaker: Optional[CircuitBreaker] = None,
    **kwargs
) -> RetryResult:
    """
    Execute async function with retry logic.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        config: Retry configuration
        circuit_breaker: Optional circuit breaker
        **kwargs: Keyword arguments for func

    Returns:
        RetryResult with success/failure info
    """
    config = config or RetryConfig()
    start_time = time.time()
    last_exception: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        # Check circuit breaker
        if circuit_breaker and not circuit_breaker.can_execute():
            return RetryResult(
                success=False,
                error=Exception("Circuit breaker is open"),
                attempts=attempt,
                total_time=time.time() - start_time,
            )

        try:
            result = await func(*args, **kwargs)

            # Check for HTTP response with error status
            if hasattr(result, 'status_code'):
                if is_retryable_status(result.status_code, config):
                    raise httpx.HTTPStatusError(
                        f"HTTP {result.status_code}",
                        request=getattr(result, 'request', None),
                        response=result
                    )

            # Success
            if circuit_breaker:
                circuit_breaker.record_success()

            return RetryResult(
                success=True,
                result=result,
                attempts=attempt + 1,
                total_time=time.time() - start_time,
            )

        except Exception as e:
            last_exception = e

            if circuit_breaker:
                circuit_breaker.record_failure()

            # Check if we should retry
            should_retry = (
                attempt < config.max_retries and
                (
                    is_retryable_exception(e, config) or
                    (hasattr(e, 'response') and
                     is_retryable_status(e.response.status_code, config))
                )
            )

            if should_retry:
                delay = calculate_delay(attempt, config)
                logger.warning(
                    f"Retry {attempt + 1}/{config.max_retries} after {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)
            else:
                break

    return RetryResult(
        success=False,
        error=last_exception,
        attempts=config.max_retries + 1,
        total_time=time.time() - start_time,
        retries_exhausted=True,
    )


def with_retry(
    config: Optional[RetryConfig] = None,
    circuit_breaker: Optional[CircuitBreaker] = None
):
    """
    Decorator for adding retry logic to async functions.

    Args:
        config: Retry configuration
        circuit_breaker: Optional circuit breaker

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await retry_async(
                func, *args,
                config=config,
                circuit_breaker=circuit_breaker,
                **kwargs
            )
            if result.success:
                return result.result
            else:
                raise result.error or Exception("Retry failed")
        return wrapper
    return decorator


# Error recovery strategies
class ErrorRecoveryStrategy:
    """Strategies for recovering from specific errors."""

    @staticmethod
    def get_recovery_message(error: Exception) -> Dict[str, Any]:
        """
        Get user-friendly error message with recovery suggestions.

        Args:
            error: The exception that occurred

        Returns:
            Dict with error info and suggestions
        """
        error_str = str(error).lower()

        # Connection errors
        if any(x in error_str for x in ['connection', 'connect', 'network']):
            return {
                "error_type": "connection",
                "message": "Unable to connect to the server",
                "suggestions": [
                    "Check your internet connection",
                    "The server may be temporarily unavailable",
                    "Try again in a few moments"
                ],
                "recoverable": True,
                "retry_recommended": True
            }

        # Timeout errors
        if 'timeout' in error_str:
            return {
                "error_type": "timeout",
                "message": "The request timed out",
                "suggestions": [
                    "The operation is taking longer than expected",
                    "Consider using a smaller spatial extent",
                    "Try running as a background job"
                ],
                "recoverable": True,
                "retry_recommended": True
            }

        # Rate limiting
        if '429' in error_str or 'rate limit' in error_str:
            return {
                "error_type": "rate_limit",
                "message": "Rate limit exceeded",
                "suggestions": [
                    "Too many requests in a short time",
                    "Please wait a moment before trying again",
                    "Consider batching your requests"
                ],
                "recoverable": True,
                "retry_recommended": True,
                "retry_delay": 60
            }

        # Authentication
        if '401' in error_str or 'unauthorized' in error_str:
            return {
                "error_type": "auth",
                "message": "Authentication required",
                "suggestions": [
                    "Your session may have expired",
                    "Check your credentials"
                ],
                "recoverable": False,
                "retry_recommended": False
            }

        # Not found
        if '404' in error_str or 'not found' in error_str:
            return {
                "error_type": "not_found",
                "message": "Resource not found",
                "suggestions": [
                    "Check the collection ID or path",
                    "The resource may have been moved or deleted"
                ],
                "recoverable": False,
                "retry_recommended": False
            }

        # Server errors
        if any(x in error_str for x in ['500', '502', '503', '504']):
            return {
                "error_type": "server",
                "message": "Server error occurred",
                "suggestions": [
                    "The server encountered an internal error",
                    "This is usually temporary",
                    "Try again in a few moments"
                ],
                "recoverable": True,
                "retry_recommended": True
            }

        # Default
        return {
            "error_type": "unknown",
            "message": str(error),
            "suggestions": [
                "An unexpected error occurred",
                "Check the error message for details"
            ],
            "recoverable": False,
            "retry_recommended": False
        }


# Global circuit breakers for different services
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(service: str) -> CircuitBreaker:
    """Get or create circuit breaker for a service."""
    if service not in _circuit_breakers:
        _circuit_breakers[service] = CircuitBreaker()
    return _circuit_breakers[service]


def reset_circuit_breaker(service: str):
    """Reset circuit breaker for a service."""
    if service in _circuit_breakers:
        _circuit_breakers[service].reset()


def reset_all_circuit_breakers():
    """Reset all circuit breakers."""
    for cb in _circuit_breakers.values():
        cb.reset()
