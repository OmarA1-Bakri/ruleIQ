"""

LangGraph state definition for compliance agent.
Defines TypedDict with messages, route, docs, profile, tool_outputs, errors, meta.
"""

from typing import Dict, List, Optional, Any, TypedDict, Annotated
from uuid import UUID
from datetime import datetime, timezone

from langgraph.graph import add_messages

from ..core.models import (
    GraphMessage,
    ComplianceProfile,
    Obligation,
    EvidenceItem,
    RouteDecision,
    SafeFallbackResponse,
)


class ComplianceAgentState(TypedDict):
    """
    State for the compliance agent graph.

    This defines the complete state that flows through all nodes in the LangGraph.
    Each node can read from and write to this state.
    """

    # Core conversation flow
    messages: Annotated[List[GraphMessage], add_messages]

    # Routing and navigation
    route: Optional[RouteDecision]
    current_node: Optional[str]
    next_node: Optional[str]

    # Business context and profile
    company_id: UUID
    profile: Optional[ComplianceProfile]
    thread_id: Optional[str]
    user_id: Optional[UUID]

    # Retrieved documents and obligations
    retrieved_docs: List[Dict[str, Any]]
    relevant_obligations: List[Obligation]
    collected_evidence: List[EvidenceItem]

    # Tool execution tracking
    tool_outputs: Dict[str, Any]
    tool_calls_made: List[Dict[str, Any]]
    tool_call_count: int

    # Error handling and fallbacks
    errors: List[SafeFallbackResponse]
    error_count: int

    # Graph execution metadata
    meta: Dict[str, Any]
    turn_count: int
    start_time: datetime
    last_updated: datetime

    # Autonomy and interrupts
    autonomy_level: int  # 1=transparent_helper, 2=trusted_advisor, 3=autonomous_partner
    requires_human_review: bool
    interrupt_before: Optional[str]  # Node name to interrupt before
    interrupt_reason: Optional[str]

    # Framework and compliance context
    selected_frameworks: List[str]
    risk_tolerance: str
    geographical_scope: List[str]

    # Performance and cost tracking
    token_usage: Dict[str, int]
    cost_estimate: float
    latency_ms: Optional[int]


def create_initial_state(
    company_id: UUID,
    user_input: str,
    thread_id: Optional[str] = None,
    user_id: Optional[UUID] = None,
    autonomy_level: int = 2,
) -> ComplianceAgentState:
    """
    Create initial state for a new compliance agent session.

    Args:
        company_id: Company UUID for tenancy isolation
        user_input: Initial user message
        thread_id: Optional thread ID for conversation tracking
        user_id: Optional user ID for audit trails
        autonomy_level: Agent autonomy level (1-3)

    Returns:
        Initial state with user message and default values
    """
    now = datetime.now(timezone.utc)

    # Create initial user message
    initial_message = GraphMessage(role="user", content=user_input, timestamp=now)

    return ComplianceAgentState(
        # Core conversation
        messages=[initial_message],
        # Routing
        route=None,
        current_node=None,
        next_node="router",  # Always start with router
        # Business context
        company_id=company_id,
        profile=None,
        thread_id=thread_id,
        user_id=user_id,
        # Retrieved content
        retrieved_docs=[],
        relevant_obligations=[],
        collected_evidence=[],
        # Tool tracking
        tool_outputs={},
        tool_calls_made=[],
        tool_call_count=0,
        # Error handling
        errors=[],
        error_count=0,
        # Metadata
        meta={
            "session_id": thread_id,
            "created_at": now.isoformat(),
            "version": "1.0.0",
        },
        turn_count=1,
        start_time=now,
        last_updated=now,
        # Autonomy
        autonomy_level=autonomy_level,
        requires_human_review=False,
        interrupt_before=None,
        interrupt_reason=None,
        # Compliance context
        selected_frameworks=[],
        risk_tolerance="medium",
        geographical_scope=[],
        # Performance
        token_usage={"input": 0, "output": 0, "total": 0},
        cost_estimate=0.0,
        latency_ms=None,
    )


def update_state_metadata(state: ComplianceAgentState) -> ComplianceAgentState:
    """
    Update state metadata with current timestamp and turn count.

    Args:
        state: Current state to update

    Returns:
        Updated state with fresh metadata
    """
    state["last_updated"] = datetime.now(timezone.utc)
    state["turn_count"] += 1
    return state


def add_error_to_state(
    state: ComplianceAgentState, error: SafeFallbackResponse
) -> ComplianceAgentState:
    """
    Add an error to the state and increment error count.

    Args:
        state: Current state
        error: SafeFallbackResponse error to add

    Returns:
        Updated state with error added
    """
    state["errors"].append(error)
    state["error_count"] += 1
    return update_state_metadata(state)


def should_interrupt(state: ComplianceAgentState, node_name: str) -> bool:
    """
    Check if execution should be interrupted before the given node.

    Args:
        state: Current state
        node_name: Name of node about to execute

    Returns:
        True if should interrupt, False otherwise
    """
    # Check explicit interrupt requests
    if state["interrupt_before"] == node_name:
        return True

    # Check if human review is required
    if state["requires_human_review"]:
        return True

    # Check error thresholds
    if state["error_count"] >= 3:
        return True

    # Check turn limits
    return state["turn_count"] >= 20


def get_state_summary(state: ComplianceAgentState) -> Dict[str, Any]:
    """
    Get a summary of the current state for logging and debugging.

    Args:
        state: Current state

    Returns:
        Summary dictionary with key metrics
    """
    return {
        "company_id": str(state["company_id"]),
        "turn_count": state["turn_count"],
        "message_count": len(state["messages"]),
        "current_node": state["current_node"],
        "next_node": state["next_node"],
        "route": state["route"].route if state["route"] else None,
        "error_count": state["error_count"],
        "tool_call_count": state["tool_call_count"],
        "autonomy_level": state["autonomy_level"],
        "requires_review": state["requires_human_review"],
        "token_usage": state["token_usage"],
        "cost_estimate": state["cost_estimate"],
        "frameworks": state["selected_frameworks"],
        "obligations_found": len(state["relevant_obligations"]),
        "evidence_collected": len(state["collected_evidence"]),
    }
