"""

# Constants
MINUTE_SECONDS = 60

DEFAULT_RETRIES = 5
HIGH_CONFIDENCE_THRESHOLD = 0.95

Test suite for ComplianceState Pydantic model following TDD principles.

WRITTEN BEFORE IMPLEMENTATION - DO NOT MODIFY WITHOUT IMPLEMENTATION.
This test suite defines the expected behavior of the ComplianceState model.
"""

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
import uuid
from typing import Dict, List, Optional, Any
from pydantic import ValidationError
import json
from langgraph_agent.models.compliance_state import (
    ComplianceState,
    EvidenceItem,
    Decision,
    CostSnapshot,
    WorkflowStatus,
    ActorType,
    MemoryStore,
    Context,
)

from tests.test_constants import DEFAULT_LIMIT, MAX_RETRIES


class TestComplianceStateInitialization:
    """Test basic state creation and initialization."""

    def test_minimal_state_creation(self):
        """Test creating a state with minimal required fields."""
        minimal_data = {
            "case_id": "test-case-001",
            "actor": "PolicyAuthor",
            "objective": "Generate compliance policy",
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**minimal_data)
        assert state.case_id == "test-case-001"
        assert state.actor == "PolicyAuthor"
        assert state.objective == "Generate compliance policy"
        assert state.evidence == []
        assert state.decisions == []
        assert state.workflow_status == WorkflowStatus.PENDING

    def test_full_state_creation(self):
        """Test creating a state with all fields."""
        full_data = {
            "case_id": "test-case-002",
            "actor": "EvidenceCollector",
            "objective": "Collect evidence for ISO 27001",
            "context": {
                "org_profile": {"name": "TestOrg", "industry": "Finance"},
                "framework": "ISO 27001",
                "obligations": ["Data Protection", "Access Control"],
            },
            "memory": {
                "episodic": ["event-001", "event-002"],
                "semantic": {"policies": ["policy-001"], "evidence": ["evidence-001"]},
            },
            "evidence": [],
            "decisions": [],
            "cost_tracker": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost": 0.0,
                "model": "gpt-4",
            },
            "trace_id": str(uuid4()),
            "workflow_status": "pending",
            "node_execution_times": {},
            "retry_count": 0,
            "error_count": 0,
        }
        state = ComplianceState(**full_data)
        assert state.context.framework == "ISO 27001"
        assert state.memory.episodic == ["event-001", "event-002"]
        assert state.workflow_status == WorkflowStatus.PENDING


class TestActorValidation:
    """Test actor type constraints and validation."""

    def test_valid_actor_types(self):
        """Test all valid actor types are accepted."""
        valid_actors = ["PolicyAuthor", "EvidenceCollector", "RegWatch", "FilingScheduler"]
        for actor in valid_actors:
            data = {
                "case_id": f"test-{actor}",
                "actor": actor,
                "objective": f"Test {actor}",
                "trace_id": str(uuid4()),
            }
            state = ComplianceState(**data)
            assert state.actor == actor

    def test_invalid_actor_type_raises_error(self):
        """Test that invalid actor types raise validation error."""
        data = {
            "case_id": "test-invalid",
            "actor": "InvalidActor",
            "objective": "Test invalid",
            "trace_id": str(uuid4()),
        }
        with pytest.raises(ValidationError):
            state = ComplianceState(**data)

    def test_actor_type_case_sensitive(self):
        """Test that actor validation is case-sensitive."""
        data = {
            "case_id": "test-case",
            "actor": "policyauthor",
            "objective": "Test case sensitivity",
            "trace_id": str(uuid4()),
        }
        with pytest.raises(ValidationError):
            state = ComplianceState(**data)


class TestEvidenceAccumulation:
    """Test evidence items are properly accumulated, not replaced."""

    def test_evidence_initialization_empty(self):
        """Test evidence starts as empty list."""
        data = {
            "case_id": "test-evidence-001",
            "actor": "EvidenceCollector",
            "objective": "Test evidence",
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        assert state.evidence == []
        assert isinstance(state.evidence, list)

    def test_evidence_accumulation_preserves_existing(self):
        """Test that evidence accumulation preserves existing items."""
        initial_evidence = [
            {"id": "ev-001", "type": "document", "content": "Policy doc"},
            {"id": "ev-002", "type": "screenshot", "content": "Dashboard"},
        ]
        new_evidence = [{"id": "ev-003", "type": "log", "content": "Audit log"}]
        data = {
            "case_id": "test-evidence-002",
            "actor": "EvidenceCollector",
            "objective": "Test accumulation",
            "evidence": initial_evidence,
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        for item in new_evidence:
            state.add_evidence(item)
        assert len(state.evidence) == MAX_RETRIES
        assert state.evidence[0].id == "ev-001"
        assert state.evidence[2].id == "ev-003"

    def test_evidence_item_validation(self):
        """Test evidence items must have required fields."""
        invalid_evidence = [{"type": "document"}]
        data = {
            "case_id": "test-evidence-003",
            "actor": "EvidenceCollector",
            "objective": "Test validation",
            "evidence": invalid_evidence,
            "trace_id": str(uuid4()),
        }
        with pytest.raises((ValidationError, ValueError)):
            state = ComplianceState(**data)


class TestCostTracking:
    """Test cost snapshot updates and calculations."""

    def test_cost_tracker_initialization(self):
        """Test cost tracker initializes with defaults."""
        data = {
            "case_id": "test-cost-001",
            "actor": "PolicyAuthor",
            "objective": "Test cost",
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        assert state.cost_tracker.total_tokens == 0
        assert state.cost_tracker.prompt_tokens == 0
        assert state.cost_tracker.completion_tokens == 0
        assert state.cost_tracker.estimated_cost == 0.0

    def test_cost_tracker_update(self):
        """Test cost tracker can be updated with new values."""
        initial_cost = {
            "total_tokens": 100,
            "prompt_tokens": 60,
            "completion_tokens": 40,
            "estimated_cost": 0.01,
            "model": "gpt-4",
        }
        data = {
            "case_id": "test-cost-002",
            "actor": "PolicyAuthor",
            "objective": "Test cost update",
            "cost_tracker": initial_cost,
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        assert state.cost_tracker.total_tokens == DEFAULT_LIMIT
        assert state.cost_tracker.estimated_cost == 0.01

    def test_cost_accumulation(self):
        """Test costs are accumulated, not replaced."""
        from langgraph_agent.graph.reducers import update_cost_tracker

        initial = CostSnapshot(
            total_tokens=100, prompt_tokens=60, completion_tokens=40, estimated_cost=0.001
        )
        additional = CostSnapshot(
            total_tokens=50, prompt_tokens=30, completion_tokens=20, estimated_cost=0.0005
        )
        result = update_cost_tracker(initial, additional)
        assert result.total_tokens == 150
        assert result.prompt_tokens == 90
        assert result.completion_tokens == MINUTE_SECONDS
        assert result.estimated_cost == 0.0015


class TestMemoryPersistence:
    """Test episodic and semantic memory storage."""

    def test_memory_initialization(self):
        """Test memory initializes with proper structure."""
        memory_data = {"episodic": [], "semantic": {}}
        data = {
            "case_id": "test-memory-001",
            "actor": "PolicyAuthor",
            "objective": "Test memory",
            "memory": memory_data,
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        assert hasattr(state.memory, "episodic")
        assert hasattr(state.memory, "semantic")
        assert isinstance(state.memory.episodic, list)
        assert isinstance(state.memory.semantic, dict)

    def test_episodic_memory_append(self):
        """Test episodic memory items can be appended."""
        memory_data = {"episodic": ["event-001"], "semantic": {}}
        data = {
            "case_id": "test-memory-002",
            "actor": "PolicyAuthor",
            "objective": "Test episodic",
            "memory": memory_data,
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        state.memory.episodic.append("event-002")
        assert len(state.memory.episodic) == 2

    def test_semantic_memory_update(self):
        """Test semantic memory can be updated with new keys."""
        memory_data = {"episodic": [], "semantic": {"policies": ["pol-001"]}}
        data = {
            "case_id": "test-memory-003",
            "actor": "PolicyAuthor",
            "objective": "Test semantic",
            "memory": memory_data,
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        state.memory.semantic["evidence"] = ["ev-001"]
        assert "evidence" in state.memory.semantic
        assert len(state.memory.semantic) == 2


class TestDecisionTracking:
    """Test decision audit trail functionality."""

    def test_decisions_initialization(self):
        """Test decisions initialize as empty list."""
        data = {
            "case_id": "test-decision-001",
            "actor": "PolicyAuthor",
            "objective": "Test decisions",
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        assert state.decisions == []
        assert isinstance(state.decisions, list)

    def test_decision_structure(self):
        """Test decision items have required fields."""
        decisions = [
            {
                "id": "dec-001",
                "timestamp": datetime.now().isoformat(),
                "actor": "PolicyAuthor",
                "action": "approve_policy",
                "reasoning": "Policy meets all requirements",
                "confidence": 0.95,
                "alternatives": ["reject", "request_review"],
            }
        ]
        data = {
            "case_id": "test-decision-002",
            "actor": "PolicyAuthor",
            "objective": "Test decision structure",
            "decisions": decisions,
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        assert len(state.decisions) == 1
        assert state.decisions[0].action == "approve_policy"
        assert state.decisions[0].confidence == HIGH_CONFIDENCE_THRESHOLD

    def test_decision_accumulation(self):
        """Test decisions are accumulated in order."""
        initial_decisions = [
            {
                "id": "dec-001",
                "timestamp": datetime.now().isoformat(),
                "actor": "PolicyAuthor",
                "action": "draft_policy",
            }
        ]
        data = {
            "case_id": "test-decision-003",
            "actor": "PolicyAuthor",
            "objective": "Test accumulation",
            "decisions": initial_decisions,
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        new_decision = Decision(
            id="dec-002",
            timestamp=datetime.now().isoformat(),
            actor="PolicyAuthor",
            action="approve_policy",
        )
        state.decisions.append(new_decision)
        assert len(state.decisions) == 2
        assert state.decisions[0].id == "dec-001"
        assert state.decisions[1].id == "dec-002"


class TestStateSerialization:
    """Test JSON serialization/deserialization."""

    def test_state_to_json(self):
        """Test state can be serialized to JSON."""
        data = {
            "case_id": "test-serial-001",
            "actor": "PolicyAuthor",
            "objective": "Test serialization",
            "trace_id": str(uuid4()),
            "context": {"framework": "ISO 27001"},
            "evidence": [{"id": "ev-001", "type": "doc"}],
            "decisions": [],
        }
        state = ComplianceState(**data)
        json_str = state.model_dump_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["case_id"] == "test-serial-001"

    def test_state_from_json(self):
        """Test state can be deserialized from JSON."""
        json_data = {
            "case_id": "test-serial-002",
            "actor": "EvidenceCollector",
            "objective": "Test deserialization",
            "trace_id": str(uuid4()),
            "context": {},
            "memory": {"episodic": [], "semantic": {}},
            "evidence": [],
            "decisions": [],
            "cost_tracker": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost": 0.0,
                "model": "gpt-4",
            },
            "workflow_status": "pending",
            "node_execution_times": {},
            "retry_count": 0,
            "error_count": 0,
        }
        json_str = json.dumps(json_data)
        state = ComplianceState.model_validate_json(json_str)
        assert state.case_id == "test-serial-002"
        assert state.actor == "EvidenceCollector"

    def test_datetime_serialization(self):
        """Test datetime fields serialize properly."""
        data = {
            "case_id": "test-serial-003",
            "actor": "PolicyAuthor",
            "objective": "Test datetime",
            "trace_id": str(uuid4()),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        state = ComplianceState(**data)
        json_str = state.model_dump_json()
        parsed = json.loads(json_str)
        assert "created_at" in parsed
        assert isinstance(parsed["created_at"], str)


class TestTraceIdGeneration:
    """Test unique trace ID creation and propagation."""

    def test_trace_id_required(self):
        """Test trace_id is a required field."""
        data = {"case_id": "test-trace-001", "actor": "PolicyAuthor", "objective": "Test trace"}
        with pytest.raises(ValidationError):
            state = ComplianceState(**data)

    def test_trace_id_format_validation(self):
        """Test trace_id must be valid UUID format."""
        data = {
            "case_id": "test-trace-002",
            "actor": "PolicyAuthor",
            "objective": "Test trace format",
            "trace_id": "invalid-uuid",
        }
        with pytest.raises(ValidationError):
            state = ComplianceState(**data)

    def test_trace_id_uniqueness(self):
        """Test trace_id should be unique per state."""
        trace_id = str(uuid4())
        data1 = {
            "case_id": "test-trace-003",
            "actor": "PolicyAuthor",
            "objective": "Test uniqueness",
            "trace_id": trace_id,
        }
        data2 = {
            "case_id": "test-trace-004",
            "actor": "EvidenceCollector",
            "objective": "Test uniqueness 2",
            "trace_id": trace_id,
        }
        state1 = ComplianceState(**data1)
        state2 = ComplianceState(**data2)
        assert state1.trace_id == state2.trace_id


class TestContextValidation:
    """Test org profile, framework, obligations context."""

    def test_context_structure(self):
        """Test context has expected structure."""
        context = {
            "org_profile": {
                "name": "TestCorp",
                "industry": "Technology",
                "size": "medium",
                "location": "US",
            },
            "framework": "ISO 27001",
            "obligations": ["Data Protection", "Access Control", "Incident Management"],
        }
        data = {
            "case_id": "test-context-001",
            "actor": "PolicyAuthor",
            "objective": "Test context",
            "context": context,
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        assert state.context.org_profile["name"] == "TestCorp"
        assert state.context.framework == "ISO 27001"
        assert len(state.context.obligations) == MAX_RETRIES

    def test_context_optional(self):
        """Test context is optional."""
        data = {
            "case_id": "test-context-002",
            "actor": "PolicyAuthor",
            "objective": "Test optional context",
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        assert state.context is not None

    def test_context_framework_validation(self):
        """Test framework field validation if provided."""
        context = {"framework": "INVALID_FRAMEWORK"}
        data = {
            "case_id": "test-context-003",
            "actor": "PolicyAuthor",
            "objective": "Test framework",
            "context": context,
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)


class TestStateTransitions:
    """Test valid state transition paths."""

    def test_workflow_status_values(self):
        """Test workflow status accepts valid values."""
        valid_statuses = ["pending", "in_progress", "completed", "failed", "cancelled"]
        for status in valid_statuses:
            data = {
                "case_id": f"test-status-{status}",
                "actor": "PolicyAuthor",
                "objective": "Test status",
                "trace_id": str(uuid4()),
                "workflow_status": status,
            }
            state = ComplianceState(**data)
            assert state.workflow_status == status

    def test_invalid_workflow_status(self):
        """Test invalid workflow status raises error."""
        data = {
            "case_id": "test-status-invalid",
            "actor": "PolicyAuthor",
            "objective": "Test invalid status",
            "trace_id": str(uuid4()),
            "workflow_status": "invalid_status",
        }
        with pytest.raises(ValidationError):
            state = ComplianceState(**data)

    def test_state_transition_tracking(self):
        """Test state transitions are tracked properly."""
        data = {
            "case_id": "test-transition-001",
            "actor": "PolicyAuthor",
            "objective": "Test transitions",
            "trace_id": str(uuid4()),
            "workflow_status": "pending",
            "state_history": [],
        }
        state = ComplianceState(**data)
        old_status = state.workflow_status
        state.workflow_status = "in_progress"
        state.state_history.append(
            {
                "from": old_status,
                "to": state.workflow_status,
                "timestamp": datetime.now().isoformat(),
                "actor": state.actor,
            }
        )
        assert len(state.state_history) == 1
        assert state.state_history[0]["from"] == "pending"
        assert state.state_history[0]["to"] == "in_progress"


class TestPerformanceMetrics:
    """Test performance tracking fields."""

    def test_node_execution_times(self):
        """Test node execution times tracking."""
        exec_times = {"policy_generator": 1234, "evidence_collector": 5678, "validator": 910}
        data = {
            "case_id": "test-perf-001",
            "actor": "PolicyAuthor",
            "objective": "Test performance",
            "trace_id": str(uuid4()),
            "node_execution_times": exec_times,
        }
        state = ComplianceState(**data)
        assert state.node_execution_times["policy_generator"] == 1234
        assert len(state.node_execution_times) == MAX_RETRIES

    def test_retry_and_error_counts(self):
        """Test retry and error counter fields."""
        data = {
            "case_id": "test-perf-002",
            "actor": "PolicyAuthor",
            "objective": "Test counters",
            "trace_id": str(uuid4()),
            "retry_count": 2,
            "error_count": 1,
        }
        state = ComplianceState(**data)
        assert state.retry_count == 2
        assert state.error_count == 1

    def test_counter_defaults(self):
        """Test counters default to zero."""
        data = {
            "case_id": "test-perf-003",
            "actor": "PolicyAuthor",
            "objective": "Test defaults",
            "trace_id": str(uuid4()),
        }
        state = ComplianceState(**data)
        assert state.retry_count == 0
        assert state.error_count == 0


class TestStateValidation:
    """Test comprehensive state validation rules."""

    def test_case_id_required(self):
        """Test case_id is required and non-empty."""
        data = {"actor": "PolicyAuthor", "objective": "Test case_id", "trace_id": str(uuid4())}
        with pytest.raises(ValidationError):
            state = ComplianceState(**data)

    def test_objective_required(self):
        """Test objective is required and non-empty."""
        data = {"case_id": "test-val-001", "actor": "PolicyAuthor", "trace_id": str(uuid4())}
        with pytest.raises(ValidationError):
            state = ComplianceState(**data)

    def test_empty_strings_validation(self):
        """Test empty strings are not allowed for required fields."""
        data = {
            "case_id": "",
            "actor": "PolicyAuthor",
            "objective": "Test empty",
            "trace_id": str(uuid4()),
        }
        with pytest.raises(ValidationError):
            state = ComplianceState(**data)

    def test_type_coercion(self):
        """Test appropriate type coercion happens."""
        data = {
            "case_id": "test-val-002",
            "actor": "PolicyAuthor",
            "objective": "Test coercion",
            "trace_id": str(uuid4()),
            "retry_count": "5",
            "error_count": "2",
        }
        state = ComplianceState(**data)
        assert isinstance(state.retry_count, int)
        assert state.retry_count == DEFAULT_RETRIES


class TestLangGraphIntegration:
    """Test integration with LangGraph state management."""

    @pytest.mark.integration
    def test_state_with_langgraph_typeddict(self):
        """Test state works as LangGraph TypedDict."""
        state = ComplianceState(
            case_id="test-123",
            actor="PolicyAuthor",
            objective="Test TypedDict compatibility",
            trace_id=str(uuid.uuid4()),
        )
        state_dict = state.model_dump()
        assert "case_id" in state_dict
        assert "actor" in state_dict
        assert "objective" in state_dict
        assert "trace_id" in state_dict
        assert "context" in state_dict
        assert "evidence" in state_dict
        assert "decisions" in state_dict
        assert "cost_tracker" in state_dict
        assert "workflow_status" in state_dict
        new_state = ComplianceState.model_validate(state_dict)
        assert new_state.case_id == state.case_id
        assert new_state.actor == state.actor

    @pytest.mark.integration
    def test_state_reducer_functions(self):
        """Test reducer functions for state aggregation."""
        from langgraph_agent.graph.reducers import (
            accumulate_evidence,
            merge_decisions,
            update_cost_tracker,
        )

        existing_evidence = [
            {
                "id": "ev1",
                "source": "source1",
                "content": "content1",
                "confidence": 0.9,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
        new_evidence = [
            {
                "id": "ev2",
                "source": "source2",
                "content": "content2",
                "confidence": 0.85,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
        combined = accumulate_evidence(existing_evidence, new_evidence)
        assert len(combined) == 2
        existing_decisions = [
            {
                "id": "dec1",
                "type": "compliance_check",
                "reasoning": "test",
                "confidence": 0.9,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
        new_decisions = [
            {
                "id": "dec2",
                "type": "risk_assessment",
                "reasoning": "test2",
                "confidence": 0.8,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
        merged = merge_decisions(existing_decisions, new_decisions)
        assert len(merged) == 2
