"""Tests for services/caching/cache_keys.py - Cache key management and versioning."""

import pytest

from services.caching.cache_keys import (
    COMPRESSED_KEY_HASH_LENGTH,
    API_PARAM_HASH_LENGTH,
    DB_PARAM_HASH_LENGTH,
    COMPUTE_PARAM_HASH_LENGTH,
    EXTERNAL_PARAM_HASH_LENGTH,
    MAX_CACHE_KEY_LENGTH,
    CACHE_KEY_PREFIX_MAX_LENGTH,
    CacheNamespace,
    CacheKeyBuilder,
)


# --- Constants ---
class TestConstants:
    def test_hash_lengths(self):
        assert COMPRESSED_KEY_HASH_LENGTH == 16
        assert API_PARAM_HASH_LENGTH == 8
        assert DB_PARAM_HASH_LENGTH == 8
        assert COMPUTE_PARAM_HASH_LENGTH == 12
        assert EXTERNAL_PARAM_HASH_LENGTH == 8

    def test_max_lengths(self):
        assert MAX_CACHE_KEY_LENGTH == 250
        assert CACHE_KEY_PREFIX_MAX_LENGTH == 50


# --- CacheNamespace Enum ---
class TestCacheNamespace:
    def test_all_values(self):
        expected = {
            "USER", "SESSION", "BUSINESS", "EVIDENCE", "ASSESSMENT",
            "COMPLIANCE", "API", "COMPUTE", "EXTERNAL", "DB",
        }
        assert {ns.name for ns in CacheNamespace} == expected

    def test_str_enum(self):
        assert isinstance(CacheNamespace.USER.value, str)


# --- CacheKeyBuilder ---
class TestBuildKey:
    def test_basic(self):
        key = CacheKeyBuilder.build_key("part1", "part2")
        assert "part1" in key
        assert "part2" in key

    def test_with_int(self):
        key = CacheKeyBuilder.build_key("user", 123)
        assert "123" in key

    def test_single_part(self):
        key = CacheKeyBuilder.build_key("solo")
        assert "solo" in key


class TestBuildNamespacedKey:
    def test_with_enum(self):
        key = CacheKeyBuilder.build_namespaced_key(CacheNamespace.USER, "profile")
        assert "user" in key.lower() or "USER" in key

    def test_with_string(self):
        key = CacheKeyBuilder.build_namespaced_key("custom", "data")
        assert "custom" in key.lower()


class TestBuildVersionedKey:
    def test_with_version(self):
        key = CacheKeyBuilder.build_versioned_key("base_key", "v2")
        assert "v2" in key

    def test_without_version(self):
        key = CacheKeyBuilder.build_versioned_key("base_key", None)
        assert isinstance(key, str)


class TestCompressKey:
    def test_output_length(self):
        key = CacheKeyBuilder.compress_key("a" * 300)
        assert len(key) <= MAX_CACHE_KEY_LENGTH

    def test_deterministic(self):
        k1 = CacheKeyBuilder.compress_key("test_key")
        k2 = CacheKeyBuilder.compress_key("test_key")
        assert k1 == k2

    def test_different_inputs(self):
        k1 = CacheKeyBuilder.compress_key("key_a")
        k2 = CacheKeyBuilder.compress_key("key_b")
        assert k1 != k2


class TestEntityKeyBuilders:
    def test_user_key(self):
        key = CacheKeyBuilder.build_user_key("usr_123", "profile")
        assert "usr_123" in key

    def test_session_key(self):
        key = CacheKeyBuilder.build_session_key("sess_abc", "data")
        assert "sess_abc" in key

    def test_business_key(self):
        key = CacheKeyBuilder.build_business_key("biz_1", "config")
        assert "biz_1" in key

    def test_evidence_key(self):
        key = CacheKeyBuilder.build_evidence_key("ev_1", "file")
        assert "ev_1" in key

    def test_assessment_key(self):
        key = CacheKeyBuilder.build_assessment_key("asmnt_1", "result")
        assert "asmnt_1" in key

    def test_compliance_key(self):
        key = CacheKeyBuilder.build_compliance_key("comp_1", "status")
        assert "comp_1" in key


class TestApiKey:
    def test_basic(self):
        key = CacheKeyBuilder.build_api_key("GET", "/api/v1/users", None)
        assert isinstance(key, str)

    def test_with_params(self):
        key = CacheKeyBuilder.build_api_key("GET", "/api/v1/users", {"page": 1})
        assert isinstance(key, str)

    def test_different_methods(self):
        k1 = CacheKeyBuilder.build_api_key("GET", "/endpoint", None)
        k2 = CacheKeyBuilder.build_api_key("POST", "/endpoint", None)
        assert k1 != k2


class TestDbQueryKey:
    def test_basic(self):
        key = CacheKeyBuilder.build_db_query_key("users", "hash123", None)
        assert isinstance(key, str)

    def test_with_params(self):
        key = CacheKeyBuilder.build_db_query_key("users", "hash123", {"limit": 10})
        assert isinstance(key, str)


class TestComputationKey:
    def test_basic(self):
        key = CacheKeyBuilder.build_computation_key("analysis", {"type": "risk"})
        assert isinstance(key, str)


class TestExternalApiKey:
    def test_basic(self):
        key = CacheKeyBuilder.build_external_api_key("openai", "/completions", None)
        assert isinstance(key, str)

    def test_with_params(self):
        key = CacheKeyBuilder.build_external_api_key("openai", "/completions", {"model": "gpt-4"})
        assert isinstance(key, str)


class TestInvalidatePattern:
    def test_basic(self):
        pattern = CacheKeyBuilder.invalidate_pattern(CacheNamespace.USER, "profile")
        assert isinstance(pattern, str)


class TestGetRelatedKeys:
    def test_basic(self):
        keys = CacheKeyBuilder.get_related_keys("user", "123")
        assert isinstance(keys, list)
        assert len(keys) > 0


class TestParseKey:
    def test_roundtrip(self):
        key = CacheKeyBuilder.build_key("test", "key")
        parsed = CacheKeyBuilder.parse_key(key)
        assert isinstance(parsed, dict)


class TestKeyVersioning:
    def test_is_expired_version_false(self):
        key = CacheKeyBuilder.build_versioned_key("base", "v1")
        result = CacheKeyBuilder.is_expired_version(key, "v1")
        assert result is False

    def test_is_expired_version_true(self):
        key = CacheKeyBuilder.build_versioned_key("base", "v1")
        result = CacheKeyBuilder.is_expired_version(key, "v2")
        assert result is True

    def test_migrate_key_version(self):
        key = CacheKeyBuilder.build_versioned_key("base", "v1")
        new_key = CacheKeyBuilder.migrate_key_version(key, "v2")
        assert "v2" in new_key
