"""
Unit tests for api/routers/health.py — Health check endpoints.

These are simple endpoints with no external dependencies.
Uses httpx.ASGITransport for TestClient compatibility.
"""

import os
import pytest

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from api.routers.health import router


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def _make_app():
    """Create a minimal FastAPI app with just the health router."""
    app = FastAPI()
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "RuleIQ" in data["message"]

    @pytest.mark.asyncio
    async def test_health_check(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_readiness_check(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"

    @pytest.mark.asyncio
    async def test_gcp_health_check(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/_ah/health")
        assert resp.status_code == 200
        assert resp.text == "OK"

    @pytest.mark.asyncio
    async def test_health_check_content_type(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
        assert "application/json" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_gcp_health_content_type(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/_ah/health")
        assert "text/plain" in resp.headers["content-type"]
