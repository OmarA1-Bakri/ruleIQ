"""
LangGraph-specific metrics collection and monitoring.

This module provides a unified interface for collecting and managing all
LangGraph-related metrics. The individual tracker implementations have been
moved to the trackers subpackage for better organization.
"""

import logging
from typing import Any, Dict, Optional

# Import all tracker classes from the new modules
from .trackers import (
    CheckpointMetrics,
    CheckpointMetricsTracker,
    ErrorAnalysisTracker,
    ErrorMetricsCollector,
    MemoryUsageTracker,
    NodeExecution,
    NodeExecutionTracker,
    NodeStatus,
    PerformanceAnalyzer,
    StateTransitionTracker,
    WorkflowExecution,
    WorkflowMetricsTracker,
    WorkflowStatus,
)

# Re-export all tracker classes for backward compatibility
__all__ = [
    # Main collector
    "LangGraphMetricsCollector",
    # Trackers
    "NodeExecutionTracker",
    "WorkflowMetricsTracker",
    "StateTransitionTracker",
    "CheckpointMetricsTracker",
    "CheckpointMetrics",  # Alias
    "MemoryUsageTracker",
    "ErrorAnalysisTracker",
    "ErrorMetricsCollector",  # Alias
    "PerformanceAnalyzer",
    # Types
    "NodeStatus",
    "WorkflowStatus",
    "NodeExecution",
    "WorkflowExecution",
]

logger = logging.getLogger(__name__)


class LangGraphMetricsCollector:
    """
    Main collector that aggregates all LangGraph metrics components.

    This class provides a unified interface for collecting and managing
    all LangGraph-related metrics including node execution, workflow tracking,
    state transitions, checkpoints, memory usage, errors, and performance.
    """

    def __init__(self) -> None:
        """Initialize all metric collectors and trackers."""
        self.node_tracker = NodeExecutionTracker()
        self.workflow_tracker = WorkflowMetricsTracker()
        self.state_tracker = StateTransitionTracker()
        self.checkpoint_metrics = CheckpointMetricsTracker()
        self.memory_tracker = MemoryUsageTracker()
        self.error_collector = ErrorAnalysisTracker()
        self.performance_analyzer = PerformanceAnalyzer()

    async def start_workflow(
        self, workflow_id: str, workflow_name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Start tracking a new workflow execution.

        Args:
            workflow_id: Unique identifier for the workflow
            workflow_name: Name of the workflow
            metadata: Optional metadata for the workflow
        """
        # Note: The original method had an await but WorkflowMetricsTracker.start_workflow
        # is not async, so we'll call it directly
        self.workflow_tracker.start_workflow(workflow_type=workflow_name, metadata=metadata)

    async def track_node_execution(
        self,
        node_name: str,
        execution_time: float,
        status: str,
        workflow_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track a node execution.

        Args:
            node_name: Name of the node
            execution_time: Time taken to execute the node
            status: Status of the execution (success/failure)
            workflow_id: Optional workflow ID
            metadata: Optional metadata
        """
        # Start and complete node execution
        exec_id = self.node_tracker.start_node_execution(
            node_name=node_name, workflow_id=workflow_id, metadata=metadata
        )
        # Complete the execution after the specified time
        self.node_tracker.complete_node_execution(node_id=exec_id, status=status)

    async def track_state_transition(
        self,
        from_state: str,
        to_state: str,
        transition_time: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track a state transition.

        Args:
            from_state: Source state
            to_state: Target state
            transition_time: Time taken for transition
            metadata: Optional metadata
        """
        # Create a workflow ID for the transition if not provided
        workflow_id = metadata.get("workflow_id", "default") if metadata else "default"
        self.state_tracker.record_transition(
            workflow_id=workflow_id, from_state=from_state, to_state=to_state, metadata=metadata
        )

    async def track_checkpoint(
        self,
        checkpoint_id: str,
        size_bytes: int,
        save_time: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track checkpoint metrics.

        Args:
            checkpoint_id: Unique checkpoint identifier
            size_bytes: Size of checkpoint in bytes
            save_time: Time taken to save checkpoint
            metadata: Optional metadata
        """
        # Record checkpoint save
        workflow_id = metadata.get("workflow_id", "default") if metadata else "default"
        save_id = self.checkpoint_metrics.record_checkpoint_save(
            workflow_id=workflow_id, checkpoint_size_bytes=size_bytes
        )
        # Complete the save operation
        self.checkpoint_metrics.complete_checkpoint_save(checkpoint_id=save_id, success=True)

    async def track_memory_usage(
        self, node_name: str, memory_mb: float, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track memory usage for a node.

        Args:
            node_name: Name of the node
            memory_mb: Memory usage in MB
            metadata: Optional metadata
        """
        # Convert MB to bytes for internal tracking
        bytes_used = int(memory_mb * 1024 * 1024)
        self.memory_tracker.record_memory_usage(component=node_name, bytes_used=bytes_used)

    async def track_error(
        self,
        error_type: str,
        node_name: Optional[str] = None,
        workflow_id: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track an error occurrence.

        Args:
            error_type: Type of error
            node_name: Optional node where error occurred
            workflow_id: Optional workflow ID
            error_details: Optional error details
        """
        self.error_collector.record_error(
            error_type=error_type,
            node_name=node_name,
            workflow_id=workflow_id,
            metadata=error_details,
            component=node_name,
        )

    async def complete_workflow(
        self, workflow_id: str, status: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Complete workflow tracking.

        Args:
            workflow_id: Workflow identifier
            status: Final status of workflow
            metadata: Optional metadata
        """
        self.workflow_tracker.complete_workflow(workflow_id=workflow_id, status=status)

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all collected metrics.

        Returns:
            Dictionary containing metrics from all collectors
        """
        summary = {}

        # Get node execution stats
        summary["node_stats"] = self.node_tracker.get_execution_stats()

        # Get workflow stats
        summary["workflow_summary"] = self.workflow_tracker.get_workflow_stats()

        # Get state transition stats
        summary["state_transitions"] = self.state_tracker.get_transition_matrix()

        # Get checkpoint stats
        summary["checkpoint_stats"] = self.checkpoint_metrics.get_statistics()

        # Get memory stats
        summary["memory_stats"] = self.memory_tracker.get_total_memory_usage()
        summary["memory_trends"] = self.memory_tracker.get_memory_trends()

        # Get error stats
        summary["error_summary"] = self.error_collector.get_error_stats()

        # Get performance analysis
        summary["performance_analysis"] = self.performance_analyzer.get_performance_summary()

        return summary

    async def reset_metrics(self) -> None:
        """Reset all metrics collectors."""
        # Reinitialize all trackers
        self.node_tracker = NodeExecutionTracker()
        self.workflow_tracker = WorkflowMetricsTracker()
        self.state_tracker = StateTransitionTracker()
        self.checkpoint_metrics = CheckpointMetricsTracker()
        self.memory_tracker = MemoryUsageTracker()
        self.error_collector = ErrorAnalysisTracker()
        self.performance_analyzer = PerformanceAnalyzer()

    def get_node_tracker(self) -> NodeExecutionTracker:
        """Get the node execution tracker instance."""
        return self.node_tracker

    def get_workflow_tracker(self) -> WorkflowMetricsTracker:
        """Get the workflow metrics tracker instance."""
        return self.workflow_tracker

    def get_state_tracker(self) -> StateTransitionTracker:
        """Get the state transition tracker instance."""
        return self.state_tracker

    def get_checkpoint_metrics(self) -> CheckpointMetricsTracker:
        """Get the checkpoint metrics tracker instance."""
        return self.checkpoint_metrics

    def get_memory_tracker(self) -> MemoryUsageTracker:
        """Get the memory usage tracker instance."""
        return self.memory_tracker

    def get_error_collector(self) -> ErrorAnalysisTracker:
        """Get the error metrics collector instance."""
        return self.error_collector

    def get_performance_analyzer(self) -> PerformanceAnalyzer:
        """Get the performance analyzer instance."""
        return self.performance_analyzer
