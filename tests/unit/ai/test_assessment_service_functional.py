"""
Functional tests for AssessmentService

These tests verify that ported methods actually work with real logic,
not just structural verification.

These are unit tests with complete mocking - no database required.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

# Mark all tests in this module as not requiring database
pytestmark = [pytest.mark.unit, pytest.mark.anyio]

from services.ai.domains.assessment_service import AssessmentService


@pytest.fixture
def mock_response_generator():
    """Mock response generator that simulates AI response."""
    generator = Mock()
    generator.generate_simple = AsyncMock(
        return_value='{"guidance": "Test guidance", "confidence_score": 0.9}'
    )
    return generator


@pytest.fixture
def mock_context_manager():
    """Mock context manager with realistic business data."""
    manager = AsyncMock()
    manager.get_conversation_context.return_value = {
        "business_profile": {
            "company_name": "Test Corp",
            "industry": "Technology",
            "employee_count": 50,
        }
    }
    return manager


@pytest.fixture
def assessment_service(mock_response_generator, mock_context_manager):
    """Create assessment service with mocks."""
    return AssessmentService(mock_response_generator, mock_context_manager)


class TestGetAssessmentHelp:
    """Functional tests for get_assessment_help method."""

    async def test_get_assessment_help_calls_response_generator(
        self, assessment_service, mock_response_generator
    ):
        """Verify method calls response generator with correct parameters."""
        business_id = uuid4()
        question_id = "q123"
        question_text = "How should we handle GDPR data subjects?"
        framework_id = "GDPR"

        await assessment_service.get_assessment_help(
            question_id=question_id,
            question_text=question_text,
            framework_id=framework_id,
            business_profile_id=business_id,
        )

        # Verify response generator was called
        mock_response_generator.generate_simple.assert_called_once()
        call_kwargs = mock_response_generator.generate_simple.call_args[1]

        assert "system_prompt" in call_kwargs
        assert framework_id in call_kwargs["system_prompt"]
        assert "task_type" in call_kwargs
        assert call_kwargs["task_type"] == "help"

    async def test_get_assessment_help_returns_correct_format(self, assessment_service):
        """Verify method returns data in expected format."""
        business_id = uuid4()

        result = await assessment_service.get_assessment_help(
            question_id="q123",
            question_text="Test question",
            framework_id="GDPR",
            business_profile_id=business_id,
        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "guidance" in result
        assert "confidence_score" in result
        assert "request_id" in result
        assert "generated_at" in result
        assert "framework_id" in result
        assert "question_id" in result
        assert "response_time" in result

    async def test_get_assessment_help_parses_json_response(
        self, assessment_service, mock_response_generator
    ):
        """Verify AI JSON response is parsed correctly."""
        json_response = '{"guidance": "Specific guidance text", "confidence_score": 0.95}'
        mock_response_generator.generate_simple.return_value = json_response

        business_id = uuid4()

        result = await assessment_service.get_assessment_help(
            question_id="q123",
            question_text="Test question",
            framework_id="ISO27001",
            business_profile_id=business_id,
        )

        # Verify parsed values from JSON
        assert result["guidance"] == "Specific guidance text"
        assert result["confidence_score"] == 0.95

    async def test_get_assessment_help_handles_non_json_response(
        self, assessment_service, mock_response_generator
    ):
        """Verify fallback when AI returns non-JSON text."""
        mock_response_generator.generate_simple.return_value = "This is just text, not JSON"

        business_id = uuid4()

        result = await assessment_service.get_assessment_help(
            question_id="q123",
            question_text="Test question",
            framework_id="GDPR",
            business_profile_id=business_id,
        )

        # Should use fallback values
        assert result["guidance"] == "This is just text, not JSON"
        assert result["confidence_score"] == 0.8  # Default from fallback

    async def test_get_assessment_help_timeout_fallback(
        self, assessment_service, mock_response_generator
    ):
        """Verify fast fallback when AI times out."""
        import asyncio

        mock_response_generator.generate_simple.side_effect = asyncio.TimeoutError()

        business_id = uuid4()

        result = await assessment_service.get_assessment_help(
            question_id="q123",
            question_text="Test question",
            framework_id="gdpr",
            business_profile_id=business_id,
        )

        # Should return fast fallback
        assert "guidance" in result
        assert "GDPR" in result["guidance"]
        assert result["confidence_score"] == 0.7
        assert result["response_time"] == 0.1

    async def test_get_assessment_help_framework_specific_fallback(
        self, assessment_service, mock_response_generator
    ):
        """Verify framework-specific fast fallback guidance."""
        import asyncio

        mock_response_generator.generate_simple.side_effect = asyncio.TimeoutError()

        business_id = uuid4()

        # Test GDPR
        result_gdpr = await assessment_service.get_assessment_help(
            question_id="q1",
            question_text="Test",
            framework_id="gdpr",
            business_profile_id=business_id,
        )
        assert "lawful basis" in result_gdpr["guidance"]

        # Test ISO27001
        result_iso = await assessment_service.get_assessment_help(
            question_id="q2",
            question_text="Test",
            framework_id="iso27001",
            business_profile_id=business_id,
        )
        assert "information security" in result_iso["guidance"]


class TestGenerateAssessmentFollowup:
    """Functional tests for generate_assessment_followup method."""

    async def test_generate_followup_calls_context_manager(
        self, assessment_service, mock_context_manager
    ):
        """Verify method calls context manager to get business context."""
        business_id = uuid4()
        current_answers = {"q1": "Yes", "q2": "No"}

        await assessment_service.generate_assessment_followup(
            current_answers=current_answers, framework_id="GDPR", business_profile_id=business_id
        )

        # Verify context manager was called
        mock_context_manager.get_conversation_context.assert_called_once()

    async def test_generate_followup_returns_correct_format(
        self, assessment_service, mock_response_generator
    ):
        """Verify method returns data in expected format."""
        # Return proper JSON for followup
        json_response = (
            '{"follow_up_questions": ["Q1?"], "recommendations": ["R1"], "confidence_score": 0.8}'
        )
        mock_response_generator.generate_simple.return_value = json_response

        business_id = uuid4()

        result = await assessment_service.generate_assessment_followup(
            current_answers={"q1": "Yes"}, framework_id="GDPR", business_profile_id=business_id
        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "follow_up_questions" in result
        assert "recommendations" in result
        assert "confidence_score" in result
        assert "request_id" in result
        assert "generated_at" in result

    async def test_generate_followup_parses_json_response(
        self, assessment_service, mock_response_generator
    ):
        """Verify AI JSON response is parsed correctly."""
        json_response = """
        {
            "follow_up_questions": ["Q1?", "Q2?", "Q3?"],
            "recommendations": ["R1", "R2"],
            "confidence_score": 0.85
        }
        """
        mock_response_generator.generate_simple.return_value = json_response

        business_id = uuid4()

        result = await assessment_service.generate_assessment_followup(
            current_answers={"q1": "Yes"}, framework_id="ISO27001", business_profile_id=business_id
        )

        # Verify parsed values
        assert len(result["follow_up_questions"]) == 3
        assert len(result["recommendations"]) == 2
        assert result["confidence_score"] == 0.85


class TestAnalyzeAssessmentResults:
    """Functional tests for analyze_assessment_results method."""

    async def test_analyze_results_calls_context_manager(
        self, assessment_service, mock_context_manager
    ):
        """Verify method calls context manager to get business context."""
        business_id = uuid4()
        assessment_results = {"responses": {"q1": "Yes", "q2": "No"}}

        await assessment_service.analyze_assessment_results(
            assessment_results=assessment_results,
            framework_id="GDPR",
            business_profile_id=business_id,
        )

        # Verify context manager was called
        mock_context_manager.get_conversation_context.assert_called_once()

    async def test_analyze_results_returns_correct_format(
        self, assessment_service, mock_response_generator
    ):
        """Verify method returns data in expected format."""
        # Return proper JSON for analysis
        json_response = """
        {
            "gaps": [],
            "recommendations": [],
            "risk_assessment": {"level": "low", "description": "OK"},
            "compliance_insights": {"summary": "Good"},
            "evidence_requirements": []
        }
        """
        mock_response_generator.generate_simple.return_value = json_response

        business_id = uuid4()

        result = await assessment_service.analyze_assessment_results(
            assessment_results={"responses": {}},
            framework_id="GDPR",
            business_profile_id=business_id,
        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "gaps" in result
        assert "recommendations" in result
        assert "risk_assessment" in result
        assert "compliance_insights" in result
        assert "evidence_requirements" in result
        assert "request_id" in result
        assert "generated_at" in result

    async def test_analyze_results_parses_json_response(
        self, assessment_service, mock_response_generator
    ):
        """Verify AI JSON response is parsed correctly."""
        json_response = """
        {
            "gaps": [
                {"id": "gap1", "title": "Gap 1", "severity": "high"}
            ],
            "recommendations": [
                {"id": "rec1", "title": "Recommendation 1", "priority": "high"}
            ],
            "risk_assessment": {
                "level": "high",
                "description": "Significant gaps identified"
            },
            "compliance_insights": {
                "summary": "Multiple improvements needed"
            },
            "evidence_requirements": ["policy", "procedure"]
        }
        """
        mock_response_generator.generate_simple.return_value = json_response

        business_id = uuid4()

        result = await assessment_service.analyze_assessment_results(
            assessment_results={"responses": {}},
            framework_id="SOC2",
            business_profile_id=business_id,
        )

        # Verify parsed values
        assert len(result["gaps"]) == 1
        assert result["gaps"][0]["severity"] == "high"
        assert len(result["recommendations"]) == 1
        assert result["risk_assessment"]["level"] == "high"
        assert len(result["evidence_requirements"]) == 2


class TestStreamingMethods:
    """Functional tests for streaming methods."""

    async def test_analyze_results_stream_yields_response(self, assessment_service):
        """Verify streaming analysis yields response."""
        business_id = uuid4()

        chunks = []
        async for chunk in assessment_service.analyze_assessment_results_stream(
            assessment_responses={"q1": "Yes"}, framework_id="GDPR", business_profile_id=business_id
        ):
            chunks.append(chunk)

        # Should have yielded at least one chunk
        assert len(chunks) > 0

    async def test_help_stream_yields_response(self, assessment_service):
        """Verify streaming help yields response."""
        business_id = uuid4()

        chunks = []
        async for chunk in assessment_service.get_assessment_help_stream(
            question_id="q123",
            question_text="Test question",
            framework_id="GDPR",
            business_profile_id=business_id,
        ):
            chunks.append(chunk)

        # Should have yielded at least one chunk
        assert len(chunks) > 0


class TestParsingMethods:
    """Test parsing helper methods."""

    def test_parse_help_response_with_json(self, assessment_service):
        """Verify parsing valid JSON help response."""
        json_response = '{"guidance": "Test", "confidence_score": 0.9}'

        result = assessment_service._parse_assessment_help_response(json_response)

        assert result["guidance"] == "Test"
        assert result["confidence_score"] == 0.9

    def test_parse_help_response_with_text(self, assessment_service):
        """Verify parsing plain text help response."""
        text_response = "This is plain text guidance"

        result = assessment_service._parse_assessment_help_response(text_response)

        assert result["guidance"] == text_response
        assert result["confidence_score"] == 0.8

    def test_parse_followup_response_with_json(self, assessment_service):
        """Verify parsing valid JSON followup response."""
        json_response = """
        {
            "follow_up_questions": ["Q1?", "Q2?"],
            "recommendations": ["R1"],
            "confidence_score": 0.85
        }
        """

        result = assessment_service._parse_assessment_followup_response(json_response)

        assert len(result["follow_up_questions"]) == 2
        assert len(result["recommendations"]) == 1

    def test_parse_analysis_response_with_json(self, assessment_service):
        """Verify parsing valid JSON analysis response."""
        json_response = """
        {
            "gaps": [{"id": "g1"}],
            "recommendations": [{"id": "r1"}],
            "risk_assessment": {"level": "medium"},
            "compliance_insights": {"summary": "OK"},
            "evidence_requirements": ["policy"]
        }
        """

        result = assessment_service._parse_assessment_analysis_response(json_response)

        assert len(result["gaps"]) == 1
        assert len(result["recommendations"]) == 1
        assert result["risk_assessment"]["level"] == "medium"


class TestFallbackMethods:
    """Test fallback helper methods."""

    def test_get_fallback_assessment_help(self, assessment_service):
        """Verify fallback help response structure."""
        result = assessment_service._get_fallback_assessment_help(
            question_text="Test question", framework_id="GDPR"
        )

        assert "guidance" in result
        assert "GDPR" in result["guidance"]
        assert result["confidence_score"] == 0.5
        assert len(result["related_topics"]) > 0

    def test_get_fast_fallback_help_gdpr(self, assessment_service):
        """Verify fast fallback for GDPR."""
        result = assessment_service._get_fast_fallback_help(
            question_text="Test", framework_id="gdpr", question_id="q123"
        )

        assert "lawful basis" in result["guidance"]
        assert result["confidence_score"] == 0.7
        assert result["response_time"] == 0.1

    def test_get_fast_fallback_help_iso27001(self, assessment_service):
        """Verify fast fallback for ISO27001."""
        result = assessment_service._get_fast_fallback_help(
            question_text="Test", framework_id="iso27001", question_id="q123"
        )

        assert "information security" in result["guidance"]

    def test_get_fast_fallback_help_unknown_framework(self, assessment_service):
        """Verify fast fallback for unknown framework."""
        result = assessment_service._get_fast_fallback_help(
            question_text="Test", framework_id="UNKNOWN", question_id="q123"
        )

        assert "UNKNOWN" in result["guidance"]

    def test_get_fallback_followup(self, assessment_service):
        """Verify fallback followup response structure."""
        result = assessment_service._get_fallback_assessment_followup("GDPR")

        assert len(result["follow_up_questions"]) == 3
        assert len(result["recommendations"]) == 3
        assert result["confidence_score"] == 0.5

    def test_get_fallback_analysis(self, assessment_service):
        """Verify fallback analysis response structure."""
        result = assessment_service._get_fallback_assessment_analysis("GDPR")

        assert len(result["gaps"]) == 1
        assert len(result["recommendations"]) == 1
        assert result["risk_assessment"]["level"] == "medium"
        assert "compliance_insights" in result


class TestErrorHandling:
    """Test error handling in assessment methods."""

    async def test_help_handles_generator_failure(
        self, assessment_service, mock_response_generator
    ):
        """Verify proper exception handling when generator fails."""
        # Make response generator fail
        mock_response_generator.generate_simple.side_effect = Exception("API error")

        business_id = uuid4()

        # Should return fallback response
        result = await assessment_service.get_assessment_help(
            question_id="q123",
            question_text="Test",
            framework_id="GDPR",
            business_profile_id=business_id,
        )

        assert "guidance" in result
        assert result["confidence_score"] == 0.5

    async def test_followup_handles_context_failure(self, assessment_service, mock_context_manager):
        """Verify proper exception handling when context manager fails."""
        # Make context manager fail
        mock_context_manager.get_conversation_context.side_effect = Exception("DB error")

        business_id = uuid4()

        # Should return fallback response
        result = await assessment_service.generate_assessment_followup(
            current_answers={"q1": "Yes"}, framework_id="GDPR", business_profile_id=business_id
        )

        assert "follow_up_questions" in result
        assert result["confidence_score"] == 0.5

    async def test_analysis_handles_generator_failure(
        self, assessment_service, mock_response_generator
    ):
        """Verify proper exception handling when analysis fails."""
        # Make response generator fail
        mock_response_generator.generate_simple.side_effect = Exception("Timeout")

        business_id = uuid4()

        # Should return fallback response
        result = await assessment_service.analyze_assessment_results(
            assessment_results={"responses": {}},
            framework_id="GDPR",
            business_profile_id=business_id,
        )

        assert len(result["gaps"]) == 1
        assert result["gaps"][0]["id"] == "general_gap"
