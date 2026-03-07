"""
Comprehensive tests for CORS Configuration (Story 1.3)

Tests CORS middleware with environment-specific configuration and security.
"""

import pytest
import os
from unittest.mock import Mock, patch
from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware

from middleware.cors_config import CORSConfig, EnhancedCORSMiddleware, setup_cors


class TestCORSConfig:
    """Test suite for CORS configuration."""

    @pytest.fixture
    def dev_config(self):
        """Create development CORS config."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            return CORSConfig()

    @pytest.fixture
    def staging_config(self):
        """Create staging CORS config."""
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}):
            return CORSConfig()

    @pytest.fixture
    def prod_config(self):
        """Create production CORS config."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            return CORSConfig()

    # Test 1: Environment Detection
    def test_environment_detection_dev(self):
        """Test development environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = CORSConfig()
            assert config.environment == "development"

    def test_environment_detection_prod(self):
        """Test production environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = CORSConfig()
            assert config.environment == "production"

    def test_environment_detection_staging(self):
        """Test staging environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}):
            config = CORSConfig()
            assert config.environment == "staging"

    def test_environment_mapping(self):
        """Test environment name mapping."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            config = CORSConfig()
            assert config.environment == "production"

        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            config = CORSConfig()
            assert config.environment == "development"

    # Test 2: Origin Configuration
    def test_dev_origins(self, dev_config):
        """Test development allowed origins."""
        assert "http://localhost:3000" in dev_config.allowed_origins
        assert "http://localhost:3001" in dev_config.allowed_origins
        assert "http://127.0.0.1:3000" in dev_config.allowed_origins

    def test_staging_origins(self, staging_config):
        """Test staging allowed origins."""
        assert "https://staging.ruleiq.com" in staging_config.allowed_origins
        assert "https://staging-app.ruleiq.com" in staging_config.allowed_origins

    def test_prod_origins(self, prod_config):
        """Test production allowed origins."""
        assert "https://app.ruleiq.com" in prod_config.allowed_origins
        assert "https://www.ruleiq.com" in prod_config.allowed_origins
        assert "https://ruleiq.com" in prod_config.allowed_origins

    def test_env_override_origins(self):
        """Test environment variable override for origins."""
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "development", "CORS_ORIGINS": '["http://custom.local:3000"]'},
        ):
            config = CORSConfig()
            assert config.allowed_origins == ["http://custom.local:3000"]

    def test_env_override_comma_separated(self):
        """Test comma-separated origins from environment."""
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "development", "CORS_ORIGINS": "http://app1.local,http://app2.local"},
        ):
            config = CORSConfig()
            assert "http://app1.local" in config.allowed_origins
            assert "http://app2.local" in config.allowed_origins

    # Test 3: Security Validation
    def test_no_wildcards_in_production(self):
        """Test that wildcards are not allowed in production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "CORS_ORIGINS": '["*"]'}):
            with pytest.raises(ValueError, match="Insecure origin"):
                CORSConfig()

    def test_no_http_in_production(self):
        """Test that HTTP origins are not allowed in production."""
        with patch.dict(
            os.environ, {"ENVIRONMENT": "production", "CORS_ORIGINS": '["http://insecure.com"]'}
        ):
            with pytest.raises(ValueError, match="Insecure origin"):
                CORSConfig()

    def test_wildcard_warning_in_dev(self, caplog):
        """Test warning for wildcard in development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "CORS_ORIGINS": '["*"]'}):
            config = CORSConfig()
            assert "Wildcard origin" in caplog.text

    def test_invalid_origin_format(self):
        """Test validation of origin format."""
        with patch.dict(
            os.environ, {"ENVIRONMENT": "development", "CORS_ORIGINS": '["not-a-valid-url"]'}
        ):
            with pytest.raises(ValueError, match="Invalid origin"):
                CORSConfig()

    # Test 4: Origin Checking
    def test_is_origin_allowed_exact_match(self, dev_config):
        """Test exact origin matching."""
        assert dev_config.is_origin_allowed("http://localhost:3000") is True
        assert dev_config.is_origin_allowed("http://localhost:4000") is False

    def test_is_origin_allowed_empty(self, dev_config):
        """Test empty origin is rejected."""
        assert dev_config.is_origin_allowed("") is False
        assert dev_config.is_origin_allowed(None) is False

    def test_is_origin_allowed_subdomain_pattern(self):
        """Test subdomain pattern matching."""
        config = CORSConfig()
        config.allowed_origins = ["*.example.com"]

        assert config.is_origin_allowed("https://app.example.com") is True
        assert config.is_origin_allowed("https://api.example.com") is True
        assert config.is_origin_allowed("https://example.com") is False
        assert config.is_origin_allowed("https://other.com") is False

    # Test 5: Headers Configuration
    def test_allowed_headers(self, dev_config):
        """Test allowed request headers."""
        assert "Authorization" in dev_config.ALLOWED_HEADERS
        assert "Content-Type" in dev_config.ALLOWED_HEADERS
        assert "X-CSRF-Token" in dev_config.ALLOWED_HEADERS

    def test_exposed_headers(self, dev_config):
        """Test exposed response headers."""
        # Pagination headers
        assert "X-Total-Count" in dev_config.EXPOSED_HEADERS
        assert "X-Page-Count" in dev_config.EXPOSED_HEADERS

        # Rate limit headers (from Story 1.2)
        assert "X-RateLimit-Limit" in dev_config.EXPOSED_HEADERS
        assert "X-RateLimit-Remaining" in dev_config.EXPOSED_HEADERS
        assert "X-RateLimit-Reset" in dev_config.EXPOSED_HEADERS

    def test_allowed_methods(self, dev_config):
        """Test allowed HTTP methods."""
        assert "GET" in dev_config.ALLOWED_METHODS
        assert "POST" in dev_config.ALLOWED_METHODS
        assert "PUT" in dev_config.ALLOWED_METHODS
        assert "DELETE" in dev_config.ALLOWED_METHODS
        assert "OPTIONS" in dev_config.ALLOWED_METHODS

    # Test 6: CORS Headers Generation
    def test_get_cors_headers_allowed(self, dev_config):
        """Test CORS headers for allowed origin."""
        headers = dev_config.get_cors_headers("http://localhost:3000")

        assert headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        assert headers["Vary"] == "Origin"
        assert headers["Access-Control-Allow-Credentials"] == "true"

    def test_get_cors_headers_not_allowed(self, dev_config):
        """Test no CORS headers for disallowed origin."""
        headers = dev_config.get_cors_headers("http://evil.com")
        assert headers == {}

    def test_get_preflight_headers(self, dev_config):
        """Test preflight response headers."""
        headers = dev_config.get_preflight_headers("http://localhost:3000")

        assert "Access-Control-Allow-Origin" in headers
        assert "Access-Control-Allow-Methods" in headers
        assert "Access-Control-Allow-Headers" in headers
        assert "Access-Control-Expose-Headers" in headers
        assert "Access-Control-Max-Age" in headers
        assert headers["Access-Control-Max-Age"] == "3600"

    # Test 7: Credentials Support
    def test_credentials_enabled(self, dev_config):
        """Test that credentials are supported."""
        assert dev_config.allow_credentials is True

        headers = dev_config.get_cors_headers("http://localhost:3000")
        assert headers["Access-Control-Allow-Credentials"] == "true"

    # Test 8: Middleware Configuration
    def test_to_middleware_kwargs(self, dev_config):
        """Test middleware configuration generation."""
        kwargs = dev_config.to_middleware_kwargs()

        assert kwargs["allow_origins"] == dev_config.allowed_origins
        assert kwargs["allow_credentials"] is True
        assert kwargs["allow_methods"] == dev_config.ALLOWED_METHODS
        assert kwargs["allow_headers"] == dev_config.ALLOWED_HEADERS
        assert kwargs["expose_headers"] == dev_config.EXPOSED_HEADERS
        assert kwargs["max_age"] == 3600


class TestEnhancedCORSMiddleware:
    """Test enhanced CORS middleware."""

    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app."""
        return Mock()

    @pytest.fixture
    def middleware(self, mock_app):
        """Create enhanced CORS middleware."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            return EnhancedCORSMiddleware(mock_app)

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.headers = {"origin": "http://localhost:3000"}
        request.client = Mock()
        request.client.host = "192.168.1.1"
        return request

    @pytest.fixture
    async def mock_call_next(self):
        """Create mock call_next function."""

        async def call_next(request):
            response = Response()
            response.headers = {}
            return response

        return call_next

    # Test 9: Preflight Handling
    def test_handle_preflight_allowed(self, middleware):
        """Test preflight handling for allowed origin."""
        request = Mock(spec=Request)
        request.headers = {"origin": "http://localhost:3000"}

        response = middleware._handle_preflight(request)

        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers

    def test_handle_preflight_not_allowed(self, middleware):
        """Test preflight handling for disallowed origin."""
        request = Mock(spec=Request)
        request.headers = {"origin": "http://evil.com"}

        response = middleware._handle_preflight(request)

        assert response.status_code == 403

    def test_handle_preflight_no_origin(self, middleware):
        """Test preflight handling without origin."""
        request = Mock(spec=Request)
        request.headers = {}

        response = middleware._handle_preflight(request)

        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers

    # Test 10: CORS Violation Logging
    def test_log_cors_violation(self, middleware):
        """Test CORS violation logging."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.headers = {"origin": "http://evil.com", "user-agent": "TestAgent"}
        request.client = Mock()
        request.client.host = "192.168.1.1"

        middleware._log_cors_violation(request, "http://evil.com")

        assert middleware.violation_count == 1
        assert len(middleware.last_violations) == 1

        violation = middleware.last_violations[0]
        assert violation["origin"] == "http://evil.com"
        assert violation["path"] == "/api/v1/test"
        assert violation["client_ip"] == "192.168.1.1"

    # Test 11: Main Request Processing
    @pytest.mark.asyncio
    async def test_process_allowed_request(self, middleware, mock_request, mock_call_next):
        """Test processing request with allowed origin."""
        response = await middleware(mock_request, mock_call_next)

        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        assert response.headers["Vary"] == "Origin"

    @pytest.mark.asyncio
    async def test_process_disallowed_request(self, middleware, mock_call_next):
        """Test processing request with disallowed origin."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.headers = {"origin": "http://evil.com"}
        request.client = Mock()
        request.client.host = "192.168.1.1"

        response = await middleware(request, mock_call_next)

        assert "Access-Control-Allow-Origin" not in response.headers
        assert middleware.violation_count == 1

    @pytest.mark.asyncio
    async def test_process_options_request(self, middleware, mock_call_next):
        """Test OPTIONS request handling."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "OPTIONS"
        request.headers = {"origin": "http://localhost:3000"}

        # Mock _handle_preflight
        middleware._handle_preflight = Mock(return_value=Response(status_code=200))

        response = await middleware(request, mock_call_next)

        middleware._handle_preflight.assert_called_once_with(request)

    # Test 12: Statistics
    def test_get_stats(self, middleware):
        """Test getting CORS statistics."""
        # Add some violations
        middleware.violation_count = 5
        middleware.last_violations = [
            {"origin": "http://evil1.com"},
            {"origin": "http://evil2.com"},
        ]

        stats = middleware.get_stats()

        assert stats["violation_count"] == 5
        assert len(stats["recent_violations"]) == 2
        assert stats["environment"] == "development"
        assert "allowed_origins" in stats


class TestCORSIntegration:
    """Test CORS integration with FastAPI."""

    def test_setup_cors(self):
        """Test CORS setup with FastAPI app."""
        app = Mock()
        app.add_middleware = Mock()

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            setup_cors(app)

        # Should add CORSMiddleware
        app.add_middleware.assert_called_once()
        call_args = app.add_middleware.call_args

        assert call_args[0][0] == CORSMiddleware
        kwargs = call_args[1]

        assert "allow_origins" in kwargs
        assert "allow_credentials" in kwargs
        assert kwargs["allow_credentials"] is True
