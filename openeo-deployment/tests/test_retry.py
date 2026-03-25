"""Tests for openeo_ai/utils/retry.py.

Verifies retry logic, exponential backoff calculation, circuit breaker
state transitions, and error recovery strategies -- all without network access.
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from openeo_ai.utils.retry import (
    RetryConfig,
    RetryResult,
    CircuitBreaker,
    calculate_delay,
    is_retryable_exception,
    is_retryable_status,
    retry_async,
    with_retry,
    ErrorRecoveryStrategy,
    get_circuit_breaker,
    reset_circuit_breaker,
    reset_all_circuit_breakers,
    RETRYABLE_EXCEPTIONS,
    RETRYABLE_STATUS_CODES,
)


# ---------------------------------------------------------------------------
# RetryConfig
# ---------------------------------------------------------------------------


class TestRetryConfig:
    """Tests for the RetryConfig dataclass defaults."""

    def test_default_values(self):
        """Verify sensible default values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_values(self):
        """Verify custom configuration."""
        config = RetryConfig(max_retries=5, initial_delay=0.5, jitter=False)

        assert config.max_retries == 5
        assert config.initial_delay == 0.5
        assert config.jitter is False


# ---------------------------------------------------------------------------
# calculate_delay
# ---------------------------------------------------------------------------


class TestCalculateDelay:
    """Tests for exponential backoff delay calculation."""

    def test_exponential_growth_no_jitter(self):
        """Delay should double with each attempt when jitter is off."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)

        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 4.0
        assert calculate_delay(3, config) == 8.0

    def test_max_delay_capped(self):
        """Delay should not exceed max_delay."""
        config = RetryConfig(
            initial_delay=1.0, exponential_base=2.0, max_delay=5.0, jitter=False
        )

        assert calculate_delay(10, config) == 5.0

    def test_jitter_varies_delay(self):
        """With jitter enabled, delays should vary across calls."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=True)

        delays = [calculate_delay(2, config) for _ in range(20)]
        # All delays should be positive
        assert all(d > 0 for d in delays)
        # With jitter, delays should not all be exactly 4.0
        assert len(set(delays)) > 1


# ---------------------------------------------------------------------------
# is_retryable_exception / is_retryable_status
# ---------------------------------------------------------------------------


class TestRetryableChecks:
    """Tests for retryable exception and status code checks."""

    def test_timeout_is_retryable(self):
        """httpx.TimeoutException should be retryable."""
        config = RetryConfig()
        exc = httpx.TimeoutException("timeout")
        assert is_retryable_exception(exc, config) is True

    def test_connect_error_is_retryable(self):
        """httpx.ConnectError should be retryable."""
        config = RetryConfig()
        exc = httpx.ConnectError("connect failed")
        assert is_retryable_exception(exc, config) is True

    def test_value_error_is_not_retryable(self):
        """ValueError should NOT be retryable by default."""
        config = RetryConfig()
        exc = ValueError("bad value")
        assert is_retryable_exception(exc, config) is False

    def test_retryable_status_codes(self):
        """Standard retryable HTTP status codes."""
        config = RetryConfig()
        for code in [408, 429, 500, 502, 503, 504]:
            assert is_retryable_status(code, config) is True

    def test_non_retryable_status_codes(self):
        """Client errors like 400, 401, 404 should not be retryable."""
        config = RetryConfig()
        for code in [400, 401, 403, 404]:
            assert is_retryable_status(code, config) is False


# ---------------------------------------------------------------------------
# retry_async
# ---------------------------------------------------------------------------


class TestRetryAsync:
    """Tests for the retry_async function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Function that succeeds immediately should return after 1 attempt."""
        func = AsyncMock(return_value="ok")
        result = await retry_async(func, config=RetryConfig(max_retries=3))

        assert result.success is True
        assert result.result == "ok"
        assert result.attempts == 1
        assert result.retries_exhausted is False
        func.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_success_after_retries(self):
        """Function that fails then succeeds should return the success."""
        func = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                httpx.TimeoutException("timeout"),
                "success",
            ]
        )
        config = RetryConfig(max_retries=3, initial_delay=0.01, jitter=False)
        result = await retry_async(func, config=config)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_retries_exhausted(self):
        """When all retries fail, result should indicate exhaustion."""
        func = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )
        config = RetryConfig(max_retries=2, initial_delay=0.01, jitter=False)
        result = await retry_async(func, config=config)

        assert result.success is False
        assert result.retries_exhausted is True
        assert result.error is not None
        # max_retries=2 means attempts 0, 1, 2 = 3 total
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception_stops_immediately(self):
        """A non-retryable exception should not be retried and should fail."""
        func = AsyncMock(side_effect=ValueError("bad input"))
        config = RetryConfig(max_retries=3, initial_delay=0.01)
        result = await retry_async(func, config=config)

        assert result.success is False
        assert isinstance(result.error, ValueError)
        # The implementation breaks out of the loop when should_retry is False,
        # but still increments attempts for the final failed attempt
        assert result.retries_exhausted is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_execution(self):
        """Verify that an open circuit breaker prevents execution."""
        func = AsyncMock(return_value="ok")
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=999)
        cb.record_failure()  # Open the breaker

        config = RetryConfig(max_retries=3)
        result = await retry_async(func, config=config, circuit_breaker=cb)

        assert result.success is False
        assert "Circuit breaker" in str(result.error)
        func.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_total_time_tracked(self):
        """Verify total_time is tracked in the result."""
        func = AsyncMock(return_value="ok")
        result = await retry_async(func, config=RetryConfig())

        assert result.total_time >= 0


# ---------------------------------------------------------------------------
# RetryResult
# ---------------------------------------------------------------------------


class TestRetryResult:
    """Tests for the RetryResult dataclass."""

    def test_to_dict(self):
        """Verify serialization of RetryResult."""
        rr = RetryResult(
            success=True,
            result="data",
            attempts=2,
            total_time=1.234,
            retries_exhausted=False,
        )
        d = rr.to_dict()

        assert d["success"] is True
        assert d["attempts"] == 2
        assert d["total_time"] == 1.23
        assert d["retries_exhausted"] is False
        assert d["error"] is None

    def test_to_dict_with_error(self):
        """Verify error is stringified in to_dict."""
        rr = RetryResult(
            success=False,
            error=ValueError("test error"),
            attempts=3,
            total_time=5.0,
            retries_exhausted=True,
        )
        d = rr.to_dict()

        assert d["success"] is False
        assert "test error" in d["error"]


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Tests for the CircuitBreaker class."""

    def test_initial_state_is_closed(self):
        """Circuit breaker starts in closed state."""
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.can_execute() is True

    def test_opens_after_threshold_failures(self):
        """Circuit opens after failure_threshold failures."""
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_execute() is False

    def test_success_resets_failure_count(self):
        """Successful operation resets failure counter in closed state."""
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # Reset counter

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"  # Not yet at threshold

    def test_half_open_after_recovery_timeout(self):
        """Circuit transitions to half-open after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == "open"

        time.sleep(0.02)
        assert cb.state == "half-open"
        assert cb.can_execute() is True

    def test_half_open_success_closes_circuit(self):
        """Successful request in half-open state closes the circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_requests=1)
        cb.record_failure()

        time.sleep(0.02)
        assert cb.state == "half-open"

        cb.record_success()
        assert cb.state == "closed"

    def test_half_open_failure_reopens_circuit(self):
        """Failed request in half-open state reopens the circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()

        time.sleep(0.02)
        assert cb.state == "half-open"

        cb.record_failure()
        assert cb.state == "open"

    def test_reset(self):
        """Reset should return circuit to initial closed state."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.state == "open"

        cb.reset()
        assert cb.state == "closed"
        assert cb.can_execute() is True

    def test_half_open_limits_requests(self):
        """Half-open state should limit concurrent requests."""
        cb = CircuitBreaker(
            failure_threshold=1, recovery_timeout=0.01, half_open_requests=1
        )
        cb.record_failure()
        time.sleep(0.02)

        assert cb.can_execute() is True
        # Simulate one in-flight request completing
        cb._half_open_count = 1
        assert cb.can_execute() is False


# ---------------------------------------------------------------------------
# with_retry decorator
# ---------------------------------------------------------------------------


class TestWithRetryDecorator:
    """Tests for the @with_retry decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Decorated function should return result on success."""
        @with_retry(config=RetryConfig(max_retries=2, initial_delay=0.01))
        async def my_func():
            return 42

        assert await my_func() == 42

    @pytest.mark.asyncio
    async def test_decorator_raises_on_exhaustion(self):
        """Decorated function should raise when retries are exhausted."""
        call_count = 0

        @with_retry(config=RetryConfig(max_retries=1, initial_delay=0.01))
        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("timeout")

        with pytest.raises(httpx.TimeoutException):
            await failing_func()


# ---------------------------------------------------------------------------
# ErrorRecoveryStrategy
# ---------------------------------------------------------------------------


class TestErrorRecoveryStrategy:
    """Tests for user-friendly error recovery messages."""

    def test_connection_error_message(self):
        """Connection errors should return recoverable message."""
        msg = ErrorRecoveryStrategy.get_recovery_message(
            ConnectionError("connection refused")
        )

        assert msg["error_type"] == "connection"
        assert msg["recoverable"] is True
        assert msg["retry_recommended"] is True

    def test_timeout_error_message(self):
        """Timeout errors should suggest smaller extents."""
        msg = ErrorRecoveryStrategy.get_recovery_message(
            TimeoutError("request timeout")
        )

        assert msg["error_type"] == "timeout"
        assert msg["recoverable"] is True

    def test_rate_limit_error_message(self):
        """429 errors should include retry_delay."""
        msg = ErrorRecoveryStrategy.get_recovery_message(
            Exception("HTTP 429: rate limit exceeded")
        )

        assert msg["error_type"] == "rate_limit"
        assert msg["retry_delay"] == 60

    def test_auth_error_message(self):
        """401 errors should NOT be retryable."""
        msg = ErrorRecoveryStrategy.get_recovery_message(
            Exception("HTTP 401 Unauthorized")
        )

        assert msg["error_type"] == "auth"
        assert msg["recoverable"] is False
        assert msg["retry_recommended"] is False

    def test_not_found_error_message(self):
        """404 errors should NOT be retryable."""
        msg = ErrorRecoveryStrategy.get_recovery_message(
            Exception("404 not found")
        )

        assert msg["error_type"] == "not_found"
        assert msg["recoverable"] is False

    def test_server_error_message(self):
        """500 errors should be retryable."""
        msg = ErrorRecoveryStrategy.get_recovery_message(
            Exception("HTTP 503 Service Unavailable")
        )

        assert msg["error_type"] == "server"
        assert msg["recoverable"] is True

    def test_unknown_error_message(self):
        """Unrecognised errors get 'unknown' type."""
        msg = ErrorRecoveryStrategy.get_recovery_message(
            Exception("something weird happened")
        )

        assert msg["error_type"] == "unknown"
        assert msg["recoverable"] is False


# ---------------------------------------------------------------------------
# Global circuit breaker helpers
# ---------------------------------------------------------------------------


class TestGlobalCircuitBreakers:
    """Tests for the global circuit breaker management functions."""

    def test_get_circuit_breaker_creates_new(self):
        """get_circuit_breaker should create a new breaker if not existing."""
        reset_all_circuit_breakers()
        cb = get_circuit_breaker("test-service")

        assert isinstance(cb, CircuitBreaker)
        assert cb.state == "closed"

    def test_get_circuit_breaker_returns_same_instance(self):
        """get_circuit_breaker should return the same object for same name."""
        reset_all_circuit_breakers()
        cb1 = get_circuit_breaker("test-svc")
        cb2 = get_circuit_breaker("test-svc")

        assert cb1 is cb2

    def test_reset_circuit_breaker(self):
        """reset_circuit_breaker should reset a specific breaker."""
        reset_all_circuit_breakers()
        cb = get_circuit_breaker("svc")
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        reset_circuit_breaker("svc")
        assert cb.state == "closed"

    def test_reset_all_circuit_breakers(self):
        """reset_all_circuit_breakers should reset every breaker."""
        reset_all_circuit_breakers()
        cb1 = get_circuit_breaker("a")
        cb2 = get_circuit_breaker("b")
        for _ in range(5):
            cb1.record_failure()
            cb2.record_failure()

        reset_all_circuit_breakers()
        assert cb1.state == "closed"
        assert cb2.state == "closed"
