"""

# Constants

TestSprite Generated Authentication Tests
Generated on: 2025-08-01T22:39:51.373546
"""

import pytest
import requests
from fastapi.testclient import TestClient
from main import app

from tests.test_constants import HTTP_CREATED, HTTP_OK


class TestAuthenticationFlow:
    """Authentication tests generated from TestSprite plans"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def test_user_data(self):
        return {
            "email": "testsprite@example.com",
            "password": "TestSprite123!",
            "full_name": "TestSprite User",
        }

    def test_user_registration_valid_data(self, client, test_user_data):
        """
        TestSprite TC001: User Registration with Valid Data
        Verify that a user can successfully register using valid credentials
        """
        response = client.post("/api/v1/auth/register", json=test_user_data)
        assert response.status_code == HTTP_CREATED
        data = response.json()
        assert "user" in data
        assert "tokens" in data
        assert data["user"]["email"] == test_user_data["email"]
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]

    def test_user_login_correct_credentials(self, client, test_user_data):
        """
        TestSprite TC002: User Login with Correct Credentials
        Validate that users can log in successfully using valid credentials
        """
        client.post("/api/v1/auth/register", json=test_user_data)
        login_data = {"email": test_user_data["email"], "password": test_user_data["password"]}
        response = client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == HTTP_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_protected_endpoint_access(self, client, test_user_data):
        """
        TestSprite: Protected Endpoint Access
        Test accessing protected endpoints with valid JWT token
        """
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": test_user_data["email"], "password": test_user_data["password"]},
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == HTTP_OK
        user_data = response.json()
        assert user_data["email"] == test_user_data["email"]
