"""

# Constants

Integration tests for AI Assessment endpoints with ComplianceAssistant (Phase 2.2).

Tests the integration between AI endpoints and ComplianceAssistant methods.
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from main import app
from services.ai.assistant import ComplianceAssistant

from tests.test_constants import HTTP_OK


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


class TestAIHelpEndpoint:
    """Test /ai/assessments/{framework_id}/help endpoint integration."""

    def test_ai_help_endpoint_integration(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test AI help endpoint calls ComplianceAssistant correctly."""
        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
            mock_help.return_value = {
                "guidance": "Test guidance",
                "confidence_score": 0.9,
                "related_topics": ["data protection"],
                "follow_up_suggestions": ["Review policies"],
                "source_references": ["GDPR Article 6"],
                "request_id": "test_request_123",
                "generated_at": "2024-01-01T00:00:00Z",
                "framework_id": "gdpr",
                "question_id": "q1",
            }
            response = client.post(
                "/api/ai/assessments/gdpr/help",
                json={
                    "question_id": "q1",
                    "question_text": "What is GDPR?",
                    "framework_id": "gdpr",
                    "section_id": "data_protection",
                    "user_context": {"role": "admin"},
                },
                headers=authenticated_headers,
            )
            mock_help.assert_called_once()
            call_args = mock_help.call_args
            assert call_args[1]["question_id"] == "q1"
            assert call_args[1]["question_text"] == "What is GDPR?"
            assert call_args[1]["framework_id"] == "gdpr"
            assert call_args[1]["section_id"] == "data_protection"
            assert response.status_code == HTTP_OK
            data = response.json()
            assert data["guidance"] == "Test guidance"
            assert data["confidence_score"] == 0.9


class TestAIFollowupEndpoint:
    """Test /ai/assessments/followup endpoint integration."""

    def test_ai_followup_endpoint_integration(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test AI followup endpoint calls ComplianceAssistant correctly."""
        with patch.object(ComplianceAssistant, "generate_assessment_followup") as mock_followup:
            mock_followup.return_value = {
                "questions": [
                    {
                        "id": "q2",
                        "text": "What data do you collect?",
                        "type": "multiple_choice",
                        "options": [
                            {"value": "personal", "label": "Personal data"},
                            {"value": "financial", "label": "Financial data"},
                            {"value": "health", "label": "Health data"},
                        ],
                        "reasoning": "Need to understand data types",
                        "priority": "high",
                    },
                    {
                        "id": "q3",
                        "text": "How do you store personal data?",
                        "type": "text",
                        "reasoning": "Storage methods affect compliance",
                        "priority": "medium",
                    },
                ],
                "request_id": "followup_123",
                "generated_at": "2024-01-01T00:00:00Z",
            }
            response = client.post(
                "/api/ai/assessments/followup",
                json={
                    "framework_id": "gdpr",
                    "current_answers": {"company_size": "50-100", "industry": "technology"},
                    "business_context": {"progress": 50},
                    "max_questions": 3,
                },
                headers=authenticated_headers,
            )
            mock_followup.assert_called_once()
            call_args = mock_followup.call_args
            assert call_args[1]["framework_id"] == "gdpr"
            assert "current_answers" in call_args[1]
            assert response.status_code == HTTP_OK
            data = response.json()
            assert len(data["questions"]) == 2


class TestAIAnalysisEndpoint:
    """Test /ai/assessments/analysis endpoint integration."""

    def test_ai_analysis_endpoint_integration(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test AI analysis endpoint calls ComplianceAssistant correctly."""
        with patch.object(ComplianceAssistant, "analyze_assessment_results") as mock_analysis:
            mock_analysis.return_value = {
                "gaps": [
                    {
                        "id": "gap1",
                        "section": "data_protection",
                        "severity": "high",
                        "description": "No privacy policy found",
                        "impact": "High risk of non-compliance",
                        "current_state": "missing",
                        "target_state": "implemented",
                    }
                ],
                "recommendations": [
                    {
                        "id": "rec1",
                        "title": "Create Privacy Policy",
                        "description": "Develop comprehensive privacy policy",
                        "priority": "high",
                        "effort_estimate": "2-3 weeks",
                        "impact_score": 0.9,
                        "resources": ["Legal team", "Compliance officer"],
                        "implementation_steps": ["Draft policy", "Review", "Approve"],
                    }
                ],
                "risk_assessment": {
                    "level": "medium",
                    "description": "Some compliance gaps identified",
                },
                "compliance_insights": {"summary": "Overall compliance is progressing"},
                "evidence_requirements": [],
                "request_id": "analysis_123",
                "generated_at": "2024-01-01T00:00:00Z",
                "framework_id": "gdpr",
            }
            response = client.post(
                "/api/ai/assessments/analysis",
                json={
                    "framework_id": "gdpr",
                    "assessment_results": {"privacy_policy": "missing", "data_mapping": "partial"},
                    "business_profile_id": str(sample_business_profile.id),
                },
                headers=authenticated_headers,
            )
            mock_analysis.assert_called_once()
            call_args = mock_analysis.call_args
            assert call_args[1]["framework_id"] == "gdpr"
            assert "assessment_results" in call_args[1]
            assert response.status_code == HTTP_OK
            data = response.json()
            assert len(data["gaps"]) == 1
            assert len(data["recommendations"]) == 1


class TestAIRecommendationsEndpoint:
    """Test /ai/assessments/recommendations endpoint integration."""

    def test_ai_recommendations_endpoint_integration(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test AI recommendations endpoint calls ComplianceAssistant correctly."""
        with patch.object(
            ComplianceAssistant, "get_assessment_recommendations"
        ) as mock_recommendations:
            mock_recommendations.return_value = {
                "recommendations": [
                    {
                        "id": "rec1",
                        "title": "Implement Data Mapping",
                        "description": "Create comprehensive data mapping",
                        "priority": "high",
                        "effort_estimate": "4-6 weeks",
                        "impact_score": 0.8,
                        "implementation_steps": [
                            "Identify data sources",
                            "Map data flows",
                            "Document processes",
                        ],
                    }
                ],
                "implementation_plan": {
                    "phases": [
                        {
                            "phase_number": 1,
                            "phase_name": "Assessment",
                            "duration_weeks": 2,
                            "tasks": ["Review current state"],
                            "dependencies": [],
                        }
                    ],
                    "total_timeline_weeks": 12,
                    "resource_requirements": ["Compliance team"],
                },
                "success_metrics": ["Data mapping completed"],
                "request_id": "recommendations_123",
                "generated_at": "2024-01-01T00:00:00Z",
                "framework_id": "general",
            }
            response = client.post(
                "/api/ai/assessments/recommendations",
                json={
                    "gaps": [{"id": "gap1", "title": "Missing data mapping"}],
                    "business_profile": {"name": "Test Company", "industry": "technology"},
                    "existing_policies": ["security_policy"],
                    "industry_context": "technology",
                    "timeline_preferences": "standard",
                },
                headers=authenticated_headers,
            )
            mock_recommendations.assert_called_once()
            call_args = mock_recommendations.call_args
            assert len(call_args[1]["gaps"]) == 1
            assert call_args[1]["business_profile"]["name"] == "Test Company"
            assert response.status_code == HTTP_OK
            data = response.json()
            assert len(data["recommendations"]) == 1
            assert "implementation_plan" in data


if __name__ == "__main__":
    pytest.main([__file__])
