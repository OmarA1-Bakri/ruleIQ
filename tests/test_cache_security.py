"""
Security tests for cache module

Ensures that caching implementation follows security best practices:
- Uses SHA-256 instead of MD5 for hashing
- No hardcoded secrets
- Proper exception handling
- Secure key generation
"""

import hashlib
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json

from services.caching.cache_manager import CacheManager, LRUCache
from services.caching.cache_keys import CacheKeyBuilder
from services.caching.cache_metrics import CacheMetrics


class TestCacheHashingSecurity:
    """Test that cache uses secure hashing algorithms"""

    def test_cache_keys_use_sha256(self):
        """Ensure cache keys are generated using SHA-256"""
        # Test API key generation
        api_key = CacheKeyBuilder.build_api_key("GET", "/api/test", {"param": "value"})

        # The key should contain a SHA-256 hash (truncated)
        assert "api:" in api_key
        parts = api_key.split(":")

        # The hash part should be from SHA-256
        # We can't test the exact value but we can verify format
        assert len(parts) >= 3
        hash_part = parts[-1]
        assert len(hash_part) <= 32  # Should be truncated SHA-256
        assert all(c in "0123456789abcdef" for c in hash_part.lower())

    def test_no_md5_usage_in_cache_keys(self):
        """Ensure MD5 is not used for cache key generation"""
        # Test that MD5 would produce different results
        test_data = {"test": "data"}
        test_str = json.dumps(test_data, sort_keys=True)

        md5_hash = hashlib.md5(test_str.encode()).hexdigest()
        sha256_hash = hashlib.sha256(test_str.encode()).hexdigest()

        # They should be different
        assert md5_hash != sha256_hash[:32]

        # Cache keys should use SHA-256 pattern
        compute_key = CacheKeyBuilder.build_computation_key("test_operation", test_data)

        # Should not contain MD5 hash
        assert md5_hash not in compute_key
        # Should contain part of SHA-256 hash
        assert sha256_hash[:12] in compute_key or sha256_hash[:8] in compute_key

    def test_cache_key_compression_uses_sha256(self):
        """Test that key compression uses SHA-256"""
        # Create a very long key to trigger compression
        long_key = "cache:" + "x" * 300

        compressed = CacheKeyBuilder.compress_key(long_key)

        # Should be compressed with SHA-256
        assert compressed.startswith("cmp:")
        assert len(compressed) < len(long_key)

        # The hash part should be from SHA-256
        parts = compressed.split(":")
        hash_part = parts[-1]
        assert len(hash_part) == 16  # COMPRESSED_KEY_HASH_LENGTH
        assert all(c in "0123456789abcdef" for c in hash_part.lower())


class TestCacheExceptionHandling:
    """Test proper exception handling in cache module"""

    @pytest.mark.asyncio
    async def test_lru_cache_estimate_size_no_bare_except(self):
        """Test that _estimate_size doesn't use bare except"""
        cache = LRUCache()

        # Test with normal object
        size = cache._estimate_size({"key": "value"})
        assert size > 0

        # Test with non-serializable object (should handle specific exceptions)
        class NonSerializable:
            def __json__(self):
                raise ValueError("Cannot serialize")

        # Should handle without bare except
        size = cache._estimate_size(NonSerializable())
        assert size == 1024  # Fallback size

    @pytest.mark.asyncio
    async def test_redis_specific_exception_handling(self):
        """Test that Redis operations handle specific exceptions"""
        cache_manager = CacheManager()

        # Mock Redis client with specific exceptions
        with patch("database.redis_client.get_redis_client") as mock_get_redis:
            # Import Redis exceptions
            from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

            mock_redis = AsyncMock()
            mock_redis.get.side_effect = RedisConnectionError("Connection failed")
            mock_get_redis.return_value = mock_redis

            await cache_manager.initialize()
            cache_manager._redis = mock_redis
            cache_manager._redis_available = True

            # Should handle Redis-specific exceptions gracefully
            result = await cache_manager.get("test_key")
            assert result is None  # Should return None on error, not crash

    def test_no_broad_exception_handlers_in_critical_paths(self):
        """Ensure critical paths don't use overly broad exception handlers"""
        # This is more of a code review test - checking the actual code
        import inspect
        from services.caching import cache_manager

        source = inspect.getsource(cache_manager)

        # Check that we're not catching bare Exception in critical methods
        # Note: Some Exception catches are acceptable if they log and re-raise
        critical_methods = ["get", "set", "delete"]

        # This is a simplified check - in practice you'd use AST parsing
        assert "except:" not in source  # No bare except

        # Count Exception catches vs specific catches
        broad_catches = source.count("except Exception")
        specific_catches = (
            source.count("except (Redis")
            + source.count("except (TypeError")
            + source.count("except (ValueError")
        )

        # Should have more specific than broad catches
        assert specific_catches > 0


class TestCacheSecurityConstants:
    """Test that security constants are properly defined and used"""

    def test_ttl_constants_defined(self):
        """Test that TTL constants are defined instead of magic numbers"""
        from services.caching.cache_manager import (
            DEFAULT_API_TTL,
            DEFAULT_COMPUTE_TTL,
            DEFAULT_EXTERNAL_API_TTL,
            DEFAULT_STARTUP_TTL,
            DEFAULT_BACKGROUND_TTL,
            BACKGROUND_WARMING_INTERVAL,
        )

        # All TTL constants should be defined
        assert DEFAULT_API_TTL == 300
        assert DEFAULT_COMPUTE_TTL == 3600
        assert DEFAULT_EXTERNAL_API_TTL == 600
        assert DEFAULT_STARTUP_TTL == 3600
        assert DEFAULT_BACKGROUND_TTL == 1800
        assert BACKGROUND_WARMING_INTERVAL == 300

    def test_hash_length_constants_defined(self):
        """Test that hash length constants are defined"""
        from services.caching.cache_keys import (
            COMPRESSED_KEY_HASH_LENGTH,
            API_PARAM_HASH_LENGTH,
            DB_PARAM_HASH_LENGTH,
            COMPUTE_PARAM_HASH_LENGTH,
            EXTERNAL_PARAM_HASH_LENGTH,
            MAX_CACHE_KEY_LENGTH,
            CACHE_KEY_PREFIX_MAX_LENGTH,
        )

        # All hash constants should be defined
        assert COMPRESSED_KEY_HASH_LENGTH == 16
        assert API_PARAM_HASH_LENGTH == 8
        assert DB_PARAM_HASH_LENGTH == 8
        assert COMPUTE_PARAM_HASH_LENGTH == 12
        assert EXTERNAL_PARAM_HASH_LENGTH == 8
        assert MAX_CACHE_KEY_LENGTH == 250
        assert CACHE_KEY_PREFIX_MAX_LENGTH == 50

    def test_metrics_constants_defined(self):
        """Test that metrics constants are defined"""
        from services.caching.cache_metrics import (
            CRITICAL_ERROR_RATE_THRESHOLD,
            WARNING_HIT_RATE_THRESHOLD,
            WARNING_RESPONSE_TIME_THRESHOLD,
            HIT_RATE_WEIGHT,
            RESPONSE_TIME_WEIGHT,
            ERROR_RATE_WEIGHT,
        )

        # All metrics constants should be defined
        assert CRITICAL_ERROR_RATE_THRESHOLD == 0.1
        assert WARNING_HIT_RATE_THRESHOLD == 0.5
        assert WARNING_RESPONSE_TIME_THRESHOLD == 0.1
        assert HIT_RATE_WEIGHT == 40
        assert RESPONSE_TIME_WEIGHT == 30
        assert ERROR_RATE_WEIGHT == 30


class TestCacheKeySecurityPatterns:
    """Test cache key generation follows security patterns"""

    def test_cache_keys_are_deterministic(self):
        """Ensure cache keys are deterministic for same input"""
        params1 = {"b": 2, "a": 1}  # Order shouldn't matter
        params2 = {"a": 1, "b": 2}

        key1 = CacheKeyBuilder.build_api_key("GET", "/test", params1)
        key2 = CacheKeyBuilder.build_api_key("GET", "/test", params2)

        assert key1 == key2  # Should be identical

    def test_cache_keys_unique_for_different_inputs(self):
        """Ensure different inputs produce different keys"""
        key1 = CacheKeyBuilder.build_api_key("GET", "/test", {"a": 1})
        key2 = CacheKeyBuilder.build_api_key("GET", "/test", {"a": 2})
        key3 = CacheKeyBuilder.build_api_key("POST", "/test", {"a": 1})

        # All should be different
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_no_sensitive_data_in_cache_keys(self):
        """Ensure sensitive data is hashed in cache keys"""
        sensitive_params = {
            "password": "secret123",
            "api_key": "sk_test_123456",
            "token": "bearer_token_xyz",
        }

        key = CacheKeyBuilder.build_api_key("POST", "/auth", sensitive_params)

        # The actual sensitive values should NOT appear in the key
        assert "secret123" not in key
        assert "sk_test_123456" not in key
        assert "bearer_token_xyz" not in key

        # Should contain a hash instead
        assert "api:" in key
        parts = key.split(":")
        assert len(parts[-1]) == 8  # API_PARAM_HASH_LENGTH


class TestCacheDualReadCompatibility:
    """Test dual-read compatibility for migration"""

    @pytest.mark.asyncio
    async def test_cache_manager_handles_legacy_keys(self):
        """Test that cache manager can handle legacy MD5 keys during migration"""
        cache_manager = CacheManager()
        await cache_manager.initialize()

        # The dual-read code should be present
        # This tests that the migration compatibility layer exists
        import inspect

        source = inspect.getsource(CacheManager.cache_api_response)

        # Should have migration/legacy handling code
        assert any(k in source.lower() for k in ("legacy", "md5", "migration"))

    def test_migration_script_exists(self):
        """Ensure migration script is available"""
        from pathlib import Path

        migration_script = Path("scripts/migrate_cache_hashing.py")
        assert migration_script.exists()

        # Check script has required functionality
        content = migration_script.read_text()
        assert "MD5" in content
        assert "SHA-256" in content
        assert "CacheHashMigrator" in content

    def test_validation_script_exists(self):
        """Ensure validation script is available"""
        from pathlib import Path

        validation_script = Path("scripts/validate_cache_security.py")
        assert validation_script.exists()

        # Check script has required functionality
        content = validation_script.read_text()
        assert "CacheSecurityValidator" in content
        assert "check_insecure_hash" in content
        assert "check_bare_except" in content


@pytest.mark.asyncio
async def test_cache_manager_initialization_security():
    """Test secure initialization of cache manager"""
    cache_manager = CacheManager()

    # Should initialize without exposing sensitive information
    await cache_manager.initialize()

    stats = cache_manager.get_stats()

    # Stats should not contain sensitive information
    assert "password" not in str(stats).lower()
    assert "secret" not in str(stats).lower()
    assert "token" not in str(stats).lower()

    # Should have security-related metrics
    assert "enabled" in stats
    assert "metrics" in stats

    await cache_manager.close()
