"""
Unit tests for AI Response modules

Tests response generation, parsing, formatting, and fallback handling.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from services.ai.response.generator import ResponseGenerator
from services.ai.response.parser import ResponseParser
from services.ai.response.formatter import ResponseFormatter
from services.ai.response.fallback import FallbackGenerator


class TestResponseFormatter:
    """Test response formatting."""

    def test_format_for_api(self):
        """Test API formatting."""
        response = {"text": "Test response", "confidence": 0.9}
        formatted = ResponseFormatter.format_for_api(response)

        assert formatted == response
        assert formatted["text"] == "Test response"

    def test_format_for_display_with_text(self):
        """Test display formatting with text field."""
        response = {"text": "Display text", "metadata": {}}
        display = ResponseFormatter.format_for_display(response)

        assert display == "Display text"

    def test_format_for_display_with_guidance(self):
        """Test display formatting with guidance field."""
        response = {"guidance": "Guidance text"}
        display = ResponseFormatter.format_for_display(response)

        assert display == "Guidance text"

    def test_format_for_display_fallback(self):
        """Test display formatting fallback to string."""
        response = {"other_field": "value"}
        display = ResponseFormatter.format_for_display(response)

        assert "other_field" in display


class TestFallbackGenerator:
    """Test fallback response generation."""

    def test_get_recommendations_gdpr(self):
        """Test GDPR recommendations."""
        recommendations = FallbackGenerator.get_recommendations("GDPR", {"maturity_level": "Basic"})

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert recommendations[0]["control_id"].startswith("GDPR")

    def test_get_recommendations_iso27001(self):
        """Test ISO 27001 recommendations."""
        recommendations = FallbackGenerator.get_recommendations(
            "ISO27001", {"maturity_level": "Intermediate"}
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert recommendations[0]["control_id"].startswith("ISO")

    def test_get_recommendations_generic(self):
        """Test generic recommendations for unknown framework."""
        recommendations = FallbackGenerator.get_recommendations(
            "CUSTOM_FRAMEWORK", {"maturity_level": "Basic"}
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert recommendations[0]["control_id"] == "GEN-1"

    def test_get_policy(self):
        """Test policy generation."""
        policy = FallbackGenerator.get_policy(
            "GDPR", "Data Protection", {"company_name": "Test Corp"}
        )

        assert policy["title"] == "GDPR Data Protection Policy"
        assert policy["version"] == "1.0"
        assert "sections" in policy
        assert len(policy["sections"]) > 0

    def test_get_workflow(self):
        """Test workflow generation."""
        workflow = FallbackGenerator.get_workflow("ISO27001", "A.9.1")

        assert workflow["framework"] == "ISO27001"
        assert workflow["control_id"] == "A.9.1"
        assert "phases" in workflow
        assert len(workflow["phases"]) > 0
        assert "effort_estimation" in workflow

    def test_get_assessment_help(self):
        """Test assessment help generation."""
        help_response = FallbackGenerator.get_assessment_help("What is GDPR Article 5?", "GDPR")

        assert "guidance" in help_response
        assert help_response["confidence_score"] == 0.5
        assert help_response["is_fallback"] is True
        assert "GDPR" in help_response["guidance"]

    def test_get_fast_fallback_help(self):
        """Test ultra-fast fallback help."""
        help_response = FallbackGenerator.get_fast_fallback_help("Quick question", "GDPR", "Q123")

        assert help_response["is_fallback"] is True
        assert help_response["is_fast_fallback"] is True
        assert help_response["confidence_score"] == 0.3

    def test_get_assessment_followup(self):
        """Test assessment followup generation."""
        followup = FallbackGenerator.get_assessment_followup("ISO27001")

        assert "questions" in followup
        assert len(followup["questions"]) > 0
        assert "question_text" in followup["questions"][0]

    def test_get_assessment_analysis(self):
        """Test assessment analysis fallback."""
        analysis = FallbackGenerator.get_assessment_analysis("GDPR")

        assert "strengths" in analysis
        assert "weaknesses" in analysis
        assert "compliance_score" in analysis
        assert analysis["is_fallback"] is True

    def test_get_assessment_recommendations(self):
        """Test assessment recommendations fallback."""
        recommendations = FallbackGenerator.get_assessment_recommendations("ISO27001")

        assert "recommendations" in recommendations
        assert len(recommendations["recommendations"]) > 0
        assert recommendations["is_fallback"] is True


class TestResponseParser:
    """Test response parsing."""

    def test_parse_json_response(self):
        """Test parsing JSON response."""
        json_text = '{"key": "value", "number": 42}'
        parsed = ResponseParser.parse_json(json_text)

        assert parsed["key"] == "value"
        assert parsed["number"] == 42

    def test_parse_json_with_markdown(self):
        """Test parsing JSON embedded in markdown."""
        markdown_json = '```json\n{"key": "value"}\n```'
        parsed = ResponseParser.parse_json(markdown_json)

        assert parsed["key"] == "value"

    def test_parse_json_invalid(self):
        """Test parsing invalid JSON returns None."""
        invalid_json = "not json at all"
        parsed = ResponseParser.parse_json(invalid_json)

        assert parsed is None

    def test_parse_assessment_help(self):
        """Test parsing assessment help response."""
        help_text = "This is guidance for the question."
        parsed = ResponseParser.parse_assessment_help(help_text)

        assert "guidance" in parsed
        assert parsed["guidance"] == help_text
        assert "confidence_score" in parsed

    def test_parse_recommendations(self):
        """Test parsing recommendations response."""
        recommendations_text = """
        Recommendation 1: Implement access controls
        Priority: High
        Effort: 8 hours

        Recommendation 2: Setup monitoring
        Priority: Medium
        Effort: 4 hours
        """
        parsed = ResponseParser.parse_recommendations(recommendations_text)

        assert isinstance(parsed, list)
        # Parser should extract structured recommendations


@pytest.mark.asyncio
class TestResponseGenerator:
    """Test response generation."""

    @pytest.fixture
    def mock_provider_factory(self):
        """Mock provider factory."""
        factory = Mock()
        model = Mock()
        model.generate_content = AsyncMock(return_value=Mock(text="Test response"))
        factory.get_provider_for_task.return_value = (model, "test_instruction")
        return factory

    @pytest.fixture
    def mock_safety_manager(self):
        """Mock safety manager."""
        manager = Mock()
        manager.should_allow_generation = AsyncMock(return_value=(True, None))
        manager.validate_response = AsyncMock(return_value=(True, None, 0.95))
        return manager

    @pytest.fixture
    def response_generator(self, mock_provider_factory, mock_safety_manager):
        """Create response generator with mocks."""
        return ResponseGenerator(
            mock_provider_factory,
            mock_safety_manager,
            Mock(),  # tool_executor
            None,  # analytics_monitor
        )

    async def test_generate_simple(self, response_generator):
        """Test simple response generation."""
        response = await response_generator.generate_simple(
            system_prompt="You are a test assistant", user_prompt="Test prompt", task_type="help"
        )

        assert response == "Test response"

    async def test_generate_with_context(self, response_generator):
        """Test generation with context."""
        context = {"framework": "GDPR", "user_id": "123"}
        response = await response_generator.generate_simple(
            system_prompt="Test", user_prompt="Test", task_type="help", context=context
        )

        assert isinstance(response, str)

    async def test_safety_check_blocks_generation(self, response_generator, mock_safety_manager):
        """Test generation blocked by safety check."""
        mock_safety_manager.should_allow_generation.return_value = (False, "Content blocked")

        response = await response_generator.generate_simple(
            system_prompt="Test", user_prompt="Unsafe content", task_type="help"
        )

        # Should return empty or error response
        assert response is not None


@pytest.mark.integration
class TestResponseModulesIntegration:
    """Integration tests for response modules."""

    def test_formatter_and_fallback_integration(self):
        """Test formatter works with fallback generator output."""
        fallback = FallbackGenerator.get_assessment_help("Test question", "GDPR")
        formatted = ResponseFormatter.format_for_display(fallback)

        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_parser_and_formatter_integration(self):
        """Test parser and formatter work together."""
        test_response = '{"text": "Test response", "confidence": 0.9}'
        parsed = ResponseParser.parse_json(test_response)
        formatted = ResponseFormatter.format_for_api(parsed)

        assert formatted["text"] == "Test response"
        assert formatted["confidence"] == 0.9
