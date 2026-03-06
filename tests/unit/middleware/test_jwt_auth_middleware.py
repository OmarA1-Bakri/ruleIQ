"""
Unit tests for middleware/jwt_auth.py — JWTAuthMiddleware.

Tests path classification, rate limiting, and token validation logic.
All external services are mocked.
"""

import os
import time
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from middleware.jwt_auth import JWTAuthMiddleware


# ---------------------------------------------------------------------------
# Public / protected path classification
# ---------------------------------------------------------------------------

class TestPathClassification:
    """Tests for is_public_path() and is_critical_path()."""

    def setup_method(self):
        self.mw = JWTAuthMiddleware(
            enable_strict_mode=True,
            enable_rate_limiting=False,
            enable_audit_logging=False,
        )

    # --- Public paths ---

    def test_docs_is_public(self):
        assert self.mw.is_public_path("/docs") is True

    def test_docs_slash_is_public(self):
        assert self.mw.is_public_path("/docs/") is True

    def test_redoc_is_public(self):
        assert self.mw.is_public_path("/redoc") is True

    def test_openapi_json_is_public(self):
        assert self.mw.is_public_path("/openapi.json") is True

    def test_health_is_public(self):
        assert self.mw.is_public_path("/health") is True

    def test_api_health_is_public(self):
        assert self.mw.is_public_path("/api/v1/health") is True

    def test_root_is_public(self):
        assert self.mw.is_public_path("/") is True

    def test_login_is_public(self):
        assert self.mw.is_public_path("/api/v1/auth/login") is True

    def test_register_is_public(self):
        assert self.mw.is_public_path("/api/v1/auth/register") is True

    def test_refresh_is_public(self):
        assert self.mw.is_public_path("/api/v1/auth/refresh") is True

    def test_forgot_password_is_public(self):
        assert self.mw.is_public_path("/api/v1/auth/forgot-password") is True

    def test_freemium_is_public(self):
        assert self.mw.is_public_path("/api/v1/freemium/assessment") is True

    def test_google_auth_is_public(self):
        assert self.mw.is_public_path("/api/v1/auth/google/callback") is True

    # --- Protected paths ---

    def test_users_is_protected(self):
        assert self.mw.is_critical_path("/api/v1/users") is True

    def test_admin_is_protected(self):
        assert self.mw.is_critical_path("/api/v1/admin/settings") is True

    def test_assessments_is_protected(self):
        assert self.mw.is_critical_path("/api/v1/assessments") is True

    def test_compliance_is_protected(self):
        assert self.mw.is_critical_path("/api/v1/compliance/frameworks") is True

    def test_policies_is_protected(self):
        assert self.mw.is_critical_path("/api/v1/policies/create") is True

    def test_api_keys_is_protected(self):
        assert self.mw.is_critical_path("/api/v1/api-keys") is True

    def test_dashboard_is_protected(self):
        assert self.mw.is_critical_path("/api/v1/dashboard") is True

    def test_iq_agent_is_protected(self):
        assert self.mw.is_critical_path("/api/v1/iq-agent/query") is True

    # --- Non-classified paths ---

    def test_random_path_not_public(self):
        assert self.mw.is_public_path("/api/v1/random") is False

    def test_random_path_may_not_be_critical(self):
        # A truly random path doesn't match any critical pattern
        assert self.mw.is_critical_path("/completely/random") is False


# ---------------------------------------------------------------------------
# Custom path patterns
# ---------------------------------------------------------------------------

class TestCustomPaths:
    """Tests for custom_public_paths and custom_protected_paths."""

    def test_custom_public_path(self):
        mw = JWTAuthMiddleware(
            enable_strict_mode=True,
            enable_rate_limiting=False,
            enable_audit_logging=False,
            custom_public_paths=[r"^/api/v1/custom-public$"],
        )
        assert mw.is_public_path("/api/v1/custom-public") is True
        assert mw.is_public_path("/api/v1/other") is False

    def test_custom_protected_path(self):
        mw = JWTAuthMiddleware(
            enable_strict_mode=True,
            enable_rate_limiting=False,
            enable_audit_logging=False,
            custom_protected_paths=[r"^/api/v1/custom-protected.*"],
        )
        assert mw.is_critical_path("/api/v1/custom-protected/data") is True


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    """Tests for check_rate_limit()."""

    def test_rate_limiting_disabled(self):
        mw = JWTAuthMiddleware(
            enable_rate_limiting=False,
            enable_audit_logging=False,
        )
        # Should always return False (not rate-limited)
        for _ in range(100):
            assert mw.check_rate_limit("client-ip") is False

    def test_rate_limiting_within_limit(self):
        mw = JWTAuthMiddleware(
            enable_rate_limiting=True,
            enable_audit_logging=False,
        )
        # max attempts from settings, but we can test within reasonable range
        for i in range(3):
            result = mw.check_rate_limit("test-ip")
            assert result is False  # Should not be rate-limited for first few

    def test_rate_limiting_exceeded(self):
        mw = JWTAuthMiddleware(
            enable_rate_limiting=True,
            enable_audit_logging=False,
        )
        # Override max_auth_attempts for testing
        mw.max_auth_attempts = 3

        # First 3 should pass
        assert mw.check_rate_limit("test-ip-2") is False
        assert mw.check_rate_limit("test-ip-2") is False
        assert mw.check_rate_limit("test-ip-2") is False

        # 4th should be rate-limited
        assert mw.check_rate_limit("test-ip-2") is True

    def test_rate_limiting_separate_ips(self):
        mw = JWTAuthMiddleware(
            enable_rate_limiting=True,
            enable_audit_logging=False,
        )
        mw.max_auth_attempts = 2

        # Two requests from ip-a
        mw.check_rate_limit("ip-a")
        mw.check_rate_limit("ip-a")
        assert mw.check_rate_limit("ip-a") is True

        # ip-b should not be rate limited
        assert mw.check_rate_limit("ip-b") is False

    def test_rate_limit_window_cleanup(self):
        mw = JWTAuthMiddleware(
            enable_rate_limiting=True,
            enable_audit_logging=False,
        )
        mw.max_auth_attempts = 2
        mw.rate_limit_window = 0  # 0 seconds — all timestamps are "old"

        # Add entries
        mw.auth_attempts["cleanup-ip"] = [time.time() - 100, time.time() - 100]

        # Should clean up old entries and not be rate-limited
        assert mw.check_rate_limit("cleanup-ip") is False


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

class TestValidateJWTToken:
    """Tests for validate_jwt_token() async method."""

    def setup_method(self):
        self.mw = JWTAuthMiddleware(
            enable_strict_mode=True,
            enable_rate_limiting=False,
            enable_audit_logging=False,
        )

    @pytest.mark.asyncio
    async def test_valid_access_token(self):
        from api.dependencies.auth import create_access_token

        token = create_access_token(data={"sub": "user@example.com"})

        with patch("middleware.jwt_auth.is_token_blacklisted", new_callable=AsyncMock, return_value=False):
            payload = await self.mw.validate_jwt_token(token)
            assert payload is not None
            assert payload["sub"] == "user@example.com"
            assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_blacklisted_token_returns_none(self):
        from api.dependencies.auth import create_access_token

        token = create_access_token(data={"sub": "user@example.com"})

        with patch("middleware.jwt_auth.is_token_blacklisted", new_callable=AsyncMock, return_value=True):
            payload = await self.mw.validate_jwt_token(token)
            assert payload is None

    @pytest.mark.asyncio
    async def test_refresh_token_rejected(self):
        from api.dependencies.auth import create_refresh_token

        token = create_refresh_token(data={"sub": "user@example.com"})

        with patch("middleware.jwt_auth.is_token_blacklisted", new_callable=AsyncMock, return_value=False):
            payload = await self.mw.validate_jwt_token(token)
            assert payload is None  # refresh tokens have type != "access"

    @pytest.mark.asyncio
    async def test_expired_token_returns_none(self):
        from api.dependencies.auth import create_access_token

        token = create_access_token(
            data={"sub": "user@example.com"},
            expires_delta=timedelta(seconds=-10),
        )

        with patch("middleware.jwt_auth.is_token_blacklisted", new_callable=AsyncMock, return_value=False):
            payload = await self.mw.validate_jwt_token(token)
            assert payload is None

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self):
        with patch("middleware.jwt_auth.is_token_blacklisted", new_callable=AsyncMock, return_value=False):
            payload = await self.mw.validate_jwt_token("garbage.token.here")
            assert payload is None


# ---------------------------------------------------------------------------
# Middleware __call__ integration
# ---------------------------------------------------------------------------

class TestMiddlewareCall:
    """Tests for the __call__ method (request processing)."""

    def setup_method(self):
        self.mw = JWTAuthMiddleware(
            enable_strict_mode=True,
            enable_rate_limiting=False,
            enable_audit_logging=False,
        )

    def _make_request(self, path, auth_header=None, method="GET", client_host="127.0.0.1"):
        """Create a mock Request."""
        mock_request = MagicMock()
        mock_request.url.path = path
        mock_request.method = method
        mock_request.headers = MagicMock()
        mock_request.headers.get = MagicMock(side_effect=lambda key, default=None: {
            "Authorization": auth_header,
            "User-Agent": "test-agent",
        }.get(key, default))
        mock_request.client = MagicMock()
        mock_request.client.host = client_host
        mock_request.state = MagicMock()
        return mock_request

    @pytest.mark.asyncio
    async def test_public_path_passes_through(self):
        request = self._make_request("/docs")
        next_response = MagicMock()
        call_next = AsyncMock(return_value=next_response)

        response = await self.mw(request, call_next)
        call_next.assert_awaited_once_with(request)
        assert response == next_response

    @pytest.mark.asyncio
    async def test_protected_path_no_auth_returns_401(self):
        request = self._make_request("/api/v1/users", auth_header=None)
        call_next = AsyncMock()

        response = await self.mw(request, call_next)
        assert response.status_code == 401
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_protected_path_invalid_bearer_returns_401(self):
        request = self._make_request("/api/v1/users", auth_header="Basic abc123")
        call_next = AsyncMock()

        response = await self.mw(request, call_next)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_path_valid_token_passes(self):
        from api.dependencies.auth import create_access_token

        token = create_access_token(data={"sub": "user@example.com"})
        request = self._make_request(
            "/api/v1/assessments",
            auth_header=f"Bearer {token}",
        )
        next_response = MagicMock()
        next_response.headers = {}
        call_next = AsyncMock(return_value=next_response)

        with patch("middleware.jwt_auth.is_token_blacklisted", new_callable=AsyncMock, return_value=False):
            response = await self.mw(request, call_next)
            call_next.assert_awaited_once()
            assert response.headers.get("X-Content-Type-Options") == "nosniff"

    @pytest.mark.asyncio
    async def test_rate_limit_on_auth_endpoint(self):
        from api.dependencies.auth import create_access_token

        mw = JWTAuthMiddleware(
            enable_strict_mode=True,
            enable_rate_limiting=True,
            enable_audit_logging=False,
        )
        mw.max_auth_attempts = 1

        token = create_access_token(data={"sub": "user@example.com"})

        # Use a non-public auth endpoint (e.g. /api/v1/auth/profile)
        # /api/v1/auth/login IS public and would bypass auth entirely.
        auth_path = "/api/v1/auth/profile"

        # First request — record attempt and pass through
        req1 = self._make_request(auth_path, auth_header=f"Bearer {token}")
        next_resp = MagicMock()
        next_resp.headers = {}

        with patch("middleware.jwt_auth.is_token_blacklisted", new_callable=AsyncMock, return_value=False):
            await mw(req1, AsyncMock(return_value=next_resp))

        # Second request — should be rate-limited (returns JSONResponse directly)
        req2 = self._make_request(auth_path, auth_header=f"Bearer {token}")
        call_next = AsyncMock()

        # Rate limit check happens before token validation
        response = await mw(req2, call_next)
        assert response.status_code == 429
        call_next.assert_not_awaited()


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

class TestFactory:
    """Tests for get_jwt_middleware factory."""

    def test_factory_returns_instance(self):
        from middleware.jwt_auth import get_jwt_middleware
        mw = get_jwt_middleware(enable_strict_mode=False)
        assert isinstance(mw, JWTAuthMiddleware)
        assert mw.enable_strict_mode is False
