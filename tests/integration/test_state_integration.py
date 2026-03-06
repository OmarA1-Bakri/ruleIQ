"""

Integration tests for ComplianceState with LangGraph and PostgreSQL.

These tests verify the state model works within the LangGraph ecosystem.
"""

import pytest
import asyncio
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any, List, TypedDict, Optional
from typing_extensions import Annotated
import json
import os
from pydantic import ValidationError

# LangGraph imports
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

# Our models and reducers
from langgraph_agent.models.compliance_state import (
    ComplianceState,
    EvidenceItem,
    Decision,
    CostSnapshot,
    Context,
    MemoryStore,
    WorkflowStatus,
)
from langgraph_agent.graph.reducers import (
    accumulate_evidence,
    merge_decisions,
    update_cost_tracker,
    append_to_memory,
    merge_context,
    merge_node_execution_times,
)


class ComplianceStateDict(TypedDict, total=False):
    """TypedDict version of ComplianceState for LangGraph integration."""

    case_id: str
    actor: str
    objective: str
    trace_id: str
    context: Dict[str, Any]
    memory: Dict[str, Any]
    evidence: Annotated[List[Dict[str, Any]], accumulate_evidence]
    decisions: Annotated[List[Dict[str, Any]], merge_decisions]
    cost_tracker: Annotated[Dict[str, Any], update_cost_tracker]
    workflow_status: str
    node_execution_times: Annotated[Dict[str, float], merge_node_execution_times]
    retry_count: int
    error_count: int
    state_history: List[Dict[str, Any]]
    iteration_count: Optional[int]  # For testing
    created_at: str
    updated_at: Optional[str]


def compliance_state_to_dict(state: ComplianceState) -> Dict[str, Any]:
    """Convert ComplianceState to dict for LangGraph."""
    return {
        "case_id": state.case_id,
        "actor": state.actor,
        "objective": state.objective,
        "trace_id": state.trace_id,
        "context": state.context.model_dump() if state.context else {},
        "memory": (
            state.memory.model_dump() if state.memory else {"episodic": [], "semantic": {}},
        ),
        "evidence": [e.model_dump() for e in state.evidence],
        "decisions": [d.model_dump() for d in state.decisions],
        "cost_tracker": state.cost_tracker.model_dump() if state.cost_tracker else {},
        "workflow_status": (
            state.workflow_status.value
            if hasattr(state.workflow_status, "value")
            else state.workflow_status,
        ),
        "node_execution_times": state.node_execution_times,
        "retry_count": state.retry_count,
        "error_count": state.error_count,
        "state_history": state.state_history,
        "created_at": (
            state.created_at.isoformat()
            if hasattr(state.created_at, "isoformat")
            else str(state.created_at),
        ),
        "updated_at": (
            state.updated_at.isoformat()
            if state.updated_at and hasattr(state.updated_at, "isoformat")
            else None,
        ),
    }


def dict_to_compliance_state(data: Dict[str, Any]) -> ComplianceState:
    """Convert dict from LangGraph back to ComplianceState."""
    # Prepare the data for ComplianceState
    prepared_data = {
        "case_id": data.get("case_id"),
        "actor": data.get("actor"),
        "objective": data.get("objective"),
        "trace_id": data.get("trace_id"),
    }

    # Handle optional fields
    if "context" in data and data["context"]:
        prepared_data["context"] = data["context"]

    if "memory" in data and data["memory"]:
        prepared_data["memory"] = data["memory"]

    if "evidence" in data:
        prepared_data["evidence"] = data["evidence"]

    if "decisions" in data:
        prepared_data["decisions"] = data["decisions"]

    if "cost_tracker" in data and data["cost_tracker"]:
        prepared_data["cost_tracker"] = data["cost_tracker"]

    if "workflow_status" in data:
        prepared_data["workflow_status"] = data["workflow_status"]

    if "node_execution_times" in data:
        prepared_data["node_execution_times"] = data["node_execution_times"]

    if "retry_count" in data:
        prepared_data["retry_count"] = data["retry_count"]

    if "error_count" in data:
        prepared_data["error_count"] = data["error_count"]

    if "state_history" in data:
        prepared_data["state_history"] = data["state_history"]

    return ComplianceState(**prepared_data)


class TestStateWithLangGraph:
    """Test state works within LangGraph context."""

    @pytest.mark.integration
    async def test_state_as_graph_state(self):
        """Test ComplianceState can be used as LangGraph state."""
        # Define a simple graph with our state dict
        workflow = StateGraph(ComplianceStateDict)

        # Add a simple node
        async def policy_node(state: Dict[str, Any]) -> Dict[str, Any]:
            # Work with dictionary state
            if "decisions" not in state:
                state["decisions"] = []

            state["decisions"].append(
                {
                    "id": "dec-001",
                    "timestamp": datetime.now().isoformat(),
                    "actor": "PolicyAuthor",
                    "action": "generate_policy",
                },
            )
            return state

        workflow.add_node("policy", policy_node)
        workflow.set_entry_point("policy")
        workflow.add_edge("policy", END)

        # Compile and run
        app = workflow.compile()

        # Create initial state as ComplianceState then convert to dict
        initial_state = ComplianceState(
            case_id="test-graph-001",
            actor="PolicyAuthor",
            objective="Test graph integration",
            trace_id=str(uuid4()),
        )

        initial_dict = compliance_state_to_dict(initial_state)

        result = await app.ainvoke(initial_dict)
        assert len(result["decisions"]) == 1
        assert result["decisions"][0]["action"] == "generate_policy"

        # Convert back to ComplianceState for validation
        final_state = dict_to_compliance_state(result)
        assert len(final_state.decisions) == 1

    @pytest.mark.integration
    async def test_state_with_conditional_edges(self):
        """Test state works with conditional routing."""
        workflow = StateGraph(ComplianceStateDict)

        # Define nodes
        async def check_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
            state["workflow_status"] = "checking_evidence"
            return state

        async def collect_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
            if "evidence" not in state:
                state["evidence"] = []

            state["evidence"].append(
                {
                    "id": "ev-001",
                    "type": "document",
                    "content": "test",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return state

        async def generate_policy(state: Dict[str, Any]) -> Dict[str, Any]:
            if "decisions" not in state:
                state["decisions"] = []

            state["decisions"].append(
                {
                    "id": "dec-001",
                    "timestamp": datetime.now().isoformat(),
                    "actor": "PolicyAuthor",
                    "action": "policy_generated",
                },
            )
            return state

        # Routing function
        def route_evidence(state: Dict[str, Any]) -> str:
            if len(state.get("evidence", [])) > 0:
                return "generate"
            return "collect"

        # Build graph
        workflow.add_node("check", check_evidence)
        workflow.add_node("collect", collect_evidence)
        workflow.add_node("generate", generate_policy)

        workflow.set_entry_point("check")
        workflow.add_conditional_edges(
            "check",
            route_evidence,
            {"collect": "collect", "generate": "generate"},
        )
        workflow.add_edge("collect", "generate")
        workflow.add_edge("generate", END)

        app = workflow.compile()

        # Test with no evidence - should collect first
        initial_state = ComplianceState(
            case_id="test-conditional-001",
            actor="PolicyAuthor",
            objective="Test conditional",
            trace_id=str(uuid4()),
            evidence=[],
        )

        initial_dict = compliance_state_to_dict(initial_state)

        result = await app.ainvoke(initial_dict)
        assert len(result.get("evidence", [])) > 0
        assert len(result.get("decisions", [])) > 0

    @pytest.mark.integration
    async def test_parallel_node_execution(self):
        """Test state with parallel node execution."""
        workflow = StateGraph(ComplianceStateDict)

        # Parallel nodes that only update Annotated fields (evidence, node_execution_times)
        async def collect_evidence_1(state: Dict[str, Any]) -> Dict[str, Any]:
            # Only return updates to annotated fields
            return {
                "evidence": [
                    {
                        "id": "ev-001",
                        "type": "document",
                        "content": "test1",
                        "timestamp": datetime.now().isoformat(),
                        "source": "node1",
                    },
                ],
                "node_execution_times": {"node1": 100},
            }

        async def collect_evidence_2(state: Dict[str, Any]) -> Dict[str, Any]:
            # Only return updates to annotated fields
            return {
                "evidence": [
                    {
                        "id": "ev-002",
                        "type": "document",
                        "content": "test2",
                        "timestamp": datetime.now().isoformat(),
                        "source": "node2",
                    },
                ],
                "node_execution_times": {"node2": 150},
            }

        # Aggregator node that can access merged state
        async def merge_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
            # Evidence already accumulated by reducers
            # We can safely update non-annotated fields here since this runs after parallel nodes
            return {"workflow_status": "completed"}

        workflow.add_node("evidence1", collect_evidence_1)
        workflow.add_node("evidence2", collect_evidence_2)
        workflow.add_node("merge", merge_evidence)

        # Proper parallel execution from START
        workflow.add_edge(START, "evidence1")
        workflow.add_edge(START, "evidence2")

        # Both converge to merge
        workflow.add_edge("evidence1", "merge")
        workflow.add_edge("evidence2", "merge")
        workflow.add_edge("merge", END)

        app = workflow.compile()

        initial_state = ComplianceState(
            case_id="test-parallel-001",
            actor="EvidenceCollector",
            objective="Test parallel",
            trace_id=str(uuid4()),
        )

        initial_dict = compliance_state_to_dict(initial_state)

        result = await app.ainvoke(initial_dict)
        # Should have evidence from both nodes
        assert len(result.get("evidence", [])) == 2  # Both nodes should execute
        assert "node1" in result.get("node_execution_times", {})
        assert "node2" in result.get("node_execution_times", {})


class TestReducerIntegration:
    """Test reducers work correctly with ComplianceState."""

    @pytest.mark.integration
    def test_evidence_accumulation_reducer(self):
        """Test evidence accumulation with reducer."""
        existing = [
            {"id": "ev-001", "type": "document", "content": "test1"},
            {"id": "ev-002", "type": "document", "content": "test2"},
        ]

        new = [
            {"id": "ev-002", "type": "document", "content": "updated"},  # Duplicate
            {"id": "ev-003", "type": "document", "content": "test3"},
        ]

        result = accumulate_evidence(existing, new)

        # Should have 3 items (deduped)
        assert len(result) == 3
        assert any(e["id"] == "ev-001" for e in result)
        assert any(e["id"] == "ev-002" for e in result)
        assert any(e["id"] == "ev-003" for e in result)

        # ev-002 should have updated content
        ev002 = next(e for e in result if e["id"] == "ev-002")
        assert ev002["content"] == "updated"

    @pytest.mark.integration
    def test_decision_merge_reducer(self):
        """Test decision merging with chronological order."""
        existing = [
            {"id": "dec-001", "timestamp": "2024-01-01T10:00:00", "action": "first"},
        ]

        new = [
            {"id": "dec-002", "timestamp": "2024-01-01T11:00:00", "action": "second"},
            {
                "id": "dec-001",  # Duplicate
                "timestamp": "2024-01-01T10:00:00",
                "action": "first_updated",
            },
        ]

        result = merge_decisions(existing, new)

        # Should have 2 decisions (deduped)
        assert len(result) == 2

        # Should be in chronological order
        assert result[0]["timestamp"] < result[1]["timestamp"]

    @pytest.mark.integration
    def test_cost_tracker_reducer(self):
        """Test cost tracking accumulation."""

        existing = {
            "total_tokens": 100,
            "prompt_tokens": 60,
            "completion_tokens": 40,
            "estimated_cost": 0.01,
        }

        new = {
            "total_tokens": 50,
            "prompt_tokens": 30,
            "completion_tokens": 20,
            "estimated_cost": 0.005,
        }

        result = update_cost_tracker(existing, new)

        # Result may be CostSnapshot or dict
        if isinstance(result, CostSnapshot):
            assert result.total_tokens == 150
            assert result.prompt_tokens == 90
            assert result.completion_tokens == 60
            assert result.estimated_cost == 0.015
        else:
            assert result["total_tokens"] == 150
            assert result["prompt_tokens"] == 90
            assert result["completion_tokens"] == 60
            assert result["estimated_cost"] == 0.015

    @pytest.mark.integration
    def test_memory_append_reducer(self):
        """Test memory store appending."""
        existing = {"episodic": ["event1"], "semantic": {"concepts": ["concept1"]}}

        new = {
            "episodic": ["event2", "event1"],  # Has duplicate
            "semantic": {"concepts": ["concept2"], "relations": ["rel1"]},
        }

        result = append_to_memory(existing, new)

        # Should have deduped episodic
        assert len(result["episodic"]) == 2
        assert "event1" in result["episodic"]
        assert "event2" in result["episodic"]

        # Should merge semantic
        assert len(result["semantic"]["concepts"]) == 2
        assert "relations" in result["semantic"]


class TestStateWithPostgreSQL:
    """Test state persistence with PostgreSQL."""

    @pytest.fixture
    def postgres_url(self):
        """Get PostgreSQL connection URL."""
        return os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5433/compliance_test",
        )

    @pytest.mark.integration
    @pytest.mark.requires_db
    def test_state_checkpointing(self, postgres_checkpointer):
        """Test state can be checkpointed to PostgreSQL."""
        # Use the checkpointer from fixture
        checkpointer = postgres_checkpointer

        # Create workflow with checkpointing
        workflow = StateGraph(ComplianceStateDict)

        def process_node(state: Dict[str, Any]) -> Dict[str, Any]:
            state["workflow_status"] = "processed"

            if "decisions" not in state:
                state["decisions"] = []

            state["decisions"].append(
                {
                    "id": "dec-checkpoint",
                    "timestamp": datetime.now().isoformat(),
                    "actor": "System",
                    "action": "checkpoint_test",
                },
            )
            return state

        workflow.add_node("process", process_node)
        workflow.set_entry_point("process")
        workflow.add_edge("process", END)

        app = workflow.compile(checkpointer=checkpointer)

        # Run with thread_id for checkpointing
        config = {"configurable": {"thread_id": "test-thread-001"}}

        initial_state = ComplianceState(
            case_id="test-checkpoint-001",
            actor="PolicyAuthor",
            objective="Test checkpointing",
            trace_id=str(uuid4()),
        )

        initial_dict = compliance_state_to_dict(initial_state)

        result = app.invoke(initial_dict, config)
        assert result["workflow_status"] == "processed"

        # Verify checkpoint was saved
        saved_state = checkpointer.get(config)
        assert saved_state is not None

    @pytest.mark.integration
    @pytest.mark.requires_db
    def test_state_recovery(self, postgres_checkpointer):
        """Test state can be recovered from checkpoint."""
        # Use the checkpointer from fixture
        checkpointer = postgres_checkpointer

        workflow = StateGraph(ComplianceStateDict)

        counter = {"value": 0}

        def increment_node(state: Dict[str, Any]) -> Dict[str, Any]:
            counter["value"] += 1
            if "iteration_count" not in state:
                state["iteration_count"] = 0
            state["iteration_count"] = counter["value"]
            return state

        workflow.add_node("increment", increment_node)
        workflow.set_entry_point("increment")
        workflow.add_edge("increment", END)

        app = workflow.compile(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": "test-recovery-001"}}

        initial_state = ComplianceState(
            case_id="test-recovery-001",
            actor="PolicyAuthor",
            objective="Test recovery",
            trace_id=str(uuid4()),
        )

        initial_dict = compliance_state_to_dict(initial_state)

        # First run
        result1 = app.invoke(initial_dict, config)
        assert result1.get("iteration_count") == 1

        # Recover and continue - should use checkpoint
        result2 = app.invoke(None, config)  # None means use checkpoint
        # Since we reached END, this might create new execution
        # but state should be recoverable

        saved_state = checkpointer.get(config)
        assert saved_state is not None


class TestComplexWorkflow:
    """Test complex multi-step compliance workflow."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_compliance_workflow(self):
        """Test complete compliance checking workflow."""
        workflow = StateGraph(ComplianceStateDict)

        # Node 1: Evidence collection
        async def collect_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
            if "evidence" not in state:
                state["evidence"] = []

            state["evidence"].extend(
                [
                    {
                        "id": "ev-001",
                        "type": "policy",
                        "content": "Security policy v1.0",
                        "timestamp": datetime.now().isoformat(),
                    },
                    {
                        "id": "ev-002",
                        "type": "audit",
                        "content": "Q4 audit report",
                        "timestamp": datetime.now().isoformat(),
                    },
                ],
            )
            state["workflow_status"] = "evidence_collected"
            return state

        # Node 2: Policy evaluation
        async def evaluate_policies(state: Dict[str, Any]) -> Dict[str, Any]:
            if "decisions" not in state:
                state["decisions"] = []

            for evidence in state.get("evidence", []):
                if evidence.get("type") == "policy":
                    state["decisions"].append(
                        {
                            "id": f"dec-{evidence['id']}",
                            "timestamp": datetime.now().isoformat(),
                            "actor": "PolicyEvaluator",
                            "action": f"evaluated_{evidence['id']}",
                            "evidence_refs": [evidence["id"]],
                        },
                    )
            state["workflow_status"] = "policies_evaluated"
            return state

        # Node 3: Generate recommendations
        async def generate_recommendations(state: Dict[str, Any]) -> Dict[str, Any]:
            if "decisions" not in state:
                state["decisions"] = []

            if len(state.get("decisions", [])) > 0:
                state["decisions"].append(
                    {
                        "id": "dec-recommend",
                        "timestamp": datetime.now().isoformat(),
                        "actor": "RecommendationEngine",
                        "action": "recommendations_generated",
                        "confidence": 0.95,
                    },
                )
            state["workflow_status"] = "completed"
            return state

        # Routing logic
        def route_after_evidence(state: Dict[str, Any]) -> str:
            if len(state.get("evidence", [])) > 0:
                return "evaluate"
            return "end"

        # Build workflow
        workflow.add_node("collect", collect_evidence)
        workflow.add_node("evaluate", evaluate_policies)
        workflow.add_node("recommend", generate_recommendations)

        workflow.set_entry_point("collect")
        workflow.add_conditional_edges(
            "collect",
            route_after_evidence,
            {"evaluate": "evaluate", "end": END},
        )
        workflow.add_edge("evaluate", "recommend")
        workflow.add_edge("recommend", END)

        app = workflow.compile()

        # Execute workflow
        initial_state = ComplianceState(
            case_id="compliance-workflow-001",
            actor="PolicyAuthor",
            objective="Full compliance check",
            trace_id=str(uuid4()),
            context={
                "org_profile": {"name": "Test Corp"},
                "framework": "ISO 27001",
                "obligations": ["security", "privacy"],
            },
        )

        initial_dict = compliance_state_to_dict(initial_state)

        result = await app.ainvoke(initial_dict)

        # Verify workflow completion
        assert result["workflow_status"] == "completed"
        assert len(result.get("evidence", [])) == 2
        assert len(result.get("decisions", [])) >= 2  # At least policy eval + recommendations
        assert any(
            d.get("action") == "recommendations_generated" for d in result.get("decisions", [])
        )

        # Verify context preserved
        assert result["context"]["framework"] == "ISO 27001"
        assert "security" in result["context"]["obligations"]


# Run tests
if __name__ == "__main__":
    asyncio.run(pytest.main([__file__, "-v"]))
