"""

# Constants
DEFAULT_TIMEOUT = 30.0
MINUTE_SECONDS = 60.0


Test suite for Phase 2: Centralized error handling system.

This test suite validates:
- Error classification logic
- Retry strategies for different error types
- Exponential backoff with jitter
- Linear backoff for database errors
- Fallback activation
- Error recovery routing
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime
from langgraph.graph import END
from langgraph_agent.graph.error_handler import (
    ErrorHandlerNode,
    should_route_to_error_handler,
    get_recovery_node,
)
from langgraph_agent.graph.enhanced_state import (
    EnhancedComplianceState,
    WorkflowStatus,
    create_enhanced_initial_state,
)
from langgraph_agent.graph.enhanced_app import EnhancedComplianceGraph

from tests.test_constants import MAX_RETRIES


class TestErrorClassification:
    """Test error type classification logic."""

    def test_classify_rate_limit_error(self):
        """Test classification of rate limit errors."""
        handler = ErrorHandlerNode()
        test_cases = [
            {"error": "Rate limit exceeded", "type": ""},
            {"error": "HTTP 429: Too Many Requests", "type": ""},
            {"error": "OpenAI rate limit reached", "type": ""},
            {"error": "Too many requests, please slow down", "type": ""},
        ]
        for error_dict in test_cases:
            state = {"errors": [error_dict]}
            assert handler._classify_error(state) == "rate_limit"

    def test_classify_database_error(self):
        """Test classification of database errors."""
        handler = ErrorHandlerNode()
        test_cases = [
            {"error": "Database connection failed", "type": ""},
            {"error": "PostgreSQL connection timeout", "type": ""},
            {"error": "Neo4j server unavailable", "type": ""},
            {"error": "Connection pool exhausted", "type": ""},
        ]
        for error_dict in test_cases:
            state = {"errors": [error_dict]}
            assert handler._classify_error(state) == "database"

    def test_classify_api_error(self):
        """Test classification of API errors."""
        handler = ErrorHandlerNode()
        test_cases = [
            {"error": "API endpoint not found", "type": ""},
            {"error": "HTTP 404: Not Found", "type": ""},
            {"error": "HTTP 500: Internal Server Error", "type": ""},
            {"error": "External API call failed", "type": ""},
        ]
        for error_dict in test_cases:
            state = {"errors": [error_dict]}
            assert handler._classify_error(state) == "api"

    def test_classify_validation_error(self):
        """Test classification of validation errors."""
        handler = ErrorHandlerNode()
        test_cases = [
            {"error": "Validation failed: invalid input", "type": ""},
            {"error": "Schema validation error", "type": ""},
            {"error": "Type error: expected string got integer", "type": ""},
            {"error": "Invalid parameter value", "type": ""},
        ]
        for error_dict in test_cases:
            state = {"errors": [error_dict]}
            assert handler._classify_error(state) == "validation"

    def test_classify_timeout_error(self):
        """Test classification of timeout errors."""
        handler = ErrorHandlerNode()
        test_cases = [
            {"error": "Operation timeout", "type": ""},
            {"error": "Request timed out after 30s", "type": ""},
            {"error": "Deadline exceeded", "type": ""},
            {"error": "Query timeout reached", "type": ""},
        ]
        for error_dict in test_cases:
            state = {"errors": [error_dict]}
            assert handler._classify_error(state) == "timeout"

    def test_classify_network_error(self):
        """Test classification of network errors."""
        handler = ErrorHandlerNode()
        test_cases = [
            {"error": "Network error: connection refused", "type": ""},
            {"error": "DNS resolution failed", "type": ""},
            {"error": "Connection refused by server", "type": ""},
            {"error": "Network timeout", "type": ""},
        ]
        for error_dict in test_cases:
            state = {"errors": [error_dict]}
            assert handler._classify_error(state) == "network"

    def test_classify_by_explicit_type(self):
        """Test classification using explicit type field."""
        handler = ErrorHandlerNode()
        state = {"errors": [{"error": "Some random error", "type": "custom"}]}
        assert handler._classify_error(state) == "custom"

    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        handler = ErrorHandlerNode()
        test_cases = [
            {"error": "Something unexpected happened", "type": ""},
            {"error": "Unknown error occurred", "type": ""},
            {"error": "Mysterious failure", "type": ""},
        ]
        for error_dict in test_cases:
            state = {"errors": [error_dict]}
            assert handler._classify_error(state) == "unknown"


@pytest.mark.asyncio
class TestRetryStrategies:
    """Test different retry strategies."""

    async def test_rate_limit_exponential_backoff(self):
        """Test exponential backoff with jitter for rate limits."""
        handler = ErrorHandlerNode()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["errors"] = [{"error": "Rate limit exceeded"}]
        state["retry_count"] = 0
        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            result = await handler._handle_rate_limit(state)
            assert mock_sleep.called
            delay = mock_sleep.call_args[0][0]
            assert 2.0 <= delay <= 2.2
            assert result["should_continue"] is True
            assert result["next_node"] == "router"
            state["retry_count"] = 1
            mock_sleep.reset_mock()
            result = await handler._handle_rate_limit(state)
            delay = mock_sleep.call_args[0][0]
            assert 4.0 <= delay <= 4.4
            state["retry_count"] = 2
            mock_sleep.reset_mock()
            result = await handler._handle_rate_limit(state)
            delay = mock_sleep.call_args[0][0]
            assert 8.0 <= delay <= 8.8
            state["retry_count"] = 10
            mock_sleep.reset_mock()
            result = await handler._handle_rate_limit(state)
            delay = mock_sleep.call_args[0][0]
            assert delay <= MINUTE_SECONDS

    async def test_database_linear_backoff(self):
        """Test linear backoff for database errors."""
        handler = ErrorHandlerNode()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["errors"] = [{"error": "Database connection failed"}]
        state["retry_count"] = 0
        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            result = await handler._handle_database_error(state)
            assert mock_sleep.called
            assert mock_sleep.call_args[0][0] == 1.0
            assert result["should_continue"] is True
            state["retry_count"] = 1
            mock_sleep.reset_mock()
            result = await handler._handle_database_error(state)
            assert mock_sleep.call_args[0][0] == 2.0
            state["retry_count"] = 2
            mock_sleep.reset_mock()
            result = await handler._handle_database_error(state)
            assert mock_sleep.call_args[0][0] == MAX_RETRIES
            state["retry_count"] = 50
            mock_sleep.reset_mock()
            result = await handler._handle_database_error(state)
            assert mock_sleep.call_args[0][0] == DEFAULT_TIMEOUT

    async def test_api_error_fallback_strategy(self):
        """Test API error handling with fallback endpoints."""
        handler = ErrorHandlerNode()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["errors"] = [{"error": "API endpoint not found"}]
        state["retry_count"] = 0
        state["metadata"] = {}
        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            result = await handler._handle_api_error(state)
            assert "use_fallback_api" not in result["metadata"]
            state["retry_count"] = 1
            result = await handler._handle_api_error(state)
            assert "use_fallback_api" not in result["metadata"]
            state["retry_count"] = 2
            result = await handler._handle_api_error(state)
            assert result["metadata"]["use_fallback_api"] is True

    async def test_validation_error_immediate_fallback(self):
        """Test validation errors trigger immediate fallback."""
        handler = ErrorHandlerNode()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["errors"] = [{"error": "Validation failed"}]
        state["error_count"] = 1
        result = await handler._handle_validation_error(state)
        assert result["workflow_status"] == WorkflowStatus.FAILED
        assert result["should_continue"] is False
        assert result["requires_human_review"] is True

    async def test_timeout_error_increases_timeout(self):
        """Test timeout errors increase timeout duration."""
        handler = ErrorHandlerNode()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["errors"] = [{"error": "Operation timeout"}]
        state["metadata"] = {"timeout": 30}
        state["retry_count"] = 0
        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            result = await handler._handle_timeout_error(state)
            assert result["metadata"]["timeout"] == 45
            assert result["should_continue"] is True
            state["retry_count"] = 1
            result = await handler._handle_timeout_error(state)
            assert result["metadata"]["timeout"] == 67.5
            state["metadata"]["timeout"] = 100
            result = await handler._handle_timeout_error(state)
            assert result["metadata"]["timeout"] == 120


@pytest.mark.asyncio
class TestErrorHandlerIntegration:
    """Test error handler integration with the main graph."""

    async def test_error_handler_process_flow(self):
        """Test complete error handler process flow."""
        handler = ErrorHandlerNode(max_retries=3)
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["errors"] = [{"error": "Rate limit exceeded", "type": "rate_limit"}]
        state["error_count"] = 1
        state["retry_count"] = 0
        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None
            result = await handler.process(state)
            assert result["retry_count"] == 1
            assert result["should_continue"] is True
            assert len(result["messages"]) > 0
            assert "Retry attempt 1/3" in result["messages"][-1]["content"]
            result["retry_count"] = 1
            result = await handler.process(result)
            assert result["retry_count"] == 2
            assert result["should_continue"] is True
            assert "Retry attempt 2/3" in result["messages"][-1]["content"]
            result["retry_count"] = 2
            result = await handler.process(result)
            assert result["retry_count"] == MAX_RETRIES
            assert result["should_continue"] is True
            assert "Retry attempt 3/3" in result["messages"][-1]["content"]
            result["retry_count"] = 3
            result = await handler.process(result)
            assert result["workflow_status"] == WorkflowStatus.FAILED
            assert result["should_continue"] is False
            assert result["requires_human_review"] is True
            assert "fallback activated" in result["termination_reason"].lower()

    async def test_error_handler_no_errors(self):
        """Test error handler behavior when no errors exist."""
        handler = ErrorHandlerNode()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["errors"] = []
        state["error_count"] = 0
        result = await handler.process(state)
        assert result == state

    async def test_error_handler_self_failure(self):
        """Test error handler behavior when it itself fails."""
        handler = ErrorHandlerNode()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["errors"] = [{"error": "Test error"}]
        state["error_count"] = 1
        with patch.object(handler, "_classify_error", side_effect=Exception("Handler failed")):
            result = await handler.process(state)
            assert result["workflow_status"] == WorkflowStatus.FAILED
            assert result["should_continue"] is False
            assert result["requires_human_review"] is True


class TestRoutingFunctions:
    """Test routing helper functions."""

    def test_should_route_to_error_handler(self):
        """Test conditional routing to error handler."""
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        assert should_route_to_error_handler(state) is None
        state["errors"] = [{"error": "Test"}]
        assert should_route_to_error_handler(state) is None
        state["error_count"] = 1
        state["retry_count"] = 0
        assert should_route_to_error_handler(state) == "error_handler"
        state["retry_count"] = 3
        assert should_route_to_error_handler(state) is None

    def test_get_recovery_node(self):
        """Test recovery node determination."""
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["next_node"] = "compliance_analyzer"
        assert get_recovery_node(state) == "compliance_analyzer"
        del state["next_node"]
        state["last_successful_node"] = "profile_builder"
        assert get_recovery_node(state) == "profile_builder"
        del state["last_successful_node"]
        assert get_recovery_node(state) == "router"


@pytest.mark.asyncio
class TestEnhancedGraphWithErrorHandling:
    """Test the enhanced graph with error handling integration."""

    async def test_graph_error_routing(self):
        """Test that errors route properly to error handler."""
        graph = EnhancedComplianceGraph()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test compliance"
        )
        state["errors"] = [{"error": "Profile builder failed", "node": "profile_builder"}]
        state["error_count"] = 1
        state["current_node"] = "profile_builder"
        assert graph._check_for_errors(state) == "error_handler"
        state["retry_count"] = 5
        assert graph._check_for_errors(state) == "continue"

    async def test_graph_recovery_routing(self):
        """Test recovery routing from error handler."""
        graph = EnhancedComplianceGraph()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        state["workflow_status"] = WorkflowStatus.FAILED
        assert graph._route_from_error_handler(state) == END
        state["workflow_status"] = WorkflowStatus.IN_PROGRESS
        state["last_successful_node"] = "compliance_analyzer"
        state["next_node"] = None
        assert graph._route_from_error_handler(state) == "compliance_analyzer"

    async def test_graph_node_error_tracking(self):
        """Test that nodes properly track errors."""
        graph = EnhancedComplianceGraph()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="Test"
        )
        with patch.object(
            graph.state_transition, "record_transition", side_effect=Exception("Transition failed")
        ):
            result = await graph._router_node(state)
            assert result["error_count"] == 1
            assert len(result["errors"]) == 1
            assert result["errors"][0]["node"] == "router"
            assert result["current_node"] == "router"

    async def test_graph_last_successful_node_tracking(self):
        """Test that nodes track last successful node."""
        graph = EnhancedComplianceGraph()
        state = create_enhanced_initial_state(
            session_id="test", company_id=uuid4(), initial_message="I need help with compliance"
        )
        result = await graph._router_node(state)
        assert result["last_successful_node"] == "router"
        state["business_profile"] = {}
        result = await graph._profile_builder_node(state)
        assert result["last_successful_node"] == "profile_builder"
        result = await graph._compliance_analyzer_node(state)
        assert result["last_successful_node"] == "compliance_analyzer"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
