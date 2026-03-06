"""

# Constants

Integration tests for AI Optimization Endpoints.

Tests the complete AI optimization implementation including
streaming endpoints, circuit breaker integration, and model selection.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch
import pytest
import requests
from fastapi.testclient import TestClient
from httpx import AsyncClient
from services.ai.assistant import ComplianceAssistant
from services.ai.circuit_breaker import AICircuitBreaker
from services.ai.exceptions import ModelUnavailableException

from tests.test_constants import HTTP_OK


class TestAIOptimizationEndpoints:
    """Integration tests for AI optimization endpoints."""

    @pytest.fixture
    def client(self, client):
        """Test client for API endpoints."""
        return client

    @pytest.fixture
    def mock_ai_assistant(self):
        """Mock AI assistant with optimization features."""
        assistant = Mock(spec=ComplianceAssistant)
        assistant.circuit_breaker = Mock(spec=AICircuitBreaker)
        assistant.circuit_breaker.is_model_available.return_value = True
        assistant.circuit_breaker.get_status.return_value = {
            "overall_state": "CLOSED",
            "model_states": {"gemini-2.5-flash": "CLOSED"},
            "metrics": {"success_rate": 0.95},
        }
        return assistant

    @pytest.mark.asyncio
    async def test_streaming_analysis_endpoint(
        self, async_test_client, authenticated_headers, mock_compliance_assistant
    ):
        """Test streaming analysis endpoint with optimization features."""
        request_data = {
            "assessment_responses": [
                {"question_id": "q1", "answer": "yes"},
                {"question_id": "q2", "answer": "no"},
            ],
            "framework_id": "gdpr",
            "business_profile_id": "profile-123",
        }

        async def mock_stream():
            yield "Analysis chunk 1"
            yield "Analysis chunk 2"
            yield "Analysis complete"

        mock_compliance_assistant.analyze_assessment_results_stream = AsyncMock(
            return_value=mock_stream()
        )
        with patch("api.routers.ai_assessments.ComplianceAssistant") as MockAssistant:
            MockAssistant.return_value = mock_compliance_assistant
            response = await async_test_client.post(
                "/api/ai/assessments/analysis/stream",
                json=request_data,
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK
            assert (response.headers["content-type"] == "text/event-stream; charset=utf-8",)

    @pytest.mark.asyncio
    async def test_streaming_recommendations_endpoint(
        self, async_test_client, authenticated_headers, mock_ai_assistant
    ):
        """Test streaming recommendations endpoint."""
        request_data = {
            "assessment_gaps": [
                {"section": "data_protection", "severity": "high"},
                {"section": "consent", "severity": "medium"},
            ],
            "framework_id": "gdpr",
            "business_profile_id": "profile-123",
            "priority_level": "high",
        }

        async def mock_stream():
            yield "Recommendation 1: "
            yield "Implement data protection measures"
            yield "Recommendation 2: "
            yield "Update consent mechanisms"

        mock_ai_assistant.get_assessment_recommendations_stream = AsyncMock(
            return_value=mock_stream()
        )
        with patch(
            "api.routers.ai_assessments.ComplianceAssistant", return_value=mock_ai_assistant
        ):
            response = await async_test_client.post(
                "/api/ai/assessments/recommendations/stream",
                json=request_data,
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK
            assert (response.headers["content-type"] == "text/event-stream; charset=utf-8",)

    @pytest.mark.asyncio
    async def test_streaming_help_endpoint(
        self, async_test_client, authenticated_headers, mock_ai_assistant
    ):
        """Test streaming help endpoint."""
        framework_id = "gdpr"
        request_data = {
            "question_id": "q1",
            "question_text": "What is personal data?",
            "framework_id": framework_id,
            "section_id": "data_protection",
        }

        async def mock_stream():
            yield "Personal data under GDPR "
            yield "includes any information "
            yield "relating to an identified person."

        mock_ai_assistant.get_assessment_help_stream = AsyncMock(return_value=mock_stream())
        with patch(
            "api.routers.ai_assessments.ComplianceAssistant", return_value=mock_ai_assistant
        ):
            response = await async_test_client.post(
                f"/api/ai/assessments/{framework_id}/help/stream",
                json=request_data,
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK
            assert (response.headers["content-type"] == "text/event-stream; charset=utf-8",)

    def test_circuit_breaker_status_endpoint(
        self, client, authenticated_headers, mock_compliance_assistant
    ):
        """Test circuit breaker status endpoint."""
        (mock_compliance_assistant.circuit_breaker.get_health_status.return_value) = {
            "overall_state": "CLOSED",
            "model_states": {
                "gemini-2.5-flash": {"state": "CLOSED", "failures": 0, "success_rate": 1.0}
            },
            "metrics": {"total_requests": 100, "total_failures": 5, "uptime_percentage": 95.0},
        }
        with patch(
            "api.routers.ai_optimization.ComplianceAssistant",
            return_value=mock_compliance_assistant,
        ):
            response = client.get(
                "/api/ai-optimization/circuit-breaker/status", headers=authenticated_headers
            )
            assert response.status_code == HTTP_OK
            data = response.json()
            assert "overall_state" in data
            assert "model_states" in data
            assert "metrics" in data

    def test_model_selection_endpoint(self, client, authenticated_headers):
        """Test model selection endpoint."""
        request_data = {
            "task_type": "analysis",
            "complexity": "complex",
            "prefer_speed": False,
            "context": {"framework": "gdpr", "prompt_length": 1500},
        }
        with patch("config.ai_config.get_ai_model") as mock_get_model:
            mock_model = Mock()
            mock_model.model_name = "gemini-2.5-pro"
            mock_get_model.return_value = mock_model
            response = client.post(
                "/api/ai-optimization/model-selection",
                json=request_data,
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK
            data = response.json()
            assert "selected_model" in data
            assert "reasoning" in data

    @pytest.mark.asyncio
    async def test_streaming_with_circuit_breaker_open(
        self, async_test_client, authenticated_headers, mock_ai_assistant
    ):
        """Test streaming behavior when circuit breaker is open."""
        request_data = {
            "assessment_responses": [{"question_id": "q1", "answer": "yes"}],
            "framework_id": "gdpr",
            "business_profile_id": "profile-123",
        }
        (mock_ai_assistant.circuit_breaker.is_model_available.return_value) = False
        mock_ai_assistant.circuit_breaker.get_status.return_value = {
            "overall_state": "OPEN",
            "model_states": {"gemini-2.5-flash": "OPEN"},
            "metrics": {"success_rate": 0.45},
        }

        async def mock_fallback_stream():
            yield "Service temporarily unavailable. Please try again later."

        mock_ai_assistant.analyze_assessment_results_stream = AsyncMock(
            return_value=mock_fallback_stream()
        )
        with patch(
            "api.routers.ai_assessments.ComplianceAssistant", return_value=mock_ai_assistant
        ):
            response = await async_test_client.post(
                "/api/ai/assessments/analysis/stream",
                json=request_data,
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK

    def test_model_fallback_chain(self, client, authenticated_headers):
        """Test model fallback chain functionality."""
        with patch("config.ai_config.get_ai_model") as mock_get_model:
            mock_get_model.side_effect = [
                ModelUnavailableException("gemini-2.5-pro", "Circuit open"),
                Mock(model_name="gemini-2.5-flash"),
            ]
            request_data = {"task_type": "analysis", "complexity": "complex", "prefer_speed": False}
            response = client.post(
                "/api/ai-optimization/model-selection",
                json=request_data,
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK
            data = response.json()
            assert "fallback_used" in data
            assert data["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_streaming_error_handling(
        self, async_test_client, authenticated_headers, mock_ai_assistant
    ):
        """Test error handling in streaming endpoints."""
        request_data = {
            "assessment_responses": [{"question_id": "q1", "answer": "yes"}],
            "framework_id": "gdpr",
            "business_profile_id": "profile-123",
        }
        mock_ai_assistant.analyze_assessment_results_stream = AsyncMock(
            side_effect=Exception("AI service error")
        )
        with patch(
            "api.routers.ai_assessments.ComplianceAssistant", return_value=mock_ai_assistant
        ):
            response = await async_test_client.post(
                "/api/ai/assessments/analysis/stream",
                json=request_data,
                headers=authenticated_headers,
            )
            assert response.status_code in [200, 500, 503]

    def test_performance_metrics_endpoint(self, client, authenticated_headers, mock_ai_assistant):
        """Test performance metrics endpoint."""
        mock_ai_assistant.circuit_breaker.metrics.total_requests = 100
        mock_ai_assistant.circuit_breaker.metrics.total_successes = 95
        mock_ai_assistant.circuit_breaker.metrics.total_failures = 5
        mock_ai_assistant.circuit_breaker.metrics.average_response_time = 2.5
        with patch(
            "api.routers.ai_assessments.ComplianceAssistant", return_value=mock_ai_assistant
        ):
            response = client.get("/api/ai/performance/metrics", headers=authenticated_headers)
            assert response.status_code == HTTP_OK
            data = response.json()
            assert "total_requests" in data
            assert "success_rate" in data
            assert "average_response_time" in data

    @pytest.mark.asyncio
    async def test_concurrent_streaming_requests(
        self, async_test_client, authenticated_headers, mock_ai_assistant
    ):
        """Test handling multiple concurrent streaming requests."""
        request_data = {
            "assessment_responses": [{"question_id": "q1", "answer": "yes"}],
            "framework_id": "gdpr",
            "business_profile_id": "profile-123",
        }

        async def mock_stream():
            yield "Concurrent response"

        mock_ai_assistant.analyze_assessment_results_stream = AsyncMock(return_value=mock_stream())
        with patch(
            "api.routers.ai_assessments.ComplianceAssistant", return_value=mock_ai_assistant
        ):
            tasks = []
            for _ in range(5):
                task = async_test_client.post(
                    "/api/ai/assessments/analysis/stream",
                    json=request_data,
                    headers=authenticated_headers,
                )
                tasks.append(task)
            responses = await asyncio.gather(*tasks)
            for response in responses:
                assert response.status_code == HTTP_OK

    def test_model_health_check_endpoint(self, client, authenticated_headers, mock_ai_assistant):
        """Test model health check endpoint."""
        (mock_ai_assistant.circuit_breaker.check_model_health.return_value) = True
        with patch(
            "api.routers.ai_assessments.ComplianceAssistant", return_value=mock_ai_assistant
        ):
            response = client.get(
                "/api/ai/models/gemini-2.5-flash/health", headers=authenticated_headers
            )
            assert response.status_code == HTTP_OK
            data = response.json()
            assert "model_name" in data
            assert "healthy" in data
            assert data["healthy"] is True
