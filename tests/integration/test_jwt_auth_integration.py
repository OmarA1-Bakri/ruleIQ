"""

# Constants


JWT Authentication Integration Tests
Tests the complete JWT authentication flow after Stack Auth removal
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4
from main import app
from database.user import User
from api.dependencies.auth import get_password_hash

from tests.test_constants import HTTP_CONFLICT, HTTP_CREATED, HTTP_OK, HTTP_UNAUTHORIZED


@pytest.fixture
def test_user_data():
    """Test user data for authentication tests"""
    return {"email": "test@example.com", "password": "TestPassword123!", "full_name": "Test User"}


@pytest.fixture
def existing_user(db_session: Session, test_user_data):
    """Create an existing user in the database"""
    hashed_password = get_password_hash(test_user_data["password"])
    user = User(
        id=uuid4(), email=test_user_data["email"], hashed_password=hashed_password, is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestJWTAuthenticationFlow:
    """Test complete JWT authentication flow"""

    def test_user_registration_flow(self, test_client: TestClient, test_user_data):
        """Test user registration with JWT token generation"""
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
                "full_name": test_user_data["full_name"],
            },
        )
        assert response.status_code == HTTP_CREATED
        data = response.json()
        assert "user" in data
        assert "tokens" in data
        assert data["user"]["email"] == test_user_data["email"]
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]
        assert data["tokens"]["token_type"] == "bearer"

    def test_user_login_flow(self, test_client: TestClient, existing_user, test_user_data):
        """Test user login with JWT token generation"""
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": test_user_data["email"], "password": test_user_data["password"]},
        )
        assert response.status_code == HTTP_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        return data["access_token"]

    def test_protected_endpoint_access(
        self, test_client: TestClient, existing_user, test_user_data
    ):
        """Test accessing protected endpoints with JWT token"""
        login_response = test_client.post(
            "/api/v1/auth/login",
            json={"email": test_user_data["email"], "password": test_user_data["password"]},
        )
        assert login_response.status_code == HTTP_OK
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = test_client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == HTTP_OK
        user_data = response.json()
        assert user_data["email"] == test_user_data["email"]
        assert user_data["is_active"] is True

    def test_token_refresh_flow(self, test_client: TestClient, existing_user, test_user_data):
        """Test JWT token refresh functionality"""
        login_response = test_client.post(
            "/api/v1/auth/login",
            json={"email": test_user_data["email"], "password": test_user_data["password"]},
        )
        assert login_response.status_code == HTTP_OK
        tokens = login_response.json()
        refresh_response = test_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refresh_response.status_code == HTTP_OK
        new_tokens = refresh_response.json()
        assert new_tokens["access_token"] != tokens["access_token"]
        assert new_tokens["refresh_token"] != tokens["refresh_token"]

    def test_logout_flow(self, test_client: TestClient, existing_user, test_user_data):
        """Test user logout and token invalidation"""
        login_response = test_client.post(
            "/api/v1/auth/login",
            json={"email": test_user_data["email"], "password": test_user_data["password"]},
        )
        assert login_response.status_code == HTTP_OK
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        logout_response = test_client.post("/api/v1/auth/logout", headers=headers)
        assert logout_response.status_code == HTTP_OK
        assert logout_response.json()["message"] == "Successfully logged out"

    def test_invalid_credentials_rejection(self, test_client: TestClient, existing_user):
        """Test rejection of invalid credentials"""
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "WrongPassword123!"},
        )
        assert response.status_code == HTTP_UNAUTHORIZED
        assert "Invalid credentials" in response.json()["detail"]

    def test_nonexistent_user_rejection(self, test_client: TestClient):
        """Test rejection of non-existent user"""
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "SomePassword123!"},
        )
        assert response.status_code == HTTP_UNAUTHORIZED
        assert "Invalid credentials" in response.json()["detail"]

    def test_duplicate_registration_rejection(self, test_client: TestClient, existing_user):
        """Test rejection of duplicate email registration"""
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "email": existing_user.email,
                "password": "NewPassword123!",
                "full_name": "Another User",
            },
        )
        assert response.status_code == HTTP_CONFLICT
        assert "Email already exists" in response.json()["detail"]

    def test_protected_endpoint_without_token(self, test_client: TestClient):
        """Test protected endpoint access without token"""
        response = test_client.get("/api/v1/auth/me")
        assert response.status_code == HTTP_UNAUTHORIZED

    def test_protected_endpoint_with_invalid_token(self, test_client: TestClient):
        """Test protected endpoint access with invalid token"""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = test_client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == HTTP_UNAUTHORIZED


class TestBusinessProfileIntegration:
    """Test JWT authentication with business profile endpoints"""

    def test_business_profile_access_with_auth(
        self, test_client: TestClient, existing_user, test_user_data
    ):
        """Test accessing business profile endpoints with JWT authentication"""
        login_response = test_client.post(
            "/api/v1/auth/login",
            json={"email": test_user_data["email"], "password": test_user_data["password"]},
        )
        assert login_response.status_code == HTTP_OK
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = test_client.get("/api/v1/business-profiles", headers=headers)
        assert response.status_code in [200, 404]

    def test_business_profile_access_without_auth(self, test_client: TestClient):
        """Test business profile endpoint requires authentication"""
        response = test_client.get("/api/v1/business-profiles")
        assert response.status_code == HTTP_UNAUTHORIZED


class TestRAGSystemIntegration:
    """Test JWT authentication with RAG system endpoints"""

    def test_chat_endpoint_with_auth(self, test_client: TestClient, existing_user, test_user_data):
        """Test chat endpoint access with JWT authentication"""
        login_response = test_client.post(
            "/api/v1/auth/login",
            json={"email": test_user_data["email"], "password": test_user_data["password"]},
        )
        assert login_response.status_code == HTTP_OK
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = test_client.get("/api/v1/chat/conversations", headers=headers)
        assert response.status_code == HTTP_OK

    def test_chat_endpoint_without_auth(self, test_client: TestClient):
        """Test chat endpoint requires authentication"""
        response = test_client.get("/api/v1/chat/conversations")
        assert response.status_code == HTTP_UNAUTHORIZED


@pytest.mark.integration
class TestAuthenticationSystemIntegration:
    """Integration tests for the complete authentication system"""

    def test_complete_user_journey(self, test_client: TestClient):
        """Test complete user journey from registration to logout"""
        user_data = {
            "email": f"journey_test_{uuid4()}@example.com",
            "password": "JourneyTest123!",
            "full_name": "Journey Test User",
        }
        register_response = test_client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == HTTP_CREATED
        register_data = register_response.json()
        token = register_data["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        me_response = test_client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == HTTP_OK
        assert me_response.json()["email"] == user_data["email"]
        logout_response = test_client.post("/api/v1/auth/logout", headers=headers)
        assert logout_response.status_code == HTTP_OK
        login_response = test_client.post(
            "/api/v1/auth/login",
            json={"email": user_data["email"], "password": user_data["password"]},
        )
        assert login_response.status_code == HTTP_OK
        new_token = login_response.json()["access_token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}
        final_me_response = test_client.get("/api/v1/auth/me", headers=new_headers)
        assert final_me_response.status_code == HTTP_OK
        assert final_me_response.json()["email"] == user_data["email"]

    def test_authentication_system_health(self, test_client: TestClient):
        """Test overall authentication system health"""
        health_response = test_client.get("/health")
        assert health_response.status_code == HTTP_OK
        protected_endpoints = [
            "/api/v1/auth/me",
            "/api/v1/business-profiles",
            "/api/v1/chat/conversations",
        ]
        for endpoint in protected_endpoints:
            response = test_client.get(endpoint)
            assert response.status_code == HTTP_UNAUTHORIZED, (
                f"Endpoint {endpoint} should require authentication"
            )
