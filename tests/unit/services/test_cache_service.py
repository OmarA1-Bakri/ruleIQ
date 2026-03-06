"""
Unit tests for services/cache_service.py — CacheService (in-memory fallback).

All Redis/KV dependencies are mocked.
"""

import os
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")


# ---------------------------------------------------------------------------
# CacheService — in-memory fallback
# ---------------------------------------------------------------------------

class TestCacheServiceInMemory:
    """Tests for CacheService using in-memory fallback."""

    def _make_service(self):
        from services.cache_service import CacheService
        svc = CacheService()
        svc._cache_available = False  # Force in-memory mode
        return svc

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        svc = self._make_service()
        result = await svc.set("key1", {"data": "value"}, ttl=60)
        assert result is True

        value = await svc.get("key1")
        assert value == {"data": "value"}

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self):
        svc = self._make_service()
        value = await svc.get("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_set_string_value(self):
        svc = self._make_service()
        await svc.set("str_key", "hello", ttl=60)
        value = await svc.get("str_key")
        assert value == "hello"

    @pytest.mark.asyncio
    async def test_set_numeric_value(self):
        svc = self._make_service()
        await svc.set("num_key", 42, ttl=60)
        value = await svc.get("num_key")
        assert value == 42

    @pytest.mark.asyncio
    async def test_set_list_value(self):
        svc = self._make_service()
        await svc.set("list_key", [1, 2, 3], ttl=60)
        value = await svc.get("list_key")
        assert value == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        svc = self._make_service()
        # Set with very short TTL
        await svc.set("expire_key", "value", ttl=1)

        # Manually expire it
        svc._memory_cache["expire_key"]["expires_at"] = time.time() - 1

        value = await svc.get("expire_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_no_ttl_persists(self):
        svc = self._make_service()
        await svc.set("no_ttl_key", "value")
        value = await svc.get("no_ttl_key")
        assert value == "value"

    @pytest.mark.asyncio
    async def test_delete(self):
        svc = self._make_service()
        await svc.set("del_key", "value", ttl=60)
        result = await svc.delete("del_key")
        assert result is True

        value = await svc.get("del_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        svc = self._make_service()
        result = await svc.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists(self):
        svc = self._make_service()
        await svc.set("exist_key", "value", ttl=60)
        assert await svc.exists("exist_key") is True
        assert await svc.exists("no_key") is False

    @pytest.mark.asyncio
    async def test_exists_expired(self):
        svc = self._make_service()
        await svc.set("exp_key", "value", ttl=1)
        svc._memory_cache["exp_key"]["expires_at"] = time.time() - 1
        assert await svc.exists("exp_key") is False

    @pytest.mark.asyncio
    async def test_clear_all(self):
        svc = self._make_service()
        await svc.set("k1", "v1", ttl=60)
        await svc.set("k2", "v2", ttl=60)

        result = await svc.clear()
        assert result is True
        assert len(svc._memory_cache) == 0

    @pytest.mark.asyncio
    async def test_clear_pattern(self):
        svc = self._make_service()
        await svc.set("user:1", "data1", ttl=60)
        await svc.set("user:2", "data2", ttl=60)
        await svc.set("session:1", "data3", ttl=60)

        await svc.clear(pattern="user:*")
        assert await svc.get("user:1") is None
        assert await svc.get("user:2") is None
        assert await svc.get("session:1") is not None

    @pytest.mark.asyncio
    async def test_memory_cache_eviction(self):
        svc = self._make_service()
        svc._max_memory_items = 5

        for i in range(10):
            await svc.set(f"key_{i}", f"value_{i}", ttl=60)

        # Should not exceed max + some buffer (evicts 100 at a time, but max is 5)
        assert len(svc._memory_cache) <= 6

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        svc = self._make_service()
        await svc.set("fresh", "value", ttl=3600)
        await svc.set("stale", "value", ttl=1)
        svc._memory_cache["stale"]["expires_at"] = time.time() - 1

        count = await svc.cleanup_expired()
        assert count == 1
        assert "stale" not in svc._memory_cache
        assert "fresh" in svc._memory_cache

    @pytest.mark.asyncio
    async def test_cleanup_no_expired(self):
        svc = self._make_service()
        await svc.set("fresh", "value", ttl=3600)
        count = await svc.cleanup_expired()
        assert count == 0


# ---------------------------------------------------------------------------
# CacheService — with timedelta TTL
# ---------------------------------------------------------------------------

class TestCacheServiceTimedelta:
    """Tests for CacheService with timedelta TTL."""

    def _make_service(self):
        from services.cache_service import CacheService
        svc = CacheService()
        svc._cache_available = False
        return svc

    @pytest.mark.asyncio
    async def test_timedelta_ttl(self):
        from datetime import timedelta
        svc = self._make_service()
        result = await svc.set("td_key", "val", ttl=timedelta(hours=1))
        assert result is True

        value = await svc.get("td_key")
        assert value == "val"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestCacheHelpers:
    """Tests for module-level helper functions."""

    @pytest.mark.asyncio
    async def test_cache_get_set_delete(self):
        from services.cache_service import cache_get, cache_set, cache_delete
        import services.cache_service as mod

        # Reset singleton
        mod._cache_service = None

        with patch.object(
            mod.CacheService, '_get_cache_adapter',
            new_callable=AsyncMock, return_value=None,
        ):
            await cache_set("helper_key", "helper_value", ttl=60)
            value = await cache_get("helper_key")
            assert value == "helper_value"

            await cache_delete("helper_key")
            value = await cache_get("helper_key")
            assert value is None

        # Clean up singleton
        mod._cache_service = None
