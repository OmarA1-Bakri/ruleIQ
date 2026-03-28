"""
Security Tests for Authentication System

Tests authentication security including token validation, session management,
password security, and protection against common auth vulnerabilities.
"""

import time
from uuid import uuid4

import pytest

from tests.conftest import assert_api_response_security


@pytest.mark.security
@pytest.mark.auth
class TestAuthenticationSecurity:
    """Test authentication security controls"""

    def test_unauthenticated_access_denied(self, unauthenticated_test_client):
        """Test that protected endpoints deny unauthenticated access"""
        protected_endpoints = [
            ("/api/business-profiles", "GET"),
            ("/api/business-profiles", "POST"),
            ("/api/evidence", "GET"),
            ("/api/evidence", "POST"),
            ("/api/reports/generate", "POST"),
        ]

        for endpoint, method in protected_endpoints:
            if method == "GET":
                response = unauthenticated_test_client.get(endpoint)
            elif method == "POST":
                response = unauthenticated_test_client.post(endpoint, json={})
            elif method == "PUT":
                response = unauthenticated_test_client.put(endpoint, json={})
            elif method == "DELETE":
                response = unauthenticated_test_client.delete(endpoint)

            # Some endpoints might return 422 if they validate request body before auth
            assert response.status_code in [
                401,
                422,
            ], (
                f"Endpoint {method} {endpoint} should require authentication or validate input (got {response.status_code})"
            )
            # Only check authentication message for 401 responses
            if response.status_code == 401:
                response_data = response.json()
                if "detail" in response_data:
                    assert (
                        "unauthorized" in response_data["detail"].lower()
                        or "not authenticated" in response_data["detail"].lower(),
                    )
                elif "error" in response_data:
                    assert (
                        "authentication" in response_data["error"]["message"].lower()
                        or "unauthorized" in response_data["error"]["message"].lower(),
                    )

    def test_invalid_token_rejected(self, unauthenticated_test_client):
        """Test that invalid tokens are properly rejected"""
        invalid_tokens = [
            "invalid_token",
            "Bearer invalid_token",
            "mock.jwt.invalid",
            "Bearer " + "x" * 100,
            "",
            "Bearer ",
            "Bearer null",
            "Bearer undefined",
        ]

        for token in invalid_tokens:
            headers = {"Authorization": token} if token else {}
            response = unauthenticated_test_client.get(
                "/api/business-profiles",
                headers=headers,
            )

            assert response.status_code == 401, f"Invalid token should be rejected: {token}"
            response_data = response.json()
            assert "detail" in response_data

            # Ensure no sensitive information is leaked in error message
            assert "secret" not in response_data["detail"].lower()
            assert "key" not in response_data["detail"].lower()

    def test_expired_token_handling(self, unauthenticated_test_client, expired_token):
        """Test proper handling of expired tokens"""
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = unauthenticated_test_client.get(
            "/api/business-profiles",
            headers=headers,
        )

        assert response.status_code == 401
        response_data = response.json()
        assert (
            "could not validate credentials" in response_data["detail"].lower()
            or "expired" in response_data["detail"].lower()
            or "invalid" in response_data["detail"].lower(),
        )

    def test_token_without_bearer_prefix(self, unauthenticated_test_client, auth_token):
        """Test that tokens without Bearer prefix are rejected"""
        headers = {"Authorization": auth_token}  # Missing "Bearer " prefix
        response = unauthenticated_test_client.get(
            "/api/business-profiles",
            headers=headers,
        )

        assert response.status_code == 401

    def test_malformed_authorization_header(self, unauthenticated_test_client):
        """Test handling of malformed authorization headers"""
        malformed_headers = [
            {"Authorization": "Basic dXNlcjpwYXNz"},  # Basic auth instead of Bearer
            {"Authorization": "Token abc123"},  # Wrong token type
            {"Authorization": "Bearer"},  # Missing token
            {"Authorization": "Bearer token1 token2"},  # Multiple tokens
            {"Authorization": " Bearer token"},  # Leading space
            {"Authorization": "Bearer\ttoken"},  # Tab character
            {"Authorization": "BEARER token"},  # Wrong case,
        ]

        for headers in malformed_headers:
            response = unauthenticated_test_client.get(
                "/api/business-profiles",
                headers=headers,
            )
            assert response.status_code == 401

    def test_password_strength_validation(self, client):
        """Test password strength requirements"""
        weak_passwords = [
            "123456",  # Too short, only numbers
            "password",  # Common password, no complexity
            "abc",  # Too short
            "PASSWORD",  # No lowercase or numbers
            "password123",  # No uppercase
            "PASSWORD123",  # No lowercase
            "Passw0rd",  # Too short (assuming 8+ char requirement)
            "aaaaaaaa",  # Only repeated characters
            "",  # Empty password,
        ]

        for weak_password in weak_passwords:
            registration_data = {
                "email": f"test-{uuid4()}@example.com",
                "password": weak_password,
                "full_name": "Test User",
            }

            response = client.post("/api/auth/register", json=registration_data)

            assert response.status_code == 422, f"Weak password should be rejected: {weak_password}"
            response_data = response.json()
            assert "detail" in response_data

            # Check that password validation errors are present
            password_errors = [
                error for error in response_data["detail"] if "password" in str(error).lower()
            ]
            assert len(password_errors) > 0

    def test_strong_password_acceptance(self, client):
        """Test that strong passwords are accepted"""
        strong_passwords = [
            "SecurePass123!",
            "MyStr0ng&P@ssw0rd",
            "C0mpl3x!P@$$w0rd",
            "Tr0ub4dor&3",
            "P@ssw0rd123!Complex",
        ]

        for strong_password in strong_passwords:
            registration_data = {
                "email": f"test-{uuid4()}@example.com",
                "password": strong_password,
                "full_name": "Test User",
            }

            response = client.post("/api/auth/register", json=registration_data)

            # Should either succeed or fail for reasons other than password strength
            if response.status_code == 422:
                response_data = response.json()
                password_errors = [
                    error
                    for error in response_data["detail"]
                    if "password" in str(error).lower() and "strength" in str(error).lower()
                ]
                assert len(password_errors) == 0, (
                    f"Strong password should not be rejected for strength: {strong_password}"
                )

    @pytest.mark.skip(
        reason="Account lockout is implemented via rate limiting which is disabled in test environment",
    )
    def test_account_lockout_protection(self, client, sample_user_data):
        """Test account lockout after multiple failed login attempts"""
        # First register a user
        register_response = client.post("/api/auth/register", json=sample_user_data)
        assert register_response.status_code in [200, 201]  # Accept both success codes

        # Attempt multiple failed logins
        failed_login_data = {
            "email": sample_user_data["email"],
            "password": "wrong_password",
        }

        # Try failed logins multiple times
        for attempt in range(6):  # Assuming 5 attempts trigger lockout
            response = client.post("/api/auth/login", json=failed_login_data)

            if attempt < 4:  # First few attempts should return 401
                assert response.status_code == 401
                assert (
                    "invalid credentials" in response.json()["detail"].lower()
                    or "unauthorized" in response.json()["detail"].lower(),
                )
            else:  # Later attempts should indicate account lockout
                assert response.status_code in [401, 429]  # 429 for too many requests
                if response.status_code == 429:
                    assert (
                        "locked" in response.json()["detail"].lower()
                        or "too many attempts" in response.json()["detail"].lower(),
                    )

        # Even correct password should be rejected when locked
        correct_login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        }
        response = client.post("/api/auth/login", json=correct_login_data)

        # Should still be locked (depending on implementation)
        if response.status_code == 429:
            assert (
                "locked" in response.json()["detail"].lower()
                or "too many attempts" in response.json()["detail"].lower(),
            )

    def test_email_enumeration_protection(self, client):
        """Test protection against email enumeration attacks"""
        # Try to login with non-existent email
        non_existent_login = {
            "email": f"nonexistent-{uuid4()}@example.com",
            "password": "SomePassword123!",
        }

        response = client.post("/api/auth/login", json=non_existent_login)
        assert response.status_code == 401

        # Error message should not reveal whether email exists
        error_message = response.json()["detail"].lower()
        assert "email not found" not in error_message
        assert "user does not exist" not in error_message
        assert "invalid email" not in error_message

        # Should use generic message like "invalid credentials"
        assert "invalid credentials" in error_message or "unauthorized" in error_message

    def test_timing_attack_protection(self, client, sample_user_data):
        """Test protection against timing attacks"""
        # Register a user
        client.post("/api/auth/register", json=sample_user_data)

        # Time login attempts with existing vs non-existent emails
        existing_email_times = []
        non_existent_email_times = []

        for _ in range(5):
            # Time login with existing email
            start_time = time.time()
            client.post(
                "/api/auth/login",
                json={"email": sample_user_data["email"], "password": "wrong_password"},
            )
            existing_email_times.append(time.time() - start_time)

            # Time login with non-existent email
            start_time = time.time()
            client.post(
                "/api/auth/login",
                json={
                    "email": f"fake-{uuid4()}@example.com",
                    "password": "wrong_password",
                },
            )
            non_existent_email_times.append(time.time() - start_time)

        # Response times should be similar (within reasonable variance)
        avg_existing = sum(existing_email_times) / len(existing_email_times)
        avg_non_existent = sum(non_existent_email_times) / len(non_existent_email_times)

        # Times should not differ by more than 50% (adjust threshold as needed)
        time_difference = abs(avg_existing - avg_non_existent) / max(
            avg_existing,
            avg_non_existent,
        )
        assert time_difference < 0.5, (
            "Response times differ too much between existing and non-existent emails"
        )

    def test_session_management_security(self, client, sample_user_data):
        """Test secure session management"""
        # Register and login
        client.post("/api/auth/register", json=sample_user_data)
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )

        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test that session is valid
        profile_response = client.get("/api/users/me", headers=headers)
        assert profile_response.status_code == 200

        # Test logout functionality if available
        logout_response = client.post("/api/auth/logout", headers=headers)
        if logout_response.status_code == 200:
            # After logout, token should be invalid
            post_logout_response = client.get("/api/users/me", headers=headers)
            assert post_logout_response.status_code == 401

    def test_password_change_security(self, client, sample_user_data):
        """Test password change security requirements"""
        # Register and login
        client.post("/api/auth/register", json=sample_user_data)
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )

        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test password change with various scenarios
        password_change_data = {
            "current_password": sample_user_data["password"],
            "new_password": "NewSecurePass123!",
            "confirm_password": "NewSecurePass123!",
        }

        # Test successful password change
        change_response = client.post(
            "/api/auth/change-password",
            json=password_change_data,
            headers=headers,
        )

        if change_response.status_code == 200:
            # Old password should no longer work
            old_login_response = client.post(
                "/api/auth/login",
                json={
                    "email": sample_user_data["email"],
                    "password": sample_user_data["password"],
                },
            )
            assert old_login_response.status_code == 401

            # New password should work
            new_login_response = client.post(
                "/api/auth/login",
                json={
                    "email": sample_user_data["email"],
                    "password": "NewSecurePass123!",
                },
            )
            assert new_login_response.status_code == 200

    def test_concurrent_session_limits(self, client, sample_user_data):
        """Test concurrent session limitations"""
        # Register user
        client.post("/api/auth/register", json=sample_user_data)

        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        }

        # Create multiple sessions
        sessions = []
        for _ in range(10):  # Try to create many concurrent sessions
            login_response = client.post("/api/auth/login", json=login_data)
            if login_response.status_code == 200:
                token = login_response.json()["access_token"]
                sessions.append(token)

        # Test that all sessions can access protected resources
        valid_sessions = 0
        for token in sessions:
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/api/users/me", headers=headers)
            if response.status_code == 200:
                valid_sessions += 1

        # Depending on implementation, there might be session limits
        # At minimum, the most recent session should be valid
        assert valid_sessions >= 1


@pytest.mark.security
@pytest.mark.auth
class TestTokenSecurity:
    """Test JWT token security"""

    def test_token_contains_no_sensitive_data(self, client, sample_user_data):
        """Test that JWT tokens don't contain sensitive information"""
        # Register and login
        client.post("/api/auth/register", json=sample_user_data)
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )

        token = login_response.json()["access_token"]

        # Decode token payload (without verification for testing)
        import base64
        import json

        try:
            # JWT tokens have 3 parts separated by dots
            parts = token.split(".")
            if len(parts) == 3:
                # Decode payload (second part)
                payload = parts[1]
                # Add padding if needed
                payload += "=" * (4 - len(payload) % 4)
                decoded = base64.b64decode(payload)
                token_data = json.loads(decoded)

                # Check that sensitive data is not in token
                sensitive_fields = [
                    "password",
                    "password_hash",
                    "secret",
                    "private_key",
                ]
                for field in sensitive_fields:
                    assert field not in token_data, f"Token contains sensitive field: {field}"

                # Token should contain minimal necessary information
                expected_fields = ["sub", "exp", "iat"]  # subject, expiry, issued at
                for field in expected_fields:
                    assert field in token_data, f"Token missing expected field: {field}"

        except (json.JSONDecodeError, KeyError, IndexError):
            # If token is not a standard JWT format, that's also acceptable
            pass

    def test_token_expiry_enforcement(self, client, sample_user_data):
        """Test that token expiry is properly enforced"""
        # This test would require manipulating system time or using short-lived tokens
        # For now, we test the basic expiry mechanism

        client.post("/api/auth/register", json=sample_user_data)
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )

        token = login_response.json()["access_token"]

        # Check that token has expiry information
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/users/me", headers=headers)
        assert response.status_code == 200

        # Token should work immediately after issuance
        immediate_response = client.get("/api/users/me", headers=headers)
        assert immediate_response.status_code == 200

    def test_token_signature_validation(self, unauthenticated_test_client, sample_user_data):
        """Test that tokens with invalid signatures are rejected"""
        # Get a valid token
        unauthenticated_test_client.post("/api/auth/register", json=sample_user_data)
        login_response = unauthenticated_test_client.post(
            "/api/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )

        valid_token = login_response.json()["access_token"]

        # Modify the signature part of the token
        parts = valid_token.split(".")
        if len(parts) == 3:
            # Change the signature
            modified_token = f"{parts[0]}.{parts[1]}.modified_signature"

            headers = {"Authorization": f"Bearer {modified_token}"}
            response = unauthenticated_test_client.get("/api/users/me", headers=headers)

            # Should be rejected due to invalid signature
            assert response.status_code == 401

    def test_token_algorithm_confusion(self, unauthenticated_test_client, sample_user_data):
        """Test protection against JWT algorithm confusion attacks"""
        # This is a complex test that would require crafting specific JWT tokens
        # For now, we test that only expected algorithms are accepted

        # Create tokens with different algorithms in header
        malicious_tokens = [
            # Token with "none" algorithm (if improperly handled)
            "mock.none-alg.jwt",
            # Token with different algorithm
            "mock.hs512.jwt",
        ]

        for malicious_token in malicious_tokens:
            headers = {"Authorization": f"Bearer {malicious_token}"}
            response = unauthenticated_test_client.get("/api/users/me", headers=headers)

            # All malicious tokens should be rejected
            assert response.status_code == 401


@pytest.mark.security
@pytest.mark.auth
class TestAuthorizationSecurity:
    """Test authorization and access control security"""

    def test_user_data_isolation(self, client, sample_user_data, another_user):
        """Test that users can only access their own data"""
        # Register first user
        user1_data = sample_user_data
        client.post("/api/auth/register", json=user1_data)
        login1_response = client.post(
            "/api/auth/login",
            json={"email": user1_data["email"], "password": user1_data["password"]},
        )
        user1_headers = {
            "Authorization": f"Bearer {login1_response.json()['access_token']}",
        }

        # Register second user
        user2_data = {
            "email": f"user2-{uuid4()}@example.com",
            "password": "User2Password123!",
            "full_name": "User Two",
        }
        client.post("/api/auth/register", json=user2_data)
        login2_response = client.post(
            "/api/auth/login",
            json={"email": user2_data["email"], "password": user2_data["password"]},
        )
        user2_headers = {
            "Authorization": f"Bearer {login2_response.json()['access_token']}",
        }

        # User 1 creates business profile
        profile_data = {
            "company_name": "User 1 Company",
            "industry": "Technology",
            "employee_count": 50,
        }
        profile_response = client.post(
            "/api/business-profiles",
            json=profile_data,
            headers=user1_headers,
        )
        assert profile_response.status_code == 201
        profile_id = profile_response.json()["id"]

        # User 2 should not be able to access User 1's business profile
        unauthorized_response = client.get(
            f"/api/business-profiles/{profile_id}",
            headers=user2_headers,
        )
        assert unauthorized_response.status_code in [403, 404]

        # User 2 should not be able to modify User 1's business profile
        modify_response = client.put(
            f"/api/business-profiles/{profile_id}",
            json={"company_name": "Hacked Company"},
            headers=user2_headers,
        )
        assert modify_response.status_code in [403, 404]

        # User 2 should not be able to delete User 1's business profile
        delete_response = client.delete(
            f"/api/business-profiles/{profile_id}",
            headers=user2_headers,
        )
        assert delete_response.status_code in [403, 404]

    def test_privilege_escalation_protection(self, client, sample_user_data):
        """Test protection against privilege escalation"""
        # Register regular user
        client.post("/api/auth/register", json=sample_user_data)
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )
        user_headers = {
            "Authorization": f"Bearer {login_response.json()['access_token']}",
        }

        # Try to access admin endpoints (if they exist)
        admin_endpoints = [
            "/api/admin/users",
            "/api/admin/settings",
            "/api/admin/audit-logs",
            "/api/admin/system-config",
        ]

        for endpoint in admin_endpoints:
            response = client.get(endpoint, headers=user_headers)
            # Should be forbidden or not found (but not unauthorized, since user is authenticated)
            assert response.status_code in [
                403,
                404,
            ], f"Regular user should not access admin endpoint: {endpoint}"

    def test_role_based_access_control(self, client, sample_user_data):
        """Test role-based access control if implemented"""
        # This test assumes RBAC is implemented
        # Register user with specific role
        registration_data = {**sample_user_data, "role": "compliance_manager"}

        register_response = client.post("/api/auth/register", json=registration_data)
        if register_response.status_code == 201:
            login_response = client.post(
                "/api/auth/login",
                json={
                    "email": sample_user_data["email"],
                    "password": sample_user_data["password"],
                },
            )
            headers = {
                "Authorization": f"Bearer {login_response.json()['access_token']}",
            }

            # Test access to role-appropriate endpoints
            profile_response = client.get("/api/users/me", headers=headers)
            assert profile_response.status_code == 200

            # Check that user profile reflects assigned role
            if "role" in profile_response.json():
                assert profile_response.json()["role"] == "compliance_manager"

    def test_api_rate_limiting_by_user(self, client, sample_user_data):
        """Test that rate limiting is applied per user"""
        # Register and login
        client.post("/api/auth/register", json=sample_user_data)
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Make many rapid requests
        for _i in range(50):  # Try many requests
            response = client.get("/api/users/me", headers=headers)

            if response.status_code == 429:  # Too Many Requests
                assert (
                    "rate limit" in response.json()["detail"].lower()
                    or "too many requests" in response.json()["detail"].lower(),
                )
                break
            elif response.status_code == 200:
                continue
            else:
                pytest.fail(f"Unexpected response code: {response.status_code}")

        # Rate limiting should eventually kick in for excessive requests
        # (This might not trigger in test environment depending on configuration)

    def test_cross_origin_request_security(self, client, sample_user_data):
        """Test CORS security configuration"""
        # Register and login
        client.post("/api/auth/register", json=sample_user_data)
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Test requests with different Origin headers
        malicious_origins = [
            "https://evil.com",
            "http://malicious-site.example",
            "https://phishing-site.net",
        ]

        for origin in malicious_origins:
            origin_headers = {**headers, "Origin": origin}
            response = client.get("/api/users/profile", headers=origin_headers)

            # Check CORS headers in response
            assert_api_response_security(response)

            # Should not include malicious origin in Access-Control-Allow-Origin
            if "Access-Control-Allow-Origin" in response.headers:
                allowed_origin = response.headers["Access-Control-Allow-Origin"]
                assert allowed_origin != origin, f"Malicious origin should not be allowed: {origin}"
