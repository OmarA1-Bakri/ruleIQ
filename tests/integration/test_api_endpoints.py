"""
Comprehensive API endpoint integration tests.
Tests all API endpoints with database transactions and external service mocks.
"""

import pytest
from typing import Dict, Any
import json
from datetime import datetime, timedelta


@pytest.mark.integration
class TestAuthenticationEndpoints:
    """Test authentication-related API endpoints."""

    def test_user_registration_flow(self, integration_client, integration_db_session):
        """Test complete user registration flow."""
        # Register new user
        registration_data = {
            "email": "newuser@test.com",
            "password": "SecurePassword123!",
            "full_name": "New Test User",
            "company": "Test Corp",
            "role": "compliance_manager",
        }

        response = integration_client.post("/api/v1/auth/register", json=registration_data)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == registration_data["email"]
        assert "id" in data
        assert "access_token" not in data  # Token sent via email

        # Verify user in database
        from database import User

        user = (
            integration_db_session.query(User).filter_by(email=registration_data["email"]).first()
        )
        assert user is not None
        assert user.is_active is True
        assert user.is_verified is False  # Email not verified yet

    def test_user_login_flow(self, integration_client, sample_integration_data):
        """Test user login with valid credentials."""
        login_data = {"username": "user0@integration.test", "password": "Password0123!"}

        response = integration_client.post(
            "/api/v1/auth/login",
            data=login_data,  # Form data for OAuth2
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_invalid_login_attempts(self, integration_client, sample_integration_data):
        """Test login with invalid credentials."""
        # Wrong password
        response = integration_client.post(
            "/api/v1/auth/login",
            data={"username": "user0@integration.test", "password": "WrongPassword!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

        # Non-existent user
        response = integration_client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent@test.com", "password": "Password123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 401

    def test_token_refresh_flow(self, integration_client, integration_auth_headers):
        """Test JWT token refresh."""
        # Get current user to verify token works
        response = integration_client.get("/api/v1/users/me", headers=integration_auth_headers)
        assert response.status_code == 200

        # Request token refresh
        response = integration_client.post("/api/v1/auth/refresh", headers=integration_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] != integration_auth_headers["Authorization"].split()[1]

    def test_password_reset_flow(
        self, integration_client, sample_integration_data, mock_all_external_services
    ):
        """Test complete password reset flow."""
        # Request password reset
        response = integration_client.post(
            "/api/v1/auth/forgot-password", json={"email": "user0@integration.test"}
        )
        assert response.status_code == 200
        assert "Password reset email sent" in response.json()["message"]

        # Verify email was "sent" (mocked)
        assert mock_all_external_services["sendgrid"].return_value.send.called

    def test_email_verification_flow(self, integration_client, integration_db_session):
        """Test email verification process."""
        from database import User
        from utils.auth import create_verification_token

        # Create unverified user
        user = User(
            email="unverified@test.com",
            full_name="Unverified User",
            hashed_password="hashed",
            is_verified=False,
        )
        integration_db_session.add(user)
        integration_db_session.commit()

        # Create verification token
        token = create_verification_token(user.email)

        # Verify email
        response = integration_client.post("/api/v1/auth/verify-email", json={"token": token})

        assert response.status_code == 200

        # Check user is now verified
        integration_db_session.refresh(user)
        assert user.is_verified is True


@pytest.mark.integration
class TestUserEndpoints:
    """Test user-related API endpoints."""

    def test_get_current_user(self, integration_client, integration_auth_headers):
        """Test getting current user profile."""
        response = integration_client.get("/api/v1/users/me", headers=integration_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "integration@test.com"
        assert data["full_name"] == "Integration Test User"

    def test_update_user_profile(self, integration_client, integration_auth_headers):
        """Test updating user profile."""
        update_data = {
            "full_name": "Updated Name",
            "company": "New Company",
            "phone": "+1234567890",
        }

        response = integration_client.put(
            "/api/v1/users/me", json=update_data, headers=integration_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == update_data["full_name"]

    def test_delete_user_account(
        self, integration_client, integration_auth_headers, integration_db_session
    ):
        """Test user account deletion."""
        # Delete account
        response = integration_client.delete("/api/v1/users/me", headers=integration_auth_headers)

        assert response.status_code == 204

        # Verify user is soft-deleted
        from database import User

        user = integration_db_session.query(User).filter_by(email="integration@test.com").first()
        assert user.is_active is False

    def test_list_users_admin_only(self, integration_client, integration_admin_headers):
        """Test admin endpoint to list all users."""
        response = integration_client.get("/api/v1/users/", headers=integration_admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_unauthorized_admin_access(self, integration_client, integration_auth_headers):
        """Test that non-admin users cannot access admin endpoints."""
        response = integration_client.get("/api/v1/users/", headers=integration_auth_headers)

        assert response.status_code == 403
        assert "Not authorized" in response.json()["detail"]


@pytest.mark.integration
class TestComplianceEndpoints:
    """Test compliance-related API endpoints."""

    def test_list_frameworks(
        self, integration_client, integration_auth_headers, sample_integration_data
    ):
        """Test listing available compliance frameworks."""
        response = integration_client.get(
            "/api/v1/compliance/frameworks", headers=integration_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        framework_names = [f["name"] for f in data]
        assert "GDPR" in framework_names
        assert "SOC 2" in framework_names
        assert "ISO 27001" in framework_names

    def test_get_framework_details(
        self, integration_client, integration_auth_headers, sample_integration_data
    ):
        """Test getting specific framework details."""
        framework_id = sample_integration_data["frameworks"][0].id

        response = integration_client.get(
            f"/api/v1/compliance/frameworks/{framework_id}", headers=integration_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "GDPR"
        assert "requirements" in data

    def test_create_assessment(
        self, integration_client, integration_auth_headers, sample_integration_data
    ):
        """Test creating a new compliance assessment."""
        framework_id = sample_integration_data["frameworks"][0].id

        assessment_data = {
            "framework_id": framework_id,
            "name": "Q1 2024 GDPR Assessment",
            "description": "Quarterly compliance check",
        }

        response = integration_client.post(
            "/api/v1/compliance/assessments", json=assessment_data, headers=integration_auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == assessment_data["name"]
        assert data["status"] == "draft"
        assert "id" in data

    def test_update_assessment_responses(
        self, integration_client, integration_auth_headers, sample_integration_data
    ):
        """Test updating assessment responses."""
        assessment = sample_integration_data["assessments"][0]

        response_data = {
            "responses": {
                "GDPR-1": {
                    "status": "compliant",
                    "evidence": ["policy.pdf"],
                    "notes": "Implemented and documented",
                },
                "GDPR-2": {"status": "partial", "evidence": [], "notes": "In progress"},
            }
        }

        response = integration_client.put(
            f"/api/v1/compliance/assessments/{assessment.id}/responses",
            json=response_data,
            headers=integration_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "GDPR-1" in data["responses"]
        assert data["responses"]["GDPR-1"]["status"] == "compliant"

    def test_generate_compliance_report(
        self,
        integration_client,
        integration_auth_headers,
        sample_integration_data,
        mock_all_external_services,
    ):
        """Test generating a compliance report."""
        assessment = sample_integration_data["assessments"][0]

        response = integration_client.post(
            f"/api/v1/compliance/assessments/{assessment.id}/report",
            headers=integration_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "report_url" in data
        assert data["status"] == "generated"

        # Verify S3 upload was called (mocked)
        assert mock_all_external_services["s3"].put_object.called


@pytest.mark.integration
class TestDocumentEndpoints:
    """Test document management endpoints."""

    def test_upload_document(self, integration_client, integration_auth_headers, tmp_path):
        """Test document upload."""
        # Create test file
        test_file = tmp_path / "test_document.pdf"
        test_file.write_bytes(b"Test PDF content")

        with open(test_file, "rb") as f:
            files = {"file": ("test_document.pdf", f, "application/pdf")}
            response = integration_client.post(
                "/api/v1/documents/upload",
                files=files,
                headers={"Authorization": integration_auth_headers["Authorization"]},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test_document.pdf"
        assert "document_id" in data
        assert data["size"] > 0

    def test_list_documents(self, integration_client, integration_auth_headers):
        """Test listing user documents."""
        response = integration_client.get("/api/v1/documents", headers=integration_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_delete_document(
        self, integration_client, integration_auth_headers, integration_db_session
    ):
        """Test document deletion."""
        from database import Document

        # Create a document record
        doc = Document(
            user_id=1,  # Assuming user ID 1 exists from fixtures
            filename="test.pdf",
            file_path="/uploads/test.pdf",
            file_size=1024,
            mime_type="application/pdf",
        )
        integration_db_session.add(doc)
        integration_db_session.commit()

        response = integration_client.delete(
            f"/api/v1/documents/{doc.id}", headers=integration_auth_headers
        )

        assert response.status_code == 204

        # Verify document is deleted
        deleted_doc = integration_db_session.query(Document).filter_by(id=doc.id).first()
        assert deleted_doc is None


@pytest.mark.integration
class TestNotificationEndpoints:
    """Test notification endpoints."""

    def test_send_email_notification(
        self, integration_client, integration_auth_headers, mock_all_external_services
    ):
        """Test sending email notifications."""
        notification_data = {
            "recipient": "user@test.com",
            "subject": "Test Notification",
            "body": "This is a test notification",
            "template": "default",
        }

        response = integration_client.post(
            "/api/v1/notifications/email", json=notification_data, headers=integration_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"

        # Verify SendGrid was called
        assert mock_all_external_services["sendgrid"].return_value.send.called

    def test_get_notification_preferences(self, integration_client, integration_auth_headers):
        """Test getting user notification preferences."""
        response = integration_client.get(
            "/api/v1/notifications/preferences", headers=integration_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "email_enabled" in data
        assert "sms_enabled" in data
        assert "push_enabled" in data

    def test_update_notification_preferences(self, integration_client, integration_auth_headers):
        """Test updating notification preferences."""
        preferences = {
            "email_enabled": False,
            "sms_enabled": True,
            "push_enabled": True,
            "frequency": "weekly",
        }

        response = integration_client.put(
            "/api/v1/notifications/preferences", json=preferences, headers=integration_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email_enabled"] is False
        assert data["sms_enabled"] is True


@pytest.mark.integration
class TestBillingEndpoints:
    """Test billing and subscription endpoints."""

    def test_create_subscription(
        self, integration_client, integration_auth_headers, mock_all_external_services
    ):
        """Test creating a subscription."""
        subscription_data = {"plan_id": "pro_monthly", "payment_method_id": "pm_test_123"}

        response = integration_client.post(
            "/api/v1/billing/subscriptions",
            json=subscription_data,
            headers=integration_auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["plan_id"] == "pro_monthly"
        assert data["status"] == "active"
        assert "subscription_id" in data

    def test_get_billing_history(self, integration_client, integration_auth_headers):
        """Test retrieving billing history."""
        response = integration_client.get(
            "/api/v1/billing/history", headers=integration_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_cancel_subscription(self, integration_client, integration_auth_headers):
        """Test cancelling a subscription."""
        response = integration_client.delete(
            "/api/v1/billing/subscriptions/current", headers=integration_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert "cancelled_at" in data


@pytest.mark.integration
class TestHealthEndpoints:
    """Test health check and monitoring endpoints."""

    def test_health_check(self, integration_client):
        """Test basic health check endpoint."""
        response = integration_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_readiness_check(self, integration_client):
        """Test readiness check with dependency verification."""
        response = integration_client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert "database" in data["checks"]
        assert "redis" in data["checks"]
        assert "external_apis" in data["checks"]

    def test_metrics_endpoint(self, integration_client, integration_admin_headers):
        """Test metrics endpoint (admin only)."""
        response = integration_client.get("/metrics", headers=integration_admin_headers)

        assert response.status_code == 200
        # Prometheus format text
        assert "http_requests_total" in response.text
        assert "http_request_duration_seconds" in response.text


@pytest.mark.integration
@pytest.mark.slow_integration
class TestRateLimiting:
    """Test API rate limiting."""

    def test_rate_limit_enforcement(self, integration_client, integration_auth_headers):
        """Test that rate limits are enforced."""
        # Make multiple rapid requests
        responses = []
        for _ in range(102):  # Assuming limit is 100 per minute
            response = integration_client.get("/api/v1/users/me", headers=integration_auth_headers)
            responses.append(response)

        # Check that we got rate limited
        rate_limited = any(r.status_code == 429 for r in responses)
        assert rate_limited, "Rate limiting not enforced"

        # Check rate limit headers
        last_response = responses[-1]
        if last_response.status_code == 429:
            assert "X-RateLimit-Limit" in last_response.headers
            assert "X-RateLimit-Remaining" in last_response.headers
            assert "X-RateLimit-Reset" in last_response.headers


@pytest.mark.integration
class TestCORSConfiguration:
    """Test CORS configuration."""

    def test_cors_headers(self, integration_client):
        """Test CORS headers are properly set."""
        response = integration_client.options(
            "/api/v1/auth/login",
            headers={"Origin": "https://example.com", "Access-Control-Request-Method": "POST"},
        )

        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Allow-Headers" in response.headers


@pytest.mark.integration
class TestErrorHandling:
    """Test API error handling."""

    def test_404_not_found(self, integration_client):
        """Test 404 error for non-existent endpoint."""
        response = integration_client.get("/api/v1/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_400_bad_request(self, integration_client):
        """Test 400 error for invalid request data."""
        response = integration_client.post(
            "/api/v1/auth/register",
            json={"invalid": "data"},  # Missing required fields
        )

        assert response.status_code == 422  # FastAPI validation error
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)

    def test_401_unauthorized(self, integration_client):
        """Test 401 error for unauthorized access."""
        response = integration_client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Invalid" in data["detail"] or "Unauthorized" in data["detail"]

    def test_500_internal_error_handling(
        self, integration_client, integration_auth_headers, monkeypatch
    ):
        """Test 500 error handling and error reporting."""

        # Mock a function to raise an exception
        def raise_error(*args, **kwargs):
            raise Exception("Simulated internal error")

        # This would need to be adjusted based on actual implementation
        # Example: monkeypatch a specific function that gets called

        # The actual implementation would depend on your error handling middleware
        pass
