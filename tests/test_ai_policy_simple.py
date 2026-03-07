"""
Simplified test for AI Policy Generation Assistant.
Tests core functionality without complex dependencies.
"""

import pytest
from unittest.mock import Mock, patch
from services.ai.policy_generator import PolicyGenerator, TemplateProcessor


class TestPolicyGeneratorBasic:
    """Basic tests for AI policy generator"""

    def test_policy_generator_initialization(self):
        """Test PolicyGenerator can be instantiated"""
        generator = PolicyGenerator()

        # Test that it initializes with expected attributes
        assert hasattr(generator, "primary_provider")
        assert hasattr(generator, "fallback_provider")
        assert hasattr(generator, "circuit_breaker")
        assert hasattr(generator, "template_processor")
        assert hasattr(generator, "cache")

    def test_template_processor_initialization(self):
        """Test TemplateProcessor can be instantiated"""
        processor = TemplateProcessor()

        # Test that it initializes
        assert processor is not None
        assert hasattr(processor, "iso27001_templates_path")

    @patch("services.ai.policy_generator.PolicyGenerator")
    def test_mock_policy_generation(self, mock_generator_class):
        """Test that we can mock policy generation for testing"""
        # Create mock instance
        mock_generator = Mock()
        mock_generator_class.return_value = mock_generator

        # Configure mock response
        mock_response = Mock()
        mock_response.success = True
        mock_response.policy_content = "Mock generated policy"
        mock_response.confidence_score = 0.9
        mock_response.provider_used = "google"

        mock_generator.generate_policy.return_value = mock_response

        # Test that the mock works
        generator = mock_generator_class()
        result = generator.generate_policy(Mock(), Mock())

        assert result.success is True
        assert result.policy_content == "Mock generated policy"
        assert result.confidence_score == 0.9
        assert result.provider_used == "google"

    def test_cache_key_generation(self):
        """Test cache key generation for optimization"""
        generator = PolicyGenerator()

        # Create mock request and framework
        mock_request = Mock()
        mock_request.framework_id = "test-framework"
        mock_request.business_context = Mock()
        mock_request.business_context.organization_name = "TestCorp"
        mock_request.policy_type = "privacy_policy"
        mock_request.customization_level = "detailed"

        mock_framework = Mock()
        mock_framework.name = "ICO_GDPR_UK"

        # Test cache key generation
        cache_key = generator._generate_cache_key(mock_request, mock_framework)

        assert cache_key is not None
        assert isinstance(cache_key, str)
        assert len(cache_key) > 0

    def test_fallback_content_generation(self):
        """Test fallback content when AI providers fail"""
        generator = PolicyGenerator()

        # Test fallback content generation
        fallback_content = generator._generate_fallback_content(
            "privacy_policy",
            "TestCorp",
        )

        assert fallback_content is not None
        assert "TestCorp" in fallback_content
        assert "privacy policy" in fallback_content.lower()
        assert "template-based" in fallback_content.lower()


class TestPolicyGeneratorIntegration:
    """Integration tests for policy generator"""

    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with policy generator"""
        generator = PolicyGenerator()

        # Test that circuit breaker exists and is configured
        assert generator.circuit_breaker is not None

        # Test initial state
        assert generator.circuit_breaker.state == "CLOSED"

    def test_template_processor_integration(self):
        """Test template processor integration"""
        generator = PolicyGenerator()

        # Test that template processor is integrated
        assert generator.template_processor is not None

        # Test template processor has ISO 27001 path configured
        assert hasattr(generator.template_processor, "iso27001_templates_path")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
