"""
Comprehensive tests for Rate Limiting (Story 1.2)

Tests rate limiting middleware with tiered limits, Redis integration, and headers.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import redis

from middleware.rate_limiter import RateLimiter, RateLimitMiddleware, UserTier


class TestRateLimiter:
    """Test suite for rate limiting functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = Mock(spec=redis.Redis)
        mock.pipeline.return_value = mock
        mock.execute.return_value = [1, 10, 1, 1]  # Results for pipeline operations
        mock.zcard.return_value = 5
        return mock

    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create rate limiter with mock Redis."""
        limiter = RateLimiter(redis_client=mock_redis)
        return limiter

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.client.host = "192.168.1.1"
        request.headers = {}
        request.state = Mock()
        request.state.user = None
        return request

    @pytest.fixture
    def authenticated_request(self, mock_request):
        """Create an authenticated request."""
        mock_request.state.user = Mock()
        mock_request.state.user.id = "user123"
        mock_request.state.user.is_admin = False
        mock_request.state.user.subscription_tier = None
        return mock_request

    # Test 1: User Tier Detection
    def test_get_user_tier_anonymous(self, rate_limiter, mock_request):
        """Test tier detection for anonymous users."""
        tier = rate_limiter.get_user_tier(mock_request)
        assert tier == UserTier.ANONYMOUS

    def test_get_user_tier_authenticated(self, rate_limiter, authenticated_request):
        """Test tier detection for authenticated users."""
        tier = rate_limiter.get_user_tier(authenticated_request)
        assert tier == UserTier.AUTHENTICATED

    def test_get_user_tier_premium(self, rate_limiter, authenticated_request):
        """Test tier detection for premium users."""
        authenticated_request.state.user.subscription_tier = "premium"
        tier = rate_limiter.get_user_tier(authenticated_request)
        assert tier == UserTier.PREMIUM

    def test_get_user_tier_enterprise(self, rate_limiter, authenticated_request):
        """Test tier detection for enterprise users."""
        authenticated_request.state.user.subscription_tier = "enterprise"
        tier = rate_limiter.get_user_tier(authenticated_request)
        assert tier == UserTier.ENTERPRISE

    def test_get_user_tier_admin(self, rate_limiter, authenticated_request):
        """Test tier detection for admin users."""
        authenticated_request.state.user.is_admin = True
        tier = rate_limiter.get_user_tier(authenticated_request)
        assert tier == UserTier.ADMIN

    # Test 2: Identifier Generation
    def test_get_identifier_anonymous(self, rate_limiter, mock_request):
        """Test identifier for anonymous users (IP-based)."""
        identifier = rate_limiter.get_identifier(mock_request)
        assert identifier == "ip:192.168.1.1"

    def test_get_identifier_authenticated(self, rate_limiter, authenticated_request):
        """Test identifier for authenticated users (user ID-based)."""
        identifier = rate_limiter.get_identifier(authenticated_request)
        assert identifier == "user:user123"

    def test_get_identifier_with_proxy(self, rate_limiter, mock_request):
        """Test identifier extraction behind proxy."""
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        identifier = rate_limiter.get_identifier(mock_request)
        assert identifier == "ip:10.0.0.1"

    # Test 3: Rate Limit Configuration
    def test_get_default_rate_limit(self, rate_limiter):
        """Test default rate limits for different tiers."""
        # Anonymous
        limits = rate_limiter.get_rate_limit("/api/v1/test", UserTier.ANONYMOUS)
        assert limits["requests"] == 10
        assert limits["window"] == 60

        # Authenticated
        limits = rate_limiter.get_rate_limit("/api/v1/test", UserTier.AUTHENTICATED)
        assert limits["requests"] == 100
        assert limits["window"] == 60

        # Premium
        limits = rate_limiter.get_rate_limit("/api/v1/test", UserTier.PREMIUM)
        assert limits["requests"] == 1000
        assert limits["window"] == 60

        # Enterprise
        limits = rate_limiter.get_rate_limit("/api/v1/test", UserTier.ENTERPRISE)
        assert limits["requests"] == 10000
        assert limits["window"] == 60

    def test_get_endpoint_specific_limit(self, rate_limiter):
        """Test endpoint-specific rate limits."""
        # Login endpoint has stricter limits
        limits = rate_limiter.get_rate_limit("/api/v1/auth/login", UserTier.ANONYMOUS)
        assert limits["requests"] == 5
        assert limits["window"] == 300

        # Report generation has different limits
        limits = rate_limiter.get_rate_limit("/api/v1/reports/generate", UserTier.AUTHENTICATED)
        assert limits["requests"] == 10
        assert limits["window"] == 3600

    # Test 4: Bypass Logic
    def test_bypass_for_whitelisted_ip(self, rate_limiter, mock_request):
        """Test bypass for whitelisted IPs."""
        rate_limiter.IP_WHITELIST.add("192.168.1.1")
        assert rate_limiter.should_bypass(mock_request) is True

    def test_bypass_for_admin(self, rate_limiter, authenticated_request):
        """Test bypass for admin users."""
        authenticated_request.state.user.is_admin = True
        assert rate_limiter.should_bypass(authenticated_request) is True

    def test_bypass_for_service_account(self, rate_limiter, authenticated_request):
        """Test bypass for service accounts."""
        rate_limiter.SERVICE_ACCOUNTS.add("user123")
        assert rate_limiter.should_bypass(authenticated_request) is True

    # Test 5: Rate Limit Checking
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter, mock_request):
        """Test rate limit check when under limit."""
        rate_limiter.redis_client.pipeline.return_value.execute.return_value = [
            1,  # zremrangebyscore result
            5,  # zcard result (5 requests)
            1,  # zadd result
            1,  # expire result
        ]

        allowed, info = await rate_limiter.check_rate_limit(mock_request)

        assert allowed is True
        assert info["limit"] == 10  # Anonymous limit
        assert info["remaining"] == 4  # 10 - 5 - 1
        assert "reset" in info

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, rate_limiter, mock_request):
        """Test rate limit check when limit exceeded."""
        rate_limiter.redis_client.pipeline.return_value.execute.return_value = [
            1,  # zremrangebyscore result
            10,  # zcard result (10 requests - at limit)
            1,  # zadd result
            1,  # expire result
        ]

        allowed, info = await rate_limiter.check_rate_limit(mock_request)

        assert allowed is False
        assert info["limit"] == 10
        assert info["remaining"] == 0
        assert info["retry_after"] == 60

    @pytest.mark.asyncio
    async def test_check_rate_limit_with_bypass(self, rate_limiter, authenticated_request):
        """Test rate limit check with bypass."""
        authenticated_request.state.user.is_admin = True

        allowed, info = await rate_limiter.check_rate_limit(authenticated_request)

        assert allowed is True
        assert info.get("bypassed") is True

    # Test 6: Redis Failure Handling
    @pytest.mark.asyncio
    async def test_redis_failure_fail_open(self, rate_limiter, mock_request):
        """Test rate limiter fails open on Redis error."""
        rate_limiter.redis_client.pipeline.side_effect = redis.RedisError("Connection failed")

        # With fail_open = True (default)
        with patch("config.settings.RATE_LIMIT_FAIL_OPEN", True):
            allowed, info = await rate_limiter.check_rate_limit(mock_request)
            assert allowed is True
            assert "error" in info

    @pytest.mark.asyncio
    async def test_redis_failure_fail_closed(self, rate_limiter, mock_request):
        """Test rate limiter fails closed on Redis error."""
        rate_limiter.redis_client.pipeline.side_effect = redis.RedisError("Connection failed")

        # With fail_open = False
        with patch("config.settings.RATE_LIMIT_FAIL_OPEN", False):
            allowed, info = await rate_limiter.check_rate_limit(mock_request)
            assert allowed is False
            assert "error" in info

    # Test 7: Statistics Tracking
    def test_update_stats(self, rate_limiter):
        """Test statistics tracking."""
        rate_limiter._update_stats("/api/v1/test", UserTier.AUTHENTICATED, violated=False)
        rate_limiter._update_stats("/api/v1/test", UserTier.AUTHENTICATED, violated=True)

        # Check Redis calls
        assert rate_limiter.redis_client.pipeline.called
        assert rate_limiter.redis_client.hincrby.called

    def test_get_stats(self, rate_limiter):
        """Test retrieving statistics."""
        rate_limiter.redis_client.hgetall.return_value = {
            b"requests:authenticated": b"100",
            b"violations:authenticated": b"5",
        }

        stats = rate_limiter.get_stats("/api/v1/test")

        assert stats["requests:authenticated"] == 100
        assert stats["violations:authenticated"] == 5

    # Test 8: Reset Limits
    def test_reset_limits_for_identifier(self, rate_limiter):
        """Test resetting limits for a specific identifier."""
        result = rate_limiter.reset_limits("user:user123", "/api/v1/test")

        assert rate_limiter.redis_client.delete.called
        assert result is True

    def test_reset_all_limits_for_identifier(self, rate_limiter):
        """Test resetting all limits for an identifier."""
        rate_limiter.redis_client.scan_iter.return_value = [
            b"rate_limit:/api/v1/test:user:user123",
            b"rate_limit:/api/v1/other:user:user123",
        ]

        result = rate_limiter.reset_limits("user:user123")

        assert rate_limiter.redis_client.scan_iter.called
        assert rate_limiter.redis_client.delete.call_count == 2


class TestRateLimitMiddleware:
    """Test rate limit middleware integration."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app."""
        return Mock()

    @pytest.fixture
    def middleware(self, mock_app):
        """Create rate limit middleware."""
        return RateLimitMiddleware(mock_app)

    @pytest.fixture
    async def mock_call_next(self):
        """Create mock call_next function."""

        async def call_next(request):
            response = Response()
            response.headers = {}
            return response

        return call_next

    # Test 9: Middleware Integration
    @pytest.mark.asyncio
    async def test_middleware_allows_request(self, middleware, mock_call_next):
        """Test middleware allows request under limit."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.client.host = "192.168.1.1"
        request.headers = {}
        request.state = Mock()
        request.state.user = None

        # Mock rate limiter to allow
        middleware.rate_limiter.check_rate_limit = AsyncMock(
            return_value=(True, {"limit": 10, "remaining": 5, "reset": int(time.time()) + 60})
        )

        response = await middleware(request, mock_call_next)

        # Check headers added
        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "10"
        assert response.headers["X-RateLimit-Remaining"] == "5"

    @pytest.mark.asyncio
    async def test_middleware_blocks_request(self, middleware, mock_call_next):
        """Test middleware blocks request over limit."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.client.host = "192.168.1.1"
        request.headers = {}
        request.state = Mock()
        request.state.user = None

        # Mock rate limiter to block
        middleware.rate_limiter.check_rate_limit = AsyncMock(
            return_value=(
                False,
                {"limit": 10, "remaining": 0, "reset": int(time.time()) + 60, "retry_after": 60},
            )
        )

        response = await middleware(request, mock_call_next)

        # Check 429 response
        assert isinstance(response, JSONResponse)
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_skips_health_check(self, middleware, mock_call_next):
        """Test middleware skips health check endpoints."""
        request = Mock(spec=Request)
        request.url.path = "/health"

        # Should not check rate limit
        middleware.rate_limiter.check_rate_limit = AsyncMock()

        response = await middleware(request, mock_call_next)

        # Rate limiter should not be called
        middleware.rate_limiter.check_rate_limit.assert_not_called()

    # Test 10: Performance
    @pytest.mark.asyncio
    async def test_rate_limit_performance(self, middleware, mock_call_next):
        """Test rate limiting adds minimal overhead."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.client.host = "192.168.1.1"
        request.headers = {}
        request.state = Mock()
        request.state.user = None

        # Mock fast rate limit check
        async def fast_check(req):
            return True, {"limit": 10, "remaining": 5, "reset": 0}

        middleware.rate_limiter.check_rate_limit = fast_check

        start = time.time()

        # Run multiple requests
        for _ in range(100):
            await middleware(request, mock_call_next)

        duration = (time.time() - start) * 1000  # Convert to ms
        avg_duration = duration / 100

        # Should add < 5ms overhead per request
        assert avg_duration < 5, f"Average overhead {avg_duration:.2f}ms"
