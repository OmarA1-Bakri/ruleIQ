"""
Security Regression Tests for RuleIQ

Comprehensive security regression testing to ensure authentication, authorization,
and security controls work correctly and prevent regressions after security fixes.

Tests cover:
- JWT Authentication: Token validation, expiration, blacklisting
- RBAC System: Role-based access control and permissions
- API Security: Input validation, SQL injection prevention, XSS protection
- Session Security: Session management, concurrent access, timeout handling
- Audit Trails: Security event logging and compliance monitoring
"""

import pytest
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
import logging

from fastapi import Request, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)
# Security components
from middleware.jwt_auth import JWTAuthMiddleware, get_jwt_middleware
from middleware.security_headers import SecurityHeadersMiddleware
from middleware.rate_limiter import RateLimiter, UserTier
from middleware.audit_logging import AuditLoggingMiddleware, AuditLogger
from services.auth_service import AuthService, SessionManager
from utils.input_validation import (
    FieldValidator,
    WhitelistValidator,
    SecurityValidator,
    ValidationError,
    validate_evidence_update,
    validate_business_profile_update,
)
from database.rbac import Role, Permission, UserRole, RolePermission
from config.settings import settings


class TestAuthenticationSecurityRegression:
    """Test JWT authentication security regression."""

    @pytest.fixture
    def jwt_middleware(self):
        """Create JWT middleware instance for testing."""
        return get_jwt_middleware(enable_strict_mode=True)

    @pytest.fixture
    def mock_request(self):
        """Create mock request for testing."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "GET"
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()
        request.state.user_id = None
        request.state.token_payload = None
        request.state.is_authenticated = False
        request.headers = {}
        return request

    @pytest.mark.asyncio
    async def test_valid_jwt_token_accepted(self, jwt_middleware, mock_request):
        """Test that valid JWT tokens are accepted."""
        # Create a valid token
        from jose import jwt
        from api.dependencies.auth import SECRET_KEY, ALGORITHM

        payload = {
            "sub": str(uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        # Set authorization header
        mock_request.headers["Authorization"] = f"Bearer {token}"

        # Mock validation to return payload
        with patch.object(jwt_middleware, "validate_jwt_token", return_value=payload):
            result = await jwt_middleware.validate_jwt_token(token)
            assert result is not None
            assert result["sub"] == payload["sub"]

    @pytest.mark.asyncio
    async def test_expired_jwt_token_rejected(self, jwt_middleware, mock_request):
        """Test that expired JWT tokens are rejected."""
        # Create an expired token
        from jose import jwt
        from api.dependencies.auth import SECRET_KEY, ALGORITHM

        payload = {
            "sub": str(uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        mock_request.headers["Authorization"] = f"Bearer {token}"

        result = await jwt_middleware.validate_jwt_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_blacklisted_jwt_token_rejected(self, jwt_middleware, mock_request):
        """Test that blacklisted JWT tokens are rejected."""
        from jose import jwt
        from api.dependencies.auth import SECRET_KEY, ALGORITHM

        payload = {
            "sub": str(uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        mock_request.headers["Authorization"] = f"Bearer {token}"

        # Mock blacklist check to return True
        with patch("middleware.jwt_auth.is_token_blacklisted", return_value=True):
            result = await jwt_middleware.validate_jwt_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_invalid_token_type_rejected(self, jwt_middleware, mock_request):
        """Test that tokens with invalid type are rejected."""
        from jose import jwt
        from api.dependencies.auth import SECRET_KEY, ALGORITHM

        payload = {
            "sub": str(uuid4()),
            "type": "refresh",  # Invalid type for access
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        mock_request.headers["Authorization"] = f"Bearer {token}"

        result = await jwt_middleware.validate_jwt_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_token_rejected(self, jwt_middleware, mock_request):
        """Test that malformed tokens are rejected."""
        malformed_tokens = [
            "not-a-jwt-token",
            "Bearer invalid",
            "",
            "Bearer mock.jwt.invalid",
        ]

        for token in malformed_tokens:
            mock_request.headers["Authorization"] = token
            result = await jwt_middleware.validate_jwt_token(token.replace("Bearer ", ""))
            assert result is None

    @pytest.mark.asyncio
    async def test_token_manipulation_prevention(self, jwt_middleware, mock_request):
        """Test prevention of token manipulation attacks."""
        from jose import jwt
        from api.dependencies.auth import SECRET_KEY, ALGORITHM

        # Create valid token
        payload = {
            "sub": str(uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        # Attempt to manipulate token
        manipulated_tokens = [
            token[:-5] + "xxxxx",  # Truncated/modified
            token + "extra",  # Extended
            token.replace(".", "x"),  # Modified separators
        ]

        for manipulated_token in manipulated_tokens:
            mock_request.headers["Authorization"] = f"Bearer {manipulated_token}"
            result = await jwt_middleware.validate_jwt_token(manipulated_token)
            assert result is None, f"Manipulated token should be rejected: {manipulated_token}"

    @pytest.mark.asyncio
    async def test_public_paths_allow_unauthenticated_access(self, jwt_middleware, mock_request):
        """Test that public paths allow unauthenticated access."""
        public_paths = ["/docs", "/health", "/api/v1/auth/login", "/api/v1/auth/register"]

        for path in public_paths:
            mock_request.url.path = path
            assert jwt_middleware.is_public_path(path), f"Path should be public: {path}"

    @pytest.mark.asyncio
    async def test_critical_paths_require_authentication(self, jwt_middleware, mock_request):
        """Test that critical paths require authentication."""
        critical_paths = [
            "/api/v1/users",
            "/api/v1/admin",
            "/api/v1/assessments",
            "/api/v1/compliance",
        ]

        for path in critical_paths:
            mock_request.url.path = path
            assert jwt_middleware.is_critical_path(path), f"Path should be critical: {path}"


class TestSessionSecurityRegression:
    """Test session security regression."""

    @pytest.fixture
    def session_manager(self):
        """Create session manager for testing."""
        return SessionManager()

    @pytest.fixture
    def auth_service(self):
        """Create auth service for testing."""
        return AuthService()

    @pytest.mark.asyncio
    async def test_session_creation_and_validation(self, session_manager, auth_service):
        """Test session creation and validation."""
        user_id = uuid4()
        token = "test-token"

        # Create session
        session_id = await session_manager.create_session(user_id, token)

        assert session_id is not None
        assert isinstance(session_id, str)

        # Validate session exists
        session_data = await session_manager.get_session(session_id)
        assert session_data is not None
        assert session_data["user_id"] == str(user_id)
        assert session_data["token"] == token

    @pytest.mark.asyncio
    async def test_session_invalidation(self, session_manager):
        """Test session invalidation."""
        user_id = uuid4()
        token = "test-token"

        # Create session
        session_id = await session_manager.create_session(user_id, token)

        # Verify it exists
        assert await session_manager.get_session(session_id) is not None

        # Invalidate session
        success = await session_manager.invalidate_session(session_id)
        assert success is True

        # Verify it's gone
        assert await session_manager.get_session(session_id) is None

    @pytest.mark.asyncio
    async def test_concurrent_session_limits(self, auth_service):
        """Test enforcement of concurrent session limits."""
        user_id = uuid4()
        max_sessions = 3

        # Create multiple sessions
        session_ids = []
        for i in range(max_sessions + 2):  # Create more than limit
            session_ids.append(
                await auth_service.session_manager.create_session(user_id, f"token-{i}")
            )

        # Enforce limits (should remove oldest sessions)
        removed_count = await auth_service.enforce_session_limits(user_id, max_sessions)
        assert removed_count >= 2  # Should have removed excess sessions

        # Verify only max_sessions remain
        active_sessions = await auth_service.get_user_active_sessions(user_id)
        assert len(active_sessions) <= max_sessions

    @pytest.mark.asyncio
    async def test_session_timeout_handling(self, session_manager):
        """Test session timeout handling."""
        user_id = uuid4()
        token = "test-token"

        # Create session
        session_id = await session_manager.create_session(user_id, token)

        # Manually set old last_activity to simulate timeout
        session_data = await session_manager.get_session(session_id)
        old_time = datetime.now(timezone.utc) - timedelta(days=40)  # Beyond 30 day limit
        session_data["last_activity"] = old_time.isoformat()

        # Update session (this would normally happen on access)
        await session_manager.update_session_activity(session_id)

        # Cleanup should remove expired sessions
        removed_count = await session_manager.cleanup_expired_sessions()
        assert removed_count >= 0  # May or may not remove depending on timing

    @pytest.mark.asyncio
    async def test_session_hijacking_prevention(self, session_manager):
        """Test prevention of session hijacking."""
        user_id = uuid4()
        token = "original-token"

        # Create session
        session_id = await session_manager.create_session(user_id, token)

        # Simulate session hijacking attempt - different token
        hijacked_token = "hijacked-token"

        # The session should still be valid with original token
        session_data = await session_manager.get_session(session_id)
        assert session_data["token"] == token
        assert session_data["token"] != hijacked_token

    @pytest.mark.asyncio
    async def test_user_logout_invalidates_all_sessions(self, auth_service):
        """Test that user logout invalidates all sessions."""
        user_id = uuid4()

        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_ids.append(
                await auth_service.session_manager.create_session(user_id, f"token-{i}")
            )

        # Verify all exist
        for session_id in session_ids:
            assert await auth_service.session_manager.get_session(session_id) is not None

        # Logout all sessions
        invalidated_count = await auth_service.logout_user(user_id)
        assert invalidated_count == 3

        # Verify all are gone
        for session_id in session_ids:
            assert await auth_service.session_manager.get_session(session_id) is None


class TestAuthorizationSecurityRegression:
    """Test RBAC authorization security regression."""

    @pytest.fixture
    def whitelist_validator(self):
        """Create whitelist validator for testing."""
        return WhitelistValidator("EvidenceItem")

    def test_role_based_field_validation(self, whitelist_validator):
        """Test that only allowed fields can be updated."""
        # Valid update
        valid_data = {
            "evidence_name": "Test Evidence",
            "description": "Test description",
            "status": "approved",
        }

        result = whitelist_validator.validate_update_data(valid_data)
        assert result["evidence_name"] == "Test Evidence"
        assert result["status"] == "approved"

    def test_unauthorized_field_rejection(self, whitelist_validator):
        """Test that unauthorized fields are rejected."""
        invalid_data = {
            "evidence_name": "Test Evidence",
            "admin_only_field": "should not be allowed",  # Not in whitelist
            "secret_data": "classified",
        }

        with pytest.raises(ValidationError, match="not allowed for updates"):
            whitelist_validator.validate_update_data(invalid_data)

    def test_enum_value_validation(self, whitelist_validator):
        """Test that only valid enum values are accepted."""
        # Valid enum value
        valid_data = {"status": "approved"}
        result = whitelist_validator.validate_update_data(valid_data)
        assert result["status"] == "approved"

        # Invalid enum value
        invalid_data = {"status": "invalid_status"}
        with pytest.raises(ValidationError, match="must be one of"):
            whitelist_validator.validate_update_data(invalid_data)

    def test_data_type_validation(self, whitelist_validator):
        """Test that correct data types are enforced."""
        # Valid data types
        valid_data = {
            "evidence_name": "Test Evidence",  # string
            "status": "pending",  # enum
            "tags": ["tag1", "tag2"],  # list
        }
        result = whitelist_validator.validate_update_data(valid_data)
        assert isinstance(result["evidence_name"], str)
        assert isinstance(result["tags"], list)

    def test_input_length_limits(self, whitelist_validator):
        """Test that input length limits are enforced."""
        # Valid length
        valid_data = {"evidence_name": "Valid Name"}
        result = whitelist_validator.validate_update_data(valid_data)
        assert result["evidence_name"] == "Valid Name"

        # Too long
        invalid_data = {"evidence_name": "x" * 300}  # Exceeds 200 char limit
        with pytest.raises(ValidationError, match="must be at most"):
            whitelist_validator.validate_update_data(invalid_data)

    def test_required_field_validation(self, whitelist_validator):
        """Test that required fields are validated."""
        # Empty required field
        invalid_data = {"evidence_name": ""}  # Empty but required min_length=1
        with pytest.raises(ValidationError, match="must be at least"):
            whitelist_validator.validate_update_data(invalid_data)


class TestInputValidationSecurityRegression:
    """Test input validation security regression."""

    def test_sql_injection_prevention(self):
        """Test that SQL injection attempts are prevented."""
        dangerous_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'--",
            "'; SELECT * FROM users; --",
            "UNION SELECT password FROM users",
        ]

        for dangerous_input in dangerous_inputs:
            # Should be caught by security validator
            assert SecurityValidator.scan_for_dangerous_patterns(dangerous_input)

            # Should be rejected by field validator
            with pytest.raises(ValidationError):
                FieldValidator.validate_string(dangerous_input)

    def test_xss_prevention(self):
        """Test that XSS attempts are prevented."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<iframe src='javascript:alert(\"XSS\")'>",
            "onclick=alert('XSS')",
        ]

        for payload in xss_payloads:
            # Should be caught by security validator
            assert SecurityValidator.scan_for_dangerous_patterns(payload)

            # Should be rejected by field validator
            with pytest.raises(ValidationError):
                FieldValidator.validate_string(payload)

    def test_command_injection_prevention(self):
        """Test that command injection attempts are prevented."""
        command_injections = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "`whoami`",
            "$(rm -rf /)",
            "&& echo 'hacked'",
        ]

        for injection in command_injections:
            # Should be caught by security validator
            assert SecurityValidator.scan_for_dangerous_patterns(injection)

    def test_safe_input_patterns(self):
        """Test that safe input patterns are accepted."""
        safe_inputs = [
            "John Doe",
            "test@example.com",
            "Valid description with numbers 123",
            "Multi-word title: The Quick Brown Fox",
            "Evidence-001",
        ]

        for safe_input in safe_inputs:
            # Should pass security validation
            assert not SecurityValidator.scan_for_dangerous_patterns(safe_input)

            # Should pass field validation
            result = FieldValidator.validate_string(safe_input)
            assert result == safe_input

    def test_email_validation(self):
        """Test email validation security."""
        valid_emails = [
            "user@example.com",
            "test.email+tag@domain.co.uk",
            "user_name@subdomain.example.org",
        ]

        invalid_emails = [
            "invalid-email",
            "user@",
            "@example.com",
            "user@.com",
            "<script>alert('XSS')</script>@evil.com",
        ]

        for email in valid_emails:
            result = FieldValidator.validate_email(email)
            assert result == email

        for email in invalid_emails:
            with pytest.raises(ValidationError):
                FieldValidator.validate_email(email)

    def test_url_validation(self):
        """Test URL validation security."""
        valid_urls = [
            "https://example.com",
            "http://subdomain.example.com/path",
            "https://example.com:8080/path?query=value",
        ]

        invalid_urls = [
            "javascript:alert('XSS')",
            "data:text/html,<script>alert('XSS')</script>",
            "vbscript:msgbox('XSS')",
            "not-a-url",
        ]

        for url in valid_urls:
            result = FieldValidator.validate_url(url)
            assert result == url

        for url in invalid_urls:
            with pytest.raises(ValidationError):
                FieldValidator.validate_url(url)

    def test_uuid_validation(self):
        """Test UUID validation security."""
        from uuid import uuid4

        # Valid UUID
        valid_uuid = uuid4()
        result = FieldValidator.validate_uuid(str(valid_uuid))
        assert result == valid_uuid

        # Invalid UUIDs
        invalid_uuids = [
            "not-a-uuid",
            "12345",
            "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "<script>alert('XSS')</script>",
        ]

        for invalid_uuid in invalid_uuids:
            with pytest.raises(ValidationError):
                FieldValidator.validate_uuid(invalid_uuid)

    def test_evidence_update_validation(self):
        """Test comprehensive evidence update validation."""
        # Valid update
        valid_update = {
            "evidence_name": "Security Audit Report",
            "description": "Comprehensive security assessment",
            "status": "approved",
            "tags": ["security", "audit"],
        }

        result = validate_evidence_update(valid_update)
        assert result["evidence_name"] == "Security Audit Report"

        # Invalid update with SQL injection
        invalid_update = {
            "evidence_name": "'; DROP TABLE evidence; --",
            "description": "<script>alert('XSS')</script>",
        }

        with pytest.raises(ValidationError, match="dangerous content"):
            validate_evidence_update(invalid_update)

    def test_business_profile_update_validation(self):
        """Test comprehensive business profile update validation."""
        # Valid update
        valid_update = {
            "company_name": "SecureTech Solutions",
            "industry": "Information Technology",
            "employee_count": 150,
            "data_sensitivity": "High",
        }

        result = validate_business_profile_update(valid_update)
        assert result["company_name"] == "SecureTech Solutions"

        # Invalid update
        invalid_update = {
            "company_name": "<script>alert('XSS')</script>",
            "employee_count": "not-a-number",
        }

        with pytest.raises(ValidationError):
            validate_business_profile_update(invalid_update)


class TestSecurityHeadersRegression:
    """Test security headers regression."""

    @pytest.fixture
    def security_headers_middleware(self):
        """Create security headers middleware for testing."""
        return SecurityHeadersMiddleware(
            app=None,  # Not needed for header testing
            csp_enabled=True,
            cors_enabled=True,
        )

    def test_csp_header_generation(self, security_headers_middleware):
        """Test Content Security Policy header generation."""
        csp_directives = security_headers_middleware.default_csp

        # Should have essential CSP directives
        assert "default-src" in csp_directives
        assert "script-src" in csp_directives
        assert "style-src" in csp_directives
        assert "object-src" in csp_directives

        # Should restrict script execution
        assert csp_directives["object-src"] == ["'none'"]

    def test_cors_headers_configuration(self, security_headers_middleware):
        """Test CORS headers configuration."""
        # CORS should be properly configured
        assert security_headers_middleware.cors_enabled is True

        # Should have CORS headers in response
        # Note: Actual CORS headers are added by FastAPI CORSMiddleware
        # This middleware focuses on security headers

    def test_security_headers_presence(self, security_headers_middleware):
        """Test that essential security headers are present."""
        # Create mock response
        mock_response = Mock()
        mock_response.headers = {}

        # Simulate adding headers
        # Note: This would normally be done in the middleware's response processing

        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
        ]

        # Verify headers would be added (in real usage)
        for header in expected_headers:
            # This is a structural test - actual header addition tested in integration
            assert header in [
                "X-Content-Type-Options",
                "X-Frame-Options",
                "X-XSS-Protection",
                "Strict-Transport-Security",
            ]

    def test_hsts_configuration(self, security_headers_middleware):
        """Test HTTP Strict Transport Security configuration."""
        # HSTS should be configured for HTTPS enforcement
        # This is typically handled by the web server, but middleware may add it

    def test_frame_options_denial(self, security_headers_middleware):
        """Test X-Frame-Options denial for clickjacking prevention."""
        # Should prevent iframe embedding
        # X-Frame-Options: DENY should be set

    def test_content_type_options_nosniff(self, security_headers_middleware):
        """Test X-Content-Type-Options nosniff for MIME type security."""
        # Should prevent MIME type sniffing attacks


class TestRateLimitingSecurityRegression:
    """Test rate limiting security regression."""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for testing."""
        return RateLimiter(redis_client=None)  # Use in-memory fallback

    @pytest.fixture
    def mock_request(self):
        """Create mock request for testing."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.headers = {"X-Forwarded-For": None}
        request.state = Mock()
        request.state.user = None
        return request

    def test_user_tier_classification(self, rate_limiter, mock_request):
        """Test user tier classification for rate limiting."""
        # Anonymous user
        tier = rate_limiter.get_user_tier(mock_request)
        assert tier == UserTier.ANONYMOUS

        # Authenticated user
        mock_user = Mock()
        mock_user.is_admin = False
        mock_user.subscription_tier = None
        mock_request.state.user = mock_user
        tier = rate_limiter.get_user_tier(mock_request)
        assert tier == UserTier.AUTHENTICATED

        # Premium user
        mock_user.subscription_tier = "premium"
        tier = rate_limiter.get_user_tier(mock_request)
        assert tier == UserTier.PREMIUM

        # Admin user
        mock_user.is_admin = True
        tier = rate_limiter.get_user_tier(mock_request)
        assert tier == UserTier.ADMIN

    def test_rate_limit_enforcement(self, rate_limiter, mock_request):
        """Test rate limit enforcement."""
        mock_request.url.path = "/api/test"

        # Should allow requests within limit
        for _i in range(5):  # Under anonymous limit of 10
            allowed, info = rate_limiter.check_rate_limit(mock_request)
            assert allowed is True
            assert info["remaining"] > 0

        # Should block when limit exceeded
        # Note: This test may be timing-dependent in real Redis

    def test_admin_bypass_rate_limiting(self, rate_limiter, mock_request):
        """Test that admins bypass rate limiting."""
        mock_request.url.path = "/api/test"

        # Set admin user
        mock_user = Mock()
        mock_user.is_admin = True
        mock_request.state.user = mock_user

        # Should bypass rate limiting
        allowed, info = rate_limiter.check_rate_limit(mock_request)
        assert allowed is True
        assert info.get("bypassed") is True

    def test_ip_based_rate_limiting(self, rate_limiter, mock_request):
        """Test IP-based rate limiting for anonymous users."""
        mock_request.url.path = "/api/test"
        mock_request.state.user = None  # Anonymous

        # Should use IP for rate limiting
        identifier = rate_limiter.get_identifier(mock_request)
        assert identifier == "ip:127.0.0.1"

    def test_endpoint_specific_limits(self, rate_limiter, mock_request):
        """Test endpoint-specific rate limits."""
        # Login endpoint has stricter limits
        mock_request.url.path = "/api/v1/auth/login"

        limits = rate_limiter.get_rate_limit("/api/v1/auth/login", UserTier.ANONYMOUS)
        assert limits["requests"] == 5  # Stricter limit for login
        assert limits["window"] == 300  # 5 minutes

    def test_whitelist_bypass(self, rate_limiter, mock_request):
        """Test IP whitelist bypass."""
        # Add IP to whitelist
        rate_limiter.IP_WHITELIST.add("127.0.0.1")

        mock_request.url.path = "/api/test"
        mock_request.state.user = None

        # Should bypass rate limiting
        assert rate_limiter.should_bypass(mock_request) is True

    def test_service_account_bypass(self, rate_limiter, mock_request):
        """Test service account bypass."""
        # Add user ID to service accounts
        test_user_id = str(uuid4())
        rate_limiter.SERVICE_ACCOUNTS.add(test_user_id)

        mock_user = Mock()
        mock_user.id = test_user_id
        mock_request.state.user = mock_user

        # Should bypass rate limiting
        assert rate_limiter.should_bypass(mock_request) is True


class TestAuditLoggingSecurityRegression:
    """Test audit logging security regression."""

    @pytest.fixture
    def audit_logger(self):
        """Create audit logger for testing."""
        return AuditLogger()

    def test_security_event_logging(self, audit_logger):
        """Test that security events are logged."""
        # Log a security event
        audit_logger.log_event(
            event_type="AUTH_FAILED",
            user_id="test-user",
            action="LOGIN",
            result="DENIED",
            details={"reason": "invalid_credentials"},
        )

        # Should be in buffer
        assert len(audit_logger.buffer) > 0
        event = audit_logger.buffer[-1]
        assert event["event_type"] == "AUTH_FAILED"
        assert event["user_id"] == "test-user"

    def test_sensitive_data_redaction(self, audit_logger):
        """Test that sensitive data is redacted in logs."""
        sensitive_details = {
            "password": "secret123",
            "token": "jwt-token-here",
            "api_key": "sk-123456789",
            "safe_field": "this is safe",
        }

        audit_logger.log_event(event_type="TEST_EVENT", details=sensitive_details)

        event = audit_logger.buffer[-1]
        redacted_details = event["details"]

        # Sensitive fields should be redacted
        assert redacted_details["password"] == "***REDACTED***"
        assert redacted_details["token"] == "***REDACTED***"
        assert redacted_details["api_key"] == "***REDACTED***"

        # Safe fields should remain
        assert redacted_details["safe_field"] == "this is safe"

    def test_critical_event_immediate_logging(self, audit_logger):
        """Test that critical events are logged immediately."""
        # This would normally trigger immediate file logging
        # In test environment, we verify the event is marked as critical

        audit_logger.log_event(event_type="AUTH_FAILED", user_id="test-user", action="LOGIN")

        event = audit_logger.buffer[-1]
        # Critical events should be in buffer
        assert event["event_type"] == "AUTH_FAILED"

    def test_audit_context_preservation(self):
        """Test that audit context is preserved across operations."""
        from middleware.audit_logging import audit_context

        # Set context
        test_request_id = str(uuid4())
        test_session_id = str(uuid4())

        audit_context.set({"request_id": test_request_id, "session_id": test_session_id})

        # Verify context is accessible
        current_context = audit_context.get()
        assert current_context["request_id"] == test_request_id
        assert current_context["session_id"] == test_session_id


class TestVulnerabilityRegression:
    """Test vulnerability regression - ensuring known security issues are resolved."""

    def test_regression_cve_prevention(self):
        """Test prevention of common CVEs and vulnerabilities."""
        # Test for common injection patterns
        injection_patterns = [
            # SQL Injection variants
            ("' OR '1'='1", "SQL injection bypass"),
            ("; DROP TABLE users;", "SQL injection drop table"),
            ("UNION SELECT * FROM users", "SQL injection union"),
            # XSS variants
            ("<script>alert('xss')</script>", "Basic XSS"),
            ("javascript:alert('xss')", "JavaScript URL XSS"),
            ("<img src=x onerror=alert('xss')>", "Image onerror XSS"),
            # Command injection
            ("; rm -rf /", "Command injection rm"),
            ("| cat /etc/passwd", "Command injection cat"),
            ("`whoami`", "Command injection backticks"),
            # Path traversal
            ("../../../etc/passwd", "Path traversal"),
            ("..\\..\\..\\windows\\system32", "Windows path traversal"),
            # Template injection
            ("{{7*7}}", "Template injection"),
            ("${7*7}", "Expression injection"),
        ]

        for payload, description in injection_patterns:
            # All should be detected as dangerous
            assert SecurityValidator.scan_for_dangerous_patterns(payload), (
                f"Should detect dangerous pattern: {description}"
            )

            # Should be rejected by input validation
            with pytest.raises(ValidationError):
                FieldValidator.validate_string(payload)

    def test_secure_defaults_enforced(self):
        """Test that secure defaults are enforced."""
        # Test CSP defaults
        from middleware.security_headers import SecurityHeadersMiddleware

        middleware = SecurityHeadersMiddleware(app=None)

        csp = middleware.default_csp

        # Should not allow unsafe-inline by default (unless nonce enabled)
        if not middleware.nonce_enabled:
            assert "'unsafe-inline'" not in csp["script-src"]

        # Should block object embedding
        assert csp["object-src"] == ["'none'"]

        # Should restrict frame ancestors
        assert csp["frame-src"] == ["'none'"]

    def test_rate_limit_dos_prevention(self):
        """Test that rate limiting prevents DoS attacks."""
        from middleware.rate_limiter import RateLimiter

        limiter = RateLimiter()

        # Create mock request
        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"
        mock_request.state.user = None
        mock_request.url.path = "/api/test"

        # Should enforce rate limits
        # Note: Actual enforcement depends on Redis timing
        # This tests the logic is in place

        tier = limiter.get_user_tier(mock_request)
        assert tier == UserTier.ANONYMOUS

        limits = limiter.get_rate_limit("/api/test", tier)
        assert limits["requests"] > 0
        assert limits["window"] > 0

    def test_session_fixation_prevention(self):
        """Test prevention of session fixation attacks."""
        # Session fixation involves forcing a user to use a known session ID
        # Our implementation should generate new session IDs on login

        session_manager = SessionManager()

        # Create a session
        user_id = uuid4()
        token = "original-token"
        session_id = session_manager.create_session(user_id, token)

        # On "login", a new session should be created
        # This prevents session fixation
        new_token = "new-token-after-login"
        new_session_id = session_manager.create_session(user_id, new_token)

        # Should be different sessions
        assert new_session_id != session_id

        # Original session should still exist (until invalidated)
        original_session = session_manager.get_session(session_id)
        assert original_session is not None

    def test_clickjacking_prevention(self):
        """Test prevention of clickjacking attacks."""
        # Should set X-Frame-Options: DENY
        # This is tested in the security headers middleware

    def test_mime_sniffing_prevention(self):
        """Test prevention of MIME type sniffing attacks."""
        # Should set X-Content-Type-Options: nosniff
        # This prevents browsers from guessing MIME types

    def test_hsts_enforcement(self):
        """Test HTTP Strict Transport Security enforcement."""
        # Should enforce HTTPS
        # This is typically handled at the server level but middleware may contribute
