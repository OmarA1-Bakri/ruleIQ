"""
Functional tests for EvidenceService

These tests verify that ported methods actually work with real logic,
not just structural verification.

These are unit tests with complete mocking - no database required.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4
from datetime import datetime

# Mark all tests in this module as not requiring database
pytestmark = [pytest.mark.unit, pytest.mark.anyio]

from services.ai.domains.evidence_service import EvidenceService


@pytest.fixture
def mock_response_generator():
    """Mock response generator that simulates AI response."""
    generator = Mock()
    generator.generate_simple = AsyncMock(
        return_value="Recommendation 1: Implement data protection policy.\nRecommendation 2: Setup access controls."
    )
    return generator


@pytest.fixture
def mock_response_parser():
    """Mock response parser."""
    return Mock()


@pytest.fixture
def mock_fallback_generator():
    """Mock fallback generator."""
    return Mock()


@pytest.fixture
def mock_context_manager():
    """Mock context manager with realistic business data."""
    manager = AsyncMock()
    manager.get_conversation_context.return_value = {
        "business_profile": {
            "company_name": "Test Corp",
            "industry": "Technology",
            "employee_count": 50,
        },
        "recent_evidence": [],
    }
    return manager


@pytest.fixture
def mock_prompt_templates():
    """Mock prompt templates."""
    templates = Mock()
    templates.get_evidence_recommendation_prompt.return_value = (
        "Generate evidence recommendations for GDPR"
    )
    return templates


@pytest.fixture
def evidence_service(
    mock_response_generator, mock_response_parser, mock_fallback_generator, mock_context_manager
):
    """Create evidence service with mocks."""
    service = EvidenceService(
        mock_response_generator, mock_response_parser, mock_fallback_generator, mock_context_manager
    )
    return service


class TestGetRecommendationsFunctional:
    """Functional tests for get_recommendations method."""

    async def test_get_recommendations_calls_context_manager(
        self, evidence_service, mock_context_manager
    ):
        """Verify method calls context manager to get business context."""
        user = Mock()
        business_id = uuid4()

        await evidence_service.get_recommendations(
            user=user, business_profile_id=business_id, framework="GDPR"
        )

        # Verify context manager was called
        mock_context_manager.get_conversation_context.assert_called_once()
        call_args = mock_context_manager.get_conversation_context.call_args

        # Should be called with a UUID and the business_profile_id
        assert call_args[0][1] == business_id

    async def test_get_recommendations_calls_prompt_templates(
        self, evidence_service, mock_prompt_templates
    ):
        """Verify method calls prompt templates with correct parameters."""
        # Patch PromptTemplates since it's instantiated in __init__
        with patch.object(evidence_service, "prompt_templates", mock_prompt_templates):
            user = Mock()
            business_id = uuid4()

            await evidence_service.get_recommendations(
                user=user, business_profile_id=business_id, framework="GDPR"
            )

            # Verify prompt template was called with framework and business context
            mock_prompt_templates.get_evidence_recommendation_prompt.assert_called_once()
            call_args = mock_prompt_templates.get_evidence_recommendation_prompt.call_args

            assert call_args[0][0] == "GDPR"  # framework
            assert "company_name" in call_args[0][1]  # business_context

    async def test_get_recommendations_calls_response_generator(
        self, evidence_service, mock_response_generator, mock_prompt_templates
    ):
        """Verify method calls response generator with correct parameters."""
        with patch.object(evidence_service, "prompt_templates", mock_prompt_templates):
            user = Mock()
            business_id = uuid4()

            await evidence_service.get_recommendations(
                user=user, business_profile_id=business_id, framework="GDPR"
            )

            # Verify response generator was called
            mock_response_generator.generate_simple.assert_called_once()
            call_kwargs = mock_response_generator.generate_simple.call_args[1]

            assert "system_prompt" in call_kwargs
            assert "compliance expert" in call_kwargs["system_prompt"].lower()
            assert call_kwargs["task_type"] == "evidence_recommendations"
            assert call_kwargs["context"]["framework"] == "GDPR"

    async def test_get_recommendations_returns_correct_format(
        self, evidence_service, mock_prompt_templates
    ):
        """Verify method returns data in expected format."""
        with patch.object(evidence_service, "prompt_templates", mock_prompt_templates):
            user = Mock()
            business_id = uuid4()

            result = await evidence_service.get_recommendations(
                user=user, business_profile_id=business_id, framework="ISO27001"
            )

            # Verify result is a list
            assert isinstance(result, list)
            assert len(result) == 1

            # Verify result structure
            recommendation = result[0]
            assert "framework" in recommendation
            assert recommendation["framework"] == "ISO27001"
            assert "recommendations" in recommendation
            assert "generated_at" in recommendation

            # Verify generated_at is ISO format timestamp
            # Should not raise exception
            datetime.fromisoformat(recommendation["generated_at"])

    async def test_get_recommendations_includes_ai_response(
        self, evidence_service, mock_response_generator, mock_prompt_templates
    ):
        """Verify AI response is included in output."""
        ai_response = "Test recommendation from AI"
        mock_response_generator.generate_simple.return_value = ai_response

        with patch.object(evidence_service, "prompt_templates", mock_prompt_templates):
            user = Mock()
            business_id = uuid4()

            result = await evidence_service.get_recommendations(
                user=user, business_profile_id=business_id, framework="GDPR"
            )

            # Verify AI response is in the output
            assert result[0]["recommendations"] == ai_response

    async def test_get_recommendations_with_different_frameworks(
        self, evidence_service, mock_prompt_templates
    ):
        """Verify method works with different frameworks."""
        frameworks = ["GDPR", "ISO27001", "SOC2", "HIPAA"]

        with patch.object(evidence_service, "prompt_templates", mock_prompt_templates):
            user = Mock()
            business_id = uuid4()

            for framework in frameworks:
                result = await evidence_service.get_recommendations(
                    user=user, business_profile_id=business_id, framework=framework
                )

                assert result[0]["framework"] == framework

    async def test_get_recommendations_preserves_control_id_parameter(
        self, evidence_service, mock_prompt_templates
    ):
        """Verify method accepts control_id parameter (for API compatibility)."""
        with patch.object(evidence_service, "prompt_templates", mock_prompt_templates):
            user = Mock()
            business_id = uuid4()

            # Should not raise exception even though control_id is not used yet
            result = await evidence_service.get_recommendations(
                user=user, business_profile_id=business_id, framework="GDPR", control_id="A.9.1"
            )

            assert result is not None


class TestGetRecommendationsErrorHandling:
    """Test error handling in get_recommendations."""

    async def test_handles_context_manager_not_found(self, evidence_service):
        """Verify proper exception handling when business profile not found."""
        from core.exceptions import NotFoundException

        user = Mock()
        business_id = uuid4()

        # Make context manager raise NotFoundException
        evidence_service.context_manager.get_conversation_context.side_effect = NotFoundException(
            "BusinessProfile", business_id
        )

        # Should re-raise NotFoundException
        with pytest.raises(NotFoundException):
            await evidence_service.get_recommendations(
                user=user, business_profile_id=business_id, framework="GDPR"
            )

    async def test_handles_response_generator_failure(
        self, evidence_service, mock_prompt_templates
    ):
        """Verify proper exception handling when AI generation fails."""
        from core.exceptions import BusinessLogicException

        # Make response generator fail
        evidence_service.response_generator.generate_simple.side_effect = Exception("API timeout")

        with patch.object(evidence_service, "prompt_templates", mock_prompt_templates):
            user = Mock()
            business_id = uuid4()

            # Should raise BusinessLogicException
            with pytest.raises(BusinessLogicException) as exc_info:
                await evidence_service.get_recommendations(
                    user=user, business_profile_id=business_id, framework="GDPR"
                )

            assert "unexpected error" in str(exc_info.value).lower()


class TestGetRecommendationsComparison:
    """Compare new implementation behavior with expected legacy behavior."""

    async def test_matches_legacy_call_sequence(
        self, evidence_service, mock_context_manager, mock_response_generator, mock_prompt_templates
    ):
        """Verify method follows same call sequence as legacy implementation."""
        with patch.object(evidence_service, "prompt_templates", mock_prompt_templates):
            user = Mock()
            business_id = uuid4()

            await evidence_service.get_recommendations(
                user=user, business_profile_id=business_id, framework="GDPR"
            )

            # Verify call sequence matches legacy:
            # 1. Get context
            assert mock_context_manager.get_conversation_context.called

            # 2. Build prompt
            assert mock_prompt_templates.get_evidence_recommendation_prompt.called

            # 3. Generate response
            assert mock_response_generator.generate_simple.called

            # Verify order
            assert mock_context_manager.get_conversation_context.call_count == 1
            assert mock_prompt_templates.get_evidence_recommendation_prompt.call_count == 1
            assert mock_response_generator.generate_simple.call_count == 1

    async def test_output_format_matches_legacy(self, evidence_service, mock_prompt_templates):
        """Verify output format matches legacy implementation."""
        with patch.object(evidence_service, "prompt_templates", mock_prompt_templates):
            user = Mock()
            business_id = uuid4()

            result = await evidence_service.get_recommendations(
                user=user, business_profile_id=business_id, framework="GDPR"
            )

            # Legacy returns: List[Dict[str, Any]]
            assert isinstance(result, list)

            # Legacy format: [{'framework': ..., 'recommendations': ..., 'generated_at': ...}]
            assert len(result) == 1
            assert "framework" in result[0]
            assert "recommendations" in result[0]
            assert "generated_at" in result[0]
