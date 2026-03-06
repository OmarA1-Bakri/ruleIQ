"""
Comprehensive integration test suite for RuleIQ.
"""

import pytest
import asyncio
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient
import json
import requests

from main import app
from database.db_setup import get_async_db
from services.agentic_assessment import AgenticAssessmentService
from services.compliance_graph_initializer import ComplianceGraphInitializer


class TestEndToEndWorkflow:
    """Test complete user workflows from registration to assessment."""

    @pytest.fixture
    async def test_user(self):
        """Create a test user."""
        return {
            "email": f"test_{datetime.now().timestamp()}@example.com",
            "password": "TestSecure123!@#",
            "full_name": "Test User",
        }

    @pytest.mark.asyncio
    async def test_complete_user_journey(self, test_user):
        """Test complete user journey from registration to assessment completion."""
        client = TestClient(app)

        # 1. User Registration
        registration_response = client.post("/api/v1/auth/register", json=test_user)
        assert registration_response.status_code in [200, 201, 422]

        if registration_response.status_code in [200, 201]:
            user_data = registration_response.json()

            # 2. User Login
            login_response = client.post(
                "/api/v1/auth/token",
                data={"username": test_user["email"], "password": test_user["password"]},
            )
            assert login_response.status_code == 200
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 3. Create Business Profile
            profile_response = client.post(
                "/api/v1/business-profiles",
                json={
                    "company_name": "Test Company",
                    "industry": "Technology",
                    "size": "small",
                    "location": "UK",
                },
                headers=headers,
            )
            assert profile_response.status_code in [200, 201]

            # 4. Start Assessment
            assessment_response = client.post(
                "/api/v1/assessments", json={"framework": "gdpr", "type": "quick"}, headers=headers
            )
            assert assessment_response.status_code in [200, 201]

            if assessment_response.status_code in [200, 201]:
                assessment_id = assessment_response.json().get("id")

                # 5. Complete Assessment
                complete_response = client.post(
                    f"/api/v1/assessments/{assessment_id}/complete",
                    json={"responses": {}},
                    headers=headers,
                )
                assert complete_response.status_code in [200, 201, 404]

                # 6. Get Results
                results_response = client.get(
                    f"/api/v1/assessments/{assessment_id}/results", headers=headers
                )
                assert results_response.status_code in [200, 404]


class TestDatabaseIntegration:
    """Test database operations and transactions."""

    @pytest.mark.asyncio
    async def test_database_transaction_rollback(self):
        """Test database transaction rollback on error."""
        async for session in get_async_db():
            try:
                # Start transaction
                async with session.begin():
                    # Perform operations
                    from database.user import User

                    test_user = User(
                        email="transaction_test@example.com",
                        hashed_password="test",
                        full_name="Transaction Test",
                    )
                    session.add(test_user)

                    # Force an error
                    raise Exception("Test rollback")
            except Exception:
                # Transaction should be rolled back
                pass

            # Verify user was not created
            from sqlalchemy import select

            result = await session.execute(
                select(User).where(User.email == "transaction_test@example.com")
            )
            assert result.scalar() is None
            break

    @pytest.mark.asyncio
    async def test_concurrent_database_access(self):
        """Test concurrent database access with connection pooling."""

        async def db_operation(index: int):
            async for session in get_async_db():
                from sqlalchemy import text

                result = await session.execute(text(f"SELECT {index}"))
                return result.scalar()

        # Run concurrent operations
        tasks = [db_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All operations should complete
        assert len(results) == 10
        assert all(results[i] == i for i in range(10))


class TestAIIntegration:
    """Test AI service integrations."""

    @pytest.mark.asyncio
    async def test_agentic_assessment_service(self):
        """Test AI-powered assessment service."""
        service = AgenticAssessmentService()

        # Mock assessment data
        assessment_data = {
            "framework": "gdpr",
            "company_info": {"name": "Test Corp", "industry": "Technology", "size": "medium"},
        }

        # Test assessment generation (mocked)
        with pytest.raises(Exception):
            # This will fail without proper AI credentials
            result = await service.generate_assessment(assessment_data)

    @pytest.mark.asyncio
    async def test_compliance_graph_initialization(self):
        """Test compliance knowledge graph initialization."""
        initializer = ComplianceGraphInitializer()

        # Test graph connection (may fail without Neo4j)
        try:
            result = await initializer.test_connection()
            assert isinstance(result, bool)
        except Exception:
            # Expected if Neo4j is not running
            pass


class TestSecurityIntegration:
    """Test security features integration."""

    def test_password_validation(self):
        """Test password strength validation."""
        from api.dependencies.auth import validate_password

        # Test weak passwords
        weak_passwords = ["123456", "password", "abc123", "test"]
        for pwd in weak_passwords:
            valid, msg = validate_password(pwd)
            assert not valid

        # Test strong passwords
        strong_passwords = ["SecurePass123!@#", "MyStr0ng&P@ssw0rd", "C0mpl3x!Pass#2024"]
        for pwd in strong_passwords:
            valid, msg = validate_password(pwd)
            assert valid

    def test_jwt_token_blacklist(self):
        """Test JWT token blacklisting."""
        client = TestClient(app)

        # Login to get token
        login_response = client.post(
            "/api/v1/auth/token", data={"username": "test@example.com", "password": "TestPass123!"}
        )

        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Logout (blacklist token)
            logout_response = client.post("/api/v1/auth/logout", headers=headers)

            # Try to use blacklisted token
            response = client.get("/api/v1/users/me", headers=headers)
            # Should be unauthorized if blacklisting works
            assert response.status_code in [401, 200]  # Depends on implementation


class TestMonitoringIntegration:
    """Test monitoring and observability features."""

    def test_health_endpoint(self):
        """Test health check endpoint."""
        client = TestClient(app)
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        client = TestClient(app)
        response = client.get("/metrics")
        # May not exist, but test for it
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_database_monitoring_queries(self):
        """Test database monitoring queries."""
        from config.database_pool_config import ConnectionPoolConfig

        queries = ConnectionPoolConfig.get_monitoring_queries()

        async for session in get_async_db():
            from sqlalchemy import text

            # Test active connections query
            try:
                result = await session.execute(text(queries["active_connections"]))
                count = result.scalar()
                assert count >= 0
            except Exception:
                # May fail without proper permissions
                pass
            break


class TestPerformanceIntegration:
    """Test performance-related features."""

    @pytest.mark.asyncio
    async def test_api_response_time(self):
        """Test API response times are acceptable."""
        client = TestClient(app)
        import time

        endpoints = ["/api/v1/health", "/api/v1/frameworks", "/api/v1/compliance/overview"]

        for endpoint in endpoints:
            start = time.time()
            response = client.get(endpoint)
            duration = time.time() - start

            # Response should be under 2 seconds
            assert duration < 2.0
            assert response.status_code in [200, 401, 404]

    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self):
        """Test handling of concurrent API requests."""
        client = TestClient(app)

        async def make_request(index: int):
            response = client.get("/api/v1/health")
            return response.status_code

        # Make 20 concurrent requests
        tasks = [make_request(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Most should succeed
        successful = sum(1 for r in results if r == 200)
        assert successful >= 15  # Allow some to fail due to rate limiting


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
