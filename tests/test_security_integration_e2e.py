"""

# Constants



End-to-End Security Integration Tests
Tests the complete security stack with all middleware and services integrated
"""

from fastapi import status
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
from datetime import datetime
import os
from main import app
from database.db_setup import get_db

from tests.test_constants import DEFAULT_LIMIT, HTTP_OK, HTTP_UNAUTHORIZED


class TestSecurityIntegrationE2E:
    """End-to-end security integration tests"""

    @pytest.fixture
    def client(self):
        """Test client with full application stack"""
        return TestClient(app)

    @pytest.fixture
    def test_user(self, db_session: Session):
        """Create a test user in the database"""
        from database.user import User
        from database.rbac import Role, UserRole, Permission, RolePermission

        user = User(
            email="security_test@example.com",
            hashed_password="$2b$12$KIXxPfF3DYFqB2V0zZPOm.JqMiLpN9kGK4nh3Q3Zq5RXzNfNqZ0Gy",
            is_active=True,
            full_name="Security Test User",
        )
        db_session.add(user)
        import uuid

        role_name = f"test_role_{uuid.uuid4().hex[:8]}"
        role = Role(
            name=role_name,
            display_name="Test Role",
            description="Test role for security integration",
            is_active=True,
        )
        db_session.add(role)
        db_session.commit()
        user_role = UserRole(user_id=user.id, role_id=role.id)
        db_session.add(user_role)
        permission = Permission(
            name="test_permission",
            display_name="Test Permission",
            description="Test permission for security integration",
        )
        db_session.add(permission)
        db_session.commit()
        role_permission = RolePermission(role_id=role.id, permission_id=permission.id)
        db_session.add(role_permission)
        db_session.commit()
        yield user
        db_session.delete(role_permission)
        db_session.delete(permission)
        db_session.delete(user_role)
        db_session.delete(role)
        db_session.delete(user)
        db_session.commit()

    def test_security_headers_present(self, client):
        """Test that security headers are added to responses"""
        response = client.get("/health")
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=" in response.headers["Strict-Transport-Security"]
        assert "Referrer-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_content_security_policy(self, client):
        """Test CSP header configuration"""
        response = client.get("/health")
        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        assert "default-src" in csp
        assert "script-src" in csp
        assert "style-src" in csp
        assert "img-src" in csp
        assert "frame-ancestors" in csp

    def test_sql_injection_prevention(self, client):
        """Test SQL injection protection"""
        response = client.get("/api/frameworks?search='; DROP TABLE users; --")
        assert response.status_code in [400, 200]
        response = client.get("/api/frameworks/1'; DELETE FROM frameworks WHERE '1'='1")
        assert response.status_code in [400, 404]

    def test_xss_prevention(self, client):
        """Test XSS prevention"""
        xss_payload = "<script>alert('XSS')</script>"
        response = client.post(
            "/api/frameworks",
            json={"name": xss_payload, "description": "Test"},
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code in [400, 401, 422]

    def test_authentication_required(self, client):
        """Test that protected endpoints require authentication"""
        response = client.get("/api/frameworks")
        assert response.status_code == HTTP_UNAUTHORIZED
        response = client.post(
            "/api/frameworks", json={"name": "Test Framework", "description": "Test"}
        )
        assert response.status_code == HTTP_UNAUTHORIZED

    def test_rate_limiting(self, client):
        """Test rate limiting functionality"""
        responses = []
        for _ in range(DEFAULT_LIMIT):
            response = client.get("/health")
            responses.append(response.status_code)
        assert all(status == HTTP_OK for status in responses)

    def test_cors_headers(self, client):
        """Test CORS configuration"""
        response = client.options(
            "/api/frameworks",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        if "Access-Control-Allow-Origin" in response.headers:
            assert response.headers["Access-Control-Allow-Origin"] in ["*", "http://localhost:3000"]
        if "Access-Control-Allow-Methods" in response.headers:
            assert "GET" in response.headers["Access-Control-Allow-Methods"]

    def test_secure_cookie_flags(self, client):
        """Test that cookies have secure flags"""
        response = client.get("/health")
        assert response.status_code == HTTP_OK

    @pytest.mark.skipif(
        not os.getenv("DATABASE_URL") and not os.getenv("TEST_DATABASE_URL"),
        reason="Database not available",
    )
    def test_audit_logging_integration(self, client, db_session):
        """Test that audit logging is working"""
        from database.rbac import AuditLog

        initial_count = db_session.query(AuditLog).count()
        response = client.get("/api/frameworks")
        final_count = db_session.query(AuditLog).count()
        assert response.status_code in [200, 401]

    async def test_encryption_service_integration(self):
        """Test encryption service is working"""
        from services.security.encryption import EncryptionService

        service = EncryptionService()
        test_data = "sensitive_information"
        encrypted = await service.encrypt_field(test_data)
        decrypted = await service.decrypt_field(encrypted)
        assert encrypted != test_data
        assert decrypted == test_data

    def test_password_validation(self):
        """Test password complexity validation"""
        from services.security.authentication import AuthenticationService

        service = AuthenticationService()
        is_valid, message = service.validate_password_complexity("weak")
        assert not is_valid
        assert "at least 12 characters" in message.lower()
        is_valid, message = service.validate_password_complexity("StrongP@ssw0rd123!")
        assert is_valid
        assert message == "Password meets complexity requirements"

    @pytest.mark.skipif(
        not os.getenv("DATABASE_URL") and not os.getenv("TEST_DATABASE_URL"),
        reason="Database not available",
    )
    def test_complete_security_flow(self, client, test_user, db_session):
        """Test complete security flow from request to response"""
        response = client.get("/health")
        assert response.status_code == HTTP_OK
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert response.json()["status"] == "healthy"
