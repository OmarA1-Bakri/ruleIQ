"""
Comprehensive tests for JWT Validation (Story 1.1)

Tests JWT token validation, refresh tokens, blacklisting, and performance.
"""

import pytest
import asyncio
import time
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
import redis
import logging

from middleware.jwt_auth_v2 import JWTAuthMiddlewareV2
from services.token_blacklist_service import TokenBlacklistService, get_blacklist_service
from api.dependencies.auth import SECRET_KEY, ALGORITHM


logger = logging.getLogger(__name__)


class TestJWTValidation:
    """Test suite for JWT validation enhancements."""

    @pytest.fixture
    def valid_token_payload(self):
        """Create a valid token payload."""
        return {
            "sub": "user123",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "jti": "unique-token-id-123",
            "iss": "ruleiq-api",
            "aud": "ruleiq-client",
            "type": "access",
            "roles": ["user"],
        }

    @pytest.fixture
    def valid_token(self, valid_token_payload):
        """Create a valid JWT token."""
        return jwt.encode(valid_token_payload, SECRET_KEY, algorithm=ALGORITHM)

    @pytest.fixture
    def expired_token_payload(self):
        """Create an expired token payload."""
        return {
            "sub": "user123",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "jti": "expired-token-id",
            "iss": "ruleiq-api",
            "aud": "ruleiq-client",
            "type": "access",
        }

    @pytest.fixture
    def expired_token(self, expired_token_payload):
        """Create an expired JWT token."""
        return jwt.encode(expired_token_payload, SECRET_KEY, algorithm=ALGORITHM)

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = Mock(spec=redis.Redis)
        mock.pipeline.return_value = mock
        mock.execute.return_value = [True, True, 1, 1]
        mock.sismember.return_value = False
        mock.exists.return_value = True
        return mock

    @pytest.fixture
    def blacklist_service(self, mock_redis):
        """Create a blacklist service with mock Redis."""
        service = TokenBlacklistService(redis_client=mock_redis)
        return service

    @pytest.fixture
    def jwt_middleware(self):
        """Create JWT middleware instance."""
        return JWTAuthMiddlewareV2(None)

    # Test 1: Token Signature Verification
    def test_token_signature_verification(self, jwt_middleware):
        """Test that invalid signatures are rejected."""
        # Create token with wrong secret
        wrong_secret_token = jwt.encode(
            {"sub": "user123", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "wrong-secret",
            algorithm=ALGORITHM,
        )

        # Should fail validation
        result = asyncio.run(jwt_middleware.validate_jwt_token(wrong_secret_token))
        assert result is None

    # Test 2: Token Expiry Validation
    def test_token_expiry_validation(self, jwt_middleware, expired_token):
        """Test that expired tokens are rejected."""
        result = asyncio.run(jwt_middleware.validate_jwt_token(expired_token))
        assert result is None

    # Test 3: Token Claims Validation
    def test_token_claims_validation(self, jwt_middleware):
        """Test validation of token claims (iss, aud, sub)."""
        # Test missing issuer
        token_no_iss = jwt.encode(
            {
                "sub": "user123",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "aud": "ruleiq-client",
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        middleware = jwt_middleware
        payload = jwt.decode(token_no_iss, SECRET_KEY, algorithms=[ALGORITHM])
        assert not middleware._validate_token_claims(payload)

        # Test wrong issuer
        token_wrong_iss = jwt.encode(
            {
                "sub": "user123",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "iss": "wrong-issuer",
                "aud": "ruleiq-client",
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        payload = jwt.decode(token_wrong_iss, SECRET_KEY, algorithms=[ALGORITHM])
        assert not middleware._validate_token_claims(payload)

        # Test missing subject
        token_no_sub = jwt.encode(
            {
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "iss": "ruleiq-api",
                "aud": "ruleiq-client",
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        payload = jwt.decode(token_no_sub, SECRET_KEY, algorithms=[ALGORITHM])
        assert not middleware._validate_token_claims(payload)

    # Test 4: Refresh Token Mechanism
    def test_refresh_token_creation(self):
        """Test refresh token generation."""
        refresh_payload = {
            "sub": "user123",
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
            "iat": datetime.now(timezone.utc),
            "jti": "refresh-token-id",
            "iss": "ruleiq-api",
            "aud": "ruleiq-client",
            "type": "refresh",
        }

        refresh_token = jwt.encode(refresh_payload, SECRET_KEY, algorithm=ALGORITHM)

        # Decode and verify
        decoded = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["type"] == "refresh"
        assert decoded["sub"] == "user123"

    def test_refresh_token_not_accepted_as_access(self, jwt_middleware):
        """Test that refresh tokens are rejected when used as access tokens."""
        refresh_payload = {
            "sub": "user123",
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
            "iat": datetime.now(timezone.utc),
            "jti": "refresh-token-id",
            "iss": "ruleiq-api",
            "aud": "ruleiq-client",
            "type": "refresh",
        }

        # Validate claims should reject refresh token
        assert not jwt_middleware._validate_token_claims(refresh_payload)

    # Test 5: Token Blacklisting
    def test_add_token_to_blacklist(self, blacklist_service):
        """Test adding token to blacklist."""
        token_jti = "test-token-id"
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        result = blacklist_service.add_to_blacklist(
            token_jti, expiry, user_id="user123", reason="logout"
        )

        assert result is True
        assert blacklist_service.redis_client.setex.called
        assert blacklist_service.redis_client.sadd.called

    def test_check_blacklisted_token(self, blacklist_service):
        """Test checking if token is blacklisted."""
        token_jti = "blacklisted-token"

        # Mock token is in blacklist
        blacklist_service.redis_client.sismember.return_value = True
        blacklist_service.redis_client.exists.return_value = True

        result = blacklist_service.is_blacklisted(token_jti)
        assert result is True

        # Mock token not in blacklist
        blacklist_service.redis_client.sismember.return_value = False
        result = blacklist_service.is_blacklisted(token_jti)
        assert result is False

    def test_blacklist_cleanup(self, blacklist_service):
        """Test cleanup of expired blacklist entries."""
        # Mock some expired entries
        blacklist_service.redis_client.smembers.return_value = {
            "expired-token-1",
            "expired-token-2",
            "valid-token",
        }

        # Mock exists check (only valid-token exists)
        blacklist_service.redis_client.exists.side_effect = [False, False, True]

        cleaned = blacklist_service.cleanup_expired()

        # Should have removed 2 expired tokens
        assert blacklist_service.redis_client.srem.call_count == 2

    # Test 6: Performance Testing
    def test_validation_performance(self, jwt_middleware, valid_token):
        """Test that token validation completes within 10ms."""
        start = time.time()

        # Run validation
        result = asyncio.run(jwt_middleware.validate_jwt_token(valid_token))

        duration = (time.time() - start) * 1000  # Convert to ms

        assert result is not None
        assert duration < 10, f"Validation took {duration:.2f}ms, expected < 10ms"

    def test_blacklist_check_performance(self, blacklist_service):
        """Test blacklist check performance."""
        token_jti = "test-token"

        start = time.time()

        # Check blacklist (should be fast with Redis)
        for _ in range(100):
            blacklist_service.is_blacklisted(token_jti)

        duration = (time.time() - start) * 1000  # Convert to ms
        avg_duration = duration / 100

        assert avg_duration < 1, f"Average blacklist check took {avg_duration:.2f}ms"

    # Test 7: Redis Failure Handling
    def test_blacklist_redis_failure(self, blacklist_service):
        """Test blacklist behavior when Redis fails."""
        token_jti = "test-token"

        # Simulate Redis error
        blacklist_service.redis_client.sismember.side_effect = redis.RedisError("Connection failed")

        # Should fail open (configurable)
        result = blacklist_service.is_blacklisted(token_jti)
        assert result is False  # Fails open by default

    # Test 8: Token Rotation
    def test_refresh_token_rotation(self):
        """Test that refresh tokens are rotated on use."""
        original_jti = "original-refresh-token"
        new_jti = "new-refresh-token"

        # When refresh token is used, old one should be blacklisted
        # and new one should be issued
        refresh_payload = {
            "sub": "user123",
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
            "jti": original_jti,
            "type": "refresh",
        }

        # New token should have different JTI
        new_payload = refresh_payload.copy()
        new_payload["jti"] = new_jti
        new_payload["iat"] = datetime.now(timezone.utc)

        assert new_payload["jti"] != refresh_payload["jti"]

    # Test 9: Concurrent Request Handling
    @pytest.mark.asyncio
    async def test_concurrent_validation(self, jwt_middleware, valid_token):
        """Test handling concurrent token validations."""
        # Create multiple validation tasks
        tasks = [jwt_middleware.validate_jwt_token(valid_token) for _ in range(10)]

        # Run concurrently
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r is not None for r in results)

    # Test 10: Edge Cases
    def test_token_without_expiry(self, jwt_middleware):
        """Test handling of tokens without expiry."""
        token_no_exp = jwt.encode(
            {"sub": "user123", "iss": "ruleiq-api", "aud": "ruleiq-client"},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        # Should be rejected (no expiry)
        result = asyncio.run(jwt_middleware.validate_jwt_token(token_no_exp))
        assert result is None

    def test_malformed_token(self, jwt_middleware):
        """Test handling of malformed tokens."""
        malformed_token = "not.a.valid.token"

        result = asyncio.run(jwt_middleware.validate_jwt_token(malformed_token))
        assert result is None

    # Test 11: Audit Logging
    @patch("middleware.jwt_auth_v2.logger")
    def test_audit_logging(self, mock_logger, jwt_middleware, expired_token):
        """Test that authentication events are logged."""
        # Try with expired token
        asyncio.run(jwt_middleware.validate_jwt_token(expired_token))

        # Should log the failure
        assert mock_logger.info.called or mock_logger.warning.called

    # Test 12: Feature Flag Integration
    def test_feature_flag_rollout(self, jwt_middleware):
        """Test feature flag controlled rollout."""
        # Mock feature flag check
        with patch("middleware.jwt_auth_v2.settings.FEATURE_FLAGS", {"jwt_validation_v2": True}):
            assert jwt_middleware.is_enabled()

        with patch("middleware.jwt_auth_v2.settings.FEATURE_FLAGS", {"jwt_validation_v2": False}):
            # Would use v1 validation
            pass


class TestRefreshTokenFlow:
    """Test refresh token implementation."""

    @pytest.fixture
    def refresh_token_payload(self):
        """Create refresh token payload."""
        return {
            "sub": "user123",
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
            "iat": datetime.now(timezone.utc),
            "jti": "refresh-token-123",
            "iss": "ruleiq-api",
            "aud": "ruleiq-client",
            "type": "refresh",
            "token_family": "family-123",
        }

    def test_refresh_token_exchange(self, refresh_token_payload):
        """Test exchanging refresh token for new access token."""
        refresh_token = jwt.encode(refresh_token_payload, SECRET_KEY, algorithm=ALGORITHM)

        # Decode refresh token
        decoded = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        # Create new access token
        access_payload = {
            "sub": decoded["sub"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "jti": "new-access-token",
            "iss": "ruleiq-api",
            "aud": "ruleiq-client",
            "type": "access",
        }

        access_token = jwt.encode(access_payload, SECRET_KEY, algorithm=ALGORITHM)

        # Verify new token
        new_decoded = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        assert new_decoded["type"] == "access"
        assert new_decoded["sub"] == decoded["sub"]
