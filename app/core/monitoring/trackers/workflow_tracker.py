"""
Workflow metrics tracking for LangGraph workflows.
"""

import logging
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Tuple, Union

from .types import NodeExecution, NodeStatus, WorkflowExecution, WorkflowStatus

logger = logging.getLogger(__name__)


class WorkflowMetricsTracker:
    """Tracks metrics for complete LangGraph workflows."""

    def __init__(self, max_history: int = 100) -> None:
        """Initialize workflow metrics tracker.

        Args:
            max_history: Maximum number of workflows to keep in history
        """
        self.max_history = max_history
        self._workflows: Deque[WorkflowExecution] = deque(maxlen=max_history)
        self._active_workflows: Dict[str, WorkflowExecution] = {}
        self._workflow_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'total_executions': 0,
                'completed': 0,
                'failed': 0,
                'cancelled': 0,
                'total_duration': 0.0,
                'avg_duration': 0.0,
                'avg_nodes_per_workflow': 0.0,
                'throughput_per_minute': 0.0,
                'total_started': 0,
                'active': 0
            }
        )
        self._throughput_window: Deque[Tuple[float, str]] = deque(maxlen=1000)
        self._concurrency_limits: Dict[str, int] = {}

    def start_workflow(
        self,
        workflow_type: str,
        trigger_source: str = 'unknown',
        metadata: Dict[str, Any] = None,
        timestamp: Optional[Union[float, datetime]] = None
    ) -> str:
        """Start tracking a workflow execution.

        Args:
            workflow_type: Type of workflow
            trigger_source: What triggered the workflow
            metadata: Additional metadata
            timestamp: Optional timestamp for when workflow started (float or datetime)

        Returns:
            Workflow ID
        """
        if timestamp is not None:
            start_time = timestamp.timestamp() if isinstance(timestamp, datetime) else timestamp
        else:
            start_time = time.time()

        workflow_id = f'{workflow_type}_{start_time}'
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            start_time=start_time,
            metadata=metadata or {}
        )

        if trigger_source:
            execution.metadata['trigger_source'] = trigger_source
        if metadata:
            execution.metadata.update(metadata)

        self._active_workflows[workflow_id] = execution
        stats = self._workflow_stats[workflow_type]
        stats['total_started'] += 1
        stats['active'] += 1

        return workflow_id

    def is_workflow_active(self, workflow_id: str) -> bool:
        """Check if a workflow is currently active.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if workflow is active
        """
        return workflow_id in self._active_workflows

    def add_node_execution(
        self,
        workflow_id: str,
        node_name: str,
        duration_ms: float,
        status: str = 'success',
        error_info: Dict[str, Any] = None
    ) -> None:
        """Add a node execution to a workflow.

        Args:
            workflow_id: Workflow ID
            node_name: Name of the node
            duration_ms: Duration in milliseconds
            status: Node execution status
            error_info: Error information if applicable
        """
        if workflow_id not in self._active_workflows:
            logger.warning(f'Unknown workflow ID: {workflow_id}')
            return

        node_exec = NodeExecution(
            node_name=node_name,
            start_time=time.time() - duration_ms / 1000,
            end_time=time.time(),
            status=NodeStatus(status) if isinstance(status, str) else status
        )

        node_exec.metadata = {'duration_ms': duration_ms}
        if error_info:
            node_exec.error = error_info.get('message', str(error_info))
            node_exec.metadata.update(error_info)

        self._active_workflows[workflow_id].nodes.append(node_exec)

    def complete_workflow(
        self,
        workflow_id: str,
        status: str = 'completed',
        output: Dict[str, Any] = None,
        output_size_bytes: int = None,
        records_processed: int = None,
        timestamp: Optional[Union[float, datetime]] = None
    ) -> Dict[str, Any]:
        """Complete a workflow execution.

        Args:
            workflow_id: Workflow ID
            status: Final status of the workflow
            output: Output data
            output_size_bytes: Size of output data
            records_processed: Number of records processed
            timestamp: Optional completion timestamp

        Returns:
            Workflow metrics summary
        """
        if workflow_id not in self._active_workflows:
            logger.warning(f'Unknown workflow ID: {workflow_id}')
            return {}

        workflow = self._active_workflows.pop(workflow_id)

        if timestamp is not None:
            if isinstance(timestamp, datetime):
                workflow.end_time = timestamp.timestamp()
            else:
                workflow.end_time = timestamp
        else:
            workflow.end_time = time.time()

        status_map = {
            'completed': WorkflowStatus.COMPLETED,
            'success': WorkflowStatus.COMPLETED,
            'failed': WorkflowStatus.FAILED,
            'cancelled': WorkflowStatus.CANCELLED,
            'error': WorkflowStatus.FAILED
        }
        workflow.status = status_map.get(status, WorkflowStatus.COMPLETED)

        duration = workflow.end_time - workflow.start_time
        stats = self._workflow_stats[workflow.workflow_type]
        stats['total_executions'] += 1
        stats['active'] -= 1

        if workflow.status == WorkflowStatus.COMPLETED:
            stats['completed'] += 1
        elif workflow.status == WorkflowStatus.FAILED:
            stats['failed'] += 1
        elif workflow.status == WorkflowStatus.CANCELLED:
            stats['cancelled'] += 1

        stats['total_duration'] += duration
        stats['avg_duration'] = stats['total_duration'] / stats['total_executions']

        node_count = len(workflow.nodes)
        total_nodes = stats.get('total_nodes', 0) + node_count
        stats['total_nodes'] = total_nodes
        stats['avg_nodes_per_workflow'] = total_nodes / stats['total_executions']

        self._throughput_window.append((workflow.end_time, workflow.workflow_type))
        self.calculate_throughput(workflow.workflow_type)

        self._workflows.append(workflow)

        total_node_duration_ms = sum(
            node.metadata.get('duration_ms', (node.end_time - node.start_time) * 1000)
            for node in workflow.nodes
            if hasattr(node, 'metadata') and node.metadata
        )

        metrics = {
            'workflow_id': workflow_id,
            'workflow_type': workflow.workflow_type,
            'status': status,
            'duration_ms': duration * 1000,
            'workflow_duration_ms': duration * 1000,
            'duration_seconds': duration,
            'total_nodes_executed': node_count,
            'total_node_duration_ms': total_node_duration_ms,
            'metadata': workflow.metadata
        }

        if output:
            metrics['output'] = output
        if output_size_bytes is not None:
            metrics['output_size_bytes'] = output_size_bytes
        if records_processed is not None:
            metrics['records_processed'] = records_processed

        return metrics

    def fail_workflow(
        self,
        workflow_id: str,
        failure_node: str = None,
        error_type: str = None,
        error_message: str = None
    ) -> Dict[str, Any]:
        """Mark a workflow as failed.

        Args:
            workflow_id: Workflow ID
            failure_node: Node that caused the failure
            error_type: Type of error
            error_message: Error description

        Returns:
            Workflow failure metrics
        """
        if workflow_id in self._active_workflows:
            workflow = self._active_workflows[workflow_id]
            successful_nodes = sum(
                1 for node in workflow.nodes if node.status == NodeStatus.SUCCESS
            )
            failed_nodes = sum(
                1 for node in workflow.nodes if node.status == NodeStatus.FAILED
            )

            if error_type:
                workflow.metadata['error_type'] = error_type
            if error_message:
                workflow.metadata['error_message'] = error_message
            if failure_node:
                workflow.metadata['failure_node'] = failure_node

            metrics = self.complete_workflow(workflow_id, status='failed')
            metrics['successful_nodes'] = successful_nodes
            metrics['failed_nodes'] = failed_nodes

            if failure_node:
                metrics['failure_node'] = failure_node
            if error_type:
                metrics['error_type'] = error_type
            if error_message:
                metrics['error_message'] = error_message

            return metrics

        return {
            'workflow_id': workflow_id,
            'status': 'failed',
            'error': 'Workflow not found',
            'successful_nodes': 0,
            'failed_nodes': 0
        }

    def cancel_workflow(
        self,
        workflow_id: str,
        cancellation_reason: str = None
    ) -> Dict[str, Any]:
        """Cancel an active workflow.

        Args:
            workflow_id: Workflow ID
            cancellation_reason: Optional reason for cancellation

        Returns:
            Workflow metrics including cancellation details
        """
        if workflow_id not in self._active_workflows:
            return {
                'status': 'not_found',
                'message': f'Workflow {workflow_id} not found in active workflows'
            }

        workflow = self._active_workflows[workflow_id]
        workflow.status = WorkflowStatus.CANCELLED
        workflow.end_time = time.time()

        nodes_completed = sum(
            1 for node in workflow.nodes
            if node.status in [NodeStatus.SUCCESS, NodeStatus.FAILED]
        )

        self._workflow_stats[workflow.workflow_type]['cancelled'] += 1
        self._workflow_stats[workflow.workflow_type]['active'] -= 1
        self._workflows.append(workflow)
        del self._active_workflows[workflow_id]

        return {
            'workflow_id': workflow_id,
            'status': 'cancelled',
            'cancellation_reason': cancellation_reason,
            'nodes_completed_before_cancellation': nodes_completed,
            'duration': workflow.end_time - workflow.start_time if workflow.end_time else 0,
            'workflow_type': workflow.workflow_type
        }

    def get_workflow_details(self, workflow_id: str) -> Dict[str, Any]:
        """Get detailed information about a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow details
        """
        if workflow_id in self._active_workflows:
            workflow = self._active_workflows[workflow_id]
            return {
                'workflow_id': workflow_id,
                'workflow_type': workflow.workflow_type,
                'status': 'active',
                'start_time': workflow.start_time,
                'duration_so_far': time.time() - workflow.start_time,
                'nodes_executed': len(workflow.nodes),
                'metadata': workflow.metadata
            }

        for wf in self._workflows:
            if wf.workflow_id == workflow_id:
                return {
                    'workflow_id': workflow_id,
                    'workflow_type': wf.workflow_type,
                    'status': wf.status.value if wf.status else 'unknown',
                    'start_time': wf.start_time,
                    'end_time': wf.end_time,
                    'duration': wf.end_time - wf.start_time if wf.end_time else None,
                    'nodes_executed': len(wf.nodes),
                    'metadata': wf.metadata
                }

        return {}

    def get_active_count(self, workflow_type: Optional[str] = None) -> int:
        """Get count of currently active workflows.

        Args:
            workflow_type: Optional workflow type to filter by

        Returns:
            Number of active workflows
        """
        if workflow_type is None:
            return len(self._active_workflows)

        return sum(
            1 for wf in self._active_workflows.values()
            if wf.workflow_type == workflow_type
        )

    def get_workflow_stats(self, workflow_type: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for workflows.

        Args:
            workflow_type: Specific workflow type or None for all

        Returns:
            Statistics dictionary
        """
        if workflow_type:
            stats = dict(self._workflow_stats.get(workflow_type, {}))
            stats['active_count'] = sum(
                1 for wf in self._active_workflows.values()
                if wf.workflow_type == workflow_type
            )
            return stats

        all_stats = dict(self._workflow_stats)
        total_active = len(self._active_workflows)
        total_started = sum(s.get('total_started', 0) for s in all_stats.values())
        total_completed = sum(s.get('completed', 0) for s in all_stats.values())
        total_failed = sum(s.get('failed', 0) for s in all_stats.values())

        return {
            'workflows': all_stats,
            'total_started': total_started,
            'total_active': total_active,
            'total_completed': total_completed,
            'total_failed': total_failed
        }

    def get_performance_stats(self, workflow_type: str) -> Dict[str, Any]:
        """Get performance statistics for a workflow type.

        Args:
            workflow_type: Type of workflow to get stats for

        Returns:
            Performance statistics including percentiles
        """
        self._workflow_stats.get(workflow_type, {})
        recent_workflows = [
            wf for wf in self._workflows
            if wf.workflow_type == workflow_type and wf.end_time
        ]
        total_workflows = len([
            wf for wf in self._workflows
            if wf.workflow_type == workflow_type
        ])
        successful_workflows = len([
            wf for wf in self._workflows
            if wf.workflow_type == workflow_type and wf.status == WorkflowStatus.COMPLETED
        ])

        if not recent_workflows:
            return {
                'workflow_type': workflow_type,
                'sample_size': 0,
                'total_workflows': total_workflows,
                'successful_workflows': successful_workflows,
                'p50_duration_ms': 0.0,
                'p90_duration_ms': 0.0,
                'p95_duration_ms': 0.0,
                'p99_duration_ms': 0.0,
                'min_duration_ms': 0.0,
                'max_duration_ms': 0.0,
                'average_duration_ms': 0.0
            }

        durations = sorted([wf.end_time - wf.start_time for wf in recent_workflows])

        def percentile(data, p) -> Any:
            if not data:
                return 0.0
            k = (len(data) - 1) * p / 100
            f = int(k)
            c = f + 1 if f < len(data) - 1 else f
            return data[f] if f == c else data[f] + (k - f) * (data[c] - data[f])

        durations_ms = [d * 1000 for d in durations]

        return {
            'workflow_type': workflow_type,
            'sample_size': len(durations),
            'total_workflows': total_workflows,
            'successful_workflows': successful_workflows,
            'p50_duration_ms': percentile(durations_ms, 50),
            'p90_duration_ms': percentile(durations_ms, 90),
            'p95_duration_ms': percentile(durations_ms, 95),
            'p99_duration_ms': percentile(durations_ms, 99),
            'min_duration_ms': min(durations_ms) if durations_ms else 0.0,
            'max_duration_ms': max(durations_ms) if durations_ms else 0.0,
            'average_duration_ms': sum(durations_ms) / len(durations_ms) if durations_ms else 0.0
        }

    def get_throughput_metrics(
        self,
        workflow_type: str,
        window_minutes: int = 5
    ) -> Dict[str, float]:
        """Get throughput metrics for a workflow type.

        Args:
            workflow_type: Type of workflow
            window_minutes: Time window in minutes

        Returns:
            Throughput metrics
        """
        cutoff_time = time.time() - window_minutes * 60
        recent_workflows = [
            (ts, wf_type) for ts, wf_type in self._throughput_window
            if ts >= cutoff_time and wf_type == workflow_type
        ]

        if not recent_workflows:
            return {
                'workflows_per_minute': 0.0,
                'avg_per_minute': 0.0,
                'peak_per_minute': 0.0
            }

        minutes_data = defaultdict(int)
        for ts, _ in recent_workflows:
            minute_bucket = int(ts / 60)
            minutes_data[minute_bucket] += 1

        rates = list(minutes_data.values())

        return {
            'workflows_per_minute': len(recent_workflows) / window_minutes,
            'avg_per_minute': sum(rates) / len(rates) if rates else 0,
            'peak_per_minute': max(rates) if rates else 0
        }

    def calculate_throughput(
        self,
        workflow_type: str,
        time_window_seconds: int = 60
    ) -> Dict[str, float]:
        """Calculate throughput for a workflow type.

        Args:
            workflow_type: Type of workflow
            time_window_seconds: Time window in seconds for calculation

        Returns:
            Throughput metrics
        """
        cutoff_time = time.time() - time_window_seconds
        recent_workflows = [
            (ts, wf_type) for ts, wf_type in self._throughput_window
            if ts >= cutoff_time and wf_type == workflow_type
        ]

        workflow_count = len(recent_workflows)
        workflows_per_second = workflow_count / time_window_seconds if time_window_seconds > 0 else 0
        workflows_per_minute = workflows_per_second * 60

        recent_completed = [
            wf for wf in self._workflows
            if (wf.workflow_type == workflow_type and
                wf.end_time is not None and
                wf.start_time is not None and
                wf.end_time >= cutoff_time)
        ]

        avg_duration_ms = 0.0
        if recent_completed:
            durations = [(wf.end_time - wf.start_time) * 1000 for wf in recent_completed]
            avg_duration_ms = sum(durations) / len(durations)

        stats = self._workflow_stats[workflow_type]
        stats['throughput_per_minute'] = workflows_per_minute

        return {
            'workflows_per_second': workflows_per_second,
            'workflows_per_minute': workflows_per_minute,
            'average_duration_ms': avg_duration_ms
        }

    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get list of currently active workflows.

        Returns:
            List of workflow summaries
        """
        return [
            {
                'workflow_id': wf.workflow_id,
                'workflow_type': wf.workflow_type,
                'duration_so_far': time.time() - wf.start_time,
                'nodes_executed': len(wf.nodes),
                'metadata': wf.metadata
            }
            for wf in self._active_workflows.values()
        ]

    def set_concurrency_limit(self, workflow_type: str, max_concurrent: int) -> None:
        """Set concurrency limit for a workflow type.

        Args:
            workflow_type: Type of workflow
            max_concurrent: Maximum number of concurrent workflows allowed
        """
        self._concurrency_limits[workflow_type] = max_concurrent

    def can_start_workflow(self, workflow_type: str) -> bool:
        """Check if a new workflow can be started based on concurrency limits.

        Args:
            workflow_type: Type of workflow to check

        Returns:
            True if the workflow can be started, False otherwise
        """
        limit = self._concurrency_limits.get(workflow_type)
        if limit is None:
            return True

        active_count = sum(
            1 for wf in self._active_workflows.values()
            if wf.workflow_type == workflow_type
        )
        return active_count < limit

    def check_concurrency_limit(self, workflow_type: str, limit: int) -> bool:
        """Check if workflow type has reached concurrency limit.

        Args:
            workflow_type: Type of workflow
            limit: Maximum concurrent workflows

        Returns:
            True if limit reached, False otherwise
        """
        active_count = sum(
            1 for wf in self._active_workflows.values()
            if wf.workflow_type == workflow_type
        )
        return active_count >= limit
