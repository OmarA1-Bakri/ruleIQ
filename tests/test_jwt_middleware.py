"""
Comprehensive test suite for JWT Authentication Middleware.

Tests all authentication flows and security requirements to ensure no bypass vulnerabilities.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from jose import jwt
import time

from middleware.jwt_auth import JWTAuthMiddleware
from api.dependencies.auth import SECRET_KEY, ALGORITHM


class TestJWTAuthMiddleware:
    """Test suite for JWT Authentication Middleware."""

    @pytest.fixture
    def middleware(self):
        """Create a middleware instance for testing."""
        return JWTAuthMiddleware(
            enable_strict_mode=True,
            enable_rate_limiting=True,
            enable_audit_logging=False,  # Disable for tests
        )

    @pytest.fixture
    def valid_token(self):
        """Generate a valid JWT token."""
        payload = {
            "sub": "test-user-id",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @pytest.fixture
    def expired_token(self):
        """Generate an expired JWT token."""
        payload = {
            "sub": "test-user-id",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @pytest.fixture
    def refresh_token(self):
        """Generate a refresh token (wrong type for access)."""
        payload = {
            "sub": "test-user-id",
            "type": "refresh",
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/v1/users/profile"
        request.method = "GET"
        request.headers = {}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()
        return request

    @pytest.fixture
    def call_next(self):
        """Create a mock call_next function."""

        async def mock_call_next(request):
            response = Mock(spec=Response)
            response.headers = {}
            return response

        return mock_call_next

    # Test 1: Public paths should be accessible without authentication
    @pytest.mark.asyncio
    async def test_public_paths_accessible_without_auth(self, middleware, mock_request, call_next):
        """Ensure public paths don't require authentication."""
        public_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/api/v1/health",
            "/",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/token",
            "/api/v1/freemium/assess",
        ]

        for path in public_paths:
            mock_request.url.path = path
            mock_request.headers = {}  # No Authorization header

            response = await middleware(mock_request, call_next)

            # Should not return 401
            assert not isinstance(response, JSONResponse) or response.status_code != 401, (
                f"Public path {path} should be accessible without auth"
            )

    # Test 2: Protected paths should require authentication
    @pytest.mark.asyncio
    async def test_protected_paths_require_auth(self, middleware, mock_request, call_next):
        """Ensure protected paths return 401 without valid token."""
        protected_paths = [
            "/api/v1/users/profile",
            "/api/v1/admin/settings",
            "/api/v1/payments/process",
            "/api/v1/assessments/create",
            "/api/v1/policies/generate",
            "/api/v1/ai/analyze",
            "/api/dashboard",
            "/api/v1/dashboard/stats",
            "/api/v1/monitoring/metrics",
            "/api/v1/security/audit",
        ]

        for path in protected_paths:
            mock_request.url.path = path
            mock_request.headers = {}  # No Authorization header

            response = await middleware(mock_request, call_next)

            # Should return 401
            assert isinstance(response, JSONResponse), (
                f"Protected path {path} should return JSONResponse"
            )
            assert response.status_code == 401, (
                f"Protected path {path} should return 401 without auth"
            )

            # Check for WWW-Authenticate header
            assert response.headers.get("WWW-Authenticate") == "Bearer", (
                f"Protected path {path} should include WWW-Authenticate header"
            )

    # Test 3: Valid token should grant access
    @pytest.mark.asyncio
    async def test_valid_token_grants_access(
        self, middleware, mock_request, call_next, valid_token
    ):
        """Ensure valid JWT token grants access to protected routes."""
        mock_request.url.path = "/api/v1/users/profile"
        mock_request.headers = {"Authorization": f"Bearer {valid_token}"}

        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=False):
            response = await middleware(mock_request, call_next)

            # Should not return 401
            assert not isinstance(response, JSONResponse) or response.status_code != 401

            # Should set user info in request state
            assert hasattr(mock_request.state, "user_id")
            assert mock_request.state.user_id == "test-user-id"
            assert hasattr(mock_request.state, "is_authenticated")
            assert mock_request.state.is_authenticated is True

    # Test 4: Expired token should be rejected
    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, middleware, mock_request, call_next, expired_token):
        """Ensure expired tokens are rejected."""
        mock_request.url.path = "/api/v1/users/profile"
        mock_request.headers = {"Authorization": f"Bearer {expired_token}"}

        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=False):
            response = await middleware(mock_request, call_next)

            # Should return 401
            assert isinstance(response, JSONResponse)
            assert response.status_code == 401
            assert "Invalid or expired token" in response.body.decode()

    # Test 5: Blacklisted token should be rejected
    @pytest.mark.asyncio
    async def test_blacklisted_token_rejected(
        self, middleware, mock_request, call_next, valid_token
    ):
        """Ensure blacklisted tokens are rejected."""
        mock_request.url.path = "/api/v1/users/profile"
        mock_request.headers = {"Authorization": f"Bearer {valid_token}"}

        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=True):
            response = await middleware(mock_request, call_next)

            # Should return 401
            assert isinstance(response, JSONResponse)
            assert response.status_code == 401

    # Test 6: Wrong token type should be rejected
    @pytest.mark.asyncio
    async def test_wrong_token_type_rejected(
        self, middleware, mock_request, call_next, refresh_token
    ):
        """Ensure refresh tokens are rejected for access endpoints."""
        mock_request.url.path = "/api/v1/users/profile"
        mock_request.headers = {"Authorization": f"Bearer {refresh_token}"}

        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=False):
            response = await middleware(mock_request, call_next)

            # Should return 401
            assert isinstance(response, JSONResponse)
            assert response.status_code == 401

    # Test 7: Invalid token format should be rejected
    @pytest.mark.asyncio
    async def test_invalid_token_format_rejected(self, middleware, mock_request, call_next):
        """Ensure invalid token formats are rejected."""
        invalid_tokens = [
            "invalid-token",
            "Bearer",
            "Bearer ",
            "Basic dGVzdDp0ZXN0",  # Basic auth instead of Bearer
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature",
        ]

        mock_request.url.path = "/api/v1/users/profile"

        for token in invalid_tokens:
            mock_request.headers = {"Authorization": token}

            response = await middleware(mock_request, call_next)

            # Should return 401
            assert isinstance(response, JSONResponse), (
                f"Invalid token format '{token}' should be rejected"
            )
            assert response.status_code == 401

    # Test 8: Rate limiting should work
    @pytest.mark.asyncio
    async def test_rate_limiting(self, middleware, mock_request, call_next):
        """Ensure rate limiting prevents brute force attacks."""
        mock_request.url.path = "/api/v1/auth/login"
        mock_request.headers = {"Authorization": "Bearer invalid-token"}

        # Set a low rate limit for testing
        middleware.max_auth_attempts = 3

        # Make multiple requests
        for i in range(5):
            response = await middleware(mock_request, call_next)

            if i < 3:
                # First 3 requests should pass through (though may fail auth)
                assert response.status_code != 429
            else:
                # Subsequent requests should be rate limited
                assert isinstance(response, JSONResponse)
                assert response.status_code == 429
                assert "Too many authentication attempts" in response.body.decode()

    # Test 9: Token about to expire should include warning headers
    @pytest.mark.asyncio
    async def test_expiring_token_warning(self, middleware, mock_request, call_next):
        """Ensure tokens about to expire include warning headers."""
        # Create token expiring in 4 minutes
        payload = {
            "sub": "test-user-id",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=4),
            "iat": datetime.now(timezone.utc),
        }
        expiring_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        mock_request.url.path = "/api/v1/users/profile"
        mock_request.headers = {"Authorization": f"Bearer {expiring_token}"}

        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=False):
            response = await middleware(mock_request, call_next)

            # Should include expiry warning headers
            assert "X-Token-Expires-In" in response.headers
            assert "X-Token-Refresh-Recommended" in response.headers
            assert response.headers["X-Token-Refresh-Recommended"] == "true"

    # Test 10: Critical paths should always require auth even without strict mode
    @pytest.mark.asyncio
    async def test_critical_paths_always_require_auth(self):
        """Ensure critical paths require auth even when strict mode is disabled."""
        # Create middleware without strict mode
        middleware = JWTAuthMiddleware(
            enable_strict_mode=False, enable_rate_limiting=False, enable_audit_logging=False
        )

        critical_paths = [
            "/api/v1/admin/users",
            "/api/v1/payments/process",
            "/api/v1/api-keys/create",
            "/api/v1/security/audit-log",
        ]

        mock_request = Mock(spec=Request)
        mock_request.url = Mock()
        mock_request.method = "GET"
        mock_request.headers = {}  # No auth
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"

        async def mock_call_next(request):
            response = Mock(spec=Response)
            response.headers = {}
            return response

        for path in critical_paths:
            mock_request.url.path = path

            response = await middleware(mock_request, mock_call_next)

            # Should return 401 even without strict mode
            assert isinstance(response, JSONResponse), (
                f"Critical path {path} should require auth even without strict mode"
            )
            assert response.status_code == 401

    # Test 11: Security headers should be added to responses
    @pytest.mark.asyncio
    async def test_security_headers_added(self, middleware, mock_request, call_next, valid_token):
        """Ensure security headers are added to responses."""
        mock_request.url.path = "/api/v1/users/profile"
        mock_request.headers = {"Authorization": f"Bearer {valid_token}"}

        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=False):
            response = await middleware(mock_request, call_next)

            # Should include security headers
            assert response.headers.get("X-Content-Type-Options") == "nosniff"
            assert response.headers.get("X-Frame-Options") == "DENY"

    # Test 12: Missing Authorization header should return proper error
    @pytest.mark.asyncio
    async def test_missing_authorization_header(self, middleware, mock_request, call_next):
        """Ensure missing Authorization header returns proper error."""
        mock_request.url.path = "/api/v1/users/profile"
        mock_request.headers = {}  # No Authorization header

        response = await middleware(mock_request, call_next)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

        # Check response body
        assert b"Authentication required" in response.body

    # Test 13: Tampered token should be rejected
    @pytest.mark.asyncio
    async def test_tampered_token_rejected(self, middleware, mock_request, call_next, valid_token):
        """Ensure tampered tokens are rejected."""
        # Tamper with the token signature
        tampered_token = valid_token[:-10] + "tampered123"

        mock_request.url.path = "/api/v1/users/profile"
        mock_request.headers = {"Authorization": f"Bearer {tampered_token}"}

        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=False):
            response = await middleware(mock_request, call_next)

            # Should return 401
            assert isinstance(response, JSONResponse)
            assert response.status_code == 401

    # Test 14: Token with invalid signature should be rejected
    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self, middleware, mock_request, call_next):
        """Ensure tokens with invalid signatures are rejected."""
        # Create token with different secret
        payload = {
            "sub": "test-user-id",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        invalid_token = jwt.encode(payload, "wrong-secret-key", algorithm=ALGORITHM)

        mock_request.url.path = "/api/v1/users/profile"
        mock_request.headers = {"Authorization": f"Bearer {invalid_token}"}

        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=False):
            response = await middleware(mock_request, call_next)

            # Should return 401
            assert isinstance(response, JSONResponse)
            assert response.status_code == 401

    # Test 15: Ensure no bypass vulnerability exists
    @pytest.mark.asyncio
    async def test_no_bypass_vulnerability(self, middleware):
        """Comprehensive test to ensure no authentication bypass exists."""
        # Test various bypass attempts
        bypass_attempts = [
            # Try different header formats
            {"Authorization": "Bearer"},
            {"Authorization": "Bearer "},
            {"Authorization": ""},
            {"authorization": "Bearer valid_token"},  # Wrong case
            {"Auth": "Bearer valid_token"},  # Wrong header name
            # Try URL manipulation
            {"Authorization": None, "path": "/api/v1/users/../auth/login"},
            {"Authorization": None, "path": "/api/v1//users/profile"},
            {"Authorization": None, "path": "/api/v1/users/profile?auth=bypass"},
            # Try method override
            {"Authorization": None, "X-HTTP-Method-Override": "OPTIONS"},
            {"Authorization": None, "X-Original-Method": "GET"},
        ]

        mock_request = Mock(spec=Request)
        mock_request.url = Mock()
        mock_request.url.path = "/api/v1/users/profile"
        mock_request.method = "GET"
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"

        async def mock_call_next(request):
            # This should never be called for protected routes without auth
            raise AssertionError("Protected route accessed without authentication!")

        for attempt in bypass_attempts:
            mock_request.headers = {k: v for k, v in attempt.items() if k != "path"}
            if "path" in attempt:
                mock_request.url.path = attempt["path"]

            response = await middleware(mock_request, mock_call_next)

            # All bypass attempts should be rejected
            assert isinstance(response, JSONResponse), (
                f"Bypass attempt {attempt} should be rejected"
            )
            assert response.status_code == 401, f"Bypass attempt {attempt} should return 401"


class TestJWTMiddlewareIntegration:
    """Integration tests for JWT middleware with the application."""

    @pytest.mark.asyncio
    async def test_middleware_integration_with_fastapi(self):
        """Test middleware integration with FastAPI application."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        # Add the JWT middleware
        jwt_middleware = JWTAuthMiddleware(
            enable_strict_mode=True, enable_rate_limiting=True, enable_audit_logging=False
        )
        app.middleware("http")(jwt_middleware)

        # Add test routes
        @app.get("/public")
        async def public_route():
            return {"message": "public"}

        @app.get("/api/v1/protected")
        async def protected_route():
            return {"message": "protected"}

        # Create test client
        client = TestClient(app)

        # Test public route accessibility
        response = client.get("/public")
        assert response.status_code == 200

        # Test protected route requires auth
        response = client.get("/api/v1/protected")
        assert response.status_code == 401

        # Test with valid token
        payload = {
            "sub": "test-user-id",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        valid_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=False):
            response = client.get(
                "/api/v1/protected", headers={"Authorization": f"Bearer {valid_token}"}
            )
            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
