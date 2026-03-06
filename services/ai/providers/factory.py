"""
Provider Factory

Handles provider selection and instantiation based on task requirements.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from config.ai_config import get_ai_model
from services.ai.circuit_breaker import AICircuitBreaker
from services.ai.instruction_integration import get_instruction_manager, InstructionManager
from services.ai.exceptions import ModelUnavailableException
from .base import AIProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)


# Task type to complexity mapping
TASK_COMPLEXITY_MAP = {
    "help": ("simple", True),  # (complexity, prefer_speed)
    "guidance": ("simple", True),
    "analysis": ("complex", False),
    "assessment": ("complex", False),
    "gap_analysis": ("complex", False),
    "recommendations": ("medium", False),
    "followup": ("medium", False),
    "policy_generation": ("complex", False),
    "workflow_generation": ("medium", False),
    "general": ("simple", True),
}


class ProviderFactory:
    """Factory for creating and managing AI providers."""

    def __init__(
        self,
        instruction_manager: Optional[InstructionManager] = None,
        circuit_breaker: Optional[AICircuitBreaker] = None,
    ) -> None:
        """
        Initialize the provider factory.

        Args:
            instruction_manager: Instruction manager for system instructions
            circuit_breaker: Circuit breaker for availability checks
        """
        self.instruction_manager = instruction_manager or get_instruction_manager()
        self.circuit_breaker = circuit_breaker or AICircuitBreaker()

        # Cache provider instances
        self._gemini_provider: Optional[GeminiProvider] = None
        self._openai_provider: Optional[OpenAIProvider] = None
        self._anthropic_provider: Optional[AnthropicProvider] = None

    def get_provider_for_task(
        self,
        task_type: str,
        context: Optional[Dict] = None,
        tools: Optional[List] = None,
        cached_content=None,
    ) -> Tuple[Any, str]:
        """
        Get the appropriate provider and model for a task.

        Args:
            task_type: Type of task (help, analysis, recommendations, etc.)
            context: Additional context for model selection
            tools: List of tool schemas for function calling
            cached_content: Optional cached content for improved performance

        Returns:
            Tuple of (configured model instance, instruction_id)

        Raises:
            ModelUnavailableException: If no models are available
        """
        # Get complexity and speed preference for task
        complexity, prefer_speed = TASK_COMPLEXITY_MAP.get(task_type, ("auto", False))

        logger.debug(
            f"Getting provider for task: {task_type} "
            f"(complexity: {complexity}, prefer_speed: {prefer_speed})"
        )

        try:
            # Get model with system instruction
            model, instruction_id = self.instruction_manager.get_model_with_instruction(
                instruction_type=task_type,
                framework=context.get("framework") if context else None,
                business_profile=context.get("business_context", {}) if context else None,
                task_complexity=complexity,
                tools=tools,
                prefer_speed=prefer_speed,
            )

            # Attach cached content if provided
            if cached_content:
                model._cached_content = cached_content
                logger.debug(f"Attached cached content to model for {task_type}")

            # Check circuit breaker for model availability
            model_name = getattr(model, "model_name", "unknown")
            if not self.circuit_breaker.is_model_available(model_name):
                logger.warning(f"Model {model_name} unavailable, trying fallback")

                # Try fallback model
                fallback_model = get_ai_model()
                fallback_model_name = getattr(fallback_model, "model_name", "unknown")

                if not self.circuit_breaker.is_model_available(fallback_model_name):
                    raise ModelUnavailableException(
                        model_name=fallback_model_name,
                        reason="All models unavailable due to circuit breaker",
                    )

                return fallback_model, "fallback_default"

            return model, instruction_id

        except Exception as e:
            logger.error(f"Failed to get model for {task_type}: {e}")
            raise ModelUnavailableException(
                model_name="unknown", reason=f"Model selection failed: {str(e)}"
            )

    def get_provider_by_name(self, provider_name: str) -> AIProvider:
        """
        Get a specific provider by name.

        Args:
            provider_name: Name of provider (gemini, openai, anthropic)

        Returns:
            AIProvider instance

        Raises:
            ValueError: If provider name is invalid
        """
        if provider_name == "gemini":
            if not self._gemini_provider:
                self._gemini_provider = GeminiProvider(self.circuit_breaker)
            return self._gemini_provider
        elif provider_name == "openai":
            if not self._openai_provider:
                self._openai_provider = OpenAIProvider(self.circuit_breaker)
            return self._openai_provider
        elif provider_name == "anthropic":
            if not self._anthropic_provider:
                self._anthropic_provider = AnthropicProvider(self.circuit_breaker)
            return self._anthropic_provider
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    def get_available_providers(self) -> List[str]:
        """
        Get list of available providers.

        Returns:
            List of provider names that are currently operational
        """
        available = []

        # Check Gemini availability
        if self.circuit_breaker.is_model_available("gemini-1.5-flash"):
            available.append("gemini")

        # OpenAI and Anthropic would be checked here when implemented
        # For now, they're not available
        # if self.circuit_breaker.is_model_available('gpt-4'):
        #     available.append('openai')
        # if self.circuit_breaker.is_model_available('claude-3-opus'):
        #     available.append('anthropic')

        return available
