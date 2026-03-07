"""
Unit tests for services/api_key_management.py — APIKeyManager pure methods.

Tests the helper/pure methods that don't require database interaction.
DB-dependent methods are tested with mocks.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.api_key_management import (
    APIKeyManager,
    APIKeyStatus,
    APIKeyType,
    APIKeyMetadata,
)


# ---------------------------------------------------------------------------
# APIKeyStatus / APIKeyType enums
# ---------------------------------------------------------------------------

class TestEnums:
    """Tests for API key enums."""

    def test_api_key_status_values(self):
        assert APIKeyStatus.ACTIVE == "active"
        assert APIKeyStatus.SUSPENDED == "suspended"
        assert APIKeyStatus.REVOKED == "revoked"
        assert APIKeyStatus.EXPIRED == "expired"

    def test_api_key_type_values(self):
        assert APIKeyType.STANDARD == "standard"
        assert APIKeyType.PREMIUM == "premium"
        assert APIKeyType.ENTERPRISE == "enterprise"
        assert APIKeyType.INTERNAL == "internal"


# ---------------------------------------------------------------------------
# APIKeyMetadata dataclass
# ---------------------------------------------------------------------------

class TestAPIKeyMetadata:
    """Tests for APIKeyMetadata dataclass."""

    def test_create_metadata(self):
        from datetime import datetime, timezone
        md = APIKeyMetadata(
            key_id="ak_test123",
            organization_id="org_1",
            organization_name="Test Org",
            key_type=APIKeyType.STANDARD,
            status=APIKeyStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            expires_at=None,
            last_used_at=None,
            allowed_ips=[],
            allowed_origins=[],
            scopes=["read:assessments"],
            rate_limit=100,
            rate_limit_window=60,
            metadata={},
        )
        assert md.key_id == "ak_test123"
        assert md.status == APIKeyStatus.ACTIVE


# ---------------------------------------------------------------------------
# Pure helper methods (no DB needed)
# ---------------------------------------------------------------------------

class TestAPIKeyManagerHelpers:
    """Tests for APIKeyManager helper methods."""

    def _make_manager(self):
        return APIKeyManager(
            db_session=AsyncMock(),
            redis_client=AsyncMock(),
        )

    def test_hash_key_secret_deterministic(self):
        mgr = self._make_manager()
        h1 = mgr._hash_key_secret("my-secret")
        h2 = mgr._hash_key_secret("my-secret")
        assert h1 == h2

    def test_hash_key_secret_different_inputs(self):
        mgr = self._make_manager()
        h1 = mgr._hash_key_secret("secret-a")
        h2 = mgr._hash_key_secret("secret-b")
        assert h1 != h2

    def test_verify_key_secret_correct(self):
        mgr = self._make_manager()
        hashed = mgr._hash_key_secret("my-secret")
        assert mgr._verify_key_secret("my-secret", hashed) is True

    def test_verify_key_secret_wrong(self):
        mgr = self._make_manager()
        hashed = mgr._hash_key_secret("my-secret")
        assert mgr._verify_key_secret("wrong-secret", hashed) is False

    def test_default_rate_limit_standard(self):
        mgr = self._make_manager()
        assert mgr._get_default_rate_limit(APIKeyType.STANDARD) == 100

    def test_default_rate_limit_premium(self):
        mgr = self._make_manager()
        assert mgr._get_default_rate_limit(APIKeyType.PREMIUM) == 500

    def test_default_rate_limit_enterprise(self):
        mgr = self._make_manager()
        assert mgr._get_default_rate_limit(APIKeyType.ENTERPRISE) == 2000

    def test_default_rate_limit_internal(self):
        mgr = self._make_manager()
        assert mgr._get_default_rate_limit(APIKeyType.INTERNAL) == 10000

    def test_default_scopes_standard(self):
        mgr = self._make_manager()
        scopes = mgr._get_default_scopes(APIKeyType.STANDARD)
        assert "read:assessments" in scopes
        assert "read:compliance" in scopes

    def test_default_scopes_enterprise(self):
        mgr = self._make_manager()
        scopes = mgr._get_default_scopes(APIKeyType.ENTERPRISE)
        assert "read:*" in scopes
        assert "write:*" in scopes

    def test_default_scopes_internal(self):
        mgr = self._make_manager()
        scopes = mgr._get_default_scopes(APIKeyType.INTERNAL)
        assert "*" in scopes


# ---------------------------------------------------------------------------
# IP address checking
# ---------------------------------------------------------------------------

class TestIPChecking:
    """Tests for _check_ip_allowed."""

    def _make_manager(self):
        return APIKeyManager(
            db_session=AsyncMock(),
            redis_client=AsyncMock(),
        )

    def test_exact_ip_match(self):
        mgr = self._make_manager()
        assert mgr._check_ip_allowed("192.168.1.1", ["192.168.1.1"]) is True

    def test_exact_ip_no_match(self):
        mgr = self._make_manager()
        assert mgr._check_ip_allowed("192.168.1.2", ["192.168.1.1"]) is False

    def test_cidr_match(self):
        mgr = self._make_manager()
        assert mgr._check_ip_allowed("10.0.0.50", ["10.0.0.0/24"]) is True

    def test_cidr_no_match(self):
        mgr = self._make_manager()
        assert mgr._check_ip_allowed("10.0.1.50", ["10.0.0.0/24"]) is False

    def test_multiple_allowed(self):
        mgr = self._make_manager()
        allowed = ["192.168.1.0/24", "10.0.0.1"]
        assert mgr._check_ip_allowed("192.168.1.100", allowed) is True
        assert mgr._check_ip_allowed("10.0.0.1", allowed) is True
        assert mgr._check_ip_allowed("172.16.0.1", allowed) is False

    def test_invalid_ip_returns_false(self):
        mgr = self._make_manager()
        assert mgr._check_ip_allowed("not-an-ip", ["10.0.0.0/24"]) is False

    def test_empty_allowed_list(self):
        mgr = self._make_manager()
        assert mgr._check_ip_allowed("10.0.0.1", []) is False

    def test_ipv6_address(self):
        mgr = self._make_manager()
        assert mgr._check_ip_allowed("::1", ["::1"]) is True

    def test_ipv6_cidr(self):
        mgr = self._make_manager()
        assert mgr._check_ip_allowed("fe80::1", ["fe80::/10"]) is True


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimit:
    """Tests for _check_rate_limit with mocked Redis."""

    @pytest.mark.asyncio
    async def test_within_limit(self):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=5)
        mgr = APIKeyManager(db_session=AsyncMock(), redis_client=mock_redis)

        result = await mgr._check_rate_limit("key1", limit=100, window=60)
        assert result is True

    @pytest.mark.asyncio
    async def test_exceeded_limit(self):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=101)
        mgr = APIKeyManager(db_session=AsyncMock(), redis_client=mock_redis)

        result = await mgr._check_rate_limit("key1", limit=100, window=60)
        assert result is False

    @pytest.mark.asyncio
    async def test_first_request_sets_expiry(self):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mgr = APIKeyManager(db_session=AsyncMock(), redis_client=mock_redis)

        await mgr._check_rate_limit("key1", limit=100, window=60)
        mock_redis.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subsequent_request_no_expiry_set(self):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=2)
        mgr = APIKeyManager(db_session=AsyncMock(), redis_client=mock_redis)

        await mgr._check_rate_limit("key1", limit=100, window=60)
        mock_redis.expire.assert_not_awaited()


# ---------------------------------------------------------------------------
# Validate API key — format check
# ---------------------------------------------------------------------------

class TestValidateAPIKeyFormat:
    """Tests for validate_api_key format checks."""

    @pytest.mark.asyncio
    async def test_invalid_format_no_dot(self):
        mgr = APIKeyManager(db_session=AsyncMock(), redis_client=AsyncMock())
        with patch.object(mgr, '_get_cached_metadata', return_value=None), \
             patch.object(mgr, '_load_key_metadata', return_value=None):
            is_valid, metadata, error = await mgr.validate_api_key("no-dot-key")
            assert is_valid is False
            assert "Invalid API key format" in error
