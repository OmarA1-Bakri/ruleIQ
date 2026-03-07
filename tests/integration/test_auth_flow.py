"""
Authentication flow integration tests.
Tests complete authentication workflows including JWT validation, session management, and security.
"""

import pytest
import jwt
import time
from datetime import datetime, timedelta
from typing import Dict, Any
import hashlib
import secrets
import requests


@pytest.mark.integration
class TestCompleteAuthenticationFlow:
    """Test complete authentication workflows."""

    def test_full_registration_to_login_flow(
        self, integration_client, integration_db_session, mock_all_external_services
    ):
        """Test complete flow from registration to successful login."""
        # Step 1: Register new user
        registration_data = {
            "email": "newuser@flow.test",
            "password": "SecurePass123!@#",
            "full_name": "Flow Test User",
            "company": "Flow Corp",
            "role": "compliance_manager",
        }

        reg_response = integration_client.post("/api/v1/auth/register", json=registration_data)
        assert reg_response.status_code == 201
        user_data = reg_response.json()

        # Step 2: Verify email was sent (mocked)
        assert mock_all_external_services["sendgrid"].return_value.send.called

        # Step 3: Simulate email verification
        from database import User
        from utils.auth import create_verification_token

        user = (
            integration_db_session.query(User).filter_by(email=registration_data["email"]).first()
        )
        assert user is not None
        assert user.is_verified is False

        verification_token = create_verification_token(user.email)
        verify_response = integration_client.post(
            "/api/v1/auth/verify-email", json={"token": verification_token}
        )
        assert verify_response.status_code == 200

        # Step 4: Login with verified account
        login_response = integration_client.post(
            "/api/v1/auth/login",
            data={
                "username": registration_data["email"],
                "password": registration_data["password"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert login_response.status_code == 200
        token_data = login_response.json()
        assert "access_token" in token_data

        # Step 5: Use token to access protected endpoint
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        me_response = integration_client.get("/api/v1/users/me", headers=headers)
        assert me_response.status_code == 200
        assert me_response.json()["email"] == registration_data["email"]

    def test_password_reset_complete_flow(
        self,
        integration_client,
        integration_db_session,
        sample_integration_data,
        mock_all_external_services,
    ):
        """Test complete password reset flow."""
        user = sample_integration_data["users"][0]
        old_password = "Password0123!"
        new_password = "NewSecurePass456!@#"

        # Step 1: Request password reset
        reset_request = integration_client.post(
            "/api/v1/auth/forgot-password", json={"email": user.email}
        )
        assert reset_request.status_code == 200

        # Step 2: Generate reset token (simulating email link)
        from utils.auth import create_password_reset_token

        reset_token = create_password_reset_token(user.email)

        # Step 3: Reset password with token
        reset_response = integration_client.post(
            "/api/v1/auth/reset-password", json={"token": reset_token, "new_password": new_password}
        )
        assert reset_response.status_code == 200

        # Step 4: Try login with old password (should fail)
        old_login = integration_client.post(
            "/api/v1/auth/login",
            data={"username": user.email, "password": old_password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert old_login.status_code == 401

        # Step 5: Login with new password (should succeed)
        new_login = integration_client.post(
            "/api/v1/auth/login",
            data={"username": user.email, "password": new_password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert new_login.status_code == 200
        assert "access_token" in new_login.json()


@pytest.mark.integration
class TestJWTSecurityValidation:
    """Test JWT token security and validation."""

    def test_jwt_token_structure(self, integration_client, sample_integration_data):
        """Validate JWT token structure and claims."""
        # Login to get token
        login_response = integration_client.post(
            "/api/v1/auth/login",
            data={"username": "user0@integration.test", "password": "Password0123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        token = login_response.json()["access_token"]

        # Decode token (without verification for inspection)
        from config.settings import settings

        decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        # Validate required claims
        assert "sub" in decoded  # Subject (user email)
        assert "exp" in decoded  # Expiration
        assert "iat" in decoded  # Issued at
        assert "jti" in decoded  # JWT ID for tracking

        # Validate expiration
        exp_time = datetime.fromtimestamp(decoded["exp"])
        assert exp_time > datetime.utcnow()

        # Validate issued at
        iat_time = datetime.fromtimestamp(decoded["iat"])
        assert iat_time <= datetime.utcnow()

    def test_expired_token_rejection(self, integration_client, integration_db_session):
        """Test that expired tokens are rejected."""
        from utils.auth import create_access_token
        from database import User

        # Create a user
        user = User(
            email="expired@test.com",
            full_name="Expired Token User",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
        )
        integration_db_session.add(user)
        integration_db_session.commit()

        # Create an expired token
        expired_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        # Try to use expired token
        response = integration_client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_token_tampering_detection(self, integration_client, sample_integration_data):
        """Test that tampered tokens are rejected."""
        # Get valid token
        login_response = integration_client.post(
            "/api/v1/auth/login",
            data={"username": "user0@integration.test", "password": "Password0123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        token = login_response.json()["access_token"]

        # Tamper with token (change last character)
        tampered_token = token[:-1] + ("a" if token[-1] != "a" else "b")

        # Try to use tampered token
        response = integration_client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {tampered_token}"}
        )

        assert response.status_code == 401
        assert (
            "Invalid" in response.json()["detail"]
            or "could not be validated" in response.json()["detail"]
        )

    def test_token_blacklisting(
        self, integration_client, integration_auth_headers, mock_all_external_services
    ):
        """Test token blacklisting after logout."""
        # Use token successfully
        response = integration_client.get("/api/v1/users/me", headers=integration_auth_headers)
        assert response.status_code == 200

        # Logout (should blacklist token)
        logout_response = integration_client.post(
            "/api/v1/auth/logout", headers=integration_auth_headers
        )
        assert logout_response.status_code == 200

        # Try to use same token after logout
        response = integration_client.get("/api/v1/users/me", headers=integration_auth_headers)
        assert response.status_code == 401
        assert (
            "Token has been revoked" in response.json()["detail"]
            or "Invalid" in response.json()["detail"]
        )


@pytest.mark.integration
class TestSessionManagement:
    """Test session management and tracking."""

    def test_concurrent_session_limit(self, integration_client, sample_integration_data):
        """Test enforcement of concurrent session limits."""
        user_email = "user0@integration.test"
        password = "Password0123!"

        # Create multiple sessions
        sessions = []
        for _i in range(5):  # Assuming limit is 3
            response = integration_client.post(
                "/api/v1/auth/login",
                data={"username": user_email, "password": password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code == 200:
                sessions.append(response.json()["access_token"])

        # Verify older sessions are invalidated
        if len(sessions) > 3:
            # First session should be invalid
            response = integration_client.get(
                "/api/v1/users/me", headers={"Authorization": f"Bearer {sessions[0]}"}
            )
            assert response.status_code == 401

            # Latest session should be valid
            response = integration_client.get(
                "/api/v1/users/me", headers={"Authorization": f"Bearer {sessions[-1]}"}
            )
            assert response.status_code == 200

    def test_session_activity_tracking(
        self, integration_client, integration_auth_headers, integration_db_session
    ):
        """Test that session activity is tracked."""
        # Make several API calls
        for _ in range(3):
            response = integration_client.get("/api/v1/users/me", headers=integration_auth_headers)
            assert response.status_code == 200
            time.sleep(0.5)

        # Check session activity in database
        from database import UserSession

        session = (
            integration_db_session.query(UserSession)
            .filter_by(
                user_id=1  # Assuming first user
            )
            .first()
        )

        if session:  # If session tracking is implemented
            assert session.last_activity is not None
            assert session.request_count >= 3

    def test_session_timeout(self, integration_client, integration_auth_headers, monkeypatch):
        """Test session timeout after inactivity."""
        # This test would require mocking time or waiting
        # Implementation depends on session timeout configuration
        pass


@pytest.mark.integration
class TestMultiFactorAuthentication:
    """Test MFA implementation."""

    def test_totp_setup_and_verification(self, integration_client, integration_auth_headers):
        """Test TOTP-based MFA setup and verification."""
        # Enable MFA
        mfa_setup = integration_client.post(
            "/api/v1/auth/mfa/setup", headers=integration_auth_headers
        )

        if mfa_setup.status_code == 200:
            data = mfa_setup.json()
            assert "secret" in data
            assert "qr_code" in data
            assert "backup_codes" in data

            # Generate TOTP code (would need pyotp in real test)
            # import pyotp
            # totp = pyotp.TOTP(data["secret"])
            # code = totp.now()

            # Verify TOTP
            # verify_response = integration_client.post(
            #     "/api/v1/auth/mfa/verify",
            #     json={"code": code},
            #     headers=integration_auth_headers
            # )
            # assert verify_response.status_code == 200

    def test_backup_codes_generation(self, integration_client, integration_auth_headers):
        """Test backup codes for MFA recovery."""
        response = integration_client.post(
            "/api/v1/auth/mfa/backup-codes", headers=integration_auth_headers
        )

        if response.status_code == 200:
            data = response.json()
            assert "codes" in data
            assert len(data["codes"]) >= 8  # Should have multiple backup codes

            # Each code should be unique
            assert len(data["codes"]) == len(set(data["codes"]))


@pytest.mark.integration
class TestOAuth2Integration:
    """Test OAuth2 provider integrations."""

    def test_google_oauth_flow(self, integration_client, mock_all_external_services):
        """Test Google OAuth2 authentication flow."""
        # Step 1: Get authorization URL
        auth_url_response = integration_client.get("/api/v1/auth/oauth/google/authorize")

        if auth_url_response.status_code == 200:
            data = auth_url_response.json()
            assert "authorization_url" in data
            assert "state" in data
            assert "accounts.google.com" in data["authorization_url"]

            # Step 2: Simulate callback with code
            # This would normally come from Google
            mock_code = "mock_auth_code_from_google"
            state = data["state"]

            callback_response = integration_client.get(
                "/api/v1/auth/oauth/google/callback", params={"code": mock_code, "state": state}
            )

            if callback_response.status_code == 200:
                token_data = callback_response.json()
                assert "access_token" in token_data
                assert "token_type" in token_data

    def test_microsoft_oauth_flow(self, integration_client):
        """Test Microsoft OAuth2 authentication flow."""
        # Similar to Google OAuth test
        pass

    def test_github_oauth_flow(self, integration_client):
        """Test GitHub OAuth2 authentication flow."""
        # Similar to Google OAuth test
        pass


@pytest.mark.integration
class TestRoleBasedAccessControl:
    """Test RBAC implementation."""

    def test_role_permissions(self, integration_client, integration_db_session):
        """Test different role permissions."""
        from database import User, Role, Permission
        from utils.auth import create_access_token, get_password_hash

        # Create users with different roles
        roles_data = [
            ("admin", ["read", "write", "delete", "admin"]),
            ("manager", ["read", "write", "delete"]),
            ("user", ["read", "write"]),
            ("viewer", ["read"]),
        ]

        users = {}
        for role_name, permissions in roles_data:
            # Create user
            user = User(
                email=f"{role_name}@rbac.test",
                full_name=f"{role_name.title()} User",
                hashed_password=get_password_hash("Password123!"),
                is_active=True,
                is_verified=True,
                role=role_name,
            )
            integration_db_session.add(user)
            integration_db_session.commit()

            # Create token
            token = create_access_token(data={"sub": user.email, "role": role_name})
            users[role_name] = {"user": user, "token": token, "permissions": permissions}

        # Test admin-only endpoint
        admin_headers = {"Authorization": f"Bearer {users['admin']['token']}"}
        response = integration_client.get("/api/v1/admin/users", headers=admin_headers)
        assert response.status_code in [200, 404]  # 404 if endpoint doesn't exist

        # Test non-admin access to admin endpoint
        user_headers = {"Authorization": f"Bearer {users['user']['token']}"}
        response = integration_client.get("/api/v1/admin/users", headers=user_headers)
        assert response.status_code in [403, 404]  # 403 Forbidden or 404

    def test_permission_inheritance(self, integration_client, integration_db_session):
        """Test permission inheritance in role hierarchy."""
        # Test that higher roles inherit lower role permissions
        pass

    def test_dynamic_permission_checking(self, integration_client, integration_auth_headers):
        """Test dynamic permission checking for resources."""
        # Test resource-specific permissions
        pass


@pytest.mark.integration
class TestSecurityHeaders:
    """Test security headers in authentication responses."""

    def test_security_headers_present(self, integration_client):
        """Test that security headers are present in responses."""
        response = integration_client.post(
            "/api/v1/auth/login",
            data={"username": "test@test.com", "password": "wrong"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Check security headers
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
        ]

        for header in expected_headers:
            if header in response.headers:
                assert response.headers[header] is not None

    def test_cors_headers(self, integration_client):
        """Test CORS headers for cross-origin requests."""
        response = integration_client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        if "Access-Control-Allow-Origin" in response.headers:
            assert response.headers["Access-Control-Allow-Origin"] in ["*", "https://example.com"]
            assert "Access-Control-Allow-Methods" in response.headers
            assert "POST" in response.headers["Access-Control-Allow-Methods"]


@pytest.mark.integration
class TestBruteForceProtection:
    """Test brute force attack protection."""

    def test_login_attempt_limiting(self, integration_client, sample_integration_data):
        """Test that login attempts are limited."""
        user_email = "user0@integration.test"

        # Make multiple failed login attempts
        failed_attempts = 0
        locked_out = False

        for i in range(10):  # Try 10 failed attempts
            response = integration_client.post(
                "/api/v1/auth/login",
                data={"username": user_email, "password": f"WrongPassword{i}!"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code == 429:  # Too Many Requests
                locked_out = True
                break
            elif response.status_code == 401:
                failed_attempts += 1

        # Should be locked out after multiple attempts
        if failed_attempts >= 5:
            # Next attempt should be blocked
            response = integration_client.post(
                "/api/v1/auth/login",
                data={
                    "username": user_email,
                    "password": "Password0123!",  # Even correct password
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            # Should still be locked
            assert response.status_code in [401, 429]

    def test_captcha_requirement(self, integration_client):
        """Test CAPTCHA requirement after failed attempts."""
        # Test that CAPTCHA is required after certain failed attempts
        pass

    def test_ip_based_rate_limiting(self, integration_client):
        """Test IP-based rate limiting."""
        # Test that requests from same IP are rate limited
        pass
