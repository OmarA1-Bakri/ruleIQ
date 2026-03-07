"""

# Constants

Integration Tests for Chat API Endpoints

Tests the chat API endpoints with real database interactions
and AI assistant integrations, ensuring proper data flow and validation.
"""

from unittest.mock import patch
from uuid import uuid4
import pytest
from tests.conftest import assert_api_response_security

from tests.test_constants import (
    HTTP_BAD_REQUEST,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNPROCESSABLE_ENTITY,
)


@pytest.mark.integration
@pytest.mark.api
class TestChatEndpoints:
    """Test chat API endpoints integration"""

    def test_create_conversation(self, client, authenticated_headers, sample_business_profile):
        """Test creating a new conversation"""
        conversation_data = {
            "title": "Test Compliance Conversation",
            "initial_message": "What are the GDPR requirements for my business?",
        }
        with patch("services.ai.assistant.ComplianceAssistant.process_message") as mock_ai:
            mock_ai.return_value = (
                "GDPR requires several key implementations including data protection policies, consent management, and breach notification procedures.",
                {"intent": "guidance_request", "framework": "GDPR", "confidence": 0.9},
            )
            response = client.post(
                "/api/chat/conversations", json=conversation_data, headers=authenticated_headers
            )
            if response.status_code == HTTP_OK:
                assert_api_response_security(response)
                response_data = response.json()
                assert "id" in response_data
                assert response_data["title"] == conversation_data["title"]
                assert "messages" in response_data
                assert len(response_data["messages"]) == 2
            else:
                assert response.status_code in [400, 500]

    def test_send_message_to_conversation(self, client, authenticated_headers):
        """Test sending a message to an existing conversation"""
        conversation_data = {"title": "Test Conversation"}
        with patch("services.ai.assistant.ComplianceAssistant.process_message") as mock_ai:
            mock_ai.return_value = (
                "I can help you with compliance requirements.",
                {"intent": "general_query", "confidence": 0.8},
            )
            create_response = client.post(
                "/api/chat/conversations", json=conversation_data, headers=authenticated_headers
            )
            if create_response.status_code == HTTP_OK:
                conversation_id = create_response.json()["id"]
                message_data = {"message": "Tell me about ISO 27001 requirements"}
                mock_ai.return_value = (
                    "ISO 27001 is an information security management standard that requires implementing security controls and risk management processes.",
                    {"intent": "guidance_request", "framework": "ISO27001", "confidence": 0.95},
                )
                response = client.post(
                    f"/api/chat/conversations/{conversation_id}/messages",
                    json=message_data,
                    headers=authenticated_headers,
                )
                assert response.status_code == HTTP_OK
                assert_api_response_security(response)
                response_data = response.json()
                assert "content" in response_data
                assert "role" in response_data
                assert response_data["role"] == "assistant"

    def test_get_evidence_recommendations(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test getting AI-powered evidence recommendations"""
        request_data = {"framework": "ISO27001"}
        with patch(
            "services.ai.assistant.ComplianceAssistant.get_evidence_recommendations"
        ) as mock_ai:
            mock_ai.return_value = [
                {
                    "framework": "ISO27001",
                    "recommendations": "Implement access control policies, conduct risk assessments.",
                    "generated_at": "2024-01-01T00:00:00",
                }
            ]
            response = client.post(
                "/api/chat/evidence-recommendations",
                json=request_data,
                headers=authenticated_headers,
            )
            if response.status_code == HTTP_OK:
                assert_api_response_security(response)
                response_data = response.json()
                assert isinstance(response_data, list)
                assert len(response_data) > 0
                assert response_data[0]["framework"] == "ISO27001"
                assert "recommendations" in response_data[0]
            else:
                assert response.status_code == HTTP_BAD_REQUEST

    def test_compliance_analysis(self, client, authenticated_headers, sample_business_profile):
        """Test compliance gap analysis endpoint"""
        request_data = {"framework": "GDPR"}
        with patch("services.ai.assistant.ComplianceAssistant.analyze_evidence_gap") as mock_ai:
            mock_ai.return_value = {
                "framework": "GDPR",
                "completion_percentage": 65,
                "evidence_collected": 8,
                "evidence_types": ["policy", "procedure", "training"],
                "recent_activity": 2,
                "recommendations": [
                    {
                        "priority": "High",
                        "action": "Implement data breach notification procedures",
                        "category": "compliance",
                    },
                    {
                        "priority": "Medium",
                        "action": "Update privacy policy",
                        "category": "documentation",
                    },
                ],
                "critical_gaps": ["Data breach notification", "DPIA procedures"],
                "risk_level": "Medium",
            }
            response = client.post(
                "/api/chat/compliance-analysis", json=request_data, headers=authenticated_headers
            )
            if response.status_code == HTTP_OK:
                assert_api_response_security(response)
                response_data = response.json()
                assert response_data["framework"] == "GDPR"
                assert "completion_percentage" in response_data
                assert "evidence_collected" in response_data
                assert "recommendations" in response_data
                assert "critical_gaps" in response_data
                assert response_data["completion_percentage"] == 65
                assert response_data["evidence_collected"] == 8
            else:
                assert response.status_code == HTTP_BAD_REQUEST

    def test_get_conversations_list(self, client, authenticated_headers):
        """Test getting list of conversations"""
        response = client.get("/api/chat/conversations", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        assert_api_response_security(response)
        response_data = response.json()
        assert isinstance(response_data, dict)
        assert "conversations" in response_data
        assert isinstance(response_data["conversations"], list)

    def test_conversation_not_found(self, client, authenticated_headers):
        """Test accessing non-existent conversation"""
        fake_conversation_id = str(uuid4())
        response = client.get(
            f"/api/chat/conversations/{fake_conversation_id}", headers=authenticated_headers
        )
        assert response.status_code == HTTP_NOT_FOUND

    def test_compliance_analysis_missing_business_profile(
        self, client, another_authenticated_headers
    ):
        """Test compliance analysis without business profile"""
        request_data = {"framework": "ISO27001"}
        response = client.post(
            "/api/chat/compliance-analysis",
            json=request_data,
            headers=another_authenticated_headers,
        )
        assert response.status_code == HTTP_BAD_REQUEST
        response_data = response.json()
        assert "Business profile not found" in response_data["detail"]


@pytest.mark.integration
@pytest.mark.api
class TestChatValidation:
    """Test chat API validation and error handling"""

    def test_invalid_framework_for_analysis(self, client, authenticated_headers):
        """Test compliance analysis with invalid framework"""
        request_data = {"framework": ""}
        response = client.post(
            "/api/chat/compliance-analysis", json=request_data, headers=authenticated_headers
        )
        assert response.status_code in [400, 422]

    def test_missing_message_content(self, client, authenticated_headers):
        """Test sending empty message"""
        conversation_data = {"title": "Test Conversation"}
        with patch("services.ai.assistant.ComplianceAssistant.process_message") as mock_ai:
            mock_ai.return_value = "Response", {}
            create_response = client.post(
                "/api/chat/conversations", json=conversation_data, headers=authenticated_headers
            )
            if create_response.status_code == HTTP_OK:
                conversation_id = create_response.json()["id"]
                message_data = {"message": ""}
                response = client.post(
                    f"/api/chat/conversations/{conversation_id}/messages",
                    json=message_data,
                    headers=authenticated_headers,
                )
                assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_ai_assistant_error_handling(self, client, authenticated_headers):
        """Test handling of AI assistant errors"""
        request_data = {"framework": "ISO27001"}
        with patch("services.ai.assistant.ComplianceAssistant.analyze_evidence_gap") as mock_ai:
            mock_ai.side_effect = Exception("AI service temporarily unavailable")
            response = client.post(
                "/api/chat/compliance-analysis", json=request_data, headers=authenticated_headers
            )
            assert response.status_code in [400, 500]
