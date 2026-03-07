"""
Unit tests for services/redis_circuit_breaker.py — LocalCache and CircuitState.

Tests the pure in-memory LocalCache class and CircuitState enum.
No Redis or external dependencies needed.
"""

import os
import time
import pytest
from unittest.mock import patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.redis_circuit_breaker import LocalCache, CircuitState


# ---------------------------------------------------------------------------
# CircuitState enum
# ---------------------------------------------------------------------------

class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_closed_value(self):
        assert CircuitState.CLOSED == "closed"

    def test_open_value(self):
        assert CircuitState.OPEN == "open"

    def test_half_open_value(self):
        assert CircuitState.HALF_OPEN == "half_open"

    def test_is_string_enum(self):
        assert isinstance(CircuitState.CLOSED, str)


# ---------------------------------------------------------------------------
# LocalCache — basic operations
# ---------------------------------------------------------------------------

class TestLocalCacheBasic:
    """Tests for LocalCache basic get/set/delete."""

    def test_set_and_get(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        cache = LocalCache(max_size=10, ttl=300)
        assert cache.get("nonexistent") is None

    def test_delete_existing(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_delete_nonexistent(self):
        cache = LocalCache(max_size=10, ttl=300)
        assert cache.delete("nonexistent") is False

    def test_clear(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_overwrite_value(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"


# ---------------------------------------------------------------------------
# LocalCache — TTL expiry
# ---------------------------------------------------------------------------

class TestLocalCacheTTL:
    """Tests for LocalCache TTL-based expiration."""

    def test_expired_entry_returns_none(self):
        cache = LocalCache(max_size=10, ttl=1)  # 1 second TTL
        cache.set("key", "value")
        # Manually expire by patching timestamp
        cache.cache["key"] = ("value", time.time() - 10)
        assert cache.get("key") is None

    def test_fresh_entry_returns_value(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_expired_entry_is_cleaned_up(self):
        cache = LocalCache(max_size=10, ttl=1)
        cache.set("key", "value")
        cache.cache["key"] = ("value", time.time() - 10)
        cache.get("key")  # Trigger cleanup
        assert "key" not in cache.cache


# ---------------------------------------------------------------------------
# LocalCache — LRU eviction
# ---------------------------------------------------------------------------

class TestLocalCacheLRU:
    """Tests for LocalCache LRU eviction behavior."""

    def test_evicts_oldest_at_capacity(self):
        cache = LocalCache(max_size=3, ttl=300)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_access_moves_to_end(self):
        cache = LocalCache(max_size=3, ttl=300)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # Touch "a" so it's recently used
        cache.set("d", 4)  # Should evict "b" (oldest untouched)
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("d") == 4

    def test_set_existing_doesnt_evict(self):
        cache = LocalCache(max_size=3, ttl=300)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("a", 10)  # Update existing, no eviction
        assert len(cache.cache) == 3
        assert cache.get("a") == 10
        assert cache.get("b") == 2

    def test_max_size_one(self):
        cache = LocalCache(max_size=1, ttl=300)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") is None
        assert cache.get("b") == 2


# ---------------------------------------------------------------------------
# LocalCache — various value types
# ---------------------------------------------------------------------------

class TestLocalCacheValueTypes:
    """Tests for storing various value types in LocalCache."""

    def test_string_value(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("k", "hello")
        assert cache.get("k") == "hello"

    def test_int_value(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("k", 42)
        assert cache.get("k") == 42

    def test_dict_value(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("k", {"nested": True})
        assert cache.get("k") == {"nested": True}

    def test_list_value(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("k", [1, 2, 3])
        assert cache.get("k") == [1, 2, 3]

    def test_none_value(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("k", None)
        # None is stored; get returns it
        # But we can't distinguish from "not found" — implementation detail
        # The cache stores (None, timestamp) which truthy check passes
        result = cache.get("k")
        assert result is None

    def test_boolean_value(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("k", True)
        assert cache.get("k") is True

    def test_float_value(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("k", 3.14)
        assert cache.get("k") == 3.14


# ---------------------------------------------------------------------------
# LocalCache — edge cases
# ---------------------------------------------------------------------------

class TestLocalCacheEdgeCases:
    """Tests for edge case behaviors."""

    def test_empty_string_key(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("", "empty-key")
        assert cache.get("") == "empty-key"

    def test_unicode_key(self):
        cache = LocalCache(max_size=10, ttl=300)
        cache.set("unicode-key", "value")
        assert cache.get("unicode-key") == "value"

    def test_large_value(self):
        cache = LocalCache(max_size=10, ttl=300)
        big = "x" * 1_000_000
        cache.set("big", big)
        assert cache.get("big") == big

    def test_many_sets_and_gets(self):
        cache = LocalCache(max_size=100, ttl=300)
        for i in range(200):
            cache.set(f"key-{i}", i)
        # Only last 100 should remain
        assert len(cache.cache) == 100
        assert cache.get("key-199") == 199
        assert cache.get("key-0") is None  # Evicted
