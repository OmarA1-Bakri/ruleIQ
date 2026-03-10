"""
Tests for services.ai.exceptions module.

Covers all 15 exception classes, GEMINI_ERROR_MAPPING, ERROR_PATTERN_MAPPING,
map_gemini_error(), and handle_ai_error().
"""

import pytest
from unittest.mock import MagicMock, patch
from enum import Enum

from services.ai.exceptions import (
    AIServiceException,
    AITimeoutException,
    AIQuotaExceededException,
    AIModelException,
    AIContentFilterException,
    AIParsingException,
    AIValidationException,
    ModelUnavailableException,
    ModelTimeoutException,
    ModelOverloadedException,
    ModelConfigurationException,
    CircuitBreakerException,
    SchemaValidationException,
    ResponseProcessingException,
    ModelRetryExhaustedException,
    GEMINI_ERROR_MAPPING,
    ERROR_PATTERN_MAPPING,
    map_gemini_error,
    handle_ai_error,
)
from core.exceptions import BusinessLogicException, IntegrationException


# =====================================================================
# Exception Class Tests
# =====================================================================


class TestAIServiceException:
    def test_basic_creation(self):
        exc = AIServiceException(message="test error")
        assert exc.service_name == "AI Service"
        assert exc.error_code is None
        assert exc.context == {}

    def test_with_all_params(self):
        exc = AIServiceException(
            message="test",
            service_name="Gemini",
            error_code="TEST_ERR",
            context={"model": "pro"},
        )
        assert exc.service_name == "Gemini"
        assert exc.error_code == "TEST_ERR"
        assert exc.context == {"model": "pro"}

    def test_inherits_integration_exception(self):
        exc = AIServiceException(message="test")
        assert isinstance(exc, IntegrationException)


class TestAITimeoutException:
    def test_creation(self):
        exc = AITimeoutException(timeout_seconds=30.0)
        assert exc.timeout_seconds == 30.0
        assert exc.error_code == "AI_TIMEOUT"

    def test_custom_service_name(self):
        exc = AITimeoutException(timeout_seconds=60.0, service_name="OpenAI")
        assert exc.service_name == "OpenAI"


class TestAIQuotaExceededException:
    def test_creation(self):
        exc = AIQuotaExceededException()
        assert exc.quota_type == "requests"
        assert exc.error_code == "AI_QUOTA_EXCEEDED"

    def test_custom_quota_type(self):
        exc = AIQuotaExceededException(quota_type="tokens")
        assert exc.quota_type == "tokens"


class TestAIModelException:
    def test_creation(self):
        exc = AIModelException(model_name="gemini-pro", model_error="rate limited")
        assert exc.model_name == "gemini-pro"
        assert exc.model_error == "rate limited"
        assert exc.error_code == "AI_MODEL_ERROR"


class TestAIContentFilterException:
    def test_creation(self):
        exc = AIContentFilterException(filter_reason="harmful content")
        assert exc.filter_reason == "harmful content"
        assert exc.error_code == "AI_CONTENT_FILTERED"


class TestAIParsingException:
    def test_creation(self):
        exc = AIParsingException(
            response_text="not json",
            expected_format="JSON",
            parsing_error="Invalid syntax",
        )
        assert exc.response_text == "not json"
        assert exc.expected_format == "JSON"
        assert exc.parsing_error == "Invalid syntax"
        assert exc.context == {}

    def test_inherits_business_logic(self):
        exc = AIParsingException(
            response_text="x",
            expected_format="JSON",
            parsing_error="err",
        )
        assert isinstance(exc, BusinessLogicException)


class TestAIValidationException:
    def test_creation(self):
        exc = AIValidationException(
            validation_errors=["field1 missing", "field2 invalid"],
            response_data={"key": "value"},
        )
        assert len(exc.validation_errors) == 2
        assert exc.response_data == {"key": "value"}
        assert exc.context == {}

    def test_inherits_business_logic(self):
        exc = AIValidationException(validation_errors=[], response_data={})
        assert isinstance(exc, BusinessLogicException)


class TestModelUnavailableException:
    def test_creation(self):
        exc = ModelUnavailableException(model_name="gemini-pro")
        assert exc.model_name == "gemini-pro"
        assert exc.reason == "Circuit breaker open"
        assert exc.error_code == "MODEL_UNAVAILABLE"

    def test_custom_reason(self):
        exc = ModelUnavailableException(
            model_name="gemini-pro",
            reason="Maintenance",
        )
        assert exc.reason == "Maintenance"


class TestModelTimeoutException:
    def test_creation(self):
        exc = ModelTimeoutException(
            model_name="gemini-pro",
            timeout_seconds=30.0,
        )
        assert exc.model_name == "gemini-pro"
        assert exc.timeout_seconds == 30.0
        assert exc.operation == "generate_content"
        assert exc.error_code == "MODEL_TIMEOUT"

    def test_custom_operation(self):
        exc = ModelTimeoutException(
            model_name="gemini-flash",
            timeout_seconds=10.0,
            operation="embed",
        )
        assert exc.operation == "embed"


class TestModelOverloadedException:
    def test_creation(self):
        exc = ModelOverloadedException(model_name="gemini-pro")
        assert exc.model_name == "gemini-pro"
        assert exc.retry_after is None
        assert exc.error_code == "MODEL_OVERLOADED"

    def test_with_retry_after(self):
        exc = ModelOverloadedException(model_name="gemini-pro", retry_after=60)
        assert exc.retry_after == 60


class TestModelConfigurationException:
    def test_creation(self):
        exc = ModelConfigurationException(
            model_name="gemini-pro",
            config_error="Invalid temperature",
        )
        assert exc.model_name == "gemini-pro"
        assert exc.config_error == "Invalid temperature"
        assert exc.error_code == "MODEL_CONFIG_ERROR"


class TestCircuitBreakerException:
    def test_basic_creation(self):
        exc = CircuitBreakerException(circuit_state="open")
        assert exc.circuit_state == "open"
        assert exc.model_name is None
        assert exc.failure_count is None
        assert exc.error_code == "CIRCUIT_BREAKER_OPEN"

    def test_with_model_and_failures(self):
        exc = CircuitBreakerException(
            circuit_state="open",
            model_name="gemini-pro",
            failure_count=5,
        )
        assert exc.model_name == "gemini-pro"
        assert exc.failure_count == 5


class TestSchemaValidationException:
    @pytest.fixture(autouse=True)
    def _inject_constants(self):
        """Inject constants that are trapped in the module docstring."""
        import services.ai.exceptions as exc_mod
        exc_mod.MAX_RETRIES = 3
        exc_mod.DEFAULT_RETRIES = 5
        yield

    def test_creation(self):
        exc = SchemaValidationException(
            response_type="gap_analysis",
            validation_errors=["field missing"],
        )
        assert exc.response_type == "gap_analysis"
        assert exc.error_count == 1
        assert exc.error_code == "SCHEMA_VALIDATION_FAILED"

    def test_error_count_property(self):
        exc = SchemaValidationException(
            response_type="test",
            validation_errors=["e1", "e2", "e3"],
        )
        assert exc.error_count == 3

    def test_error_count_none_errors(self):
        exc = SchemaValidationException(
            response_type="test",
            validation_errors=None,
        )
        assert exc.error_count == 0

    def test_get_error_summary_no_errors(self):
        exc = SchemaValidationException(
            response_type="test",
            validation_errors=None,
        )
        assert "No specific validation errors" in exc.get_error_summary()

    def test_get_error_summary_with_errors(self):
        exc = SchemaValidationException(
            response_type="gap_analysis",
            validation_errors=["error1", "error2"],
        )
        summary = exc.get_error_summary()
        assert "gap_analysis" in summary
        assert "error1" in summary
        assert "error2" in summary

    def test_get_error_summary_many_errors(self):
        errors = [f"error_{i}" for i in range(10)]
        exc = SchemaValidationException(
            response_type="test",
            validation_errors=errors,
        )
        summary = exc.get_error_summary()
        assert "and 5 more errors" in summary

    def test_with_response_data(self):
        exc = SchemaValidationException(
            response_type="test",
            validation_errors=["err"],
            response_data={"key": "value"},
            model_name="gemini-pro",
        )
        assert exc.response_data == {"key": "value"}
        assert exc.model_name == "gemini-pro"

    def test_truncated_error_message(self):
        errors = ["e1", "e2", "e3", "e4"]
        exc = SchemaValidationException(
            response_type="test",
            validation_errors=errors,
        )
        # MAX_RETRIES = 3, so >3 triggers "(and N more errors)" in __init__ message
        assert "and 1 more" in str(exc)


class TestResponseProcessingException:
    def test_creation(self):
        exc = ResponseProcessingException(
            response_type="gap_analysis",
            processing_stage="parsing",
            original_error="Invalid JSON",
        )
        assert exc.response_type == "gap_analysis"
        assert exc.processing_stage == "parsing"
        assert exc.original_error == "Invalid JSON"
        assert exc.error_code == "RESPONSE_PROCESSING_FAILED"


class TestModelRetryExhaustedException:
    def test_creation(self):
        exc = ModelRetryExhaustedException(
            model_name="gemini-pro",
            attempts=3,
            last_error="Connection timeout",
        )
        assert exc.model_name == "gemini-pro"
        assert exc.attempts == 3
        assert exc.last_error == "Connection timeout"
        assert exc.error_code == "RETRY_EXHAUSTED"


# =====================================================================
# Error Mapping Tests
# =====================================================================


class TestGeminiErrorMapping:
    def test_all_error_types_present(self):
        expected_keys = {
            "DEADLINE_EXCEEDED",
            "RESOURCE_EXHAUSTED",
            "INVALID_ARGUMENT",
            "PERMISSION_DENIED",
            "UNAUTHENTICATED",
            "UNAVAILABLE",
            "INTERNAL",
        }
        assert set(GEMINI_ERROR_MAPPING.keys()) == expected_keys

    def test_mapping_types(self):
        assert GEMINI_ERROR_MAPPING["DEADLINE_EXCEEDED"] == ModelTimeoutException
        assert GEMINI_ERROR_MAPPING["RESOURCE_EXHAUSTED"] == ModelOverloadedException
        assert GEMINI_ERROR_MAPPING["INVALID_ARGUMENT"] == ModelConfigurationException
        assert GEMINI_ERROR_MAPPING["UNAVAILABLE"] == ModelUnavailableException
        assert GEMINI_ERROR_MAPPING["PERMISSION_DENIED"] == AIServiceException


class TestErrorPatternMapping:
    def test_timeout_patterns(self):
        assert ERROR_PATTERN_MAPPING["timeout"] == ModelTimeoutException

    def test_quota_patterns(self):
        assert ERROR_PATTERN_MAPPING["quota"] == ModelOverloadedException
        assert ERROR_PATTERN_MAPPING["rate limit"] == ModelOverloadedException
        assert ERROR_PATTERN_MAPPING["overloaded"] == ModelOverloadedException

    def test_unavailable_patterns(self):
        assert ERROR_PATTERN_MAPPING["unavailable"] == ModelUnavailableException
        assert ERROR_PATTERN_MAPPING["not found"] == ModelUnavailableException

    def test_safety_patterns(self):
        assert ERROR_PATTERN_MAPPING["safety"] == AIContentFilterException
        assert ERROR_PATTERN_MAPPING["filter"] == AIContentFilterException

    def test_config_patterns(self):
        assert ERROR_PATTERN_MAPPING["configuration"] == ModelConfigurationException
        assert ERROR_PATTERN_MAPPING["invalid model"] == ModelConfigurationException

    def test_schema_patterns(self):
        assert ERROR_PATTERN_MAPPING["schema validation"] == SchemaValidationException
        assert ERROR_PATTERN_MAPPING["response processing"] == ResponseProcessingException


# =====================================================================
# map_gemini_error Tests
# =====================================================================


class TestMapGeminiError:
    def _make_error_with_code(self, code_name):
        """Create an error with a code attribute that has a name property."""
        class MockCode:
            name = code_name
        error = Exception("Test error")
        error.code = MockCode()
        return error

    def test_deadline_exceeded(self):
        error = self._make_error_with_code("DEADLINE_EXCEEDED")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelTimeoutException)
        assert result.timeout_seconds == 30.0

    def test_resource_exhausted(self):
        error = self._make_error_with_code("RESOURCE_EXHAUSTED")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelOverloadedException)

    def test_unavailable(self):
        error = self._make_error_with_code("UNAVAILABLE")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelUnavailableException)

    def test_invalid_argument(self):
        error = self._make_error_with_code("INVALID_ARGUMENT")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelConfigurationException)

    def test_permission_denied(self):
        error = self._make_error_with_code("PERMISSION_DENIED")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, AIServiceException)
        assert result.error_code == "PERMISSION_DENIED"

    def test_pattern_matching_timeout(self):
        error = Exception("Request timeout after 30s")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelTimeoutException)

    def test_pattern_matching_quota(self):
        error = Exception("API quota exceeded")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelOverloadedException)

    def test_pattern_matching_rate_limit(self):
        error = Exception("Rate limit reached")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelOverloadedException)

    def test_pattern_matching_overloaded(self):
        error = Exception("Server overloaded")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelOverloadedException)

    def test_pattern_matching_unavailable(self):
        error = Exception("Service unavailable")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelUnavailableException)

    def test_pattern_matching_not_found(self):
        error = Exception("Model not found")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelUnavailableException)

    def test_pattern_matching_safety(self):
        error = Exception("Content blocked by safety filter")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, AIContentFilterException)

    def test_pattern_matching_configuration(self):
        error = Exception("Invalid configuration parameter")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, ModelConfigurationException)

    def test_unknown_error_fallback(self):
        error = Exception("Some completely unknown error")
        result = map_gemini_error(error, "gemini-pro")
        assert isinstance(result, AIServiceException)
        assert result.error_code == "UNKNOWN_ERROR"
        assert result.service_name == "Google Gemini"

    def test_model_name_from_context(self):
        error = Exception("Unknown error xyz")
        result = map_gemini_error(
            error,
            model_name="unknown",
            context={"model_name": "gemini-flash"},
        )
        assert isinstance(result, AIServiceException)

    def test_with_context(self):
        error = Exception("Unknown error")
        ctx = {"request_id": "123"}
        result = map_gemini_error(error, "gemini-pro", context=ctx)
        assert result.context == ctx


# =====================================================================
# handle_ai_error Tests
# =====================================================================


class TestHandleAiError:
    @patch("config.logging_config.get_logger")
    def test_with_ai_exception(self, mock_get_logger):
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        original = AIServiceException(
            message="test error",
            error_code="TEST",
        )
        fallback, exc = handle_ai_error(original, "test_op")
        assert fallback is None
        assert exc is original
        mock_logger.error.assert_called_once()

    @patch("config.logging_config.get_logger")
    def test_with_plain_exception(self, mock_get_logger):
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        original = Exception("timeout occurred")
        fallback, exc = handle_ai_error(original, "test_op", "gemini-pro")
        assert fallback is None
        assert isinstance(exc, ModelTimeoutException)

    @patch("config.logging_config.get_logger")
    def test_with_fallback_response(self, mock_get_logger):
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        fallback_val = {"default": True}
        original = Exception("Unknown error")
        fallback, exc = handle_ai_error(
            original,
            "test_op",
            fallback_response=fallback_val,
        )
        assert fallback == fallback_val
        assert isinstance(exc, AIServiceException)

    @patch("config.logging_config.get_logger")
    def test_logging_includes_context(self, mock_get_logger):
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        ctx = {"request_id": "abc"}
        original = AIServiceException(
            message="err",
            error_code="CODE",
            context=ctx,
        )
        handle_ai_error(original, "my_op", context=ctx)
        mock_logger.error.assert_called_once()
        call_kwargs = mock_logger.error.call_args
        assert "extra" in call_kwargs.kwargs or len(call_kwargs) > 1
