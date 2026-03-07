"""
Tenancy validation tests for LangGraph compliance agent.
Ensures proper company_id enforcement and data isolation across all components.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4, UUID
from datetime import datetime

from langgraph_agent.graph.state import create_initial_state, update_state_metadata
from langgraph_agent.graph.app import invoke_graph, stream_graph
from langgraph_agent.agents.tool_manager import ToolManager
from langgraph_agent.core.models import SafeFallbackResponse


class TestStateTenancy:
    """Test tenancy enforcement in state management."""

    def test_state_creation_requires_company_id(self):
        """Test that state creation requires company_id."""
        company_id = uuid4()

        state = create_initial_state(company_id=company_id, user_input="Test message")

        assert state["company_id"] == company_id
        assert isinstance(state["company_id"], UUID)

    def test_state_isolation_between_companies(self):
        """Test that states for different companies are isolated."""
        company_a = uuid4()
        company_b = uuid4()

        state_a = create_initial_state(
            company_id=company_a, user_input="Company A message", thread_id="thread_a"
        )

        state_b = create_initial_state(
            company_id=company_b, user_input="Company B message", thread_id="thread_b"
        )

        # States should be completely separate
        assert state_a["company_id"] != state_b["company_id"]
        assert state_a["thread_id"] != state_b["thread_id"]
        assert state_a["messages"][0].content != state_b["messages"][0].content

        # Modifying one should not affect the other
        state_a["metadata"]["test_key"] = "test_value"
        assert "test_key" not in state_b["metadata"]

    def test_state_thread_isolation_within_company(self):
        """Test thread isolation within the same company."""
        company_id = uuid4()

        state_thread1 = create_initial_state(
            company_id=company_id, user_input="Thread 1 message", thread_id="thread_1"
        )

        state_thread2 = create_initial_state(
            company_id=company_id, user_input="Thread 2 message", thread_id="thread_2"
        )

        # Same company, different threads
        assert state_thread1["company_id"] == state_thread2["company_id"]
        assert state_thread1["thread_id"] != state_thread2["thread_id"]
        assert state_thread1["messages"][0].content != state_thread2["messages"][0].content

    def test_state_user_isolation(self):
        """Test user isolation within company and thread."""
        company_id = uuid4()
        thread_id = "shared_thread"
        user_a = uuid4()
        user_b = uuid4()

        state_user_a = create_initial_state(
            company_id=company_id,
            user_input="User A message",
            thread_id=thread_id,
            user_id=user_a,
        )

        state_user_b = create_initial_state(
            company_id=company_id,
            user_input="User B message",
            thread_id=thread_id,
            user_id=user_b,
        )

        # Different user IDs but potentially shared thread
        assert state_user_a["user_id"] != state_user_b["user_id"]
        assert state_user_a["company_id"] == state_user_b["company_id"]
        assert state_user_a["thread_id"] == state_user_b["thread_id"]


class TestToolTenancy:
    """Test tenancy enforcement in tool execution."""

    @pytest.mark.asyncio
    async def test_tool_manager_company_id_injection(self):
        """Test that ToolManager properly injects company_id."""
        manager = ToolManager("test_secret")
        company_id = uuid4()
        thread_id = "test_thread"

        # Mock tool execution to verify company_id is passed
        with patch.object(manager.tools["evidence_collection"], "_execute") as mock_execute:
            mock_execute.return_value = {"result": "success"}

            await manager.execute_tool(
                tool_name="evidence_collection",
                company_id=company_id,
                thread_id=thread_id,
                frameworks=["GDPR"],
            )

            # Verify company_id was injected
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            assert "company_id" in call_args.kwargs
            assert call_args.kwargs["company_id"] == str(company_id)

    @pytest.mark.asyncio
    async def test_tool_execution_company_id_validation(self):
        """Test tool execution validates company_id presence."""
        manager = ToolManager("test_secret")
        company_id = uuid4()
        thread_id = "test_thread"

        # Test that tool execution includes company context
        result = await manager.execute_tool(
            tool_name="compliance_analysis",
            company_id=company_id,
            thread_id=thread_id,
            business_profile={"industry": "tech"},
            frameworks=["GDPR"],
        )

        # Result should be successful and include company context
        assert result.success
        assert result.tool_name == "compliance_analysis"
        # Tool manager should have tracked this execution for the company

    @pytest.mark.asyncio
    async def test_parallel_tool_execution_tenancy(self):
        """Test parallel tool execution maintains tenancy."""
        manager = ToolManager("test_secret")
        company_a = uuid4()
        company_b = uuid4()
        thread_a = "thread_a"
        thread_b = "thread_b"

        tool_configs_a = [
            {
                "tool": "compliance_analysis",
                "kwargs": {
                    "business_profile": {"industry": "retail"},
                    "frameworks": ["GDPR"],
                },
            }
        ]

        tool_configs_b = [
            {
                "tool": "compliance_analysis",
                "kwargs": {
                    "business_profile": {"industry": "finance"},
                    "frameworks": ["PCI_DSS"],
                },
            }
        ]

        # Execute for both companies in parallel
        results_a, results_b = await asyncio.gather(
            manager.execute_parallel_tools(tool_configs_a, company_a, thread_a),
            manager.execute_parallel_tools(tool_configs_b, company_b, thread_b),
        )

        # Both should succeed
        assert len(results_a) == 1
        assert len(results_b) == 1
        assert results_a[0].success
        assert results_b[0].success

        # Results should be different (different company contexts)
        assert results_a[0].result != results_b[0].result

    @pytest.mark.asyncio
    async def test_tool_stats_isolation(self):
        """Test that tool statistics are properly isolated by execution context."""
        manager = ToolManager("test_secret")
        company_a = uuid4()
        company_b = uuid4()

        # Execute tools for different companies
        await manager.execute_tool(
            "compliance_analysis",
            company_a,
            "thread_a",
            business_profile={"industry": "tech"},
            frameworks=["GDPR"],
        )

        await manager.execute_tool(
            "compliance_analysis",
            company_b,
            "thread_b",
            business_profile={"industry": "retail"},
            frameworks=["GDPR"],
        )

        # Tool stats should reflect both executions
        stats = manager.get_tool_stats("compliance_analysis")
        assert stats["total_executions"] == 2
        assert stats["successful_executions"] == 2


class TestGraphTenancy:
    """Test tenancy enforcement in graph execution."""

    @pytest.mark.asyncio
    async def test_graph_invocation_company_isolation(self):
        """Test graph invocation maintains company isolation."""
        # Mock compiled graph
        mock_graph = AsyncMock()

        # Different companies
        company_a = uuid4()
        company_b = uuid4()

        # Mock different responses for different companies
        def mock_invoke(state, config=None):
            company_id = UUID(config.configurable["company_id"])
            state["company_id"] = company_id
            if company_id == company_a:
                state["messages"].append(Mock(role="assistant", content="Response for Company A"))
            else:
                state["messages"].append(Mock(role="assistant", content="Response for Company B"))
            return state

        mock_graph.ainvoke.side_effect = mock_invoke

        # Invoke for both companies
        result_a = await invoke_graph(
            compiled_graph=mock_graph, company_id=company_a, user_input="Test input A"
        )

        result_b = await invoke_graph(
            compiled_graph=mock_graph, company_id=company_b, user_input="Test input B"
        )

        # Verify company isolation
        assert result_a["company_id"] == company_a
        assert result_b["company_id"] == company_b

        # Verify different responses
        assert result_a["messages"][-1].content != result_b["messages"][-1].content

    @pytest.mark.asyncio
    async def test_graph_config_tenancy(self):
        """Test that graph configuration includes proper tenancy info."""
        mock_graph = AsyncMock()
        company_id = uuid4()
        thread_id = "test_thread"

        # Capture config passed to graph
        captured_config = None

        def capture_config(state, config=None):
            nonlocal captured_config
            captured_config = config
            return state

        mock_graph.ainvoke.side_effect = capture_config

        await invoke_graph(
            compiled_graph=mock_graph,
            company_id=company_id,
            user_input="Test input",
            thread_id=thread_id,
        )

        # Verify config contains tenancy information
        assert captured_config is not None
        assert "configurable" in captured_config.__dict__
        assert captured_config.configurable["company_id"] == str(company_id)
        assert captured_config.configurable["thread_id"] == thread_id

    @pytest.mark.asyncio
    async def test_stream_graph_tenancy(self):
        """Test streaming graph maintains tenancy."""
        mock_graph = AsyncMock()
        company_id = uuid4()
        thread_id = "test_stream"

        # Mock streaming chunks with company context
        async def mock_stream(state, config=None):
            company_from_config = UUID(config.configurable["company_id"])
            yield {"company_id": company_from_config, "chunk": 1}
            yield {"company_id": company_from_config, "chunk": 2}

        mock_graph.astream.side_effect = mock_stream

        chunks = []
        async for chunk in stream_graph(
            compiled_graph=mock_graph,
            company_id=company_id,
            user_input="Test stream",
            thread_id=thread_id,
        ):
            chunks.append(chunk)

        # Verify all chunks maintain company context
        assert len(chunks) == 2
        for chunk in chunks:
            assert chunk["company_id"] == company_id


class TestErrorTenancy:
    """Test tenancy enforcement in error handling."""

    def test_safe_fallback_response_tenancy(self):
        """Test SafeFallbackResponse includes proper tenancy info."""
        company_id = uuid4()
        thread_id = "error_thread"

        fallback = SafeFallbackResponse(
            error_message="Test error",
            error_details={"error_type": "validation"},
            company_id=company_id,
            thread_id=thread_id,
        )

        assert fallback.company_id == company_id
        assert fallback.thread_id == thread_id

        # Serialization should maintain tenancy
        fallback_dict = fallback.model_dump()
        assert fallback_dict["company_id"] == company_id
        assert fallback_dict["thread_id"] == thread_id

    @pytest.mark.asyncio
    async def test_tool_error_fallback_tenancy(self):
        """Test tool errors maintain tenancy in fallback responses."""
        manager = ToolManager("test_secret")
        company_id = uuid4()
        thread_id = "error_thread"

        # Execute non-existent tool to trigger error
        result = await manager.execute_tool(
            tool_name="nonexistent_tool", company_id=company_id, thread_id=thread_id
        )

        # Should return SafeFallbackResponse with proper tenancy
        assert isinstance(result, SafeFallbackResponse)
        assert result.company_id == company_id
        assert result.thread_id == thread_id

    @pytest.mark.asyncio
    async def test_graph_error_tenancy(self):
        """Test graph errors maintain tenancy context."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke.side_effect = Exception("Graph execution failed")

        company_id = uuid4()
        thread_id = "error_thread"

        result = await invoke_graph(
            compiled_graph=mock_graph,
            company_id=company_id,
            user_input="Test error",
            thread_id=thread_id,
        )

        # Result should be initial state with error
        assert result["company_id"] == company_id
        assert result["thread_id"] == thread_id
        assert result["error_count"] == 1
        assert len(result["errors"]) == 1

        # Error should maintain tenancy
        error = result["errors"][0]
        assert error.company_id == company_id
        assert error.thread_id == thread_id


class TestDataIsolation:
    """Test data isolation between tenants."""

    def test_conversation_history_isolation(self):
        """Test conversation history isolation between companies."""
        company_a = uuid4()
        company_b = uuid4()

        # Create states with conversation history
        state_a = create_initial_state(company_id=company_a, user_input="Company A conversation")
        state_a["conversation_history"].append(
            {"role": "assistant", "content": "Company A response"}
        )

        state_b = create_initial_state(company_id=company_b, user_input="Company B conversation")
        state_b["conversation_history"].append(
            {"role": "assistant", "content": "Company B response"}
        )

        # Histories should be completely separate
        assert len(state_a["conversation_history"]) == 1
        assert len(state_b["conversation_history"]) == 1
        assert (
            state_a["conversation_history"][0]["content"]
            != state_b["conversation_history"][0]["content"]
        )

    def test_context_data_isolation(self):
        """Test context data isolation between companies."""
        company_a = uuid4()
        company_b = uuid4()

        state_a = create_initial_state(company_id=company_a, user_input="Test A")
        state_a["context_data"]["business_profile"] = {
            "industry": "technology",
            "employees": 100,
        }

        state_b = create_initial_state(company_id=company_b, user_input="Test B")
        state_b["context_data"]["business_profile"] = {
            "industry": "retail",
            "employees": 50,
        }

        # Context data should be isolated
        assert state_a["context_data"]["business_profile"]["industry"] == "technology"
        assert state_b["context_data"]["business_profile"]["industry"] == "retail"
        assert (
            state_a["context_data"]["business_profile"]["employees"]
            != state_b["context_data"]["business_profile"]["employees"]
        )

    def test_tool_results_isolation(self):
        """Test tool results isolation between companies."""
        company_a = uuid4()
        company_b = uuid4()

        state_a = create_initial_state(company_id=company_a, user_input="Test A")
        state_b = create_initial_state(company_id=company_b, user_input="Test B")

        # Add different tool results
        from langgraph_agent.agents.tool_manager import ToolResult

        result_a = ToolResult(
            tool_name="compliance_analysis",
            success=True,
            result={"compliance_score": 0.85},
            execution_time_ms=200,
        )

        result_b = ToolResult(
            tool_name="compliance_analysis",
            success=True,
            result={"compliance_score": 0.72},
            execution_time_ms=250,
        )

        state_a["tool_results"].append(result_a)
        state_b["tool_results"].append(result_b)

        # Tool results should be isolated
        assert len(state_a["tool_results"]) == 1
        assert len(state_b["tool_results"]) == 1
        assert (
            state_a["tool_results"][0].result["compliance_score"]
            != state_b["tool_results"][0].result["compliance_score"]
        )


class TestCrossCompanySecurityValidation:
    """Test security measures preventing cross-company data access."""

    def test_company_id_required_everywhere(self):
        """Test that company_id is required in all operations."""
        # State creation
        with pytest.raises(TypeError):
            create_initial_state(user_input="test")  # Missing company_id

        # Tool execution would require company_id (tested in tool manager tests)
        manager = ToolManager("test_secret")

        # Should not be able to call execute_tool without company_id
        with pytest.raises(TypeError):
            asyncio.run(
                manager.execute_tool(
                    tool_name="compliance_analysis",
                    # Missing company_id
                    thread_id="test",
                    business_profile={"industry": "tech"},
                )
            )

    def test_uuid_validation(self):
        """Test that company_id must be valid UUID."""
        # Valid UUID should work
        valid_uuid = uuid4()
        state = create_initial_state(company_id=valid_uuid, user_input="test")
        assert state["company_id"] == valid_uuid

        # Invalid UUID should raise error
        with pytest.raises((TypeError, ValueError)):
            create_initial_state(company_id="invalid-uuid-string", user_input="test")

    def test_thread_id_isolation_enforcement(self):
        """Test that thread_id isolation is enforced."""
        company_id = uuid4()

        # Same company, different threads should be isolated
        state1 = create_initial_state(
            company_id=company_id, user_input="message 1", thread_id="thread-001"
        )

        state2 = create_initial_state(
            company_id=company_id, user_input="message 2", thread_id="thread-002"
        )

        # Should be completely separate despite same company
        assert state1["thread_id"] != state2["thread_id"]
        assert state1["messages"][0].content != state2["messages"][0].content

        # Modifying one thread should not affect the other
        state1["metadata"]["custom_data"] = "thread-1-data"
        assert "custom_data" not in state2["metadata"]


class TestAuditTrails:
    """Test audit trail generation for tenancy compliance."""

    def test_state_metadata_includes_tenancy_info(self):
        """Test that state metadata includes proper tenancy information."""
        company_id = uuid4()
        user_id = uuid4()
        thread_id = "audit_thread"

        state = create_initial_state(
            company_id=company_id,
            user_input="Audit test",
            thread_id=thread_id,
            user_id=user_id,
        )

        # Metadata should be available for audit trails
        assert state["company_id"] == company_id
        assert state["user_id"] == user_id
        assert state["thread_id"] == thread_id
        assert isinstance(state["created_at"], datetime)
        assert isinstance(state["updated_at"], datetime)

        # Turn count should track interactions for audit
        assert state["turn_count"] == 1

        # Update should increment audit info
        updated_state = update_state_metadata(state)
        assert updated_state["turn_count"] == 2
        assert updated_state["updated_at"] > state["updated_at"]

    def test_error_audit_trails(self):
        """Test that errors generate proper audit trails."""
        company_id = uuid4()
        thread_id = "error_audit"

        error = SafeFallbackResponse(
            error_message="Audit test error",
            error_details={"test": "audit"},
            company_id=company_id,
            thread_id=thread_id,
        )

        # Error should include full audit context
        assert error.company_id == company_id
        assert error.thread_id == thread_id
        assert isinstance(error.timestamp, datetime)
        assert error.error_details["test"] == "audit"

        # Error should serialize with audit info
        error_dict = error.model_dump()
        assert error_dict["company_id"] == company_id
        assert error_dict["thread_id"] == thread_id
        assert "timestamp" in error_dict
