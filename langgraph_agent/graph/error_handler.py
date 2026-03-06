"""
import logging


logger = logging.getLogger(__name__)
Centralized error handling for LangGraph implementation.

Phase 2 Implementation: Centralized error handling with retry strategies.
This module provides a comprehensive error handling node that:
- Classifies errors by type
- Implements appropriate retry strategies
- Manages retry limits
- Activates fallback mechanisms
"""

import asyncio
import random
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from langsmith import traceable

from .enhanced_state import EnhancedComplianceState, WorkflowStatus
from config.logging_config import get_logger

logger = get_logger(__name__)


class ErrorHandlerNode:
    """Centralized error handling for all graph nodes."""

    def __init__(self, max_retries: int = 3) -> None:
        """
        Initialize error handler with retry strategies.

        Args:
            max_retries: Maximum number of retry attempts before fallback
        """
        self.max_retries = max_retries

        # Map error types to their handling strategies
        self.retry_strategies = {
            "rate_limit": self._handle_rate_limit,
            "database": self._handle_database_error,
            "api": self._handle_api_error,
            "validation": self._handle_validation_error,
            "timeout": self._handle_timeout_error,
            "network": self._handle_network_error,
            "unknown": self._generic_retry,
        }

        # Retry delays for different error types (in seconds)
        self.base_delays = {
            "rate_limit": 2.0,  # Start with 2 seconds for rate limits
            "database": 1.0,  # 1 second for database errors
            "api": 1.5,  # 1.5 seconds for API errors
            "timeout": 0.5,  # 0.5 seconds for timeout errors
            "network": 1.0,  # 1 second for network errors
            "unknown": 1.0,  # 1 second for unknown errors
        }

    @traceable(name="error_handler_process")
    async def process(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """
        Main error processing logic.

        Args:
            state: Current state with error information

        Returns:
            Updated state with retry or fallback decision
        """
        try:
            # Log the error handling invocation
            error_count = state.get("error_count", 0)
            retry_count = state.get("retry_count", 0)
            logger.info(f"Error handler invoked - errors: {error_count}, retries: {retry_count}")

            # Check if we have errors to handle
            if not state.get("errors") or error_count == 0:
                logger.warning("Error handler called but no errors found in state")
                return state

            # Classify the error type
            error_type = self._classify_error(state)
            logger.info(f"Error classified as: {error_type}")

            # Check retry limit
            if retry_count >= self.max_retries:
                logger.warning(f"Max retries ({self.max_retries}) exceeded, activating fallback")
                return await self._activate_fallback(state)

            # Apply appropriate retry strategy
            handler = self.retry_strategies.get(error_type, self._generic_retry)
            state = await handler(state)

            # Update retry count and workflow status
            state["retry_count"] = retry_count + 1

            # Add retry message
            state["messages"].append(
                {
                    "role": "system",
                    "content": f"Retry attempt {state['retry_count']}/{self.max_retries} for {error_type} error",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

            return state

        except Exception as e:
            logger.error(f"Error handler itself failed: {e}")
            # If error handler fails, activate fallback immediately
            return await self._activate_fallback(state)

    def _classify_error(self, state: EnhancedComplianceState) -> str:
        """
        Classify error type from state.

        Args:
            state: Current state with error information

        Returns:
            Error type classification
        """
        if not state.get("errors"):
            return "unknown"

        # Get the most recent error
        last_error = state["errors"][-1]

        # Convert error to string for analysis
        if isinstance(last_error, dict):
            error_msg = str(last_error.get("error", "")).lower()
            error_type = last_error.get("type", "").lower()
        else:
            error_msg = str(last_error).lower()
            error_type = ""

        # Classification logic based on error content
        # Check more specific patterns first
        if "rate limit" in error_msg or "429" in error_msg or "too many requests" in error_msg:
            return "rate_limit"
        elif "network" in error_msg or "dns" in error_msg or "connection refused" in error_msg:
            return "network"
        elif (
            "database" in error_msg
            or "postgres" in error_msg
            or "neo4j" in error_msg
            or "connection pool" in error_msg
        ):
            return "database"
        elif "timeout" in error_msg or "timed out" in error_msg or "deadline" in error_msg:
            return "timeout"
        elif (
            "api" in error_msg
            or "endpoint" in error_msg
            or "404" in error_msg
            or "500" in error_msg
        ):
            return "api"
        elif (
            "validation" in error_msg
            or "invalid" in error_msg
            or "schema" in error_msg
            or "type error" in error_msg
        ):
            return "validation"
        elif error_type:  # Use explicit type if provided
            return error_type

        return "unknown"

    async def _handle_rate_limit(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """
        Handle rate limit errors with exponential backoff and jitter.

        Args:
            state: Current state

        Returns:
            Updated state after applying rate limit strategy
        """
        retry_count = state.get("retry_count", 0)
        base_delay = self.base_delays["rate_limit"]

        # Exponential backoff: 2^retry_count * base_delay
        delay = base_delay * (2**retry_count)

        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, delay * 0.1)  # Up to 10% jitter
        total_delay = delay + jitter

        # Cap maximum delay at 60 seconds
        total_delay = min(total_delay, 60.0)

        logger.info(f"Rate limit retry: waiting {total_delay:.2f} seconds")
        await asyncio.sleep(total_delay)

        # Clear errors for retry
        state["should_continue"] = True

        # Set next node to retry from last successful node
        if state.get("last_successful_node"):
            state["next_node"] = state["last_successful_node"]
        else:
            state["next_node"] = state.get("current_node") or "router"

        return state

    async def _handle_database_error(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Handle database errors with linear backoff and connection pool refresh.

        Args:
            state: Current state

        Returns:
            Updated state after applying database error strategy
        """
        retry_count = state.get("retry_count", 0)
        base_delay = self.base_delays["database"]

        # Linear backoff for database errors
        delay = base_delay * (retry_count + 1)

        # Cap at 30 seconds
        delay = min(delay, 30.0)

        logger.info(f"Database error retry: waiting {delay:.2f} seconds")
        await asyncio.sleep(delay)

        # Note: In production, you would refresh connection pool here
        # For now, we just log the intent
        logger.info("Would refresh database connection pool in production")

        # Clear errors and continue
        state["should_continue"] = True
        state["next_node"] = state.get("current_node", "router")

        return state

    async def _handle_api_error(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """
        Handle API errors with retry and potential fallback endpoints.

        Args:
            state: Current state

        Returns:
            Updated state after applying API error strategy
        """
        retry_count = state.get("retry_count", 0)
        base_delay = self.base_delays["api"]

        # Exponential backoff for API errors
        delay = base_delay * (1.5**retry_count)

        # Cap at 20 seconds
        delay = min(delay, 20.0)

        logger.info(f"API error retry: waiting {delay:.2f} seconds")
        await asyncio.sleep(delay)

        # Mark for retry with potential fallback endpoint
        state["should_continue"] = True
        state["next_node"] = state.get("current_node", "router")

        # Add metadata about fallback if needed
        if retry_count >= 2:
            state["metadata"]["use_fallback_api"] = True
            logger.info("Switching to fallback API endpoint")

        return state

    async def _handle_validation_error(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Handle validation errors - typically no retry, immediate fallback.

        Args:
            state: Current state

        Returns:
            Updated state with fallback activation
        """
        logger.warning("Validation error detected - no retry, activating fallback")

        # Validation errors typically can't be fixed by retry
        # Go straight to fallback
        return await self._activate_fallback(state)

    async def _handle_timeout_error(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Handle timeout errors by increasing timeout and retrying.

        Args:
            state: Current state

        Returns:
            Updated state with increased timeout
        """
        retry_count = state.get("retry_count", 0)
        base_delay = self.base_delays["timeout"]

        # Short delay before retry
        delay = base_delay * (retry_count + 1)

        logger.info(f"Timeout error retry: waiting {delay:.2f} seconds")
        await asyncio.sleep(delay)

        # Increase timeout for next attempt
        current_timeout = state.get("metadata", {}).get("timeout", 30)
        new_timeout = min(current_timeout * 1.5, 120)  # Cap at 2 minutes

        state["metadata"]["timeout"] = new_timeout
        logger.info(f"Increased timeout from {current_timeout}s to {new_timeout}s")

        # Continue with retry
        state["should_continue"] = True
        state["next_node"] = state.get("current_node", "router")

        return state

    async def _handle_network_error(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Handle network errors with exponential backoff.

        Args:
            state: Current state

        Returns:
            Updated state after network error handling
        """
        retry_count = state.get("retry_count", 0)
        base_delay = self.base_delays["network"]

        # Exponential backoff for network errors
        delay = base_delay * (2**retry_count)

        # Cap at 30 seconds
        delay = min(delay, 30.0)

        logger.info(f"Network error retry: waiting {delay:.2f} seconds")
        await asyncio.sleep(delay)

        # Continue with retry
        state["should_continue"] = True
        state["next_node"] = state.get("current_node", "router")

        return state

    async def _generic_retry(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """
        Generic retry strategy for unknown error types.

        Args:
            state: Current state

        Returns:
            Updated state with generic retry strategy
        """
        retry_count = state.get("retry_count", 0)
        base_delay = self.base_delays["unknown"]

        # Simple exponential backoff
        delay = base_delay * (1.5**retry_count)

        # Cap at 15 seconds
        delay = min(delay, 15.0)

        logger.info(f"Generic retry: waiting {delay:.2f} seconds")
        await asyncio.sleep(delay)

        # Continue with retry
        state["should_continue"] = True
        state["next_node"] = state.get("current_node", "router")

        return state

    async def handle_error(self, state: Dict[str, Any], error: Exception) -> Dict[str, Any]:
        """
        Handle an error and update state accordingly.

        Args:
            state: Current state dictionary
            error: The exception that occurred

        Returns:
            Updated state with error information
        """
        error_info = {
            "error": str(error),
            "error_type": type(error).__name__,
            "timestamp": datetime.now().isoformat(),
        }

        # Add error to state's error list
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(error_info)

        # Update error count
        state["error_count"] = state.get("error_count", 0) + 1

        # Determine if we should retry
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", self.max_retries)

        if retry_count < max_retries:
            state["retry_count"] = retry_count + 1
            state["task_status"] = "pending"  # Reset to pending for retry
            logger.info(f"Error handled, will retry. Attempt {retry_count + 1}/{max_retries}")
        else:
            state["task_status"] = "failed"
            logger.error(f"Max retries ({max_retries}) reached, marking as failed")

        return state

    async def _activate_fallback(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """
        Activate fallback mechanism when retries are exhausted.

        Args:
            state: Current state

        Returns:
            Updated state with fallback activation
        """
        logger.warning("Activating fallback mechanism")

        # Set workflow status to failed
        state["workflow_status"] = WorkflowStatus.FAILED
        state["should_continue"] = False
        state["termination_reason"] = "Max retries exceeded - fallback activated"

        # Mark that we need human review
        state["requires_human_review"] = True

        # Add fallback message
        state["messages"].append(
            {
                "role": "assistant",
                "content": "I encountered persistent errors and couldn't complete the analysis. "
                "The issue has been logged for manual review. Please try again later or "
                "contact support if the problem persists.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Log error details for debugging
        error_summary = {
            "error_count": state.get("error_count", 0),
            "retry_count": state.get("retry_count", 0),
            "last_errors": state.get("errors", [])[-3:] if state.get("errors") else [],
            "last_node": state.get("current_node"),
            "session_id": state.get("session_id"),
        }

        logger.error(f"Fallback activated - Error summary: {error_summary}")

        # Route to response generator for graceful termination
        state["next_node"] = "response_generator"

        return state


def should_route_to_error_handler(state: EnhancedComplianceState) -> Optional[str]:
    """
    Conditional routing function to determine if error handler should be invoked.

    Args:
        state: Current state

    Returns:
        "error_handler" if errors exist, None otherwise
    """
    if state.get("errors") and state.get("error_count", 0) > 0:
        # Check if we haven't already exceeded max retries
        if state.get("retry_count", 0) < 3:  # Default max retries
            return "error_handler"
    return None


def get_recovery_node(state: EnhancedComplianceState) -> str:
    """
    Determine which node to route to after error handling.

    Args:
        state: Current state

    Returns:
        Name of the node to route to for recovery
    """
    # If we have a specific next node set, use it
    if state.get("next_node"):
        return state["next_node"]

    # If we have a last successful node, retry from there
    if state.get("last_successful_node"):
        return state["last_successful_node"]

    # Default to router if nothing else is specified
    return "router"
