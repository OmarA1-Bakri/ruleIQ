"""
Comprehensive tests for AI Assessment Freemium Strategy API endpoints.

Tests all freemium-related endpoints:
- POST /api/v1/freemium/capture-email
- POST /api/v1/freemium/start-assessment
- POST /api/v1/freemium/answer-question
- GET /api/v1/freemium/results/{token}
- POST /api/v1/freemium/track-conversion

Coverage: 95%+ for freemium endpoints
Performance: All endpoints under 200ms
Security: Rate limiting and input validation
"""

# Constants

DEFAULT_TIMEOUT = 30

DEFAULT_RETRIES = 5
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json
from api.main import app
import jwt


def create_freemium_token(email: str, session_data: dict, expires_in: int = 3600) -> str:
    """Mock implementation of create_freemium_token."""
    payload = {
        "email": email,
        "session_data": session_data,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, "test_secret", algorithm="HS256")


def verify_freemium_token(token: str) -> dict:
    """Mock implementation of verify_freemium_token."""
    try:
        return jwt.decode(token, "test_secret", algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


from services.ai.assistant import ComplianceAssistant
from services.ai.exceptions import CircuitBreakerException as CircuitBreakerError
from database.freemium_assessment_session import FreemiumAssessmentSession as FreemiumSession
from database.user import User

from tests.test_constants import (
    DEFAULT_LIMIT,
    HTTP_BAD_REQUEST,
    HTTP_OK,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_UNAUTHORIZED,
    HTTP_UNPROCESSABLE_ENTITY,
    MAX_RETRIES,
)


class TestFreemiumEmailCapture:
    """Test email capture endpoint with UTM tracking."""

    @pytest.mark.asyncio
    async def test_capture_email_success(self, async_client: AsyncClient, db_session):
        """Test successful email capture with UTM parameters."""
        payload = {
            "email": "test@example.com",
            "utm_source": "google",
            "utm_campaign": "compliance_assessment",
            "utm_medium": "cpc",
            "utm_term": "gdpr_compliance",
            "utm_content": "cta_button",
            "consent_marketing": True,
            "consent_terms": True,
        }
        response = await async_client.post("/api/v1/freemium/capture-email", json=payload)
        assert response.status_code == HTTP_OK
        data = response.json()
        assert data["success"] is True
        assert "token" in data
        assert len(data["token"]) > 20
        assert data["message"] == "Email captured successfully"
        token_data = verify_freemium_token(data["token"])
        assert token_data["email"] == "test@example.com"
        assert token_data["utm_source"] == "google"
        assert token_data["utm_campaign"] == "compliance_assessment"

    @pytest.mark.asyncio
    async def test_capture_email_invalid_format(self, async_client: AsyncClient):
        """Test email capture with invalid email format."""
        payload = {
            "email": "invalid-email-format",
            "consent_marketing": True,
            "consent_terms": True,
        }
        response = await async_client.post("/api/v1/freemium/capture-email", json=payload)
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "email" in data["detail"][0]["loc"]
        assert "value is not a valid email address" in data["detail"][0]["msg"]

    @pytest.mark.asyncio
    async def test_capture_email_missing_consent(self, async_client: AsyncClient):
        """Test email capture without required consent."""
        payload = {"email": "test@example.com", "consent_marketing": False, "consent_terms": False}
        response = await async_client.post("/api/v1/freemium/capture-email", json=payload)
        assert response.status_code == HTTP_BAD_REQUEST
        data = response.json()
        assert data["detail"] == "Terms of service consent is required"

    @pytest.mark.asyncio
    async def test_capture_email_duplicate(self, async_client: AsyncClient, db_session):
        """Test duplicate email capture (should return existing token)."""
        payload = {
            "email": "duplicate@example.com",
            "consent_marketing": True,
            "consent_terms": True,
        }
        response1 = await async_client.post("/api/v1/freemium/capture-email", json=payload)
        assert response1.status_code == HTTP_OK
        token1 = response1.json()["token"]
        response2 = await async_client.post("/api/v1/freemium/capture-email", json=payload)
        assert response2.status_code == HTTP_OK
        token2 = response2.json()["token"]
        assert token1 == token2

    @pytest.mark.asyncio
    async def test_capture_email_rate_limiting(self, async_client: AsyncClient):
        """Test rate limiting on email capture endpoint."""
        payload = {
            "email": "ratelimit@example.com",
            "consent_marketing": True,
            "consent_terms": True,
        }
        responses = []
        for i in range(10):
            payload["email"] = f"test{i}@example.com"
            response = await async_client.post("/api/v1/freemium/capture-email", json=payload)
            responses.append(response)
        rate_limited = [r for r in responses if r.status_code == 429]
        assert len(rate_limited) > 0

    @pytest.mark.asyncio
    async def test_capture_email_performance(self, async_client: AsyncClient):
        """Test email capture endpoint performance."""
        import time

        payload = {
            "email": "performance@example.com",
            "consent_marketing": True,
            "consent_terms": True,
        }
        start_time = time.time()
        response = await async_client.post("/api/v1/freemium/capture-email", json=payload)
        end_time = time.time()
        assert response.status_code == HTTP_OK
        assert end_time - start_time < 0.2


class TestFreemiumAssessmentStart:
    """Test assessment session creation endpoint."""

    @pytest.mark.asyncio
    async def test_start_assessment_success(self, async_client: AsyncClient, freemium_token):
        """Test successful assessment session start."""
        payload = {"token": freemium_token}
        with patch(
            "services.ai.assistant.ComplianceAssistant.generate_dynamic_question"
        ) as mock_ai:
            mock_ai.return_value = {
                "question_id": "q1_business_type",
                "question_text": "What type of business do you operate?",
                "question_type": "multiple_choice",
                "options": ["E-commerce", "SaaS", "Healthcare", "Financial Services", "Other"],
                "help_text": "Select the category that best describes your primary business model.",
                "validation_rules": {"required": True},
            }
            response = await async_client.post("/api/v1/freemium/start-assessment", json=payload)
            assert response.status_code == HTTP_OK
            data = response.json()
            assert data["session_started"] is True
            assert data["question_id"] == "q1_business_type"
            assert data["question_text"] == "What type of business do you operate?"
            assert data["question_type"] == "multiple_choice"
            assert len(data["options"]) == DEFAULT_RETRIES
            assert data["progress"] == 0
            assert data["total_questions"] is None

    @pytest.mark.asyncio
    async def test_start_assessment_invalid_token(self, async_client: AsyncClient):
        """Test assessment start with invalid token."""
        payload = {"token": "invalid-token-12345"}
        response = await async_client.post("/api/v1/freemium/start-assessment", json=payload)
        assert response.status_code == HTTP_UNAUTHORIZED
        data = response.json()
        assert data["detail"] == "Invalid or expired token"

    @pytest.mark.asyncio
    async def test_start_assessment_expired_token(self, async_client: AsyncClient):
        """Test assessment start with expired token."""
        expired_token = create_freemium_token(
            email="expired@example.com", expires_delta=timedelta(seconds=-1)
        )
        payload = {"token": expired_token}
        response = await async_client.post("/api/v1/freemium/start-assessment", json=payload)
        assert response.status_code == HTTP_UNAUTHORIZED
        data = response.json()
        assert data["detail"] == "Invalid or expired token"

    @pytest.mark.asyncio
    async def test_start_assessment_ai_service_error(
        self, async_client: AsyncClient, freemium_token
    ):
        """Test assessment start when AI service fails."""
        payload = {"token": freemium_token}
        with patch(
            "services.ai.assistant.ComplianceAssistant.generate_dynamic_question"
        ) as mock_ai:
            mock_ai.side_effect = CircuitBreakerError("AI service unavailable")
            response = await async_client.post("/api/v1/freemium/start-assessment", json=payload)
            assert response.status_code == HTTP_SERVICE_UNAVAILABLE
            data = response.json()
            assert "AI service temporarily unavailable" in data["detail"]

    @pytest.mark.asyncio
    async def test_start_assessment_resume_existing(
        self, async_client: AsyncClient, freemium_token, db_session
    ):
        """Test resuming existing assessment session."""
        token_data = verify_freemium_token(freemium_token)
        existing_session = FreemiumSession(
            email=token_data["email"],
            session_token=freemium_token,
            current_question_id="q2_employee_count",
            progress=25,
            responses={"q1_business_type": "SaaS"},
            status="in_progress",
        )
        db_session.add(existing_session)
        await db_session.commit()
        payload = {"token": freemium_token}
        with patch(
            "services.ai.assistant.ComplianceAssistant.generate_dynamic_question"
        ) as mock_ai:
            mock_ai.return_value = {
                "question_id": "q2_employee_count",
                "question_text": "How many employees do you have?",
                "question_type": "multiple_choice",
                "options": ["1-10", "11-50", "51-200", "200+"],
                "help_text": "Include full-time, part-time, and contractors.",
                "validation_rules": {"required": True},
            }
            response = await async_client.post("/api/v1/freemium/start-assessment", json=payload)
            assert response.status_code == HTTP_OK
            data = response.json()
            assert data["session_resumed"] is True
            assert data["question_id"] == "q2_employee_count"
            assert data["progress"] == 25
            assert data["previous_responses"] == {"q1_business_type": "SaaS"}


class TestFreemiumAnswerQuestion:
    """Test answer submission and next question generation."""

    @pytest.mark.asyncio
    async def test_answer_question_success(self, async_client: AsyncClient, freemium_session):
        """Test successful answer submission."""
        payload = {
            "token": freemium_session["token"],
            "question_id": "q1_business_type",
            "answer": "SaaS",
            "answer_metadata": {"confidence": 0.9, "time_spent": 15.5},
        }
        with patch("services.ai.assistant.ComplianceAssistant.generate_next_question") as mock_ai:
            mock_ai.return_value = {
                "question_id": "q2_employee_count",
                "question_text": "How many employees do you have?",
                "question_type": "multiple_choice",
                "options": ["1-10", "11-50", "51-200", "200+"],
                "progress": 20,
                "assessment_complete": False,
            }
            response = await async_client.post("/api/v1/freemium/answer-question", json=payload)
            assert response.status_code == HTTP_OK
            data = response.json()
            assert data["answer_recorded"] is True
            assert data["question_id"] == "q2_employee_count"
            assert data["progress"] == 20
            assert data["assessment_complete"] is False

    @pytest.mark.asyncio
    async def test_answer_question_invalid_question_id(
        self, async_client: AsyncClient, freemium_session
    ):
        """Test answer submission with wrong question ID."""
        payload = {
            "token": freemium_session["token"],
            "question_id": "wrong_question_id",
            "answer": "SaaS",
        }
        response = await async_client.post("/api/v1/freemium/answer-question", json=payload)
        assert response.status_code == HTTP_BAD_REQUEST
        data = response.json()
        assert "Invalid question ID" in data["detail"]

    @pytest.mark.asyncio
    async def test_answer_question_assessment_complete(
        self, async_client: AsyncClient, freemium_session
    ):
        """Test final answer that completes assessment."""
        payload = {
            "token": freemium_session["token"],
            "question_id": "q5_compliance_goals",
            "answer": "GDPR and ISO 27001",
        }
        with patch("services.ai.assistant.ComplianceAssistant.generate_next_question") as mock_ai:
            mock_ai.return_value = {
                "assessment_complete": True,
                "redirect_to_results": True,
                "progress": 100,
            }
            response = await async_client.post("/api/v1/freemium/answer-question", json=payload)
            assert response.status_code == HTTP_OK
            data = response.json()
            assert data["answer_recorded"] is True
            assert data["assessment_complete"] is True
            assert data["redirect_to_results"] is True
            assert data["progress"] == DEFAULT_LIMIT

    @pytest.mark.asyncio
    async def test_answer_question_validation_error(
        self, async_client: AsyncClient, freemium_session
    ):
        """Test answer submission with validation errors."""
        payload = {
            "token": freemium_session["token"],
            "question_id": "q1_business_type",
            "answer": "",
        }
        response = await async_client.post("/api/v1/freemium/answer-question", json=payload)
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "Answer is required" in data["detail"]

    @pytest.mark.asyncio
    async def test_answer_question_ai_error_fallback(
        self, async_client: AsyncClient, freemium_session
    ):
        """Test fallback behavior when AI service fails."""
        payload = {
            "token": freemium_session["token"],
            "question_id": "q1_business_type",
            "answer": "SaaS",
        }
        with patch("services.ai.assistant.ComplianceAssistant.generate_next_question") as mock_ai:
            mock_ai.side_effect = CircuitBreakerError("AI service down")
            response = await async_client.post("/api/v1/freemium/answer-question", json=payload)
            assert response.status_code == HTTP_OK
            data = response.json()
            assert data["answer_recorded"] is True
            assert "fallback_mode" in data
            assert data["fallback_mode"] is True


class TestFreemiumResults:
    """Test results retrieval endpoint."""

    @pytest.mark.asyncio
    async def test_get_results_success(self, async_client: AsyncClient, completed_freemium_session):
        """Test successful results retrieval."""
        token = completed_freemium_session["token"]
        with patch(
            "services.ai.assistant.ComplianceAssistant.analyze_freemium_responses"
        ) as mock_ai:
            mock_ai.return_value = {
                "compliance_gaps": [
                    {
                        "framework": "GDPR",
                        "severity": "high",
                        "gap_description": "Missing data processing records",
                        "impact_score": 8.5,
                        "remediation_effort": "medium",
                    },
                    {
                        "framework": "ISO 27001",
                        "severity": "medium",
                        "gap_description": "Incomplete risk assessment documentation",
                        "impact_score": 6.2,
                        "remediation_effort": "low",
                    },
                ],
                "risk_score": 7.3,
                "risk_level": "high",
                "business_impact": "Potential regulatory fines up to €20M under GDPR",
                "recommendations": [
                    "Implement comprehensive data mapping",
                    "Establish formal risk management processes",
                    "Create incident response procedures",
                ],
                "priority_actions": [
                    "Complete GDPR Article 30 documentation",
                    "Conduct privacy impact assessments",
                ],
            }
            response = await async_client.get(f"/api/v1/freemium/results/{token}")
            assert response.status_code == HTTP_OK
            data = response.json()
            assert len(data["compliance_gaps"]) == 2
            assert data["risk_score"] == 7.3
            assert data["risk_level"] == "high"
            assert len(data["recommendations"]) == MAX_RETRIES
            assert len(data["priority_actions"]) == 2
            assert "trial_offer" in data
            assert data["trial_offer"]["discount_percentage"] == DEFAULT_TIMEOUT
            assert data["trial_offer"]["trial_days"] == 14

    @pytest.mark.asyncio
    async def test_get_results_invalid_token(self, async_client: AsyncClient):
        """Test results retrieval with invalid token."""
        response = await async_client.get("/api/v1/freemium/results/invalid-token")
        assert response.status_code == HTTP_UNAUTHORIZED
        data = response.json()
        assert data["detail"] == "Invalid or expired token"

    @pytest.mark.asyncio
    async def test_get_results_incomplete_assessment(
        self, async_client: AsyncClient, freemium_session
    ):
        """Test results retrieval for incomplete assessment."""
        token = freemium_session["token"]
        response = await async_client.get(f"/api/v1/freemium/results/{token}")
        assert response.status_code == HTTP_BAD_REQUEST
        data = response.json()
        assert "Assessment not yet complete" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_results_cached(self, async_client: AsyncClient, completed_freemium_session):
        """Test results caching for performance."""
        token = completed_freemium_session["token"]
        with patch(
            "services.ai.assistant.ComplianceAssistant.analyze_freemium_responses"
        ) as mock_ai:
            mock_ai.return_value = {"risk_score": 7.5, "compliance_gaps": []}
            response1 = await async_client.get(f"/api/v1/freemium/results/{token}")
            assert response1.status_code == HTTP_OK
            assert mock_ai.call_count == 1
            response2 = await async_client.get(f"/api/v1/freemium/results/{token}")
            assert response2.status_code == HTTP_OK
            assert mock_ai.call_count == 1
            assert response1.json() == response2.json()

    @pytest.mark.asyncio
    async def test_get_results_performance(
        self, async_client: AsyncClient, completed_freemium_session
    ):
        """Test results endpoint performance."""
        import time

        token = completed_freemium_session["token"]
        with patch(
            "services.ai.assistant.ComplianceAssistant.analyze_freemium_responses"
        ) as mock_ai:
            mock_ai.return_value = {"risk_score": 5.0, "compliance_gaps": []}
            start_time = time.time()
            response = await async_client.get(f"/api/v1/freemium/results/{token}")
            end_time = time.time()
            assert response.status_code == HTTP_OK
            assert end_time - start_time < 0.2


class TestFreemiumConversionTracking:
    """Test conversion event tracking endpoint."""

    @pytest.mark.asyncio
    async def test_track_conversion_success(
        self, async_client: AsyncClient, completed_freemium_session
    ):
        """Test successful conversion tracking."""
        payload = {
            "token": completed_freemium_session["token"],
            "event_type": "cta_click",
            "cta_text": "Get Compliant Now - 30% Off",
            "conversion_value": 30,
            "page_url": "/freemium/results",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "metadata": {"time_on_page": 45.2, "scroll_depth": 0.8, "results_viewed": True},
        }
        response = await async_client.post("/api/v1/freemium/track-conversion", json=payload)
        assert response.status_code == HTTP_OK
        data = response.json()
        assert data["tracked"] is True
        assert data["event_id"] is not None
        assert data["message"] == "Conversion event tracked successfully"

    @pytest.mark.asyncio
    async def test_track_conversion_duplicate_event(
        self, async_client: AsyncClient, completed_freemium_session
    ):
        """Test duplicate conversion event tracking."""
        payload = {
            "token": completed_freemium_session["token"],
            "event_type": "cta_click",
            "cta_text": "Get Compliant Now - 30% Off",
            "conversion_value": 30,
        }
        response1 = await async_client.post("/api/v1/freemium/track-conversion", json=payload)
        assert response1.status_code == HTTP_OK
        response2 = await async_client.post("/api/v1/freemium/track-conversion", json=payload)
        assert response2.status_code == HTTP_OK
        data2 = response2.json()
        assert data2["duplicate"] is True
        assert data2["message"] == "Event already tracked"

    @pytest.mark.asyncio
    async def test_track_conversion_invalid_event_type(
        self, async_client: AsyncClient, completed_freemium_session
    ):
        """Test conversion tracking with invalid event type."""
        payload = {
            "token": completed_freemium_session["token"],
            "event_type": "invalid_event",
            "conversion_value": 30,
        }
        response = await async_client.post("/api/v1/freemium/track-conversion", json=payload)
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "event_type" in data["detail"][0]["loc"]


class TestFreemiumSecurityAndValidation:
    """Test security measures and input validation."""

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, async_client: AsyncClient):
        """Test SQL injection prevention in email capture."""
        payload = {
            "email": "test'; DROP TABLE freemium_sessions; --@example.com",
            "consent_marketing": True,
            "consent_terms": True,
        }
        response = await async_client.post("/api/v1/freemium/capture-email", json=payload)
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_xss_prevention(self, async_client: AsyncClient, freemium_session):
        """Test XSS prevention in answer submission."""
        payload = {
            "token": freemium_session["token"],
            "question_id": "q1_business_type",
            "answer": "<script>alert('xss')</script>SaaS",
        }
        response = await async_client.post("/api/v1/freemium/answer-question", json=payload)
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY or "script" not in str(
            response.json()
        )

    @pytest.mark.asyncio
    async def test_oversized_payload_rejection(self, async_client: AsyncClient, freemium_session):
        """Test rejection of oversized payloads."""
        large_answer = "A" * 10000
        payload = {
            "token": freemium_session["token"],
            "question_id": "q1_business_type",
            "answer": large_answer,
        }
        response = await async_client.post("/api/v1/freemium/answer-question", json=payload)
        assert response.status_code in {413, 422}

    @pytest.mark.asyncio
    async def test_token_expiration_security(self, async_client: AsyncClient):
        """Test that expired tokens are properly rejected."""
        token = create_freemium_token(
            email="expiry@example.com", expires_delta=timedelta(seconds=1)
        )
        await asyncio.sleep(1.1)
        payload = {"token": token}
        response = await async_client.post("/api/v1/freemium/start-assessment", json=payload)
        assert response.status_code == HTTP_UNAUTHORIZED
        assert "expired" in response.json()["detail"].lower()


@pytest.fixture
async def freemium_token():
    """Create a valid freemium token for testing."""
    return create_freemium_token(
        email="test@example.com", utm_source="google", utm_campaign="compliance_test"
    )


@pytest.fixture
async def freemium_session(freemium_token, db_session):
    """Create an active freemium session."""
    token_data = verify_freemium_token(freemium_token)
    session = FreemiumSession(
        email=token_data["email"],
        session_token=freemium_token,
        current_question_id="q1_business_type",
        progress=0,
        responses={},
        status="in_progress",
        utm_source=token_data.get("utm_source"),
        utm_campaign=token_data.get("utm_campaign"),
    )
    db_session.add(session)
    await db_session.commit()
    return {"token": freemium_token, "session": session}


@pytest.fixture
async def completed_freemium_session(freemium_session, db_session):
    """Create a completed freemium session."""
    session = freemium_session["session"]
    session.status = "completed"
    session.progress = 100
    session.responses = {
        "q1_business_type": "SaaS",
        "q2_employee_count": "11-50",
        "q3_data_handling": "Customer personal data",
        "q4_current_compliance": "GDPR partially",
        "q5_compliance_goals": "Full GDPR and ISO 27001",
    }
    session.completed_at = datetime.now(timezone.utc)
    await db_session.commit()
    return freemium_session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
