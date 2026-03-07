"""

Test suite for LangGraph execution patterns.

This module tests the core execution patterns of LangGraph including:
- Node execution order and sequencing
- Conditional edge evaluation
- Error handling and recovery
- Retry mechanisms

Following TDD principles, these tests are written BEFORE implementation
and will initially fail, defining expected behavior.
"""

import pytest
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, AsyncMock, patch
import asyncio
from datetime import datetime, timedelta
import json

# These imports will be created during implementation
# from app.agents.graph_builder import GraphBuilder
# from app.agents.nodes import ComplianceNode
# from app.agents.edges import ConditionalEdge
# from app.agents.exceptions import NodeExecutionError, GraphTimeoutError

from tests.fixtures.mock_llm import MockLLM, mock_llm_factory
from tests.fixtures.state_fixtures import (
    StateBuilder,
    TestScenario,
    create_test_state,
    create_compliance_context,
)
from tests.fixtures.graph_fixtures import (
    GraphTestHarness,
    create_simple_graph as create_linear_graph,
    create_conditional_graph,
    create_simple_graph as create_parallel_graph,
    create_cycle_graph as create_cyclic_graph,
)


class TestNodeExecutionOrder:
    """Test that nodes execute in the correct order."""

    def test_linear_execution_order(self, graph_test_harness):
        """Test nodes execute sequentially in a linear graph."""
        # Arrange
        graph = create_linear_graph()
        initial_state = create_test_state(TestScenario.SIMPLE_COMPLIANCE)
        expected_order = ["start", "process", "validate", "complete"]

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        graph_test_harness.assert_path(expected_order)
        assert result.workflow_status == "completed"
        assert len(result.execution_history) == 4

        # Verify timestamps are sequential
        timestamps = [entry["timestamp"] for entry in result.execution_history]
        assert all((timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1)))

    def test_parallel_execution_order(self, graph_test_harness):
        """Test parallel nodes can execute simultaneously."""
        # Arrange
        graph = create_parallel_graph()
        initial_state = create_test_state(TestScenario.MULTI_OBLIGATION)

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        # Parallel nodes should have overlapping execution times
        parallel_nodes = [
            "check_obligation_1",
            "check_obligation_2",
            "check_obligation_3",
        ]
        executions = graph_test_harness.get_node_executions(parallel_nodes)

        # At least two should have overlapping times
        overlaps = 0
        for i in range(len(executions)):
            for j in range(i + 1, len(executions)):
                if self._execution_overlaps(executions[i], executions[j]):
                    overlaps += 1
        assert overlaps >= 1, "Parallel nodes should execute simultaneously"

    def test_cyclic_execution_with_limit(self, graph_test_harness):
        """Test cyclic graphs respect iteration limits."""
        # Arrange
        graph = create_cyclic_graph(max_iterations=3)
        initial_state = create_test_state(TestScenario.WITH_RETRY)

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        retry_node_count = graph_test_harness.count_node_executions("retry_analysis")
        assert retry_node_count <= 3, "Should not exceed max iterations"
        assert result.retry_count == 3

    def test_execution_order_with_skipped_nodes(self, graph_test_harness):
        """Test execution order when nodes are conditionally skipped."""
        # Arrange
        graph = create_conditional_graph()
        initial_state = create_test_state(TestScenario.WITH_EXEMPTION)
        initial_state.has_exemption = True

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        graph_test_harness.assert_node_not_called("detailed_analysis")
        graph_test_harness.assert_node_called("exemption_handler")
        assert "exemption_applied" in result.metadata

    def _execution_overlaps(self, exec1: Dict, exec2: Dict) -> bool:
        """Check if two executions overlap in time."""
        start1, end1 = exec1["start_time"], exec1["end_time"]
        start2, end2 = exec2["start_time"], exec2["end_time"]
        return start1 < end2 and start2 < end1


class TestConditionalEdges:
    """Test conditional edge evaluation and routing."""

    def test_simple_conditional_routing(self, graph_test_harness):
        """Test basic if-then-else routing."""
        # Arrange
        graph = create_conditional_graph()
        initial_state = create_test_state(TestScenario.SIMPLE_COMPLIANCE)
        initial_state.confidence_score = 0.8  # High confidence

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        graph_test_harness.assert_node_called("high_confidence_path")
        graph_test_harness.assert_node_not_called("low_confidence_path")
        assert not result.review_required

    def test_multi_branch_conditional(self, graph_test_harness):
        """Test routing with multiple conditional branches."""
        # Arrange
        test_cases = [
            (0.9, "high_confidence_path"),
            (0.5, "medium_confidence_path"),
            (0.2, "low_confidence_path"),
            (0.0, "manual_review_path"),
        ]

        for confidence, expected_path in test_cases:
            graph = create_conditional_graph()
            initial_state = create_test_state(TestScenario.SIMPLE_COMPLIANCE)
            initial_state.confidence_score = confidence

            # Act
            result = graph_test_harness.execute(graph, initial_state)

            # Assert
            graph_test_harness.assert_node_called(expected_path)
            assert result.confidence_path == expected_path

    def test_conditional_edge_with_state_mutation(self, graph_test_harness):
        """Test conditional edges that depend on state mutations."""
        # Arrange
        graph = create_conditional_graph()
        initial_state = create_test_state(TestScenario.PROGRESSIVE_COMPLIANCE)

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        # State should be modified during execution affecting routing
        assert result.phase_completed == ["phase_1", "phase_2", "phase_3"]
        graph_test_harness.assert_path_contains_sequence(
            [
                "evaluate_phase_1",
                "execute_phase_1",
                "evaluate_phase_2",
                "execute_phase_2",
            ],
        )

    def test_conditional_edge_with_external_data(self, graph_test_harness, mocker):
        """Test conditional routing based on external API calls."""
        # Arrange
        mock_api = mocker.patch("app.agents.edges.check_compliance_api")
        mock_api.return_value = {"status": "requires_review", "reason": "high_risk"}

        graph = create_conditional_graph()
        initial_state = create_test_state(TestScenario.WITH_EXTERNAL_CHECK)

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        mock_api.assert_called_once()
        graph_test_harness.assert_node_called("manual_review_required")
        assert result.external_check_result == "requires_review"

    def test_conditional_edge_error_handling(self, graph_test_harness):
        """Test behavior when conditional edge evaluation fails."""
        # Arrange
        graph = create_conditional_graph()
        initial_state = create_test_state(TestScenario.INVALID_STATE)
        initial_state.confidence_score = None  # Will cause evaluation error

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        graph_test_harness.assert_node_called("error_handler")
        assert result.had_routing_error
        assert "fallback_path" in result.execution_history


class TestErrorHandling:
    """Test error handling and recovery mechanisms."""

    def test_node_execution_error_recovery(self, graph_test_harness):
        """Test recovery from node execution errors."""
        # Arrange
        graph = create_linear_graph()
        initial_state = create_test_state(TestScenario.WITH_ERROR)

        # Configure node to fail
        graph_test_harness.configure_node_to_fail("process", times=1)

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        assert result.had_errors
        assert len(result.errors) == 1
        assert result.errors[0]["node"] == "process"
        assert result.workflow_status == "completed_with_errors"

    def test_timeout_error_handling(self, graph_test_harness):
        """Test handling of node execution timeouts."""
        # Arrange
        graph = create_linear_graph()
        initial_state = create_test_state(TestScenario.SIMPLE_COMPLIANCE)

        # Configure node to timeout
        graph_test_harness.configure_node_timeout("validate", timeout_ms=100)

        # Act
        with pytest.raises(GraphTimeoutError) as exc_info:
            result = graph_test_harness.execute(graph, initial_state, timeout=5)

        # Assert
        assert "validate" in str(exc_info.value)
        assert exc_info.value.node_name == "validate"
        assert exc_info.value.timeout_ms == 100

    def test_cascading_error_handling(self, graph_test_harness):
        """Test handling of errors that cascade through the graph."""
        # Arrange
        graph = create_parallel_graph()
        initial_state = create_test_state(TestScenario.WITH_ERROR)

        # Configure multiple nodes to fail
        graph_test_harness.configure_node_to_fail("check_obligation_1")
        graph_test_harness.configure_node_to_fail("check_obligation_2")

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        assert result.had_errors
        assert len(result.errors) == 2
        assert result.partial_results_available
        assert "check_obligation_3" in [r["node"] for r in result.successful_nodes]

    def test_error_handler_node_invocation(self, graph_test_harness):
        """Test that error handler nodes are properly invoked."""
        # Arrange
        graph = create_conditional_graph()
        initial_state = create_test_state(TestScenario.WITH_ERROR)

        # Configure main path to fail
        graph_test_harness.configure_node_to_fail("process_compliance")

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        graph_test_harness.assert_node_called("error_handler")
        assert result.error_handled
        assert result.recovery_action == "manual_intervention_required"

    def test_validation_error_handling(self, graph_test_harness):
        """Test handling of state validation errors."""
        # Arrange
        graph = create_linear_graph()
        initial_state = create_test_state(TestScenario.INVALID_STATE)
        initial_state.company_id = None  # Invalid state

        # Act
        with pytest.raises(ValidationError) as exc_info:
            result = graph_test_harness.execute(graph, initial_state)

        # Assert
        assert "company_id" in str(exc_info.value)
        assert exc_info.value.validation_errors["company_id"] == "required field"


class TestRetryMechanisms:
    """Test retry mechanisms and backoff strategies."""

    def test_simple_retry_on_failure(self, graph_test_harness):
        """Test basic retry on node failure."""
        # Arrange
        graph = create_linear_graph()
        initial_state = create_test_state(TestScenario.WITH_RETRY)

        # Configure node to fail twice then succeed
        graph_test_harness.configure_node_to_fail("process", times=2)

        # Act
        result = graph_test_harness.execute(graph, initial_state, max_retries=3)

        # Assert
        assert result.workflow_status == "completed"
        assert result.retry_count == 2
        graph_test_harness.assert_node_called("process", times=3)

    def test_exponential_backoff_retry(self, graph_test_harness):
        """Test exponential backoff between retries."""
        # Arrange
        graph = create_linear_graph()
        initial_state = create_test_state(TestScenario.WITH_RETRY)

        # Configure node to fail with tracking of retry timing
        graph_test_harness.configure_node_to_fail("process", times=3)
        graph_test_harness.enable_timing_tracking()

        # Act
        result = graph_test_harness.execute(
            graph,
            initial_state,
            max_retries=4,
            backoff_strategy="exponential",
        )

        # Assert
        retry_delays = graph_test_harness.get_retry_delays("process")
        assert len(retry_delays) == 3
        # Each delay should be approximately double the previous
        assert retry_delays[1] >= retry_delays[0] * 1.8
        assert retry_delays[2] >= retry_delays[1] * 1.8

    def test_retry_with_jitter(self, graph_test_harness):
        """Test retry with jitter to prevent thundering herd."""
        # Arrange
        graph = create_linear_graph()
        initial_state = create_test_state(TestScenario.WITH_RETRY)

        # Run multiple executions with same failure pattern
        graph_test_harness.configure_node_to_fail("process", times=2)

        retry_times = []
        for _ in range(10):
            graph_test_harness.reset()
            graph_test_harness.enable_timing_tracking()
            result = graph_test_harness.execute(
                graph,
                initial_state,
                max_retries=3,
                backoff_strategy="exponential_with_jitter",
            )
            retry_times.append(graph_test_harness.get_retry_delays("process")[0])

        # Assert - retry times should vary due to jitter
        assert len(set(retry_times)) > 5, "Jitter should create variation in retry delays"
        assert max(retry_times) - min(retry_times) > 0.1  # At least 100ms variation

    def test_retry_budget_exhaustion(self, graph_test_harness):
        """Test behavior when retry budget is exhausted."""
        # Arrange
        graph = create_linear_graph()
        initial_state = create_test_state(TestScenario.WITH_RETRY)

        # Configure node to always fail
        graph_test_harness.configure_node_to_fail("process", times=10)

        # Act
        result = graph_test_harness.execute(graph, initial_state, max_retries=3)

        # Assert
        assert result.workflow_status == "failed"
        assert result.retry_count == 3
        assert result.failure_reason == "max_retries_exceeded"
        graph_test_harness.assert_node_called("process", times=4)  # Initial + 3 retries

    def test_selective_retry_by_error_type(self, graph_test_harness):
        """Test that only certain error types trigger retries."""
        # Arrange
        graph = create_linear_graph()
        initial_state = create_test_state(TestScenario.WITH_ERROR)

        # Test different error types
        test_cases = [
            ("NetworkError", True, 3),  # Should retry
            ("ValidationError", False, 1),  # Should not retry
            ("RateLimitError", True, 3),  # Should retry
            ("AuthenticationError", False, 1),  # Should not retry,
        ]

        for error_type, should_retry, expected_calls in test_cases:
            graph_test_harness.reset()
            graph_test_harness.configure_node_to_raise("process", error_type)

            # Act
            result = graph_test_harness.execute(graph, initial_state, max_retries=3)

            # Assert
            graph_test_harness.assert_node_called("process", times=expected_calls)
            if should_retry:
                assert result.retry_count > 0
            else:
                assert result.retry_count == 0

    def test_retry_with_state_reset(self, graph_test_harness):
        """Test retry mechanism with partial state reset."""
        # Arrange
        graph = create_conditional_graph()
        initial_state = create_test_state(TestScenario.WITH_RETRY)

        # Configure node to fail and track state changes
        graph_test_harness.configure_node_to_fail("analyze_compliance", times=2)
        graph_test_harness.track_state_changes()

        # Act
        result = graph_test_harness.execute(
            graph,
            initial_state,
            max_retries=3,
            reset_on_retry=["intermediate_results", "confidence_score"],
        )

        # Assert
        state_snapshots = graph_test_harness.get_state_snapshots("analyze_compliance")

        # Verify state was reset between retries
        assert state_snapshots[1].intermediate_results == []
        assert state_snapshots[1].confidence_score == 0.0

        # But other fields preserved
        assert state_snapshots[1].company_id == initial_state.company_id
        assert state_snapshots[1].workflow_id == initial_state.workflow_id


class TestGraphIntegration:
    """Integration tests for complete graph execution scenarios."""

    @pytest.mark.asyncio
    async def test_full_compliance_workflow(self, graph_test_harness):
        """Test complete compliance checking workflow end-to-end."""
        # Arrange
        graph = create_conditional_graph()
        initial_state = create_test_state(TestScenario.FULL_COMPLIANCE_CHECK)

        # Mock external services
        graph_test_harness.mock_external_service(
            "regulation_api",
            {
                "obligations": ["SOC2", "ISO27001", "GDPR"],
                "deadlines": ["2024-03-01", "2024-06-01", "2024-09-01"],
            },
        )

        # Act
        result = await graph_test_harness.execute_async(graph, initial_state)

        # Assert
        assert result.workflow_status == "completed"
        assert len(result.obligations_checked) == 3
        assert all(ob["status"] == "compliant" for ob in result.obligations_checked)
        assert result.compliance_report_generated

    @pytest.mark.asyncio
    async def test_concurrent_graph_executions(self, graph_test_harness):
        """Test multiple graphs executing concurrently."""
        # Arrange
        graphs = [create_linear_graph() for _ in range(5)]
        states = [
            create_test_state(TestScenario.SIMPLE_COMPLIANCE, company_id=f"company_{i}")
            for i in range(5)
        ]

        # Act
        tasks = [
            graph_test_harness.execute_async(graph, state) for graph, state in zip(graphs, states)
        ]
        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == 5
        assert all(r.workflow_status == "completed" for r in results)
        # Each should have unique execution ID
        execution_ids = [r.execution_id for r in results]
        assert len(set(execution_ids)) == 5

    def test_graph_with_checkpoint_recovery(self, graph_test_harness, tmp_path):
        """Test graph recovery from checkpointed state."""
        # Arrange
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()

        graph = create_linear_graph()
        initial_state = create_test_state(TestScenario.WITH_CHECKPOINT)

        # Configure checkpoint after second node
        graph_test_harness.enable_checkpointing(checkpoint_dir)
        graph_test_harness.configure_checkpoint_after("process")

        # Simulate failure after checkpoint
        graph_test_harness.configure_node_to_fail("validate", times=1, permanent=True)

        # Act - First execution (will fail)
        result1 = graph_test_harness.execute(graph, initial_state)
        assert result1.workflow_status == "failed"

        # Act - Resume from checkpoint
        graph_test_harness.reset_failures()
        result2 = graph_test_harness.resume_from_checkpoint(
            graph,
            checkpoint_dir / f"{initial_state.workflow_id}.checkpoint",
        )

        # Assert
        assert result2.workflow_status == "completed"
        assert result2.resumed_from_checkpoint
        # Should not re-execute nodes before checkpoint
        graph_test_harness.assert_node_not_called("start", context="resume")
        graph_test_harness.assert_node_not_called("process", context="resume")

    def test_graph_observability_metrics(self, graph_test_harness):
        """Test that graphs emit proper observability metrics."""
        # Arrange
        graph = create_conditional_graph()
        initial_state = create_test_state(TestScenario.SIMPLE_COMPLIANCE)

        # Enable metrics collection
        graph_test_harness.enable_metrics_collection()

        # Act
        result = graph_test_harness.execute(graph, initial_state)

        # Assert
        metrics = graph_test_harness.get_collected_metrics()

        assert "graph_execution_duration_ms" in metrics
        assert "node_execution_count" in metrics
        assert "edge_traversal_count" in metrics
        assert "state_size_bytes" in metrics
        assert "llm_token_usage" in metrics

        # Verify metric values are reasonable
        assert metrics["graph_execution_duration_ms"] > 0
        assert metrics["node_execution_count"] >= 4
        assert metrics["state_size_bytes"] > 100


# Fixtures for graph testing


@pytest.fixture
def graph_test_harness():
    """Provide a fresh graph test harness for each test."""
    return GraphTestHarness()


@pytest.fixture
def mock_regulation_api(mocker):
    """Mock external regulation API."""
    mock = mocker.patch("app.agents.external.regulation_api")
    mock.get_obligations.return_value = ["SOC2", "ISO27001"]
    mock.check_compliance.return_value = {"status": "compliant"}
    return mock


@pytest.fixture
def async_graph_test_harness():
    """Provide async-capable graph test harness."""
    harness = GraphTestHarness()
    harness.enable_async_mode()
    return harness


# Test data generators


def generate_test_graphs(count: int = 5) -> List[Any]:
    """Generate multiple test graphs with varying complexity."""
    graphs = []
    for i in range(count):
        if i % 3 == 0:
            graphs.append(create_linear_graph())
        elif i % 3 == 1:
            graphs.append(create_conditional_graph())
        else:
            graphs.append(create_parallel_graph())
    return graphs


def generate_error_scenarios() -> List[Dict[str, Any]]:
    """Generate various error scenarios for testing."""
    return [
        {"type": "NetworkError", "retryable": True, "message": "Connection timeout"},
        {"type": "ValidationError", "retryable": False, "message": "Invalid state"},
        {
            "type": "RateLimitError",
            "retryable": True,
            "message": "API rate limit exceeded",
        },
        {
            "type": "AuthenticationError",
            "retryable": False,
            "message": "Invalid credentials",
        },
        {"type": "TimeoutError", "retryable": True, "message": "Operation timeout"},
    ]
