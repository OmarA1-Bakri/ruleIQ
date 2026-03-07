"""

Unified state management for LangGraph compliance system.
Complete state definition for ALL phases of the compliance workflow.
"""

from typing import TypedDict, List, Dict, Any, Optional, Literal
from datetime import datetime
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from typing_extensions import Annotated
from uuid import uuid4


class UnifiedComplianceState(TypedDict):
    """
    Complete unified state for ALL phases of the compliance system.
    This state is used across all nodes and integrates all functionality.
    """

    # Core workflow fields
    workflow_id: str
    workflow_status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "RETRYING"]
    current_step: str

    # Messages with proper reducer for LangGraph
    messages: Annotated[List[BaseMessage], add_messages]

    # Execution tracking
    steps_completed: List[str]
    steps_remaining: List[str]
    retry_count: int
    max_retries: int
    should_continue: bool

    # Error tracking (Phase 2 integration)
    errors: List[Dict[str, Any]]
    error_count: int
    error_correlation_id: Optional[str]
    circuit_breaker_status: Dict[str, Any]
    last_error_time: Optional[datetime]

    # RAG context (Phase 3 integration)
    rag_queries: List[Dict[str, Any]]
    rag_responses: List[Dict[str, Any]]
    relevant_documents: List[Dict[str, Any]]
    vector_store_status: str

    # Task scheduling (Phase 4 integration)
    scheduled_task_id: Optional[str]
    task_type: Optional[str]
    task_schedule: Optional[str]
    task_result: Optional[Any]
    celery_task_status: Optional[str]

    # Compliance specific fields
    compliance_data: Dict[str, Any]
    evidence_items: List[Dict[str, Any]]
    obligations: List[Dict[str, Any]]
    assessment_results: Dict[str, Any]

    # Business context
    company_id: Optional[str]
    business_profile_id: Optional[str]
    session_id: Optional[str]
    user_id: Optional[str]

    # History and metadata
    history: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    workflow_checkpoint_id: Optional[str]
    thread_id: str

    # Additional tracking fields
    turn_count: int
    questions_asked: List[str]
    questions_answered: int
    assessment_phase: str


def create_unified_initial_state(
    workflow_id: Optional[str] = None,
    workflow_type: str = "compliance_check",
    company_id: Optional[str] = None,
    session_id: Optional[str] = None,
    initial_message: Optional[str] = None,
    max_retries: int = 3,
    metadata: Optional[Dict[str, Any]] = None,
) -> UnifiedComplianceState:
    """
    Create an initial unified state with all required fields.

    Args:
        workflow_id: Unique workflow identifier
        workflow_type: Type of workflow (compliance_check, evidence_collection, etc.)
        company_id: Company identifier
        session_id: Session identifier
        initial_message: Initial user message
        max_retries: Maximum retry attempts
        metadata: Additional metadata

    Returns:
        Initialized UnifiedComplianceState
    """
    workflow_id = workflow_id or str(uuid4())
    thread_id = f"workflow-{workflow_id}"

    # Build initial messages list
    messages = []
    if initial_message:
        from langchain_core.messages import HumanMessage

        messages.append(HumanMessage(content=initial_message))

    # Define workflow steps based on type
    steps_map = {
        "compliance_check": [
            "state_validator",
            "rag_query",
            "compliance_check",
            "notification",
            "reporting",
        ],
        "evidence_collection": [
            "state_validator",
            "evidence_collection",
            "compliance_check",
            "reporting",
        ],
        "notification": ["state_validator", "notification"],
        "reporting": ["state_validator", "reporting"],
    }

    steps_remaining = steps_map.get(workflow_type, ["state_validator"])

    return UnifiedComplianceState(
        # Core workflow fields
        workflow_id=workflow_id,
        workflow_status="PENDING",
        current_step="state_validator",
        # Messages
        messages=messages,
        # Execution tracking
        steps_completed=[],
        steps_remaining=steps_remaining,
        retry_count=0,
        max_retries=max_retries,
        should_continue=True,
        # Error tracking
        errors=[],
        error_count=0,
        error_correlation_id=None,
        circuit_breaker_status={},
        last_error_time=None,
        # RAG context
        rag_queries=[],
        rag_responses=[],
        relevant_documents=[],
        vector_store_status="UNKNOWN",
        # Task scheduling
        scheduled_task_id=None,
        task_type=workflow_type,
        task_schedule=None,
        task_result=None,
        celery_task_status=None,
        # Compliance specific
        compliance_data={},
        evidence_items=[],
        obligations=[],
        assessment_results={},
        # Business context
        company_id=company_id,
        business_profile_id=None,
        session_id=session_id,
        user_id=None,
        # History and metadata
        history=[
            {
                "timestamp": datetime.now().isoformat(),
                "action": "workflow_initialized",
                "workflow_type": workflow_type,
            }
        ],
        metadata=metadata or {},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        workflow_checkpoint_id=None,
        thread_id=thread_id,
        # Additional tracking
        turn_count=0,
        questions_asked=[],
        questions_answered=0,
        assessment_phase="initialization",
    )


def update_state_timestamp(state: UnifiedComplianceState) -> UnifiedComplianceState:
    """Update the state's updated_at timestamp."""
    state["updated_at"] = datetime.now()
    return state


def add_state_history(
    state: UnifiedComplianceState, action: str, details: Optional[Dict[str, Any]] = None
) -> UnifiedComplianceState:
    """
    Add an entry to the state's history.

    Args:
        state: Current state
        action: Action being recorded
        details: Optional additional details

    Returns:
        Updated state with new history entry
    """
    history_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "step": state.get("current_step", "unknown"),
    }

    if details:
        history_entry.update(details)

    state["history"].append(history_entry)
    state = update_state_timestamp(state)

    return state
