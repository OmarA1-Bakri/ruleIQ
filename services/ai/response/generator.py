"""
Response Generator

Orchestrates AI response generation with tool integration.
"""

import logging
from typing import Any, Dict, List, Optional

from services.ai.providers.factory import ProviderFactory
from services.ai.tools import get_tool_schemas

logger = logging.getLogger(__name__)


# Task-to-tool mapping
TASK_TOOL_MAPPING = {
    "gap_analysis": ["extract_compliance_gaps"],
    "recommendations": ["generate_compliance_recommendations"],
    "regulation_lookup": ["lookup_industry_regulations", "check_compliance_requirements"],
    "assessment": ["extract_compliance_gaps", "generate_compliance_recommendations"],
    "analysis": ["extract_compliance_gaps", "lookup_industry_regulations"],
    "help": ["lookup_industry_regulations", "check_compliance_requirements"],
    "guidance": ["check_compliance_requirements"],
}


class ResponseGenerator:
    """Handles AI response generation with tools and safety validation."""

    def __init__(
        self,
        provider_factory: ProviderFactory,
        safety_manager: Optional[Any] = None,
        tool_executor: Optional[Any] = None,
        analytics_monitor: Optional[Any] = None,
    ) -> None:
        """
        Initialize the response generator.

        Args:
            provider_factory: Factory for getting AI providers
            safety_manager: Safety validation manager
            tool_executor: Tool execution manager
            analytics_monitor: Analytics monitoring service
        """
        self.provider_factory = provider_factory
        self.safety_manager = safety_manager
        self.tool_executor = tool_executor
        self.analytics_monitor = analytics_monitor

    async def generate_with_tools(
        self,
        prompt: str,
        task_type: str,
        tool_names: Optional[List[str]] = None,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Generate AI response with tool integration.

        Args:
            prompt: The input prompt
            task_type: Type of task for provider selection
            tool_names: Optional list of tool names to use
            context: Optional context for provider selection

        Returns:
            Dict with response text, function call results, and metadata
        """
        # Get appropriate tools for task
        tools = self._get_tools_for_task(task_type, tool_names)

        # Get provider from factory
        model, instruction_id = self.provider_factory.get_provider_for_task(
            task_type=task_type,
            context=context,
            tools=[tool["schema"] for tool in tools] if tools else None,
        )

        try:
            # Generate response
            # Note: This uses the model directly for now
            # In a full implementation, this would use the provider abstraction
            response = await model.generate_content_async(
                prompt, tools=[tool["schema"] for tool in tools] if tools else None
            )

            # Extract text and function calls
            response_text = self._extract_text(response)
            function_calls = self._extract_function_calls(response)

            # Execute function calls if present
            function_results = {}
            if function_calls and self.tool_executor:
                function_results = await self.handle_function_calls(function_calls, context)

            # Record analytics
            if self.analytics_monitor:
                await self.analytics_monitor.record_response_generation(
                    task_type=task_type,
                    instruction_id=instruction_id,
                    had_function_calls=len(function_calls) > 0,
                )

            return {
                "text": response_text,
                "function_calls": function_calls,
                "function_results": function_results,
                "metadata": {
                    "task_type": task_type,
                    "instruction_id": instruction_id,
                    "tools_used": len(function_calls),
                },
            }

        except Exception as e:
            logger.error(f"Response generation failed: {e}", exc_info=True)
            return {"text": "", "function_calls": [], "function_results": {}, "error": str(e)}

    async def generate_simple(
        self,
        system_prompt: str,
        user_prompt: str,
        task_type: str = "general",
        context: Optional[Dict] = None,
    ) -> str:
        """
        Generate a simple response without tools.

        Args:
            system_prompt: System instruction
            user_prompt: User prompt
            task_type: Type of task
            context: Optional context

        Returns:
            Response text
        """
        # Combine prompts
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        # Get provider
        model, _ = self.provider_factory.get_provider_for_task(task_type=task_type, context=context)

        try:
            # Generate response
            response = await model.generate_content_async(full_prompt)
            response_text = self._extract_text(response)

            # Validate safety if manager available
            if self.safety_manager:
                is_safe, _ = await self.safety_manager.validate_response(response_text)
                if not is_safe:
                    logger.warning("Response failed safety validation")
                    return ""

            return response_text

        except Exception as e:
            logger.error(f"Simple generation failed: {e}", exc_info=True)
            return ""

    async def handle_function_calls(
        self, function_calls: List[Dict], context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Execute function calls and collect results.

        Args:
            function_calls: List of function calls to execute
            context: Optional context for execution

        Returns:
            Dict mapping function names to their results
        """
        results = {}

        for fc in function_calls:
            function_name = fc.get("name")
            function_args = fc.get("args", {})

            try:
                # Execute tool
                if self.tool_executor:
                    result = await self.tool_executor.execute_tool(function_name, function_args)
                    results[function_name] = result
                else:
                    logger.warning(f"No tool executor available for {function_name}")
                    results[function_name] = {"error": "Tool executor not available"}

            except Exception as e:
                logger.error(f"Tool execution failed for {function_name}: {e}")
                results[function_name] = {"error": str(e)}

        return results

    def _get_tools_for_task(
        self, task_type: str, tool_names: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get tool schemas for a task type.

        Args:
            task_type: Type of task
            tool_names: Optional specific tool names to use

        Returns:
            List of tool schema dictionaries
        """
        if tool_names:
            # Use specific tools
            return get_tool_schemas(tool_names)

        # Get tools based on task type
        default_tools = TASK_TOOL_MAPPING.get(task_type, [])
        if default_tools:
            return get_tool_schemas(default_tools)

        return []

    def _extract_text(self, response) -> str:
        """Extract text from response."""
        try:
            if hasattr(response, "text"):
                return response.text
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    parts = candidate.content.parts
                    return "".join(part.text for part in parts if hasattr(part, "text"))
            return ""
        except Exception as e:
            logger.error(f"Failed to extract text: {e}")
            return ""

    def _extract_function_calls(self, response) -> List[Dict]:
        """Extract function calls from response."""
        function_calls = []
        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call"):
                            fc = part.function_call
                            function_calls.append(
                                {
                                    "name": fc.name,
                                    "args": dict(fc.args) if hasattr(fc, "args") else {},
                                }
                            )
        except Exception as e:
            logger.error(f"Failed to extract function calls: {e}")

        return function_calls
