"""
Security Enhancements Test Suite
Tests for all critical and high-priority security fixes
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
import jwt

# Import our security modules
from config.security_settings import get_security_settings, SecurityEnvironment
from middleware.cors_enhanced import EnhancedCORSMiddleware
from middleware.jwt_enhanced import JWTEnhancedMiddleware
from middleware.rate_limiter_enhanced import EnhancedRateLimiter, TokenBucket
from services.redis_circuit_breaker import RedisCircuitBreaker, CircuitState, RedisFailureStrategy


class TestCORSConfiguration:
    """Test CORS security enhancements"""

    def test_cors_production_settings(self):
        """Test that CORS uses explicit lists in production"""
        settings = get_security_settings()
        settings.environment = SecurityEnvironment.PRODUCTION

        cors_config = settings.get_cors_config()

        # Verify no wildcards in production
        assert "*" not in cors_config["allow_methods"]
        assert "*" not in cors_config["allow_headers"]

        # Verify explicit lists
        assert "GET" in cors_config["allow_methods"]
        assert "POST" in cors_config["allow_methods"]
        assert "Authorization" in cors_config["allow_headers"]
        assert "Content-Type" in cors_config["allow_headers"]

    def test_cors_websocket_configuration(self):
        """Test WebSocket CORS configuration"""
        settings = get_security_settings()

        # Production WebSocket origins
        assert "wss://app.ruleiq.com" in settings.cors.websocket_origins
        assert "wss://www.ruleiq.com" in settings.cors.websocket_origins

    @pytest.mark.asyncio
    async def test_cors_vary_origin_header(self):
        """Test that Vary: Origin header is added"""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # Add enhanced CORS middleware
        cors_middleware = EnhancedCORSMiddleware(app, environment=SecurityEnvironment.PRODUCTION)

        # Create test request
        request = Mock(spec=Request)
        request.method = "GET"
        request.headers = {"origin": "https://app.ruleiq.com"}

        async def call_next(req):
            response = Response(content='{"status": "ok"}')
            return response

        # Process request
        response = await cors_middleware.dispatch(request, call_next)

        # Verify Vary header
        assert "Vary" in response.headers
        assert "Origin" in response.headers["Vary"]

    def test_cors_preflight_validation(self):
        """Test CORS preflight request validation"""
        app = FastAPI()
        cors_middleware = EnhancedCORSMiddleware(app, environment=SecurityEnvironment.PRODUCTION)

        # Test allowed origin
        assert cors_middleware._is_origin_allowed("https://app.ruleiq.com")

        # Test disallowed origin
        assert not cors_middleware._is_origin_allowed("https://evil.com")


class TestRedisCircuitBreaker:
    """Test Redis circuit breaker implementation"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions"""
        breaker = RedisCircuitBreaker(
            failure_strategy=RedisFailureStrategy.DEGRADED, failure_threshold=3, recovery_timeout=1
        )

        # Initial state should be closed
        assert breaker.state == CircuitState.CLOSED

        # Record failures
        for _ in range(3):
            breaker._record_failure()

        # Circuit should be open
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Check if circuit can transition to half-open
        assert breaker._should_allow_request()

    @pytest.mark.asyncio
    async def test_redis_failure_strategies(self):
        """Test different Redis failure strategies"""

        # Test FAIL_OPEN strategy
        breaker_open = RedisCircuitBreaker(
            failure_strategy=RedisFailureStrategy.FAIL_OPEN, failure_threshold=1
        )
        breaker_open._trip_circuit()
        assert breaker_open._should_allow_request()  # Should allow even when open

        # Test FAIL_CLOSED strategy
        breaker_closed = RedisCircuitBreaker(
            failure_strategy=RedisFailureStrategy.FAIL_CLOSED, failure_threshold=1
        )
        breaker_closed._trip_circuit()
        assert not breaker_closed._should_allow_request()  # Should deny when open

        # Test DEGRADED strategy
        breaker_degraded = RedisCircuitBreaker(
            failure_strategy=RedisFailureStrategy.DEGRADED, failure_threshold=1
        )
        breaker_degraded._trip_circuit()
        assert breaker_degraded._should_allow_request()  # Should allow with local cache

    def test_local_cache_fallback(self):
        """Test local cache for degraded mode"""
        breaker = RedisCircuitBreaker(failure_strategy=RedisFailureStrategy.DEGRADED)

        # Test local cache operations
        breaker.local_cache.set("test_key", "test_value")
        assert breaker.local_cache.get("test_key") == "test_value"

        # Test cache expiration
        breaker.local_cache.ttl = 0.1
        breaker.local_cache.set("expire_key", "expire_value")
        time.sleep(0.2)
        assert breaker.local_cache.get("expire_key") is None


class TestJWTEnhancements:
    """Test JWT security enhancements"""

    def test_httponly_cookie_configuration(self):
        """Test HttpOnly cookie settings"""
        app = FastAPI()
        jwt_middleware = JWTEnhancedMiddleware(app)

        assert jwt_middleware.use_httponly_cookies
        assert jwt_middleware.cookie_secure
        assert jwt_middleware.cookie_samesite == "strict"

    def test_jwt_token_creation(self):
        """Test JWT token creation with security features"""
        app = FastAPI()
        jwt_middleware = JWTEnhancedMiddleware(app)

        # Create access token
        access_token = jwt_middleware.create_access_token(
            user_id="123", email="test@example.com", role="user"
        )

        # Decode and verify token structure
        payload = jwt.decode(
            access_token, jwt_middleware.secret_key, algorithms=[jwt_middleware.algorithm]
        )

        assert payload["sub"] == "123"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload
        assert "nbf" in payload

    def test_refresh_token_rotation(self):
        """Test refresh token rotation mechanism"""
        app = FastAPI()
        jwt_middleware = JWTEnhancedMiddleware(app)

        # Create refresh token with family ID
        refresh_token = jwt_middleware.create_refresh_token(
            user_id="123", email="test@example.com", family_id="family_123"
        )

        # Decode and verify family ID
        payload = jwt.decode(
            refresh_token, jwt_middleware.secret_key, algorithms=[jwt_middleware.algorithm]
        )

        assert payload["family_id"] == "family_123"
        assert payload["type"] == "refresh"

    def test_cookie_operations(self):
        """Test setting and clearing auth cookies"""
        app = FastAPI()
        jwt_middleware = JWTEnhancedMiddleware(app)

        response = Response()

        # Test setting cookies
        jwt_middleware.set_auth_cookies(
            response, access_token="test_access", refresh_token="test_refresh"
        )

        # Verify cookies are set with correct attributes
        # (In real test, would check response.set_cookie calls)

        # Test clearing cookies
        jwt_middleware.clear_auth_cookies(response)


class TestRateLimiting:
    """Test rate limiting enhancements"""

    def test_token_bucket_algorithm(self):
        """Test token bucket implementation"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        # Initial capacity
        assert bucket.tokens == 10

        # Consume tokens
        assert bucket.consume(5)
        assert bucket.tokens == 5

        # Try to consume more than available
        assert not bucket.consume(6)
        assert bucket.tokens == 5

        # Test refill
        time.sleep(2)
        bucket._refill()
        assert bucket.tokens > 5

    def test_burst_allowance(self):
        """Test burst allowance mechanism"""
        bucket = TokenBucket(capacity=120, refill_rate=100 / 60)  # 100/min + 20 burst

        # Can burst up to capacity
        assert bucket.consume(120)

        # Cannot exceed capacity
        assert not bucket.consume(1)

    @pytest.mark.asyncio
    async def test_endpoint_specific_limits(self):
        """Test endpoint-specific rate limits"""
        app = FastAPI()
        rate_limiter = EnhancedRateLimiter(app)

        # Test auth endpoint limit
        auth_limit = rate_limiter._get_endpoint_limit("/api/v1/auth/login")
        assert auth_limit["limit"] == 5
        assert auth_limit["burst"] == 2

        # Test AI endpoint limit
        ai_limit = rate_limiter._get_endpoint_limit("/api/v1/ai/generate")
        assert ai_limit["limit"] == 20
        assert ai_limit["burst"] == 5

        # Test default limit
        default_limit = rate_limiter._get_endpoint_limit("/api/v1/other")
        assert default_limit["limit"] == 100
        assert default_limit["burst"] == 20

    def test_rate_limit_headers(self):
        """Test rate limit response headers"""
        app = FastAPI()
        rate_limiter = EnhancedRateLimiter(app)

        result = {
            "allowed": True,
            "limit": 100,
            "burst": 20,
            "remaining": 95,
            "reset": int(time.time()) + 60,
        }

        headers = rate_limiter._create_rate_limit_headers(result)

        assert "X-RateLimit-Limit" in headers
        assert headers["X-RateLimit-Limit"] == "100"
        assert "X-RateLimit-Remaining" in headers
        assert headers["X-RateLimit-Remaining"] == "95"
        assert "X-RateLimit-Burst" in headers
        assert headers["X-RateLimit-Burst"] == "20"

    def test_ip_vs_user_based_limiting(self):
        """Test IP-based vs user-based rate limiting"""
        app = FastAPI()
        rate_limiter = EnhancedRateLimiter(app)

        # Test IP extraction
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        request.client = Mock(host="127.0.0.1")

        ip = rate_limiter._get_client_ip(request)
        assert ip == "192.168.1.1"  # First IP in forwarded chain


class TestConfigurationHotReload:
    """Test configuration hot-reload functionality"""

    @pytest.mark.asyncio
    async def test_rate_limit_config_reload(self):
        """Test rate limiting configuration hot-reload"""
        app = FastAPI()
        rate_limiter = EnhancedRateLimiter(app)

        # Initial configuration
        initial_limit = rate_limiter.default_rate_limit

        # Simulate configuration change
        rate_limiter.rate_config.default_rate_limit = 200

        # Trigger reload
        await rate_limiter._reload_configuration()

        # Verify configuration updated
        # (In real scenario, would reload from file/database)


class TestIntegration:
    """Integration tests for all security components"""

    @pytest.mark.asyncio
    async def test_full_security_stack(self):
        """Test all security components working together"""
        app = FastAPI()

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"status": "ok"}

        # Add all security middleware
        app.add_middleware(EnhancedCORSMiddleware)
        app.add_middleware(JWTEnhancedMiddleware)
        app.add_middleware(EnhancedRateLimiter)

        # Create test client
        client = TestClient(app)

        # Test request with proper headers
        response = client.get(
            "/api/v1/test",
            headers={"Origin": "https://app.ruleiq.com", "Authorization": "Bearer test_token"},
        )

        # Verify security headers are present
        assert "Vary" in response.headers
        assert "X-RateLimit-Limit" in response.headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
