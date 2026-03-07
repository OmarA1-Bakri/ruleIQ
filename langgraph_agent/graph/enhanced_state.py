"""

Enhanced state management for LangGraph with proper TypedDict and Annotated reducers.

Phase 1 Implementation: Proper state management with reducers for aggregating data.
This module provides enhanced state definitions with custom reducers for:
- Message aggregation with deduplication
- Tool output merging
- Error accumulation with limits
- Metadata updates with timestamps
"""

from typing import Dict, List, Optional, Any, TypedDict, Annotated, Union
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum

from langgraph.graph import add_messages


# Custom reducer functions for state management
def merge_tool_outputs(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge tool outputs, preserving history and avoiding overwrites.

    Args:
        existing: Current tool outputs in state
        new: New tool outputs to merge

    Returns:
        Merged tool outputs with timestamped history
    """
    merged = existing.copy()

    for key, value in new.items():
        if key in merged:
            # Create history for existing values
            if not key.endswith("_history"):
                history_key = f"{key}_history"
                if history_key not in merged:
                    merged[history_key] = []

                # Add previous value to history with timestamp
                merged[history_key].append(
                    {
                        "value": merged[key],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

        # Update with new value
        merged[key] = value
        merged[f"{key}_timestamp"] = datetime.now(timezone.utc).isoformat()

    return merged


def accumulate_errors(existing: List[Dict], new: Union[Dict, List[Dict]]) -> List[Dict]:
    """
    Accumulate errors with a maximum limit to prevent memory issues.

    Args:
        existing: Current error list
        new: New error(s) to add

    Returns:
        Updated error list with newest errors retained (max 10)
    """
    max_errors = 10  # Fixed limit

    if isinstance(new, dict):
        new = [new]

    combined = existing + new

    # Keep only the most recent errors if we exceed the limit
    if len(combined) > max_errors:
        return combined[-max_errors:]

    return combined


def merge_compliance_data(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge compliance-specific data structures intelligently.

    Args:
        existing: Current compliance data
        new: New compliance data to merge

    Returns:
        Merged compliance data with proper deduplication
    """
    merged = existing.copy()

    for key, value in new.items():
        if key == "frameworks":
            # Deduplicate frameworks
            existing_frameworks = set(merged.get("frameworks", []))
            new_frameworks = set(value) if isinstance(value, list) else {value}
            merged["frameworks"] = list(existing_frameworks | new_frameworks)

        elif key == "obligations":
            # Merge obligations by ID
            existing_obligations = {o.get("id"): o for o in merged.get("obligations", [])}
            new_obligations = value if isinstance(value, list) else [value]

            for obligation in new_obligations:
                if obligation.get("id"):
                    existing_obligations[obligation["id"]] = obligation

            merged["obligations"] = list(existing_obligations.values())

        elif key == "evidence":
            # Append evidence with deduplication by hash
            existing_evidence = merged.get("evidence", [])
            evidence_hashes = {e.get("hash") for e in existing_evidence if e.get("hash")}

            new_evidence = value if isinstance(value, list) else [value]
            for evidence in new_evidence:
                if evidence.get("hash") not in evidence_hashes:
                    existing_evidence.append(evidence)

            merged["evidence"] = existing_evidence

        else:
            # Default merge
            merged[key] = value

    merged["last_updated"] = datetime.now(timezone.utc).isoformat()
    return merged


def increment_counter(existing: int, new: int) -> int:
    """
    Increment a counter value.

    Args:
        existing: Current counter value
        new: Value to add (typically 1)

    Returns:
        Incremented counter
    """
    return existing + new


def update_metadata(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update metadata with timestamp and version tracking.

    Args:
        existing: Current metadata
        new: New metadata to merge

    Returns:
        Updated metadata with history
    """
    merged = existing.copy()

    # Track changes
    if "change_history" not in merged:
        merged["change_history"] = []

    change_record = {"timestamp": datetime.now(timezone.utc).isoformat(), "changes": {}}

    for key, value in new.items():
        if key in merged and merged[key] != value:
            change_record["changes"][key] = {"from": merged[key], "to": value}
        merged[key] = value

    if change_record["changes"]:
        merged["change_history"].append(change_record)

    merged["last_updated"] = datetime.now(timezone.utc).isoformat()
    merged["update_count"] = merged.get("update_count", 0) + 1

    return merged


class WorkflowStatus(Enum):
    """Status of the workflow execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    RETRYING = "retrying"  # Added for retry logic


class EnhancedComplianceState(TypedDict):
    """
    Enhanced state for compliance workflows with proper reducers.

    This state uses Annotated types with custom reducers for intelligent
    data aggregation and state management.
    """

    # Core conversation flow with message deduplication
    messages: Annotated[List[Any], add_messages]

    # Session and identity management
    session_id: str
    company_id: UUID
    user_id: Optional[UUID]
    thread_id: Optional[str]

    # Workflow status and routing
    workflow_status: WorkflowStatus
    current_node: Optional[str]
    next_node: Optional[str]
    visited_nodes: List[str]

    # Tool execution with output merging
    tool_outputs: Annotated[Dict[str, Any], merge_tool_outputs]
    tool_call_count: Annotated[int, increment_counter]
    tool_execution_history: List[Dict[str, Any]]

    # Error handling with accumulation limits
    errors: Annotated[List[Dict], accumulate_errors]
    error_count: Annotated[int, increment_counter]
    max_retries: int
    retry_count: int

    # Compliance data with intelligent merging
    compliance_data: Annotated[Dict[str, Any], merge_compliance_data]

    # Assessment context
    assessment_phase: Optional[str]
    questions_asked: List[str]
    questions_answered: Annotated[int, increment_counter]

    # Business profile accumulation
    business_profile: Dict[str, Any]
    risk_profile: Dict[str, Any]

    # Metadata with versioning
    metadata: Annotated[Dict[str, Any], update_metadata]

    # Performance metrics
    start_time: datetime
    end_time: Optional[datetime]
    total_latency_ms: Optional[int]
    node_latencies: Dict[str, int]

    # Cost tracking
    token_usage: Dict[str, int]
    estimated_cost: float
    cost_breakdown: Dict[str, float]

    # Human-in-the-loop controls
    requires_human_review: bool
    human_feedback: Optional[Dict[str, Any]]
    autonomy_level: int  # 1-3 scale

    # Graph execution control
    max_turns: int
    turn_count: Annotated[int, increment_counter]
    should_continue: bool
    termination_reason: Optional[str]

    # Workflow history tracking
    history: List[Dict[str, Any]]

    # Additional workflow tracking
    last_error_time: Optional[datetime]
    last_successful_node: Optional[str]
    updated_at: Optional[datetime]

    # Evidence collection fields
    evidence_items: List[Dict[str, Any]]
    evidence_status: Dict[str, str]
    evidence_scores: Dict[str, float]
    evidence_validation_results: List[Dict[str, Any]]
    evidence_collection_state: str  # "init", "collecting", "validating", "complete"
    actor: str  # Current actor/node processing the state


def create_enhanced_initial_state(
    session_id: str,
    company_id: UUID,
    initial_message: str,
    user_id: Optional[UUID] = None,
    thread_id: Optional[str] = None,
    autonomy_level: int = 2,
    max_turns: int = 20,
    max_retries: int = 3,
) -> EnhancedComplianceState:
    """
    Create an enhanced initial state with proper defaults.

    Args:
        session_id: Unique session identifier
        company_id: Company UUID for multi-tenancy
        initial_message: User's initial message
        user_id: Optional user identifier
        thread_id: Optional conversation thread ID
        autonomy_level: Level of agent autonomy (1-3)
        max_turns: Maximum conversation turns
        max_retries: Maximum retries for failed operations

    Returns:
        Enhanced initial state with all fields properly initialized
    """
    now = datetime.now(timezone.utc)

    return EnhancedComplianceState(
        # Conversation
        messages=[{"role": "user", "content": initial_message, "timestamp": now.isoformat()}],
        # Identity
        session_id=session_id,
        company_id=company_id,
        user_id=user_id,
        thread_id=thread_id,
        # Workflow
        workflow_status=WorkflowStatus.PENDING,
        current_node=None,
        next_node="router",
        visited_nodes=[],
        # Tools
        tool_outputs={},
        tool_call_count=0,
        tool_execution_history=[],
        # Errors
        errors=[],
        error_count=0,
        max_retries=max_retries,
        retry_count=0,
        # Compliance
        compliance_data={
            "frameworks": [],
            "obligations": [],
            "evidence": [],
            "last_updated": now.isoformat(),
        },
        # Assessment
        assessment_phase=None,
        questions_asked=[],
        questions_answered=0,
        # Business context
        business_profile={},
        risk_profile={},
        # Metadata
        metadata={
            "version": "2.0.0",
            "created_at": now.isoformat(),
            "last_updated": now.isoformat(),
            "update_count": 0,
            "change_history": [],
        },
        # Performance
        start_time=now,
        end_time=None,
        total_latency_ms=None,
        node_latencies={},
        # Cost
        token_usage={"input": 0, "output": 0, "total": 0},
        estimated_cost=0.0,
        cost_breakdown={},
        # Human controls
        requires_human_review=False,
        human_feedback=None,
        autonomy_level=autonomy_level,
        # Execution control
        max_turns=max_turns,
        turn_count=0,
        should_continue=True,
        termination_reason=None,
        # Workflow history
        history=[],
        # Additional tracking fields
        last_error_time=None,
        last_successful_node=None,
        updated_at=now,
    )


class StateTransition:
    """
    Helper class for state transitions with validation.
    """

    @staticmethod
    def validate_transition(state: EnhancedComplianceState, from_node: str, to_node: str) -> bool:
        """
        Validate if a state transition is allowed.

        Args:
            state: Current state
            from_node: Source node
            to_node: Target node

        Returns:
            True if transition is valid
        """
        # Check if we've exceeded limits
        if state["turn_count"] >= state["max_turns"]:
            return False

        if state["error_count"] >= state["max_retries"]:
            return False

        if not state["should_continue"]:
            return False

        # Add more transition rules as needed
        return True

    @staticmethod
    def record_transition(
        state: EnhancedComplianceState,
        from_node: str,
        to_node: str,
        latency_ms: Optional[int] = None,
    ) -> EnhancedComplianceState:
        """
        Record a node transition in the state.

        Args:
            state: Current state
            from_node: Source node
            to_node: Target node
            latency_ms: Optional latency for the transition

        Returns:
            Updated state with transition recorded
        """
        state["visited_nodes"].append(from_node)
        state["current_node"] = to_node

        if latency_ms:
            state["node_latencies"][from_node] = latency_ms

            # Update total latency
            total = state.get("total_latency_ms", 0) or 0
            state["total_latency_ms"] = total + latency_ms

        # Update workflow status
        if to_node == "END":
            state["workflow_status"] = WorkflowStatus.COMPLETED
            state["end_time"] = datetime.now(timezone.utc)
        elif state["workflow_status"] == WorkflowStatus.PENDING:
            state["workflow_status"] = WorkflowStatus.IN_PROGRESS

        return state


class StateAggregator:
    """
    Utility class for aggregating and summarizing state data.
    """

    @staticmethod
    def get_conversation_summary(state: EnhancedComplianceState) -> Dict[str, Any]:
        """
        Get a summary of the conversation from state.

        Args:
            state: Current state

        Returns:
            Conversation summary
        """
        return {
            "session_id": state["session_id"],
            "message_count": len(state["messages"]),
            "turn_count": state["turn_count"],
            "current_phase": state.get("assessment_phase"),
            "questions_asked": len(state["questions_asked"]),
            "questions_answered": state["questions_answered"],
            "workflow_status": state["workflow_status"].value,
        }

    @staticmethod
    def get_compliance_summary(state: EnhancedComplianceState) -> Dict[str, Any]:
        """
        Get a summary of compliance data from state.

        Args:
            state: Current state

        Returns:
            Compliance summary
        """
        compliance_data = state["compliance_data"]
        return {
            "frameworks_identified": len(compliance_data.get("frameworks", [])),
            "obligations_found": len(compliance_data.get("obligations", [])),
            "evidence_collected": len(compliance_data.get("evidence", [])),
            "last_updated": compliance_data.get("last_updated"),
        }

    @staticmethod
    def get_performance_metrics(state: EnhancedComplianceState) -> Dict[str, Any]:
        """
        Extract performance metrics from state.

        Args:
            state: Current state

        Returns:
            Performance metrics
        """
        duration = None
        if state["end_time"] and state["start_time"]:
            duration = (state["end_time"] - state["start_time"]).total_seconds()

        return {
            "total_latency_ms": state.get("total_latency_ms"),
            "duration_seconds": duration,
            "tool_calls": state["tool_call_count"],
            "errors": state["error_count"],
            "retries": state["retry_count"],
            "token_usage": state["token_usage"],
            "estimated_cost": state["estimated_cost"],
            "nodes_visited": len(state["visited_nodes"]),
        }
