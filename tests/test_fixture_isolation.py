"""

# Constants

Test fixture isolation to debug the test client issue.
"""

import pytest

from tests.test_constants import HTTP_OK, HTTP_UNAUTHORIZED


def test_authenticated_client_works(client, authenticated_headers, sample_business_profile):
    """Test that authenticated client works properly."""
    print(f"Business profile ID: {sample_business_profile.id}")
    print(f"User ID: {sample_business_profile.user_id}")
    request_data = {
        "question_id": "q1",
        "question_text": "What is GDPR compliance?",
        "framework_id": "gdpr",
        "section_id": "data_protection",
        "user_context": {
            "business_profile_id": str(sample_business_profile.id),
            "industry": "technology",
        },
    }
    from unittest.mock import patch
    from services.ai.assistant import ComplianceAssistant

    with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
        mock_help.return_value = {
            "guidance": "GDPR requires organizations to protect personal data...",
            "confidence_score": 0.95,
            "related_topics": ["data protection", "privacy rights"],
            "follow_up_suggestions": ["What are the key GDPR principles?"],
            "source_references": ["GDPR Article 5"],
            "request_id": "test-request-id",
            "generated_at": "2024-01-01T00:00:00Z",
        }
        response = client.post(
            "/api/ai/assessments/gdpr/help", json=request_data, headers=authenticated_headers
        )
        print(f"Response status: {response.status_code}")
        if response.status_code != HTTP_OK:
            print(f"Response body: {response.json()}")
        assert response.status_code == HTTP_OK


def test_unauthenticated_client_fails(unauthenticated_test_client):
    """Test that unauthenticated client fails properly."""
    request_data = {
        "question_id": "q1",
        "question_text": "What is GDPR compliance?",
        "framework_id": "gdpr",
    }
    response = unauthenticated_test_client.post("/api/ai/assessments/gdpr/help", json=request_data)
    print(f"Response status: {response.status_code}")
    assert response.status_code == HTTP_UNAUTHORIZED


def test_authenticated_client_works_again(client, authenticated_headers, sample_business_profile):
    """Test that authenticated client still works after unauthenticated test."""
    print(f"Business profile ID: {sample_business_profile.id}")
    print(f"User ID: {sample_business_profile.user_id}")
    request_data = {
        "question_id": "q1",
        "question_text": "What is compliance?",
        "framework_id": "invalid_framework",
    }
    response = client.post(
        "/api/ai/assessments/invalid_framework/help",
        json=request_data,
        headers=authenticated_headers,
    )
    print(f"Response status: {response.status_code}")
    if response.status_code not in [200, 400, 404]:
        print(f"Response body: {response.json()}")
    assert response.status_code in [200, 400, 404]
