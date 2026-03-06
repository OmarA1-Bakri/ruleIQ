"""
import logging
import requests


logger = logging.getLogger(__name__)
# Constants
DEFAULT_RETRIES = 5
MAX_RETRIES = 3


AI-specific exceptions for better error handling and debugging.
"""

from typing import Any, Dict, Optional
from core.exceptions import BusinessLogicException, IntegrationException


class AIServiceException(IntegrationException):
    """Base exception for AI service errors."""

    def __init__(
        self,
        message: str,
        service_name: str = "AI Service",
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.service_name = service_name
        self.error_code = error_code
        self.context = context or {}


class AITimeoutException(AIServiceException):
    """Raised when AI service requests timeout."""

    def __init__(
        self,
        timeout_seconds: float,
        service_name: str = "AI Service",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = (f"{service_name} request timed out after {timeout_seconds} seconds",)
        super().__init__(
            message=message, service_name=service_name, error_code="AI_TIMEOUT", context=context
        )
        self.timeout_seconds = timeout_seconds


class AIQuotaExceededException(AIServiceException):
    """Raised when AI service quota is exceeded."""

    def __init__(
        self,
        quota_type: str = "requests",
        service_name: str = "AI Service",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = f"{service_name} {quota_type} quota exceeded"
        super().__init__(
            message=message,
            service_name=service_name,
            error_code="AI_QUOTA_EXCEEDED",
            context=context,
        )
        self.quota_type = quota_type


class AIModelException(AIServiceException):
    """Raised when AI model encounters an error."""

    def __init__(
        self,
        model_name: str,
        model_error: str,
        service_name: str = "AI Service",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = f"{service_name} model '{model_name}' error: {model_error}"
        super().__init__(
            message=message, service_name=service_name, error_code="AI_MODEL_ERROR", context=context
        )
        self.model_name = model_name
        self.model_error = model_error


class AIContentFilterException(AIServiceException):
    """Raised when AI content is filtered for safety."""

    def __init__(
        self,
        filter_reason: str,
        service_name: str = "AI Service",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = f"{service_name} content filtered: {filter_reason}"
        super().__init__(
            message=message,
            service_name=service_name,
            error_code="AI_CONTENT_FILTERED",
            context=context,
        )
        self.filter_reason = filter_reason


class AIParsingException(BusinessLogicException):
    """Raised when AI response cannot be parsed."""

    def __init__(
        self,
        response_text: str,
        expected_format: str,
        parsing_error: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = (f"Failed to parse AI response as {expected_format}: {parsing_error}",)
        super().__init__(message)
        self.response_text = response_text
        self.expected_format = expected_format
        self.parsing_error = parsing_error
        self.context = context or {}


class AIValidationException(BusinessLogicException):
    """Raised when AI response fails validation."""

    def __init__(
        self,
        validation_errors: list,
        response_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = f"AI response validation failed: {', '.join(validation_errors)}"
        super().__init__(message)
        self.validation_errors = validation_errors
        self.response_data = response_data
        self.context = context or {}


class ModelUnavailableException(AIServiceException):
    """Raised when a specific AI model is unavailable."""

    def __init__(
        self,
        model_name: str,
        reason: str = "Circuit breaker open",
        service_name: str = "AI Service",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = f"Model '{model_name}' is unavailable: {reason}"
        super().__init__(
            message=message,
            service_name=service_name,
            error_code="MODEL_UNAVAILABLE",
            context=context,
        )
        self.model_name = model_name
        self.reason = reason


class ModelTimeoutException(AIServiceException):
    """Raised when AI model request times out."""

    def __init__(
        self,
        model_name: str,
        timeout_seconds: float,
        operation: str = "generate_content",
        service_name: str = "AI Service",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = (f"Model '{model_name}' timed out after {timeout_seconds}s during {operation}",)
        super().__init__(
            message=message, service_name=service_name, error_code="MODEL_TIMEOUT", context=context
        )
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.operation = operation


class ModelOverloadedException(AIServiceException):
    """Raised when AI model is overloaded and cannot process requests."""

    def __init__(
        self,
        model_name: str,
        retry_after: Optional[int] = None,
        service_name: str = "AI Service",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = f"Model '{model_name}' is overloaded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(
            message=message,
            service_name=service_name,
            error_code="MODEL_OVERLOADED",
            context=context,
        )
        self.model_name = model_name
        self.retry_after = retry_after


class ModelConfigurationException(AIServiceException):
    """Raised when AI model configuration is invalid."""

    def __init__(
        self,
        model_name: str,
        config_error: str,
        service_name: str = "AI Service",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = f"Model '{model_name}' configuration error: {config_error}"
        super().__init__(
            message=message,
            service_name=service_name,
            error_code="MODEL_CONFIG_ERROR",
            context=context,
        )
        self.model_name = model_name
        self.config_error = config_error


class CircuitBreakerException(AIServiceException):
    """Raised when circuit breaker prevents operation."""

    def __init__(
        self,
        circuit_state: str,
        model_name: Optional[str] = None,
        failure_count: Optional[int] = None,
        service_name: str = "AI Circuit Breaker",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if model_name:
            message = f"Circuit breaker {circuit_state} for model '{model_name}'"
        else:
            message = f"Circuit breaker {circuit_state}"
        if failure_count:
            message += f" (failures: {failure_count})"
        super().__init__(
            message=message,
            service_name=service_name,
            error_code="CIRCUIT_BREAKER_OPEN",
            context=context,
        )
        self.circuit_state = circuit_state
        self.model_name = model_name
        self.failure_count = failure_count


class SchemaValidationException(AIServiceException):
    """Raised when AI response fails schema validation in Phase 6 implementation."""

    def __init__(
        self,
        response_type: str,
        validation_errors: list,
        response_data: Optional[Dict[str, Any]] = None,
        model_name: str = "unknown",
        service_name: str = "AI Schema Validator",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        error_summary = f"Schema validation failed for {response_type}"
        if validation_errors:
            error_summary += f": {', '.join(validation_errors[:3])}"
            if len(validation_errors) > MAX_RETRIES:
                error_summary += f" (and {len(validation_errors) - 3} more errors)"
        super().__init__(
            message=error_summary,
            service_name=service_name,
            error_code="SCHEMA_VALIDATION_FAILED",
            context=context,
        )
        self.response_type = response_type
        self.validation_errors = validation_errors
        self.response_data = response_data
        self.model_name = model_name

    @property
    def error_count(self) -> int:
        """Get the number of validation errors."""
        return len(self.validation_errors) if self.validation_errors else 0

    def get_error_summary(self) -> str:
        """Get a formatted summary of validation errors."""
        if not self.validation_errors:
            return "No specific validation errors available"
        summary = f"""Schema validation failed for {self.response_type} with {self.error_count} errors:
"""
        for i, error in enumerate(self.validation_errors[:5], 1):
            summary += f"  {i}. {error}\n"
        if len(self.validation_errors) > DEFAULT_RETRIES:
            summary += f"  ... and {len(self.validation_errors) - 5} more errors"
        return summary


class ResponseProcessingException(AIServiceException):
    """Raised when AI response processing fails during Phase 6 implementation."""

    def __init__(
        self,
        response_type: str,
        processing_stage: str,
        original_error: str,
        model_name: str = "unknown",
        service_name: str = "AI Response Processor",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = (
            f"Response processing failed at {processing_stage} for {response_type}: {original_error}",
        )
        super().__init__(
            message=message,
            service_name=service_name,
            error_code="RESPONSE_PROCESSING_FAILED",
            context=context,
        )
        self.response_type = response_type
        self.processing_stage = processing_stage
        self.original_error = original_error
        self.model_name = model_name


class ModelRetryExhaustedException(AIServiceException):
    """Raised when all retry attempts for a model have been exhausted."""

    def __init__(
        self,
        model_name: str,
        attempts: int,
        last_error: str,
        service_name: str = "AI Service",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        message = (
            f"Model '{model_name}' retry exhausted after {attempts} attempts. Last error: {last_error}",
        )
        super().__init__(
            message=message,
            service_name=service_name,
            error_code="RETRY_EXHAUSTED",
            context=context,
        )
        self.model_name = model_name
        self.attempts = attempts
        self.last_error = last_error


GEMINI_ERROR_MAPPING = {
    "DEADLINE_EXCEEDED": ModelTimeoutException,
    "RESOURCE_EXHAUSTED": ModelOverloadedException,
    "INVALID_ARGUMENT": ModelConfigurationException,
    "PERMISSION_DENIED": AIServiceException,
    "UNAUTHENTICATED": AIServiceException,
    "UNAVAILABLE": ModelUnavailableException,
    "INTERNAL": AIServiceException,
}
ERROR_PATTERN_MAPPING = {
    "timeout": ModelTimeoutException,
    "quota": ModelOverloadedException,
    "rate limit": ModelOverloadedException,
    "overloaded": ModelOverloadedException,
    "unavailable": ModelUnavailableException,
    "not found": ModelUnavailableException,
    "safety": AIContentFilterException,
    "filter": AIContentFilterException,
    "configuration": ModelConfigurationException,
    "invalid model": ModelConfigurationException,
    "schema validation": SchemaValidationException,
    "response processing": ResponseProcessingException,
}


def map_gemini_error(
    error: Exception, model_name: str = "unknown", context: Optional[Dict[str, Any]] = None
) -> AIServiceException:
    """Map Google Gemini errors to our AI exceptions."""
    error_message = str(error)
    error_type = getattr(error, "code", None)
    if model_name == "unknown" and context and "model_name" in context:
        model_name = context["model_name"]
    if error_type and error_type.name in GEMINI_ERROR_MAPPING:
        exception_class = GEMINI_ERROR_MAPPING[error_type.name]
        if exception_class == ModelTimeoutException:
            return ModelTimeoutException(
                model_name=model_name,
                timeout_seconds=30.0,
                service_name="Google Gemini",
                context=context,
            )
        elif exception_class == ModelOverloadedException:
            return ModelOverloadedException(
                model_name=model_name, service_name="Google Gemini", context=context
            )
        elif exception_class == ModelUnavailableException:
            return ModelUnavailableException(
                model_name=model_name,
                reason=error_message,
                service_name="Google Gemini",
                context=context,
            )
        elif exception_class == ModelConfigurationException:
            return ModelConfigurationException(
                model_name=model_name,
                config_error=error_message,
                service_name="Google Gemini",
                context=context,
            )
        else:
            return exception_class(
                message=error_message,
                service_name="Google Gemini",
                error_code=error_type.name,
                context=context,
            )
    error_lower = error_message.lower()
    for pattern, exception_class in ERROR_PATTERN_MAPPING.items():
        if pattern in error_lower:
            if exception_class == ModelTimeoutException:
                return ModelTimeoutException(
                    model_name=model_name,
                    timeout_seconds=30.0,
                    service_name="Google Gemini",
                    context=context,
                )
            elif exception_class == ModelOverloadedException:
                return ModelOverloadedException(
                    model_name=model_name, service_name="Google Gemini", context=context
                )
            elif exception_class == ModelUnavailableException:
                return ModelUnavailableException(
                    model_name=model_name,
                    reason=error_message,
                    service_name="Google Gemini",
                    context=context,
                )
            elif exception_class == ModelConfigurationException:
                return ModelConfigurationException(
                    model_name=model_name,
                    config_error=error_message,
                    service_name="Google Gemini",
                    context=context,
                )
            elif exception_class == AIContentFilterException:
                return AIContentFilterException(
                    filter_reason=error_message, service_name="Google Gemini", context=context
                )
    return AIServiceException(
        message=error_message,
        service_name="Google Gemini",
        error_code="UNKNOWN_ERROR",
        context=context,
    )


def handle_ai_error(
    error: Exception,
    operation: str,
    model_name: str = "unknown",
    context: Optional[Dict[str, Any]] = None,
    fallback_response: Optional[Any] = None,
) -> tuple[Optional[Any], AIServiceException]:
    """
    Handle AI errors with proper logging and fallback.

    Returns:
        Tuple of (fallback_response, mapped_exception)
    """
    from config.logging_config import get_logger

    logger = get_logger(__name__)
    if isinstance(error, AIServiceException):
        ai_exception = error
    else:
        ai_exception = map_gemini_error(error, model_name, context)
    logger.error(
        "AI error in %s: %s" % (operation, ai_exception.message),
        extra={
            "operation": operation,
            "error_code": ai_exception.error_code,
            "service_name": ai_exception.service_name,
            "context": ai_exception.context,
        },
    )
    return fallback_response, ai_exception
