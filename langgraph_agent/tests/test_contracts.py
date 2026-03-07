"""
Contract testing for LangGraph compliance agent.
Validates schemas, interfaces, and data contracts across all components.
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timezone

from pydantic import ValidationError

from langgraph_agent.core.models import (
    GraphMessage,
    SafeFallbackResponse,
    ComplianceAnalysisRequest,
    ComplianceAnalysisResponse,
)
from langgraph_agent.graph.state import create_initial_state, update_state_metadata
from langgraph_agent.agents.tool_manager import (
    ToolResult,
    ToolError,
    ToolCategory,
    ToolPriority,
)
from langgraph_agent.core.constants import (
    GRAPH_NODES,
    AUTONOMY_LEVELS,
    SLO_P95_LATENCY_MS,
)


class TestCoreModelContracts:
    """Test core model schemas and validation."""

    def test_graph_message_schema(self):
        """Test GraphMessage schema validation."""
        # Valid message
        valid_msg = GraphMessage(
            role="user", content="Test message", timestamp=datetime.now(timezone.utc)
        )
        assert valid_msg.role == "user"
        assert valid_msg.content == "Test message"
        assert isinstance(valid_msg.timestamp, datetime)

        # Test serialization
        msg_dict = valid_msg.model_dump()
        assert "role" in msg_dict
        assert "content" in msg_dict
        assert "timestamp" in msg_dict

        # Test invalid role
        with pytest.raises(ValidationError):
            GraphMessage(
                role="invalid_role",  # Should be "user" or "assistant"
                content="Test",
                timestamp=datetime.now(timezone.utc),
            )

        # Test required fields
        with pytest.raises(ValidationError):
            GraphMessage(role="user")  # Missing content

    def test_safe_fallback_response_schema(self):
        """Test SafeFallbackResponse schema validation."""
        company_id = uuid4()
        thread_id = "test_thread"

        # Valid fallback response
        fallback = SafeFallbackResponse(
            error_message="Test error",
            error_details={"test": "details"},
            company_id=company_id,
            thread_id=thread_id,
        )

        assert fallback.error_message == "Test error"
        assert fallback.error_details == {"test": "details"}
        assert fallback.company_id == company_id
        assert fallback.thread_id == thread_id
        assert isinstance(fallback.timestamp, datetime)

        # Test serialization
        fallback_dict = fallback.model_dump()
        assert "error_message" in fallback_dict
        assert "company_id" in fallback_dict
        assert "thread_id" in fallback_dict

        # Test required fields
        with pytest.raises(ValidationError):
            SafeFallbackResponse(
                error_message="Test",
                company_id=company_id,
                # Missing thread_id
            )

    def test_compliance_analysis_request_schema(self):
        """Test ComplianceAnalysisRequest schema validation."""
        company_id = uuid4()

        # Valid request
        request = ComplianceAnalysisRequest(
            company_id=company_id,
            business_profile={
                "industry": "technology",
                "employees": 50,
                "revenue": 1000000,
            },
            frameworks=["GDPR", "UK_GDPR"],
            analysis_type="full",
        )

        assert request.company_id == company_id
        assert request.business_profile["industry"] == "technology"
        assert "GDPR" in request.frameworks
        assert request.analysis_type == "full"

        # Test default values
        minimal_request = ComplianceAnalysisRequest(
            company_id=company_id, business_profile={"industry": "retail"}
        )
        assert minimal_request.frameworks == []
        assert minimal_request.analysis_type == "basic"

        # Test invalid analysis_type
        with pytest.raises(ValidationError):
            ComplianceAnalysisRequest(
                company_id=company_id,
                business_profile={"industry": "retail"},
                analysis_type="invalid_type",
            )

    def test_compliance_analysis_response_schema(self):
        """Test ComplianceAnalysisResponse schema validation."""
        company_id = uuid4()

        # Valid response
        response = ComplianceAnalysisResponse(
            company_id=company_id,
            applicable_frameworks=["GDPR", "UK_GDPR"],
            compliance_score=0.85,
            priority_obligations=["GDPR Article 13 - Information to be provided"],
            risk_areas=["Data processing without consent"],
            recommendations=["Implement privacy policy"],
            detailed_analysis={"gdpr_score": 0.9, "risk_level": "medium"},
        )

        assert response.company_id == company_id
        assert response.compliance_score == 0.85
        assert len(response.applicable_frameworks) == 2
        assert response.detailed_analysis["gdpr_score"] == 0.9

        # Test score validation (should be 0-1)
        with pytest.raises(ValidationError):
            ComplianceAnalysisResponse(
                company_id=company_id,
                applicable_frameworks=["GDPR"],
                compliance_score=1.5,  # Invalid: > 1.0
                priority_obligations=[],
                risk_areas=[],
                recommendations=[],
            )

        with pytest.raises(ValidationError):
            ComplianceAnalysisResponse(
                company_id=company_id,
                applicable_frameworks=["GDPR"],
                compliance_score=-0.1,  # Invalid: < 0.0
                priority_obligations=[],
                risk_areas=[],
                recommendations=[],
            )


class TestStateContracts:
    """Test state management contracts."""

    def test_compliance_agent_state_structure(self):
        """Test ComplianceAgentState structure and required fields."""
        company_id = uuid4()
        user_input = "Test GDPR question"

        state = create_initial_state(company_id=company_id, user_input=user_input)

        # Test required fields exist
        required_fields = [
            "company_id",
            "thread_id",
            "user_id",
            "messages",
            "current_node",
            "next_node",
            "conversation_history",
            "context_data",
            "tool_results",
            "errors",
            "metadata",
            "turn_count",
            "error_count",
            "autonomy_level",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            assert field in state, f"Required field '{field}' missing from state"

        # Test field types
        assert isinstance(state["company_id"], UUID)
        assert isinstance(state["thread_id"], str)
        assert isinstance(state["messages"], list)
        assert isinstance(state["conversation_history"], list)
        assert isinstance(state["context_data"], dict)
        assert isinstance(state["tool_results"], list)
        assert isinstance(state["errors"], list)
        assert isinstance(state["metadata"], dict)
        assert isinstance(state["turn_count"], int)
        assert isinstance(state["error_count"], int)
        assert isinstance(state["autonomy_level"], int)
        assert isinstance(state["created_at"], datetime)
        assert isinstance(state["updated_at"], datetime)

        # Test initial values
        assert state["company_id"] == company_id
        assert len(state["messages"]) == 1
        assert state["messages"][0].content == user_input
        assert state["turn_count"] == 1
        assert state["error_count"] == 0

    def test_state_update_metadata_contract(self):
        """Test state metadata update contract."""
        state = create_initial_state(company_id=uuid4(), user_input="Test")

        original_turn_count = state["turn_count"]
        original_updated_at = state["updated_at"]

        # Add small delay to ensure timestamp changes
        import time

        time.sleep(0.001)

        updated_state = update_state_metadata(state)

        # Test that metadata was updated
        assert updated_state["turn_count"] == original_turn_count + 1
        assert updated_state["updated_at"] > original_updated_at

        # Test that other fields remain unchanged
        assert updated_state["company_id"] == state["company_id"]
        assert updated_state["thread_id"] == state["thread_id"]
        assert len(updated_state["messages"]) == len(state["messages"])

    def test_state_immutability_protection(self):
        """Test that state modifications don't break structure."""
        state = create_initial_state(company_id=uuid4(), user_input="Test")

        # Add new message
        new_message = GraphMessage(
            role="assistant", content="Response", timestamp=datetime.now(timezone.utc)
        )
        state["messages"].append(new_message)

        # State should still be valid
        assert len(state["messages"]) == 2
        assert state["messages"][-1].role == "assistant"

        # Update metadata should still work
        updated_state = update_state_metadata(state)
        assert updated_state["turn_count"] == 2


class TestToolContracts:
    """Test tool interface contracts."""

    def test_tool_result_contract(self):
        """Test ToolResult contract and serialization."""
        # Valid tool result
        result = ToolResult(
            tool_name="test_tool",
            success=True,
            result={"test": "data"},
            execution_time_ms=250,
        )

        assert result.tool_name == "test_tool"
        assert result.success is True
        assert result.result == {"test": "data"}
        assert result.execution_time_ms == 250
        assert isinstance(result.timestamp, datetime)
        assert result.error is None
        assert isinstance(result.metadata, dict)

        # Test serialization
        result_dict = result.to_dict()
        assert "tool_name" in result_dict
        assert "success" in result_dict
        assert "result" in result_dict
        assert "execution_time_ms" in result_dict
        assert "timestamp" in result_dict
        assert "metadata" in result_dict

        # Test error result
        error_result = ToolResult(
            tool_name="failing_tool",
            success=False,
            error="Test error message",
            execution_time_ms=100,
        )

        assert error_result.success is False
        assert error_result.error == "Test error message"
        assert error_result.result is None

    def test_tool_error_contract(self):
        """Test ToolError contract and fallback conversion."""
        company_id = uuid4()
        thread_id = "test_thread"

        # Valid tool error
        error = ToolError(
            tool_name="failing_tool",
            error_type="validation_error",
            message="Input validation failed",
            details={"field": "business_profile", "issue": "missing"},
        )

        assert error.tool_name == "failing_tool"
        assert error.error_type == "validation_error"
        assert error.message == "Input validation failed"
        assert error.details["field"] == "business_profile"

        # Test fallback response conversion
        fallback = error.to_fallback_response(company_id, thread_id)

        assert isinstance(fallback, SafeFallbackResponse)
        assert fallback.company_id == company_id
        assert fallback.thread_id == thread_id
        assert "failing_tool" in fallback.error_message
        assert fallback.error_details["tool_name"] == "failing_tool"
        assert fallback.error_details["error_type"] == "validation_error"

    def test_tool_category_enum_contract(self):
        """Test ToolCategory enum values."""
        # Test all expected categories exist
        expected_categories = [
            "COMPLIANCE_ANALYSIS",
            "DOCUMENT_RETRIEVAL",
            "EVIDENCE_COLLECTION",
            "LEGAL_RESEARCH",
            "REPORT_GENERATION",
            "DATA_PROCESSING",
            "INTEGRATION",
            "UTILITY",
        ]

        for category_name in expected_categories:
            assert hasattr(ToolCategory, category_name)
            category = getattr(ToolCategory, category_name)
            assert isinstance(category.value, str)

        # Test enum is string-based
        assert ToolCategory.COMPLIANCE_ANALYSIS == "compliance_analysis"
        assert ToolCategory.DOCUMENT_RETRIEVAL == "document_retrieval"

    def test_tool_priority_enum_contract(self):
        """Test ToolPriority enum values."""
        expected_priorities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        for priority_name in expected_priorities:
            assert hasattr(ToolPriority, priority_name)
            priority = getattr(ToolPriority, priority_name)
            assert isinstance(priority.value, str)

        # Test enum values
        assert ToolPriority.LOW == "low"
        assert ToolPriority.MEDIUM == "medium"
        assert ToolPriority.HIGH == "high"
        assert ToolPriority.CRITICAL == "critical"


class TestConstantsContracts:
    """Test that constants maintain expected contracts."""

    def test_graph_nodes_contract(self):
        """Test GRAPH_NODES constant structure."""
        # Test all expected nodes exist
        expected_nodes = [
            "router",
            "compliance_analyzer",
            "obligation_finder",
            "evidence_collector",
            "legal_reviewer",
        ]

        for node_name in expected_nodes:
            assert node_name in GRAPH_NODES
            assert isinstance(GRAPH_NODES[node_name], str)
            assert len(GRAPH_NODES[node_name]) > 0

        # Test node names are valid (no special characters that could break routing)
        for node_value in GRAPH_NODES.values():
            assert node_value.replace("_", "").replace("-", "").isalnum()

    def test_autonomy_levels_contract(self):
        """Test AUTONOMY_LEVELS constant structure."""
        # Test expected autonomy levels exist
        expected_levels = ["human_in_loop", "trusted_advisor", "autonomous"]

        for level_name in expected_levels:
            assert level_name in AUTONOMY_LEVELS
            assert isinstance(AUTONOMY_LEVELS[level_name], int)
            assert AUTONOMY_LEVELS[level_name] >= 0

        # Test levels are ordered correctly
        assert AUTONOMY_LEVELS["human_in_loop"] < AUTONOMY_LEVELS["trusted_advisor"]
        assert AUTONOMY_LEVELS["trusted_advisor"] < AUTONOMY_LEVELS["autonomous"]

    def test_slo_constants_contract(self):
        """Test SLO constants are properly defined."""
        # Test SLO_P95_LATENCY_MS exists and is reasonable
        assert isinstance(SLO_P95_LATENCY_MS, (int, float))
        assert SLO_P95_LATENCY_MS > 0
        assert SLO_P95_LATENCY_MS <= 10000  # Should be <= 10 seconds for reasonable UX


class TestAPIContracts:
    """Test API interface contracts."""

    @pytest.mark.asyncio
    async def test_graph_invocation_contract(self):
        """Test graph invocation interface contract."""
        # This would test the actual graph invocation interface
        # For now, we'll test the expected signature and return structure
        from langgraph_agent.graph.app import invoke_graph

        # Test function signature (should not raise)
        import inspect

        sig = inspect.signature(invoke_graph)

        expected_params = [
            "compiled_graph",
            "company_id",
            "user_input",
            "thread_id",
            "user_id",
            "autonomy_level",
        ]

        for param_name in expected_params:
            assert param_name in sig.parameters

        # Test that company_id and user_input are required
        assert sig.parameters["compiled_graph"].default == inspect.Parameter.empty
        assert sig.parameters["company_id"].default == inspect.Parameter.empty
        assert sig.parameters["user_input"].default == inspect.Parameter.empty

        # Test that thread_id, user_id are optional
        assert sig.parameters["thread_id"].default is None
        assert sig.parameters["user_id"].default is None

    @pytest.mark.asyncio
    async def test_stream_graph_contract(self):
        """Test stream graph interface contract."""
        from langgraph_agent.graph.app import stream_graph

        # Test function signature
        import inspect

        sig = inspect.signature(stream_graph)

        # Should have same parameters as invoke_graph
        expected_params = [
            "compiled_graph",
            "company_id",
            "user_input",
            "thread_id",
            "user_id",
            "autonomy_level",
        ]

        for param_name in expected_params:
            assert param_name in sig.parameters


class TestIntegrationContracts:
    """Test integration between components maintains contracts."""

    def test_state_tool_result_integration(self):
        """Test that tool results integrate properly with state."""
        state = create_initial_state(company_id=uuid4(), user_input="Test")

        # Create tool result
        tool_result = ToolResult(
            tool_name="test_tool",
            success=True,
            result={"compliance_score": 0.85},
            execution_time_ms=200,
        )

        # Add to state
        state["tool_results"].append(tool_result)

        # State should remain valid
        assert len(state["tool_results"]) == 1
        assert state["tool_results"][0].tool_name == "test_tool"

        # Should be able to update metadata
        updated_state = update_state_metadata(state)
        assert updated_state["turn_count"] == 2

    def test_error_fallback_integration(self):
        """Test that errors integrate properly with fallback responses."""
        company_id = uuid4()
        thread_id = "test_thread"

        # Create tool error
        tool_error = ToolError(
            tool_name="failing_tool",
            error_type="timeout",
            message="Tool execution timed out",
        )

        # Convert to fallback
        fallback = tool_error.to_fallback_response(company_id, thread_id)

        # Add to state
        state = create_initial_state(company_id=company_id, user_input="Test", thread_id=thread_id)
        state["errors"].append(fallback)
        state["error_count"] += 1

        # State should remain valid
        assert len(state["errors"]) == 1
        assert state["error_count"] == 1
        assert state["errors"][0].company_id == company_id


class TestBackwardCompatibility:
    """Test that changes maintain backward compatibility."""

    def test_state_serialization_compatibility(self):
        """Test that state can be serialized and maintains compatibility."""
        state = create_initial_state(company_id=uuid4(), user_input="Test compatibility")

        # Should be able to extract key data without errors
        try:
            company_id = state["company_id"]
            thread_id = state["thread_id"]
            messages = state["messages"]
            turn_count = state["turn_count"]

            # Basic validation that extraction worked
            assert isinstance(company_id, UUID)
            assert isinstance(thread_id, str)
            assert isinstance(messages, list)
            assert isinstance(turn_count, int)

        except KeyError as e:
            pytest.fail(f"State serialization compatibility broken: {e}")

    def test_message_format_compatibility(self):
        """Test that message format remains compatible."""
        # Create message using current format
        msg = GraphMessage(
            role="user", content="Test message", timestamp=datetime.now(timezone.utc)
        )

        # Should be able to access required fields
        assert hasattr(msg, "role")
        assert hasattr(msg, "content")
        assert hasattr(msg, "timestamp")

        # Should serialize to expected format
        msg_dict = msg.model_dump()
        assert "role" in msg_dict
        assert "content" in msg_dict
        assert "timestamp" in msg_dict
