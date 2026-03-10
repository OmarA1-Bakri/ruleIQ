"""
Tests for services.ai.tools module.

Covers ToolType enum, ToolResult dataclass, BaseTool ABC, ToolRegistry,
ToolValidator, and ToolExecutor.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.ai.tools import (
    ToolType,
    ToolResult,
    BaseTool,
    ToolRegistry,
    ToolValidator,
    ToolExecutor,
)

# Inject constant trapped in module docstring
import services.ai.tools as _tools_mod
if not hasattr(_tools_mod, "MAX_ITEMS"):
    _tools_mod.MAX_ITEMS = 1000


# =====================================================================
# ToolType Tests
# =====================================================================


class TestToolType:
    def test_all_types(self):
        assert ToolType.GAP_ANALYSIS.value == "gap_analysis"
        assert ToolType.RECOMMENDATION.value == "recommendation"
        assert ToolType.EVIDENCE_MAPPING.value == "evidence_mapping"
        assert ToolType.COMPLIANCE_SCORING.value == "compliance_scoring"
        assert ToolType.REGULATION_LOOKUP.value == "regulation_lookup"
        assert ToolType.FRAMEWORK_SPECIFICS.value == "framework_specifics"
        assert ToolType.RISK_CALCULATION.value == "risk_calculation"

    def test_member_count(self):
        assert len(ToolType) == 7


# =====================================================================
# ToolResult Tests
# =====================================================================


class TestToolResult:
    def test_success_result(self):
        result = ToolResult(success=True, data={"key": "val"})
        assert result.success is True
        assert result.data == {"key": "val"}
        assert result.error is None
        assert result.execution_time == 0.0
        assert result.metadata == {}

    def test_failure_result(self):
        result = ToolResult(success=False, error="Something broke")
        assert result.success is False
        assert result.error == "Something broke"

    def test_to_dict(self):
        result = ToolResult(
            success=True,
            data={"gaps": []},
            execution_time=1.5,
            metadata={"tool_type": "gap_analysis"},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == {"gaps": []}
        assert d["execution_time"] == 1.5
        assert d["metadata"]["tool_type"] == "gap_analysis"
        assert d["error"] is None

    def test_with_metadata(self):
        result = ToolResult(success=True, metadata={"x": 1, "y": 2})
        assert result.metadata == {"x": 1, "y": 2}


# =====================================================================
# Concrete Tool for Testing
# =====================================================================


class MockTool(BaseTool):
    """Concrete implementation for testing BaseTool."""

    def __init__(self, name="mock_tool", description="a mock tool"):
        super().__init__(name=name, description=description)

    def get_function_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                },
                "required": ["input"],
            },
        }

    async def execute(self, parameters, context=None):
        return ToolResult(success=True, data=parameters)


# =====================================================================
# BaseTool Tests
# =====================================================================


class TestBaseTool:
    def test_init(self):
        tool = MockTool()
        assert tool.name == "mock_tool"
        assert tool.description == "a mock tool"
        assert tool.execution_count == 0
        assert tool.created_at is not None

    def test_validate_parameters_valid(self):
        tool = MockTool()
        assert tool.validate_parameters({"input": "hello"}) is True

    def test_validate_parameters_missing_required(self):
        tool = MockTool()
        assert tool.validate_parameters({}) is False

    def test_increment_execution_count(self):
        tool = MockTool()
        assert tool.execution_count == 0
        tool.increment_execution_count()
        assert tool.execution_count == 1
        tool.increment_execution_count()
        assert tool.execution_count == 2

    @pytest.mark.asyncio
    async def test_execute(self):
        tool = MockTool()
        result = await tool.execute({"input": "test"})
        assert result.success is True
        assert result.data == {"input": "test"}


# =====================================================================
# ToolRegistry Tests
# =====================================================================


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = MockTool("test_tool")
        registry.register_tool(tool, ToolType.GAP_ANALYSIS)
        assert registry.get_tool("test_tool") is tool

    def test_get_nonexistent(self):
        registry = ToolRegistry()
        assert registry.get_tool("nope") is None

    def test_get_tools_by_type(self):
        registry = ToolRegistry()
        tool1 = MockTool("t1")
        tool2 = MockTool("t2")
        registry.register_tool(tool1, ToolType.GAP_ANALYSIS)
        registry.register_tool(tool2, ToolType.GAP_ANALYSIS)
        tools = registry.get_tools_by_type(ToolType.GAP_ANALYSIS)
        assert len(tools) == 2

    def test_get_tools_by_type_empty(self):
        registry = ToolRegistry()
        assert registry.get_tools_by_type(ToolType.RECOMMENDATION) == []

    def test_list_all_tools(self):
        registry = ToolRegistry()
        registry.register_tool(MockTool("a"), ToolType.GAP_ANALYSIS)
        registry.register_tool(MockTool("b"), ToolType.RECOMMENDATION)
        assert len(registry.list_all_tools()) == 2

    def test_get_function_schemas(self):
        registry = ToolRegistry()
        registry.register_tool(MockTool("t1"), ToolType.GAP_ANALYSIS)
        registry.register_tool(MockTool("t2"), ToolType.RECOMMENDATION)
        schemas = registry.get_function_schemas()
        assert len(schemas) == 2
        assert all("name" in s for s in schemas)

    def test_get_function_schemas_specific(self):
        registry = ToolRegistry()
        registry.register_tool(MockTool("t1"), ToolType.GAP_ANALYSIS)
        registry.register_tool(MockTool("t2"), ToolType.RECOMMENDATION)
        schemas = registry.get_function_schemas(["t1"])
        assert len(schemas) == 1

    def test_get_function_schemas_nonexistent_name(self):
        registry = ToolRegistry()
        registry.register_tool(MockTool("t1"), ToolType.GAP_ANALYSIS)
        schemas = registry.get_function_schemas(["nonexistent"])
        assert len(schemas) == 0

    def test_remove_tool(self):
        registry = ToolRegistry()
        tool = MockTool("rm_me")
        registry.register_tool(tool, ToolType.GAP_ANALYSIS)
        assert registry.remove_tool("rm_me") is True
        assert registry.get_tool("rm_me") is None
        assert registry.get_tools_by_type(ToolType.GAP_ANALYSIS) == []

    def test_remove_nonexistent(self):
        registry = ToolRegistry()
        assert registry.remove_tool("nope") is False

    def test_get_tool_statistics(self):
        registry = ToolRegistry()
        tool = MockTool("stats_tool")
        registry.register_tool(tool, ToolType.GAP_ANALYSIS)
        tool.increment_execution_count()
        stats = registry.get_tool_statistics()
        assert stats["total_tools"] == 1
        assert stats["tool_execution_counts"]["stats_tool"] == 1


# =====================================================================
# ToolValidator Tests
# =====================================================================


class TestToolValidator:
    def test_valid_schema(self):
        schema = {
            "name": "test",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {"input": {"type": "string"}},
            },
        }
        assert ToolValidator.validate_function_schema(schema) is True

    def test_missing_name(self):
        schema = {
            "description": "A test tool",
            "parameters": {"type": "object", "properties": {}},
        }
        assert ToolValidator.validate_function_schema(schema) is False

    def test_missing_description(self):
        schema = {
            "name": "test",
            "parameters": {"type": "object", "properties": {}},
        }
        assert ToolValidator.validate_function_schema(schema) is False

    def test_missing_parameters(self):
        schema = {"name": "test", "description": "test"}
        assert ToolValidator.validate_function_schema(schema) is False

    def test_parameters_not_dict(self):
        schema = {"name": "t", "description": "d", "parameters": "wrong"}
        assert ToolValidator.validate_function_schema(schema) is False

    def test_parameters_wrong_type(self):
        schema = {
            "name": "t",
            "description": "d",
            "parameters": {"type": "array", "properties": {}},
        }
        assert ToolValidator.validate_function_schema(schema) is False

    def test_parameters_no_properties(self):
        schema = {
            "name": "t",
            "description": "d",
            "parameters": {"type": "object"},
        }
        assert ToolValidator.validate_function_schema(schema) is False

    def test_validate_tool_result_success(self):
        result = ToolResult(success=True, data="ok")
        assert ToolValidator.validate_tool_result(result) is True

    def test_validate_tool_result_failure_with_error(self):
        result = ToolResult(success=False, error="failed")
        assert ToolValidator.validate_tool_result(result) is True

    def test_validate_tool_result_failure_no_error(self):
        result = ToolResult(success=False)
        assert ToolValidator.validate_tool_result(result) is False

    def test_validate_tool_result_not_tool_result(self):
        assert ToolValidator.validate_tool_result("not a result") is False


# =====================================================================
# ToolExecutor Tests
# =====================================================================


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        registry = ToolRegistry()
        tool = MockTool("exec_tool")
        registry.register_tool(tool, ToolType.GAP_ANALYSIS)

        executor = ToolExecutor(registry)
        result = await executor.execute_tool("exec_tool", {"input": "hi"})
        assert result.success is True
        assert result.data == {"input": "hi"}
        assert tool.execution_count == 1
        assert len(executor.execution_history) == 1

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        result = await executor.execute_tool("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_invalid_params(self):
        registry = ToolRegistry()
        tool = MockTool("strict_tool")
        registry.register_tool(tool, ToolType.GAP_ANALYSIS)
        executor = ToolExecutor(registry)
        result = await executor.execute_tool("strict_tool", {})
        assert result.success is False
        assert "Invalid parameters" in result.error

    @pytest.mark.asyncio
    async def test_execute_exception_handling(self):
        registry = ToolRegistry()

        class FailingTool(BaseTool):
            def __init__(self):
                super().__init__("fail_tool", "always fails")

            def get_function_schema(self):
                return {
                    "name": "fail_tool",
                    "description": "fails",
                    "parameters": {"type": "object", "properties": {}},
                }

            async def execute(self, parameters, context=None):
                raise RuntimeError("boom")

        tool = FailingTool()
        registry.register_tool(tool, ToolType.GAP_ANALYSIS)
        executor = ToolExecutor(registry)
        result = await executor.execute_tool("fail_tool", {})
        assert result.success is False
        assert "boom" in result.error

    def test_get_execution_statistics_empty(self):
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        stats = executor.get_execution_statistics()
        assert stats["total_executions"] == 0

    @pytest.mark.asyncio
    async def test_get_execution_statistics_with_data(self):
        registry = ToolRegistry()
        tool = MockTool("stat_tool")
        registry.register_tool(tool, ToolType.GAP_ANALYSIS)
        executor = ToolExecutor(registry)
        await executor.execute_tool("stat_tool", {"input": "x"})
        stats = executor.get_execution_statistics()
        assert stats["total_executions"] == 1
        assert stats["success_rate"] == 1.0
        assert "stat_tool" in stats["tool_usage"]
