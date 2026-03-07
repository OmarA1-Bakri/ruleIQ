"""

End-to-end integration test for LangSmith tracing with LangGraph nodes.
Tests actual tracing functionality with real node execution.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any
import logging

from config.langsmith_config import LangSmithConfig, with_langsmith_tracing
from langgraph_agent.graph.unified_state import UnifiedComplianceState


logger = logging.getLogger(__name__)


class MockEvidenceNode:
    """Mock evidence node with LangSmith tracing."""

    @with_langsmith_tracing("mock.process_evidence")
    async def process_evidence(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process mock evidence with tracing."""
        state["evidence_processed"] = True
        state["evidence_count"] = state.get("evidence_count", 0) + 1
        await asyncio.sleep(0.01)  # Simulate processing time
        return state

    @with_langsmith_tracing("mock.validate_evidence")
    async def validate_evidence(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate mock evidence with tracing."""
        state["evidence_validated"] = True
        return state


class MockComplianceNode:
    """Mock compliance node with LangSmith tracing."""

    @with_langsmith_tracing("mock.check_compliance")
    async def check_compliance(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Check compliance with tracing."""
        state["compliance_checked"] = True
        state["compliance_score"] = 85
        await asyncio.sleep(0.01)  # Simulate processing time
        return state


class MockRAGNode:
    """Mock RAG node with LangSmith tracing."""

    @with_langsmith_tracing("mock.retrieve_documents")
    async def retrieve_documents(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve documents with tracing."""
        state["documents_retrieved"] = ["doc1", "doc2", "doc3"]
        await asyncio.sleep(0.01)  # Simulate retrieval time
        return state


@pytest.mark.asyncio
class TestLangSmithIntegrationE2E:
    """End-to-end tests for LangSmith integration."""

    async def test_workflow_with_tracing_enabled(self, monkeypatch):
        """Test complete workflow with LangSmith tracing enabled."""
        # Enable tracing
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        monkeypatch.setenv("LANGCHAIN_PROJECT", "test-project")

        traced_operations = []

        # Mock the tracing context
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            # Capture traced operations
            def capture_trace(*args, **kwargs):
                traced_operations.append(
                    {
                        "project": kwargs.get("project_name"),
                        "tags": kwargs.get("tags", []),
                        "metadata": kwargs.get("metadata", {}),
                    },
                )
                mock_context = Mock()
                mock_context.__enter__ = Mock(return_value=None)
                mock_context.__exit__ = Mock(return_value=None)
                return mock_context

            mock_tracing.side_effect = capture_trace

            # Create mock nodes
            evidence_node = MockEvidenceNode()
            compliance_node = MockComplianceNode()
            rag_node = MockRAGNode()

            # Initial state
            state = {
                "session_id": "test-session-123",
                "current_phase": "evidence_collection",
                "user_id": "user-456",
                "business_profile_id": "profile-789",
            }

            # Execute workflow with tracing
            state = await evidence_node.process_evidence(state=state)
            state = await evidence_node.validate_evidence(state=state)
            state["current_phase"] = "compliance_check"
            state = await compliance_node.check_compliance(state=state)
            state["current_phase"] = "document_retrieval"
            state = await rag_node.retrieve_documents(state=state)

            # Verify workflow completed
            assert state["evidence_processed"] is True
            assert state["evidence_validated"] is True
            assert state["compliance_checked"] is True
            assert state["compliance_score"] == 85
            assert len(state["documents_retrieved"]) == 3

            # Verify tracing was called for each operation
            assert len(traced_operations) == 4

            # Verify trace metadata
            for trace in traced_operations:
                assert trace["project"] == "test-project"
                assert "session:test-session-123" in trace["tags"]

            # Verify phase tracking
            evidence_traces = [t for t in traced_operations if "mock.process_evidence" in t["tags"]]
            assert "phase:evidence_collection" in evidence_traces[0]["tags"]

            compliance_traces = [
                t for t in traced_operations if "mock.check_compliance" in t["tags"]
            ]
            assert "phase:compliance_check" in compliance_traces[0]["tags"]

    async def test_workflow_with_tracing_disabled(self, monkeypatch):
        """Test workflow executes correctly when tracing is disabled."""
        # Disable tracing
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

        # Create mock nodes
        evidence_node = MockEvidenceNode()
        compliance_node = MockComplianceNode()

        # Initial state
        state = {"session_id": "test-session-456", "user_id": "user-789"}

        # Execute workflow without tracing
        state = await evidence_node.process_evidence(state=state)
        state = await compliance_node.check_compliance(state=state)

        # Verify workflow completed without tracing
        assert state["evidence_processed"] is True
        assert state["compliance_checked"] is True

    async def test_concurrent_node_execution_with_tracing(self, monkeypatch):
        """Test concurrent node execution with tracing."""
        # Enable tracing
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")

        traced_operations = []

        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            # Capture traced operations
            def capture_trace(*args, **kwargs):
                traced_operations.append(
                    {
                        "tags": kwargs.get("tags", []),
                        "metadata": kwargs.get("metadata", {}),
                    },
                )
                mock_context = Mock()
                mock_context.__enter__ = Mock(return_value=None)
                mock_context.__exit__ = Mock(return_value=None)
                return mock_context

            mock_tracing.side_effect = capture_trace

            # Create multiple node instances
            evidence_nodes = [MockEvidenceNode() for _ in range(3)]

            # Create multiple states with different session IDs
            states = [{"session_id": f"session-{i}", "data": f"data-{i}"} for i in range(3)]

            # Execute nodes concurrently
            tasks = [evidence_nodes[i].process_evidence(state=states[i]) for i in range(3)]

            results = await asyncio.gather(*tasks)

            # Verify all executions completed
            assert all(r["evidence_processed"] for r in results)

            # Verify each execution was traced with correct session
            assert len(traced_operations) == 3
            for _i, trace in enumerate(traced_operations):
                assert any((f"session-{j}" in tag for j in range(3) for tag in trace["tags"]))

    async def test_error_handling_with_tracing(self, monkeypatch):
        """Test error handling in traced functions."""
        # Enable tracing
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")

        class ErrorNode:
            @with_langsmith_tracing("error.test")
            async def failing_operation(self, state: Dict[str, Any]) -> Dict[str, Any]:
                """Operation that raises an error."""
                raise ValueError("Test error in operation")

        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_context = Mock()
            mock_context.__enter__ = Mock(return_value=None)
            mock_context.__exit__ = Mock(return_value=None)
            mock_tracing.return_value = mock_context

            error_node = ErrorNode()
            state = {"session_id": "error-test"}

            # Verify error is propagated correctly
            with pytest.raises(ValueError, match="Test error in operation"):
                await error_node.failing_operation(state=state)

            # Verify tracing was still attempted
            assert mock_tracing.called

    async def test_nested_traced_operations(self, monkeypatch):
        """Test nested operations with tracing."""
        # Enable tracing
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")

        traced_operations = []

        class NestedNode:
            @with_langsmith_tracing("nested.outer")
            async def outer_operation(self, state: Dict[str, Any]) -> Dict[str, Any]:
                """Outer operation that calls inner."""
                state["outer_called"] = True
                state = await self.inner_operation(state=state)
                return state

            @with_langsmith_tracing("nested.inner")
            async def inner_operation(self, state: Dict[str, Any]) -> Dict[str, Any]:
                """Inner operation."""
                state["inner_called"] = True
                return state

        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:

            def capture_trace(*args, **kwargs):
                traced_operations.append({"tags": kwargs.get("tags", [])})
                mock_context = Mock()
                mock_context.__enter__ = Mock(return_value=None)
                mock_context.__exit__ = Mock(return_value=None)
                return mock_context

            mock_tracing.side_effect = capture_trace

            nested_node = NestedNode()
            state = {"session_id": "nested-test"}

            state = await nested_node.outer_operation(state=state)

            # Verify both operations completed
            assert state["outer_called"] is True
            assert state["inner_called"] is True

            # Verify both operations were traced
            assert len(traced_operations) == 2
            assert any("nested.outer" in tag for tag in traced_operations[0]["tags"])
            assert any("nested.inner" in tag for tag in traced_operations[1]["tags"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
