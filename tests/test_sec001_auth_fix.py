"""
Test suite for SEC-001 Authentication Middleware Security Fix
Verifies that the authentication bypass vulnerability is resolved
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import jwt
from datetime import datetime, timedelta, timezone

from middleware.jwt_auth_v2 import JWTAuthMiddlewareV2
from config.settings import settings

# Test secret for JWT generation
TEST_SECRET = "test-secret-key"
TEST_ALGORITHM = "HS256"


def generate_test_token(user_id: str = "test_user", expired: bool = False):
    """Generate a test JWT token"""
    exp_time = (
        datetime.now(timezone.utc) - timedelta(hours=1)
        if expired
        else datetime.now(timezone.utc) + timedelta(hours=1)
    )
    payload = {"sub": user_id, "type": "access", "exp": exp_time.timestamp()}
    return jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)


@pytest.fixture
def test_app():
    """Create test FastAPI app with JWT middleware v2"""
    app = FastAPI()

    # Add the secure JWT middleware v2
    middleware = JWTAuthMiddlewareV2(
        enable_strict_mode=True,
        enable_rate_limiting=False,  # Disable for testing
        enable_audit_logging=False,  # Disable for testing
        enable_performance_monitoring=False,
        test_mode=True,
    )

    @app.middleware("http")
    async def jwt_middleware(request, call_next):
        return await middleware(request, call_next)

    # Test endpoints
    @app.get("/api/v1/auth/login")
    async def login():
        return {"message": "Login endpoint (public)"}

    @app.get("/api/v1/users/profile")
    async def profile():
        return {"message": "Profile endpoint (protected)"}

    @app.get("/api/v1/assessments/create")
    async def create_assessment():
        return {"message": "Assessment endpoint (protected)"}

    @app.get("/api/v1/policies/generate")
    async def generate_policy():
        return {"message": "Policy endpoint (protected)"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/v1/admin/settings")
    async def admin_settings():
        return {"message": "Admin endpoint (high-value protected)"}

    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


class TestSEC001AuthenticationFix:
    """Test suite for SEC-001 authentication middleware security fix"""

    def test_public_endpoints_accessible_without_auth(self, client):
        """Test that public endpoints remain accessible without authentication"""
        public_endpoints = ["/health", "/api/v1/auth/login"]

        for endpoint in public_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Public endpoint {endpoint} should be accessible"

    def test_protected_endpoints_require_authentication(self, client):
        """Test that protected endpoints return 401 without authentication"""
        protected_endpoints = [
            "/api/v1/users/profile",
            "/api/v1/assessments/create",
            "/api/v1/policies/generate",
            "/api/v1/admin/settings",
        ]

        for endpoint in protected_endpoints:
            # Test without any authentication header
            response = client.get(endpoint)
            assert response.status_code == 401, f"Protected endpoint {endpoint} should require auth"
            assert "Authentication required" in response.json()["detail"]

    def test_protected_endpoints_reject_invalid_token(self, client):
        """Test that protected endpoints reject invalid tokens"""
        protected_endpoints = ["/api/v1/users/profile", "/api/v1/assessments/create"]

        invalid_token = "invalid.token.here"
        headers = {"Authorization": f"Bearer {invalid_token}"}

        for endpoint in protected_endpoints:
            response = client.get(endpoint, headers=headers)
            assert response.status_code == 401, f"Endpoint {endpoint} should reject invalid token"
            assert "Invalid or expired token" in response.json()["detail"]

    @patch("middleware.jwt_auth_v2.SECRET_KEY", TEST_SECRET)
    @patch("middleware.jwt_auth_v2.ALGORITHM", TEST_ALGORITHM)
    def test_protected_endpoints_accept_valid_token(self, client):
        """Test that protected endpoints accept valid tokens"""
        valid_token = generate_test_token("user123")
        headers = {"Authorization": f"Bearer {valid_token}"}

        protected_endpoints = [
            "/api/v1/users/profile",
            "/api/v1/assessments/create",
            "/api/v1/policies/generate",
        ]

        for endpoint in protected_endpoints:
            response = client.get(endpoint, headers=headers)
            assert response.status_code == 200, f"Endpoint {endpoint} should accept valid token"

    @patch("middleware.jwt_auth_v2.SECRET_KEY", TEST_SECRET)
    @patch("middleware.jwt_auth_v2.ALGORITHM", TEST_ALGORITHM)
    def test_expired_token_rejected(self, client):
        """Test that expired tokens are rejected"""
        expired_token = generate_test_token("user123", expired=True)
        headers = {"Authorization": f"Bearer {expired_token}"}

        response = client.get("/api/v1/users/profile", headers=headers)
        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]

    def test_missing_bearer_prefix_rejected(self, client):
        """Test that tokens without Bearer prefix are rejected"""
        token = generate_test_token("user123")
        headers = {"Authorization": token}  # Missing "Bearer " prefix

        response = client.get("/api/v1/users/profile", headers=headers)
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

    def test_no_bypass_for_undefined_routes(self, client):
        """Test that undefined/new routes also require authentication (no bypass)"""
        # These routes don't exist but should still require auth
        undefined_routes = [
            "/api/v1/new/endpoint",
            "/api/v1/future/feature",
            "/api/undefined/route",
        ]

        for route in undefined_routes:
            response = client.get(route)
            # Should get 401 (auth required) not 404 (not found) first
            assert response.status_code == 401, f"Undefined route {route} should require auth first"

    def test_security_headers_present(self, client):
        """Test that security headers are added to responses"""
        response = client.get("/health")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert response.headers.get("X-Auth-Version") == "v2"

    @patch("middleware.jwt_auth_v2.SECRET_KEY", TEST_SECRET)
    @patch("middleware.jwt_auth_v2.ALGORITHM", TEST_ALGORITHM)
    def test_token_expiry_warning_header(self, client):
        """Test that expiring tokens get warning headers"""
        # Token expires in 4 minutes (under 5 minute threshold)
        exp_time = datetime.now(timezone.utc) + timedelta(minutes=4)
        payload = {"sub": "test_user", "type": "access", "exp": exp_time.timestamp()}
        token = jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/v1/users/profile", headers=headers)
        assert response.status_code == 200
        assert "X-Token-Expires-In" in response.headers
        assert "X-Token-Refresh-Recommended" in response.headers
        assert response.headers["X-Token-Refresh-Recommended"] == "true"


class TestVulnerabilityScenarios:
    """Test specific vulnerability scenarios from SEC-001"""

    def test_no_path_prefix_bypass(self, client):
        """Test that there's no bypass based on path prefixes"""
        # The old vulnerability allowed bypass for paths not starting with /api/protected
        bypass_attempts = [
            "/users/sensitive-data",
            "/admin/config",
            "/internal/api/data",
            "/../../etc/passwd",  # Path traversal attempt
        ]

        for path in bypass_attempts:
            response = client.get(path)
            assert response.status_code == 401, f"Path {path} should not bypass authentication"

    def test_high_value_endpoints_properly_protected(self, client):
        """Test that high-value endpoints are properly protected"""
        high_value_endpoints = [
            "/api/v1/admin/settings",
        ]

        for endpoint in high_value_endpoints:
            # Without auth
            response = client.get(endpoint)
            assert response.status_code == 401

            # With invalid token
            response = client.get(endpoint, headers={"Authorization": "Bearer invalid"})
            assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
