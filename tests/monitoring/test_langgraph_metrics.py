"""
Test suite for LangGraph-specific custom metrics.
Tests node execution tracking, workflow metrics, and state management metrics.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from app.core.monitoring.langgraph_metrics import (
    LangGraphMetricsCollector,
    NodeExecutionTracker,
    WorkflowMetricsTracker,
    StateTransitionTracker,
    CheckpointMetrics,
    MemoryUsageTracker,
    ErrorMetricsCollector,
    PerformanceAnalyzer,
)


class TestNodeExecutionTracker:
    """Test tracking metrics for individual LangGraph nodes."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = NodeExecutionTracker()

    def test_node_execution_start(self):
        """Test starting node execution tracking."""
        node_id = self.tracker.start_node_execution(
            node_name="compliance_check",
            workflow_id="wf-123",
            metadata={"user_id": "user-456"},
        )

        assert node_id is not None
        assert self.tracker.is_node_executing(node_id)

        # Verify node details
        details = self.tracker.get_node_details(node_id)
        assert details["node_name"] == "compliance_check"
        assert details["workflow_id"] == "wf-123"
        assert details["status"] == "executing"
        assert "start_time" in details

    def test_node_execution_completion(self):
        """Test completing node execution with metrics."""
        node_id = self.tracker.start_node_execution("test_node")

        # Simulate some work
        time.sleep(0.1)

        # Complete execution
        metrics = self.tracker.complete_node_execution(
            node_id=node_id,
            status="success",
            output_size_bytes=1024,
            records_processed=100,
        )

        assert metrics is not None
        assert metrics["status"] == "success"
        assert metrics["duration_ms"] >= 100  # At least 100ms due to sleep
        assert metrics["output_size_bytes"] == 1024
        assert metrics["records_processed"] == 100
        assert not self.tracker.is_node_executing(node_id)

    def test_node_execution_failure(self):
        """Test tracking failed node execution."""
        node_id = self.tracker.start_node_execution("failing_node")

        # Fail execution
        metrics = self.tracker.fail_node_execution(
            node_id=node_id,
            error_type="ValidationError",
            error_message="Invalid input data",
            stack_trace="...",
        )

        assert metrics["status"] == "failed"
        assert metrics["error_type"] == "ValidationError"
        assert metrics["error_message"] == "Invalid input data"
        assert "duration_ms" in metrics

    def test_node_execution_timeout(self):
        """Test handling node execution timeout."""
        node_id = self.tracker.start_node_execution(
            node_name="slow_node",
            timeout_seconds=1,
        )

        # Simulate timeout
        time.sleep(1.1)

        # Check if timeout is detected
        is_timed_out = self.tracker.check_timeout(node_id)
        assert is_timed_out

        # Complete as timeout
        metrics = self.tracker.timeout_node_execution(node_id)
        assert metrics["status"] == "timeout"
        assert metrics["duration_ms"] >= 1000

    def test_concurrent_node_executions(self):
        """Test tracking multiple concurrent node executions."""
        node_ids = []

        # Start multiple nodes
        for i in range(5):
            node_id = self.tracker.start_node_execution(
                node_name=f"node_{i}",
                workflow_id="concurrent_test",
            )
            node_ids.append(node_id)

        # Verify all are executing
        assert self.tracker.get_executing_count() == 5
        assert self.tracker.get_executing_nodes("concurrent_test") == node_ids

        # Complete some nodes
        self.tracker.complete_node_execution(node_ids[0], "success")
        self.tracker.fail_node_execution(node_ids[1], "Error", "Test error")

        # Verify counts
        assert self.tracker.get_executing_count() == 3

        # Get aggregated metrics
        stats = self.tracker.get_execution_stats()
        assert stats["total_started"] == 5
        assert stats["successful"] == 1
        assert stats["failed"] == 1
        assert stats["executing"] == 3

    def test_node_retry_tracking(self):
        """Test tracking node execution retries."""
        original_id = self.tracker.start_node_execution("retry_node")

        # Fail first attempt
        self.tracker.fail_node_execution(
            original_id,
            "NetworkError",
            "Connection failed",
        )

        # Start retry
        retry_id = self.tracker.start_node_retry(
            original_node_id=original_id,
            retry_attempt=1,
            retry_reason="NetworkError",
        )

        assert retry_id != original_id

        # Complete retry successfully
        metrics = self.tracker.complete_node_execution(retry_id, "success")

        # Get retry statistics
        retry_stats = self.tracker.get_retry_stats("retry_node")
        assert retry_stats["total_retries"] == 1
        assert retry_stats["successful_retries"] == 1
        assert retry_stats["retry_reasons"]["NetworkError"] == 1


class TestWorkflowMetricsTracker:
    """Test tracking metrics for complete LangGraph workflows."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = WorkflowMetricsTracker()

    def test_workflow_lifecycle(self):
        """Test complete workflow lifecycle tracking."""
        # Start workflow
        workflow_id = self.tracker.start_workflow(
            workflow_type="assessment",
            trigger_source="api",
            metadata={"user_id": "user-123", "company_id": "comp-456"},
        )

        assert workflow_id is not None
        assert self.tracker.is_workflow_active(workflow_id)

        # Add node executions
        self.tracker.add_node_execution(workflow_id, "node1", 100, "success")
        self.tracker.add_node_execution(workflow_id, "node2", 150, "success")
        self.tracker.add_node_execution(workflow_id, "node3", 200, "success")

        # Complete workflow
        metrics = self.tracker.complete_workflow(
            workflow_id=workflow_id,
            status="completed",
            output={"result": "success"},
        )

        assert metrics["status"] == "completed"
        assert metrics["total_nodes_executed"] == 3
        assert metrics["total_node_duration_ms"] == 450
        assert metrics["workflow_duration_ms"] >= 0
        assert not self.tracker.is_workflow_active(workflow_id)

    def test_workflow_failure_tracking(self):
        """Test tracking workflow failures and error propagation."""
        workflow_id = self.tracker.start_workflow("validation_workflow")

        # Add successful nodes
        self.tracker.add_node_execution(workflow_id, "validate_input", 50, "success")

        # Add failed node
        self.tracker.add_node_execution(
            workflow_id=workflow_id,
            node_name="process_data",
            duration_ms=100,
            status="failed",
            error_info={"type": "DataError", "message": "Invalid format"},
        )

        # Fail workflow
        metrics = self.tracker.fail_workflow(
            workflow_id=workflow_id,
            failure_node="process_data",
            error_type="DataError",
            error_message="Invalid format in input data",
        )

        assert metrics["status"] == "failed"
        assert metrics["failure_node"] == "process_data"
        assert metrics["successful_nodes"] == 1
        assert metrics["failed_nodes"] == 1
        assert metrics["error_type"] == "DataError"

    def test_workflow_cancellation(self):
        """Test tracking workflow cancellation."""
        workflow_id = self.tracker.start_workflow("long_running_workflow")

        # Add some node executions
        self.tracker.add_node_execution(workflow_id, "node1", 100, "success")

        # Cancel workflow
        metrics = self.tracker.cancel_workflow(
            workflow_id=workflow_id,
            cancellation_reason="User requested cancellation",
        )

        assert metrics["status"] == "cancelled"
        assert metrics["cancellation_reason"] == "User requested cancellation"
        assert metrics["nodes_completed_before_cancellation"] == 1

    def test_workflow_performance_metrics(self):
        """Test collecting workflow performance metrics."""
        # Run multiple workflows
        for i in range(10):
            wf_id = self.tracker.start_workflow("perf_test")

            # Add variable node executions
            for j in range(3):
                self.tracker.add_node_execution(
                    wf_id,
                    f"node_{j}",
                    duration_ms=100 * (i + 1),  # Variable duration
                    status="success",
                )

            self.tracker.complete_workflow(wf_id, "completed")

        # Get performance statistics
        perf_stats = self.tracker.get_performance_stats("perf_test")

        assert perf_stats["total_workflows"] == 10
        assert perf_stats["successful_workflows"] == 10
        assert perf_stats["average_duration_ms"] > 0
        assert perf_stats["min_duration_ms"] > 0
        assert perf_stats["max_duration_ms"] > perf_stats["min_duration_ms"]
        assert perf_stats["p50_duration_ms"] > 0
        assert perf_stats["p95_duration_ms"] > 0
        assert perf_stats["p99_duration_ms"] > 0

    def test_workflow_throughput_tracking(self):
        """Test tracking workflow throughput over time."""
        # Simulate workflows over time
        start_time = datetime.now()

        for i in range(20):
            wf_id = self.tracker.start_workflow(
                workflow_type="throughput_test",
                timestamp=start_time + timedelta(seconds=i),
            )
            self.tracker.complete_workflow(
                wf_id,
                "completed",
                timestamp=start_time + timedelta(seconds=i, milliseconds=100),
            )

        # Calculate throughput
        throughput = self.tracker.calculate_throughput(
            workflow_type="throughput_test",
            time_window_seconds=60,
        )

        assert throughput["workflows_per_second"] > 0
        assert throughput["workflows_per_minute"] == 20
        assert throughput["average_duration_ms"] >= 0

    def test_workflow_concurrency_limits(self):
        """Test tracking concurrent workflow execution limits."""
        # Set concurrency limit
        self.tracker.set_concurrency_limit("limited_workflow", max_concurrent=3)

        # Start workflows up to limit
        workflow_ids = []
        for _i in range(5):
            can_start = self.tracker.can_start_workflow("limited_workflow")

            if can_start:
                wf_id = self.tracker.start_workflow("limited_workflow")
                workflow_ids.append(wf_id)

        # Should only start 3 workflows
        assert len(workflow_ids) == 3
        assert self.tracker.get_active_count("limited_workflow") == 3

        # Complete one workflow
        self.tracker.complete_workflow(workflow_ids[0], "completed")

        # Now another can start
        assert self.tracker.can_start_workflow("limited_workflow")


class TestStateTransitionTracker:
    """Test tracking state transitions in LangGraph."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = StateTransitionTracker()

    def test_state_transition_recording(self):
        """Test recording state transitions."""
        transition_id = self.tracker.record_transition(
            workflow_id="wf-123",
            from_state="pending",
            to_state="processing",
            transition_trigger="user_action",
            metadata={"user_id": "user-456"},
        )

        assert transition_id is not None

        # Get transition details
        details = self.tracker.get_transition_details(transition_id)
        assert details["from_state"] == "pending"
        assert details["to_state"] == "processing"
        assert details["transition_trigger"] == "user_action"
        assert "timestamp" in details

    def test_state_machine_validation(self):
        """Test validation of state transitions against state machine rules."""
        # Define valid transitions
        self.tracker.define_state_machine(
            {
                "pending": ["processing", "cancelled"],
                "processing": ["completed", "failed", "cancelled"],
                "completed": [],  # Terminal state
                "failed": ["pending"],  # Can retry
                "cancelled": [],  # Terminal state,
            },
        )

        # Test valid transitions
        assert self.tracker.is_valid_transition("pending", "processing")
        assert self.tracker.is_valid_transition("processing", "completed")
        assert self.tracker.is_valid_transition("failed", "pending")

        # Test invalid transitions
        assert not self.tracker.is_valid_transition("pending", "completed")
        assert not self.tracker.is_valid_transition("completed", "pending")
        assert not self.tracker.is_valid_transition("cancelled", "processing")

    def test_workflow_state_history(self):
        """Test tracking complete state history for a workflow."""
        workflow_id = "history-test"

        # Record state transitions
        self.tracker.record_transition(workflow_id, "pending", "processing")
        time.sleep(0.1)
        self.tracker.record_transition(workflow_id, "processing", "validation")
        time.sleep(0.1)
        self.tracker.record_transition(workflow_id, "validation", "completed")

        # Get state history
        history = self.tracker.get_workflow_history(workflow_id)

        assert len(history) == 3
        assert history[0]["to_state"] == "processing"
        assert history[1]["to_state"] == "validation"
        assert history[2]["to_state"] == "completed"

        # Verify chronological order
        for i in range(len(history) - 1):
            assert history[i]["timestamp"] < history[i + 1]["timestamp"]

    def test_state_duration_tracking(self):
        """Test tracking time spent in each state."""
        workflow_id = "duration-test"

        # Start in pending state
        self.tracker.enter_state(workflow_id, "pending")
        time.sleep(0.1)

        # Move to processing
        self.tracker.enter_state(workflow_id, "processing")
        time.sleep(0.2)

        # Move to completed
        self.tracker.enter_state(workflow_id, "completed")

        # Get state durations
        durations = self.tracker.get_state_durations(workflow_id)

        assert durations["pending"] >= 100  # At least 100ms
        assert durations["processing"] >= 200  # At least 200ms
        assert "completed" not in durations  # Still in this state

    def test_state_transition_patterns(self):
        """Test analyzing state transition patterns."""
        # Record many transitions
        for i in range(100):
            workflow_id = f"pattern-{i}"

            if i % 10 == 0:
                # 10% fail
                self.tracker.record_transition(workflow_id, "pending", "processing")
                self.tracker.record_transition(workflow_id, "processing", "failed")
            elif i % 5 == 0:
                # 10% cancelled (excluding failures)
                self.tracker.record_transition(workflow_id, "pending", "cancelled")
            else:
                # 80% success
                self.tracker.record_transition(workflow_id, "pending", "processing")
                self.tracker.record_transition(workflow_id, "processing", "completed")

        # Analyze patterns
        patterns = self.tracker.analyze_transition_patterns()

        # Check transition frequencies
        assert patterns["pending->processing"]["count"] == 90
        assert patterns["pending->cancelled"]["count"] == 10
        assert patterns["processing->completed"]["count"] == 80
        assert patterns["processing->failed"]["count"] == 10

        # Check probabilities
        assert abs(patterns["processing->completed"]["probability"] - 0.888) < 0.01
        assert abs(patterns["processing->failed"]["probability"] - 0.111) < 0.01


class TestCheckpointMetrics:
    """Test metrics for LangGraph checkpointing operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = CheckpointMetrics()

    def test_checkpoint_save_metrics(self):
        """Test metrics for checkpoint save operations."""
        # Record checkpoint save
        checkpoint_id = self.metrics.record_checkpoint_save(
            workflow_id="wf-123",
            checkpoint_size_bytes=1024 * 10,  # 10KB
            storage_backend="postgres",
            compression_ratio=0.5,
        )

        assert checkpoint_id is not None

        # Simulate save duration
        time.sleep(0.05)

        # Complete save
        save_metrics = self.metrics.complete_checkpoint_save(
            checkpoint_id=checkpoint_id,
            success=True,
        )

        assert save_metrics["success"]
        assert save_metrics["duration_ms"] >= 50
        assert save_metrics["size_bytes"] == 1024 * 10
        assert save_metrics["compression_ratio"] == 0.5

    def test_checkpoint_load_metrics(self):
        """Test metrics for checkpoint load operations."""
        # Record checkpoint load
        load_id = self.metrics.record_checkpoint_load(
            workflow_id="wf-123",
            checkpoint_id="ckpt-456",
            storage_backend="postgres",
        )

        # Simulate load duration
        time.sleep(0.03)

        # Complete load
        load_metrics = self.metrics.complete_checkpoint_load(
            load_id=load_id,
            success=True,
            checkpoint_size_bytes=1024 * 10,
        )

        assert load_metrics["success"]
        assert load_metrics["duration_ms"] >= 30
        assert load_metrics["size_bytes"] == 1024 * 10

    def test_checkpoint_failure_tracking(self):
        """Test tracking checkpoint operation failures."""
        # Record failed save
        save_id = self.metrics.record_checkpoint_save("wf-fail", 1024, "redis")
        save_metrics = self.metrics.complete_checkpoint_save(
            checkpoint_id=save_id,
            success=False,
            error_type="StorageError",
            error_message="Redis connection failed",
        )

        assert not save_metrics["success"]
        assert save_metrics["error_type"] == "StorageError"

        # Record failed load
        load_id = self.metrics.record_checkpoint_load("wf-fail", "ckpt-bad", "redis")
        load_metrics = self.metrics.complete_checkpoint_load(
            load_id=load_id,
            success=False,
            error_type="CorruptedCheckpoint",
        )

        assert not load_metrics["success"]
        assert load_metrics["error_type"] == "CorruptedCheckpoint"

        # Get failure statistics
        stats = self.metrics.get_failure_stats()
        assert stats["save_failures"] == 1
        assert stats["load_failures"] == 1
        assert "StorageError" in stats["save_error_types"]
        assert "CorruptedCheckpoint" in stats["load_error_types"]

    def test_checkpoint_storage_metrics(self):
        """Test metrics for checkpoint storage usage."""
        # Record multiple checkpoints
        for i in range(10):
            self.metrics.record_checkpoint_save(
                workflow_id=f"wf-{i}",
                checkpoint_size_bytes=1024 * (i + 1),  # Increasing sizes
                storage_backend="postgres",
            )

        # Get storage statistics
        storage_stats = self.metrics.get_storage_stats()

        assert storage_stats["total_checkpoints"] == 10
        assert storage_stats["total_size_bytes"] == sum(1024 * (i + 1) for i in range(10))
        assert storage_stats["average_size_bytes"] == storage_stats["total_size_bytes"] / 10
        assert storage_stats["largest_checkpoint_bytes"] == 1024 * 10
        assert storage_stats["smallest_checkpoint_bytes"] == 1024

    def test_checkpoint_retention_metrics(self):
        """Test metrics for checkpoint retention and cleanup."""
        # Record checkpoints with timestamps
        base_time = datetime.now()

        for i in range(20):
            checkpoint_time = base_time - timedelta(hours=i)
            self.metrics.record_checkpoint_with_timestamp(
                workflow_id=f"wf-{i}",
                checkpoint_size_bytes=1024,
                timestamp=checkpoint_time,
            )

        # Perform cleanup (remove checkpoints older than 12 hours)
        cleanup_metrics = self.metrics.cleanup_old_checkpoints(retention_hours=12)

        assert cleanup_metrics["removed_count"] == 8  # Hours 12-19
        assert cleanup_metrics["freed_bytes"] == 1024 * 8
        assert cleanup_metrics["remaining_count"] == 12


class TestMemoryUsageTracker:
    """Test memory usage tracking for LangGraph components."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = MemoryUsageTracker()

    def test_component_memory_tracking(self):
        """Test tracking memory usage by component."""
        # Record memory usage for different components
        self.tracker.record_memory_usage(
            component="state_store",
            bytes_used=1024 * 1024,  # 1MB
            bytes_allocated=2 * 1024 * 1024,  # 2MB allocated,
        )

        self.tracker.record_memory_usage(
            component="message_queue",
            bytes_used=512 * 1024,  # 512KB
            bytes_allocated=1024 * 1024,  # 1MB allocated,
        )

        # Get component statistics
        stats = self.tracker.get_component_stats("state_store")
        assert stats["current_bytes"] == 1024 * 1024
        assert stats["allocated_bytes"] == 2 * 1024 * 1024
        assert stats["usage_ratio"] == 0.5

        # Get total memory usage
        total = self.tracker.get_total_memory_usage()
        assert total["total_used_bytes"] == 1024 * 1024 + 512 * 1024
        assert total["total_allocated_bytes"] == 3 * 1024 * 1024

    def test_memory_growth_tracking(self):
        """Test tracking memory growth over time."""
        component = "growing_component"

        # Simulate memory growth
        for i in range(10):
            self.tracker.record_memory_usage(
                component=component,
                bytes_used=1024 * (i + 1),  # Growing usage,
            )
            time.sleep(0.01)

        # Analyze growth
        growth = self.tracker.analyze_memory_growth(component)

        assert growth["initial_bytes"] == 1024
        assert growth["current_bytes"] == 1024 * 10
        assert growth["growth_bytes"] == 1024 * 9
        assert growth["growth_rate_bytes_per_second"] > 0

    def test_memory_leak_detection(self):
        """Test detecting potential memory leaks."""
        # Simulate potential leak (continuous growth)
        for i in range(20):
            self.tracker.record_memory_usage(
                component="leaky_component",
                bytes_used=1024 * 1024 * i,  # Linear growth,
            )

        # Check for leaks
        leaks = self.tracker.detect_memory_leaks(growth_threshold_mb_per_hour=10)

        assert "leaky_component" in leaks
        assert leaks["leaky_component"]["suspected_leak"]
        assert leaks["leaky_component"]["growth_rate_mb_per_hour"] > 10

    def test_memory_limits_enforcement(self):
        """Test enforcing memory limits for components."""
        # Set memory limits
        self.tracker.set_memory_limit("limited_component", max_bytes=1024 * 1024)

        # Check if within limits
        assert self.tracker.check_memory_limit(
            "limited_component",
            current_bytes=512 * 1024,
        )

        # Check if exceeds limits
        assert not self.tracker.check_memory_limit(
            "limited_component",
            current_bytes=2 * 1024 * 1024,
        )

        # Get limit violations
        violations = self.tracker.get_limit_violations()
        assert len(violations) == 0  # No violations recorded yet

        # Record violation
        self.tracker.record_memory_usage(
            component="limited_component",
            bytes_used=2 * 1024 * 1024,
        )

        violations = self.tracker.get_limit_violations()
        assert "limited_component" in violations
        assert violations["limited_component"]["over_limit_bytes"] == 1024 * 1024


class TestErrorMetricsCollector:
    """Test error metrics collection for LangGraph."""

    def setup_method(self):
        """Set up test fixtures."""
        self.collector = ErrorMetricsCollector()

    def test_error_recording(self):
        """Test recording different types of errors."""
        # Record various errors
        self.collector.record_error(
            error_type="ValidationError",
            error_message="Invalid input format",
            component="input_validator",
            workflow_id="wf-123",
            node_name="validate_node",
            severity="warning",
        )

        self.collector.record_error(
            error_type="NetworkError",
            error_message="Connection timeout",
            component="api_client",
            severity="error",
            retry_count=3,
        )

        # Get error statistics
        stats = self.collector.get_error_stats()

        assert stats["total_errors"] == 2
        assert stats["by_type"]["ValidationError"] == 1
        assert stats["by_type"]["NetworkError"] == 1
        assert stats["by_severity"]["warning"] == 1
        assert stats["by_severity"]["error"] == 1

    def test_error_rate_calculation(self):
        """Test calculating error rates over time."""
        # Record errors over time
        start_time = datetime.now()

        for i in range(20):
            if i % 5 == 0:  # Error every 5th operation
                self.collector.record_error(
                    error_type="ProcessingError",
                    timestamp=start_time + timedelta(seconds=i),
                )

            # Record successful operation
            self.collector.record_success(
                component="processor",
                timestamp=start_time + timedelta(seconds=i),
            )

        # Calculate error rate
        error_rate = self.collector.calculate_error_rate(time_window_seconds=60)

        assert error_rate["error_rate"] == 0.2  # 4 errors out of 20 operations
        assert error_rate["errors_per_minute"] == 4
        assert error_rate["success_rate"] == 0.8

    def test_error_pattern_detection(self):
        """Test detecting patterns in errors."""
        # Record pattern of errors
        for i in range(50):
            if i % 10 < 3:  # Burst pattern
                self.collector.record_error(
                    error_type="BurstError",
                    component="burst_component",
                    timestamp=datetime.now() + timedelta(seconds=i),
                )

        # Detect patterns
        patterns = self.collector.detect_error_patterns()

        assert "burst_pattern" in patterns
        assert patterns["burst_pattern"]["detected"]
        assert patterns["burst_pattern"]["burst_count"] == 5  # 5 bursts

    def test_error_recovery_tracking(self):
        """Test tracking error recovery success."""
        # Record error and recovery attempts
        error_id = self.collector.record_error(
            error_type="RecoverableError",
            component="resilient_component",
        )

        # Record recovery attempts
        self.collector.record_recovery_attempt(error_id, attempt=1, success=False)
        self.collector.record_recovery_attempt(error_id, attempt=2, success=False)
        self.collector.record_recovery_attempt(error_id, attempt=3, success=True)

        # Get recovery statistics
        recovery_stats = self.collector.get_recovery_stats()

        assert recovery_stats["total_recovery_attempts"] == 3
        assert recovery_stats["successful_recoveries"] == 1
        assert recovery_stats["recovery_success_rate"] == 1 / 3
        assert recovery_stats["average_attempts_to_recovery"] == 3


class TestPerformanceAnalyzer:
    """Test performance analysis for LangGraph workflows."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = PerformanceAnalyzer()

    def test_bottleneck_detection(self):
        """Test detecting performance bottlenecks in workflows."""
        # Record node execution times
        workflow_id = "bottleneck-test"

        node_times = {
            "fast_node_1": 50,
            "fast_node_2": 60,
            "slow_node": 500,  # Bottleneck
            "fast_node_3": 40,
        }

        for node, duration in node_times.items():
            self.analyzer.record_node_performance(
                workflow_id=workflow_id,
                node_name=node,
                duration_ms=duration,
            )

        # Detect bottlenecks
        bottlenecks = self.analyzer.detect_bottlenecks(workflow_id)

        assert len(bottlenecks) == 1
        assert bottlenecks[0]["node_name"] == "slow_node"
        assert bottlenecks[0]["duration_ms"] == 500
        assert bottlenecks[0]["percentage_of_total"] > 0.75

    def test_performance_regression_detection(self):
        """Test detecting performance regressions."""
        node_name = "regression_node"

        # Record baseline performance
        for i in range(10):
            self.analyzer.record_node_performance(
                workflow_id=f"baseline-{i}",
                node_name=node_name,
                duration_ms=100 + i,  # ~100ms baseline,
            )

        # Record current performance (degraded)
        for i in range(10):
            self.analyzer.record_node_performance(
                workflow_id=f"current-{i}",
                node_name=node_name,
                duration_ms=200 + i,  # ~200ms current,
            )

        # Detect regression
        regression = self.analyzer.detect_regression(
            node_name=node_name,
            baseline_window_minutes=60,
            threshold_percentage=50,
        )

        assert regression["regression_detected"]
        assert regression["performance_degradation_percentage"] >= 90
        assert regression["baseline_avg_ms"] < regression["current_avg_ms"]

    def test_optimization_recommendations(self):
        """Test generating optimization recommendations."""
        # Record workflow with various issues
        workflow_id = "optimize-me"

        # Slow node
        self.analyzer.record_node_performance(workflow_id, "slow_node", 1000)

        # High memory node
        self.analyzer.record_node_memory(workflow_id, "memory_hog", 100 * 1024 * 1024)

        # Frequently failing node
        for _i in range(10):
            self.analyzer.record_node_failure(workflow_id, "unreliable_node")

        # Get recommendations
        recommendations = self.analyzer.get_optimization_recommendations(workflow_id)

        assert len(recommendations) > 0
        assert any(r["type"] == "performance" for r in recommendations)
        assert any(r["type"] == "memory" for r in recommendations)
        assert any(r["type"] == "reliability" for r in recommendations)

    def test_performance_trends(self):
        """Test analyzing performance trends over time."""
        node_name = "trending_node"
        base_time = datetime.now()

        # Simulate improving performance over time
        for hour in range(24):
            for i in range(10):
                duration = 200 - (hour * 5)  # Gradually improving
                self.analyzer.record_node_performance(
                    workflow_id=f"wf-{hour}-{i}",
                    node_name=node_name,
                    duration_ms=duration,
                    timestamp=base_time + timedelta(hours=hour),
                )

        # Analyze trend
        trend = self.analyzer.analyze_performance_trend(
            node_name=node_name,
            time_window_hours=24,
        )

        assert trend["trend_direction"] == "improving"
        assert trend["improvement_percentage"] > 0
        assert trend["start_avg_ms"] > trend["end_avg_ms"]
