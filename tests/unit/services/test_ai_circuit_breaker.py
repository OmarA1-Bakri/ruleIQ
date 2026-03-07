"""

# Constants

Unit tests for AI Circuit Breaker functionality.

Tests the circuit breaker pattern implementation for AI services,
including failure tracking, state transitions, and model fallback logic.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from services.ai.circuit_breaker import AICircuitBreaker, CircuitBreakerConfig, CircuitState
from services.ai.exceptions import AIServiceException

from tests.test_constants import MAX_RETRIES


class TestAICircuitBreaker:
    """Test suite for AI Circuit Breaker functionality."""

    @pytest.fixture
    def circuit_breaker_config(self):
        """Circuit breaker configuration for testing."""
        return CircuitBreakerConfig(
            failure_threshold=3, recovery_timeout=60, success_threshold=2, time_window=60
        )

    @pytest.fixture
    def circuit_breaker(self, circuit_breaker_config):
        """Circuit breaker instance for testing."""
        return AICircuitBreaker(circuit_breaker_config)

    def test_circuit_breaker_initialization(self, circuit_breaker):
        """Test circuit breaker initializes correctly."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.total_requests == 0
        assert circuit_breaker.metrics.failed_requests == 0
        assert circuit_breaker.metrics.successful_requests == 0

    def test_model_availability_when_closed(self, circuit_breaker):
        """Test model availability when circuit is closed."""
        assert circuit_breaker.is_model_available("gemini-2.5-pro") is True
        assert circuit_breaker.is_model_available("gemini-2.5-flash") is True

    def test_record_success(self, circuit_breaker):
        """Test recording successful operations."""
        model_name = "gemini-2.5-pro"
        circuit_breaker.record_success(model_name)
        assert circuit_breaker.metrics.total_successes == 1
        assert circuit_breaker.metrics.total_requests == 1
        assert circuit_breaker.get_model_state(model_name) == CircuitState.CLOSED

    def test_record_failure(self, circuit_breaker):
        """Test recording failed operations."""
        model_name = "gemini-2.5-pro"
        error = AIServiceException("Test error")
        circuit_breaker.record_failure(model_name, error)
        assert circuit_breaker.metrics.total_failures == 1
        assert circuit_breaker.metrics.total_requests == 1
        assert len(circuit_breaker._failures[model_name]) == 1

    def test_circuit_opens_after_threshold_failures(self, circuit_breaker):
        """Test circuit opens after reaching failure threshold."""
        model_name = "gemini-2.5-pro"
        error = AIServiceException("Test error")
        for _ in range(circuit_breaker.config.failure_threshold):
            circuit_breaker.record_failure(model_name, error)
        assert circuit_breaker.get_model_state(model_name) == CircuitState.OPEN
        assert circuit_breaker.is_model_available(model_name) is False

    def test_circuit_transitions_to_half_open(self, circuit_breaker):
        """Test circuit transitions to half-open after timeout."""
        model_name = "gemini-2.5-pro"
        error = AIServiceException("Test error")
        for _ in range(circuit_breaker.config.failure_threshold):
            circuit_breaker.record_failure(model_name, error)
        circuit_breaker._last_failure_time = datetime.now(timezone.utc) - timedelta(
            seconds=circuit_breaker.config.timeout_seconds + 1
        )
        assert circuit_breaker.is_model_available(model_name) is True
        assert circuit_breaker.get_model_state(model_name) == CircuitState.HALF_OPEN

    def test_circuit_closes_after_successful_half_open(self, circuit_breaker):
        """Test circuit closes after successful operations in half-open state."""
        model_name = "gemini-2.5-pro"
        error = AIServiceException("Test error")
        for _ in range(circuit_breaker.config.failure_threshold):
            circuit_breaker.record_failure(model_name, error)
        circuit_breaker._last_failure_time = datetime.now(timezone.utc) - timedelta(
            seconds=circuit_breaker.config.timeout_seconds + 1
        )
        circuit_breaker.is_model_available(model_name)
        for _ in range(circuit_breaker.config.success_threshold):
            circuit_breaker.record_success(model_name)
        assert circuit_breaker.get_model_state(model_name) == CircuitState.CLOSED

    def test_synchronous_call_with_circuit_breaker(self, circuit_breaker):
        """Test synchronous operation with circuit breaker protection."""
        model_name = "gemini-2.5-pro"

        def mock_operation():
            return "success"

        result = circuit_breaker.call_with_circuit_breaker(model_name, mock_operation)
        assert result == "success"
        assert circuit_breaker.metrics.total_successes == 1

    @pytest.mark.asyncio
    async def test_asynchronous_call_with_circuit_breaker(self, circuit_breaker):
        """Test asynchronous operation with circuit breaker protection."""
        model_name = "gemini-2.5-pro"

        async def mock_async_operation():
            return "async_success"

        result = await circuit_breaker.async_call_with_circuit_breaker(
            model_name, mock_async_operation
        )
        assert result == "async_success"
        assert circuit_breaker.metrics.total_successes == 1

    def test_circuit_breaker_blocks_when_open(self, circuit_breaker):
        """Test circuit breaker blocks operations when open."""
        model_name = "gemini-2.5-pro"
        error = AIServiceException("Test error")
        for _ in range(circuit_breaker.config.failure_threshold):
            circuit_breaker.record_failure(model_name, error)

        def mock_operation():
            return "should_not_execute"

        with pytest.raises(AIServiceException) as exc_info:
            circuit_breaker.call_with_circuit_breaker(model_name, mock_operation)
        assert "Circuit breaker is OPEN" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_circuit_breaker_blocks_when_open(self, circuit_breaker):
        """Test async circuit breaker blocks operations when open."""
        model_name = "gemini-2.5-pro"
        error = AIServiceException("Test error")
        for _ in range(circuit_breaker.config.failure_threshold):
            circuit_breaker.record_failure(model_name, error)

        async def mock_async_operation():
            return "should_not_execute"

        with pytest.raises(AIServiceException) as exc_info:
            await circuit_breaker.async_call_with_circuit_breaker(model_name, mock_async_operation)
        assert "Circuit breaker is OPEN" in str(exc_info.value)

    def test_multiple_models_independent_circuits(self, circuit_breaker):
        """Test that different models have independent circuit states."""
        model1 = "gemini-2.5-pro"
        model2 = "gemini-2.5-flash"
        error = AIServiceException("Test error")
        for _ in range(circuit_breaker.config.failure_threshold):
            circuit_breaker.record_failure(model1, error)
        assert circuit_breaker.is_model_available(model1) is False
        assert circuit_breaker.is_model_available(model2) is True
        assert circuit_breaker.get_model_state(model1) == CircuitState.OPEN
        assert circuit_breaker.get_model_state(model2) == CircuitState.CLOSED

    def test_failure_cleanup(self, circuit_breaker):
        """Test that old failures are cleaned up."""
        model_name = "gemini-2.5-pro"
        error = AIServiceException("Test error")
        circuit_breaker.record_failure(model_name, error)
        circuit_breaker._failures[model_name][0].timestamp = datetime.now(timezone.utc) - timedelta(
            seconds=circuit_breaker.config.timeout_seconds + 1
        )
        circuit_breaker.record_failure(model_name, error)
        assert len(circuit_breaker._failures[model_name]) == 1

    def test_circuit_breaker_metrics(self, circuit_breaker):
        """Test circuit breaker metrics tracking."""
        model_name = "gemini-2.5-pro"
        error = AIServiceException("Test error")
        circuit_breaker.record_success(model_name)
        circuit_breaker.record_success(model_name)
        circuit_breaker.record_failure(model_name, error)
        metrics = circuit_breaker.metrics
        assert metrics.total_requests == MAX_RETRIES
        assert metrics.total_successes == 2
        assert metrics.total_failures == 1
        assert metrics.success_rate == 2 / 3

    def test_get_circuit_breaker_status(self, circuit_breaker):
        """Test getting comprehensive circuit breaker status."""
        model_name = "gemini-2.5-pro"
        circuit_breaker.record_success(model_name)
        status = circuit_breaker.get_status()
        assert "overall_state" in status
        assert "model_states" in status
        assert "metrics" in status
        assert model_name in status["model_states"]

    def test_manual_circuit_reset(self, circuit_breaker):
        """Test manual circuit breaker reset functionality."""
        model_name = "gemini-2.5-pro"
        error = AIServiceException("Test error")
        for _ in range(circuit_breaker.config.failure_threshold):
            circuit_breaker.record_failure(model_name, error)
        assert circuit_breaker.get_model_state(model_name) == CircuitState.OPEN
        circuit_breaker.reset_circuit(model_name)
        assert circuit_breaker.get_model_state(model_name) == CircuitState.CLOSED
        assert circuit_breaker.is_model_available(model_name) is True

    def test_health_check_integration(self, circuit_breaker):
        """Test health check integration with circuit breaker."""
        model_name = "gemini-2.5-pro"
        with patch.object(circuit_breaker, "_perform_health_check", return_value=True):
            health_status = circuit_breaker.check_model_health(model_name)
            assert health_status is True
        with patch.object(circuit_breaker, "_perform_health_check", return_value=False):
            health_status = circuit_breaker.check_model_health(model_name)
            assert health_status is False
