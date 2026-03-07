"""

Integrated error handler with circuit breaker pattern for LangGraph nodes.
Provides comprehensive error handling, retry logic, and circuit breaking.
"""

import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Callable
from uuid import uuid4
from functools import wraps
from langgraph_agent.graph.unified_state import UnifiedComplianceState

logger = logging.getLogger(__name__)


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


class IntegratedErrorHandler:
    """
    Complete error handler with circuit breaker pattern for all nodes.
    Tracks failures per node and implements circuit breaking to prevent cascading failures.
    """

    def __init__(
        self, failure_threshold: int = 3, recovery_timeout: int = 60, half_open_requests: int = 1
    ) -> None:
        """
        Initialize error handler with circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            half_open_requests: Number of test requests in half-open state
        """
        self.circuit_breakers = {}
        self.error_counts = {}
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        self.retryable_errors = [ConnectionError, TimeoutError, OSError]

    async def handle_node_error(
        self, node_name: str, error: Exception, state: UnifiedComplianceState
    ) -> UnifiedComplianceState:
        """
        Handle errors with circuit breaker pattern.

        Args:
            node_name: Name of the node that failed
            error: The exception that occurred
            state: Current workflow state

        Returns:
            Updated state with error handling decisions
        """
        error_id = str(uuid4())
        error_details = {
            "id": error_id,
            "node": node_name,
            "error": str(error),
            "type": type(error).__name__,
            "timestamp": datetime.now().isoformat(),
            "traceback": traceback.format_exc(),
            "retry_count": state.get("retry_count", 0),
        }
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(error_details)
        state["error_count"] = len(state["errors"])
        state["error_correlation_id"] = error_id
        logger.error(
            f"Error in node {node_name}: {error}",
            extra={"error_id": error_id, "node": node_name, "error_type": type(error).__name__},
        )
        breaker_state = self._check_circuit_breaker(node_name)
        if breaker_state == "OPEN":
            logger.error(f"Circuit breaker OPEN for {node_name}, failing workflow")
            state["circuit_breaker_status"][node_name] = "OPEN"
            state["workflow_status"] = "FAILED"
            state["should_continue"] = False
            state["metadata"]["failure_reason"] = f"Circuit breaker open for {node_name}"
        elif breaker_state == "HALF_OPEN":
            logger.info(f"Circuit breaker HALF_OPEN for {node_name}, attempting test request")
            state["circuit_breaker_status"][node_name] = "HALF_OPEN"
            if self._is_retryable_error(error):
                state["should_continue"] = True
                state["current_step"] = node_name
            else:
                self._open_circuit(node_name)
                state["workflow_status"] = "FAILED"
                state["should_continue"] = False
        else:
            self._record_failure(node_name)
            if self._should_open_circuit(node_name):
                self._open_circuit(node_name)
                state["circuit_breaker_status"][node_name] = "OPEN"
                state["workflow_status"] = "FAILED"
                state["should_continue"] = False
                logger.error(
                    f"Opening circuit breaker for {node_name} after {self.failure_threshold} failures"
                )
            elif self._is_retryable_error(error):
                state["should_continue"] = True
                state["current_step"] = node_name
                logger.info(f"Error is retryable for {node_name}, will retry")
            else:
                state["workflow_status"] = "FAILED"
                state["should_continue"] = False
                logger.error(f"Non-retryable error in {node_name}: {type(error).__name__}")
        state["last_error_time"] = datetime.now()
        return state

    def _check_circuit_breaker(self, node_name: str) -> str:
        """
        Check the state of the circuit breaker for a node.

        Returns:
            Circuit state: "CLOSED", "OPEN", or "HALF_OPEN"
        """
        if node_name not in self.circuit_breakers:
            self.circuit_breakers[node_name] = {
                "state": "CLOSED",
                "failures": 0,
                "last_failure_time": None,
                "success_count": 0,
            }
            return "CLOSED"
        breaker = self.circuit_breakers[node_name]
        if breaker["state"] == "OPEN":
            if breaker["last_failure_time"]:
                time_since_failure = datetime.now() - breaker["last_failure_time"]
                if time_since_failure > timedelta(seconds=self.recovery_timeout):
                    breaker["state"] = "HALF_OPEN"
                    breaker["success_count"] = 0
                    logger.info(f"Circuit breaker for {node_name} moved to HALF_OPEN")
                    return "HALF_OPEN"
            return "OPEN"
        elif breaker["state"] == "HALF_OPEN":
            if breaker["success_count"] >= self.half_open_requests:
                breaker["state"] = "CLOSED"
                breaker["failures"] = 0
                breaker["success_count"] = 0
                logger.info(f"Circuit breaker for {node_name} CLOSED after successful recovery")
                return "CLOSED"
            return "HALF_OPEN"
        return "CLOSED"

    def _record_failure(self, node_name: str):
        """Record a failure for a node."""
        if node_name not in self.circuit_breakers:
            self.circuit_breakers[node_name] = {
                "state": "CLOSED",
                "failures": 0,
                "last_failure_time": None,
                "success_count": 0,
            }
        breaker = self.circuit_breakers[node_name]
        breaker["failures"] += 1
        breaker["last_failure_time"] = datetime.now()

    def _record_success(self, node_name: str):
        """Record a successful execution for a node."""
        if node_name in self.circuit_breakers:
            breaker = self.circuit_breakers[node_name]
            if breaker["state"] == "HALF_OPEN":
                breaker["success_count"] += 1
                if breaker["success_count"] >= self.half_open_requests:
                    breaker["state"] = "CLOSED"
                    breaker["failures"] = 0
                    breaker["success_count"] = 0
                    logger.info(f"Circuit breaker for {node_name} CLOSED")
            elif breaker["state"] == "CLOSED":
                breaker["failures"] = 0

    def _should_open_circuit(self, node_name: str) -> bool:
        """Check if circuit should be opened."""
        if node_name in self.circuit_breakers:
            breaker = self.circuit_breakers[node_name]
            return breaker["failures"] >= self.failure_threshold
        return False

    def _open_circuit(self, node_name: str):
        """Open the circuit breaker for a node."""
        if node_name not in self.circuit_breakers:
            self.circuit_breakers[node_name] = {
                "state": "OPEN",
                "failures": self.failure_threshold,
                "last_failure_time": datetime.now(),
                "success_count": 0,
            }
        else:
            breaker = self.circuit_breakers[node_name]
            breaker["state"] = "OPEN"
            breaker["last_failure_time"] = datetime.now()

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.

        Args:
            error: The exception to check

        Returns:
            True if the error is retryable
        """
        for error_type in self.retryable_errors:
            if isinstance(error, error_type):
                return True
        error_message = str(error).lower()
        retryable_patterns = [
            "connection",
            "timeout",
            "rate limit",
            "temporary",
            "unavailable",
            "too many requests",
        ]
        return any(pattern in error_message for pattern in retryable_patterns)

    def wrap_node(self, node_func: Callable) -> Callable:
        """
        Wrap a node function with error handling.

        Args:
            node_func: The node function to wrap

        Returns:
            Wrapped function with error handling
        """

        @wraps(node_func)
        async def wrapped(state: UnifiedComplianceState) -> UnifiedComplianceState:
            node_name = node_func.__name__
            breaker_state = self._check_circuit_breaker(node_name)
            if breaker_state == "OPEN":
                logger.warning(f"Circuit breaker OPEN for {node_name}, skipping execution")
                error = CircuitBreakerError(f"Circuit breaker open for {node_name}")
                return await self.handle_node_error(node_name, error, state)
            try:
                state["current_step"] = node_name
                logger.info(f"Executing node: {node_name}")
                result = await node_func(state)
                self._record_success(node_name)
                if "steps_completed" not in result:
                    result["steps_completed"] = []
                result["steps_completed"].append(node_name)
                if "steps_remaining" in result and node_name in result["steps_remaining"]:
                    result["steps_remaining"].remove(node_name)
                result["history"].append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "action": f"{node_name}_completed",
                        "status": "success",
                    }
                )
                return result
            except Exception as e:
                logger.error(f"Error in {node_name}: {e}", exc_info=True)
                return await self.handle_node_error(node_name, e, state)

        wrapped.__name__ = node_func.__name__
        return wrapped

    def get_circuit_status(self) -> Dict[str, Any]:
        """
        Get the status of all circuit breakers.

        Returns:
            Dictionary with circuit breaker states
        """
        return {
            node: {
                "state": breaker["state"],
                "failures": breaker["failures"],
                "last_failure": breaker["last_failure_time"].isoformat()
                if breaker["last_failure_time"]
                else None,
            }
            for node, breaker in self.circuit_breakers.items()
        }

    def reset_circuit(self, node_name: str) -> None:
        """
        Manually reset a circuit breaker.

        Args:
            node_name: Node to reset
        """
        if node_name in self.circuit_breakers:
            self.circuit_breakers[node_name] = {
                "state": "CLOSED",
                "failures": 0,
                "last_failure_time": None,
                "success_count": 0,
            }
            logger.info(f"Circuit breaker for {node_name} manually reset")
