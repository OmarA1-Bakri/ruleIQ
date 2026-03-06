"""
Comprehensive tests for JWT authentication implementation.

Tests cover:
- Token generation and validation
- Token blacklisting
- Protected route access
- Rate limiting
- Token refresh flow
- Security headers
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
from jose import jwt
from fastapi import HTTPException
from fastapi.testclient import TestClient

from config.settings import settings
from api.dependencies.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    SECRET_KEY,
    ALGORITHM,
)
from api.dependencies.token_blacklist import (
    EnhancedTokenBlacklist as TokenBlacklistService,
    blacklist_token,
    is_token_blacklisted,
)
from middleware.jwt_auth import JWTAuthMiddleware


class TestJWTTokenGeneration:
    """Test JWT token generation and validation."""

    def test_create_access_token(self):
        """Test access token creation with correct claims."""
        user_data = {"sub": "test-user-id", "email": "test@example.com"}
        token = create_access_token(user_data)

        # Decode and verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == "test-user-id"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_refresh_token(self):
        """Test refresh token creation with correct claims."""
        user_data = {"sub": "test-user-id"}
        token = create_refresh_token(user_data)

        # Decode and verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == "test-user-id"
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload

    def test_access_token_expiry(self):
        """Test that access tokens expire at the correct time."""
        user_data = {"sub": "test-user-id"}
        expires_delta = timedelta(minutes=1)
        token = create_access_token(user_data, expires_delta)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        current_time = datetime.now(timezone.utc)

        # Check expiry is approximately 1 minute from now
        time_diff = (exp_time - current_time).total_seconds()
        assert 55 < time_diff < 65  # Allow some margin

    def test_decode_expired_token(self):
        """Test that expired tokens are rejected."""
        user_data = {"sub": "test-user-id"}
        # Create token that expires immediately
        expires_delta = timedelta(seconds=-1)
        token = create_access_token(user_data, expires_delta)

        # Should raise exception for expired token
        with pytest.raises(Exception):  # NotAuthenticatedException
            decode_token(token)

    def test_decode_invalid_token(self):
        """Test that invalid tokens are rejected."""
        invalid_token = "invalid.token.here"

        with pytest.raises(Exception):
            decode_token(invalid_token)

    def test_decode_token_wrong_secret(self):
        """Test that tokens with wrong secret are rejected."""
        user_data = {"sub": "test-user-id"}
        wrong_secret = "wrong-secret-key"

        # Create token with wrong secret
        to_encode = user_data.copy()
        to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=30)
        to_encode["type"] = "access"
        wrong_token = jwt.encode(to_encode, wrong_secret, algorithm=ALGORITHM)

        with pytest.raises(Exception):
            decode_token(wrong_token)


@pytest.mark.asyncio
class TestTokenBlacklist:
    """Test token blacklisting functionality."""

    async def test_blacklist_token(self):
        """Test adding a token to blacklist."""
        service = TokenBlacklistService()
        service.redis_client = AsyncMock()
        service._initialized = True

        token = "test-token-123"
        result = await service.blacklist_token(token=token, reason="logout", user_id="user-123")

        assert result is True
        # Verify Redis operations were called
        service.redis_client.setex.assert_called_once()

    async def test_check_blacklisted_token(self):
        """Test checking if a token is blacklisted."""
        service = TokenBlacklistService()
        service.redis_client = AsyncMock()
        service._initialized = True

        # Mock Redis to return 1 (exists)
        service.redis_client.exists.return_value = 1

        token = "blacklisted-token"
        result = await service.is_token_blacklisted(token)

        assert result is True
        service.redis_client.exists.assert_called_once()

    async def test_check_non_blacklisted_token(self):
        """Test checking a token that is not blacklisted."""
        service = TokenBlacklistService()
        service.redis_client = AsyncMock()
        service._initialized = True

        # Mock Redis to return 0 (not exists)
        service.redis_client.exists.return_value = 0

        token = "valid-token"
        result = await service.is_token_blacklisted(token)

        assert result is False

    async def test_blacklist_user_tokens(self):
        """Test blacklisting all tokens for a user."""
        service = TokenBlacklistService()
        service.redis_client = AsyncMock()
        service._initialized = True

        # Mock user has 3 tokens
        service.redis_client.smembers.return_value = {
            "token-hash-1",
            "token-hash-2",
            "token-hash-3",
        }
        service.redis_client.exists.return_value = False

        count = await service.blacklist_user_tokens("user-123", "security")

        assert count == 3
        # Verify setex was called for each token
        assert service.redis_client.setex.call_count == 3

    async def test_get_blacklist_stats(self):
        """Test retrieving blacklist statistics."""
        service = TokenBlacklistService()
        service.redis_client = AsyncMock()
        service._initialized = True

        # Mock stats data
        stats_data = {
            "total_blacklisted": 100,
            "total_checked": 500,
            "reasons": {"logout": 80, "security": 20},
        }
        service.redis_client.get.return_value = '{"total_blacklisted": 100, "total_checked": 500, "reasons": {"logout": 80, "security": 20}}'
        service.redis_client.keys.return_value = ["key1", "key2", "key3"]

        stats = await service.get_blacklist_stats()

        assert stats["current_blacklisted"] == 3
        assert stats["total_blacklisted"] == 100
        assert stats["total_checked"] == 500


@pytest.mark.asyncio
class TestJWTMiddleware:
    """Test JWT authentication middleware."""

    async def test_public_path_access(self):
        """Test that public paths don't require authentication."""
        middleware = JWTAuthMiddleware()

        # Mock request for public path
        request = Mock()
        request.url.path = "/docs"
        request.headers = {}
        request.client = Mock(host="127.0.0.1")

        # Mock call_next
        response = Mock()

        async def call_next(req):
            return response

        result = await middleware(request, call_next)

        assert result == response
        # Verify no authentication was attempted
        assert not hasattr(request.state, "user_id")

    async def test_protected_path_requires_auth(self):
        """Test that protected paths require valid JWT."""
        middleware = JWTAuthMiddleware()

        # Mock request for protected path without token
        request = Mock()
        request.url.path = "/api/v1/users/profile"
        request.headers = {}
        request.client = Mock(host="127.0.0.1")

        async def call_next(req):
            return Mock()

        result = await middleware(request, call_next)

        # Should return 401 Unauthorized
        assert result.status_code == 401
        assert "Authentication required" in str(result.content)

    @patch("middleware.jwt_auth.is_token_blacklisted")
    async def test_valid_token_access(self, mock_blacklist):
        """Test access with valid JWT token."""
        mock_blacklist.return_value = False

        middleware = JWTAuthMiddleware()

        # Create valid token
        user_data = {"sub": "user-123"}
        token = create_access_token(user_data)

        # Mock request with valid token
        request = Mock()
        request.url.path = "/api/v1/users/profile"
        request.headers = {"Authorization": f"Bearer {token}"}
        request.client = Mock(host="127.0.0.1")
        request.state = Mock()

        response = Mock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware(request, call_next)

        # Should allow access
        assert result == response
        assert request.state.user_id == "user-123"
        assert request.state.is_authenticated is True

    @patch("middleware.jwt_auth.is_token_blacklisted")
    async def test_blacklisted_token_rejected(self, mock_blacklist):
        """Test that blacklisted tokens are rejected."""
        mock_blacklist.return_value = True

        middleware = JWTAuthMiddleware()

        # Create token (will be blacklisted)
        user_data = {"sub": "user-123"}
        token = create_access_token(user_data)

        # Mock request with blacklisted token
        request = Mock()
        request.url.path = "/api/v1/users/profile"
        request.headers = {"Authorization": f"Bearer {token}"}
        request.client = Mock(host="127.0.0.1")

        async def call_next(req):
            return Mock()

        result = await middleware(request, call_next)

        # Should return 401 Unauthorized
        assert result.status_code == 401
        assert "Invalid or expired token" in str(result.content)

    async def test_rate_limiting_auth_endpoints(self):
        """Test rate limiting on authentication endpoints."""
        middleware = JWTAuthMiddleware(enable_rate_limiting=True)
        middleware.max_auth_attempts = 2  # Low limit for testing

        # Mock request for auth endpoint
        request = Mock()
        request.url.path = "/api/v1/auth/login"
        request.headers = {}
        request.client = Mock(host="127.0.0.1")

        response = Mock()

        async def call_next(req):
            return response

        # First two attempts should succeed
        for _ in range(2):
            result = await middleware(request, call_next)
            assert result == response

        # Third attempt should be rate limited
        result = await middleware(request, call_next)
        assert result.status_code == 429
        assert "Too many authentication attempts" in str(result.content)

    @patch("middleware.jwt_auth.is_token_blacklisted")
    async def test_token_expiry_warning_header(self, mock_blacklist):
        """Test that expiring tokens get warning headers."""
        mock_blacklist.return_value = False

        middleware = JWTAuthMiddleware()

        # Create token expiring in 3 minutes
        user_data = {"sub": "user-123"}
        expires_delta = timedelta(minutes=3)
        token = create_access_token(user_data, expires_delta)

        # Mock request
        request = Mock()
        request.url.path = "/api/v1/users/profile"
        request.headers = {"Authorization": f"Bearer {token}"}
        request.client = Mock(host="127.0.0.1")
        request.state = Mock()

        response = Mock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware(request, call_next)

        # Should have expiry warning headers
        assert "X-Token-Expires-In" in result.headers
        assert "X-Token-Refresh-Recommended" in result.headers
        assert result.headers["X-Token-Refresh-Recommended"] == "true"

    async def test_security_headers_added(self):
        """Test that security headers are added to responses."""
        middleware = JWTAuthMiddleware()

        # Mock request for public path (simpler)
        request = Mock()
        request.url.path = "/health"
        request.headers = {}

        response = Mock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware(request, call_next)

        # Check security headers
        assert result.headers["X-Content-Type-Options"] == "nosniff"
        assert result.headers["X-Frame-Options"] == "DENY"


class TestProtectedRoutes:
    """Test that critical routes are properly protected."""

    def test_critical_routes_list(self):
        """Verify the list of critical protected routes."""
        middleware = JWTAuthMiddleware()

        critical_paths = [
            "/api/v1/users/profile",
            "/api/v1/admin/users",
            "/api/v1/reports/export/pdf",
            "/api/v1/settings/update",
            "/api/v1/payments/process",
            "/api/v1/api-keys/create",
            "/api/v1/webhooks/configure",
            "/api/v1/assessments/create",
            "/api/v1/ai/generate",
            "/api/v1/dashboard/stats",
        ]

        for path in critical_paths:
            assert middleware.is_critical_path(path), f"{path} should be protected"

    def test_public_routes_list(self):
        """Verify the list of public routes."""
        middleware = JWTAuthMiddleware()

        public_paths = [
            "/docs",
            "/openapi.json",
            "/health",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/freemium/assessment",
        ]

        for path in public_paths:
            assert middleware.is_public_path(path), f"{path} should be public"

    def test_route_coverage_percentage(self):
        """Verify we're protecting at least 20% of routes."""
        middleware = JWTAuthMiddleware()

        # Count total API routes (approximate)
        total_routes = 45  # Based on main.py router count

        # Count protected routes
        protected_count = len(middleware.CRITICAL_PROTECTED_ROUTES)

        coverage_percentage = (protected_count / total_routes) * 100

        assert coverage_percentage >= 20, (
            f"Only {coverage_percentage:.1f}% coverage, need at least 20%"
        )
        print(f"JWT Protection Coverage: {coverage_percentage:.1f}% of routes")


@pytest.mark.asyncio
class TestTokenRefreshFlow:
    """Test token refresh mechanism."""

    async def test_refresh_token_generation(self):
        """Test that refresh tokens can be generated and validated."""
        user_data = {"sub": "user-123", "email": "test@example.com"}

        # Generate refresh token
        refresh_token = create_refresh_token(user_data)

        # Decode and verify
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"

        # Check expiry is longer than access token
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        days_until_expiry = (exp_time - current_time).days

        assert days_until_expiry >= 6  # Should be around 7 days

    async def test_refresh_token_cannot_access_protected_routes(self):
        """Test that refresh tokens cannot be used for API access."""
        middleware = JWTAuthMiddleware()

        # Create refresh token (not access token)
        user_data = {"sub": "user-123"}
        refresh_token = create_refresh_token(user_data)

        # Mock request with refresh token
        request = Mock()
        request.url.path = "/api/v1/users/profile"
        request.headers = {"Authorization": f"Bearer {refresh_token}"}
        request.client = Mock(host="127.0.0.1")

        async def call_next(req):
            return Mock()

        # Patch blacklist check to avoid that issue
        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=False):
            result = await middleware(request, call_next)

        # Should be rejected (wrong token type)
        assert result.status_code == 401


class TestSecurityBestPractices:
    """Test security best practices are followed."""

    def test_jwt_secret_strength(self):
        """Test that JWT secret key is strong enough."""
        assert len(SECRET_KEY) >= 32, "JWT secret key should be at least 32 characters"

        # In production, should not be the default
        if settings.is_production:
            assert SECRET_KEY != "insecure-dev-key-change-in-production-minimum-32-chars"

    def test_jwt_algorithm_security(self):
        """Test that secure JWT algorithm is used."""
        assert ALGORITHM in ["HS256", "RS256"], "Should use secure algorithm"

    def test_token_expiry_times(self):
        """Test that token expiry times are reasonable."""
        assert settings.jwt_access_token_expire_minutes <= 60, (
            "Access tokens should expire within 1 hour"
        )
        assert settings.jwt_refresh_token_expire_days <= 30, (
            "Refresh tokens should expire within 30 days"
        )

    def test_rate_limiting_configured(self):
        """Test that rate limiting is properly configured."""
        assert settings.auth_rate_limit_per_minute <= 10, (
            "Auth endpoints should have strict rate limiting"
        )
        assert settings.rate_limit_per_minute <= 200, "General rate limit should be reasonable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
