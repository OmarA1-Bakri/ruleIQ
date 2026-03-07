"""

# Constants
HALF_RATIO = 0.5

Tests for ComplianceAssistant assessment-specific methods (Phase 2.2).

Tests the new assessment integration methods:
- get_assessment_help()
- generate_assessment_followup()
- analyze_assessment_results()
- get_assessment_recommendations()
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
from services.ai.assistant import ComplianceAssistant
from services.ai.context_manager import ContextManager
from services.ai.prompt_templates import PromptTemplates


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_context_manager():
    """Mock context manager."""
    context_manager = AsyncMock(spec=ContextManager)
    context_manager.get_conversation_context.return_value = {
        "business_profile": {
            "name": "Test Company",
            "industry": "Technology",
            "employee_count": 50,
            "frameworks": ["GDPR", "ISO27001"],
        },
        "recent_evidence": [],
        "compliance_status": {"overall_score": 75},
    }
    return context_manager


@pytest.fixture
def mock_prompt_templates():
    """Mock prompt templates."""
    templates = AsyncMock(spec=PromptTemplates)
    templates.get_assessment_help_prompt.return_value = {
        "system": "You are a compliance expert.",
        "user": "Help with this question.",
    }
    templates.get_assessment_followup_prompt.return_value = {
        "system": "Generate follow-up questions.",
        "user": "Based on these answers.",
    }
    templates.get_assessment_analysis_prompt.return_value = {
        "system": "Analyze assessment results.",
        "user": "Analyze these results.",
    }
    templates.get_assessment_recommendations_prompt.return_value = {
        "system": "Generate recommendations.",
        "user": "Provide recommendations.",
    }
    return templates


@pytest.fixture
def compliance_assistant(mock_db, mock_context_manager, mock_prompt_templates):
    """Create ComplianceAssistant instance with mocked dependencies."""
    assistant = ComplianceAssistant(mock_db)
    assistant.context_manager = mock_context_manager
    assistant.prompt_templates = mock_prompt_templates
    return assistant


class TestAssessmentHelp:
    """Test get_assessment_help method."""

    @pytest.mark.asyncio
    async def test_get_assessment_help_success(self, compliance_assistant):
        """Test successful assessment help generation."""
        with patch.object(compliance_assistant, "_generate_ai_response") as mock_ai:
            mock_ai.return_value = ('{"guidance": "Test guidance", "confidence_score": 0.9}',)
            result = await compliance_assistant.get_assessment_help(
                question_id="q1",
                question_text="What is GDPR?",
                framework_id="gdpr",
                business_profile_id=uuid4(),
                section_id="data_protection",
                user_context={"role": "admin"},
            )
            assert result is not None
            assert "guidance" in result
            assert "confidence_score" in result
            assert "request_id" in result
            assert "generated_at" in result
            assert result["framework_id"] == "gdpr"
            assert result["question_id"] == "q1"

    @pytest.mark.asyncio
    async def test_get_assessment_help_with_fallback(self, compliance_assistant):
        """Test assessment help with fallback when AI fails."""
        with patch.object(compliance_assistant, "_generate_ai_response") as mock_ai:
            mock_ai.side_effect = Exception("AI service unavailable")
            result = await compliance_assistant.get_assessment_help(
                question_id="q1",
                question_text="What is GDPR?",
                framework_id="gdpr",
                business_profile_id=uuid4(),
            )
            assert result is not None
            assert "guidance" in result
            assert "confidence_score" in result
            assert result["confidence_score"] == HALF_RATIO


class TestAssessmentFollowup:
    """Test generate_assessment_followup method."""

    @pytest.mark.asyncio
    async def test_generate_assessment_followup_success(self, compliance_assistant):
        """Test successful followup generation."""
        current_answers = {
            "company_size": "50-100",
            "industry": "technology",
            "data_types": ["personal_data", "financial_data"],
        }
        with patch.object(compliance_assistant, "_generate_ai_response") as mock_ai:
            mock_ai.return_value = ('{"follow_up_questions": ["Question 1", "Question 2"]}',)
            result = await compliance_assistant.generate_assessment_followup(
                current_answers=current_answers,
                framework_id="gdpr",
                business_profile_id=uuid4(),
                assessment_context={"progress": 50},
            )
            assert result is not None
            assert "follow_up_questions" in result
            assert "request_id" in result
            assert "framework_id" in result


class TestAssessmentAnalysis:
    """Test analyze_assessment_results method."""

    @pytest.mark.asyncio
    async def test_analyze_assessment_results_success(self, compliance_assistant):
        """Test successful assessment analysis."""
        assessment_results = {
            "gdpr_compliance": "partial",
            "data_protection_measures": "basic",
            "privacy_policies": "missing",
        }
        with patch.object(compliance_assistant, "_generate_ai_response") as mock_ai:
            mock_ai.return_value = '{"gaps": [], "recommendations": []}'
            result = await compliance_assistant.analyze_assessment_results(
                assessment_results=assessment_results,
                framework_id="gdpr",
                business_profile_id=uuid4(),
            )
            assert result is not None
            assert "gaps" in result
            assert "recommendations" in result
            assert "request_id" in result


class TestAssessmentRecommendations:
    """Test get_assessment_recommendations method."""

    @pytest.mark.asyncio
    async def test_get_assessment_recommendations_success(self, compliance_assistant):
        """Test successful recommendations generation."""
        gaps = [{"id": "gap1", "title": "Missing privacy policy", "severity": "high"}]
        business_profile = {"name": "Test Company", "industry": "technology", "employee_count": 50}
        with patch.object(compliance_assistant, "_generate_ai_response") as mock_ai:
            mock_ai.return_value = '{"recommendations": [], "implementation_plan": {}}'
            result = await compliance_assistant.get_assessment_recommendations(
                gaps=gaps,
                business_profile=business_profile,
                framework_id="gdpr",
                existing_policies=["security_policy"],
                industry_context="technology",
                timeline_preferences="standard",
            )
            assert result is not None
            assert "recommendations" in result
            assert "implementation_plan" in result
            assert "request_id" in result


class TestIntentClassification:
    """Test enhanced intent classification for assessments."""

    def test_classify_assessment_intent(self, compliance_assistant):
        """Test classification of assessment-specific intents."""
        result = compliance_assistant._classify_intent(
            "Can you help me with this question?",
            assessment_context={"in_assessment": True, "framework_id": "gdpr"},
        )
        assert result["intent"] == "assessment_help"
        assert result["confidence"] >= 0.9
        assert "assessment_context" in result
        result = compliance_assistant._classify_intent(
            "I don't understand what this is asking, can you clarify?",
            assessment_context={"in_assessment": True},
        )
        assert result["intent"] == "question_clarification"
        result = compliance_assistant._classify_intent(
            "Can you identify gaps in my compliance?", assessment_context={"in_assessment": True}
        )
        assert result["intent"] == "gap_analysis"


class TestEntityExtraction:
    """Test enhanced entity extraction for assessments."""

    def test_extract_assessment_entities(self, compliance_assistant):
        """Test extraction of assessment-specific entities."""
        result = compliance_assistant._extract_entities(
            "This multiple choice question is confusing",
            assessment_context={
                "in_assessment": True,
                "framework_id": "gdpr",
                "section_id": "data_protection",
            },
        )
        assert "assessment_entities" in result
        assert "context_enhanced" in result
        assert result["context_enhanced"] is True
        assert "gdpr" in result["frameworks"]


if __name__ == "__main__":
    pytest.main([__file__])
