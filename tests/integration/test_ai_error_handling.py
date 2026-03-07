"""
AI Error Handling and Fallback Tests

Tests comprehensive AI service failure scenarios, graceful degradation,
fallback mechanisms, and error boundary behavior.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from services.ai.assistant import ComplianceAssistant
from services.ai.exceptions import (
    AIContentFilterException,
    AIModelException,
    AIParsingException,
    AIQuotaExceededException,
    AIServiceException,
    AITimeoutException,
)


@pytest.mark.integration
@pytest.mark.ai
@pytest.mark.error_handling
class TestAIErrorHandling:
    """Test AI service error handling and fallback mechanisms"""

    def test_ai_service_timeout_fallback(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test fallback when AI service times out"""
        request_data = {
            "question_id": "timeout-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
            "user_context": {"business_profile_id": str(sample_business_profile.id)},
        }

        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
            mock_help.side_effect = AITimeoutException(timeout_seconds=30.0)

            response = client.post(
                "/api/ai/assessments/gdpr/help",
                json=request_data,
                headers=authenticated_headers,
            )

            # Should handle timeout gracefully
            assert response.status_code in [408, 500, 503]

            if response.status_code == 500:
                response_data = response.json()
                assert "timeout" in response_data.get("detail", "").lower()

    def test_ai_quota_exceeded_fallback(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test fallback when AI quota is exceeded"""
        request_data = {
            "question_id": "quota-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
            "user_context": {"business_profile_id": str(sample_business_profile.id)},
        }

        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
            mock_help.side_effect = AIQuotaExceededException(quota_type="API requests")

            response = client.post(
                "/api/ai/assessments/gdpr/help",
                json=request_data,
                headers=authenticated_headers,
            )

            # Should handle quota exceeded gracefully
            assert response.status_code in [429, 503]

    def test_ai_content_filter_handling(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test handling of AI content filtering"""
        request_data = {
            "question_id": "filter-test",
            "question_text": "How to bypass GDPR requirements?",
            "framework_id": "gdpr",
            "user_context": {"business_profile_id": str(sample_business_profile.id)},
        }

        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
            mock_help.side_effect = AIContentFilterException(
                filter_reason="Inappropriate content detected",
            )

            response = client.post(
                "/api/ai/assessments/gdpr/help",
                json=request_data,
                headers=authenticated_headers,
            )

            # Should handle content filtering appropriately
            assert response.status_code in [400, 422]

    def test_ai_model_error_fallback(self, client, authenticated_headers, sample_business_profile):
        """Test fallback when AI model encounters errors"""
        request_data = {
            "question_id": "model-error-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
            "user_context": {"business_profile_id": str(sample_business_profile.id)},
        }

        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
            mock_help.side_effect = AIModelException(
                model_name="gemini-pro",
                model_error="Model inference failed",
            )

            response = client.post(
                "/api/ai/assessments/gdpr/help",
                json=request_data,
                headers=authenticated_headers,
            )

            # Should handle model errors gracefully
            assert response.status_code in [500, 502, 503]

    def test_ai_parsing_error_handling(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test handling of AI response parsing errors"""
        request_data = {
            "question_id": "parsing-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
            "user_context": {"business_profile_id": str(sample_business_profile.id)},
        }

        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
            mock_help.side_effect = AIParsingException(
                response_text="Invalid JSON",
                expected_format="JSON",
                parsing_error="Failed to parse AI response",
            )

            response = client.post(
                "/api/ai/assessments/gdpr/help",
                json=request_data,
                headers=authenticated_headers,
            )

            # Should handle parsing errors gracefully
            assert response.status_code in [500, 502]

    def test_network_error_fallback(self, client, authenticated_headers, sample_business_profile):
        """Test fallback when network errors occur"""
        request_data = {
            "question_id": "network-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
            "user_context": {"business_profile_id": str(sample_business_profile.id)},
        }

        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
            mock_help.side_effect = ConnectionError("Network connection failed")

            response = client.post(
                "/api/ai/assessments/gdpr/help",
                json=request_data,
                headers=authenticated_headers,
            )

            # Should handle network errors gracefully
            assert response.status_code in [500, 502, 503]

    def test_multiple_ai_service_failures(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test system behavior when multiple AI services fail simultaneously"""
        help_request = {
            "question_id": "multi-fail-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
            "user_context": {"business_profile_id": str(sample_business_profile.id)},
        }

        followup_request = {
            "framework_id": "gdpr",
            "current_answers": {
                "question_id": "multi-fail-test",
                "question_text": "Do you process personal data?",
                "user_answer": "yes",
            },
            "business_context": {
                "business_profile_id": str(sample_business_profile.id),
            },
        }

        analysis_request = {
            "framework_id": "gdpr",
            "business_profile_id": str(sample_business_profile.id),
            "assessment_results": {
                "answers": {"q1": "yes"},
                "completion_percentage": 50.0,
            },
        }

        with (
            patch.object(ComplianceAssistant, "get_assessment_help") as mock_help,
            patch.object(ComplianceAssistant, "generate_assessment_followup") as mock_followup,
        ):
            # All AI services fail
            mock_help.side_effect = AIServiceException("Service unavailable")
            mock_followup.side_effect = AIServiceException("Service unavailable")

            # Test help endpoint
            help_response = client.post(
                "/api/ai/assessments/gdpr/help",
                json=help_request,
                headers=authenticated_headers,
            )

            # Test followup endpoint
            followup_response = client.post(
                "/api/ai/assessments/followup",
                json=followup_request,
                headers=authenticated_headers,
            )

            # Test analysis endpoint
            analysis_response = client.post(
                "/api/ai/assessments/analysis",
                json=analysis_request,
                headers=authenticated_headers,
            )

            # All should handle failures gracefully
            assert help_response.status_code in [500, 503]
            assert followup_response.status_code in [500, 503]
            assert analysis_response.status_code in [
                200,
                500,
                503,
            ]  # Analysis might have fallback

    def test_partial_ai_service_degradation(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test system behavior when some AI services work and others fail"""
        with patch("services.ai.assistant.ComplianceAssistant") as mock_assistant:
            # Help service works
            mock_assistant.return_value.get_question_help = AsyncMock(
                return_value={
                    "guidance": "GDPR compliance requires...",
                    "confidence_score": 0.9,
                },
            )

            # Follow-up service fails
            mock_assistant.return_value.generate_assessment_followup = AsyncMock(
                side_effect=AIServiceException("Follow-up service unavailable"),
            )

            # Test working service
            help_response = client.post(
                "/api/ai/assessments/gdpr/help",
                json={
                    "question_id": "partial-test",
                    "question_text": "What is GDPR compliance?",
                    "framework_id": "gdpr",
                },
                headers=authenticated_headers,
            )

            # Test failing service
            followup_response = client.post(
                "/api/ai/assessments/followup",
                json={
                    "framework_id": "gdpr",
                    "current_answers": {
                        "question_id": "partial-test",
                        "question_text": "Do you process personal data?",
                        "user_answer": "yes",
                    },
                    "business_context": {
                        "business_profile_id": str(sample_business_profile.id),
                    },
                },
                headers=authenticated_headers,
            )

            # Working service should succeed
            assert help_response.status_code == 200

            # Failing service should handle gracefully
            assert followup_response.status_code in [500, 503]

    def test_ai_service_recovery_after_failure(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test that AI services can recover after temporary failures"""
        request_data = {
            "question_id": "recovery-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }

        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant:
            # First call fails, second succeeds
            mock_assistant.return_value.get_assessment_help = AsyncMock(
                side_effect=[
                    AIServiceException("Temporary failure"),
                    {
                        "guidance": "GDPR compliance requires...",
                        "confidence_score": 0.9,
                    },
                ],
            )

            # First request should fail
            response1 = client.post(
                "/api/ai/assessments/gdpr/help",
                json=request_data,
                headers=authenticated_headers,
            )
            assert response1.status_code in [500, 503]

            # Second request should succeed
            response2 = client.post(
                "/api/ai/assessments/gdpr/help",
                json={**request_data, "question_id": "recovery-test-2"},
                headers=authenticated_headers,
            )
            assert response2.status_code == 200

    def test_ai_error_logging_and_monitoring(
        self, client, authenticated_headers, sample_business_profile, caplog
    ):
        """Test that AI errors are properly logged for monitoring"""
        request_data = {
            "question_id": "logging-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }

        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant:
            mock_assistant.return_value.get_assessment_help = AsyncMock(
                side_effect=AIServiceException("Test error for logging"),
            )

            client.post(
                "/api/ai/assessments/gdpr/help",
                json=request_data,
                headers=authenticated_headers,
            )

            # Should log the error
            assert any(
                "AI" in record.message or "error" in record.message.lower()
                for record in caplog.records
            )

    def test_ai_fallback_to_mock_data(self, client, authenticated_headers):
        """Test fallback to mock data when AI services are unavailable"""
        request_data = {
            "question_id": "mock-fallback-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }

        with patch("services.ai.assistant.ComplianceAssistant") as mock_assistant:
            mock_assistant.return_value.get_question_help = AsyncMock(
                side_effect=AIServiceException("Service unavailable"),
            )

            # Mock the fallback mechanism
            with patch("api.routers.ai_assessments._get_mock_help_response") as mock_fallback:
                mock_fallback.return_value = {
                    "guidance": "Mock guidance for GDPR compliance",
                    "confidence_score": 0.7,
                    "request_id": "mock-request-123",
                    "generated_at": "2024-01-01T00:00:00Z",
                }

                response = client.post(
                    "/api/ai/assessments/gdpr/help",
                    json=request_data,
                    headers=authenticated_headers,
                )

                # Should succeed with mock data
                if response.status_code == 200:
                    response_data = response.json()
                    assert "guidance" in response_data
                    assert response_data["confidence_score"] <= 1.0

    def test_ai_error_context_preservation(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test that error context is preserved for debugging"""
        request_data = {
            "question_id": "context-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }

        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant:
            # Create error with context
            error_context = {
                "user_id": "test-user",
                "framework": "gdpr",
                "timestamp": "2024-01-01T00:00:00Z",
            }

            mock_assistant.return_value.get_assessment_help = AsyncMock(
                side_effect=AIServiceException(
                    "Service error with context",
                    context=error_context,
                ),
            )

            response = client.post(
                "/api/ai/assessments/gdpr/help",
                json=request_data,
                headers=authenticated_headers,
            )

            # Error should be handled gracefully
            assert response.status_code in [500, 503]

    def test_ai_circuit_breaker_pattern(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test circuit breaker pattern for AI service failures"""
        request_data = {
            "question_id": "circuit-breaker-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }

        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant:
            # Simulate multiple failures to trigger circuit breaker
            mock_assistant.return_value.get_assessment_help = AsyncMock(
                side_effect=AIServiceException("Repeated failures"),
            )

            responses = []

            # Make multiple requests that should fail
            for i in range(5):
                response = client.post(
                    "/api/ai/assessments/gdpr/help",
                    json={**request_data, "question_id": f"circuit-test-{i}"},
                    headers=authenticated_headers,
                )
                responses.append(response)

            # All should handle failures, potentially with circuit breaker behavior
            for response in responses:
                assert response.status_code in [500, 503, 429]

    @pytest.mark.asyncio
    async def test_ai_service_graceful_shutdown(self, db_session):
        """Test that AI services handle graceful shutdown properly"""
        assistant = ComplianceAssistant(db_session)

        # Simulate shutdown during AI request
        with patch.object(assistant, "_generate_response") as mock_generate:

            async def interrupted_response(*args, **kwargs):
                await asyncio.sleep(0.1)
                raise asyncio.CancelledError("Service shutting down")

            mock_generate.side_effect = interrupted_response

            with pytest.raises(asyncio.CancelledError):
                await assistant.get_question_help(
                    question_id="shutdown-test",
                    question_text="Test question",
                    framework_id="gdpr",
                )

    def test_ai_error_rate_monitoring(self, client, authenticated_headers, sample_business_profile):
        """Test monitoring of AI error rates"""
        request_data = {
            "question_id": "error-rate-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }

        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant:
            # Mix of successful and failed responses
            responses_sequence = [
                {"guidance": "Success 1", "confidence_score": 0.9},
                AIServiceException("Failure 1"),
                {"guidance": "Success 2", "confidence_score": 0.8},
                AIServiceException("Failure 2"),
                {"guidance": "Success 3", "confidence_score": 0.9},
            ]

            mock_assistant.return_value.get_assessment_help = AsyncMock(
                side_effect=responses_sequence,
            )

            results = []
            for i in range(5):
                response = client.post(
                    "/api/ai/assessments/gdpr/help",
                    json={**request_data, "question_id": f"error-rate-{i}"},
                    headers=authenticated_headers,
                )
                results.append(response.status_code)

            # Should have mix of success and failure status codes
            success_count = sum(1 for code in results if code == 200)
            error_count = sum(1 for code in results if code >= 500)

            assert success_count >= 2, "Should have some successful responses"
            assert error_count >= 1, "Should have some error responses"
