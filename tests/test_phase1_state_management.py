"""

# Constants
DEFAULT_TIMEOUT = 30.0

DEFAULT_RETRIES = 5

Test suite for Phase 1: Enhanced state management with TypedDict and reducers.

This test suite validates:
- Custom reducer functions
- State aggregation
- Error accumulation
- Tool output merging
- Performance tracking
"""

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from langgraph_agent.graph.enhanced_state import (
    EnhancedComplianceState,
    WorkflowStatus,
    create_enhanced_initial_state,
    merge_tool_outputs,
    accumulate_errors,
    merge_compliance_data,
    increment_counter,
    update_metadata,
    StateTransition,
    StateAggregator,
)
from langgraph_agent.graph.enhanced_app import EnhancedComplianceGraph

from tests.test_constants import MAX_RETRIES


class TestStateReducers:
    """Test custom reducer functions."""

    def test_merge_tool_outputs(self):
        """Test tool output merging with history preservation."""
        existing = {"tool1": "result1", "tool2": "result2"}
        new = {"tool2": "updated_result2", "tool3": "result3"}
        merged = merge_tool_outputs(existing, new)
        assert "tool2_history" in merged
        assert len(merged["tool2_history"]) == 1
        assert merged["tool2_history"][0]["value"] == "result2"
        assert merged["tool2"] == "updated_result2"
        assert merged["tool3"] == "result3"
        assert "tool3_timestamp" in merged

    def test_accumulate_errors_with_limit(self):
        """Test error accumulation with maximum limit."""
        existing = [{"error": f"error_{i}"} for i in range(8)]
        new = [{"error": "error_9"}, {"error": "error_10"}, {"error": "error_11"}]
        accumulated = accumulate_errors(existing, new)
        assert len(accumulated) == 10
        assert accumulated[0]["error"] == "error_1"
        assert accumulated[-1]["error"] == "error_11"

    def test_merge_compliance_data(self):
        """Test compliance data merging with deduplication."""
        existing = {
            "frameworks": ["GDPR", "HIPAA"],
            "obligations": [
                {"id": "ob1", "title": "Obligation 1"},
                {"id": "ob2", "title": "Obligation 2"},
            ],
            "evidence": [{"hash": "hash1", "data": "evidence1"}],
        }
        new = {
            "frameworks": ["GDPR", "SOX"],
            "obligations": [
                {"id": "ob2", "title": "Updated Obligation 2"},
                {"id": "ob3", "title": "Obligation 3"},
            ],
            "evidence": [
                {"hash": "hash1", "data": "evidence1"},
                {"hash": "hash2", "data": "evidence2"},
            ],
        }
        merged = merge_compliance_data(existing, new)
        assert len(merged["frameworks"]) == MAX_RETRIES
        assert set(merged["frameworks"]) == {"GDPR", "HIPAA", "SOX"}
        assert len(merged["obligations"]) == MAX_RETRIES
        ob2 = next(o for o in merged["obligations"] if o["id"] == "ob2")
        assert ob2["title"] == "Updated Obligation 2"
        assert len(merged["evidence"]) == 2

    def test_increment_counter(self):
        """Test simple counter increment."""
        assert increment_counter(5, 1) == 6
        assert increment_counter(0, 10) == 10

    def test_update_metadata_with_history(self):
        """Test metadata updates with change tracking."""
        existing = {"version": "1.0.0", "status": "active", "update_count": 5}
        new = {"version": "1.1.0", "status": "inactive"}
        updated = update_metadata(existing, new)
        assert updated["version"] == "1.1.0"
        assert updated["status"] == "inactive"
        assert updated["update_count"] == 6
        assert "change_history" in updated
        assert len(updated["change_history"]) == 1
        changes = updated["change_history"][0]["changes"]
        assert changes["version"]["from"] == "1.0.0"
        assert changes["version"]["to"] == "1.1.0"


class TestStateTransition:
    """Test state transition validation and recording."""

    def test_validate_transition_limits(self):
        """Test transition validation with limits."""
        state = create_enhanced_initial_state(
            session_id="test",
            company_id=uuid4(),
            initial_message="Test",
            max_turns=5,
            max_retries=3,
        )
        validator = StateTransition()
        assert validator.validate_transition(state, "node1", "node2") is True
        state["turn_count"] = 5
        assert validator.validate_transition(state, "node1", "node2") is False
        state["turn_count"] = 2
        state["error_count"] = 3
        assert validator.validate_transition(state, "node1", "node2") is False
        state["error_count"] = 1
        state["should_continue"] = False
        assert validator.validate_transition(state, "node1", "node2") is False

    def test_record_transition(self):
        """Test recording state transitions."""
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        transition = StateTransition()
        state = transition.record_transition(state, "router", "analyzer", 150)
        assert "router" in state["visited_nodes"]
        assert state["current_node"] == "analyzer"
        assert state["node_latencies"]["router"] == 150
        assert state["total_latency_ms"] == 150
        assert state["workflow_status"] == WorkflowStatus.IN_PROGRESS
        state = transition.record_transition(state, "analyzer", "END", 200)
        assert state["workflow_status"] == WorkflowStatus.COMPLETED
        assert state["end_time"] is not None
        assert state["total_latency_ms"] == 350


class TestStateAggregator:
    """Test state aggregation utilities."""

    def test_get_conversation_summary(self):
        """Test conversation summary extraction."""
        state = create_enhanced_initial_state(
            session_id="test-session", company_id=uuid4(), initial_message="Test message"
        )
        state["turn_count"] = 5
        state["questions_asked"] = ["Q1", "Q2", "Q3"]
        state["questions_answered"] = 2
        state["assessment_phase"] = "discovery"
        aggregator = StateAggregator()
        summary = aggregator.get_conversation_summary(state)
        assert summary["session_id"] == "test-session"
        assert summary["message_count"] == 1
        assert summary["turn_count"] == DEFAULT_RETRIES
        assert summary["questions_asked"] == MAX_RETRIES
        assert summary["questions_answered"] == 2
        assert summary["current_phase"] == "discovery"

    def test_get_compliance_summary(self):
        """Test compliance data summary."""
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["compliance_data"] = {
            "frameworks": ["GDPR", "HIPAA", "SOX"],
            "obligations": [{"id": "ob1"}, {"id": "ob2"}],
            "evidence": [{"id": "ev1"}],
            "last_updated": "2024-01-01T00:00:00",
        }
        aggregator = StateAggregator()
        summary = aggregator.get_compliance_summary(state)
        assert summary["frameworks_identified"] == MAX_RETRIES
        assert summary["obligations_found"] == 2
        assert summary["evidence_collected"] == 1
        assert summary["last_updated"] == "2024-01-01T00:00:00"

    def test_get_performance_metrics(self):
        """Test performance metrics extraction."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(seconds=30)
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["start_time"] = start
        state["end_time"] = end
        state["total_latency_ms"] = 1500
        state["tool_call_count"] = 5
        state["error_count"] = 1
        state["retry_count"] = 2
        state["visited_nodes"] = ["router", "analyzer", "collector"]
        state["token_usage"] = {"input": 100, "output": 50, "total": 150}
        state["estimated_cost"] = 0.0015
        aggregator = StateAggregator()
        metrics = aggregator.get_performance_metrics(state)
        assert metrics["total_latency_ms"] == 1500
        assert metrics["duration_seconds"] == DEFAULT_TIMEOUT
        assert metrics["tool_calls"] == DEFAULT_RETRIES
        assert metrics["errors"] == 1
        assert metrics["retries"] == 2
        assert metrics["nodes_visited"] == MAX_RETRIES
        assert metrics["token_usage"]["total"] == 150
        assert metrics["estimated_cost"] == 0.0015


@pytest.mark.asyncio
class TestEnhancedComplianceGraph:
    """Test the enhanced compliance graph."""

    async def test_graph_initialization(self):
        """Test graph initialization and structure."""
        graph = await EnhancedComplianceGraph.create()
        assert graph.graph is not None
        assert graph.checkpointer is not None
        assert graph.state_transition is not None
        assert graph.state_aggregator is not None

    async def test_graph_execution_simple(self):
        """Test simple graph execution flow."""
        graph = await EnhancedComplianceGraph.create()
        session_id = str(uuid4())
        company_id = uuid4()
        user_input = "I need help with GDPR compliance"
        events = []
        async for event in graph.run(
            session_id=session_id, company_id=company_id, user_input=user_input
        ):
            events.append(event)
            if len(events) > DEFAULT_RETRIES:
                break
        assert len(events) > 0
        event_types = [e.get("type") for e in events if "type" in e]
        assert any(t in ["summary", "error"] for t in event_types)

    async def test_error_handling(self):
        """Test error handling in graph execution."""
        graph = await EnhancedComplianceGraph.create()
        state = create_enhanced_initial_state(
            session_id="error-test", company_id=uuid4(), initial_message="Test", max_retries=2
        )
        state["error_count"] = 2
        state["errors"] = [{"error": "Test error 1"}, {"error": "Test error 2"}]
        updated_state = await graph._error_handler_node(state)
        assert updated_state["retry_count"] == 1
        assert updated_state["should_continue"] is True
        updated_state["error_count"] = 3
        updated_state = await graph._error_handler_node(updated_state)
        assert updated_state["retry_count"] == 2
        assert updated_state["should_continue"] is True
        updated_state["error_count"] = 4
        updated_state = await graph._error_handler_node(updated_state)
        assert updated_state["workflow_status"] == WorkflowStatus.FAILED
        assert updated_state["should_continue"] is False

    async def test_router_decision_logic(self):
        """Test router node decision logic."""
        graph = await EnhancedComplianceGraph.create()
        state = create_enhanced_initial_state(
            session_id="router-test", company_id=uuid4(), initial_message="Tell me about compliance"
        )
        updated_state = await graph._router_node(state)
        assert updated_state["next_node"] in [
            "profile",
            "compliance",
            "evidence",
            "response",
            "error",
            "end",
        ]
        assert "router" in updated_state["visited_nodes"]

    async def test_profile_builder(self):
        """Test profile builder node."""
        graph = await EnhancedComplianceGraph.create()
        state = create_enhanced_initial_state(
            session_id="profile-test",
            company_id=uuid4(),
            initial_message="We are a healthcare startup in California",
        )
        updated_state = await graph._profile_builder_node(state)
        assert "business_profile" in updated_state
        assert updated_state["business_profile"].get("industry") == "healthcare"
        assert "profile_builder" in updated_state["node_latencies"]

    async def test_compliance_analyzer(self):
        """Test compliance analyzer node."""
        graph = await EnhancedComplianceGraph.create()
        state = create_enhanced_initial_state(
            session_id="compliance-test", company_id=uuid4(), initial_message="Analyze compliance"
        )
        state["business_profile"] = {"industry": "healthcare", "location": "California"}
        updated_state = await graph._compliance_analyzer_node(state)
        assert "HIPAA" in updated_state["compliance_data"]["frameworks"]
        assert len(updated_state["compliance_data"]["obligations"]) > 0
        assert updated_state["token_usage"]["total"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
