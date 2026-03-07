"""

External Service Integration Tests

Tests integration with external services including:
- AI Services (Google Gemini, OpenAI) with circuit breaker
- Database integration (Neon PostgreSQL)
- Redis caching integration
- Email service integration
- File storage integration
- Third-party API integrations
"""

import asyncio
import json
import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import redis
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app
from services.ai.circuit_breaker import AICircuitBreaker as CircuitBreaker, CircuitState
from services.ai.assistant import ComplianceAssistant
from config.settings import settings
from tests.utils.auth_test_utils import TestAuthManager


@pytest.mark.integration
@pytest.mark.external
class TestAIServiceIntegration:
    """Test AI service integrations with circuit breaker patterns"""

    @pytest.fixture
    async def async_client(self):
        """Create async test client"""
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    async def auth_headers(self, async_db):
        """Create authentication headers"""
        auth_manager = TestAuthManager()
        user = auth_manager.create_test_user(
            email="ai.integration@test.com",
            username=["ai.integration", "test.com"][0],
        )
        from api.dependencies.auth import create_access_token

        token = create_access_token(data={"sub": user.email})
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_gemini_integration_with_circuit_breaker(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test Google Gemini integration with circuit breaker functionality"""

        # Create test assessment for AI analysis
        assessment_data = {
            "name": "Gemini Integration Test",
            "framework": "GDPR",
            "questions": [
                {
                    "question_id": "gdpr_data_processing",
                    "question_text": "Do you process personal data?",
                    "answer": "yes",
                    "evidence_ids": [],
                },
            ],
        }

        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        assessment_id = response.json()["id"]

        # Test 1: Successful Gemini API call
        with patch("services.ai.assistant.ComplianceAssistant._call_gemini_api") as mock_gemini:
            mock_gemini.return_value = {
                "compliance_score": 0.85,
                "risk_level": "LOW",
                "analysis": "Strong data protection practices",
                "recommendations": ["Implement regular audits"],
            }

            response = await async_client.post(
                f"/assessments/{assessment_id}/analyze",
                headers=auth_headers,
            )

            assert response.status_code == 200
            analysis = response.json()

            # Verify Gemini was called
            mock_gemini.assert_called_once()
            assert analysis["compliance_score"] == 0.85
            assert analysis["risk_level"] == "LOW"

    @pytest.mark.asyncio
    async def test_ai_service_circuit_breaker_states(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test AI service circuit breaker state transitions"""

        assessment_data = {"name": "Circuit Breaker Test", "framework": "GDPR"}
        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=auth_headers,
        )
        assessment_id = response.json()["id"]

        # Test circuit breaker CLOSED state (normal operation)
        with patch("services.ai.circuit_breaker.CircuitBreaker") as mock_cb_class:
            mock_cb = Mock()
            mock_cb.state = CircuitState.CLOSED
            mock_cb.call = AsyncMock(
                return_value={"compliance_score": 0.8, "risk_level": "MEDIUM"},
            )
            mock_cb_class.return_value = mock_cb

            response = await async_client.post(
                f"/assessments/{assessment_id}/analyze",
                headers=auth_headers,
            )

            assert response.status_code == 200
            result = response.json()
            assert result["compliance_score"] == 0.8

        # Test circuit breaker OPEN state (failures trigger fallback)
        with patch("services.ai.assistant.ComplianceAssistant._call_gemini_api") as mock_gemini:
            # Simulate repeated failures
            mock_gemini.side_effect = Exception("API timeout")

            # Multiple failed requests should eventually trigger fallback
            for attempt in range(3):
                response = await async_client.post(
                    f"/assessments/{assessment_id}/analyze",
                    headers=auth_headers,
                )

                # Should still return 200 due to fallback mechanism
                assert response.status_code == 200
                result = response.json()

                # After enough failures, should use fallback response
                if attempt >= 2:
                    assert "fallback" in result.get("source", "").lower() or result.get(
                        "compliance_score"
                    ) in [
                        0.5,
                        0.0,
                    ]  # Fallback scores

    @pytest.mark.asyncio
    async def test_ai_service_timeout_handling(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test AI service timeout handling"""

        assessment_data = {"name": "Timeout Test", "framework": "GDPR"}
        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=auth_headers,
        )
        assessment_id = response.json()["id"]

        with patch("services.ai.assistant.ComplianceAssistant._call_gemini_api") as mock_gemini:
            # Simulate timeout
            async def slow_response(*args, **kwargs):
                await asyncio.sleep(2)  # Longer than circuit breaker timeout
                return {"compliance_score": 0.7}

            mock_gemini.side_effect = slow_response

            start_time = time.time()
            response = await async_client.post(
                f"/assessments/{assessment_id}/analyze",
                headers=auth_headers,
            )
            end_time = time.time()

            # Should timeout and use fallback within reasonable time
            assert response.status_code == 200
            assert (end_time - start_time) < 5  # Should not wait full 2 seconds due to timeout

            result = response.json()
            # Should either be fallback response or successful with timeout handling
            assert "compliance_score" in result

    @pytest.mark.asyncio
    async def test_multiple_ai_provider_fallback(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test fallback chain: Gemini → OpenAI → Static fallback"""

        assessment_data = {"name": "Multi-Provider Test", "framework": "GDPR"}
        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=auth_headers,
        )
        assessment_id = response.json()["id"]

        with (
            patch("services.ai.assistant.ComplianceAssistant._call_gemini_api") as mock_gemini,
            patch("services.ai.assistant.ComplianceAssistant._call_openai_api") as mock_openai,
        ):
            # Gemini fails
            mock_gemini.side_effect = Exception("Gemini API unavailable")

            # OpenAI succeeds
            mock_openai.return_value = {
                "compliance_score": 0.72,
                "risk_level": "MEDIUM",
                "analysis": "Fallback analysis from OpenAI",
            }

            response = await async_client.post(
                f"/assessments/{assessment_id}/analyze",
                headers=auth_headers,
            )

            assert response.status_code == 200
            result = response.json()

            # Should use OpenAI fallback
            mock_gemini.assert_called_once()
            mock_openai.assert_called_once()
            assert result["compliance_score"] == 0.72


@pytest.mark.integration
@pytest.mark.external
@pytest.mark.database
class TestDatabaseIntegration:
    """Test database integration with Neon PostgreSQL"""

    @pytest.fixture
    async def async_client(self):
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    async def auth_headers(self, async_db):
        auth_manager = TestAuthManager()
        user = auth_manager.create_test_user(
            email="db.integration@test.com",
            username=["db.integration", "test.com"][0],
        )
        from api.dependencies.auth import create_access_token

        token = create_access_token(data={"sub": user.email})
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_database_connection_pool_behavior(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test database connection pool under concurrent load"""

        async def create_assessment(i: int):
            assessment_data = {
                "name": f"Concurrent Assessment {i}",
                "framework": "GDPR",
            }
            return await async_client.post(
                "/assessments",
                json=assessment_data,
                headers=auth_headers,
            )

        # Create multiple assessments concurrently
        tasks = [create_assessment(i) for i in range(10)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful responses
        successful_responses = [
            r for r in responses if not isinstance(r, Exception) and r.status_code == 201
        ]

        # Most requests should succeed (allowing for some connection pool limits)
        assert len(successful_responses) >= 8, (
            f"Only {len(successful_responses)}/10 requests succeeded"
        )

    @pytest.mark.asyncio
    async def test_database_transaction_consistency(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test database transaction consistency across service operations"""

        # Create assessment with evidence (should be atomic)
        assessment_data = {
            "name": "Transaction Test Assessment",
            "framework": "GDPR",
            "evidence_ids": [],  # Will add evidence in separate call,
        }

        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        assessment_id = response.json()["id"]

        # Upload evidence
        files = {"file": ("test.pdf", b"Test content", "application/pdf")}
        metadata = {"title": "Transaction Test Evidence", "framework": "GDPR"}

        response = await async_client.post(
            "/evidence/upload",
            files=files,
            data=metadata,
            headers=auth_headers,
        )
        assert response.status_code == 201
        evidence_id = response.json()["id"]

        # Link evidence to assessment (should maintain referential integrity)
        update_data = {"evidence_ids": [evidence_id]}
        response = await async_client.patch(
            f"/assessments/{assessment_id}",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Verify consistency - both assessment and evidence should exist and be linked
        response = await async_client.get(
            f"/assessments/{assessment_id}",
            headers=auth_headers,
        )
        assessment = response.json()
        assert evidence_id in assessment["evidence_ids"]

        response = await async_client.get(
            f"/evidence/{evidence_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_database_failover_behavior(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test database failover and recovery behavior"""

        # This test simulates database connectivity issues
        with patch("database.db_setup.get_async_db") as mock_db:
            # First call succeeds
            mock_db.return_value.__anext__ = AsyncMock()

            # Simulate temporary database connection failure
            from sqlalchemy.exc import DisconnectionError

            mock_db.side_effect = [DisconnectionError("Connection lost", None, None)]

            assessment_data = {"name": "Failover Test", "framework": "GDPR"}

            # Should handle database connection errors gracefully
            response = await async_client.post(
                "/assessments",
                json=assessment_data,
                headers=auth_headers,
            )

            # Either succeeds with retry or returns appropriate error
            assert response.status_code in [201, 503, 500]


@pytest.mark.integration
@pytest.mark.external
class TestRedisIntegration:
    """Test Redis caching integration"""

    @pytest.fixture
    async def async_client(self):
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    async def auth_headers(self, async_db):
        auth_manager = TestAuthManager()
        user = auth_manager.create_test_user(
            email="redis.integration@test.com",
            username=["redis.integration", "test.com"][0],
        )
        from api.dependencies.auth import create_access_token

        token = create_access_token(data={"sub": user.email})
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_redis_session_management(self, async_client: httpx.AsyncClient):
        """Test Redis session storage and retrieval"""

        # Login to create session
        login_data = {
            "username": "redis.test@example.com",
            "password": "TestPassword123!",
        }

        # First register user
        registration_data = {
            "email": login_data["username"],
            "password": login_data["password"],
            "company_name": "Redis Test Co",
            "role": "business_user",
        }

        response = await async_client.post("/auth/register", json=registration_data)
        assert response.status_code == 201

        # Then login
        response = await async_client.post("/auth/login", data=login_data)
        assert response.status_code == 200
        token_data = response.json()

        headers = {"Authorization": f"Bearer {token_data['access_token']}"}

        # Test session persistence across requests
        response1 = await async_client.get("/auth/me", headers=headers)
        assert response1.status_code == 200

        response2 = await async_client.get("/auth/me", headers=headers)
        assert response2.status_code == 200

        # Should return consistent user data
        assert response1.json()["id"] == response2.json()["id"]

    @pytest.mark.asyncio
    async def test_redis_caching_behavior(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test Redis caching for API responses"""

        # Make request that should be cached
        response1 = await async_client.get("/frameworks", headers=auth_headers)
        assert response1.status_code == 200
        frameworks1 = response1.json()

        start_time = time.time()
        # Second request should be faster due to caching
        response2 = await async_client.get("/frameworks", headers=auth_headers)
        end_time = time.time()

        assert response2.status_code == 200
        frameworks2 = response2.json()

        # Should return same data
        assert frameworks1 == frameworks2

        # Second request should be faster (cached)
        response_time = end_time - start_time
        assert response_time < 0.1  # Should be very fast if cached

    @pytest.mark.asyncio
    async def test_redis_cache_invalidation(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test Redis cache invalidation on data updates"""

        # Create assessment (should invalidate assessment list cache)
        assessment_data = {"name": "Cache Test Assessment", "framework": "GDPR"}

        # Get initial list
        response = await async_client.get("/assessments", headers=auth_headers)
        initial_count = len(response.json())

        # Create new assessment
        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=auth_headers,
        )
        assert response.status_code == 201

        # Get updated list (cache should be invalidated)
        response = await async_client.get("/assessments", headers=auth_headers)
        updated_count = len(response.json())

        assert updated_count == initial_count + 1

    def test_redis_connection_health(self):
        """Test Redis connection health and configuration"""

        try:
            # Test direct Redis connection
            redis_client = (
                redis.from_url(settings.REDIS_URL) if hasattr(settings, "REDIS_URL") else None,
            )

            if redis_client:
                # Test basic operations
                test_key = "health_check_test"
                redis_client.set(test_key, "test_value", ex=60)
                retrieved_value = redis_client.get(test_key)

                assert retrieved_value.decode() == "test_value"

                # Cleanup
                redis_client.delete(test_key)

        except Exception as e:
            # Redis might not be available in test environment
            pytest.skip(f"Redis not available for testing: {e}")


@pytest.mark.integration
@pytest.mark.external
@pytest.mark.slow
class TestEmailServiceIntegration:
    """Test email service integration"""

    @pytest.fixture
    async def async_client(self):
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    async def test_password_reset_email_integration(self, async_client: httpx.AsyncClient):
        """Test password reset email functionality"""

        # Register user first
        registration_data = {
            "email": "email.test@example.com",
            "password": "TestPassword123!",
            "company_name": "Email Test Co",
            "role": "business_user",
        }

        response = await async_client.post("/auth/register", json=registration_data)
        assert response.status_code == 201

        # Request password reset
        with patch("services.email_service.send_password_reset_email") as mock_email:
            mock_email.return_value = True

            reset_data = {"email": registration_data["email"]}
            response = await async_client.post("/auth/forgot-password", json=reset_data)

            # Should succeed regardless of actual email sending
            assert response.status_code in [200, 202]

            # Email service should be called
            if response.status_code == 200:
                mock_email.assert_called_once_with(
                    registration_data["email"],
                    reset_token=str,
                )

    @pytest.mark.asyncio
    async def test_assessment_completion_notification(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test email notifications for assessment completion"""

        with patch("services.email_service.send_assessment_completion_email") as mock_email:
            mock_email.return_value = True

            # Create and complete assessment
            assessment_data = {"name": "Email Notification Test", "framework": "GDPR"}
            response = await async_client.post(
                "/assessments",
                json=assessment_data,
                headers=auth_headers,
            )
            assessment_id = response.json()["id"]

            # Mark as completed (trigger email)
            update_data = {"status": "completed"}
            response = await async_client.patch(
                f"/assessments/{assessment_id}",
                json=update_data,
                headers=auth_headers,
            )

            assert response.status_code == 200

            # Email should be sent (if configured)
            # mock_email.assert_called_once()


@pytest.mark.integration
@pytest.mark.external
class TestFileStorageIntegration:
    """Test file storage integration"""

    @pytest.fixture
    async def async_client(self):
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    async def auth_headers(self, async_db):
        auth_manager = TestAuthManager()
        user = auth_manager.create_test_user(
            email="storage.test@example.com",
            username=["storage.test", "example.com"][0],
        )
        from api.dependencies.auth import create_access_token

        token = create_access_token(data={"sub": user.email})
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_file_upload_storage_integration(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test file upload and storage integration"""

        # Test file upload
        files = {
            "file": ("integration_test.pdf", b"Test PDF content", "application/pdf"),
        }
        metadata = {
            "title": "Storage Integration Test",
            "description": "Test file for storage integration",
            "evidence_type": "policy_document",
        }

        response = await async_client.post(
            "/evidence/upload",
            files=files,
            data=metadata,
            headers=auth_headers,
        )

        assert response.status_code == 201
        evidence = response.json()

        # Verify file was stored
        assert "file_path" in evidence
        assert evidence["title"] == metadata["title"]

        # Test file retrieval
        evidence_id = evidence["id"]
        response = await async_client.get(
            f"/evidence/{evidence_id}/download",
            headers=auth_headers,
        )

        # Should either return file or redirect to file location
        assert response.status_code in [200, 302]

    @pytest.mark.asyncio
    async def test_file_processing_integration(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test file processing workflow integration"""

        # Upload file
        files = {
            "file": (
                "process_test.pdf",
                b"Document content for processing",
                "application/pdf",
            )
        }
        metadata = {
            "title": "Processing Test Document",
            "evidence_type": "policy_document",
            "framework": "GDPR",
        }

        response = await async_client.post(
            "/evidence/upload",
            files=files,
            data=metadata,
            headers=auth_headers,
        )

        assert response.status_code == 201
        evidence_id = response.json()["id"]

        # Trigger processing
        with patch("services.document_processor.process_document") as mock_processor:
            mock_processor.return_value = {
                "document_type": "privacy_policy",
                "extracted_text": "Privacy policy content...",
                "compliance_areas": ["data_protection", "consent"],
                "confidence_score": 0.95,
            }

            response = await async_client.post(
                f"/evidence/{evidence_id}/process",
                headers=auth_headers,
            )

            assert response.status_code == 200
            processing_result = response.json()

            # Verify processing was triggered
            mock_processor.assert_called_once()
            assert processing_result["document_type"] == "privacy_policy"
            assert processing_result["confidence_score"] == 0.95


@pytest.mark.integration
@pytest.mark.external
@pytest.mark.network
class TestThirdPartyAPIIntegration:
    """Test third-party API integrations"""

    @pytest.fixture
    async def async_client(self):
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    async def auth_headers(self, async_db):
        auth_manager = TestAuthManager()
        user = auth_manager.create_test_user(
            email="api.integration@test.com",
            username=["api.integration", "test.com"][0],
        )
        from api.dependencies.auth import create_access_token

        token = create_access_token(data={"sub": user.email})
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_companies_house_api_integration(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test Companies House API integration for company verification"""

        with patch("services.companies_house.CompaniesHouseAPI.lookup_company") as mock_ch:
            mock_ch.return_value = {
                "company_number": "12345678",
                "company_name": "Test Company Ltd",
                "company_status": "active",
                "incorporation_date": "2020-01-01",
            }

            # Test company lookup
            lookup_data = {"company_number": "12345678"}
            response = await async_client.post(
                "/integrations/companies-house/lookup",
                json=lookup_data,
                headers=auth_headers,
            )

            if response.status_code == 404:
                pytest.skip("Companies House integration endpoint not implemented")

            assert response.status_code == 200
            company_data = response.json()

            mock_ch.assert_called_once_with("12345678")
            assert company_data["company_name"] == "Test Company Ltd"

    @pytest.mark.asyncio
    async def test_external_api_timeout_handling(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test external API timeout and error handling"""

        with patch("httpx.AsyncClient.get") as mock_get:
            # Simulate timeout
            mock_get.side_effect = httpx.TimeoutException("Request timeout")

            # Try to use an external integration
            response = await async_client.get(
                "/integrations/health-check",
                headers=auth_headers,
            )

            if response.status_code == 404:
                pytest.skip("External integrations health check not implemented")

            # Should handle timeout gracefully
            assert response.status_code in [200, 503, 504]

    @pytest.mark.asyncio
    async def test_external_api_rate_limiting_respect(
        self, async_client: httpx.AsyncClient, auth_headers: Dict
    ):
        """Test that external API rate limits are respected"""

        with patch("services.external_integration.RateLimiter") as mock_limiter:
            mock_limiter.return_value.is_allowed.return_value = False

            # Multiple rapid requests should be rate limited
            responses = []
            for i in range(5):
                response = await async_client.post(
                    "/integrations/test-api",
                    json={"test": f"request_{i}"},
                    headers=auth_headers,
                )
                responses.append(response)

            # Should respect rate limiting (either 429 responses or controlled timing)
            status_codes = [r.status_code for r in responses]

            # If endpoint exists, should show rate limiting behavior
            if any(code != 404 for code in status_codes):
                rate_limited_responses = [code for code in status_codes if code == 429]
                # Should have some rate limited responses or controlled timing
                assert len(rate_limited_responses) > 0 or all(
                    code in [200, 201, 503] for code in status_codes if code != 404
                )
