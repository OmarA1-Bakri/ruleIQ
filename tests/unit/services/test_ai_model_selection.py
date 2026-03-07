"""
Unit tests for AI Model Selection and Configuration.

Tests the intelligent model selection logic, model metadata,
and task-complexity based model assignment.
"""

# Constants
DEFAULT_RETRIES = 5.0

import os
from unittest.mock import Mock, patch
import pytest
from config.ai_config import (
    MODEL_FALLBACK_CHAIN,
    MODEL_METADATA,
    AIConfig,
    ModelMetadata,
    ModelType,
    get_ai_model,
)

from tests.test_constants import MAX_RETRIES


class TestModelMetadata:
    """Test suite for ModelMetadata functionality."""

    def test_model_metadata_creation(self):
        """Test ModelMetadata creation and properties."""
        metadata = ModelMetadata(
            name="test-model",
            cost_score=5.0,
            speed_score=8.0,
            capability_score=9.0,
            max_tokens=8192,
            timeout_seconds=30.0,
        )
        assert metadata.name == "test-model"
        assert metadata.cost_score == DEFAULT_RETRIES
        assert metadata.speed_score == 8.0
        assert metadata.capability_score == 9.0
        assert metadata.efficiency_score == 9.0 / 5.0

    def test_efficiency_score_calculation(self):
        """Test efficiency score calculation."""
        high_efficiency = ModelMetadata(
            name="efficient-model",
            cost_score=2.0,
            speed_score=7.0,
            capability_score=9.0,
            max_tokens=8192,
            timeout_seconds=30.0,
        )
        low_efficiency = ModelMetadata(
            name="inefficient-model",
            cost_score=9.0,
            speed_score=5.0,
            capability_score=3.0,
            max_tokens=4096,
            timeout_seconds=30.0,
        )
        assert high_efficiency.efficiency_score > low_efficiency.efficiency_score

    def test_efficiency_score_zero_cost(self):
        """Test efficiency score with zero cost."""
        metadata = ModelMetadata(
            name="free-model",
            cost_score=0.0,
            speed_score=5.0,
            capability_score=7.0,
            max_tokens=4096,
            timeout_seconds=30.0,
        )
        assert metadata.efficiency_score == 0


class TestModelType:
    """Test suite for ModelType enum."""

    def test_model_type_values(self):
        """Test ModelType enum values."""
        assert ModelType.GEMINI_25_PRO.value == "gemini-2.5-pro"
        assert ModelType.GEMINI_25_FLASH.value == "gemini-2.5-flash"
        assert ModelType.GEMINI_FLASH.value == "gemini-2.5-flash-preview-05-20"
        assert ModelType.GEMMA_3.value == "gemma-3-8b-it"

    def test_fallback_chain_order(self):
        """Test model fallback chain is properly ordered."""
        assert len(MODEL_FALLBACK_CHAIN) >= MAX_RETRIES
        assert ModelType.GEMINI_25_PRO in MODEL_FALLBACK_CHAIN
        assert ModelType.GEMINI_25_FLASH in MODEL_FALLBACK_CHAIN
        pro_index = MODEL_FALLBACK_CHAIN.index(ModelType.GEMINI_25_PRO)
        flash_index = MODEL_FALLBACK_CHAIN.index(ModelType.GEMINI_25_FLASH)
        assert pro_index < flash_index


class TestAIConfig:
    """Test suite for AIConfig class."""

    @pytest.fixture
    def ai_config(self):
        """AI configuration instance for testing."""
        return AIConfig()

    def test_ai_config_initialization(self, ai_config):
        """Test AIConfig initializes correctly."""
        assert ai_config.default_model_type == ModelType.GEMINI_25_FLASH
        assert ai_config.fallback_chain == MODEL_FALLBACK_CHAIN
        assert len(ai_config.model_metadata) > 0

    def test_get_model_metadata(self, ai_config):
        """Test getting model metadata."""
        metadata = ai_config.get_model_metadata(ModelType.GEMINI_25_PRO)
        assert isinstance(metadata, ModelMetadata)
        assert metadata.name == ModelType.GEMINI_25_PRO.value
        assert metadata.cost_score > 0
        assert metadata.capability_score > 0

    def test_get_optimal_model_simple_task(self, ai_config):
        """Test optimal model selection for simple tasks."""
        model_type = ai_config.get_optimal_model(task_complexity="simple", prefer_speed=True)
        ai_config.get_model_metadata(model_type)
        assert model_type in [
            ModelType.GEMINI_FLASH,
            ModelType.GEMMA_3,
            ModelType.GEMINI_25_FLASH,
        ]

    def test_get_optimal_model_complex_task(self, ai_config):
        """Test optimal model selection for complex tasks."""
        model_type = ai_config.get_optimal_model(task_complexity="complex", prefer_speed=False)
        assert model_type in [ModelType.GEMINI_25_PRO, ModelType.GEMINI_25_FLASH]

    def test_get_optimal_model_with_context(self, ai_config):
        """Test optimal model selection with task context."""
        context = {
            "task_type": "analysis",
            "prompt_length": 5000,
            "framework": "gdpr",
            "business_context": {"industry": "healthcare"},
        }
        model_type = ai_config.get_optimal_model(task_complexity="auto", task_context=context)
        assert model_type in MODEL_FALLBACK_CHAIN

    def test_calculate_task_complexity_auto(self, ai_config):
        """Test automatic task complexity calculation."""
        simple_context = {"task_type": "help", "prompt_length": 100}
        complexity = ai_config._calculate_task_complexity(simple_context)
        assert complexity in ["simple", "medium"]
        complex_context = {"task_type": "analysis", "prompt_length": 3000, "framework": "gdpr"}
        complexity = ai_config._calculate_task_complexity(complex_context)
        assert complexity in ["medium", "complex"]

    def test_get_model_success(self, ai_config):
        """Test successful model instantiation returns a wrapper with generate_content."""
        mock_client = Mock()
        with patch.object(ai_config, "_get_genai_client", return_value=mock_client):
            model = ai_config.get_model(ModelType.GEMINI_25_FLASH)
        assert hasattr(model, "generate_content")
        assert hasattr(model, "model_name")

    def test_get_model_with_correct_model_name(self, ai_config):
        """Test model instantiation uses the correct model name."""
        mock_client = Mock()
        with patch.object(ai_config, "_get_genai_client", return_value=mock_client):
            model = ai_config.get_model(ModelType.GEMINI_25_PRO)
        if os.getenv("USE_MOCK_AI", "false").lower() != "true":
            assert model.model_name == ModelType.GEMINI_25_PRO.value

    def test_model_selection_prefer_speed(self, ai_config):
        """Test model selection when preferring speed."""
        model_type = ai_config.get_optimal_model(task_complexity="medium", prefer_speed=True)
        metadata = ai_config.get_model_metadata(model_type)
        assert metadata.speed_score >= 6.0

    def test_model_selection_prefer_capability(self, ai_config):
        """Test model selection when preferring capability."""
        model_type = ai_config.get_optimal_model(task_complexity="complex", prefer_speed=False)
        metadata = ai_config.get_model_metadata(model_type)
        assert metadata.capability_score >= 8.0


class TestGetAIModel:
    """Test suite for get_ai_model function."""

    @patch("config.ai_config.ai_config")
    def test_get_ai_model_default(self, mock_ai_config):
        """Test get_ai_model with default parameters."""
        mock_model = Mock()
        mock_ai_config.get_optimal_model.return_value = ModelType.GEMINI_25_FLASH
        mock_ai_config.get_model.return_value = mock_model
        result = get_ai_model()
        assert result == mock_model
        mock_ai_config.get_optimal_model.assert_called_once()
        mock_ai_config.get_model.assert_called_once()

    @patch("config.ai_config.ai_config")
    def test_get_ai_model_specific_type(self, mock_ai_config):
        """Test get_ai_model with specific model type."""
        mock_model = Mock()
        mock_ai_config.get_model.return_value = mock_model
        result = get_ai_model(model_type=ModelType.GEMINI_25_PRO)
        assert result == mock_model
        mock_ai_config.get_model.assert_called_once_with(
            ModelType.GEMINI_25_PRO, system_instruction=None, tools=None
        )
        mock_ai_config.get_optimal_model.assert_not_called()

    @patch("config.ai_config.ai_config")
    def test_get_ai_model_with_task_context(self, mock_ai_config):
        """Test get_ai_model with task context."""
        mock_model = Mock()
        mock_ai_config.get_optimal_model.return_value = ModelType.GEMINI_25_FLASH
        mock_ai_config.get_model.return_value = mock_model
        task_context = {"task_type": "analysis", "framework": "gdpr"}
        result = get_ai_model(
            task_complexity="complex", prefer_speed=False, task_context=task_context
        )
        assert result == mock_model
        mock_ai_config.get_optimal_model.assert_called_once_with("complex", False, task_context)

    @patch("config.ai_config.ai_config")
    def test_get_ai_model_fallback_on_error(self, mock_ai_config):
        """Test get_ai_model fallback behavior on error."""
        mock_model = Mock()
        mock_ai_config.get_optimal_model.side_effect = Exception("Selection failed")
        mock_ai_config.get_model.return_value = mock_model
        mock_ai_config.default_model_type = ModelType.GEMINI_25_FLASH
        result = get_ai_model()
        assert result == mock_model
        mock_ai_config.get_model.assert_called_with(
            ModelType.GEMINI_25_FLASH, system_instruction=None, tools=None
        )


class TestModelMetadataIntegration:
    """Integration tests for model metadata and selection."""

    def test_all_models_have_metadata(self):
        """Test that all model types have corresponding metadata."""
        for model_type in ModelType:
            assert model_type in MODEL_METADATA, f"Missing metadata for {model_type}"
            metadata = MODEL_METADATA[model_type]
            assert isinstance(metadata, ModelMetadata)
            assert metadata.name == model_type.value

    def test_metadata_consistency(self):
        """Test metadata values are consistent and reasonable."""
        for model_type, metadata in MODEL_METADATA.items():
            assert metadata.cost_score > 0, f"Invalid cost score for {model_type}"
            assert metadata.speed_score > 0, f"Invalid speed score for {model_type}"
            assert metadata.capability_score > 0, f"Invalid capability score for {model_type}"
            assert 1 <= metadata.cost_score <= 10, f"Cost score out of range for {model_type}"
            assert 1 <= metadata.speed_score <= 10, f"Speed score out of range for {model_type}"
            assert 1 <= metadata.capability_score <= 10, (
                f"Capability score out of range for {model_type}"
            )
            assert metadata.max_tokens > 0, f"Invalid max_tokens for {model_type}"
            assert metadata.timeout_seconds > 0, f"Invalid timeout for {model_type}"

    def test_fallback_chain_metadata_ordering(self):
        """Test that fallback chain respects capability ordering."""
        capabilities = []
        for model_type in MODEL_FALLBACK_CHAIN:
            metadata = MODEL_METADATA[model_type]
            capabilities.append(metadata.capability_score)
        assert capabilities[0] >= capabilities[-1], (
            "Fallback chain should start with most capable model"
        )
