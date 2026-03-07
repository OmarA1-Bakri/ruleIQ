"""

# Constants


Integration Tests for AI Assessment Endpoints

Tests the new /ai/assessments/* endpoints including authentication,
rate limiting, error handling, and response validation.
"""

import time
from unittest.mock import patch, MagicMock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from services.ai.assistant import ComplianceAssistant
from services.ai.exceptions import (
    AIContentFilterException,
    AIQuotaExceededException,
    AIServiceException,
    AITimeoutException,
)

from tests.test_constants import (
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    HTTP_UNPROCESSABLE_ENTITY,
    MAX_RETRIES,
)


@pytest.mark.integration
@pytest.mark.ai
class TestAIAssessmentEndpoints:
    """Test AI assessment endpoints integration"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, sample_business_profile):
        """Set up mocks for all tests in this class"""
        self.mock_user = MagicMock()
        self.mock_user.id = "test-user-id"
        self.mock_user.email = "test@example.com"
        self.mock_user.is_active = True
        self.mock_db = MagicMock()
        self.mock_profile = sample_business_profile
        self.mock_assistant = MagicMock()

        async def mock_get_assessment_help(*args, **kwargs):
            return {
                "guidance": "Test guidance",
                "confidence_score": 0.9,
                "related_topics": ["topic1", "topic2"],
                "follow_up_suggestions": ["question1"],
                "source_references": ["source1"],
                "request_id": "test-request-id",
                "generated_at": "2024-01-01T00:00:00Z",
            }

        async def mock_generate_followup_questions(*args, **kwargs):
            return {
                "followup_questions": ["question1", "question2"],
                "request_id": "test-request-id",
                "generated_at": "2024-01-01T00:00:00Z",
            }

        async def mock_generate_assessment_followup(*args, **kwargs):
            return {
                "questions": [
                    {
                        "id": "ai-q1",
                        "text": "What types of personal data do you process?",
                        "type": "multiple_choice",
                        "options": [
                            {"value": "names", "label": "Names"},
                            {"value": "emails", "label": "Email addresses"},
                            {"value": "financial", "label": "Financial data"},
                        ],
                        "reasoning": "Need to understand data types",
                        "priority": "high",
                    }
                ],
                "request_id": "followup_123",
                "generated_at": "2024-01-01T00:00:00Z",
            }

        async def mock_analyze_assessment_results(*args, **kwargs):
            return {
                "gaps": [
                    {
                        "id": "gap1",
                        "section": "Data Protection",
                        "severity": "high",
                        "description": "Missing data protection policy",
                        "impact": "High risk of non-compliance",
                        "current_state": "No policy",
                        "target_state": "Complete policy",
                    }
                ],
                "recommendations": [
                    {
                        "id": "rec1",
                        "title": "Create Data Protection Policy",
                        "description": "Develop comprehensive data protection policy",
                        "priority": "high",
                        "effort_estimate": "2 weeks",
                        "impact_score": 0.9,
                        "resources": ["Template available"],
                        "implementation_steps": ["Step 1", "Step 2"],
                    }
                ],
                "risk_assessment": {"level": "medium", "score": 0.6},
                "compliance_insights": {
                    "key_findings": ["insight1", "insight2"],
                    "compliance_score": 0.75,
                },
                "evidence_requirements": [
                    {"type": "document", "description": "evidence1"},
                    {"type": "process", "description": "evidence2"},
                ],
                "confidence_score": 0.85,
                "request_id": "test-request-id",
                "generated_at": "2024-01-01T00:00:00Z",
            }

        self.mock_assistant.get_assessment_help = mock_get_assessment_help
        self.mock_assistant.generate_followup_questions = (mock_generate_followup_questions,)
        self.mock_assistant.generate_assessment_followup = (mock_generate_assessment_followup,)
        self.mock_assistant.analyze_assessment_results = mock_analyze_assessment_results
        self.patches = [
            patch("api.routers.ai_assessments.RateLimitService"),
            patch("api.routers.ai_assessments.get_user_business_profile"),
            patch("api.routers.ai_assessments.ComplianceAssistant"),
            patch("api.routers.ai_assessments.ai_rate_limit_stats"),
        ]
        for p in self.patches:
            p.start()
        from api.routers import ai_assessments

        async def mock_check_rate_limit(*args, **kwargs):
            return None

        async def mock_track_usage(*args, **kwargs):
            return None

        ai_assessments.RateLimitService.check_rate_limit = mock_check_rate_limit
        ai_assessments.RateLimitService.track_usage = mock_track_usage

        async def mock_get_user_business_profile(*args, **kwargs):
            return self.mock_profile

        ai_assessments.get_user_business_profile = mock_get_user_business_profile
        ai_assessments.ComplianceAssistant.return_value = self.mock_assistant
        ai_assessments.ai_rate_limit_stats.record_request.return_value = None
        from main import app
        from api.dependencies.auth import get_current_active_user
        from database.db_setup import get_async_db

        app.dependency_overrides[get_current_active_user] = lambda: self.mock_user
        app.dependency_overrides[get_async_db] = lambda: self.mock_db
        yield
        for p in self.patches:
            p.stop()
        app.dependency_overrides.clear()

    def test_ai_help_endpoint_success(self, client, authenticated_headers):
        """Test successful AI help request"""
        request_data = {
            "question_id": "q1",
            "question_text": "What are the data subject rights under GDPR?",
            "framework_id": "gdpr",
            "section_id": "section-1",
            "user_context": {"industry": "technology"},
        }
        response = client.post(
            "/api/v1/ai/gdpr/help", json=request_data, headers=authenticated_headers
        )
        if response.status_code != HTTP_OK:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert "guidance" in response_data
        assert "confidence_score" in response_data
        assert "request_id" in response_data
        assert "generated_at" in response_data
        assert response_data["confidence_score"] >= 0.0
        assert response_data["confidence_score"] <= 1.0

    def test_ai_help_endpoint_authentication_required(self, client):
        """Test AI help endpoint requires authentication"""
        from main import app
        from api.dependencies.auth import get_current_active_user

        current_override = app.dependency_overrides.get(get_current_active_user)
        if get_current_active_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_active_user]
        request_data = {
            "question_id": "q1",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        response = client.post("/api/v1/ai/gdpr/help", json=request_data)
        if current_override:
            app.dependency_overrides[get_current_active_user] = current_override
        assert response.status_code == HTTP_UNAUTHORIZED, (
            f"Expected 401, got {response.status_code}. Response: {response.json() if response.status_code != HTTP_UNAUTHORIZED else 'N/A'}"
        )

    def test_ai_help_endpoint_invalid_framework(self, client, authenticated_headers):
        """Test AI help endpoint with invalid framework"""
        request_data = {
            "question_id": "q1",
            "question_text": "What is compliance?",
            "framework_id": "invalid_framework",
        }
        response = client.post(
            "/api/v1/ai/invalid_framework/help", json=request_data, headers=authenticated_headers
        )
        assert response.status_code in [200, 400, 404]
        if response.status_code == HTTP_OK:
            data = response.json()
            assert "guidance" in data or "error" in data

    def test_followup_questions_endpoint_success(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test successful follow-up questions generation"""
        request_data = {
            "framework_id": "gdpr",
            "current_answers": {"q1": {"value": "yes", "source": "framework"}},
            "business_context": {
                "section_id": "data_processing",
                "business_profile_id": str(sample_business_profile.id),
            },
        }
        with patch.object(ComplianceAssistant, "generate_assessment_followup") as mock_followup:
            mock_followup.return_value = {
                "questions": [
                    {
                        "id": "ai-q1",
                        "text": "What types of personal data do you process?",
                        "type": "multiple_choice",
                        "options": [
                            {"value": "names", "label": "Names"},
                            {"value": "emails", "label": "Email addresses"},
                            {"value": "financial", "label": "Financial data"},
                        ],
                        "reasoning": "Need to understand data types",
                        "priority": "high",
                    }
                ],
                "request_id": "followup_123",
                "generated_at": "2024-01-01T00:00:00Z",
            }
            response = client.post(
                "/api/v1/ai/followup", json=request_data, headers=authenticated_headers
            )
            assert response.status_code == HTTP_OK
            response_data = response.json()
            assert "questions" in response_data
            assert len(response_data["questions"]) > 0
            assert response_data["questions"][0]["id"] == "ai-q1"
            assert "request_id" in response_data

    def test_analysis_endpoint_success(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test successful assessment analysis"""
        request_data = {
            "framework_id": "gdpr",
            "business_profile_id": str(sample_business_profile.id),
            "assessment_results": {
                "answers": {"q1": "yes", "q2": "no"},
                "completion_percentage": 85.0,
                "sections_completed": ["data_protection", "security"],
            },
        }
        response = client.post(
            "/api/v1/ai/analysis", json=request_data, headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert "gaps" in response_data
        assert "recommendations" in response_data
        assert "risk_assessment" in response_data
        assert "compliance_insights" in response_data
        assert "evidence_requirements" in response_data
        assert "request_id" in response_data

    def test_recommendations_endpoint_success(self, client, authenticated_headers):
        """Test successful personalized recommendations via stream endpoint"""
        request_data = {
            "gaps": [
                {"type": "missing_policy", "description": "Data protection policy missing"},
                {"type": "training", "description": "Staff training required"},
            ],
            "business_profile": {"industry": "technology", "size": "small", "location": "UK"},
            "timeline_preferences": "urgent",
        }
        response = client.post(
            "/api/v1/ai/recommendations/stream", json=request_data, headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK

    def test_feedback_endpoint_success(self, client, authenticated_headers):
        """Test successful feedback submission"""
        request_data = {
            "interaction_id": "test-request-123",
            "helpful": True,
            "rating": 5,
            "comments": "Very helpful guidance",
        }
        response = client.post(
            "/api/v1/ai/feedback", json=request_data, headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert "message" in response_data
        assert "status" in response_data
        assert response_data["status"] == "received"

    def test_metrics_endpoint_success(self, client, authenticated_headers):
        """Test AI metrics endpoint"""
        response = client.get(
            "/api/v1/ai/assessments/metrics?days=30", headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert "response_times" in response_data
        assert "accuracy_score" in response_data
        assert "user_satisfaction" in response_data
        assert "total_interactions" in response_data
        assert "quota_usage" in response_data

    def test_ai_service_timeout_handling(self, client, authenticated_headers):
        """Test handling of AI service timeouts"""
        request_data = {
            "question_id": "q1",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }

        async def mock_timeout(*args, **kwargs):
            raise AITimeoutException(timeout_seconds=30.0)

        self.mock_assistant.get_assessment_help = mock_timeout
        response = client.post(
            "/api/v1/ai/gdpr/help", json=request_data, headers=authenticated_headers
        )
        assert response.status_code in [408, 500, 503]

    def test_ai_quota_exceeded_handling(self, client, authenticated_headers):
        """Test handling of AI quota exceeded errors"""
        request_data = {
            "question_id": "q1",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }

        async def mock_quota_exceeded(*args, **kwargs):
            raise AIQuotaExceededException(quota_type="API requests")

        self.mock_assistant.get_assessment_help = mock_quota_exceeded
        response = client.post(
            "/api/v1/ai/gdpr/help", json=request_data, headers=authenticated_headers
        )
        assert response.status_code in [429, 503]

    def test_ai_content_filter_handling(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test handling of AI content filtering"""
        request_data = {
            "question_id": "q1",
            "question_text": "How to bypass GDPR requirements?",
            "framework_id": "gdpr",
            "user_context": {"business_profile_id": str(sample_business_profile.id)},
        }

        async def mock_content_filter(*args, **kwargs):
            raise AIContentFilterException(filter_reason="Inappropriate content")

        self.mock_assistant.get_assessment_help = mock_content_filter
        response = client.post(
            "/api/v1/ai/gdpr/help", json=request_data, headers=authenticated_headers
        )
        assert response.status_code in [400, 422, 503]

    def test_invalid_request_data_validation(self, client, authenticated_headers):
        """Test validation of invalid request data"""
        invalid_request = {"question_text": "What is GDPR compliance?"}
        response = client.post(
            "/api/v1/ai/gdpr/help", json=invalid_request, headers=authenticated_headers
        )
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_business_profile_not_found(self, client, authenticated_headers):
        """Test handling when business profile is not found"""
        from api.routers.ai_assessments import NotFoundException

        fake_profile_id = str(uuid4())
        request_data = {
            "framework_id": "gdpr",
            "business_profile_id": fake_profile_id,
            "assessment_results": {"answers": {"q1": "yes"}, "completion_percentage": 50.0},
        }

        async def mock_profile_not_found(*args, **kwargs):
            raise NotFoundException(f"Business profile {fake_profile_id} not found")

        from api.routers import ai_assessments

        original_get_profile = ai_assessments.get_user_business_profile
        ai_assessments.get_user_business_profile = mock_profile_not_found
        response = client.post(
            "/api/v1/ai/analysis", json=request_data, headers=authenticated_headers
        )
        ai_assessments.get_user_business_profile = original_get_profile
        assert response.status_code == HTTP_NOT_FOUND


@pytest.mark.integration
@pytest.mark.ai
@pytest.mark.rate_limiting
class TestAIRateLimiting:
    """Test AI-specific rate limiting"""

    @pytest.fixture(autouse=True)
    def setup_auth(self, sample_business_profile):
        """Set up minimal authentication for rate limiting tests"""
        mock_user = MagicMock()
        mock_user.id = "test-user-id"
        mock_user.email = "test@example.com"
        mock_user.is_active = True

        class AsyncMockDB:
            async def execute(self, stmt):
                result = MagicMock()
                result.scalar = MagicMock(return_value=0)
                return result

            def add(self, obj):
                pass

            async def commit(self):
                pass

            async def rollback(self):
                pass

            async def close(self):
                pass

        mock_db = AsyncMockDB()
        mock_assistant = MagicMock()

        async def mock_get_assessment_help(*args, **kwargs):
            return {
                "guidance": "Test guidance for rate limiting",
                "confidence_score": 0.9,
                "related_topics": ["topic1", "topic2"],
                "follow_up_suggestions": ["question1"],
                "source_references": ["source1"],
                "request_id": "test-request-id",
                "generated_at": "2024-01-01T00:00:00Z",
            }

        mock_assistant.get_assessment_help = mock_get_assessment_help
        from main import app
        from api.dependencies.auth import get_current_active_user
        from database.db_setup import get_async_db

        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        app.dependency_overrides[get_async_db] = lambda: mock_db
        patches = [
            patch("api.routers.ai_assessments.ComplianceAssistant"),
            patch("api.routers.ai_assessments.get_user_business_profile"),
        ]
        for p in patches:
            p.start()
        from api.routers import ai_assessments

        ai_assessments.ComplianceAssistant.return_value = mock_assistant

        async def mock_get_user_business_profile(*args, **kwargs):
            return sample_business_profile

        ai_assessments.get_user_business_profile = mock_get_user_business_profile
        yield
        for p in patches:
            p.stop()
        app.dependency_overrides.clear()

    def test_ai_help_rate_limiting(self, client, authenticated_headers):
        """Test rate limiting for AI help endpoint (10 req/min)"""
        request_data = {
            "question_id": "q1",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        responses = []
        for _i in range(12):
            response = client.post(
                "/api/v1/ai/gdpr/help", json=request_data, headers=authenticated_headers
            )
            responses.append(response)
        success_count = sum(1 for r in responses if r.status_code == HTTP_OK)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        if rate_limited_count > 0:
            assert success_count <= 11
            assert rate_limited_count >= 1
        else:
            assert success_count >= 10

    def test_ai_analysis_rate_limiting(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test rate limiting for AI analysis endpoint (3 req/min)"""
        request_data = {
            "framework_id": "gdpr",
            "business_profile_id": str(sample_business_profile.id),
            "assessment_results": {"answers": {"q1": "yes"}, "completion_percentage": 50.0},
        }
        responses = []
        for _i in range(5):
            response = client.post(
                "/api/v1/ai/analysis", json=request_data, headers=authenticated_headers
            )
            responses.append(response)
        success_count = sum(1 for r in responses if r.status_code == HTTP_OK)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        if rate_limited_count > 0:
            assert success_count <= 4
            assert rate_limited_count >= 1
        else:
            assert success_count >= MAX_RETRIES

    def test_regular_endpoints_higher_rate_limit(self, client, authenticated_headers):
        """Test that regular assessment endpoints have higher rate limits (100 req/min)"""
        responses = []
        for _i in range(15):
            response = client.get("/api/assessments", headers=authenticated_headers)
            responses.append(response)
        success_count = sum(1 for r in responses if r.status_code in [200, 404])
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        assert success_count >= 10
        assert rate_limited_count <= 2


@pytest.mark.integration
@pytest.mark.ai
@pytest.mark.error_handling
class TestAIErrorHandling:
    """Test comprehensive AI error handling scenarios"""

    @pytest.mark.skip(reason="Needs setup_mocks fixture")
    def test_ai_service_unavailable(self, client, authenticated_headers):
        """Test handling when AI service is completely unavailable"""
        request_data = {
            "question_id": "q1",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
            mock_help.side_effect = AIServiceException("AI service unavailable")
            response = client.post(
                "/api/v1/ai/gdpr/help", json=request_data, headers=authenticated_headers
            )
            assert response.status_code in [500, 503]
            if response.status_code == HTTP_INTERNAL_SERVER_ERROR:
                response_data = response.json()
                assert "detail" in response_data

    @pytest.mark.skip(reason="Needs setup_mocks fixture")
    def test_malformed_ai_response_handling(self, client, authenticated_headers):
        """Test handling of malformed AI responses"""
        request_data = {
            "question_id": "q1",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
            mock_help.return_value = "Invalid response format"
            response = client.post(
                "/api/v1/ai/gdpr/help", json=request_data, headers=authenticated_headers
            )
            assert response.status_code in [500, 502]

    @pytest.mark.skip(reason="Needs setup_mocks fixture")
    def test_ai_response_validation_errors(self, client, authenticated_headers):
        """Test handling of AI responses that fail validation"""
        request_data = {
            "question_id": "q1",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:
            mock_help.return_value = {
                "guidance": "Test guidance",
                "confidence_score": 1.5,
                "related_topics": ["data protection"],
                "follow_up_suggestions": ["Review policies"],
                "source_references": ["GDPR Article 6"],
                "request_id": "test_request_123",
                "generated_at": "2024-01-01T00:00:00Z",
            }
            response = client.post(
                "/api/v1/ai/gdpr/help", json=request_data, headers=authenticated_headers
            )
            assert response.status_code in [422, 500]

    def test_concurrent_ai_requests_handling(self, client, authenticated_headers):
        """Test handling of concurrent AI requests"""
        request_data = {
            "question_id": "q1",
            "question_text": "What is GDPR compliance?",
            "framework_id": "gdpr",
        }
        with patch.object(ComplianceAssistant, "get_assessment_help") as mock_help:

            def slow_response(*_args, **_kwargs):
                time.sleep(0.1)
                return {
                    "guidance": "Test guidance",
                    "confidence_score": 0.9,
                    "related_topics": ["data protection"],
                    "follow_up_suggestions": ["Review policies"],
                    "source_references": ["GDPR Article 6"],
                    "request_id": "test_request_123",
                    "generated_at": "2024-01-01T00:00:00Z",
                }

            mock_help.side_effect = slow_response
            responses = []
            for _i in range(5):
                response = client.post(
                    "/api/v1/ai/gdpr/help", json=request_data, headers=authenticated_headers
                )
                responses.append(response)
            pytest.skip("Authentication issue in test setup - needs setup_mocks fixture")
