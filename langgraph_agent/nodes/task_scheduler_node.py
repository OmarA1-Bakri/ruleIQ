"""

Task scheduler node for LangGraph workflow.
Manages task scheduling and orchestration.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from langgraph_agent.graph.unified_state import UnifiedComplianceState
from langgraph_agent.utils.cost_tracking import track_node_cost

logger = logging.getLogger(__name__)


@track_node_cost(node_name="task_scheduler_node", track_tokens=False)
async def task_scheduler_node(state: UnifiedComplianceState) -> UnifiedComplianceState:
    """
    Main task scheduler node for workflow orchestration.

    This node handles:
    - Task scheduling and prioritization
    - Workflow orchestration
    - Task dependency management
    - Schedule-based task triggers

    Args:
        state: The current compliance state

    Returns:
        Updated state with scheduled tasks
    """
    try:
        logger.info("Task scheduler node executing")

        # Extract scheduling metadata
        metadata = state.get("metadata", {})
        schedule_type = metadata.get("schedule_type", "immediate")

        # Initialize scheduled_tasks if not present
        if "scheduled_tasks" not in state:
            state["scheduled_tasks"] = []

        # Determine tasks to schedule based on state
        tasks_to_schedule = []

        # Check if compliance check is needed
        if should_schedule_compliance_check(state):
            tasks_to_schedule.append(
                {
                    "task_type": "compliance_check",
                    "priority": "high",
                    "scheduled_time": get_next_scheduled_time(schedule_type),
                    "metadata": {
                        "company_id": state.get("company_id"),
                        "regulation": metadata.get("regulation"),
                    },
                }
            )

        # Check if report generation is needed
        if should_schedule_report(state):
            tasks_to_schedule.append(
                {
                    "task_type": "report_generation",
                    "priority": "medium",
                    "scheduled_time": get_next_scheduled_time(schedule_type, delay_hours=1),
                    "metadata": {
                        "report_type": metadata.get("report_type", "compliance_summary"),
                        "format": metadata.get("report_format", "pdf"),
                    },
                }
            )

        # Check if notification is needed
        if should_schedule_notification(state):
            tasks_to_schedule.append(
                {
                    "task_type": "notification",
                    "priority": "low",
                    "scheduled_time": get_next_scheduled_time(schedule_type, delay_hours=2),
                    "metadata": {
                        "recipient_emails": metadata.get("recipient_emails", []),
                        "notification_type": "compliance_update",
                    },
                }
            )

        # Add tasks to state
        for task in tasks_to_schedule:
            task["task_id"] = generate_task_id()
            task["status"] = "scheduled"
            state["scheduled_tasks"].append(task)
            logger.info(f"Scheduled task: {task['task_type']} with ID: {task['task_id']}")

        # Update workflow metadata
        state["metadata"]["tasks_scheduled"] = len(tasks_to_schedule)
        state["metadata"]["schedule_timestamp"] = datetime.now().isoformat()

        # Update history
        if "history" not in state:
            state["history"] = []

        state["history"].append(
            {
                "step": "task_scheduling",
                "action": f"Scheduled {len(tasks_to_schedule)} tasks",
                "timestamp": datetime.now().isoformat(),
            }
        )

        logger.info(f"Scheduled {len(tasks_to_schedule)} tasks")
        return state

    except Exception as e:
        logger.error(f"Error in task scheduler node: {str(e)}")

        # Update error tracking
        if "errors" not in state:
            state["errors"] = []
        if "error_count" not in state:
            state["error_count"] = 0

        state["errors"].append(
            {"type": "SchedulerError", "message": str(e), "node": "task_scheduler_node"}
        )
        state["error_count"] += 1

        return state


def should_schedule_compliance_check(state: Dict[str, Any]) -> bool:
    """
    Determine if a compliance check should be scheduled.

    Args:
        state: Current state

    Returns:
        True if compliance check should be scheduled
    """
    # Check if compliance data exists and is recent
    compliance_data = state.get("compliance_data", {})
    if not compliance_data:
        return True

    # Check if last check was more than configured interval
    last_check = compliance_data.get("last_check_timestamp")
    if last_check:
        # In production, compare with configured interval
        # For now, always schedule if requested
        pass

    # Check if explicitly requested
    metadata = state.get("metadata", {})
    if metadata.get("force_compliance_check"):
        return True

    return not compliance_data


def should_schedule_report(state: Dict[str, Any]) -> bool:
    """
    Determine if a report should be scheduled.

    Args:
        state: Current state

    Returns:
        True if report should be scheduled
    """
    # Check if compliance check has results
    compliance_data = state.get("compliance_data", {})
    if compliance_data and compliance_data.get("check_results"):
        return True

    # Check if explicitly requested
    metadata = state.get("metadata", {})
    return bool(metadata.get("generate_report"))


def should_schedule_notification(state: Dict[str, Any]) -> bool:
    """
    Determine if a notification should be scheduled.

    Args:
        state: Current state

    Returns:
        True if notification should be scheduled
    """
    # Check if there are violations to notify about
    compliance_data = state.get("compliance_data", {})
    check_results = compliance_data.get("check_results", {})
    if check_results.get("violations"):
        return True

    # Check if explicitly requested
    metadata = state.get("metadata", {})
    return bool(metadata.get("send_notification"))


def get_next_scheduled_time(schedule_type: str, delay_hours: int = 0) -> str:
    """
    Calculate next scheduled time based on schedule type.

    Args:
        schedule_type: Type of schedule (immediate, daily, weekly)
        delay_hours: Additional delay in hours

    Returns:
        ISO format timestamp for next scheduled time
    """
    base_time = datetime.now()

    if schedule_type == "immediate":
        scheduled_time = base_time + timedelta(hours=delay_hours)
    elif schedule_type == "daily":
        scheduled_time = base_time.replace(hour=9, minute=0, second=0) + timedelta(
            days=1, hours=delay_hours
        )
    elif schedule_type == "weekly":
        scheduled_time = base_time + timedelta(days=7, hours=delay_hours)
    else:
        scheduled_time = base_time + timedelta(hours=delay_hours)

    return scheduled_time.isoformat()


def generate_task_id() -> str:
    """
    Generate unique task ID.

    Returns:
        Unique task ID
    """
    import uuid

    return str(uuid.uuid4())


async def execute_scheduled_tasks(
    state: UnifiedComplianceState,
) -> UnifiedComplianceState:
    """
    Execute scheduled tasks that are due.

    Args:
        state: Current state

    Returns:
        Updated state after task execution
    """
    try:
        scheduled_tasks = state.get("scheduled_tasks", [])
        current_time = datetime.now()

        for task in scheduled_tasks:
            if task["status"] != "scheduled":
                continue

            scheduled_time = datetime.fromisoformat(task["scheduled_time"])

            if scheduled_time <= current_time:
                logger.info(f"Executing scheduled task: {task['task_id']} - {task['task_type']}")
                task["status"] = "executing"

                # In production, this would trigger the appropriate node
                # For now, mark as completed
                task["status"] = "completed"
                task["completed_time"] = current_time.isoformat()

        return state

    except Exception as e:
        logger.error(f"Error executing scheduled tasks: {str(e)}")
        return state
