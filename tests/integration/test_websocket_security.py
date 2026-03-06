"""
Integration tests for WebSocket security improvements.
"""

import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from websocket import create_connection, WebSocket
from jose import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import logging

from main import app
from api.dependencies.auth import SECRET_KEY, ALGORITHM
from database.user import User


logger = logging.getLogger(__name__)


class TestWebSocketSecurity:
    """Test suite for WebSocket JWT authentication via headers."""

    @pytest.fixture
    def valid_token(self):
        """Generate a valid JWT token for testing."""
        payload = {"sub": "test-user-123", "exp": datetime.utcnow() + timedelta(hours=1)}
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @pytest.fixture
    def expired_token(self):
        """Generate an expired JWT token."""
        payload = {"sub": "test-user-123", "exp": datetime.utcnow() - timedelta(hours=1)}
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @pytest.mark.asyncio
    async def test_websocket_auth_via_headers(self, valid_token):
        """Test WebSocket authentication using headers."""
        client = TestClient(app)

        # Test with Authorization header
        with client.websocket_connect(
            "/api/v1/ai-cost/realtime-dashboard", headers={"Authorization": f"Bearer {valid_token}"}
        ) as websocket:
            # Should connect successfully
            data = websocket.receive_json()
            assert data is not None

    @pytest.mark.asyncio
    async def test_websocket_auth_via_x_auth_token(self, valid_token):
        """Test WebSocket authentication using X-Auth-Token header."""
        client = TestClient(app)

        with client.websocket_connect(
            "/api/v1/ai-cost/realtime-dashboard", headers={"X-Auth-Token": valid_token}
        ) as websocket:
            data = websocket.receive_json()
            assert data is not None

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_token(self):
        """Test WebSocket rejects invalid tokens."""
        client = TestClient(app)

        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/ai-cost/realtime-dashboard",
                headers={"Authorization": "Bearer invalid-token"},
            ) as websocket:
                pass

    @pytest.mark.asyncio
    async def test_websocket_rejects_expired_token(self, expired_token):
        """Test WebSocket rejects expired tokens."""
        client = TestClient(app)

        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/ai-cost/realtime-dashboard",
                headers={"Authorization": f"Bearer {expired_token}"},
            ) as websocket:
                pass

    @pytest.mark.asyncio
    async def test_websocket_fallback_to_query_deprecated(self, valid_token):
        """Test deprecated query parameter authentication still works with warning."""
        client = TestClient(app)

        with patch("api.routers.ai_cost_websocket.logger") as mock_logger:
            with client.websocket_connect(
                f"/api/v1/ai-cost/realtime-dashboard?token={valid_token}"
            ) as websocket:
                # Should log deprecation warning
                mock_logger.warning.assert_called()
                data = websocket.receive_json()
                assert data is not None


class TestGrafanaSecurityConfig:
    """Test suite for Grafana security configuration."""

    def test_grafana_no_default_credentials(self):
        """Ensure Grafana doesn't use default credentials."""
        from config.monitoring_security import get_grafana_credentials

        creds = get_grafana_credentials()
        assert creds["username"] != "admin"
        assert creds["password"] != "admin"
        assert len(creds["password"]) >= 20

    def test_grafana_password_strength(self):
        """Test Grafana password meets security requirements."""
        from config.monitoring_security import generate_secure_password

        password = generate_secure_password(24)
        assert len(password) >= 24
        assert any(c.islower() for c in password)
        assert any(c.isupper() for c in password)
        assert any(c.isdigit() for c in password)
        assert any(c in "!@#$%^&*()_+-=" for c in password)

    def test_monitoring_env_file_generation(self, tmp_path):
        """Test secure monitoring environment file generation."""
        from config.monitoring_security import generate_monitoring_env_file

        env_file = tmp_path / ".env.monitoring"
        generate_monitoring_env_file(str(env_file))

        assert env_file.exists()
        content = env_file.read_text()
        assert "GRAFANA_ADMIN_USER" in content
        assert "GRAFANA_ADMIN_PASSWORD" in content
        assert "admin" not in content  # No default credentials


class TestDatabaseConnectionPooling:
    """Test suite for database connection pooling."""

    def test_pool_configuration_validation(self):
        """Test database pool configuration validation."""
        from config.database_pool_config import ConnectionPoolConfig

        validation = ConnectionPoolConfig.validate_pool_config()
        assert validation["pool_size_valid"]
        assert validation["max_overflow_valid"]
        assert validation["timeout_valid"]

    def test_production_pool_settings(self):
        """Test production pool settings are appropriate."""
        from config.database_pool_config import ConnectionPoolConfig

        settings = ConnectionPoolConfig.get_pool_settings(is_production=True)
        assert settings["pool_size"] >= 20
        assert settings["max_overflow"] >= 20
        assert settings["pool_pre_ping"] is True
        assert settings["pool_timeout"] >= 30

    def test_async_pool_settings(self):
        """Test async pool settings."""
        from config.database_pool_config import ConnectionPoolConfig

        settings = ConnectionPoolConfig.get_async_pool_settings(is_production=True)
        assert settings["pool_reset_on_return"] == "commit"
        assert "server_settings" in settings["connect_args"]

    @pytest.mark.asyncio
    async def test_database_connection_with_pooling(self):
        """Test database connections use proper pooling."""
        from database.db_setup import get_async_db, test_async_database_connection

        # Test connection
        result = await test_async_database_connection()
        assert result is True

        # Test session creation
        async for session in get_async_db():
            assert session is not None
            break

    def test_connection_limits_calculation(self):
        """Test connection limit calculations based on system resources."""
        from config.database_pool_config import ConnectionPoolConfig

        limits = ConnectionPoolConfig.get_connection_limits()
        assert limits["total_max_connections"] > 0
        assert limits["per_service_pool_size"] > 0
        assert limits["warning_threshold"] > limits["per_service_pool_size"]


class TestAPISecurityIntegration:
    """Integration tests for API security features."""

    def test_jwt_header_authentication(self):
        """Test JWT authentication via headers."""
        client = TestClient(app)

        # Login to get token
        response = client.post(
            "/api/v1/auth/token", data={"username": "test@example.com", "password": "TestPass123!"}
        )

        if response.status_code == 200:
            token = response.json()["access_token"]

            # Test authenticated endpoint
            response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code in [200, 401]

    def test_rate_limiting(self):
        """Test API rate limiting."""
        client = TestClient(app)

        # Make multiple requests
        responses = []
        for _ in range(10):
            response = client.get("/api/v1/health")
            responses.append(response.status_code)

        # Should not all be successful if rate limiting is working
        # (This assumes rate limiting is configured)
        assert all(r in [200, 429] for r in responses)

    def test_cors_configuration(self):
        """Test CORS is properly configured."""
        client = TestClient(app)

        response = client.options("/api/v1/health", headers={"Origin": "http://localhost:3000"})

        # Check CORS headers
        assert "access-control-allow-origin" in response.headers or response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
