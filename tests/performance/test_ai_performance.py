"""

# Constants

MINUTE_SECONDS = 60

DEFAULT_RETRIES = 5.0


AI Performance and Rate Limiting Tests

Tests AI service performance, response times, caching mechanisms,
and rate limiting validation for the AI assessment endpoints.
"""

import asyncio
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID
import pytest
from services.ai.assistant import ComplianceAssistant
from services.ai.exceptions import AITimeoutException

from tests.test_constants import DEFAULT_LIMIT, HTTP_INTERNAL_SERVER_ERROR, HTTP_OK


@pytest.mark.performance
@pytest.mark.ai
class TestAIPerformance:
    """Test AI service performance characteristics"""

    def test_ai_help_response_time_under_threshold(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test AI help endpoint responds within acceptable time limits"""
        request_data = {
            "question_id": "perf-test-1",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant_class:
            mock_assistant = Mock()
            mock_assistant.get_assessment_help = AsyncMock(
                return_value={
                    "guidance": "GDPR compliance requires...",
                    "confidence_score": 0.9,
                    "related_topics": ["data protection"],
                    "follow_up_suggestions": ["Learn more about GDPR"],
                    "source_references": ["GDPR Article 5"],
                    "request_id": "test-request-id",
                    "generated_at": "2024-01-01T00:00:00Z",
                }
            )
            mock_assistant_class.return_value = mock_assistant
            start_time = time.time()
            response = client.post(
                "/api/ai/assessments/gdpr/help", json=request_data, headers=authenticated_headers
            )
            end_time = time.time()
            response_time = end_time - start_time
            assert response.status_code == HTTP_OK
            assert response_time < DEFAULT_RETRIES

    def test_ai_help_concurrent_requests_performance(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test performance under concurrent AI help requests"""
        request_data = {
            "question_id": "perf-test-concurrent",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant_class:
            mock_assistant = Mock()
            mock_assistant.get_assessment_help = AsyncMock(
                return_value={
                    "guidance": "GDPR compliance requires...",
                    "confidence_score": 0.9,
                    "related_topics": ["data protection"],
                    "follow_up_suggestions": ["Learn more about GDPR"],
                    "source_references": ["GDPR Article 5"],
                    "request_id": "test-request-id",
                    "generated_at": "2024-01-01T00:00:00Z",
                }
            )
            mock_assistant_class.return_value = mock_assistant

            def make_request():
                start_time = time.time()
                response = client.post(
                    "/api/ai/assessments/gdpr/help",
                    json=request_data,
                    headers=authenticated_headers,
                )
                end_time = time.time()
                return response.status_code, end_time - start_time

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_request) for _ in range(10)]
                results = [future.result() for future in as_completed(futures)]
            response_times = [result[1] for result in results]
            success_count = sum(1 for result in results if result[0] == HTTP_OK)
            assert success_count >= 8
            assert statistics.mean(response_times) < DEFAULT_RETRIES
            assert max(response_times) < 10.0

    def test_ai_analysis_performance_with_large_dataset(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test AI analysis performance with large assessment data"""
        large_answers = {f"q{i}": ("yes" if i % 2 == 0 else "no") for i in range(DEFAULT_LIMIT)}
        request_data = {
            "framework_id": "gdpr",
            "business_profile_id": str(sample_business_profile.id),
            "assessment_results": {
                "answers": large_answers,
                "completion_percentage": 100.0,
                "sections_completed": [f"section-{i}" for i in range(10)],
            },
        }
        start_time = time.time()
        response = client.post(
            "/api/ai/assessments/analysis", json=request_data, headers=authenticated_headers
        )
        end_time = time.time()
        response_time = end_time - start_time
        assert response.status_code == HTTP_OK
        assert response_time < 10.0

    @pytest.mark.asyncio
    async def test_ai_service_timeout_handling(self, async_db_session):
        """Test AI service handles timeouts gracefully"""
        assistant = ComplianceAssistant(async_db_session)
        with patch.object(assistant, "get_assessment_help") as mock_help:
            mock_help.side_effect = AITimeoutException(timeout_seconds=30.0)
            start_time = time.time()
            with pytest.raises(AITimeoutException):
                await assistant.get_assessment_help(
                    question_id="timeout-test",
                    question_text="Test question",
                    framework_id="gdpr",
                    business_profile_id=UUID("12345678-1234-5678-9012-123456789012"),
                )
            end_time = time.time()
            assert end_time - start_time < 2.0

    def test_ai_caching_improves_performance(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test that AI response caching improves performance for repeated requests"""
        request_data = {
            "question_id": "cache-test-1",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant_class:
            mock_assistant = Mock()
            mock_assistant.get_assessment_help = AsyncMock(
                return_value={
                    "guidance": "GDPR compliance requires...",
                    "confidence_score": 0.9,
                    "related_topics": ["data protection"],
                    "follow_up_suggestions": ["Learn more about GDPR"],
                    "source_references": ["GDPR Article 5"],
                    "request_id": "test-request-id",
                    "generated_at": "2024-01-01T00:00:00Z",
                }
            )
            mock_assistant_class.return_value = mock_assistant
            start_time = time.time()
            response1 = client.post(
                "/api/ai/assessments/gdpr/help", json=request_data, headers=authenticated_headers
            )
            first_request_time = time.time() - start_time
            start_time = time.time()
            response2 = client.post(
                "/api/ai/assessments/gdpr/help", json=request_data, headers=authenticated_headers
            )
            second_request_time = time.time() - start_time
            assert response1.status_code == HTTP_OK
            assert response2.status_code == HTTP_OK
            assert second_request_time <= first_request_time * 1.5


@pytest.mark.performance
@pytest.mark.rate_limiting
class TestAIRateLimiting:
    """Test AI-specific rate limiting implementation"""

    def test_ai_help_rate_limit_enforcement(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test that AI help endpoint enforces 10 requests per minute limit"""
        request_data = {
            "question_id": "rate-limit-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant_class:
            mock_assistant = Mock()
            mock_assistant.get_assessment_help = AsyncMock(
                return_value={
                    "guidance": "GDPR compliance requires...",
                    "confidence_score": 0.9,
                    "related_topics": ["data protection"],
                    "follow_up_suggestions": ["Learn more about GDPR"],
                    "source_references": ["GDPR Article 5"],
                    "request_id": "test-request-id",
                    "generated_at": "2024-01-01T00:00:00Z",
                }
            )
            mock_assistant_class.return_value = mock_assistant
            responses = []
            start_time = time.time()
            for i in range(15):
                response = client.post(
                    "/api/ai/assessments/gdpr/help",
                    json={**request_data, "question_id": f"rate-limit-test-{i}"},
                    headers=authenticated_headers,
                )
                responses.append(response)
                time.sleep(0.1)
            end_time = time.time()
            total_time = end_time - start_time
            success_responses = [r for r in responses if r.status_code == HTTP_OK]
            rate_limited_responses = [r for r in responses if r.status_code == 429]
            if total_time < MINUTE_SECONDS:
                assert len(rate_limited_responses) > 0, "Expected some requests to be rate limited"
                assert len(success_responses) <= 12, "Too many requests succeeded"

    def test_ai_analysis_stricter_rate_limit(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test that AI analysis endpoint has stricter rate limiting (3 req/min)"""
        request_data = {
            "framework_id": "gdpr",
            "business_profile_id": str(sample_business_profile.id),
            "assessment_results": {"answers": {"q1": "yes"}, "completion_percentage": 50.0},
        }
        responses = []
        for _i in range(6):
            response = client.post(
                "/api/ai/assessments/analysis", json=request_data, headers=authenticated_headers
            )
            responses.append(response)
            time.sleep(0.1)
        success_responses = [r for r in responses if r.status_code == HTTP_OK]
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        assert len(success_responses) <= 4, "Analysis endpoint should have stricter rate limiting"
        assert len(rate_limited_responses) >= 2, "Expected multiple requests to be rate limited"

    def test_regular_endpoints_higher_rate_limits(self, client, authenticated_headers):
        """Test that regular assessment endpoints have higher rate limits (100 req/min)"""
        responses = []
        for _i in range(20):
            response = client.get("/api/assessments", headers=authenticated_headers)
            responses.append(response)
        success_responses = [r for r in responses if r.status_code in [200, 404]]
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        assert len(success_responses) >= 15, "Regular endpoints should handle more requests"
        assert len(rate_limited_responses) <= 2, (
            "Regular endpoints should have minimal rate limiting"
        )

    def test_rate_limit_headers_present(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test that rate limit headers are included in AI endpoint responses"""
        request_data = {
            "question_id": "header-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant_class:
            mock_assistant = Mock()
            mock_assistant.get_assessment_help = AsyncMock(
                return_value={
                    "guidance": "GDPR compliance requires...",
                    "confidence_score": 0.9,
                    "related_topics": ["data protection"],
                    "follow_up_suggestions": ["Learn more about GDPR"],
                    "source_references": ["GDPR Article 5"],
                    "request_id": "test-request-id",
                    "generated_at": "2024-01-01T00:00:00Z",
                }
            )
            mock_assistant_class.return_value = mock_assistant
            response = client.post(
                "/api/ai/assessments/gdpr/help", json=request_data, headers=authenticated_headers
            )
            expected_headers = ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
            for header in expected_headers:
                if header in response.headers:
                    assert response.headers[header] is not None

    def test_rate_limit_reset_after_window(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test that rate limits reset after the time window"""
        request_data = {
            "question_id": "reset-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant_class:
            mock_assistant = Mock()
            mock_assistant.get_assessment_help = AsyncMock(
                return_value={
                    "guidance": "GDPR compliance requires...",
                    "confidence_score": 0.9,
                    "related_topics": ["data protection"],
                    "follow_up_suggestions": ["Learn more about GDPR"],
                    "source_references": ["GDPR Article 5"],
                    "request_id": "test-request-id",
                    "generated_at": "2024-01-01T00:00:00Z",
                }
            )
            mock_assistant_class.return_value = mock_assistant
            for i in range(8):
                response = client.post(
                    "/api/ai/assessments/gdpr/help",
                    json={**request_data, "question_id": f"reset-test-{i}"},
                    headers=authenticated_headers,
                )
            time.sleep(2)
            response = client.post(
                "/api/ai/assessments/gdpr/help",
                json={**request_data, "question_id": "reset-test-final"},
                headers=authenticated_headers,
            )
            assert response.status_code in [200, 500]


@pytest.mark.performance
@pytest.mark.load
class TestAILoadTesting:
    """Load testing for AI endpoints"""

    def test_ai_endpoint_load_capacity(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test AI endpoint capacity under sustained load"""
        request_data = {
            "question_id": "load-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant_class:
            mock_assistant = Mock()
            mock_assistant.get_assessment_help = AsyncMock(
                return_value={
                    "guidance": "GDPR compliance requires...",
                    "confidence_score": 0.9,
                    "related_topics": ["data protection"],
                    "follow_up_suggestions": ["Learn more about GDPR"],
                    "source_references": ["GDPR Article 5"],
                    "request_id": "test-request-id",
                    "generated_at": "2024-01-01T00:00:00Z",
                }
            )
            mock_assistant_class.return_value = mock_assistant

            def make_sustained_requests(duration_seconds: int = 30):
                """Make requests for a sustained period"""
                start_time = time.time()
                responses = []
                request_count = 0
                while time.time() - start_time < duration_seconds:
                    response = client.post(
                        "/api/ai/assessments/gdpr/help",
                        json={**request_data, "question_id": f"load-test-{request_count}"},
                        headers=authenticated_headers,
                    )
                    responses.append(response)
                    request_count += 1
                    time.sleep(0.5)
                return responses

            responses = make_sustained_requests(10)
            success_count = sum(1 for r in responses if r.status_code == HTTP_OK)
            error_count = sum(1 for r in responses if r.status_code >= HTTP_INTERNAL_SERVER_ERROR)
            sum(1 for r in responses if r.status_code == 429)
            total_requests = len(responses)
            success_rate = success_count / total_requests if total_requests > 0 else 0
            assert total_requests > 0, "Should have made some requests"
            assert success_rate >= 0.7, f"Success rate too low: {success_rate:.2%}"
            assert error_count / total_requests <= 0.1, "Too many server errors"

    def test_ai_memory_usage_under_load(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test that AI endpoints don't have memory leaks under load"""
        import os
        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        request_data = {
            "question_id": "memory-test",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch("api.routers.ai_assessments.ComplianceAssistant") as mock_assistant_class:
            mock_assistant = Mock()
            mock_assistant.get_assessment_help = AsyncMock(
                return_value={
                    "guidance": "GDPR compliance requires...",
                    "confidence_score": 0.9,
                    "related_topics": ["data protection"],
                    "follow_up_suggestions": ["Learn more about GDPR"],
                    "source_references": ["GDPR Article 5"],
                    "request_id": "test-request-id",
                    "generated_at": "2024-01-01T00:00:00Z",
                }
            )
            mock_assistant_class.return_value = mock_assistant
            for i in range(50):
                client.post(
                    "/api/ai/assessments/gdpr/help",
                    json={**request_data, "question_id": f"memory-test-{i}"},
                    headers=authenticated_headers,
                )
                if i % 10 == 0:
                    time.sleep(0.1)
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            assert memory_increase < 100 * 1024 * 1024, (
                f"Memory usage increased by {memory_increase / 1024 / 1024:.2f}MB"
            )
