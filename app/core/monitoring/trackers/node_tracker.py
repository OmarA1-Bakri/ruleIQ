"""
Node execution tracking for LangGraph workflows.
"""

import logging
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from typing import Any, Deque, Dict, Generator, List, Optional

from .types import NodeExecution, NodeStatus

logger = logging.getLogger(__name__)


class NodeExecutionTracker:
    """Tracks execution of individual LangGraph nodes."""

    def __init__(self, max_history: int = 1000) -> None:
        """Initialize node execution tracker.

        Args:
            max_history: Maximum number of executions to keep in history
        """
        self.max_history = max_history
        self._executions: Deque[NodeExecution] = deque(maxlen=max_history)
        self._active_nodes: Dict[str, NodeExecution] = {}
        self._node_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "timeouts": 0,
                "total_duration": 0.0,
                "min_duration": float("inf"),
                "max_duration": 0.0,
                "avg_duration": 0.0,
                "retry_counts": [],
                "total_started": 0,
                "executing": 0,
            }
        )
        self._retry_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_retries": 0,
                "successful_retries": 0,
                "failed_retries": 0,
                "retry_reasons": defaultdict(int),
            }
        )

    def start_node_execution(
        self,
        node_name: str,
        workflow_id: str = None,
        metadata: Dict[str, Any] = None,
        timeout_seconds: Optional[float] = None,
    ) -> str:
        """Start tracking a node execution.

        Args:
            node_name: Name of the node
            workflow_id: Associated workflow ID
            metadata: Additional metadata
            timeout_seconds: Optional timeout for node execution

        Returns:
            Execution ID
        """
        exec_id = f"{node_name}_{time.time()}"
        execution = NodeExecution(
            node_name=node_name,
            start_time=time.time(),
            metadata=metadata or {},
            timeout_seconds=timeout_seconds,
        )

        if workflow_id:
            execution.metadata["workflow_id"] = workflow_id
        if metadata:
            execution.metadata.update(metadata)
        if timeout_seconds is not None:
            execution.metadata["timeout_seconds"] = timeout_seconds
            execution.metadata["timeout_at"] = time.time() + timeout_seconds

        self._active_nodes[exec_id] = execution
        stats = self._node_stats[node_name]
        stats["total_started"] += 1
        stats["executing"] += 1

        return exec_id

    def complete_node_execution(
        self,
        node_id: str,
        status: str = "success",
        output_size_bytes: int = None,
        records_processed: int = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Complete a node execution.

        Args:
            node_id: Execution ID
            status: Final status of the node
            output_size_bytes: Size of output data
            records_processed: Number of records processed
            error: Error message if failed

        Returns:
            Execution metrics
        """
        if node_id not in self._active_nodes:
            logger.warning(f"Unknown execution ID: {node_id}")
            return {}

        execution = self._active_nodes.pop(node_id)
        execution.end_time = time.time()

        status_map = {
            "success": NodeStatus.SUCCESS,
            "failed": NodeStatus.FAILED,
            "timeout": NodeStatus.TIMEOUT,
            "cancelled": NodeStatus.CANCELLED,
        }
        execution.status = status_map.get(status, NodeStatus.SUCCESS)
        execution.error = error

        duration = execution.end_time - execution.start_time
        stats = self._node_stats[execution.node_name]
        stats["total_executions"] += 1
        stats["executing"] -= 1

        if execution.status == NodeStatus.SUCCESS:
            stats["successful"] += 1
        elif execution.status == NodeStatus.FAILED:
            stats["failed"] += 1
        elif execution.status == NodeStatus.TIMEOUT:
            stats["timeouts"] += 1

        stats["total_duration"] += duration
        stats["min_duration"] = min(stats["min_duration"], duration)
        stats["max_duration"] = max(stats["max_duration"], duration)
        stats["avg_duration"] = stats["total_duration"] / stats["total_executions"]

        if execution.retry_count > 0:
            stats["retry_counts"].append(execution.retry_count)

        self._executions.append(execution)

        metrics = {
            "status": status,
            "duration_ms": duration * 1000,
            "node_name": execution.node_name,
        }

        if output_size_bytes is not None:
            metrics["output_size_bytes"] = output_size_bytes
        if records_processed is not None:
            metrics["records_processed"] = records_processed

        return metrics

    def fail_node_execution(
        self, node_id: str, error_type: str, error_message: str, stack_trace: Optional[str] = None
    ) -> Any:
        """Mark a node execution as failed.

        Args:
            node_id: Execution ID
            error_type: Type of error
            error_message: Error description
            stack_trace: Optional stack trace for debugging

        Returns:
            Dict containing execution metrics
        """
        error_details = f"{error_type}: {error_message}"
        if stack_trace:
            error_details += f"\nStack trace:\n{stack_trace}"

        metrics = self.complete_node_execution(
            node_id=node_id, status="failed", error=error_details
        )

        if metrics:
            metrics["error_type"] = error_type
            metrics["error_message"] = error_message
            if stack_trace:
                metrics["stack_trace"] = stack_trace

        return metrics

    def check_timeout(self, node_id: str) -> bool:
        """Check if a node execution has timed out.

        Args:
            node_id: Execution ID to check

        Returns:
            True if the node has timed out, False otherwise
        """
        if node_id not in self._active_nodes:
            return False

        node = self._active_nodes[node_id]
        if node.timeout_seconds is None:
            return False

        elapsed = time.time() - node.start_time
        return elapsed > node.timeout_seconds

    def timeout_node_execution(self, node_id: str) -> Dict[str, Any]:
        """Mark a node execution as timed out.

        Args:
            node_id: Execution ID

        Returns:
            Execution metrics with timeout status
        """
        return self.complete_node_execution(
            node_id=node_id, status="timeout", error="Node execution timed out"
        )

    def start_node_retry(self, original_node_id: str, retry_attempt: int, retry_reason: str) -> str:
        """Start a retry of a failed node execution.

        Args:
            original_node_id: ID of the original failed execution
            retry_attempt: Number of retry attempt
            retry_reason: Reason for retry

        Returns:
            New execution ID for the retry
        """
        # Find original execution
        original_exec = None
        for exec in self._executions:
            if hasattr(exec, "exec_id") and exec.exec_id == original_node_id:
                original_exec = exec
                break

        if not original_exec:
            for exec in self._executions:
                if exec.node_name in original_node_id:
                    original_exec = exec
                    break

        if not original_exec:
            node_name = original_node_id.split("_")[0] if "_" in original_node_id else "unknown"
        else:
            node_name = original_exec.node_name

        retry_id = self.start_node_execution(
            node_name=node_name,
            metadata={
                "retry_attempt": retry_attempt,
                "retry_reason": retry_reason,
                "original_node_id": original_node_id,
            },
        )

        retry_stats = self._retry_stats[node_name]
        retry_stats["total_retries"] += 1
        retry_stats["retry_reasons"][retry_reason] += 1

        if retry_id in self._active_nodes:
            self._active_nodes[retry_id].retry_count = retry_attempt

        return retry_id

    def is_node_executing(self, node_id: str) -> bool:
        """Check if a node is currently executing.

        Args:
            node_id: Execution ID

        Returns:
            True if node is executing
        """
        return node_id in self._active_nodes

    def get_node_details(self, node_id: str) -> Dict[str, Any]:
        """Get detailed information about a node execution.

        Args:
            node_id: Execution ID

        Returns:
            Node execution details
        """
        if node_id in self._active_nodes:
            execution = self._active_nodes[node_id]
            return {
                "node_name": execution.node_name,
                "workflow_id": execution.metadata.get("workflow_id"),
                "status": "executing",
                "start_time": execution.start_time,
                "metadata": execution.metadata,
            }

        for exec in self._executions:
            if hasattr(exec, "exec_id") and exec.exec_id == node_id:
                return {
                    "node_name": exec.node_name,
                    "workflow_id": exec.metadata.get("workflow_id"),
                    "status": exec.status.value if exec.status else "unknown",
                    "start_time": exec.start_time,
                    "end_time": exec.end_time,
                    "duration": exec.end_time - exec.start_time if exec.end_time else None,
                    "metadata": exec.metadata,
                }

        return {}

    def get_executing_count(self) -> int:
        """Get count of currently executing nodes.

        Returns:
            Number of executing nodes
        """
        return len(self._active_nodes)

    def get_executing_nodes(self, workflow_id: str = None) -> List[str]:
        """Get list of currently executing node IDs.

        Args:
            workflow_id: Optional workflow ID to filter by

        Returns:
            List of executing node IDs
        """
        if workflow_id is None:
            return list(self._active_nodes.keys())

        return [
            node_id
            for node_id, execution in self._active_nodes.items()
            if execution.metadata.get("workflow_id") == workflow_id
        ]

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get aggregated execution statistics.

        Returns:
            Statistics dictionary
        """
        total_started = sum(stats["total_started"] for stats in self._node_stats.values())
        successful = sum(stats["successful"] for stats in self._node_stats.values())
        failed = sum(stats["failed"] for stats in self._node_stats.values())
        executing = len(self._active_nodes)

        return {
            "total_started": total_started,
            "successful": successful,
            "failed": failed,
            "executing": executing,
            "completed": successful + failed,
            "nodes": dict(self._node_stats),
        }

    def get_retry_stats(self, node_name: str) -> Dict[str, Any]:
        """Get retry statistics for a specific node.

        Args:
            node_name: Name of the node

        Returns:
            Retry statistics
        """
        stats = self._retry_stats.get(node_name, {})
        if not stats:
            return {
                "total_retries": 0,
                "successful_retries": 0,
                "failed_retries": 0,
                "retry_reasons": {},
            }

        successful_retries = 0
        for exec in self._executions:
            if (
                exec.node_name == node_name
                and exec.metadata.get("retry_attempt")
                and exec.status == NodeStatus.SUCCESS
            ):
                successful_retries += 1

        stats["successful_retries"] = successful_retries
        stats["failed_retries"] = stats["total_retries"] - successful_retries

        return dict(stats)

    # Legacy compatibility methods
    def start_node(self, node_name: str, metadata: Dict[str, Any] = None) -> str:
        """Start tracking a node execution (legacy method)."""
        return self.start_node_execution(node_name, metadata=metadata)

    def complete_node(
        self, exec_id: str, status: NodeStatus = NodeStatus.SUCCESS, error: Optional[str] = None
    ) -> None:
        """Complete a node execution (legacy method)."""
        status_str = "success" if status == NodeStatus.SUCCESS else "failed"
        self.complete_node_execution(exec_id, status=status_str, error=error)

    def retry_node(self, exec_id: str) -> None:
        """Mark a node as retrying (legacy method)."""
        if exec_id in self._active_nodes:
            self._active_nodes[exec_id].retry_count += 1
            self._active_nodes[exec_id].status = NodeStatus.RETRYING

    def get_active_nodes(self) -> List[str]:
        """Get list of currently active nodes."""
        return [exec.node_name for exec in self._active_nodes.values()]

    def get_node_stats(self, node_name: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for nodes."""
        if node_name:
            return dict(self._node_stats.get(node_name, {}))
        return dict(self._node_stats)

    def get_failure_rate(self, node_name: str, window_seconds: int = 300) -> float:
        """Calculate failure rate for a node in a time window."""
        cutoff_time = time.time() - window_seconds
        recent_executions = [
            exec
            for exec in self._executions
            if exec.node_name == node_name and exec.start_time >= cutoff_time
        ]

        if not recent_executions:
            return 0.0

        failures = sum(1 for exec in recent_executions if exec.status == NodeStatus.FAILED)
        return failures / len(recent_executions)

    @contextmanager
    def track_node(
        self, node_name: str, metadata: Dict[str, Any] = None
    ) -> Generator[Any, None, None]:
        """Context manager for tracking node execution."""
        exec_id = self.start_node_execution(node_name, metadata=metadata)
        try:
            yield exec_id
            self.complete_node_execution(exec_id, "success")
        except TimeoutError:
            self.complete_node_execution(exec_id, "timeout", error="Execution timeout")
            raise
        except (ValueError, TypeError) as e:
            self.complete_node_execution(exec_id, "failed", error=str(e))
            raise
