"""

State validator node for validating and preparing workflow state.
"""

import logging
from datetime import datetime

from langgraph_agent.graph.unified_state import UnifiedComplianceState

logger = logging.getLogger(__name__)


async def state_validator_node(state: UnifiedComplianceState) -> UnifiedComplianceState:
    """
    Validate and prepare the workflow state.

    This node:
    - Validates required fields
    - Sets defaults for missing values
    - Prepares the state for workflow execution
    - Logs workflow initiation

    Args:
        state: Initial workflow state

    Returns:
        Validated and prepared state
    """
    logger.info(f"Validating state for workflow {state.get('workflow_id', 'unknown')}")

    # Validate required fields
    required_fields = ["workflow_id", "task_type", "thread_id"]
    missing_fields = []

    for field in required_fields:
        if field not in state or state[field] is None:
            missing_fields.append(field)

    if missing_fields:
        error_msg = f"Missing required fields: {missing_fields}"
        logger.error(error_msg)

        # Add validation error to state
        if "errors" not in state:
            state["errors"] = []

        state["errors"].append(
            {
                "type": "ValidationError",
                "message": error_msg,
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] = len(state["errors"])
        state["workflow_status"] = "FAILED"
        state["should_continue"] = False

        return state

    # Set defaults for optional fields
    defaults = {
        "workflow_status": "RUNNING",
        "retry_count": 0,
        "max_retries": 3,
        "should_continue": True,
        "error_count": 0,
        "errors": [],
        "steps_completed": [],
        "steps_remaining": [],
        "history": [],
        "metadata": {},
        "compliance_data": {},
        "evidence_items": [],
        "obligations": [],
        "assessment_results": {},
        "rag_queries": [],
        "rag_responses": [],
        "relevant_documents": [],
        "vector_store_status": "UNKNOWN",
        "questions_asked": [],
        "questions_answered": 0,
        "turn_count": 0,
        "assessment_phase": "initialization",
    }

    for key, default_value in defaults.items():
        if key not in state:
            state[key] = default_value

    # Update workflow status
    state["workflow_status"] = "RUNNING"
    state["updated_at"] = datetime.now()

    # Add validation completion to history
    state["history"].append(
        {
            "timestamp": datetime.now().isoformat(),
            "action": "state_validation_completed",
            "status": "success",
            "task_type": state["task_type"],
        }
    )

    # Log validation success
    logger.info(
        f"State validation successful for workflow {state['workflow_id']}, "
        f"task type: {state['task_type']}"
    )

    return state
