"""
Unit tests for middleware/rate_limiter.py — RateLimiter, UserTier,
and RateLimitMiddleware.

Redis is mocked throughout.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from middleware.rate_limiter import RateLimiter, UserTier, RateLimitMiddleware


# ---------------------------------------------------------------------------
# UserTier enum
# ---------------------------------------------------------------------------

class TestUserTier:
    """Tests for UserTier enum."""

    def test_values(self):
        assert UserTier.ANONYMOUS == "anonymous"
        assert UserTier.AUTHENTICATED == "authenticated"
        assert UserTier.PREMIUM == "premium"
        assert UserTier.ENTERPRISE == "enterprise"
        assert UserTier.ADMIN == "admin"


# ---------------------------------------------------------------------------
# RateLimiter — configuration
# ---------------------------------------------------------------------------

class TestRateLimiterConfig:
    """Tests for RateLimiter configuration."""

    def _make_limiter(self):
        mock_redis = MagicMock()
        return RateLimiter(redis_client=mock_redis)

    def test_default_limits_exist_for_all_tiers(self):
        rl = self._make_limiter()
        for tier in UserTier:
            assert tier in rl.DEFAULT_LIMITS
            assert "requests" in rl.DEFAULT_LIMITS[tier]
            assert "window" in rl.DEFAULT_LIMITS[tier]

    def test_endpoint_limits_configured(self):
        rl = self._make_limiter()
        assert "/api/v1/auth/login" in rl.ENDPOINT_LIMITS
        assert "/api/v1/auth/register" in rl.ENDPOINT_LIMITS
        login_limit = rl.ENDPOINT_LIMITS["/api/v1/auth/login"]
        assert login_limit["requests"] == 5
        assert login_limit["window"] == 300

    def test_admin_tier_effectively_unlimited(self):
        rl = self._make_limiter()
        admin_limit = rl.DEFAULT_LIMITS[UserTier.ADMIN]
        assert admin_limit["requests"] >= 999999


# ---------------------------------------------------------------------------
# get_user_tier
# ---------------------------------------------------------------------------

class TestGetUserTier:
    """Tests for get_user_tier()."""

    def _make_limiter(self):
        return RateLimiter(redis_client=MagicMock())

    def _make_request(self, user=None):
        req = MagicMock()
        req.state = MagicMock()
        req.state.user = user
        return req

    def test_anonymous_when_no_user(self):
        rl = self._make_limiter()
        request = self._make_request(user=None)
        assert rl.get_user_tier(request) == UserTier.ANONYMOUS

    def test_admin_user(self):
        rl = self._make_limiter()
        user = MagicMock()
        user.is_admin = True
        request = self._make_request(user=user)
        assert rl.get_user_tier(request) == UserTier.ADMIN

    def test_enterprise_user(self):
        rl = self._make_limiter()
        user = MagicMock()
        user.is_admin = False
        user.id = "user-1"
        user.subscription_tier = "enterprise"
        request = self._make_request(user=user)
        assert rl.get_user_tier(request) == UserTier.ENTERPRISE

    def test_premium_user(self):
        rl = self._make_limiter()
        user = MagicMock()
        user.is_admin = False
        user.id = "user-2"
        user.subscription_tier = "premium"
        request = self._make_request(user=user)
        assert rl.get_user_tier(request) == UserTier.PREMIUM

    def test_authenticated_user_no_subscription(self):
        rl = self._make_limiter()
        user = MagicMock()
        user.is_admin = False
        user.id = "user-3"
        user.subscription_tier = None
        request = self._make_request(user=user)
        assert rl.get_user_tier(request) == UserTier.AUTHENTICATED


# ---------------------------------------------------------------------------
# get_identifier
# ---------------------------------------------------------------------------

class TestGetIdentifier:
    """Tests for get_identifier()."""

    def _make_limiter(self):
        return RateLimiter(redis_client=MagicMock())

    def test_authenticated_user_id(self):
        rl = self._make_limiter()
        user = MagicMock()
        user.id = "user-123"
        req = MagicMock()
        req.state = MagicMock()
        req.state.user = user
        assert rl.get_identifier(req) == "user:user-123"

    def test_anonymous_ip(self):
        rl = self._make_limiter()
        req = MagicMock()
        req.state = MagicMock()
        req.state.user = None
        req.client = MagicMock()
        req.client.host = "10.0.0.1"
        req.headers = {}
        assert rl.get_identifier(req) == "ip:10.0.0.1"

    def test_x_forwarded_for(self):
        rl = self._make_limiter()
        req = MagicMock()
        req.state = MagicMock()
        req.state.user = None
        req.client = MagicMock()
        req.client.host = "127.0.0.1"
        mock_headers = MagicMock()
        mock_headers.get = MagicMock(side_effect=lambda k, d=None: {
            "X-Forwarded-For": "203.0.113.50, 70.41.3.18",
        }.get(k, d))
        req.headers = mock_headers
        assert rl.get_identifier(req) == "ip:203.0.113.50"


# ---------------------------------------------------------------------------
# get_rate_limit
# ---------------------------------------------------------------------------

class TestGetRateLimit:
    """Tests for get_rate_limit()."""

    def _make_limiter(self):
        return RateLimiter(redis_client=MagicMock())

    def test_endpoint_specific_override(self):
        rl = self._make_limiter()
        limits = rl.get_rate_limit("/api/v1/auth/login", UserTier.AUTHENTICATED)
        assert limits["requests"] == 5
        assert limits["window"] == 300

    def test_default_for_tier(self):
        rl = self._make_limiter()
        limits = rl.get_rate_limit("/api/v1/some/generic/endpoint", UserTier.AUTHENTICATED)
        assert limits == rl.DEFAULT_LIMITS[UserTier.AUTHENTICATED]

    def test_anonymous_default(self):
        rl = self._make_limiter()
        limits = rl.get_rate_limit("/api/v1/something", UserTier.ANONYMOUS)
        assert limits["requests"] == 10


# ---------------------------------------------------------------------------
# should_bypass
# ---------------------------------------------------------------------------

class TestShouldBypass:
    """Tests for should_bypass()."""

    def _make_limiter(self):
        return RateLimiter(redis_client=MagicMock())

    def test_whitelisted_ip(self):
        rl = self._make_limiter()
        rl.IP_WHITELIST.add("10.0.0.1")
        req = MagicMock()
        req.state = MagicMock()
        req.state.user = None
        req.client = MagicMock()
        req.client.host = "10.0.0.1"
        assert rl.should_bypass(req) is True
        rl.IP_WHITELIST.discard("10.0.0.1")  # cleanup

    def test_admin_bypass(self):
        rl = self._make_limiter()
        user = MagicMock()
        user.is_admin = True
        user.id = "admin-1"
        req = MagicMock()
        req.state = MagicMock()
        req.state.user = user
        req.client = MagicMock()
        req.client.host = "10.0.0.2"
        req.url.path = "/api/v1/test"
        assert rl.should_bypass(req) is True

    def test_regular_user_no_bypass(self):
        rl = self._make_limiter()
        user = MagicMock()
        user.is_admin = False
        user.id = "user-1"
        req = MagicMock()
        req.state = MagicMock()
        req.state.user = user
        req.client = MagicMock()
        req.client.host = "10.0.0.3"
        assert rl.should_bypass(req) is False


# ---------------------------------------------------------------------------
# RateLimitMiddleware
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    def test_middleware_init(self):
        mock_rl = MagicMock()
        app = MagicMock()
        mw = RateLimitMiddleware(app, rate_limiter=mock_rl)
        assert mw.rate_limiter is mock_rl

    @pytest.mark.asyncio
    async def test_skip_health_endpoint(self):
        mock_rl = MagicMock()
        mock_app = MagicMock()
        mw = RateLimitMiddleware(mock_app, rate_limiter=mock_rl)

        req = MagicMock()
        req.url.path = "/health"
        next_response = MagicMock()
        call_next = AsyncMock(return_value=next_response)

        response = await mw(req, call_next)
        call_next.assert_awaited_once()
        assert response == next_response

    @pytest.mark.asyncio
    async def test_rate_limited_returns_429(self):
        mock_rl = MagicMock()
        mock_rl.check_rate_limit = AsyncMock(return_value=(
            False,
            {"limit": 10, "remaining": 0, "reset": 9999, "retry_after": 60},
        ))
        mock_app = MagicMock()
        mw = RateLimitMiddleware(mock_app, rate_limiter=mock_rl)

        req = MagicMock()
        req.url.path = "/api/v1/test"
        call_next = AsyncMock()

        response = await mw(req, call_next)
        assert response.status_code == 429
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_allowed_request_has_headers(self):
        mock_rl = MagicMock()
        mock_rl.check_rate_limit = AsyncMock(return_value=(
            True,
            {"limit": 100, "remaining": 99, "reset": 9999},
        ))
        mock_app = MagicMock()
        mw = RateLimitMiddleware(mock_app, rate_limiter=mock_rl)

        req = MagicMock()
        req.url.path = "/api/v1/test"
        next_response = MagicMock()
        next_response.headers = {}
        call_next = AsyncMock(return_value=next_response)

        response = await mw(req, call_next)
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert response.headers["X-RateLimit-Remaining"] == "99"

    @pytest.mark.asyncio
    async def test_bypassed_request_no_headers(self):
        mock_rl = MagicMock()
        mock_rl.check_rate_limit = AsyncMock(return_value=(
            True,
            {"bypassed": True},
        ))
        mock_app = MagicMock()
        mw = RateLimitMiddleware(mock_app, rate_limiter=mock_rl)

        req = MagicMock()
        req.url.path = "/api/v1/test"
        next_response = MagicMock()
        next_response.headers = {}
        call_next = AsyncMock(return_value=next_response)

        response = await mw(req, call_next)
        assert "X-RateLimit-Limit" not in response.headers
