"""

State fixtures for LangGraph testing.

Provides factory functions and builders for creating test states.
"""

from typing import Dict, List, Any, Optional
from uuid import uuid4
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from langgraph_agent.graph.enhanced_state import (
    EnhancedComplianceState,
    WorkflowStatus,
    create_enhanced_initial_state,
)


class TestScenario(Enum):
    """Common test scenarios for state testing."""

    INITIAL = "initial"
    IN_PROGRESS = "in_progress"
    ERROR_STATE = "error_state"
    COMPLETED = "completed"
    REVIEW_NEEDED = "review_needed"
    RETRY_REQUIRED = "retry_required"


@dataclass
class StateBuilder:
    """
    Builder pattern for creating test states with specific configurations.
    """

    company_id: str = field(default_factory=lambda: str(uuid4()))
    workflow_status: WorkflowStatus = WorkflowStatus.PENDING
    current_node: str = "start"
    messages: List[Dict[str, Any]] = field(default_factory=list)
    compliance_data: Dict[str, Any] = field(default_factory=dict)
    tool_outputs: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)

    def with_company(self, company_id: str) -> "StateBuilder":
        """Set company ID."""
        self.company_id = company_id
        return self

    def with_status(self, status: WorkflowStatus) -> "StateBuilder":
        """Set workflow status."""
        self.workflow_status = status
        return self

    def with_node(self, node_name: str) -> "StateBuilder":
        """Set current node."""
        self.current_node = node_name
        return self

    def add_message(self, role: str, content: str, **kwargs) -> "StateBuilder":
        """Add a message to the state."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        self.messages.append(message)
        return self

    def add_compliance_data(self, key: str, value: Any) -> "StateBuilder":
        """Add compliance data."""
        self.compliance_data[key] = value
        return self

    def add_tool_output(self, tool_name: str, output: Any, success: bool = True) -> "StateBuilder":
        """Add a tool output."""
        self.tool_outputs.append(
            {
                "tool": tool_name,
                "output": output,
                "success": success,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        return self

    def add_error(self, error_type: str, message: str, **kwargs) -> "StateBuilder":
        """Add an error to the state."""
        error = {
            "type": error_type,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        self.errors.append(error)
        return self

    def with_context(self, **kwargs) -> "StateBuilder":
        """Set context values."""
        self.context.update(kwargs)
        return self

    def with_retry(self, count: int) -> "StateBuilder":
        """Set retry count."""
        self.retry_count = count
        return self

    def add_checkpoint(self, checkpoint_id: str, data: Dict[str, Any]) -> "StateBuilder":
        """Add a checkpoint."""
        self.checkpoints.append(
            {
                "id": checkpoint_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
            },
        )
        return self

    def build(self) -> EnhancedComplianceState:
        """Build the state object."""
        from uuid import uuid4

        # Default parameters for backward compatibility
        session_id = str(uuid4())
        company_id = uuid4() if isinstance(self.company_id, str) else self.company_id
        initial_message = "Test initialization"

        return self.build_with_params(session_id, company_id, initial_message)

    def build_with_params(
        self, session_id: str, company_id: Any, initial_message: str
    ) -> EnhancedComplianceState:
        """Build the state object with specific parameters."""
        # Start with enhanced initial state
        state = create_enhanced_initial_state(session_id, company_id, initial_message)

        # Update with builder values
        state["workflow_status"] = self.workflow_status
        state["current_node"] = self.current_node
        if self.messages:  # Only replace if we have custom messages
            state["messages"] = self.messages
        state["compliance_data"].update(self.compliance_data)
        state["tool_outputs"] = self.tool_outputs
        state["errors"] = self.errors
        state["context"] = self.context
        state["retry_count"] = self.retry_count
        state["metadata"].update(self.metadata)
        state["checkpoints"] = self.checkpoints

        return state


def create_test_state(
    scenario: TestScenario = TestScenario.INITIAL, **overrides
) -> EnhancedComplianceState:
    """
    Factory function to create test states for common scenarios.

    Args:
        scenario: Test scenario to create
        **overrides: Override specific state values

    Returns:
        Configured test state
    """
    from uuid import uuid4

    builder = StateBuilder()

    # Create with proper arguments for enhanced initial state
    session_id = str(uuid4())
    company_id = uuid4()
    initial_message = "Test initialization"

    if scenario == TestScenario.INITIAL:
        builder.with_status(WorkflowStatus.PENDING).with_node("start").add_message(
            "system",
            "Workflow initialized",
        )

    elif scenario == TestScenario.IN_PROGRESS:
        builder.with_status(WorkflowStatus.IN_PROGRESS).with_node("data_collection").add_message(
            "system", "Processing compliance data"
        ).add_compliance_data("framework", "SOC2").add_tool_output(
            "data_collector",
            {"records": 100},
        )

    elif scenario == TestScenario.ERROR_STATE:
        builder.with_status(WorkflowStatus.FAILED).with_node("validation").add_error(
            "ValidationError", "Invalid data format"
        ).with_retry(2)

    elif scenario == TestScenario.COMPLETED:
        builder.with_status(WorkflowStatus.COMPLETED).with_node("end").add_compliance_data(
            "assessment_complete", True
        ).add_compliance_data(
            "compliance_score",
            0.95,
        )

    elif scenario == TestScenario.REVIEW_NEEDED:
        builder.with_status(WorkflowStatus.REVIEW_REQUIRED).with_node(
            "human_review"
        ).add_compliance_data("requires_human_input", True).with_context(
            review_reason="Ambiguous compliance requirement",
        )

    elif scenario == TestScenario.RETRY_REQUIRED:
        builder.with_status(WorkflowStatus.IN_PROGRESS).with_node("retry_handler").with_retry(
            1
        ).add_error("TransientError", "API temporarily unavailable")

    # Apply overrides
    for key, value in overrides.items():
        if hasattr(builder, key):
            setattr(builder, key, value)

    # Build with proper parameters
    return builder.build_with_params(session_id, company_id, initial_message)


def create_batch_states(
    count: int = 5, scenario: TestScenario = TestScenario.INITIAL
) -> List[EnhancedComplianceState]:
    """
    Create multiple test states for batch testing.

    Args:
        count: Number of states to create
        scenario: Base scenario for all states

    Returns:
        List of test states
    """
    states = []
    for i in range(count):
        state = create_test_state(scenario)
        # Make each state unique
        state["company_id"] = f"test_company_{i}"
        state["metadata"]["batch_index"] = i
        states.append(state)

    return states


def assert_state_transition(
    initial_state: EnhancedComplianceState,
    final_state: EnhancedComplianceState,
    expected_node: str,
    expected_status: WorkflowStatus = None,
):
    """
    Helper function to assert state transitions in tests.

    Args:
        initial_state: State before transition
        final_state: State after transition
        expected_node: Expected current node after transition
        expected_status: Expected workflow status (optional)
    """
    # Check node transition
    assert final_state["current_node"] == expected_node, (
        f"Expected node {expected_node}, got {final_state['current_node']}"
    )

    # Check status if specified
    if expected_status:
        assert final_state["workflow_status"] == expected_status, (
            f"Expected status {expected_status}, got {final_state['workflow_status']}"
        )

    # Ensure state has progressed
    assert (final_state["metadata"]["last_updated"] >= initial_state["metadata"]["last_updated"],)

    # Check for state consistency
    assert final_state["company_id"] == initial_state["company_id"], (
        "Company ID should not change during transition"
    )


def assert_error_recorded(state: EnhancedComplianceState, error_type: str):
    """
    Assert that an error of a specific type was recorded.

    Args:
        state: State to check
        error_type: Expected error type
    """
    error_types = [e.get("type") for e in state.get("errors", [])]
    assert error_type in error_types, (
        f"Expected error type {error_type} not found. Found: {error_types}"
    )


def assert_tool_output_exists(state: EnhancedComplianceState, tool_name: str):
    """
    Assert that output from a specific tool exists in state.

    Args:
        state: State to check
        tool_name: Name of the tool
    """
    tool_names = [t.get("tool") for t in state.get("tool_outputs", [])]
    assert tool_name in tool_names, f"Expected tool {tool_name} not found. Found: {tool_names}"


# Pytest fixture
def state_builder_fixture():
    """Pytest fixture for state builder."""
    return StateBuilder()


def test_states_fixture():
    """Pytest fixture providing various test states."""
    return {
        "initial": create_test_state(TestScenario.INITIAL),
        "in_progress": create_test_state(TestScenario.IN_PROGRESS),
        "error": create_test_state(TestScenario.ERROR_STATE),
        "completed": create_test_state(TestScenario.COMPLETED),
        "review": create_test_state(TestScenario.REVIEW_NEEDED),
        "retry": create_test_state(TestScenario.RETRY_REQUIRED),
    }


def create_compliance_context(
    company_name: str = "Test Company", framework: str = "SOC2"
) -> Dict[str, Any]:
    """Create a compliance context for testing.

    Args:
        company_name: Name of the company
        framework: Compliance framework

    Returns:
        Dictionary containing compliance context
    """
    return {
        "company_name": company_name,
        "framework": framework,
        "industry": "Technology",
        "size": "Medium",
        "risk_level": "Medium",
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_fixture",
        },
    }
