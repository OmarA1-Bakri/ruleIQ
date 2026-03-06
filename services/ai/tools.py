"""
import logging


logger = logging.getLogger(__name__)
# Constants
MAX_ITEMS = 1000


AI Tools Module for Function Calling Implementation

Provides base tool interface, tool registry system, and validation for
Google Generative AI function calling capabilities.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from config.logging_config import get_logger

logger = get_logger(__name__)


class ToolType(Enum):
    """Types of AI tools available"""

    GAP_ANALYSIS = "gap_analysis"
    RECOMMENDATION = "recommendation"
    EVIDENCE_MAPPING = "evidence_mapping"
    COMPLIANCE_SCORING = "compliance_scoring"
    REGULATION_LOOKUP = "regulation_lookup"
    FRAMEWORK_SPECIFICS = "framework_specifics"
    RISK_CALCULATION = "risk_calculation"


@dataclass
class ToolResult:
    """Result from tool execution"""

    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """Base interface for all AI tools"""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description
        self.created_at = datetime.now()
        self.execution_count = 0

    @abstractmethod
    def get_function_schema(self) -> Dict[str, Any]:
        """
        Get the function schema for Google Generative AI function calling

        Returns:
            Dictionary containing the function schema with name, description, and parameters
        """
        pass

    @abstractmethod
    async def execute(
        self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """
        Execute the tool with given parameters

        Args:
            parameters: Function parameters from AI model
            context: Additional context (user info, business profile, etc.)

        Returns:
            ToolResult containing execution results
        """
        pass

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate parameters against tool requirements

        Args:
            parameters: Parameters to validate

        Returns:
            True if parameters are valid, False otherwise
        """
        schema = self.get_function_schema()
        required_params = schema.get("parameters", {}).get("required", [])
        for param in required_params:
            if param not in parameters:
                logger.error("Missing required parameter '%s' for tool '%s'" % (param, self.name))
                return False
        return True

    def increment_execution_count(self) -> None:
        """Track tool usage"""
        self.execution_count += 1


class ToolRegistry:
    """Registry for managing AI tools"""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._tool_by_type: Dict[ToolType, List[BaseTool]] = {}

    def register_tool(self, tool: BaseTool, tool_type: ToolType) -> None:
        """
        Register a tool in the registry

        Args:
            tool: Tool instance to register
            tool_type: Type category for the tool
        """
        self._tools[tool.name] = tool
        if tool_type not in self._tool_by_type:
            self._tool_by_type[tool_type] = []
        self._tool_by_type[tool_type].append(tool)
        logger.info("Registered tool '%s' of type '%s'" % (tool.name, tool_type.value))

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get tool by name"""
        return self._tools.get(name)

    def get_tools_by_type(self, tool_type: ToolType) -> List[BaseTool]:
        """Get all tools of specified type"""
        return self._tool_by_type.get(tool_type, [])

    def list_all_tools(self) -> List[BaseTool]:
        """Get list of all registered tools"""
        return list(self._tools.values())

    def get_function_schemas(self, tool_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get function schemas for specified tools or all tools

        Args:
            tool_names: List of tool names to get schemas for. If None, returns all.

        Returns:
            List of function schemas compatible with Google Generative AI
        """
        if tool_names is None:
            tools = self.list_all_tools()
        else:
            tools = [self.get_tool(name) for name in tool_names if self.get_tool(name)]
        return [tool.get_function_schema() for tool in tools]

    def remove_tool(self, name: str) -> bool:
        """
        Remove tool from registry

        Args:
            name: Name of tool to remove

        Returns:
            True if tool was removed, False if not found
        """
        if name in self._tools:
            tool = self._tools.pop(name)
            for _tool_type, tools in self._tool_by_type.items():
                if tool in tools:
                    tools.remove(tool)
                    break
            logger.info("Removed tool '%s' from registry" % name)
            return True
        return False

    def get_tool_statistics(self) -> Dict[str, Any]:
        """Get statistics about registered tools"""
        return {
            "total_tools": len(self._tools),
            "tools_by_type": {
                tool_type.value: len(tools) for tool_type, tools in self._tool_by_type.items()
            },
            "tool_execution_counts": {
                name: tool.execution_count for name, tool in self._tools.items()
            },
        }


class ToolValidator:
    """Validation utilities for tools"""

    @staticmethod
    def validate_function_schema(schema: Dict[str, Any]) -> bool:
        """
        Validate that a function schema is compatible with Google Generative AI

        Args:
            schema: Function schema to validate

        Returns:
            True if schema is valid, False otherwise
        """
        required_fields = ["name", "description", "parameters"]
        for field_name in required_fields:
            if field_name not in schema:
                logger.error("Missing required field '%s' in function schema" % field_name)
                return False
        parameters = schema["parameters"]
        if not isinstance(parameters, dict):
            logger.error("Parameters must be a dictionary")
            return False
        if "type" not in parameters or parameters["type"] != "object":
            logger.error("Parameters type must be 'object'")
            return False
        if "properties" not in parameters:
            logger.error("Parameters must have 'properties' field")
            return False
        return True

    @staticmethod
    def validate_tool_result(result: ToolResult) -> bool:
        """
        Validate tool execution result

        Args:
            result: Tool result to validate

        Returns:
            True if result is valid, False otherwise
        """
        if not isinstance(result, ToolResult):
            logger.error("Result must be a ToolResult instance")
            return False
        if not isinstance(result.success, bool):
            logger.error("Result success must be a boolean")
            return False
        if not result.success and not result.error:
            logger.error("Failed result must have error message")
            return False
        return True


class ToolExecutor:
    """Executes tools and handles results"""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self.execution_history: List[Dict[str, Any]] = []

    async def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """
        Execute a tool by name

        Args:
            tool_name: Name of tool to execute
            parameters: Parameters for tool execution
            context: Additional context

        Returns:
            ToolResult with execution results
        """
        start_time = datetime.now()
        try:
            tool = self.registry.get_tool(tool_name)
            if not tool:
                return ToolResult(success=False, error=f"Tool '{tool_name}' not found in registry")
            if not tool.validate_parameters(parameters):
                return ToolResult(success=False, error=f"Invalid parameters for tool '{tool_name}'")
            result = await tool.execute(parameters, context)
            tool.increment_execution_count()
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            self._record_execution(tool_name, parameters, result, context)
            return result
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_result = ToolResult(
                success=False, error=f"Tool execution failed: {e!s}", execution_time=execution_time
            )
            self._record_execution(tool_name, parameters, error_result, context)
            logger.error("Tool execution failed for '%s': %s" % (tool_name, e))
            return error_result

    def _record_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: ToolResult,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record tool execution for monitoring"""
        execution_record = {
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "parameters": parameters,
            "success": result.success,
            "execution_time": result.execution_time,
            "error": result.error,
            "context": context or {},
        }
        self.execution_history.append(execution_record)
        if len(self.execution_history) > MAX_ITEMS:
            self.execution_history = self.execution_history[-1000:]

    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get statistics about tool executions"""
        if not self.execution_history:
            return {"total_executions": 0}
        total_executions = len(self.execution_history)
        successful_executions = sum(1 for exec in self.execution_history if exec["success"])
        avg_execution_time = (
            sum(exec["execution_time"] for exec in self.execution_history) / total_executions
        )
        tool_usage = {}
        for exec in self.execution_history:
            tool_name = exec["tool_name"]
            if tool_name not in tool_usage:
                tool_usage[tool_name] = {"count": 0, "success_rate": 0}
            tool_usage[tool_name]["count"] += 1
        for tool_name in tool_usage:
            tool_executions = [
                exec for exec in self.execution_history if exec["tool_name"] == tool_name
            ]
            successes = sum(1 for exec in tool_executions if exec["success"])
            tool_usage[tool_name]["success_rate"] = successes / len(tool_executions)
        return {
            "total_executions": total_executions,
            "success_rate": successful_executions / total_executions,
            "average_execution_time": avg_execution_time,
            "tool_usage": tool_usage,
        }


tool_registry = ToolRegistry()
tool_executor = ToolExecutor(tool_registry)


def register_tool(tool: BaseTool, tool_type: ToolType) -> None:
    """Convenience function to register a tool"""
    tool_registry.register_tool(tool, tool_type)


def get_tool_schemas(tool_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Convenience function to get tool schemas"""
    return tool_registry.get_function_schemas(tool_names)


async def execute_tool(
    tool_name: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> ToolResult:
    """Convenience function to execute a tool"""
    return await tool_executor.execute_tool(tool_name, parameters, context)
