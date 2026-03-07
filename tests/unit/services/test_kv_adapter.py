"""
Unit tests for services/kv_adapter.py — VercelKVAdapter, RedisAdapter,
factory function, and CacheAdapter abstract interface.

All external HTTP and Redis connections are mocked.
"""

import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.kv_adapter import (
    CacheAdapter,
    VercelKVAdapter,
    get_cache_adapter,
    get_cache,
)


# ---------------------------------------------------------------------------
# VercelKVAdapter
# ---------------------------------------------------------------------------

class TestVercelKVAdapter:
    """Tests for VercelKVAdapter with mocked HTTP client."""

    def _make_adapter(self):
        with patch.dict(os.environ, {
            "VERCEL_KV_REST_API_URL": "https://kv.example.com",
            "VERCEL_KV_REST_API_TOKEN": "test-token",
        }):
            adapter = VercelKVAdapter()
            adapter.client = AsyncMock()
            return adapter

    @pytest.mark.asyncio
    async def test_get_returns_value(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": json.dumps({"key": "value"})}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.get("test-key")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_returns_none_on_miss(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": None}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.get("missing-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_string_on_json_error(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "plain-string"}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.get("str-key")
        assert result == "plain-string"

    @pytest.mark.asyncio
    async def test_set_with_expire(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "OK"}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.set("key", "value", expire=60)
        assert result is True

        # Verify the command includes EX
        call_args = adapter.client.post.call_args
        command = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "EX" in command

    @pytest.mark.asyncio
    async def test_set_without_expire(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "OK"}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.set("key", "value")
        assert result is True

    @pytest.mark.asyncio
    async def test_set_serializes_dict(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "OK"}
        adapter.client.post = AsyncMock(return_value=mock_response)

        await adapter.set("key", {"nested": "data"})
        call_args = adapter.client.post.call_args
        command = call_args.kwargs.get("json") or call_args[1].get("json")
        # The value should be JSON-serialized
        assert any('"nested"' in str(c) for c in command)

    @pytest.mark.asyncio
    async def test_delete(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 1}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.delete("key")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 1}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.exists("key")
        assert result is True

    @pytest.mark.asyncio
    async def test_ttl(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 3600}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.ttl("key")
        assert result == 3600

    @pytest.mark.asyncio
    async def test_keys(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": ["key1", "key2"]}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.keys("*")
        assert result == ["key1", "key2"]

    @pytest.mark.asyncio
    async def test_execute_error_response(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal error"
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter._execute(["GET", "key"])
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_no_url_configured(self):
        adapter = self._make_adapter()
        adapter.api_url = ""

        result = await adapter._execute(["GET", "key"])
        assert result is None

    @pytest.mark.asyncio
    async def test_incr(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 5}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.incr("counter")
        assert result == 5

    @pytest.mark.asyncio
    async def test_hset_and_hget(self):
        adapter = self._make_adapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 1}
        adapter.client.post = AsyncMock(return_value=mock_response)

        result = await adapter.hset("hash", "field", "value")
        assert result is True

    @pytest.mark.asyncio
    async def test_close(self):
        adapter = self._make_adapter()
        await adapter.close()
        adapter.client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

class TestGetCacheAdapter:
    """Tests for get_cache_adapter factory."""

    def test_default_returns_redis_adapter(self):
        with patch.dict(os.environ, {"USE_VERCEL_KV": "false"}, clear=False):
            os.environ.pop("VERCEL_ENV", None)
            with patch("services.kv_adapter.RedisAdapter") as mock_cls:
                mock_cls.return_value = MagicMock()
                adapter = get_cache_adapter()
                mock_cls.assert_called_once()

    def test_vercel_kv_returns_vercel_adapter(self):
        with patch.dict(os.environ, {"USE_VERCEL_KV": "true"}, clear=False):
            with patch("services.kv_adapter.VercelKVAdapter") as mock_cls:
                mock_cls.return_value = MagicMock()
                adapter = get_cache_adapter()
                mock_cls.assert_called_once()

    def test_production_env_returns_vercel_adapter(self):
        with patch.dict(os.environ, {"VERCEL_ENV": "production", "USE_VERCEL_KV": "false"}, clear=False):
            with patch("services.kv_adapter.VercelKVAdapter") as mock_cls:
                mock_cls.return_value = MagicMock()
                adapter = get_cache_adapter()
                mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# Singleton get_cache()
# ---------------------------------------------------------------------------

class TestGetCache:
    """Tests for get_cache() singleton."""

    @pytest.mark.asyncio
    async def test_get_cache_returns_adapter(self):
        import services.kv_adapter as mod
        mod._cache_adapter = None  # Reset singleton

        with patch("services.kv_adapter.get_cache_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_factory.return_value = mock_adapter

            result = await get_cache()
            assert result == mock_adapter
            mock_factory.assert_called_once()

        # Clean up
        mod._cache_adapter = None

    @pytest.mark.asyncio
    async def test_get_cache_returns_same_instance(self):
        import services.kv_adapter as mod
        mod._cache_adapter = None

        with patch("services.kv_adapter.get_cache_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_factory.return_value = mock_adapter

            r1 = await get_cache()
            r2 = await get_cache()
            assert r1 is r2
            # Factory called only once
            mock_factory.assert_called_once()

        mod._cache_adapter = None
