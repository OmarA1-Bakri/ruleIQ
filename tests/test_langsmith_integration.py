"""

# Constants


Comprehensive test suite for LangSmith integration with LangGraph.

Tests cover:
1. Configuration validation
2. Client initialization
3. Tracing callbacks and decorators
4. Metadata collection
5. Performance impact
6. Error scenarios and edge cases
7. Trace data structure validation
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.langsmith_config import (
    LangSmithConfig,
    with_langsmith_tracing,
    LANGSMITH_SETUP_INSTRUCTIONS,
)

from tests.test_constants import DEFAULT_LIMIT, MAX_RETRIES


class TestLangSmithConfiguration:
    """Test LangSmith client configuration."""

    def test_is_tracing_enabled_when_true(self, monkeypatch):
        """Test tracing detection when enabled."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        assert LangSmithConfig.is_tracing_enabled() is True

    def test_is_tracing_enabled_when_false(self, monkeypatch):
        """Test tracing detection when disabled."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
        assert LangSmithConfig.is_tracing_enabled() is False

    def test_is_tracing_enabled_when_not_set(self, monkeypatch):
        """Test tracing detection when env var not set."""
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
        assert LangSmithConfig.is_tracing_enabled() is False

    def test_get_api_key_present(self, monkeypatch):
        """Test API key retrieval when present."""
        test_key = "ls__test_api_key_123"
        monkeypatch.setenv("LANGCHAIN_API_KEY", test_key)
        assert LangSmithConfig.get_api_key() == test_key

    def test_get_api_key_missing(self, monkeypatch):
        """Test API key retrieval when missing."""
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        assert LangSmithConfig.get_api_key() is None

    def test_get_project_name_custom(self, monkeypatch):
        """Test custom project name."""
        monkeypatch.setenv("LANGCHAIN_PROJECT", "custom-project")
        assert LangSmithConfig.get_project_name() == "custom-project"

    def test_get_project_name_default(self, monkeypatch):
        """Test default project name."""
        monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
        assert LangSmithConfig.get_project_name() == "ruleiq-assessment"

    def test_get_endpoint_custom(self, monkeypatch):
        """Test custom endpoint."""
        custom_endpoint = "https://custom.langchain.com"
        monkeypatch.setenv("LANGCHAIN_ENDPOINT", custom_endpoint)
        assert LangSmithConfig.get_endpoint() == custom_endpoint

    def test_get_endpoint_default(self, monkeypatch):
        """Test default endpoint."""
        monkeypatch.delenv("LANGCHAIN_ENDPOINT", raising=False)
        assert LangSmithConfig.get_endpoint() == "https://api.smith.langchain.com"

    def test_validate_configuration_success(self, monkeypatch, caplog):
        """Test successful configuration validation."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__valid_key")
        monkeypatch.setenv("LANGCHAIN_PROJECT", "test-project")
        assert LangSmithConfig.validate_configuration() is True
        assert "LangSmith tracing configured" in caplog.text
        assert "Project: test-project" in caplog.text

    def test_validate_configuration_disabled(self, monkeypatch, caplog):
        """Test validation when tracing is disabled."""
        import logging

        caplog.set_level(logging.DEBUG)
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
        assert LangSmithConfig.validate_configuration() is False
        assert "LangSmith tracing is disabled" in caplog.text

    def test_validate_configuration_missing_api_key(self, monkeypatch, caplog):
        """Test validation with missing API key."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        assert LangSmithConfig.validate_configuration() is False
        assert "LANGCHAIN_API_KEY is not set" in caplog.text

    def test_validate_configuration_invalid_api_key_format(self, monkeypatch, caplog):
        """Test validation with invalid API key format."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "invalid_key_format")
        assert LangSmithConfig.validate_configuration() is False
        assert "should start with 'ls__'" in caplog.text


class TestLangSmithMetadata:
    """Test metadata collection functionality."""

    def test_get_trace_metadata_basic(self, monkeypatch):
        """Test basic metadata generation."""
        monkeypatch.setenv("ENVIRONMENT", "testing")
        metadata = LangSmithConfig.get_trace_metadata()
        assert metadata["application"] == "ruleiq"
        assert metadata["component"] == "assessment_agent"
        assert metadata["environment"] == "testing"

    def test_get_trace_metadata_with_session(self):
        """Test metadata with session ID."""
        metadata = LangSmithConfig.get_trace_metadata(
            session_id="test-session-123", lead_id="lead-456"
        )
        assert metadata["session_id"] == "test-session-123"
        assert metadata["lead_id"] == "lead-456"

    def test_get_trace_metadata_with_custom_fields(self):
        """Test metadata with custom fields."""
        metadata = LangSmithConfig.get_trace_metadata(
            session_id="session-1", custom_field="custom_value", phase="evidence_collection"
        )
        assert metadata["session_id"] == "session-1"
        assert metadata["custom_field"] == "custom_value"
        assert metadata["phase"] == "evidence_collection"

    def test_get_trace_tags_basic(self):
        """Test basic tag generation."""
        tags = LangSmithConfig.get_trace_tags("test_operation")
        assert "ruleiq" in tags
        assert "assessment" in tags
        assert "langgraph" in tags
        assert "test_operation" in tags

    def test_get_trace_tags_with_phase(self):
        """Test tags with phase."""
        tags = LangSmithConfig.get_trace_tags("evidence_collection", phase="initial")
        assert "phase:initial" in tags
        assert "evidence_collection" in tags

    def test_get_trace_tags_with_custom(self):
        """Test tags with custom values."""
        tags = LangSmithConfig.get_trace_tags(
            "validation", phase="final", priority="high", source="api"
        )
        assert "phase:final" in tags
        assert "priority:high" in tags
        assert "source:api" in tags


class TestTracingDecorator:
    """Test tracing decorators and callbacks."""

    @pytest.mark.asyncio
    async def test_decorator_with_tracing_disabled(self, monkeypatch):
        """Test decorator behavior when tracing is disabled."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
        call_count = 0

        @with_langsmith_tracing("test_op")
        async def test_function(arg1, arg2):
            nonlocal call_count
            call_count += 1
            return arg1 + arg2

        result = await test_function(1, 2)
        assert result == MAX_RETRIES
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_with_tracing_enabled(self, monkeypatch):
        """Test decorator behavior when tracing is enabled."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=None)
            mock_context.__exit__ = MagicMock(return_value=None)
            mock_tracing.return_value = mock_context

            @with_langsmith_tracing("test_operation")
            async def test_function(session_id, value):
                return {"result": value * 2}

            result = await test_function(session_id="test-123", value=5)
            assert result == {"result": 10}
            mock_tracing.assert_called_once()
            call_kwargs = mock_tracing.call_args[1]
            assert call_kwargs["project_name"] == "ruleiq-assessment"
            assert "test_operation" in call_kwargs["tags"]
            assert "session:test-123" in call_kwargs["tags"]

    @pytest.mark.asyncio
    async def test_decorator_with_state_extraction(self, monkeypatch):
        """Test decorator extracting context from state."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=None)
            mock_context.__exit__ = MagicMock(return_value=None)
            mock_tracing.return_value = mock_context

            @with_langsmith_tracing("process_state", include_input=True, include_output=True)
            async def test_function(state):
                return {"processed": True}

            test_state = {
                "session_id": "state-session-789",
                "current_phase": "evidence_collection",
                "data": "test_data",
            }
            result = await test_function(state=test_state)
            assert result == {"processed": True}
            call_kwargs = mock_tracing.call_args[1]
            assert "session:state-session-789" in call_kwargs["tags"]
            assert "phase:evidence_collection" in call_kwargs["tags"]
            assert call_kwargs["metadata"]["session_id"] == "state-session-789"

    @pytest.mark.asyncio
    async def test_decorator_error_handling(self, monkeypatch):
        """Test decorator handles errors gracefully."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_tracing.side_effect = Exception("Tracing setup failed")

            @with_langsmith_tracing("error_test")
            async def test_function():
                return "success"

            with pytest.raises(Exception) as exc_info:
                await test_function()
            assert str(exc_info.value) == "Tracing setup failed"


class TestPerformanceImpact:
    """Test performance impact of tracing."""

    @pytest.mark.asyncio
    async def test_performance_without_tracing(self, monkeypatch):
        """Measure performance without tracing."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

        @with_langsmith_tracing("perf_test")
        async def test_function():
            await asyncio.sleep(0.01)
            return "done"

        start_time = time.perf_counter()
        await test_function()
        elapsed = time.perf_counter() - start_time
        assert elapsed < 0.02

    @pytest.mark.asyncio
    async def test_performance_with_tracing(self, monkeypatch):
        """Measure performance with tracing enabled."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=None)
            mock_context.__exit__ = MagicMock(return_value=None)
            mock_tracing.return_value = mock_context

            @with_langsmith_tracing("perf_test")
            async def test_function():
                await asyncio.sleep(0.01)
                return "done"

            start_time = time.perf_counter()
            await test_function()
            elapsed = time.perf_counter() - start_time
            assert elapsed < 0.03

    @pytest.mark.asyncio
    async def test_bulk_operations_performance(self, monkeypatch):
        """Test performance with multiple traced operations."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=None)
            mock_context.__exit__ = MagicMock(return_value=None)
            mock_tracing.return_value = mock_context

            @with_langsmith_tracing("bulk_test")
            async def test_function(index):
                return index * 2

            start_time = time.perf_counter()
            tasks = [test_function(i) for i in range(DEFAULT_LIMIT)]
            results = await asyncio.gather(*tasks)
            elapsed = time.perf_counter() - start_time
            assert len(results) == DEFAULT_LIMIT
            assert results[50] == DEFAULT_LIMIT
            assert elapsed < 1.0


class TestErrorScenarios:
    """Test error scenarios and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_api_key_handling(self, monkeypatch, caplog):
        """Test handling of invalid API key."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "invalid_key")
        result = LangSmithConfig.validate_configuration()
        assert result is False
        assert "should start with 'ls__'" in caplog.text

    @pytest.mark.asyncio
    async def test_network_error_handling(self, monkeypatch):
        """Test handling of network errors during tracing."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_tracing.side_effect = ConnectionError("Network unreachable")

            @with_langsmith_tracing("network_test")
            async def test_function():
                return "should_still_work"

            with pytest.raises(ConnectionError):
                await test_function()

    @pytest.mark.asyncio
    async def test_malformed_metadata_handling(self, monkeypatch):
        """Test handling of malformed metadata."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=None)
            mock_context.__exit__ = MagicMock(return_value=None)
            mock_tracing.return_value = mock_context

            @with_langsmith_tracing("metadata_test")
            async def test_function(**kwargs):
                return "success"

            circular_ref = {}
            circular_ref["self"] = circular_ref
            result = await test_function(
                circular_data=circular_ref, none_value=None, large_string="x" * 10000
            )
            assert result == "success"

    @pytest.mark.asyncio
    async def test_concurrent_tracing_operations(self, monkeypatch):
        """Test concurrent traced operations."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=None)
            mock_context.__exit__ = MagicMock(return_value=None)
            mock_tracing.return_value = mock_context

            @with_langsmith_tracing("concurrent_test")
            async def test_function(session_id, delay):
                await asyncio.sleep(delay)
                return session_id

            tasks = [test_function(f"session-{i}", 0.01) for i in range(10)]
            results = await asyncio.gather(*tasks)
            assert len(results) == 10
            assert results[0] == "session-0"
            assert results[9] == "session-9"
            assert mock_tracing.call_count == 10


class TestTraceDataStructure:
    """Test and validate trace data structure."""

    def test_trace_metadata_structure(self):
        """Validate metadata structure matches LangSmith requirements."""
        metadata = LangSmithConfig.get_trace_metadata(
            session_id="test-session", lead_id="test-lead", custom_field="value"
        )
        assert "application" in metadata
        assert "component" in metadata
        assert "environment" in metadata
        assert "session_id" in metadata
        assert "lead_id" in metadata
        assert "custom_field" in metadata
        json_str = json.dumps(metadata)
        assert json_str

    def test_trace_tags_structure(self):
        """Validate tags structure."""
        tags = LangSmithConfig.get_trace_tags("test_op", phase="testing", priority="high")
        assert isinstance(tags, list)
        assert all(isinstance(tag, str) for tag in tags)
        assert len(tags) >= 4
        assert any("phase:" in tag for tag in tags)
        assert any("priority:" in tag for tag in tags)

    @pytest.mark.asyncio
    async def test_trace_output_structure(self, monkeypatch):
        """Test trace output includes expected structure."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        trace_calls = []
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:

            def capture_trace(**kwargs):
                trace_calls.append(kwargs)
                mock_context = MagicMock()
                mock_context.__enter__ = MagicMock(return_value=None)
                mock_context.__exit__ = MagicMock(return_value=None)
                return mock_context

            mock_tracing.side_effect = capture_trace

            @with_langsmith_tracing("struct_test", include_input=True, include_output=True)
            async def test_function(data):
                return {"processed": data, "timestamp": "2024-01-01"}

            result = await test_function(data={"input": "test"})
            assert len(trace_calls) == 1
            trace = trace_calls[0]
            assert "project_name" in trace
            assert "tags" in trace
            assert "metadata" in trace
            assert isinstance(trace["tags"], list)
            assert isinstance(trace["metadata"], dict)


class TestIntegrationWithLangGraph:
    """Test integration with LangGraph nodes."""

    @pytest.mark.asyncio
    async def test_langgraph_node_tracing(self, monkeypatch):
        """Test tracing integration with LangGraph nodes."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=None)
            mock_context.__exit__ = MagicMock(return_value=None)
            mock_tracing.return_value = mock_context

            class TestNode:
                @with_langsmith_tracing("node_operation")
                async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
                    state["processed"] = True
                    return state

            node = TestNode()
            test_state = {
                "session_id": "node-session-123",
                "current_phase": "testing",
                "data": "test",
            }
            result = await node.process(state=test_state)
            assert result["processed"] is True
            call_kwargs = mock_tracing.call_args[1]
            assert "session:node-session-123" in call_kwargs["tags"]
            assert "phase:testing" in call_kwargs["tags"]

    @pytest.mark.asyncio
    async def test_checkpoint_tracing(self, monkeypatch):
        """Test tracing of checkpoint operations."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=None)
            mock_context.__exit__ = MagicMock(return_value=None)
            mock_tracing.return_value = mock_context

            @with_langsmith_tracing("checkpoint_save")
            async def save_checkpoint(session_id: str, state: Dict) -> bool:
                return True

            @with_langsmith_tracing("checkpoint_load")
            async def load_checkpoint(session_id: str) -> Dict:
                return {"restored": True}

            save_result = await save_checkpoint("ckpt-123", {"data": "test"})
            assert save_result is True
            load_result = await load_checkpoint("ckpt-123")
            assert load_result["restored"] is True
            assert mock_tracing.call_count == 2


class TestMockTracingCallbacks:
    """Test mock tracing callbacks for testing."""

    def test_mock_callback_creation(self):
        """Test creating mock tracing callbacks."""
        mock_handler = Mock()
        mock_handler.on_llm_start = Mock()
        mock_handler.on_llm_end = Mock()
        mock_handler.on_chain_start = Mock()
        mock_handler.on_chain_end = Mock()
        mock_handler.on_chain_start(serialized={"name": "test_chain"}, inputs={"query": "test"})
        mock_handler.on_chain_end(outputs={"result": "success"})
        assert mock_handler.on_chain_start.called
        assert mock_handler.on_chain_end.called
        chain_start_args = mock_handler.on_chain_start.call_args[1]
        assert chain_start_args["serialized"]["name"] == "test_chain"
        assert chain_start_args["inputs"]["query"] == "test"

    @pytest.mark.asyncio
    async def test_async_mock_callbacks(self):
        """Test async mock callbacks."""
        mock_handler = AsyncMock()
        await mock_handler.on_tool_start(serialized={"name": "test_tool"}, input_str="test input")
        await mock_handler.on_tool_end(output="test output")
        assert mock_handler.on_tool_start.called
        assert mock_handler.on_tool_end.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
