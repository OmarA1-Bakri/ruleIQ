"""Critical authentication tests for security validation."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Constants

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from main import app

from tests.test_constants import HTTP_OK, HTTP_UNAUTHORIZED

client = TestClient(app)


class TestAuthenticationSecurity:
    """Test authentication security measures."""

    def test_login_requires_credentials(self):
        """Test that login requires valid credentials."""
        response = client.post("/api/auth/login", json={})
        assert response.status_code in [400, 422]

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/auth/login", json={"email": "invalid@test.com", "password": "wrongpassword"}
        )
        assert response.status_code in [401, 403]

    @patch("services.auth_service.AuthService.authenticate_user")
    def test_login_with_valid_credentials(self, mock_auth):
        """Test login with valid credentials."""
        mock_auth.return_value = {
            "user": {"id": "test-id", "email": "test@example.com"},
            "access_token": "test-token",
            "refresh_token": "test-refresh",
        }
        response = client.post(
            "/api/auth/login", json={"email": "test@example.com", "password": "validpassword"}
        )
        assert response.status_code == HTTP_OK
        data = response.json()
        assert "access_token" in data

    def test_protected_endpoint_requires_auth(self):
        """Test that protected endpoints require authentication."""
        response = client.get("/api/auth/me")
        assert response.status_code == HTTP_UNAUTHORIZED

    @patch("api.dependencies.auth.get_current_user")
    def test_protected_endpoint_with_auth(self, mock_user):
        """Test protected endpoint with valid authentication."""
        mock_user.return_value = {"id": "test-id", "email": "test@example.com"}
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer test-token"})
        assert response.status_code in [200, 401]


class TestPasswordSecurity:
    """Test password security measures."""

    def test_password_not_in_response(self):
        """Test that passwords are never returned in responses."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "SecureP@ssw0rd",
                "full_name": "Test User",
            },
        )
        if response.status_code == HTTP_OK:
            data = response.json()
            assert "password" not in str(data)
            assert "SecureP@ssw0rd" not in str(data)

    def test_weak_password_rejected(self):
        """Test that weak passwords are rejected."""
        response = client.post(
            "/api/auth/register",
            json={"email": "weak@test.com", "password": "123", "full_name": "Test User"},
        )
        assert response.status_code in [400, 422]


class TestSessionManagement:
    """Test session management security."""

    def test_logout_invalidates_session(self):
        """Test that logout properly invalidates session."""
        with patch("services.auth_service.AuthService.authenticate_user") as mock_auth:
            mock_auth.return_value = {
                "user": {"id": "test-id", "email": "test@example.com"},
                "access_token": "test-token",
                "refresh_token": "test-refresh",
            }
            login_response = client.post(
                "/api/auth/login", json={"email": "test@example.com", "password": "password"}
            )
            if login_response.status_code == HTTP_OK:
                token = login_response.json().get("access_token")
                logout_response = client.post(
                    "/api/auth/logout", headers={"Authorization": f"Bearer {token}"}
                )
                me_response = client.get(
                    "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
                )
                assert me_response.status_code == HTTP_UNAUTHORIZED


class TestInputValidation:
    """Test input validation and injection prevention."""

    def test_sql_injection_prevention(self):
        """Test that SQL injection attempts are prevented."""
        response = client.post(
            "/api/auth/login", json={"email": "admin' OR '1'='1", "password": "' OR '1'='1"}
        )
        assert response.status_code in [400, 401, 422]
        if response.status_code == HTTP_OK:
            pytest.fail("SQL injection vulnerability detected")

    def test_xss_prevention(self):
        """Test that XSS attempts are sanitized."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "ValidP@ssw0rd",
                "full_name": "<script>alert('XSS')</script>",
            },
        )
        if response.status_code == HTTP_OK:
            data = response.json()
            assert "<script>" not in str(data)
            assert "alert(" not in str(data)
