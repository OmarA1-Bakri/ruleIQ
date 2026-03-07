"""
Unit tests for AI Provider Factory

Tests the provider selection and instantiation logic.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any

from services.ai.providers.factory import ProviderFactory, TASK_COMPLEXITY_MAP
from services.ai.providers.base import AIProvider
from services.ai.exceptions import ModelUnavailableException


@pytest.fixture
def mock_instruction_manager():
    """Mock instruction manager."""
    manager = Mock()
    model = Mock()
    model.model_name = "gemini-1.5-flash"
    manager.get_model_with_instruction.return_value = (model, "test_instruction_id")
    return manager


@pytest.fixture
def mock_circuit_breaker():
    """Mock circuit breaker."""
    breaker = Mock()
    breaker.is_model_available.return_value = True
    return breaker


@pytest.fixture
def provider_factory(mock_instruction_manager, mock_circuit_breaker):
    """Create provider factory with mocks."""
    return ProviderFactory(mock_instruction_manager, mock_circuit_breaker)


class TestProviderFactory:
    """Test provider factory functionality."""

    def test_initialization(self, provider_factory):
        """Test factory initializes correctly."""
        assert provider_factory.instruction_manager is not None
        assert provider_factory.circuit_breaker is not None
        assert provider_factory._gemini_provider is None
        assert provider_factory._openai_provider is None
        assert provider_factory._anthropic_provider is None

    def test_get_provider_for_help_task(self, provider_factory, mock_instruction_manager):
        """Test getting provider for help task."""
        model, instruction_id = provider_factory.get_provider_for_task("help")

        assert model is not None
        assert instruction_id == "test_instruction_id"

        # Verify correct complexity passed
        call_args = mock_instruction_manager.get_model_with_instruction.call_args
        assert call_args[1]["task_complexity"] == "simple"
        assert call_args[1]["prefer_speed"] is True

    def test_get_provider_for_analysis_task(self, provider_factory, mock_instruction_manager):
        """Test getting provider for analysis task."""
        model, instruction_id = provider_factory.get_provider_for_task("analysis")

        # Verify correct complexity passed
        call_args = mock_instruction_manager.get_model_with_instruction.call_args
        assert call_args[1]["task_complexity"] == "complex"
        assert call_args[1]["prefer_speed"] is False

    def test_get_provider_with_context(self, provider_factory):
        """Test getting provider with context."""
        context = {"framework": "GDPR", "business_context": {"industry": "healthcare"}}

        model, instruction_id = provider_factory.get_provider_for_task("assessment", context)
        assert model is not None

    def test_get_provider_with_tools(self, provider_factory):
        """Test getting provider with tools."""
        tools = [{"name": "search", "description": "Search tool"}]

        model, instruction_id = provider_factory.get_provider_for_task("help", tools=tools)
        assert model is not None

    def test_get_provider_with_cached_content(self, provider_factory):
        """Test getting provider with cached content."""
        cached_content = Mock()

        model, instruction_id = provider_factory.get_provider_for_task(
            "help", cached_content=cached_content
        )

        assert model is not None
        assert hasattr(model, "_cached_content")
        assert model._cached_content == cached_content

    def test_circuit_breaker_fallback(self, provider_factory, mock_circuit_breaker):
        """Test fallback when circuit breaker blocks primary model."""
        # First call returns False (primary unavailable), second returns True (fallback available)
        mock_circuit_breaker.is_model_available.side_effect = [False, True]

        with patch("services.ai.providers.factory.get_ai_model") as mock_get_model:
            fallback_model = Mock()
            fallback_model.model_name = "gemini-1.5-flash-fallback"
            mock_get_model.return_value = fallback_model

            model, instruction_id = provider_factory.get_provider_for_task("help")

            assert model == fallback_model
            assert instruction_id == "fallback_default"

    def test_all_models_unavailable(self, provider_factory, mock_circuit_breaker):
        """Test exception when all models unavailable."""
        mock_circuit_breaker.is_model_available.return_value = False

        with pytest.raises(ModelUnavailableException) as exc_info:
            provider_factory.get_provider_for_task("help")

        assert "circuit breaker" in str(exc_info.value.reason).lower()

    def test_get_provider_by_name_gemini(self, provider_factory):
        """Test getting Gemini provider by name."""
        provider = provider_factory.get_provider_by_name("gemini")

        assert provider is not None
        assert provider_factory._gemini_provider is not None

        # Test caching
        provider2 = provider_factory.get_provider_by_name("gemini")
        assert provider is provider2

    def test_get_provider_by_name_invalid(self, provider_factory):
        """Test exception for invalid provider name."""
        with pytest.raises(ValueError) as exc_info:
            provider_factory.get_provider_by_name("invalid_provider")

        assert "Unknown provider" in str(exc_info.value)

    def test_get_available_providers(self, provider_factory):
        """Test getting list of available providers."""
        available = provider_factory.get_available_providers()

        assert isinstance(available, list)
        assert "gemini" in available

    def test_task_complexity_mapping(self):
        """Test task complexity mappings are correct."""
        assert TASK_COMPLEXITY_MAP["help"] == ("simple", True)
        assert TASK_COMPLEXITY_MAP["analysis"] == ("complex", False)
        assert TASK_COMPLEXITY_MAP["assessment"] == ("complex", False)
        assert TASK_COMPLEXITY_MAP["recommendations"] == ("medium", False)

    def test_model_selection_exception_handling(self, provider_factory, mock_instruction_manager):
        """Test exception handling during model selection."""
        mock_instruction_manager.get_model_with_instruction.side_effect = Exception("API error")

        with pytest.raises(ModelUnavailableException) as exc_info:
            provider_factory.get_provider_for_task("help")

        assert "Model selection failed" in str(exc_info.value.reason)


@pytest.mark.integration
class TestProviderFactoryIntegration:
    """Integration tests for provider factory."""

    def test_real_provider_initialization(self):
        """Test factory can initialize with real dependencies."""
        factory = ProviderFactory()

        assert factory.instruction_manager is not None
        assert factory.circuit_breaker is not None

    @pytest.mark.skip(reason="Requires AI API keys")
    def test_real_model_selection(self):
        """Test actual model selection with real API."""
        factory = ProviderFactory()
        model, instruction_id = factory.get_provider_for_task("help")

        assert model is not None
        assert instruction_id is not None
