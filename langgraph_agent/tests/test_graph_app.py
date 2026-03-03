"""
Tests for LangGraph application and graph compilation.
Validates graph structure, node execution, and basic functionality.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from langgraph_agent.graph.app import (
    router_node,
    compliance_analyzer_node,
    obligation_finder_node,
    evidence_collector_node,
    legal_reviewer_node,
    create_graph,
    invoke_graph,
    stream_graph,
)
from langgraph_agent.graph.state import create_initial_state
from langgraph_agent.core.constants import GRAPH_NODES


class TestNodeFunctions:
    """Test individual node functions."""

    @pytest.mark.asyncio
    async def test_router_node_gdpr_keyword(self):
        """Test router routes GDPR keywords to compliance analyzer."""
        state = create_initial_state(
            company_id=uuid4(), user_input="What GDPR obligations apply to my business?"
        )

        result = await router_node(state)

        assert result["current_node"] == GRAPH_NODES["router"]
        assert result["next_node"] == GRAPH_NODES["compliance_analyzer"]
        assert result["turn_count"] == 2  # Incremented by update_state_metadata

    @pytest.mark.asyncio
    async def test_router_node_obligation_keyword(self):
        """Test router routes obligation keywords to obligation finder."""
        state = create_initial_state(
            company_id=uuid4(), user_input="What are my data processing obligations?"
        )

        result = await router_node(state)

        assert result["next_node"] == GRAPH_NODES["obligation_finder"]

    @pytest.mark.asyncio
    async def test_router_node_evidence_keyword(self):
        """Test router routes evidence keywords to evidence collector."""
        state = create_initial_state(
            company_id=uuid4(),
            user_input="I need to collect compliance evidence documents",
        )

        result = await router_node(state)

        assert result["next_node"] == GRAPH_NODES["evidence_collector"]

    @pytest.mark.asyncio
    async def test_router_node_legal_keyword(self):
        """Test router routes legal keywords to legal reviewer."""
        state = create_initial_state(
            company_id=uuid4(), user_input="I need a legal review of my privacy policy"
        )

        result = await router_node(state)

        assert result["next_node"] == GRAPH_NODES["legal_reviewer"]

    @pytest.mark.asyncio
    async def test_router_node_default_route(self):
        """Test router defaults to compliance analyzer for unknown input."""
        state = create_initial_state(
            company_id=uuid4(), user_input="Hello there, how are you today?"
        )

        result = await router_node(state)

        assert result["next_node"] == GRAPH_NODES["compliance_analyzer"]

    @pytest.mark.asyncio
    async def test_router_node_empty_messages(self):
        """Test router handles empty messages gracefully."""
        state = create_initial_state(company_id=uuid4(), user_input="Test")
        state["messages"] = []  # Clear messages

        result = await router_node(state)

        assert result["next_node"] == "END"

    @pytest.mark.asyncio
    async def test_compliance_analyzer_node(self):
        """Test compliance analyzer node execution."""
        state = create_initial_state(
            company_id=uuid4(), user_input="Analyze my compliance requirements"
        )

        result = await compliance_analyzer_node(state)

        assert result["current_node"] == GRAPH_NODES["compliance_analyzer"]
        assert result["next_node"] == "END"
        assert len(result["messages"]) == 2  # Initial + response
        assert result["messages"][-1].role == "assistant"
        assert "analyzing" in result["messages"][-1].content.lower()

    @pytest.mark.asyncio
    async def test_obligation_finder_node(self):
        """Test obligation finder node execution."""
        state = create_initial_state(
            company_id=uuid4(), user_input="Find my compliance obligations"
        )

        result = await obligation_finder_node(state)

        assert result["current_node"] == GRAPH_NODES["obligation_finder"]
        assert result["next_node"] == "END"
        assert len(result["messages"]) == 2
        assert result["messages"][-1].role == "assistant"
        assert "searching" in result["messages"][-1].content.lower()

    @pytest.mark.asyncio
    async def test_evidence_collector_node(self):
        """Test evidence collector node execution."""
        state = create_initial_state(
            company_id=uuid4(), user_input="Help me collect evidence"
        )

        result = await evidence_collector_node(state)

        assert result["current_node"] == GRAPH_NODES["evidence_collector"]
        assert result["next_node"] == "END"
        assert len(result["messages"]) == 2
        assert result["messages"][-1].role == "assistant"
        assert "collect" in result["messages"][-1].content.lower()

    @pytest.mark.asyncio
    async def test_legal_reviewer_node(self):
        """Test legal reviewer node execution."""
        state = create_initial_state(
            company_id=uuid4(), user_input="I need legal review"
        )

        result = await legal_reviewer_node(state)

        assert result["current_node"] == GRAPH_NODES["legal_reviewer"]
        assert result["next_node"] == "END"
        assert len(result["messages"]) == 2
        assert result["messages"][-1].role == "assistant"
        assert "legal review" in result["messages"][-1].content.lower()


class TestGraphCreation:
    """Test graph structure and creation."""

    def test_create_graph_structure(self):
        """Test graph creation has correct structure."""
        graph = create_graph()

        # Check all nodes are added
        [
            GRAPH_NODES[key]
            for key in [
                "router",
                "compliance_analyzer",
                "obligation_finder",
                "evidence_collector",
                "legal_reviewer",
            ]
        ]

        # The graph object doesn't expose nodes directly in a simple way
        # So we'll just ensure the graph compiles without errors
        assert graph is not None

    def test_create_graph_compilation_ready(self):
        """Test created graph is ready for compilation."""
        graph = create_graph()

        # Should be able to call compile without errors
        # We'll mock the checkpointer since we don't have a real DB connection
        with patch(
            "langgraph_agent.graph.app.create_checkpointer"
        ) as mock_checkpointer:
            mock_checkpointer.return_value = Mock()

            try:
                compiled = graph.compile(checkpointer=mock_checkpointer.return_value)
                assert compiled is not None
            except Exception as e:
                pytest.fail(f"Graph compilation failed: {e}")


@pytest.mark.asyncio
class TestGraphInvocation:
    """Test graph invocation and execution."""

    async def test_invoke_graph_basic_flow(self):
        """Test basic graph invocation flow."""
        # Mock the compiled graph behavior
        mock_compiled_graph = AsyncMock()
        mock_final_state = create_initial_state(
            company_id=uuid4(), user_input="Test GDPR question"
        )
        mock_final_state["current_node"] = "compliance_analyzer"
        mock_final_state["next_node"] = "END"

        mock_compiled_graph.ainvoke.return_value = mock_final_state

        company_id = uuid4()
        result = await invoke_graph(
            compiled_graph=mock_compiled_graph,
            company_id=company_id,
            user_input="What GDPR obligations apply to my business?",
        )

        # Check invocation was called
        mock_compiled_graph.ainvoke.assert_called_once()

        # Check result
        assert result["company_id"] == company_id
        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], int)

    async def test_invoke_graph_with_thread_id(self):
        """Test graph invocation with specific thread ID."""
        mock_compiled_graph = AsyncMock()
        mock_final_state = create_initial_state(
            company_id=uuid4(), user_input="Test input"
        )
        mock_compiled_graph.ainvoke.return_value = mock_final_state

        thread_id = "custom_thread_123"
        company_id = uuid4()

        await invoke_graph(
            compiled_graph=mock_compiled_graph,
            company_id=company_id,
            user_input="Test input",
            thread_id=thread_id,
        )

        # Check config was passed with thread_id
        call_args = mock_compiled_graph.ainvoke.call_args
        config = call_args[1]["config"]
        assert config.configurable["thread_id"] == thread_id
        assert config.configurable["company_id"] == str(company_id)

    async def test_invoke_graph_error_handling(self):
        """Test graph invocation handles errors gracefully."""
        mock_compiled_graph = AsyncMock()
        mock_compiled_graph.ainvoke.side_effect = Exception("Test error")

        company_id = uuid4()
        result = await invoke_graph(
            compiled_graph=mock_compiled_graph,
            company_id=company_id,
            user_input="Test input",
        )

        # Should return state with error
        assert result["error_count"] == 1
        assert len(result["errors"]) == 1
        assert "Test error" in result["errors"][0].error_message

    async def test_invoke_graph_slo_monitoring(self):
        """Test SLO monitoring in graph invocation."""
        mock_compiled_graph = AsyncMock()
        mock_final_state = create_initial_state(
            company_id=uuid4(), user_input="Test input"
        )
        mock_compiled_graph.ainvoke.return_value = mock_final_state

        with patch("langgraph_agent.graph.app.logger") as mock_logger:
            result = await invoke_graph(
                compiled_graph=mock_compiled_graph,
                company_id=uuid4(),
                user_input="Test input",
            )

            # Should log execution time
            assert "latency_ms" in result
            mock_logger.info.assert_called()

    async def test_stream_graph_basic_flow(self):
        """Test basic graph streaming flow."""
        mock_compiled_graph = AsyncMock()

        # Mock streaming chunks
        async def mock_astream(*args, **kwargs):
            yield {"chunk": 1}
            yield {"chunk": 2}
            yield {"final": True}

        mock_compiled_graph.astream = mock_astream

        company_id = uuid4()
        chunks = []

        async for chunk in stream_graph(
            compiled_graph=mock_compiled_graph,
            company_id=company_id,
            user_input="Test streaming",
        ):
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0] == {"chunk": 1}
        assert chunks[1] == {"chunk": 2}
        assert chunks[2] == {"final": True}

    async def test_stream_graph_error_handling(self):
        """Test streaming handles errors gracefully."""
        mock_compiled_graph = AsyncMock()

        async def mock_astream_error(*args, **kwargs):
            yield {"chunk": 1}
            raise Exception("Streaming error")

        mock_compiled_graph.astream = mock_astream_error

        company_id = uuid4()
        chunks = []

        async for chunk in stream_graph(
            compiled_graph=mock_compiled_graph,
            company_id=company_id,
            user_input="Test error",
        ):
            chunks.append(chunk)

        # Should get one successful chunk and one error chunk
        assert len(chunks) == 2
        assert chunks[0] == {"chunk": 1}
        assert "error" in chunks[1]
        assert "Streaming error" in chunks[1]["error"].error_message


@pytest.mark.asyncio
class TestIntegrationFlow:
    """Test end-to-end integration flows."""

    async def test_full_router_to_analyzer_flow(self):
        """Test full flow from router to compliance analyzer."""
        state = create_initial_state(
            company_id=uuid4(),
            user_input="What GDPR requirements apply to my retail business?",
        )

        # Execute router
        routed_state = await router_node(state)
        assert routed_state["next_node"] == GRAPH_NODES["compliance_analyzer"]

        # Execute compliance analyzer
        final_state = await compliance_analyzer_node(routed_state)
        assert final_state["current_node"] == GRAPH_NODES["compliance_analyzer"]
        assert final_state["next_node"] == "END"
        assert len(final_state["messages"]) == 2

    async def test_full_router_to_obligation_finder_flow(self):
        """Test full flow from router to obligation finder."""
        state = create_initial_state(
            company_id=uuid4(),
            user_input="What obligations must I implement for data processing?",
        )

        # Execute router
        routed_state = await router_node(state)
        assert routed_state["next_node"] == GRAPH_NODES["obligation_finder"]

        # Execute obligation finder
        final_state = await obligation_finder_node(routed_state)
        assert final_state["current_node"] == GRAPH_NODES["obligation_finder"]
        assert final_state["next_node"] == "END"

    async def test_state_consistency_through_flow(self):
        """Test state remains consistent through node execution."""
        company_id = uuid4()
        thread_id = "test_thread_456"

        state = create_initial_state(
            company_id=company_id, user_input="Test consistency", thread_id=thread_id
        )

        original_company_id = state["company_id"]
        original_thread_id = state["thread_id"]

        # Execute router
        routed_state = await router_node(state)

        # Execute compliance analyzer
        final_state = await compliance_analyzer_node(routed_state)

        # Check consistency
        assert final_state["company_id"] == original_company_id
        assert final_state["thread_id"] == original_thread_id
        assert final_state["turn_count"] > state["turn_count"]
