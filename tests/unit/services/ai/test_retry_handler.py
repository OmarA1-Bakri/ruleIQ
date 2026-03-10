"""Tests for services/ai/retry_handler.py - Retry handler with backoff strategies."""

import os
import pytest
from unittest.mock import AsyncMock

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.ai.retry_handler import (
    RetryStrategy,
    RetryConfig,
    RetryAttempt,
    RetryHandler,
    retry_on_failure,
    get_retry_handler,
    DEFAULT_RETRY_CONFIG,
    AGGRESSIVE_RETRY_CONFIG,
    CONSERVATIVE_RETRY_CONFIG,
)
from services.ai.exceptions import (
    AIServiceException,
    ModelOverloadedException,
    ModelRetryExhaustedException,
    ModelTimeoutException,
    ModelUnavailableException,
    CircuitBreakerException,
)


# --- RetryStrategy Enum ---
class TestRetryStrategy:
    def test_values(self):
        assert RetryStrategy.EXPONENTIAL_BACKOFF.value == "exponential_backoff"
        assert RetryStrategy.LINEAR_BACKOFF.value == "linear_backoff"
        assert RetryStrategy.FIBONACCI_BACKOFF.value == "fibonacci_backoff"

    def test_count(self):
        assert len(RetryStrategy) == 3


# --- RetryConfig ---
class TestRetryConfig:
    def test_defaults(self):
        c = RetryConfig()
        assert c.max_attempts == 3
        assert c.base_delay == 1.0
        assert c.max_delay == 60.0
        assert c.exponential_base == 2.0
        assert c.jitter is True
        assert c.strategy == RetryStrategy.EXPONENTIAL_BACKOFF

    def test_post_init_defaults(self):
        c = RetryConfig()
        assert ModelTimeoutException in c.retryable_exceptions
        assert ModelOverloadedException in c.retryable_exceptions
        assert AIServiceException in c.retryable_exceptions
        assert ModelUnavailableException in c.non_retryable_exceptions
        assert CircuitBreakerException in c.non_retryable_exceptions
        assert ValueError in c.non_retryable_exceptions

    def test_custom_exceptions(self):
        c = RetryConfig(
            retryable_exceptions=[ValueError],
            non_retryable_exceptions=[TypeError],
        )
        assert c.retryable_exceptions == [ValueError]
        assert c.non_retryable_exceptions == [TypeError]


# --- RetryAttempt ---
class TestRetryAttempt:
    def test_creation(self):
        a = RetryAttempt(attempt_number=1, model_name="gpt-4", delay=0.0)
        assert a.attempt_number == 1
        assert a.success is False
        assert a.exception is None

    def test_duration_with_times(self):
        a = RetryAttempt(
            attempt_number=1,
            model_name="gpt-4",
            delay=0.0,
            start_time=100.0,
            end_time=101.5,
        )
        assert a.duration == 1.5

    def test_duration_without_times(self):
        a = RetryAttempt(attempt_number=1, model_name="gpt-4", delay=0.0)
        assert a.duration is None


# --- RetryHandler ---
class TestRetryHandlerShouldRetry:
    def test_within_attempts_retryable(self):
        h = RetryHandler()
        exc = AIServiceException(message="test")
        assert h.should_retry(exc, attempt_number=1) is True

    def test_exceeded_attempts(self):
        h = RetryHandler()
        exc = AIServiceException(message="test")
        assert h.should_retry(exc, attempt_number=3) is False

    def test_non_retryable_exception(self):
        h = RetryHandler()
        assert h.should_retry(ValueError("bad"), attempt_number=1) is False

    def test_circuit_breaker_not_retryable(self):
        h = RetryHandler()
        exc = CircuitBreakerException(circuit_state="open")
        assert h.should_retry(exc, attempt_number=1) is False

    def test_unknown_exception_not_retried(self):
        h = RetryHandler()
        assert h.should_retry(RuntimeError("unknown"), attempt_number=1) is False


class TestRetryHandlerCalculateDelay:
    def test_exponential(self):
        h = RetryHandler(RetryConfig(jitter=False))
        assert h.calculate_delay(1) == 1.0
        assert h.calculate_delay(2) == 2.0
        assert h.calculate_delay(3) == 4.0

    def test_linear(self):
        h = RetryHandler(
            RetryConfig(strategy=RetryStrategy.LINEAR_BACKOFF, jitter=False)
        )
        assert h.calculate_delay(1) == 1.0
        assert h.calculate_delay(2) == 2.0
        assert h.calculate_delay(3) == 3.0

    def test_fibonacci(self):
        h = RetryHandler(
            RetryConfig(strategy=RetryStrategy.FIBONACCI_BACKOFF, jitter=False)
        )
        d1 = h.calculate_delay(1)
        d2 = h.calculate_delay(2)
        d3 = h.calculate_delay(3)
        assert d1 == 1.0
        assert d2 == 1.0
        assert d3 == 2.0

    def test_max_delay_cap(self):
        h = RetryHandler(RetryConfig(max_delay=5.0, jitter=False))
        assert h.calculate_delay(10) <= 5.0

    def test_jitter_modifies_delay(self):
        h = RetryHandler(RetryConfig(jitter=True, jitter_range=0.5))
        delays = {h.calculate_delay(2) for _ in range(20)}
        assert len(delays) > 1  # jitter should produce varied values


class TestRetryHandlerFibonacci:
    def test_base_cases(self):
        h = RetryHandler()
        # pylint: disable=protected-access
        assert h._fibonacci(1) == 1
        assert h._fibonacci(2) == 1

    def test_sequence(self):
        h = RetryHandler()
        # pylint: disable=protected-access
        assert h._fibonacci(3) == 2
        assert h._fibonacci(4) == 3
        assert h._fibonacci(5) == 5
        assert h._fibonacci(6) == 8


class TestRetrySync:
    def test_success_first_attempt(self):
        h = RetryHandler(RetryConfig(max_attempts=3))
        result = h.retry_sync(lambda: "ok", model_name="test")
        assert result == "ok"
        assert len(h.retry_history) == 1
        assert h.retry_history[0].success is True

    def test_success_after_retries(self):
        call_count = {"n": 0}

        def flaky():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise AIServiceException(message="temporary")
            return "recovered"

        h = RetryHandler(RetryConfig(max_attempts=3, base_delay=0.01, jitter=False))
        result = h.retry_sync(flaky, model_name="test")
        assert result == "recovered"

    def test_exhaust_retries(self):
        def always_fail():
            raise AIServiceException(message="permanent")

        h = RetryHandler(RetryConfig(max_attempts=2, base_delay=0.01, jitter=False))
        with pytest.raises(ModelRetryExhaustedException):
            h.retry_sync(always_fail, model_name="test")

    def test_non_retryable_stops_immediately(self):
        def bad():
            raise ValueError("invalid input")

        h = RetryHandler(RetryConfig(max_attempts=5, base_delay=0.01))
        with pytest.raises(ModelRetryExhaustedException):
            h.retry_sync(bad, model_name="test")
        assert len(h.retry_history) == 1


class TestRetryAsync:
    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        h = RetryHandler(RetryConfig(max_attempts=3))
        result = await h.retry_async(AsyncMock(return_value="ok"), model_name="test")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_exhaust_retries(self):
        async def always_fail():
            raise AIServiceException(message="fail")

        h = RetryHandler(RetryConfig(max_attempts=2, base_delay=0.01, jitter=False))
        with pytest.raises(ModelRetryExhaustedException):
            await h.retry_async(always_fail, model_name="test")


# --- Statistics ---
class TestRetryStatistics:
    def test_empty_history(self):
        h = RetryHandler()
        stats = h.get_retry_statistics()
        assert stats["total_attempts"] == 0

    def test_with_history(self):
        h = RetryHandler(RetryConfig(max_attempts=3, base_delay=0.01, jitter=False))
        h.retry_sync(lambda: "ok", model_name="test")
        stats = h.get_retry_statistics()
        assert stats["total_attempts"] == 1
        assert stats["successful_attempts"] == 1
        assert stats["success_rate"] == 1.0

    def test_clear_history(self):
        h = RetryHandler()
        h.retry_sync(lambda: "ok", model_name="test")
        assert len(h.retry_history) > 0
        h.clear_history()
        assert len(h.retry_history) == 0


# --- Module-level configs ---
class TestModuleConfigs:
    def test_default_config(self):
        assert DEFAULT_RETRY_CONFIG.max_attempts == 3
        assert DEFAULT_RETRY_CONFIG.strategy == RetryStrategy.EXPONENTIAL_BACKOFF

    def test_aggressive_config(self):
        assert AGGRESSIVE_RETRY_CONFIG.max_attempts == 5
        assert AGGRESSIVE_RETRY_CONFIG.max_delay == 30.0

    def test_conservative_config(self):
        assert CONSERVATIVE_RETRY_CONFIG.max_attempts == 2
        assert CONSERVATIVE_RETRY_CONFIG.strategy == RetryStrategy.LINEAR_BACKOFF


# --- get_retry_handler ---
class TestGetRetryHandler:
    def test_default(self):
        h = get_retry_handler("default")
        assert isinstance(h, RetryHandler)
        assert h.config.max_attempts == 3

    def test_aggressive(self):
        h = get_retry_handler("aggressive")
        assert isinstance(h, RetryHandler)
        assert h.config.max_attempts == 5

    def test_conservative(self):
        h = get_retry_handler("conservative")
        assert isinstance(h, RetryHandler)
        assert h.config.max_attempts == 2

    def test_unknown_returns_default(self):
        h = get_retry_handler("unknown_type")
        assert isinstance(h, RetryHandler)


# --- retry_on_failure decorator ---
class TestRetryOnFailureDecorator:
    def test_sync_decorator(self):
        @retry_on_failure(max_attempts=2, base_delay=0.01)
        def my_func():
            return "decorated_result"

        result = my_func()
        assert result == "decorated_result"

    @pytest.mark.asyncio
    async def test_async_decorator(self):
        @retry_on_failure(max_attempts=2, base_delay=0.01)
        async def my_async_func():
            return "async_result"

        result = await my_async_func()
        assert result == "async_result"
