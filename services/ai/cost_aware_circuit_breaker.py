"""
Cost-Aware Circuit Breaker Integration

Extends the existing circuit breaker with cost tracking and budget-aware operations.
Integrates cost management with reliability patterns.
"""

import asyncio
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional
from threading import Lock
import logging

from services.ai.circuit_breaker import AICircuitBreaker, CircuitBreakerConfig
from services.ai.cost_management import (
    AICostManager,
    CostTrackingService,
    BudgetAlertService,
)

logger = logging.getLogger(__name__)
from services.ai.exceptions import AIServiceException, CircuitBreakerException
from config.logging_config import get_logger

logger = get_logger(__name__)


class CostAwareCircuitBreakerConfig(CircuitBreakerConfig):
    """Extended circuit breaker configuration with cost awareness."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
        time_window: int = 60,
        # Cost-aware additions
        cost_threshold_per_minute: Optional[Decimal] = None,
        budget_enforcement: bool = True,
        cost_spike_threshold: float = 3.0,  # 3x normal cost triggers circuit
        track_cost_efficiency: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(
            failure_threshold,
            recovery_timeout,
            success_threshold,
            time_window,
        )
        self.cost_threshold_per_minute = cost_threshold_per_minute
        self.budget_enforcement = budget_enforcement
        self.cost_spike_threshold = cost_spike_threshold
        self.track_cost_efficiency = track_cost_efficiency


class CostAwareCircuitBreaker(AICircuitBreaker):
    """
    Enhanced circuit breaker with cost tracking and budget awareness.

    Integrates cost management into circuit breaker decisions, providing
    budget enforcement and cost-based circuit tripping.
    """

    def __init__(self, config: Optional[CostAwareCircuitBreakerConfig] = None) -> None:
        # Initialize base circuit breaker
        base_config = CircuitBreakerConfig(
            failure_threshold=config.failure_threshold if config else 5,
            recovery_timeout=config.recovery_timeout if config else 60,
            success_threshold=config.success_threshold if config else 3,
            time_window=config.time_window if config else 60,
        )
        super().__init__(base_config)

        # Cost-aware configuration
        self.cost_config = config or CostAwareCircuitBreakerConfig()

        # Cost management services
        self.cost_manager = AICostManager()
        self.cost_tracker = CostTrackingService()
        self.budget_service = BudgetAlertService()

        # Cost tracking
        self._cost_history: Dict[str, List[Dict[str, Any]]] = {}
        self._cost_lock = Lock()

    async def call_with_cost_tracking(
        self,
        model_name: str,
        service_name: str,
        operation: Callable,
        input_tokens: int,
        output_tokens: int,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute operation with both circuit breaker protection and cost tracking.

        Args:
            model_name: Name of the AI model being used
            service_name: Name of the service (for cost categorization)
            operation: Function to execute
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            user_id: User identifier
            session_id: Session identifier
            request_id: Request identifier
            *args, **kwargs: Arguments for the operation

        Returns:
            Result of the operation

        Raises:
            CircuitBreakerException: If circuit is open
            AIServiceException: If budget is exceeded or operation fails
        """

        # Check if model is available (circuit not open)
        if not self.is_model_available(model_name):
            raise CircuitBreakerException(
                f"Circuit breaker is OPEN for model {model_name}",
                context={
                    "model_name": model_name,
                    "state": self.get_model_state(model_name).value,
                },
            )

        # Check budget constraints if enabled
        if self.cost_config.budget_enforcement:
            await self._check_budget_constraints(
                model_name,
                input_tokens,
                output_tokens,
            )

        # Execute operation with timing
        start_time = time.time()

        try:
            result = (
                await operation(*args, **kwargs)
                if asyncio.iscoroutinefunction(operation)
                else operation(*args, **kwargs),
            )
            response_time = time.time() - start_time

            # Track successful usage and cost
            await self._track_successful_usage(
                model_name=model_name,
                service_name=service_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_time_ms=response_time * 1000,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
            )

            # Record success in circuit breaker
            self.record_success(model_name, response_time)

            return result

        except Exception as error:
            response_time = time.time() - start_time

            # Track failed usage and cost (still incurs cost even on failure)
            await self._track_failed_usage(
                model_name=model_name,
                service_name=service_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error=error,
                response_time_ms=response_time * 1000,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
            )

            # Record failure in circuit breaker
            self.record_failure(
                model_name,
                error,
                {
                    "operation": (
                        operation.__name__ if hasattr(operation, "__name__") else str(operation),
                    ),
                    "service_name": service_name,
                    "cost_incurred": True,
                },
            )

            raise

    async def _check_budget_constraints(
        self, model_name: str, input_tokens: int, output_tokens: int
    ) -> None:
        """Check if request would exceed budget constraints."""

        # Estimate cost for this request
        model_config = self.cost_tracker.model_configs.get(model_name)
        if model_config:
            estimated_cost = model_config.calculate_total_cost(
                input_tokens,
                output_tokens,
            )

            # Check daily budget
            budget_config = await self.budget_service.get_current_budget()
            daily_limit = budget_config.get("daily_limit")

            if daily_limit:
                # Get current daily usage
                from datetime import date

                today_costs = await self.cost_tracker.calculate_daily_costs(
                    date.today(),
                )
                current_usage = today_costs["total_cost"]

                if current_usage + estimated_cost > daily_limit:
                    raise AIServiceException(
                        message=(
                            f"Request would exceed daily budget: ${current_usage + estimated_cost:.2f} > "
                            f"${daily_limit:.2f}"
                        ),
                        service_name="Cost-Aware Circuit Breaker",
                        error_code="BUDGET_EXCEEDED",
                        context={
                            "current_usage": str(current_usage),
                            "estimated_cost": str(estimated_cost),
                            "daily_limit": str(daily_limit),
                        },
                    )

    async def _track_successful_usage(
        self,
        model_name: str,
        service_name: str,
        input_tokens: int,
        output_tokens: int,
        response_time_ms: float,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Track successful AI usage with cost calculation."""

        try:
            await self.cost_manager.track_ai_request(
                service_name=service_name,
                model_name=model_name,
                input_prompt="",  # Not stored in circuit breaker context
                response_content="",  # Not stored in circuit breaker context
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
                response_time_ms=response_time_ms,
                cache_hit=False,
                error_occurred=False,
                metadata={"circuit_breaker": "cost_aware"},
            )

            # Track cost history for spike detection
            await self._update_cost_history(
                model_name,
                service_name,
                input_tokens + output_tokens,
            )

        except Exception as e:
            logger.error(f"Failed to track successful usage: {str(e)}")

    async def _track_failed_usage(
        self,
        model_name: str,
        service_name: str,
        input_tokens: int,
        output_tokens: int,
        error: Exception,
        response_time_ms: float,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Track failed AI usage (cost still incurred)."""

        try:
            await self.cost_manager.track_ai_request(
                service_name=service_name,
                model_name=model_name,
                input_prompt="",
                response_content="",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
                response_time_ms=response_time_ms,
                cache_hit=False,
                error_occurred=True,
                metadata={
                    "circuit_breaker": "cost_aware",
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                },
            )

        except Exception as e:
            logger.error(f"Failed to track failed usage: {str(e)}")

    async def _update_cost_history(
        self, model_name: str, service_name: str, total_tokens: int
    ) -> None:
        """Update cost history for spike detection."""

        with self._cost_lock:
            key = f"{model_name}:{service_name}"

            if key not in self._cost_history:
                self._cost_history[key] = []

            # Add current usage
            self._cost_history[key].append(
                {
                    "timestamp": datetime.now(),
                    "tokens": total_tokens,
                    "model_name": model_name,
                    "service_name": service_name,
                },
            )

            # Keep only recent history (last hour)
            cutoff_time = datetime.now() - timedelta(hours=1)
            self._cost_history[key] = [
                entry for entry in self._cost_history[key] if entry["timestamp"] > cutoff_time
            ]

    async def check_cost_spike(self, model_name: str, service_name: str) -> bool:
        """Check if recent usage represents a cost spike."""

        if not self.cost_config.track_cost_efficiency:
            return False

        key = f"{model_name}:{service_name}"

        with self._cost_lock:
            if key not in self._cost_history or len(self._cost_history[key]) < 3:
                return False

            recent_history = self._cost_history[key]

            # Calculate average tokens in recent history
            recent_tokens = [entry["tokens"] for entry in recent_history[-10:]]
            avg_tokens = sum(recent_tokens) / len(recent_tokens)

            # Check if latest usage is significantly higher
            latest_tokens = recent_history[-1]["tokens"]

            return latest_tokens > avg_tokens * self.cost_config.cost_spike_threshold

    def get_cost_aware_status(self) -> Dict[str, Any]:
        """Get circuit breaker status with cost information."""

        base_status = self.get_status()

        # Add cost-specific information
        cost_status = {
            "cost_config": {
                "budget_enforcement": self.cost_config.budget_enforcement,
                "cost_spike_threshold": self.cost_config.cost_spike_threshold,
                "track_cost_efficiency": self.cost_config.track_cost_efficiency,
                "cost_threshold_per_minute": (
                    str(self.cost_config.cost_threshold_per_minute)
                    if self.cost_config.cost_threshold_per_minute
                    else None,
                ),
            },
            "cost_history_keys": list(self._cost_history.keys()),
            "cost_tracking_active": True,
        }

        return {**base_status, "cost_awareness": cost_status}

    async def get_cost_efficiency_metrics(self) -> Dict[str, Any]:
        """Get cost efficiency metrics for circuit breaker decisions."""

        try:
            # Get recent cost trends
            trends = await self.cost_tracker.get_cost_trends(7)

            # Calculate efficiency metrics
            if trends:
                recent_costs = [float(trend["cost"]) for trend in trends[-3:]]
                avg_recent_cost = (sum(recent_costs) / len(recent_costs) if recent_costs else 0,)

                total_requests = sum(trend["requests"] for trend in trends[-3:])
                cost_per_request = (avg_recent_cost / total_requests if total_requests > 0 else 0,)

                return {
                    "average_daily_cost": avg_recent_cost,
                    "cost_per_request": cost_per_request,
                    "cost_trend": (
                        "increasing"
                        if len(recent_costs) >= 2 and recent_costs[-1] > recent_costs[0]
                        else "stable",
                    ),
                    "efficiency_score": max(
                        0, 1 - (cost_per_request / 0.1)
                    ),  # Normalize against $0.10 baseline,
                }

            return {
                "average_daily_cost": 0,
                "cost_per_request": 0,
                "cost_trend": "stable",
                "efficiency_score": 1.0,
            }

        except Exception as e:
            logger.error(f"Failed to get cost efficiency metrics: {str(e)}")
            return {
                "average_daily_cost": 0,
                "cost_per_request": 0,
                "cost_trend": "unknown",
                "efficiency_score": 0.5,
                "error": str(e),
            }

    async def optimize_model_selection(
        self,
        available_models: List[str],
        task_complexity: str = "medium",
        max_cost_per_request: Optional[Decimal] = None,
    ) -> str:
        """
        Select optimal model considering both availability and cost efficiency.

        Args:
            available_models: List of available models
            task_complexity: Complexity of the task
            max_cost_per_request: Maximum acceptable cost per request

        Returns:
            Optimal model name
        """

        # Filter models by circuit breaker availability
        available_models = [model for model in available_models if self.is_model_available(model)]

        if not available_models:
            raise AIServiceException(
                message="No AI models available - all circuits are open",
                service_name="Cost-Aware Circuit Breaker",
                error_code="NO_MODELS_AVAILABLE",
            )

        # If cost constraint is specified, filter by cost
        if max_cost_per_request:
            cost_efficient_models = []
            for model_name in available_models:
                model_config = self.cost_tracker.model_configs.get(model_name)
                if model_config:
                    # Estimate cost for average request
                    estimated_cost = model_config.calculate_total_cost(1000, 500)
                    if estimated_cost <= max_cost_per_request:
                        cost_efficient_models.append(model_name)

            if cost_efficient_models:
                available_models = cost_efficient_models

        # Use intelligent model router for final selection
        from services.ai.cost_management import IntelligentModelRouter

        router = IntelligentModelRouter()

        # Mock task description for routing
        task_description = f"Task with {task_complexity} complexity"

        routing_result = await router.select_optimal_model(
            task_description=task_description,
            task_type="general",
            max_cost_per_request=max_cost_per_request,
        )

        recommended_model = routing_result["model"]

        # Return recommended model if available, otherwise first available
        return (
            recommended_model if recommended_model in available_models else available_models[0],
        )


# Global cost-aware circuit breaker instance
_cost_aware_circuit_breaker: Optional[CostAwareCircuitBreaker] = None


def get_cost_aware_circuit_breaker() -> CostAwareCircuitBreaker:
    """Get global cost-aware circuit breaker instance."""
    global _cost_aware_circuit_breaker

    if _cost_aware_circuit_breaker is None:
        _cost_aware_circuit_breaker = CostAwareCircuitBreaker()

    return _cost_aware_circuit_breaker


def reset_cost_aware_circuit_breaker() -> None:
    """Reset global cost-aware circuit breaker instance."""
    global _cost_aware_circuit_breaker
    _cost_aware_circuit_breaker = None


# Convenience function for easy integration
async def execute_with_cost_and_circuit_protection(
    model_name: str,
    service_name: str,
    operation: Callable,
    input_tokens: int,
    output_tokens: int,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    *args,
    **kwargs,
) -> Any:
    """
    Convenience function to execute AI operations with cost tracking and circuit breaker protection.

    Args:
        model_name: Name of the AI model
        service_name: Name of the service
        operation: Function to execute
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        user_id: User identifier
        session_id: Session identifier
        request_id: Request identifier
        *args, **kwargs: Arguments for the operation

    Returns:
        Result of the operation
    """

    circuit_breaker = get_cost_aware_circuit_breaker()

    return await circuit_breaker.call_with_cost_tracking(
        model_name=model_name,
        service_name=service_name,
        operation=operation,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        *args,
        **kwargs,
    )
