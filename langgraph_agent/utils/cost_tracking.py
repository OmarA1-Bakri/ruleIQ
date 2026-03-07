"""

Cost tracking decorator and utilities for LangGraph nodes.

This module provides decorators and utilities to track AI costs
across all LangGraph nodes, integrating with the existing cost
management infrastructure.
"""

import asyncio
import functools
import time
from typing import Any, Callable, Dict, Optional, TypeVar

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
from datetime import datetime, timezone
import logging
from services.ai.cost_management import AICostManager

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])
_cost_manager: Optional[AICostManager] = None


def get_cost_manager() -> AICostManager:
    """Get or create the global cost manager instance."""
    global _cost_manager
    if _cost_manager is None:
        _cost_manager = AICostManager()
    return _cost_manager


def track_node_cost(
    node_name: Optional[str] = None,
    service_name: str = "langgraph",
    model_name: Optional[str] = None,
    track_tokens: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to track costs for LangGraph nodes.

    Args:
        node_name: Name of the node (defaults to function name)
        service_name: Service identifier for cost tracking
        model_name: AI model being used (if applicable)
        track_tokens: Whether to track token usage

    Returns:
        Decorated function that tracks costs

    Example:
        @track_node_cost(node_name="compliance_check", model_name="gpt-4")
        async def compliance_check_node(state: AgentState) -> AgentState:
            # Node implementation
            pass
    """

    def decorator(func: F) -> F:
        is_async = asyncio.iscoroutinefunction(func)
        actual_node_name = node_name or func.__name__
        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                start_time = time.time()
                cost_manager = get_cost_manager()
                state = None
                if args and hasattr(args[0], "__dict__"):
                    state = args[0]
                input_tokens = 0
                output_tokens = 0
                total_cost = 0.0
                try:
                    user_id = None
                    if state and hasattr(state, "user_id"):
                        user_id = state.user_id
                    elif state and hasattr(state, "get"):
                        user_id = state.get("user_id")
                    result = await func(*args, **kwargs)
                    if isinstance(result, dict):
                        if "usage" in result:
                            usage = result["usage"]
                            if isinstance(usage, dict):
                                input_tokens = usage.get("input_tokens", 0)
                                output_tokens = usage.get("output_tokens", 0)
                        if "input_tokens" in result:
                            input_tokens = result["input_tokens"]
                        if "output_tokens" in result:
                            output_tokens = result["output_tokens"]
                        if "total_cost" in result:
                            total_cost = result["total_cost"]
                    execution_time = time.time() - start_time
                    if track_tokens and (input_tokens > 0 or output_tokens > 0):
                        await cost_manager.track_ai_request(
                            model=model_name or "unknown",
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            user_id=user_id or "system",
                            service_name=f"{service_name}.{actual_node_name}",
                            metadata={
                                "node_name": actual_node_name,
                                "execution_time": execution_time,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                        )
                        logger.info(
                            f"Cost tracked for {actual_node_name}: input_tokens={input_tokens}, output_tokens={output_tokens}, cost=${total_cost:.4f}, execution_time={execution_time:.2f}s"
                        )
                    if isinstance(result, dict) and (not result.get("cost_tracking")):
                        result["cost_tracking"] = {
                            "node_name": actual_node_name,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_cost": total_cost,
                            "execution_time": execution_time,
                        }
                    return result
                except Exception as e:
                    logger.error(f"Error in cost tracking for {actual_node_name}: {e}")
                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                start_time = time.time()
                cost_manager = get_cost_manager()
                state = None
                if args and hasattr(args[0], "__dict__"):
                    state = args[0]
                input_tokens = 0
                output_tokens = 0
                total_cost = 0.0
                try:
                    user_id = None
                    if state and hasattr(state, "user_id"):
                        user_id = state.user_id
                    elif state and hasattr(state, "get"):
                        user_id = state.get("user_id")
                    result = func(*args, **kwargs)
                    if isinstance(result, dict):
                        if "usage" in result:
                            usage = result["usage"]
                            if isinstance(usage, dict):
                                input_tokens = usage.get("input_tokens", 0)
                                output_tokens = usage.get("output_tokens", 0)
                        if "input_tokens" in result:
                            input_tokens = result["input_tokens"]
                        if "output_tokens" in result:
                            output_tokens = result["output_tokens"]
                        if "total_cost" in result:
                            total_cost = result["total_cost"]
                    execution_time = time.time() - start_time
                    if track_tokens and (input_tokens > 0 or output_tokens > 0):
                        asyncio.create_task(
                            cost_manager.track_ai_request(
                                model=model_name or "unknown",
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                user_id=user_id or "system",
                                service_name=f"{service_name}.{actual_node_name}",
                                metadata={
                                    "node_name": actual_node_name,
                                    "execution_time": execution_time,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                },
                            )
                        )
                        logger.info(
                            f"Cost tracked for {actual_node_name}: input_tokens={input_tokens}, output_tokens={output_tokens}, cost=${total_cost:.4f}, execution_time={execution_time:.2f}s"
                        )
                    if isinstance(result, dict) and (not result.get("cost_tracking")):
                        result["cost_tracking"] = {
                            "node_name": actual_node_name,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_cost": total_cost,
                            "execution_time": execution_time,
                        }
                    return result
                except Exception as e:
                    logger.error(f"Error in cost tracking for {actual_node_name}: {e}")
                    raise

            return sync_wrapper

    return decorator


def aggregate_node_costs(state: Dict[str, Any]) -> Dict[str, float]:
    """
    Aggregate cost tracking information from multiple nodes in the state.

    Args:
        state: The LangGraph state dictionary

    Returns:
        Dictionary with aggregated cost metrics
    """
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    total_execution_time = 0.0
    node_costs = {}
    if "cost_tracking" in state:
        tracking = state["cost_tracking"]
        if isinstance(tracking, dict):
            total_input_tokens += tracking.get("input_tokens", 0)
            total_output_tokens += tracking.get("output_tokens", 0)
            total_cost += tracking.get("total_cost", 0.0)
            total_execution_time += tracking.get("execution_time", 0.0)
            node_name = tracking.get("node_name", "unknown")
            node_costs[node_name] = tracking.get("total_cost", 0.0)
    if "accumulated_costs" in state:
        for node_name, cost in state["accumulated_costs"].items():
            node_costs[node_name] = cost
            total_cost += cost
    return {
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cost": total_cost,
        "total_execution_time": total_execution_time,
        "node_costs": node_costs,
    }


class CostTrackingContext:
    """
    Context manager for tracking costs across multiple operations.

    Example:
        with CostTrackingContext("workflow_name") as tracker:
            # Perform operations
            result = await some_ai_operation()
            tracker.add_tokens(100, 50)  # input, output

        total_cost = tracker.total_cost
    """

    def __init__(self, context_name: str, user_id: Optional[str] = None) -> None:
        self.context_name = context_name
        self.user_id = user_id or "system"
        self.cost_manager = get_cost_manager()
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0
        self.start_time = None
        self.operations = []

    def __enter__(self) -> Self:
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        execution_time = time.time() - self.start_time
        logger.info(
            f"Cost tracking context '{self.context_name}' completed: input_tokens={self.input_tokens}, output_tokens={self.output_tokens}, total_cost=${self.total_cost:.4f}, execution_time={execution_time:.2f}s"
        )

    def add_tokens(
        self, input_tokens: int, output_tokens: int, cost: Optional[float] = None
    ) -> None:
        """Add token counts to the context."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        if cost:
            self.total_cost += cost

    def add_operation(self, operation_name: str, metrics: Dict[str, Any]) -> None:
        """Track an individual operation within the context."""
        self.operations.append(
            {
                "name": operation_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": metrics,
            }
        )
