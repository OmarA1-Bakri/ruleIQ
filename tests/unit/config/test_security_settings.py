"""
Unit tests for config/security_settings.py — SecuritySettings, CORSConfig,
JWTConfig, RedisConfig, RateLimitConfig.

Pure Pydantic model tests with no external dependencies.
"""

import os
import pytest
from unittest.mock import patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from config.security_settings import (
    SecurityEnvironment,
    CORSConfig,
    JWTConfig,
    RedisConfig,
    RedisFailureStrategy,
    RateLimitConfig,
    SecuritySettings,
)


# ---------------------------------------------------------------------------
# SecurityEnvironment enum
# ---------------------------------------------------------------------------

class TestSecurityEnvironment:
    """Tests for SecurityEnvironment enum."""

    def test_development(self):
        assert SecurityEnvironment.DEVELOPMENT == "development"

    def test_staging(self):
        assert SecurityEnvironment.STAGING == "staging"

    def test_production(self):
        assert SecurityEnvironment.PRODUCTION == "production"

    def test_testing(self):
        assert SecurityEnvironment.TESTING == "testing"


# ---------------------------------------------------------------------------
# RedisFailureStrategy enum
# ---------------------------------------------------------------------------

class TestRedisFailureStrategy:
    """Tests for RedisFailureStrategy enum."""

    def test_fail_open(self):
        assert RedisFailureStrategy.FAIL_OPEN == "fail_open"

    def test_fail_closed(self):
        assert RedisFailureStrategy.FAIL_CLOSED == "fail_closed"

    def test_degraded(self):
        assert RedisFailureStrategy.DEGRADED == "degraded"


# ---------------------------------------------------------------------------
# CORSConfig
# ---------------------------------------------------------------------------

class TestCORSConfig:
    """Tests for CORSConfig Pydantic model."""

    def test_default_allowed_origins(self):
        cfg = CORSConfig()
        assert "https://app.ruleiq.com" in cfg.allowed_origins
        assert "https://www.ruleiq.com" in cfg.allowed_origins
        assert "https://staging.ruleiq.com" in cfg.allowed_origins

    def test_default_allowed_methods(self):
        cfg = CORSConfig()
        assert "GET" in cfg.allowed_methods
        assert "POST" in cfg.allowed_methods
        assert "DELETE" in cfg.allowed_methods

    def test_default_allowed_headers(self):
        cfg = CORSConfig()
        assert "Authorization" in cfg.allowed_headers
        assert "Content-Type" in cfg.allowed_headers

    def test_default_exposed_headers(self):
        cfg = CORSConfig()
        assert "X-Request-ID" in cfg.exposed_headers
        assert "X-RateLimit-Limit" in cfg.exposed_headers

    def test_default_credentials(self):
        cfg = CORSConfig()
        assert cfg.allow_credentials is True

    def test_default_max_age(self):
        cfg = CORSConfig()
        assert cfg.max_age == 3600

    def test_websocket_origins(self):
        cfg = CORSConfig()
        assert "wss://app.ruleiq.com" in cfg.websocket_origins

    def test_development_cors_config(self):
        cfg = CORSConfig()
        result = cfg.get_config_for_environment(SecurityEnvironment.DEVELOPMENT)
        assert "http://localhost:3000" in result["allow_origins"]
        assert "http://localhost:8000" in result["allow_origins"]

    def test_testing_cors_config(self):
        cfg = CORSConfig()
        result = cfg.get_config_for_environment(SecurityEnvironment.TESTING)
        assert "http://testserver" in result["allow_origins"]

    def test_production_cors_config(self):
        cfg = CORSConfig()
        result = cfg.get_config_for_environment(SecurityEnvironment.PRODUCTION)
        assert "https://app.ruleiq.com" in result["allow_origins"]
        assert "http://localhost:3000" not in result["allow_origins"]


# ---------------------------------------------------------------------------
# JWTConfig
# ---------------------------------------------------------------------------

class TestJWTConfig:
    """Tests for JWTConfig Pydantic model."""

    def test_default_access_token_expiry(self):
        cfg = JWTConfig()
        assert cfg.access_token_expire_minutes == 15

    def test_default_refresh_token_expiry(self):
        cfg = JWTConfig()
        assert cfg.refresh_token_expire_days == 7

    def test_default_algorithm(self):
        cfg = JWTConfig()
        assert cfg.algorithm == "HS256"

    def test_httponly_cookies_enabled(self):
        cfg = JWTConfig()
        assert cfg.use_httponly_cookies is True
        assert cfg.cookie_secure is True
        assert cfg.cookie_samesite == "strict"

    def test_security_features_enabled(self):
        cfg = JWTConfig()
        assert cfg.enable_refresh_rotation is True
        assert cfg.enable_jti_validation is True
        assert cfg.enable_audience_validation is True

    def test_default_issuer(self):
        cfg = JWTConfig()
        assert cfg.issuer == "ruleiq.com"

    def test_default_audience(self):
        cfg = JWTConfig()
        assert "ruleiq-api" in cfg.audience

    def test_refresh_rate_limit(self):
        cfg = JWTConfig()
        assert cfg.refresh_rate_limit == 5
        assert cfg.refresh_rate_window == 300

    def test_secret_rotation(self):
        cfg = JWTConfig()
        assert cfg.enable_secret_rotation is True
        assert cfg.rotation_interval_days == 30
        assert cfg.rotation_overlap_hours == 24


# ---------------------------------------------------------------------------
# RedisConfig
# ---------------------------------------------------------------------------

class TestRedisConfig:
    """Tests for RedisConfig Pydantic model."""

    def test_default_host(self):
        cfg = RedisConfig()
        assert cfg.host == "localhost"

    def test_default_port(self):
        cfg = RedisConfig()
        assert cfg.port == 6379

    def test_default_db(self):
        cfg = RedisConfig()
        assert cfg.db == 0

    def test_connection_pool(self):
        cfg = RedisConfig()
        assert cfg.max_connections == 50
        assert cfg.socket_timeout == 5
        assert cfg.socket_connect_timeout == 5
        assert cfg.socket_keepalive is True

    def test_circuit_breaker_defaults(self):
        cfg = RedisConfig()
        assert cfg.failure_strategy == RedisFailureStrategy.DEGRADED
        assert cfg.circuit_breaker_threshold == 5
        assert cfg.circuit_breaker_timeout == 60
        assert cfg.circuit_breaker_half_open_requests == 3

    def test_local_cache_defaults(self):
        cfg = RedisConfig()
        assert cfg.enable_local_cache is True
        assert cfg.local_cache_ttl == 300
        assert cfg.local_cache_max_size == 1000

    def test_health_check_defaults(self):
        cfg = RedisConfig()
        assert cfg.health_check_interval == 30
        assert cfg.health_check_timeout == 5


# ---------------------------------------------------------------------------
# RateLimitConfig
# ---------------------------------------------------------------------------

class TestRateLimitConfig:
    """Tests for RateLimitConfig Pydantic model."""

    def test_default_rate_limit(self):
        cfg = RateLimitConfig()
        assert cfg.default_rate_limit == 100

    def test_default_burst_size(self):
        cfg = RateLimitConfig()
        assert cfg.default_burst_size == 20

    def test_auth_endpoint_limits(self):
        cfg = RateLimitConfig()
        login_limit = cfg.endpoint_limits["/api/v1/auth/login"]
        assert login_limit["limit"] == 5
        assert login_limit["burst"] == 2

    def test_ai_endpoint_limits(self):
        cfg = RateLimitConfig()
        ai_limit = cfg.endpoint_limits["/api/v1/ai/*"]
        assert ai_limit["limit"] == 20

    def test_rate_limiting_strategy(self):
        cfg = RateLimitConfig()
        assert cfg.use_ip_based is True
        assert cfg.use_user_based is True
        assert cfg.combine_limits is False

    def test_token_bucket_settings(self):
        cfg = RateLimitConfig()
        assert cfg.refill_rate == 1.0
        assert cfg.bucket_capacity == 100

    def test_response_headers(self):
        cfg = RateLimitConfig()
        assert cfg.include_headers is True
        assert cfg.header_prefix == "X-RateLimit"


# ---------------------------------------------------------------------------
# SecuritySettings — master configuration
# ---------------------------------------------------------------------------

class TestSecuritySettings:
    """Tests for SecuritySettings master model."""

    def test_environment_from_env_var(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "testing"}):
            settings = SecuritySettings()
            assert settings.environment == SecurityEnvironment.TESTING

    def test_has_cors_config(self):
        settings = SecuritySettings()
        assert isinstance(settings.cors, CORSConfig)

    def test_has_jwt_config(self):
        settings = SecuritySettings()
        assert isinstance(settings.jwt, JWTConfig)

    def test_has_redis_config(self):
        settings = SecuritySettings()
        assert isinstance(settings.redis, RedisConfig)

    def test_has_rate_limit_config(self):
        settings = SecuritySettings()
        assert isinstance(settings.rate_limit, RateLimitConfig)

    def test_security_headers_enabled(self):
        settings = SecuritySettings()
        assert settings.enable_security_headers is True
        assert settings.enable_csrf_protection is True
        assert settings.enable_xss_protection is True

    def test_frame_options(self):
        settings = SecuritySettings()
        assert settings.enable_frame_options is True
        assert settings.frame_options_value == "DENY"

    def test_csp_enabled(self):
        settings = SecuritySettings()
        assert settings.enable_csp is True
        assert "default-src" in settings.csp_directives

    def test_is_production_property(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            settings = SecuritySettings()
            assert settings.is_production is True
            assert settings.is_development is False

    def test_is_development_property(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            settings = SecuritySettings()
            assert settings.is_development is True
            assert settings.is_production is False

    def test_get_cors_config_method(self):
        settings = SecuritySettings()
        cors_config = settings.get_cors_config()
        assert "allow_origins" in cors_config
        assert "allow_methods" in cors_config
