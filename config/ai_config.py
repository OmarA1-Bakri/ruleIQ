"""
AI Configuration and Model Setup for ComplianceGPT

This module handles configuration and initialization of AI models,
primarily Google Generative AI for compliance content generation.
"""

# Constants
MAX_ITEMS = 1000

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import google.genai as genai
else:
    try:
        import google.genai as genai
    except ImportError:
        genai = None
from dotenv import load_dotenv
from config.logging_config import get_logger

load_dotenv()
LARGE_PROMPT_THRESHOLD = 2000
MEDIUM_PROMPT_THRESHOLD = 1000
ENTERPRISE_EMPLOYEE_THRESHOLD = 1000
SIMPLE_COMPLEXITY_THRESHOLD = 0.3
COMPLEX_COMPLEXITY_THRESHOLD = 0.7


class ModelType(Enum):
    """Available AI model types"""

    GEMINI_FLASH = "gemini-2.5-flash-preview-05-20"
    GEMINI_25_PRO = "gemini-2.5-pro"
    GEMINI_25_FLASH = "gemini-2.5-flash"
    GEMMA_3 = "gemma-3-8b-it"


@dataclass
class ModelMetadata:
    """Metadata for AI model capabilities and characteristics"""

    name: str
    cost_score: float
    speed_score: float
    capability_score: float
    max_tokens: int
    timeout_seconds: float

    @property
    def efficiency_score(self) -> float:
        """Calculate efficiency as capability/cost ratio"""
        return self.capability_score / self.cost_score if self.cost_score > 0 else 0


MODEL_FALLBACK_CHAIN = [ModelType.GEMINI_25_PRO, ModelType.GEMINI_25_FLASH, ModelType.GEMMA_3]
MODEL_METADATA = {
    ModelType.GEMINI_25_PRO: ModelMetadata(
        name=ModelType.GEMINI_25_PRO.value,
        cost_score=8.0,
        speed_score=6.0,
        capability_score=10.0,
        max_tokens=8192,
        timeout_seconds=45.0,
    ),
    ModelType.GEMINI_25_FLASH: ModelMetadata(
        name=ModelType.GEMINI_25_FLASH.value,
        cost_score=4.0,
        speed_score=9.0,
        capability_score=8.0,
        max_tokens=4096,
        timeout_seconds=30.0,
    ),
    ModelType.GEMMA_3: ModelMetadata(
        name=ModelType.GEMMA_3.value,
        cost_score=1.0,
        speed_score=8.0,
        capability_score=5.0,
        max_tokens=2048,
        timeout_seconds=15.0,
    ),
    ModelType.GEMINI_FLASH: ModelMetadata(
        name=ModelType.GEMINI_FLASH.value,
        cost_score=4.0,
        speed_score=8.0,
        capability_score=7.0,
        max_tokens=2048,
        timeout_seconds=30.0,
    ),
}


class _GenAIModelWrapper:
    """Wraps google.genai Client to expose a GenerativeModel-compatible interface."""

    def __init__(
        self,
        client: Any,
        model_name: str,
        generation_config: Dict[str, Any],
        safety_settings: list,
        system_instruction: Optional[str] = None,
    ) -> None:
        self._client = client
        self._model_name = model_name
        self._generation_config = generation_config
        self._safety_settings = safety_settings
        self._system_instruction = system_instruction

    @property
    def model_name(self) -> str:
        return self._model_name

    def _build_genai_config(self, generation_config: Any = None, safety_settings: Any = None) -> Any:
        from google.genai import types as _gtypes

        gen_cfg = generation_config if generation_config is not None else self._generation_config
        safe_cfg = safety_settings if safety_settings is not None else self._safety_settings

        if not isinstance(gen_cfg, dict):
            return gen_cfg  # already a config object

        config_kwargs: Dict[str, Any] = {
            "temperature": gen_cfg.get("temperature", 0.7),
            "top_p": gen_cfg.get("top_p", 0.8),
            "top_k": gen_cfg.get("top_k", 40),
            "max_output_tokens": gen_cfg.get("max_output_tokens", 4096),
        }
        if "response_mime_type" in gen_cfg:
            config_kwargs["response_mime_type"] = gen_cfg["response_mime_type"]
        if "response_schema" in gen_cfg:
            config_kwargs["response_schema"] = gen_cfg["response_schema"]
        if self._system_instruction:
            config_kwargs["system_instruction"] = self._system_instruction
        if safe_cfg and isinstance(safe_cfg, list) and safe_cfg and isinstance(safe_cfg[0], dict):
            config_kwargs["safety_settings"] = [
                _gtypes.SafetySetting(category=s["category"], threshold=s["threshold"])
                for s in safe_cfg
            ]
        elif safe_cfg:
            config_kwargs["safety_settings"] = safe_cfg

        return _gtypes.GenerateContentConfig(**config_kwargs)

    def generate_content(
        self,
        prompt: Any,
        safety_settings: Any = None,
        generation_config: Any = None,
        stream: bool = False,
    ) -> Any:
        config = self._build_genai_config(generation_config, safety_settings)
        if stream:
            return self._client.models.generate_content_stream(
                model=self._model_name, contents=prompt, config=config
            )
        return self._client.models.generate_content(
            model=self._model_name, contents=prompt, config=config
        )


class AIConfig:
    """AI Configuration Manager"""

    def __init__(self) -> None:
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.default_model = ModelType.GEMINI_25_FLASH.value
        self.default_model_type = ModelType.GEMINI_25_FLASH
        self.fallback_chain = MODEL_FALLBACK_CHAIN
        self.model_metadata = MODEL_METADATA
        self.generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 4096,
        }
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ]
        self.retry_config = {
            "default": {
                "max_attempts": 3,
                "base_delay": 1.0,
                "max_delay": 60.0,
                "strategy": "exponential_backoff",
                "jitter": True,
            },
            "quick_operations": {
                "max_attempts": 2,
                "base_delay": 0.5,
                "max_delay": 10.0,
                "strategy": "linear_backoff",
                "jitter": True,
            },
            "long_operations": {
                "max_attempts": 5,
                "base_delay": 2.0,
                "max_delay": 120.0,
                "strategy": "exponential_backoff",
                "jitter": True,
            },
            "critical_operations": {
                "max_attempts": 7,
                "base_delay": 1.0,
                "max_delay": 60.0,
                "strategy": "fibonacci_backoff",
                "jitter": True,
            },
        }
        self.circuit_breaker_config = {
            "failure_threshold": 5,
            "recovery_timeout": 60,
            "success_threshold": 3,
            "time_window": 60,
            "model_timeouts": {
                ModelType.GEMINI_25_PRO.value: 45.0,
                ModelType.GEMINI_25_FLASH.value: 30.0,
                ModelType.GEMMA_3.value: 15.0,
                ModelType.GEMINI_FLASH.value: 30.0,
            },
        }
        self.offline_config = {
            "mode": os.getenv("AI_OFFLINE_MODE", "enhanced"),
            "database_path": os.getenv("AI_OFFLINE_DB_PATH", "data/offline_ai.db"),
            "cache_ttl_hours": int(os.getenv("AI_OFFLINE_CACHE_TTL", "24")),
            "max_history_size": int(os.getenv("AI_OFFLINE_HISTORY_SIZE", "1000")),
            "enable_request_queuing": os.getenv("AI_OFFLINE_QUEUE_REQUESTS", "true").lower()
            == "true",
        }
        self._genai_client: Optional[Any] = None

    def _get_genai_client(self) -> Any:
        """Get or lazily create the google.genai Client instance."""
        if self._genai_client is None:
            if genai is None:
                raise ImportError("google.genai package is not installed")
            if not self.google_api_key:
                raise ValueError("GOOGLE_API_KEY environment variable is required")
            self._genai_client = genai.Client(api_key=self.google_api_key)
        return self._genai_client

    def _initialize_google_ai(self) -> None:
        """Initialize Google AI client with API key"""
        if os.getenv("USE_MOCK_AI", "false").lower() == "true":
            return
        self._get_genai_client()

    def get_model(
        self,
        model_type: Optional[ModelType] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """Get configured AI model instance with optional system instruction and tools"""
        if os.getenv("USE_MOCK_AI", "false").lower() == "true":
            from unittest.mock import MagicMock

            mock_model = MagicMock()
            mock_model.generate_content.return_value.text = "Mock AI response"
            return mock_model
        model_name = model_type.value if model_type else self.default_model
        client = self._get_genai_client()
        return _GenAIModelWrapper(
            client=client,
            model_name=model_name,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings,
            system_instruction=system_instruction,
        )

    def update_generation_config(self, **kwargs) -> None:
        """Update generation configuration parameters"""
        self.generation_config.update(kwargs)

    def get_compliance_optimized_config(self) -> Dict[str, Any]:
        """Get AI configuration optimized for compliance content generation"""
        return {"temperature": 0.3, "top_p": 0.8, "top_k": 40, "max_output_tokens": 4096}

    def get_creative_config(self) -> Dict[str, Any]:
        """Get AI configuration for more creative content generation"""
        return {"temperature": 0.8, "top_p": 0.9, "top_k": 50, "max_output_tokens": 2048}

    def get_structured_output_config(
        self, response_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get AI configuration optimized for structured JSON output"""
        config = {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 4096,
            "response_mime_type": "application/json",
        }
        if response_schema:
            config["response_schema"] = response_schema
        return config

    def get_schema_aware_config(self, schema_type: str) -> Dict[str, Any]:
        """
        Get configuration with appropriate schema for response type

        Args:
            schema_type: Type of response schema (gap_analysis, recommendations, etc.)
        """
        from services.ai.response_formats import get_schema_for_response_type

        schema = get_schema_for_response_type(schema_type)
        return self.get_structured_output_config(schema)

    def get_model_with_schema(
        self,
        model_type: Optional[ModelType] = None,
        system_instruction: Optional[str] = None,
        response_schema_type: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """
        Get AI model configured for structured output with schema validation

        Args:
            model_type: Specific model to use
            system_instruction: System instruction
            response_schema_type: Type of response schema to enforce
            tools: List of tool schemas for function calling
        """
        model_name = model_type.value if model_type else self.default_model
        if response_schema_type:
            generation_config = self.get_schema_aware_config(response_schema_type)
        else:
            generation_config = self.generation_config
        client = self._get_genai_client()
        return _GenAIModelWrapper(
            client=client,
            model_name=model_name,
            generation_config=generation_config,
            safety_settings=self.safety_settings,
            system_instruction=system_instruction,
        )

    def get_retry_config(self, operation_type: str = "default") -> Dict[str, Any]:
        """
        Get retry configuration for specific operation type

        Args:
            operation_type: Type of operation ("default", "quick_operations",
                          "long_operations", "critical_operations")
        """
        return self.retry_config.get(operation_type, self.retry_config["default"])

    def get_circuit_breaker_config(self) -> Dict[str, Any]:
        """Get circuit breaker configuration"""
        return self.circuit_breaker_config.copy()

    def get_model_timeout(self, model_type: ModelType) -> float:
        """Get timeout for specific model"""
        return self.circuit_breaker_config["model_timeouts"].get(model_type.value, 30.0)

    def update_retry_config(self, operation_type: str, **kwargs) -> None:
        """Update retry configuration for specific operation type"""
        if operation_type not in self.retry_config:
            self.retry_config[operation_type] = self.retry_config["default"].copy()
        self.retry_config[operation_type].update(kwargs)

    def update_circuit_breaker_config(self, **kwargs) -> None:
        """Update circuit breaker configuration"""
        self.circuit_breaker_config.update(kwargs)

    def get_offline_config(self) -> Dict[str, Any]:
        """Get offline mode configuration"""
        return self.offline_config.copy()

    def update_offline_config(self, **kwargs) -> None:
        """Update offline mode configuration"""
        self.offline_config.update(kwargs)

    def get_model_metadata(self, model_type: ModelType) -> ModelMetadata:
        """Get metadata for a specific model"""
        return MODEL_METADATA.get(model_type, MODEL_METADATA[ModelType.GEMINI_25_FLASH])

    def get_fallback_models(self, preferred_model: Optional[ModelType] = None) -> List[ModelType]:
        """Get ordered list of fallback models starting from preferred model"""
        if preferred_model and preferred_model in MODEL_FALLBACK_CHAIN:
            start_index = MODEL_FALLBACK_CHAIN.index(preferred_model)
            return MODEL_FALLBACK_CHAIN[start_index:]
        else:
            return MODEL_FALLBACK_CHAIN.copy()

    def calculate_task_complexity_score(self, task_context: Dict[str, Any]) -> float:
        """
        Calculate task complexity score based on context

        Args:
            task_context: Dictionary containing task information

        Returns:
            Complexity score from 0.0 (simple) to 1.0 (complex)
        """
        score = 0.0
        framework = task_context.get("framework", "")
        if framework in ["GDPR", "HIPAA", "SOX"]:
            score += 0.3
        elif framework in ["ISO27001", "SOC2"]:
            score += 0.2
        else:
            score += 0.1
        task_type = task_context.get("task_type", "")
        if "analysis" in task_type.lower() or "assessment" in task_type.lower():
            score += 0.3
        elif "recommendation" in task_type.lower():
            score += 0.2
        elif "help" in task_type.lower() or "guidance" in task_type.lower():
            score += 0.1
        prompt_length = task_context.get("prompt_length", 0)
        if prompt_length > 2000:
            score += 0.2
        elif prompt_length > MAX_ITEMS:
            score += 0.1
        business_context = task_context.get("business_context", {})
        if business_context.get("employee_count", 0) > MAX_ITEMS:
            score += 0.1
        return min(1.0, score)

    def _calculate_task_complexity(self, task_context: Dict[str, Any]) -> str:
        """
        Calculate task complexity category based on context (for test compatibility)

        Args:
            task_context: Dictionary containing task information

        Returns:
            Complexity category: "simple", "medium", or "complex"
        """
        complexity_score = self.calculate_task_complexity_score(task_context)
        if complexity_score < 0.3:
            return "simple"
        elif complexity_score > 0.7:
            return "complex"
        else:
            return "medium"

    def get_optimal_model(
        self,
        task_complexity: str = "medium",
        prefer_speed: bool = False,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """
        Get optimal model based on task complexity and preferences

        Args:
            task_complexity: "simple", "medium", "complex" or "auto" for automatic scoring
            prefer_speed: Whether to prioritize speed over capability
            task_context: Context for automatic complexity calculation
        """
        logger = get_logger(__name__)
        if task_complexity == "auto" and task_context:
            complexity_score = self.calculate_task_complexity_score(task_context)
            if complexity_score < 0.3:
                task_complexity = "simple"
            elif complexity_score > 0.7:
                task_complexity = "complex"
            else:
                task_complexity = "medium"
            logger.debug(
                "Auto-calculated task complexity: %s (score: %s)"
                % (task_complexity, complexity_score)
            )
        if task_complexity == "simple":
            selected_model = ModelType.GEMINI_FLASH if prefer_speed else ModelType.GEMINI_25_FLASH
        elif task_complexity == "complex":
            selected_model = ModelType.GEMINI_25_PRO
        else:
            selected_model = ModelType.GEMINI_25_FLASH
        metadata = self.get_model_metadata(selected_model)
        logger.info(
            "Model selected: %s for %s task (efficiency: %s)"
            % (selected_model.value, task_complexity, metadata.efficiency_score)
        )
        return selected_model

    def select_model_with_fallback(
        self,
        circuit_breaker,
        preferred_model: Optional[ModelType] = None,
        task_complexity: str = "medium",
    ) -> ModelType:
        """
        Select best available model considering circuit breaker state

        Args:
            circuit_breaker: Circuit breaker instance to check model availability
            preferred_model: Preferred model to try first
            task_complexity: Task complexity level

        Returns:
            Available model from fallback chain

        Raises:
            AIServiceException: If no models are available
        """
        if preferred_model:
            fallback_models = self.get_fallback_models(preferred_model)
        else:
            optimal_model = self.get_optimal_model(task_complexity)
            fallback_models = self.get_fallback_models(optimal_model)
        for model_type in fallback_models:
            if circuit_breaker.is_model_available(model_type.value):
                return model_type
        from services.ai.exceptions import AIServiceException

        raise AIServiceException(
            message="No AI models available - all circuits are open",
            service_name="AI Model Selection",
            error_code="NO_MODELS_AVAILABLE",
            context={"attempted_models": [m.value for m in fallback_models]},
        )


ai_config = AIConfig()


def get_ai_model(
    model_type: Optional[ModelType] = None,
    task_complexity: str = "medium",
    prefer_speed: bool = False,
    task_context: Optional[Dict[str, Any]] = None,
    system_instruction: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Any:
    """
    Convenience function to get AI model instance with intelligent selection, system instructions, and tools

    Args:
        model_type: Specific model to use (overrides intelligent selection)
        task_complexity: "simple", "medium", "complex", or "auto"
        prefer_speed: Whether to prioritize speed over capability
        task_context: Context for automatic complexity calculation
        system_instruction: System instruction to use with the model
        tools: List of tool schemas for function calling
    """
    if model_type is None:
        try:
            model_type = ai_config.get_optimal_model(task_complexity, prefer_speed, task_context)
        except Exception:
            model_type = ai_config.default_model_type
    return ai_config.get_model(model_type, system_instruction=system_instruction, tools=tools)


def get_structured_ai_model(
    response_schema_type: str,
    model_type: Optional[ModelType] = None,
    task_complexity: str = "medium",
    prefer_speed: bool = False,
    task_context: Optional[Dict[str, Any]] = None,
    system_instruction: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Any:
    """
    Convenience function to get AI model configured for structured output with schema validation

    Args:
        response_schema_type: Type of response schema to enforce (gap_analysis, recommendations, etc.)
        model_type: Specific model to use (overrides intelligent selection)
        task_complexity: "simple", "medium", "complex", or "auto"
        prefer_speed: Whether to prioritize speed over capability
        task_context: Context for automatic complexity calculation
        system_instruction: System instruction to use with the model
        tools: List of tool schemas for function calling
    """
    if model_type is None:
        model_type = ai_config.get_optimal_model(task_complexity, prefer_speed, task_context)
    return ai_config.get_model_with_schema(
        model_type=model_type,
        system_instruction=system_instruction,
        response_schema_type=response_schema_type,
        tools=tools,
    )


async def generate_compliance_content(prompt: str, model_type: Optional[ModelType] = None) -> str:
    """Generate compliance-focused content using optimized settings"""
    model = get_ai_model(model_type)
    original_config = ai_config.generation_config.copy()
    ai_config.update_generation_config(**ai_config.get_compliance_optimized_config())
    try:
        response = model.generate_content(prompt)
        return response.text
    finally:
        ai_config.generation_config = original_config


def generate_creative_content(prompt: str, model_type: Optional[ModelType] = None) -> str:
    """Generate creative content using higher temperature settings"""
    model = get_ai_model(model_type)
    original_config = ai_config.generation_config.copy()
    ai_config.update_generation_config(**ai_config.get_creative_config())
    try:
        response = model.generate_content(prompt)
        return response.text
    finally:
        ai_config.generation_config = original_config
