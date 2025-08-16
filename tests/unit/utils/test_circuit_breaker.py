"""
Unit Tests for Circuit Breaker Implementation

Tests the circuit breaker pattern for protecting external services
from cascading failures and managing service resilience.
"""

import asyncio
import time

import pytest

from api.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenException,
    CircuitBreakerState,
)


@pytest.mark.unit
class TestCircuitBreakerStates:
    """Test circuit breaker state transitions"""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in closed state"""
        breaker = CircuitBreaker("test_service")

        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker._failure_count == 0
        assert breaker._success_count == 0

    def test_circuit_breaker_custom_config(self):
        """Test circuit breaker with custom configuration"""
        config = CircuitBreakerConfig(
            failure_threshold=3, recovery_timeout=30.0, success_threshold=2, timeout_seconds=10.0
        )

        breaker = CircuitBreaker("test_service", config)

        assert breaker.config.failure_threshold == 3
        assert breaker.config.recovery_timeout == 30.0
        assert breaker.config.success_threshold == 2
        assert breaker.config.timeout_seconds == 10.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after reaching failure threshold"""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test_service", config)

        async def failing_function():
            raise ConnectionError("Service unavailable")

        # First 2 failures should keep circuit closed
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_function)
            assert breaker.state == CircuitBreakerState.CLOSED

        # Third failure should open the circuit
        with pytest.raises(ConnectionError):
            await breaker.call(failing_function)

        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker._failure_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_calls_when_open(self):
        """Test circuit breaker blocks calls when open"""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test_service", config)

        async def failing_function():
            raise ConnectionError("Service unavailable")

        # Trigger failure to open circuit
        with pytest.raises(ConnectionError):
            await breaker.call(failing_function)

        assert breaker.state == CircuitBreakerState.OPEN

        # Subsequent calls should raise CircuitBreakerOpenException
        with pytest.raises(CircuitBreakerOpenException) as exc_info:
            await breaker.call(failing_function)

        assert "Circuit breaker open" in str(exc_info.value)
        assert "test_service" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_circuit_breaker_transitions_to_half_open(self):
        """Test circuit breaker transitions to half-open after recovery timeout"""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker("test_service", config)

        async def failing_function():
            raise ConnectionError("Service unavailable")

        # Open the circuit
        with pytest.raises(ConnectionError):
            await breaker.call(failing_function)

        assert breaker.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Circuit should transition to half-open
        assert breaker.state == CircuitBreakerState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_after_successful_calls(self):
        """Test circuit breaker closes after successful calls in half-open state"""
        config = CircuitBreakerConfig(
            failure_threshold=1, recovery_timeout=0.1, success_threshold=2
        )
        breaker = CircuitBreaker("test_service", config)

        call_count = 0

        async def function_that_recovers():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Service unavailable")
            return f"Success {call_count}"

        # Open the circuit
        with pytest.raises(ConnectionError):
            await breaker.call(function_that_recovers)

        assert breaker.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        assert breaker.state == CircuitBreakerState.HALF_OPEN

        # First successful call
        result1 = await breaker.call(function_that_recovers)
        assert result1 == "Success 2"
        assert breaker.state == CircuitBreakerState.HALF_OPEN

        # Second successful call should close the circuit
        result2 = await breaker.call(function_that_recovers)
        assert result2 == "Success 3"
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_reopens_on_failure_in_half_open(self):
        """Test circuit breaker reopens on failure in half-open state"""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker("test_service", config)

        call_count = 0

        async def intermittent_function():
            nonlocal call_count
            call_count += 1
            if call_count in [1, 3]:  # Fail on first and third calls
                raise ConnectionError("Service unavailable")
            return f"Success {call_count}"

        # Open the circuit
        with pytest.raises(ConnectionError):
            await breaker.call(intermittent_function)

        assert breaker.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        assert breaker.state == CircuitBreakerState.HALF_OPEN

        # Successful call
        result = await breaker.call(intermittent_function)
        assert result == "Success 2"

        # Failure should reopen the circuit
        with pytest.raises(ConnectionError):
            await breaker.call(intermittent_function)

        assert breaker.state == CircuitBreakerState.OPEN


@pytest.mark.unit
class TestCircuitBreakerTimeout:
    """Test circuit breaker timeout functionality"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_timeout_success(self):
        """Test circuit breaker with timeout - successful call"""
        config = CircuitBreakerConfig(timeout_seconds=1.0)
        breaker = CircuitBreaker("test_service", config)

        async def fast_function():
            await asyncio.sleep(0.1)  # Complete within timeout
            return "Success"

        result = await breaker.call(fast_function)
        assert result == "Success"
        assert breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_timeout_failure(self):
        """Test circuit breaker with timeout - timeout exceeded"""
        config = CircuitBreakerConfig(timeout_seconds=0.1, failure_threshold=1)
        breaker = CircuitBreaker("test_service", config)

        async def slow_function():
            await asyncio.sleep(0.5)  # Exceed timeout
            return "Success"

        with pytest.raises(asyncio.TimeoutError):
            await breaker.call(slow_function)

        assert breaker.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_no_timeout_when_disabled(self):
        """Test circuit breaker without timeout when disabled"""
        config = CircuitBreakerConfig(timeout_seconds=None)
        breaker = CircuitBreaker("test_service", config)

        async def slow_function():
            await asyncio.sleep(0.2)
            return "Success"

        result = await breaker.call(slow_function)
        assert result == "Success"


@pytest.mark.unit
class TestCircuitBreakerExceptionHandling:
    """Test circuit breaker exception handling"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_handles_expected_exceptions(self):
        """Test circuit breaker counts expected exceptions as failures"""
        config = CircuitBreakerConfig(
            failure_threshold=2, expected_exception=(ConnectionError, TimeoutError)
        )
        breaker = CircuitBreaker("test_service", config)

        async def function_with_expected_error():
            raise ConnectionError("Expected error")

        # First expected exception
        with pytest.raises(ConnectionError):
            await breaker.call(function_with_expected_error)

        assert breaker._failure_count == 1
        assert breaker.state == CircuitBreakerState.CLOSED

        # Second expected exception should open circuit
        with pytest.raises(ConnectionError):
            await breaker.call(function_with_expected_error)

        assert breaker._failure_count == 2
        assert breaker.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_ignores_unexpected_exceptions(self):
        """Test circuit breaker doesn't count unexpected exceptions as failures"""
        config = CircuitBreakerConfig(failure_threshold=1, expected_exception=(ConnectionError,))
        breaker = CircuitBreaker("test_service", config)

        async def function_with_unexpected_error():
            raise ValueError("Unexpected error")

        # Unexpected exception should not count as failure
        with pytest.raises(ValueError):
            await breaker.call(function_with_unexpected_error)

        assert breaker._failure_count == 0
        assert breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_handles_multiple_exception_types(self):
        """Test circuit breaker handles multiple expected exception types"""
        config = CircuitBreakerConfig(
            failure_threshold=3, expected_exception=(ConnectionError, TimeoutError, OSError)
        )
        breaker = CircuitBreaker("test_service", config)

        exceptions = [
            ConnectionError("Connection failed"),
            TimeoutError("Timeout occurred"),
            OSError("OS error"),
        ]

        for i, exc in enumerate(exceptions):

            async def failing_function():
                raise exc

            with pytest.raises(type(exc)):
                await breaker.call(failing_function)

            assert breaker._failure_count == i + 1

        assert breaker.state == CircuitBreakerState.OPEN


@pytest.mark.unit
class TestCircuitBreakerDecorator:
    """Test circuit breaker as decorator"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_decorator_usage(self):
        """Test using circuit breaker as a decorator"""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test_service", config)

        call_count = 0

        @breaker
        async def decorated_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Service unavailable")
            return f"Success on attempt {call_count}"

        # First two calls should fail
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await decorated_function()

        assert breaker.state == CircuitBreakerState.OPEN

        # Third call should be blocked by circuit breaker
        with pytest.raises(CircuitBreakerOpenException):
            await decorated_function()

    @pytest.mark.asyncio
    async def test_circuit_breaker_decorator_preserves_function_metadata(self):
        """Test circuit breaker decorator preserves function metadata"""
        breaker = CircuitBreaker("test_service")

        @breaker
        async def example_function():
            """Example function docstring"""
            return "result"

        # Function metadata should be preserved
        assert example_function.__name__ == "example_function"
        assert "Example function docstring" in example_function.__doc__


@pytest.mark.unit
class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics and monitoring"""

    def test_circuit_breaker_exception_details(self):
        """Test CircuitBreakerOpenException contains useful details"""
        service_name = "external_api"
        failure_count = 5
        recovery_time = 45.5

        exception = CircuitBreakerOpenException(service_name, failure_count, recovery_time)

        assert service_name in str(exception)
        assert str(failure_count) in str(exception)
        assert exception.details["service_name"] == service_name
        assert exception.details["failure_count"] == failure_count
        assert exception.details["recovery_time"] == recovery_time
        assert exception.status_code == 503

    def test_circuit_breaker_state_timing(self):
        """Test circuit breaker tracks state timing correctly"""
        breaker = CircuitBreaker("test_service")

        initial_time = breaker._last_state_change
        assert initial_time > 0

        # State change time should be tracked using the same time source
        current_time = time.time()
        assert abs(initial_time - current_time) < 1.0  # Within 1 second

    @pytest.mark.asyncio
    async def test_circuit_breaker_success_tracking(self):
        """Test circuit breaker tracks successful calls correctly"""
        config = CircuitBreakerConfig(
            failure_threshold=1, recovery_timeout=0.1, success_threshold=2
        )
        breaker = CircuitBreaker("test_service", config)

        call_count = 0

        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Initial failure")
            return f"Success {call_count}"

        # Trigger failure
        with pytest.raises(ConnectionError):
            await breaker.call(test_function)

        # Wait for half-open
        await asyncio.sleep(0.15)

        # Track successful calls
        assert breaker._success_count == 0

        await breaker.call(test_function)
        assert breaker._success_count == 1

        await breaker.call(test_function)
        assert breaker._success_count >= breaker.config.success_threshold
        assert breaker.state == CircuitBreakerState.CLOSED


@pytest.mark.unit
class TestPreconfiguredCircuitBreakers:
    """Test preconfigured circuit breakers for common services"""

    def test_openai_circuit_breaker_config(self):
        """Test OpenAI circuit breaker has appropriate configuration"""
        from api.utils.circuit_breaker import openai_breaker

        assert openai_breaker.name == "OpenAI"
        assert openai_breaker.config.failure_threshold == 3
        assert openai_breaker.config.recovery_timeout == 30.0
        assert openai_breaker.config.timeout_seconds == 60.0

    def test_google_circuit_breaker_config(self):
        """Test Google circuit breaker has appropriate configuration"""
        from api.utils.circuit_breaker import google_breaker

        assert google_breaker.name == "Google"
        assert google_breaker.config.failure_threshold == 5
        assert google_breaker.config.recovery_timeout == 60.0
        assert google_breaker.config.timeout_seconds == 30.0

    def test_aws_circuit_breaker_config(self):
        """Test AWS circuit breaker has appropriate configuration"""
        from api.utils.circuit_breaker import aws_breaker

        assert aws_breaker.name == "AWS"
        assert aws_breaker.config.failure_threshold == 5
        assert aws_breaker.config.recovery_timeout == 45.0
        assert aws_breaker.config.timeout_seconds == 30.0


@pytest.mark.unit
class TestCircuitBreakerConcurrency:
    """Test circuit breaker thread safety and concurrency"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_concurrent_calls(self):
        """Test circuit breaker handles concurrent calls correctly"""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test_service", config)

        call_count = 0
        
        async def concurrent_function():
            nonlocal call_count
            call_count += 1
            # Always fail for the first 5 calls to ensure consistent behavior
            if call_count <= 5:
                raise ConnectionError("Concurrent failure")
            return "Success"

        # Execute multiple concurrent calls
        tasks = []
        for _ in range(5):
            # Create coroutine for each call
            task = asyncio.create_task(breaker.call(concurrent_function))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Some calls should fail with ConnectionError, others might be blocked by circuit breaker
        connection_errors = sum(1 for r in results if isinstance(r, ConnectionError))
        circuit_breaker_errors = sum(
            1 for r in results if isinstance(r, CircuitBreakerOpenException)
        )
        success_results = sum(1 for r in results if isinstance(r, str))

        # All results should be either connection errors or circuit breaker errors (no successes)
        assert connection_errors + circuit_breaker_errors == len(results), f"Got unexpected successes: {success_results}"
        # Circuit should be open after processing
        assert breaker.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_lock_prevents_race_conditions(self):
        """Test circuit breaker lock prevents race conditions"""
        breaker = CircuitBreaker("test_service")

        # Test that internal state changes are atomic
        async def state_check_function():
            # This should not cause race conditions
            state_before = breaker.state
            await asyncio.sleep(0.01)  # Small delay
            state_after = breaker.state
            return state_before == state_after

        # Run multiple concurrent state checks
        tasks = [breaker.call(state_check_function) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All state checks should be consistent
        assert all(results)
