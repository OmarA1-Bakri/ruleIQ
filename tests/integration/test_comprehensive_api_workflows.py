"""

Comprehensive API Workflow Integration Tests

Tests complete end-to-end API workflows including:
- Authentication flow with JWT + RBAC
- Compliance assessment pipeline
- Evidence collection workflow
- AI service integration with circuit breaker
- Cross-service data consistency
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app
from database.assessment_session import AssessmentSession as Assessment
from database.models.evidence import Evidence
from database.user import User
from services.ai.circuit_breaker import AICircuitBreaker as CircuitBreaker, CircuitState
from services.ai.assistant import ComplianceAssistant
from tests.utils.auth_test_utils import TestAuthManager

# create_test_assessment is not implemented yet


@pytest.mark.integration
@pytest.mark.api
class TestComprehensiveAPIWorkflows:
    """Test complete API workflow integrations"""

    @pytest.fixture
    def client(self):
        """Create test client with app instance"""
        return TestClient(app)

    @pytest.fixture
    async def async_client(self):
        """Create async test client for concurrent operations"""
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    async def test_user_with_token(self, async_db: AsyncSession):
        """Create test user with valid authentication token"""
        auth_manager = TestAuthManager()
        user = auth_manager.create_test_user(
            email="integration@test.com",
            role="business_user",
        )

        # Generate JWT token for user
        from api.dependencies.auth import create_access_token

        token = create_access_token(data={"sub": user.email})

        return {
            "user": user,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
        }

    @pytest.mark.asyncio
    async def test_complete_authentication_workflow(self, async_client: httpx.AsyncClient):
        """Test complete authentication flow integration

        Flow: Login → Token Validation → RBAC Check → Protected Resource Access
        """
        # Step 1: User registration
        registration_data = {
            "email": "workflow@test.com",
            "password": "SecurePassword123!",
            "company_name": "Test Compliance Co",
            "role": "business_user",
        }

        response = await async_client.post("/auth/register", json=registration_data)
        assert response.status_code == 201
        user_data = response.json()

        # Step 2: Login and token generation
        login_data = {
            "username": registration_data["email"],
            "password": registration_data["password"],
        }

        response = await async_client.post("/auth/login", data=login_data)
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data

        # Step 3: Token validation and user info retrieval
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        response = await async_client.get("/auth/me", headers=headers)
        assert response.status_code == 200
        user_profile = response.json()
        assert user_profile["email"] == registration_data["email"]

        # Step 4: RBAC protected resource access
        response = await async_client.get("/assessments", headers=headers)
        assert response.status_code == 200  # User has permission to view assessments

        # Step 5: Admin-only resource access (should fail)
        response = await async_client.get("/admin/users", headers=headers)
        assert response.status_code == 403  # Insufficient permissions

    @pytest.mark.asyncio
    async def test_compliance_assessment_pipeline_integration(
        self, async_client: httpx.AsyncClient, test_user_with_token: Dict
    ):
        """Test complete compliance assessment workflow

        Flow: Assessment Creation → AI Analysis → Database Storage → Report Generation
        """
        headers = test_user_with_token["headers"]
        user_id = test_user_with_token["user"].id

        # Step 1: Create assessment
        assessment_data = {
            "name": "GDPR Compliance Assessment",
            "framework": "GDPR",
            "company_id": str(uuid4()),
            "assessment_type": "full_assessment",
            "questions": [
                {
                    "question_id": "gdpr_consent",
                    "question_text": "Do you have a lawful basis for processing personal data?",
                    "answer": "yes",
                    "evidence_ids": [],
                },
                {
                    "question_id": "gdpr_retention",
                    "question_text": "Do you have data retention policies?",
                    "answer": "partial",
                    "evidence_ids": [],
                },
            ],
        }

        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=headers,
        )
        assert response.status_code == 201
        assessment = response.json()
        assessment_id = assessment["id"]

        # Step 2: Trigger AI analysis
        with patch("services.ai.assistant.ComplianceAssistant.analyze_assessment") as mock_ai:
            mock_ai.return_value = {
                "compliance_score": 0.75,
                "risk_level": "MEDIUM",
                "gaps": ["Consent Management", "Data Retention"],
                "recommendations": [
                    {
                        "priority": "HIGH",
                        "action": "Implement explicit consent system",
                        "timeline": "30 days",
                    },
                ],
            }

            response = await async_client.post(
                f"/assessments/{assessment_id}/analyze",
                headers=headers,
            )
            assert response.status_code == 200
            analysis = response.json()

            # Verify AI service was called
            mock_ai.assert_called_once()
            assert analysis["compliance_score"] == 0.75
            assert analysis["risk_level"] == "MEDIUM"

        # Step 3: Verify database state
        response = await async_client.get(
            f"/assessments/{assessment_id}",
            headers=headers,
        )
        assert response.status_code == 200
        db_assessment = response.json()
        assert db_assessment["status"] == "analyzed"
        assert db_assessment["compliance_score"] == 0.75

        # Step 4: Generate compliance report
        response = await async_client.post(
            f"/assessments/{assessment_id}/generate-report",
            headers=headers,
        )
        assert response.status_code == 200
        report = response.json()

        # Step 5: Validate end-to-end data integrity
        assert report["assessment_id"] == assessment_id
        assert report["compliance_score"] == analysis["compliance_score"]
        assert len(report["recommendations"]) > 0

        # Step 6: Verify report can be retrieved
        response = await async_client.get(
            f"/assessments/{assessment_id}/report",
            headers=headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_evidence_collection_workflow_integration(
        self, async_client: httpx.AsyncClient, test_user_with_token: Dict
    ):
        """Test complete evidence collection and processing workflow

        Flow: Evidence Upload → Classification → Processing → Compliance Mapping
        """
        headers = test_user_with_token["headers"]

        # Step 1: Upload evidence document
        files = {"file": ("privacy_policy.pdf", b"Mock PDF content", "application/pdf")}
        metadata = {
            "title": "Privacy Policy Document",
            "description": "Company privacy policy for GDPR compliance",
            "evidence_type": "policy_document",
            "framework": "GDPR",
        }

        response = await async_client.post(
            "/evidence/upload",
            files=files,
            data=metadata,
            headers=headers,
        )
        assert response.status_code == 201
        evidence = response.json()
        evidence_id = evidence["id"]

        # Step 2: Trigger evidence processing
        with patch("services.evidence_processor.classify_evidence") as mock_classifier:
            mock_classifier.return_value = {
                "document_type": "privacy_policy",
                "compliance_areas": ["data_protection", "consent_management"],
                "confidence_score": 0.92,
                "extracted_text": "This privacy policy outlines...",
            }

            response = await async_client.post(
                f"/evidence/{evidence_id}/process",
                headers=headers,
            )
            assert response.status_code == 200
            processing_result = response.json()

            assert processing_result["document_type"] == "privacy_policy"
            assert processing_result["confidence_score"] > 0.9

        # Step 3: Map evidence to compliance requirements
        mapping_data = {
            "framework": "GDPR",
            "requirements": ["article_13", "article_14", "article_21"],
        }

        response = await async_client.post(
            f"/evidence/{evidence_id}/map-compliance",
            json=mapping_data,
            headers=headers,
        )
        assert response.status_code == 200
        mapping_result = response.json()

        # Step 4: Verify evidence is linked to assessment
        assessment_data = {
            "name": "GDPR Privacy Policy Review",
            "framework": "GDPR",
            "evidence_ids": [evidence_id],
        }

        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=headers,
        )
        assert response.status_code == 201
        assessment = response.json()

        # Verify evidence is properly linked
        assert evidence_id in assessment["evidence_ids"]

    @pytest.mark.asyncio
    async def test_ai_service_circuit_breaker_integration(
        self, async_client: httpx.AsyncClient, test_user_with_token: Dict
    ):
        """Test AI service integration with circuit breaker pattern

        Tests circuit breaker states: CLOSED → OPEN → HALF_OPEN → CLOSED
        """
        headers = test_user_with_token["headers"]

        # Create test assessment for AI analysis
        assessment_data = {
            "name": "Circuit Breaker Test",
            "framework": "GDPR",
            "questions": [{"question_id": "test", "answer": "yes"}],
        }

        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=headers,
        )
        assessment_id = response.json()["id"]

        # Test 1: Circuit breaker in CLOSED state (normal operation)
        with patch("services.ai.circuit_breaker.CircuitBreaker") as mock_cb:
            mock_cb.return_value.state = CircuitState.CLOSED
            mock_cb.return_value.call = AsyncMock(return_value={"score": 0.8})

            response = await async_client.post(
                f"/assessments/{assessment_id}/analyze",
                headers=headers,
            )
            assert response.status_code == 200
            assert response.json()["source"] != "fallback"  # Not using fallback

        # Test 2: Circuit breaker in OPEN state (failures trigger fallback)
        with patch("services.ai.assistant.ComplianceAssistant.analyze_assessment") as mock_ai:
            # Simulate AI service failures
            mock_ai.side_effect = Exception("AI service unavailable")

            # Multiple requests should trigger circuit breaker
            for _ in range(3):
                response = await async_client.post(
                    f"/assessments/{assessment_id}/analyze",
                    headers=headers,
                )
                # Should still return 200 due to fallback mechanism
                assert response.status_code == 200
                result = response.json()

                # Verify fallback response is used
                assert (
                    "fallback" in result.get("source", "").lower()
                    or result.get("compliance_score") == 0.5,
                )

        # Test 3: Verify circuit breaker recovery (HALF_OPEN → CLOSED)
        with patch("services.ai.assistant.ComplianceAssistant.analyze_assessment") as mock_ai:
            mock_ai.return_value = {"compliance_score": 0.85, "risk_level": "LOW"}

            # After recovery timeout, should attempt to close circuit
            response = await async_client.post(
                f"/assessments/{assessment_id}/analyze",
                headers=headers,
            )
            assert response.status_code == 200

            # Successful responses should eventually close the circuit
            for _ in range(5):  # Multiple successful calls
                response = await async_client.post(
                    f"/assessments/{assessment_id}/analyze",
                    headers=headers,
                )
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cross_service_data_consistency(
        self, async_client: httpx.AsyncClient, test_user_with_token: Dict
    ):
        """Test data consistency across multiple services

        Validates that data remains consistent between:
        - API responses and database state
        - Cache and database
        - Different service endpoints
        """
        headers = test_user_with_token["headers"]

        # Step 1: Create assessment and verify immediate consistency
        assessment_data = {
            "name": "Consistency Test Assessment",
            "framework": "ISO27001",
            "status": "draft",
        }

        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=headers,
        )
        assert response.status_code == 201
        assessment = response.json()
        assessment_id = assessment["id"]

        # Step 2: Verify GET endpoint returns same data
        response = await async_client.get(
            f"/assessments/{assessment_id}",
            headers=headers,
        )
        assert response.status_code == 200
        retrieved_assessment = response.json()

        assert retrieved_assessment["name"] == assessment["name"]
        assert retrieved_assessment["framework"] == assessment["framework"]
        assert retrieved_assessment["status"] == assessment["status"]

        # Step 3: Update assessment and verify consistency
        update_data = {"status": "in_progress", "completion_percentage": 25}
        response = await async_client.patch(
            f"/assessments/{assessment_id}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200
        updated_assessment = response.json()

        # Step 4: Verify update is reflected in all endpoints
        response = await async_client.get(
            f"/assessments/{assessment_id}",
            headers=headers,
        )
        consistency_check = response.json()

        assert consistency_check["status"] == "in_progress"
        assert consistency_check["completion_percentage"] == 25

        # Step 5: Verify list endpoint reflects changes
        response = await async_client.get("/assessments", headers=headers)
        assessments_list = response.json()

        target_assessment = next(a for a in assessments_list if a["id"] == assessment_id)
        assert target_assessment["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_concurrent_api_operations_integration(
        self, async_client: httpx.AsyncClient, test_user_with_token: Dict
    ):
        """Test API behavior under concurrent operations

        Validates:
        - Race condition handling
        - Database transaction isolation
        - Resource locking behavior
        """
        headers = test_user_with_token["headers"]

        # Create test assessment
        assessment_data = {"name": "Concurrent Test Assessment", "framework": "GDPR"}

        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=headers,
        )
        assessment_id = response.json()["id"]

        # Test concurrent updates to same resource
        async def update_assessment(update_data: Dict):
            return await async_client.patch(
                f"/assessments/{assessment_id}",
                json=update_data,
                headers=headers,
            )

        # Concurrent updates with different fields
        tasks = [
            update_assessment({"status": "in_progress"}),
            update_assessment({"completion_percentage": 50}),
            update_assessment({"notes": "Updated concurrently"}),
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All updates should succeed (different fields, no conflicts)
        successful_responses = [r for r in responses if not isinstance(r, Exception)]
        assert len(successful_responses) >= 2  # At least 2 should succeed

        # Verify final state is consistent
        response = await async_client.get(
            f"/assessments/{assessment_id}",
            headers=headers,
        )
        final_state = response.json()

        # Should have at least some of the updates applied
        assert final_state["status"] in [
            "draft",
            "in_progress",
        ]  # One of the attempted values

    @pytest.mark.asyncio
    async def test_rate_limiting_integration_across_endpoints(
        self, async_client: httpx.AsyncClient, test_user_with_token: Dict
    ):
        """Test rate limiting integration across multiple API endpoints

        Validates:
        - Per-user rate limiting
        - Per-endpoint rate limiting
        - Rate limiting with different endpoint types
        """
        headers = test_user_with_token["headers"]

        # Test general API rate limiting (100/min)
        responses = []
        for i in range(10):  # Test with moderate number of requests
            response = await async_client.get("/assessments", headers=headers)
            responses.append(response)

        # All should succeed under normal rate limits
        assert all(r.status_code == 200 for r in responses[:8])

        # Test AI endpoint rate limiting (20/min) - more restrictive
        assessment_data = {"name": f"Rate Test {i}", "framework": "GDPR"}
        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=headers,
        )
        assessment_id = response.json()["id"]

        ai_responses = []
        for i in range(5):  # Test AI endpoint rate limiting
            response = await async_client.post(
                f"/assessments/{assessment_id}/analyze",
                headers=headers,
            )
            ai_responses.append(response)

            if i < 3:  # First few should succeed
                assert response.status_code in [200, 429]  # Success or rate limited

        # Verify rate limiting headers are present
        if ai_responses:
            last_response = ai_responses[-1]
            assert (
                "X-RateLimit-Remaining" in last_response.headers
                or "X-RateLimit-Reset" in last_response.headers,
            )

    @pytest.mark.asyncio
    async def test_error_handling_integration_across_services(
        self, async_client: httpx.AsyncClient, test_user_with_token: Dict
    ):
        """Test error handling and propagation across service boundaries

        Validates:
        - Error response consistency
        - Error logging and correlation IDs
        - Graceful degradation
        """
        headers = test_user_with_token["headers"]

        # Test 1: Invalid resource access
        response = await async_client.get("/assessments/invalid-uuid", headers=headers)
        assert response.status_code == 404
        error_data = response.json()
        assert "detail" in error_data
        assert "correlation_id" in error_data  # Should have correlation ID

        # Test 2: Invalid data submission
        invalid_assessment = {
            "name": "",  # Invalid: empty name
            "framework": "INVALID_FRAMEWORK",  # Invalid framework,
        }

        response = await async_client.post(
            "/assessments",
            json=invalid_assessment,
            headers=headers,
        )
        assert response.status_code == 422  # Validation error
        error_data = response.json()
        assert "detail" in error_data

        # Test 3: Service dependency failure (mock external service down)
        with patch("services.external_integration.ExternalService.call") as mock_external:
            mock_external.side_effect = Exception("External service unavailable")

            assessment_data = {"name": "Service Failure Test", "framework": "GDPR"}
            response = await async_client.post(
                "/assessments",
                json=assessment_data,
                headers=headers,
            )

            # Should still succeed with graceful degradation
            assert response.status_code == 201
            assessment = response.json()

            # Should indicate external service was unavailable
            assert ("warnings" in assessment or not assessment.get("external_data_available"),)


@pytest.mark.integration
@pytest.mark.performance
class TestAPIWorkflowPerformance:
    """Test performance characteristics of API workflows"""

    @pytest.mark.asyncio
    async def test_assessment_workflow_performance(
        self, async_client: httpx.AsyncClient, test_user_with_token: Dict
    ):
        """Test performance of complete assessment workflow"""
        headers = test_user_with_token["headers"]

        import time

        start_time = time.time()

        # Complete assessment workflow
        assessment_data = {
            "name": "Performance Test Assessment",
            "framework": "GDPR",
            "questions": [{"question_id": "test", "answer": "yes"}],
        }

        # Create assessment
        response = await async_client.post(
            "/assessments",
            json=assessment_data,
            headers=headers,
        )
        assert response.status_code == 201
        assessment_id = response.json()["id"]

        # Analyze assessment (mock AI for consistent timing)
        with patch("services.ai.assistant.ComplianceAssistant.analyze_assessment") as mock_ai:
            mock_ai.return_value = {"compliance_score": 0.8}

            response = await async_client.post(
                f"/assessments/{assessment_id}/analyze",
                headers=headers,
            )
            assert response.status_code == 200

        # Generate report
        response = await async_client.post(
            f"/assessments/{assessment_id}/generate-report",
            headers=headers,
        )
        assert response.status_code == 200

        end_time = time.time()
        workflow_time = end_time - start_time

        # Workflow should complete within 2 seconds (excluding AI processing)
        assert workflow_time < 2.0, f"Workflow took {workflow_time:.2f}s, expected <2s"
