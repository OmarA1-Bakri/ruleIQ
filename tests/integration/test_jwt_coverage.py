"""
Integration tests for JWT coverage across all API endpoints
Part of SEC-005: Complete JWT Coverage Extension

These tests verify that all protected routes require valid JWT authentication.
"""

import pytest
import asyncio
from httpx import AsyncClient
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import jwt

from main import app
from config.settings import settings
from api.dependencies.auth import SECRET_KEY, ALGORITHM


class TestJWTCoverage:
    """Test JWT authentication coverage across all API endpoints"""

    # Routes that should be publicly accessible without authentication
    PUBLIC_ROUTES = [
        ("GET", "/"),
        ("GET", "/health"),
        ("GET", "/docs"),
        ("GET", "/redoc"),
        ("GET", "/openapi.json"),
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/register"),
        ("POST", "/api/v1/auth/token"),
        ("POST", "/api/v1/auth/refresh"),
        ("POST", "/api/v1/auth/forgot-password"),
        ("POST", "/api/v1/auth/reset-password"),
        ("GET", "/api/v1/freemium/leads"),
        ("POST", "/api/v1/freemium/sessions"),
        ("GET", "/metrics"),
    ]

    # Routes that MUST require authentication
    PROTECTED_ROUTES = [
        # Assessments
        ("GET", "/api/v1/assessments"),
        ("POST", "/api/v1/assessments"),
        ("GET", "/api/v1/assessments/{id}"),
        ("PUT", "/api/v1/assessments/{id}"),
        ("DELETE", "/api/v1/assessments/{id}"),
        ("POST", "/api/v1/assessments/quick"),
        # Compliance
        ("GET", "/api/v1/compliance/status"),
        ("GET", "/api/v1/compliance/requirements"),
        ("POST", "/api/v1/compliance/check"),
        ("GET", "/api/v1/compliance/report"),
        # Evidence
        ("GET", "/api/v1/evidence"),
        ("POST", "/api/v1/evidence"),
        ("GET", "/api/v1/evidence/{id}"),
        ("PUT", "/api/v1/evidence/{id}"),
        ("DELETE", "/api/v1/evidence/{id}"),
        ("POST", "/api/v1/evidence/bulk"),
        ("GET", "/api/v1/evidence/search"),
        # Policies
        ("GET", "/api/v1/policies"),
        ("POST", "/api/v1/policies/generate"),
        ("GET", "/api/v1/policies/{id}"),
        ("PATCH", "/api/v1/policies/{id}/status"),
        ("DELETE", "/api/v1/policies/{id}"),
        # Users
        ("GET", "/api/v1/users/profile"),
        ("PUT", "/api/v1/users/profile"),
        ("GET", "/api/v1/users/me"),
        ("DELETE", "/api/v1/users/me"),
        # Business Profiles
        ("GET", "/api/v1/business-profiles"),
        ("POST", "/api/v1/business-profiles"),
        ("GET", "/api/v1/business-profiles/{id}"),
        ("PUT", "/api/v1/business-profiles/{id}"),
        # Admin endpoints (critical)
        ("GET", "/api/v1/admin/users"),
        ("GET", "/api/v1/admin/metrics"),
        ("POST", "/api/v1/admin/audit"),
        ("GET", "/api/v1/admin/logs"),
        # Reports
        ("GET", "/api/v1/reports"),
        ("POST", "/api/v1/reports/generate"),
        ("GET", "/api/v1/reports/{id}"),
        # Dashboard
        ("GET", "/api/v1/dashboard"),
        ("GET", "/api/v1/dashboard/metrics"),
        ("GET", "/api/v1/dashboard/analytics"),
        # Payments
        ("GET", "/api/v1/payments"),
        ("POST", "/api/v1/payments/create"),
        ("GET", "/api/v1/payments/history"),
        # API Keys
        ("GET", "/api/v1/api-keys"),
        ("POST", "/api/v1/api-keys"),
        ("DELETE", "/api/v1/api-keys/{id}"),
        # Secrets Vault
        ("GET", "/api/v1/secrets"),
        ("POST", "/api/v1/secrets"),
        ("DELETE", "/api/v1/secrets/{id}"),
    ]

    @pytest.fixture
    async def client(self):
        """Create an async test client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    def valid_token(self):
        """Generate a valid JWT token for testing"""
        payload = {
            "sub": "test-user-id",
            "email": "test@example.com",
            "type": "access",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @pytest.fixture
    def expired_token(self):
        """Generate an expired JWT token for testing"""
        payload = {
            "sub": "test-user-id",
            "email": "test@example.com",
            "type": "access",
            "exp": datetime.utcnow() - timedelta(hours=1),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @pytest.fixture
    def invalid_token(self):
        """Generate an invalid JWT token"""
        return "invalid.jwt.token"

    @pytest.mark.asyncio
    async def test_public_routes_accessible_without_auth(self, client: AsyncClient):
        """Test that public routes are accessible without authentication"""
        for method, path in self.PUBLIC_ROUTES:
            # Skip paths with parameters
            if "{" in path:
                continue

            if method == "GET":
                response = await client.get(path)
            elif method == "POST":
                response = await client.post(path, json={})
            else:
                continue

            # Public routes should not return 401
            assert response.status_code != 401, f"Public route {method} {path} returned 401"

    @pytest.mark.asyncio
    async def test_protected_routes_require_auth(self, client: AsyncClient):
        """Test that protected routes require authentication"""
        for method, path in self.PROTECTED_ROUTES:
            # Replace path parameters with test values
            test_path = path.replace("{id}", "test-id")

            # Make request without authentication
            if method == "GET":
                response = await client.get(test_path)
            elif method == "POST":
                response = await client.post(test_path, json={})
            elif method == "PUT":
                response = await client.put(test_path, json={})
            elif method == "PATCH":
                response = await client.patch(test_path, json={})
            elif method == "DELETE":
                response = await client.delete(test_path)
            else:
                continue

            # Protected routes MUST return 401 without auth
            assert response.status_code == 401, (
                f"Protected route {method} {test_path} did not return 401 without auth (got {response.status_code})"
            )

    @pytest.mark.asyncio
    async def test_protected_routes_reject_expired_token(
        self, client: AsyncClient, expired_token: str
    ):
        """Test that protected routes reject expired tokens"""
        headers = {"Authorization": f"Bearer {expired_token}"}

        # Test a sample of protected routes
        test_routes = [
            ("GET", "/api/v1/assessments"),
            ("GET", "/api/v1/compliance/status"),
            ("GET", "/api/v1/evidence"),
            ("GET", "/api/v1/policies"),
        ]

        for method, path in test_routes:
            response = await client.get(path, headers=headers)

            # Should reject expired token
            assert response.status_code == 401, f"Route {method} {path} accepted expired token"

    @pytest.mark.asyncio
    async def test_protected_routes_reject_invalid_token(
        self, client: AsyncClient, invalid_token: str
    ):
        """Test that protected routes reject invalid tokens"""
        headers = {"Authorization": f"Bearer {invalid_token}"}

        # Test a sample of protected routes
        test_routes = [
            ("GET", "/api/v1/assessments"),
            ("GET", "/api/v1/compliance/status"),
            ("GET", "/api/v1/evidence"),
            ("GET", "/api/v1/policies"),
        ]

        for method, path in test_routes:
            response = await client.get(path, headers=headers)

            # Should reject invalid token
            assert response.status_code == 401, f"Route {method} {path} accepted invalid token"

    @pytest.mark.asyncio
    async def test_auth_header_format_validation(self, client: AsyncClient, valid_token: str):
        """Test that various malformed auth headers are rejected"""
        test_cases = [
            ("", "Empty header"),
            ("Bearer", "Missing token"),
            (f"Basic {valid_token}", "Wrong scheme"),
            (f"bearer {valid_token}", "Lowercase scheme"),
            (f"Bearer  {valid_token}", "Extra space"),
            (valid_token, "No scheme"),
        ]

        for auth_header, description in test_cases:
            headers = {"Authorization": auth_header} if auth_header else {}

            response = await client.get("/api/v1/assessments", headers=headers)

            assert response.status_code == 401, f"Malformed auth header accepted: {description}"

    @pytest.mark.asyncio
    async def test_concurrent_auth_requests(self, client: AsyncClient, valid_token: str):
        """Test that JWT middleware handles concurrent requests correctly"""
        headers = {"Authorization": f"Bearer {valid_token}"}

        # Make multiple concurrent requests
        tasks = []
        for _ in range(10):
            tasks.append(client.get("/api/v1/assessments", headers=headers))

        responses = await asyncio.gather(*tasks)

        # All should be processed correctly
        for response in responses:
            # Should either succeed or fail consistently
            assert response.status_code in [200, 401, 404], (
                f"Unexpected status code in concurrent request: {response.status_code}"
            )


class TestJWTMiddlewareFeatures:
    """Test specific JWT middleware features"""

    @pytest.mark.asyncio
    async def test_token_expiry_warning_header(self, client: AsyncClient):
        """Test that token expiry warning headers are added when appropriate"""
        # Create token expiring in 4 minutes (under 5 minute threshold)
        payload = {
            "sub": "test-user-id",
            "email": "test@example.com",
            "type": "access",
            "exp": datetime.utcnow() + timedelta(minutes=4),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/assessments", headers=headers)

        # Should have expiry warning headers
        assert "X-Token-Expires-In" in response.headers
        assert "X-Token-Refresh-Recommended" in response.headers
        assert response.headers["X-Token-Refresh-Recommended"] == "true"

    @pytest.mark.asyncio
    async def test_security_headers_present(self, client: AsyncClient, valid_token: str):
        """Test that security headers are added to responses"""
        headers = {"Authorization": f"Bearer {valid_token}"}

        response = await client.get("/api/v1/assessments", headers=headers)

        # Check for security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

        assert "X-Auth-Version" in response.headers
        assert response.headers["X-Auth-Version"] == "v2"

    @pytest.mark.asyncio
    async def test_rate_limiting_on_auth_endpoints(self, client: AsyncClient):
        """Test that rate limiting is applied to authentication endpoints"""
        # Make many rapid requests to auth endpoint
        for i in range(settings.auth_rate_limit_per_minute + 5):
            response = await client.post(
                "/api/v1/auth/login", json={"email": f"test{i}@example.com", "password": "wrong"}
            )

            # After rate limit, should get 429
            if i >= settings.auth_rate_limit_per_minute:
                assert response.status_code == 429, "Rate limiting not applied to auth endpoint"
                assert "retry_after" in response.json()


class TestJWTCoverageMetrics:
    """Test JWT coverage metrics and monitoring"""

    @pytest.mark.asyncio
    async def test_authentication_success_metrics(self, client: AsyncClient, valid_token: str):
        """Test that successful authentications are tracked"""
        headers = {"Authorization": f"Bearer {valid_token}"}

        # Make authenticated request
        response = await client.get("/api/v1/assessments", headers=headers)

        # Check metrics endpoint (if available)
        metrics_response = await client.get("/metrics")
        if metrics_response.status_code == 200:
            metrics_text = metrics_response.text
            # Should track authentication success
            assert "authentication_success" in metrics_text or "auth_success" in metrics_text

    @pytest.mark.asyncio
    async def test_authentication_failure_metrics(self, client: AsyncClient, invalid_token: str):
        """Test that authentication failures are tracked"""
        headers = {"Authorization": f"Bearer {invalid_token}"}

        # Make request with invalid token
        response = await client.get("/api/v1/assessments", headers=headers)
        assert response.status_code == 401

        # Check metrics endpoint (if available)
        metrics_response = await client.get("/metrics")
        if metrics_response.status_code == 200:
            metrics_text = metrics_response.text
            # Should track authentication failures
            assert "authentication_failure" in metrics_text or "auth_failure" in metrics_text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
