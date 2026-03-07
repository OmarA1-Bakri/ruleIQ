"""

Graph fixtures for LangGraph testing.

Provides test graph configurations and utilities for graph testing.
"""

from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import asyncio

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# from langgraph.prebuilt import ToolInvocation, ToolExecutor  # Not used

from tests.fixtures.mock_llm import MockLLM, create_deterministic_llm
from tests.fixtures.state_fixtures import EnhancedComplianceState, WorkflowStatus


class TestGraphType(Enum):
    """Types of test graphs available."""

    SIMPLE = "simple"
    WITH_CONDITIONALS = "with_conditionals"
    WITH_CYCLES = "with_cycles"
    WITH_SUBGRAPHS = "with_subgraphs"
    WITH_TOOLS = "with_tools"
    ERROR_HANDLING = "error_handling"


class TestNode:
    """Base class for test nodes."""

    def __init__(self, name: str, behavior: str = "pass"):
        """
        Initialize test node.

        Args:
            name: Node identifier
            behavior: Node behavior (pass, fail, delay, etc.)
        """
        self.name = name
        self.behavior = behavior
        self.call_count = 0
        self.call_history = []

    async def __call__(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """Execute node logic."""
        self.call_count += 1
        self.call_history.append(
            {
                "state_snapshot": state.copy(),
                "timestamp": state["metadata"]["last_updated"],
            },
        )

        # Apply behavior
        if self.behavior == "fail":
            state["errors"].append(
                {
                    "type": "TestError",
                    "message": f"Node {self.name} failed as configured",
                    "node": self.name,
                },
            )
            state["workflow_status"] = WorkflowStatus.FAILED

        elif self.behavior == "delay":
            await asyncio.sleep(0.1)  # Small delay for testing
            state["messages"].append(
                {"role": "system", "content": f"Node {self.name} completed with delay"},
            )

        else:  # Default "pass" behavior
            state["messages"].append(
                {"role": "system", "content": f"Node {self.name} executed successfully"},
            )
            state["tool_outputs"].append(
                {"tool": self.name, "output": {"result": "success"}, "success": True},
            )

        state["current_node"] = self.name
        return state

    def reset(self):
        """Reset node state for fresh testing."""
        self.call_count = 0
        self.call_history = []


def create_simple_graph() -> tuple[StateGraph, Dict[str, TestNode]]:
    """
    Create a simple linear test graph: start -> process -> end

    Returns:
        Tuple of (graph, nodes_dict)
    """
    # Create nodes
    nodes = {
        "start": TestNode("start"),
        "process": TestNode("process"),
        "finalize": TestNode("finalize"),
    }

    # Build graph
    graph = StateGraph(EnhancedComplianceState)

    # Add nodes
    graph.add_node("start", nodes["start"])
    graph.add_node("process", nodes["process"])
    graph.add_node("finalize", nodes["finalize"])

    # Add edges
    graph.set_entry_point("start")
    graph.add_edge("start", "process")
    graph.add_edge("process", "finalize")
    graph.add_edge("finalize", END)

    return graph, nodes


def create_conditional_graph() -> tuple[StateGraph, Dict[str, TestNode]]:
    """
    Create a graph with conditional routing.

    Returns:
        Tuple of (graph, nodes_dict)
    """
    # Create nodes
    nodes = {
        "start": TestNode("start"),
        "evaluate": TestNode("evaluate"),
        "path_a": TestNode("path_a"),
        "path_b": TestNode("path_b"),
        "merge": TestNode("merge"),
    }

    # Routing function
    def route_decision(state: EnhancedComplianceState) -> str:
        """Decide which path to take based on state."""
        if state.get("compliance_data", {}).get("risk_level") == "high":
            return "path_a"
        return "path_b"

    # Build graph
    graph = StateGraph(EnhancedComplianceState)

    # Add nodes
    for name, node in nodes.items():
        graph.add_node(name, node)

    # Add edges
    graph.set_entry_point("start")
    graph.add_edge("start", "evaluate")

    # Conditional routing
    graph.add_conditional_edges(
        "evaluate",
        route_decision,
        {"path_a": "path_a", "path_b": "path_b"},
    )

    graph.add_edge("path_a", "merge")
    graph.add_edge("path_b", "merge")
    graph.add_edge("merge", END)

    return graph, nodes


def create_cycle_graph() -> tuple[StateGraph, Dict[str, TestNode]]:
    """
    Create a graph with a retry cycle.

    Returns:
        Tuple of (graph, nodes_dict)
    """
    # Create nodes
    nodes = {
        "start": TestNode("start"),
        "attempt": TestNode("attempt"),
        "check": TestNode("check"),
        "retry": TestNode("retry"),
        "success": TestNode("success"),
    }

    # Routing function for cycle
    def check_retry(state: EnhancedComplianceState) -> str:
        """Check if retry is needed."""
        retry_count = state.get("retry_count", 0)
        if retry_count < 3 and state.get("workflow_status") == WorkflowStatus.FAILED:
            return "retry"
        return "success"

    # Build graph
    graph = StateGraph(EnhancedComplianceState)

    # Add nodes
    for name, node in nodes.items():
        graph.add_node(name, node)

    # Add edges
    graph.set_entry_point("start")
    graph.add_edge("start", "attempt")
    graph.add_edge("attempt", "check")

    # Conditional with cycle
    graph.add_conditional_edges(
        "check",
        check_retry,
        {"retry": "retry", "success": "success"},
    )

    graph.add_edge("retry", "attempt")  # Create cycle
    graph.add_edge("success", END)

    return graph, nodes


def create_error_handling_graph() -> tuple[StateGraph, Dict[str, Any]]:
    """
    Create a graph with error handling capabilities.

    Returns:
        Tuple of (graph, nodes_dict)
    """
    # Create nodes with different behaviors
    nodes = {
        "start": TestNode("start", "pass"),
        "risky_operation": TestNode("risky_operation", "fail"),
        "error_handler": TestNode("error_handler", "pass"),
        "fallback": TestNode("fallback", "pass"),
        "success": TestNode("success", "pass"),
    }

    # Error detection function
    def detect_error(state: EnhancedComplianceState) -> str:
        """Route based on error state."""
        if state.get("errors"):
            return "error_handler"
        return "success"

    # Recovery decision
    def recovery_route(state: EnhancedComplianceState) -> str:
        """Decide recovery path."""
        error_count = len(state.get("errors", []))
        if error_count > 2:
            return "fallback"
        return "risky_operation"  # Retry

    # Build graph
    graph = StateGraph(EnhancedComplianceState)

    # Add nodes
    for name, node in nodes.items():
        graph.add_node(name, node)

    # Add edges
    graph.set_entry_point("start")
    graph.add_edge("start", "risky_operation")

    # Error detection
    graph.add_conditional_edges(
        "risky_operation",
        detect_error,
        {"error_handler": "error_handler", "success": "success"},
    )

    # Recovery routing
    graph.add_conditional_edges(
        "error_handler",
        recovery_route,
        {"fallback": "fallback", "risky_operation": "risky_operation"},
    )

    graph.add_edge("fallback", END)
    graph.add_edge("success", END)

    return graph, nodes


class GraphTestHarness:
    """
    Test harness for running and validating graph executions.
    """

    def __init__(
        self,
        graph: StateGraph,
        nodes: Dict[str, TestNode],
        checkpointer: Optional[Any] = None,
    ):
        """
        Initialize test harness.

        Args:
            graph: StateGraph to test
            nodes: Dictionary of test nodes
            checkpointer: Optional checkpointer (defaults to MemorySaver)
        """
        self.graph = graph
        self.nodes = nodes
        self.checkpointer = checkpointer or MemorySaver()
        self.compiled_graph = None
        self.execution_history = []

    async def compile_and_prepare(self):
        """Compile the graph and prepare for testing."""
        self.compiled_graph = self.graph.compile(checkpointer=self.checkpointer)
        return self.compiled_graph

    async def run_with_state(
        self,
        initial_state: EnhancedComplianceState,
        config: Optional[Dict[str, Any]] = None,
    ) -> EnhancedComplianceState:
        """
        Run graph with given initial state.

        Args:
            initial_state: Starting state
            config: Optional configuration

        Returns:
            Final state after execution
        """
        if not self.compiled_graph:
            await self.compile_and_prepare()

        config = config or {"configurable": {"thread_id": "test_thread"}}

        # Run the graph
        final_state = await self.compiled_graph.ainvoke(initial_state, config)

        # Record execution
        self.execution_history.append(
            {
                "initial_state": initial_state,
                "final_state": final_state,
                "config": config,
                "node_calls": {name: node.call_count for name, node in self.nodes.items()},
            },
        )

        return final_state

    def get_execution_path(self) -> List[str]:
        """Get the execution path from the last run."""
        if not self.execution_history:
            return []

        path = []
        for name, node in self.nodes.items():
            if node.call_count > 0:
                # Add node multiple times if called multiple times (for cycles)
                for _ in range(node.call_count):
                    path.append(name)

        return path

    def assert_path(self, expected_path: List[str]):
        """Assert the execution followed expected path."""
        actual_path = self.get_execution_path()
        assert actual_path == expected_path, f"Expected path {expected_path}, got {actual_path}"

    def assert_node_called(self, node_name: str, times: int = 1):
        """Assert a node was called specific number of times."""
        actual_calls = self.nodes[node_name].call_count
        assert actual_calls == times, (
            f"Expected {node_name} called {times} times, got {actual_calls}"
        )

    def assert_no_errors(self, final_state: EnhancedComplianceState):
        """Assert no errors in final state."""
        errors = final_state.get("errors", [])
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def reset(self):
        """Reset harness for fresh testing."""
        for node in self.nodes.values():
            node.reset()
        self.execution_history = []


def create_test_harness(
    graph_type: TestGraphType = TestGraphType.SIMPLE,
) -> GraphTestHarness:
    """
    Factory function to create test harness with specified graph type.

    Args:
        graph_type: Type of test graph to create

    Returns:
        Configured GraphTestHarness
    """
    graph_creators = {
        TestGraphType.SIMPLE: create_simple_graph,
        TestGraphType.WITH_CONDITIONALS: create_conditional_graph,
        TestGraphType.WITH_CYCLES: create_cycle_graph,
        TestGraphType.ERROR_HANDLING: create_error_handling_graph,
    }

    creator = graph_creators.get(graph_type, create_simple_graph)
    graph, nodes = creator()

    return GraphTestHarness(graph, nodes)


# Pytest fixtures
def simple_graph_fixture():
    """Pytest fixture for simple graph."""
    return create_test_harness(TestGraphType.SIMPLE)


def conditional_graph_fixture():
    """Pytest fixture for conditional graph."""
    return create_test_harness(TestGraphType.WITH_CONDITIONALS)


def cycle_graph_fixture():
    """Pytest fixture for graph with cycles."""
    return create_test_harness(TestGraphType.WITH_CYCLES)


def error_graph_fixture():
    """Pytest fixture for error handling graph."""
    return create_test_harness(TestGraphType.ERROR_HANDLING)
