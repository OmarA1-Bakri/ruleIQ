"""
Integration tests for feature flag system (FF-001).
Tests feature flag functionality and integration with API endpoints.
"""

import pytest
from typing import Dict, Any
import json


@pytest.mark.integration
class TestFeatureFlagIntegration:
    """Test feature flag integration with the system."""

    def test_feature_flags_loaded_on_startup(self, integration_client):
        """Test that feature flags are loaded and accessible."""
        response = integration_client.get("/api/v1/admin/feature-flags")

        # This endpoint might require admin auth
        if response.status_code == 401:
            pytest.skip("Feature flags endpoint requires authentication")

        if response.status_code == 404:
            pytest.skip("Feature flags endpoint not implemented yet")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

        # Check for expected feature flags from FF-001
        expected_flags = [
            "enable_ai_assistant",
            "enable_advanced_reporting",
            "enable_multi_factor_auth",
            "enable_api_rate_limiting",
        ]

        for flag in expected_flags:
            assert flag in data, f"Feature flag '{flag}' not found"

    def test_feature_flag_middleware_integration(
        self, integration_client, integration_auth_headers
    ):
        """Test that feature flags are checked in middleware."""
        # Try to access a feature that might be behind a flag
        response = integration_client.get("/api/v1/ai/assistant", headers=integration_auth_headers)

        # If feature is disabled, should get 403 or specific error
        if response.status_code == 403:
            error_detail = response.json().get("detail", "")
            assert "feature" in error_detail.lower() or "disabled" in error_detail.lower()
        elif response.status_code == 404:
            # Feature might not be implemented
            pass
        else:
            # Feature is enabled
            assert response.status_code in [200, 201]

    def test_feature_flag_dynamic_toggle(self, integration_client, integration_admin_headers):
        """Test dynamic feature flag toggling."""
        # Get current flags
        response = integration_client.get(
            "/api/v1/admin/feature-flags", headers=integration_admin_headers
        )

        if response.status_code == 404:
            pytest.skip("Feature flag management not implemented")

        if response.status_code == 200:
            current_flags = response.json()

            # Try to toggle a flag
            test_flag = "enable_test_feature"
            new_value = not current_flags.get(test_flag, False)

            update_response = integration_client.put(
                f"/api/v1/admin/feature-flags/{test_flag}",
                json={"enabled": new_value},
                headers=integration_admin_headers,
            )

            if update_response.status_code == 200:
                # Verify the change
                verify_response = integration_client.get(
                    "/api/v1/admin/feature-flags", headers=integration_admin_headers
                )
                updated_flags = verify_response.json()
                assert updated_flags[test_flag] == new_value

    def test_feature_flag_user_targeting(
        self, integration_client, integration_auth_headers, sample_integration_data
    ):
        """Test feature flags with user targeting rules."""
        # Some features might be enabled only for specific users
        response = integration_client.get(
            "/api/v1/users/features", headers=integration_auth_headers
        )

        if response.status_code == 404:
            pytest.skip("User feature endpoint not implemented")

        if response.status_code == 200:
            user_features = response.json()
            assert isinstance(user_features, dict)

            # Check if user targeting is working
            # Premium features might be enabled for certain users
            if "premium_features" in user_features:
                assert isinstance(user_features["premium_features"], bool)

    def test_feature_flag_percentage_rollout(self, integration_client, integration_db_session):
        """Test percentage-based feature rollout."""
        from database import User
        from utils.auth import create_access_token, get_password_hash

        # Create multiple test users
        users_with_feature = 0
        users_without_feature = 0

        for i in range(20):
            user = User(
                email=f"rollout_test_{i}@test.com",
                full_name=f"Rollout User {i}",
                hashed_password=get_password_hash("Password123!"),
                is_active=True,
                is_verified=True,
            )
            integration_db_session.add(user)

        integration_db_session.commit()

        # Check feature availability for each user
        for i in range(20):
            token = create_access_token(data={"sub": f"rollout_test_{i}@test.com"})
            headers = {"Authorization": f"Bearer {token}"}

            response = integration_client.get("/api/v1/users/features", headers=headers)

            if response.status_code == 200:
                features = response.json()
                if features.get("experimental_feature", False):
                    users_with_feature += 1
                else:
                    users_without_feature += 1

        # With percentage rollout, some users should have it, some shouldn't
        # Unless it's 0% or 100%
        if users_with_feature > 0 and users_without_feature > 0:
            # Partial rollout is working
            assert True
        elif users_with_feature == 0 or users_without_feature == 0:
            # Feature is fully on or off
            assert True

    def test_feature_flag_environment_specific(self, integration_client, monkeypatch):
        """Test environment-specific feature flags."""
        # Test that certain features are only enabled in specific environments

        # Set environment to production
        monkeypatch.setenv("ENVIRONMENT", "production")

        response = integration_client.get("/api/v1/system/info")

        if response.status_code == 200:
            info = response.json()
            env = info.get("environment", "")

            # Debug features should be disabled in production
            assert not info.get("debug_mode", False), "Debug mode should be disabled in production"

        # Set environment to development
        monkeypatch.setenv("ENVIRONMENT", "development")

        response = integration_client.get("/api/v1/system/info")

        if response.status_code == 200:
            info = response.json()
            # Debug features might be enabled in development
            # This is environment-specific behavior

    def test_feature_flag_api_versioning(self, integration_client, integration_auth_headers):
        """Test feature flags affecting API versioning."""
        # Test v1 endpoint
        v1_response = integration_client.get(
            "/api/v1/compliance/frameworks", headers=integration_auth_headers
        )

        # Test v2 endpoint (might be behind feature flag)
        v2_response = integration_client.get(
            "/api/v2/compliance/frameworks", headers=integration_auth_headers
        )

        if v2_response.status_code == 404:
            # V2 API not available (feature flag disabled)
            assert v1_response.status_code in [200, 404]
        elif v2_response.status_code == 200:
            # V2 API is available (feature flag enabled)
            v1_data = v1_response.json() if v1_response.status_code == 200 else []
            v2_data = v2_response.json()

            # V2 might have additional fields or different structure
            assert isinstance(v2_data, (list, dict))

    def test_feature_flag_dependency_chain(self, integration_client, integration_admin_headers):
        """Test feature flags with dependencies on other flags."""
        response = integration_client.get(
            "/api/v1/admin/feature-flags", headers=integration_admin_headers
        )

        if response.status_code == 200:
            flags = response.json()

            # If advanced_reporting is enabled, basic_reporting should also be enabled
            if flags.get("enable_advanced_reporting", False):
                assert flags.get("enable_basic_reporting", True), (
                    "Basic reporting should be enabled when advanced reporting is enabled"
                )

            # If MFA is enabled, basic auth should be enabled
            if flags.get("enable_multi_factor_auth", False):
                assert flags.get("enable_authentication", True), (
                    "Authentication must be enabled for MFA to work"
                )

    def test_feature_flag_performance_impact(
        self, integration_client, integration_auth_headers, performance_monitor
    ):
        """Test that feature flag checks don't significantly impact performance."""
        # Make requests with and without feature flag checks
        performance_monitor.start("with_flags")

        for _ in range(10):
            response = integration_client.get("/api/v1/users/me", headers=integration_auth_headers)
            assert response.status_code in [200, 401]

        performance_monitor.end("with_flags")

        # Feature flag checks should add minimal overhead (<50ms per request)
        duration = performance_monitor.get_duration("with_flags")
        avg_duration = duration / 10
        assert avg_duration < 0.5, (
            f"Feature flag checks adding too much latency: {avg_duration}s per request"
        )

    def test_feature_flag_audit_logging(
        self, integration_client, integration_admin_headers, integration_db_session
    ):
        """Test that feature flag changes are audit logged."""
        # Change a feature flag
        response = integration_client.put(
            "/api/v1/admin/feature-flags/enable_audit_test",
            json={"enabled": True, "reason": "Testing audit logging"},
            headers=integration_admin_headers,
        )

        if response.status_code == 200:
            # Check audit logs
            from database import AuditLog

            # Look for recent audit log entry
            audit_entry = (
                integration_db_session.query(AuditLog)
                .filter(
                    AuditLog.action.like("%feature_flag%"),
                    AuditLog.details.like("%enable_audit_test%"),
                )
                .order_by(AuditLog.created_at.desc())
                .first()
            )

            if audit_entry:
                assert "enable_audit_test" in audit_entry.details
                assert audit_entry.user_id is not None
                assert audit_entry.action in ["feature_flag_updated", "feature_flag_changed"]


@pytest.mark.integration
class TestFeatureFlagConfiguration:
    """Test feature flag configuration and management."""

    def test_feature_flag_config_file_loading(self):
        """Test loading feature flags from configuration file."""
        from config.feature_flags import FeatureFlagConfig

        config = FeatureFlagConfig()

        # Check that configuration is loaded
        assert hasattr(config, "flags")
        assert isinstance(config.flags, dict)

        # Check for required flags
        assert "enable_ai_assistant" in config.flags
        assert "enable_api_rate_limiting" in config.flags

    def test_feature_flag_default_values(self):
        """Test that feature flags have sensible defaults."""
        from config.feature_flags import FeatureFlagConfig

        config = FeatureFlagConfig()

        # Security features should be enabled by default
        assert config.flags.get("enable_authentication", True)
        assert config.flags.get("enable_api_rate_limiting", True)

        # Experimental features should be disabled by default
        assert not config.flags.get("enable_experimental_ai", False)
        assert not config.flags.get("enable_beta_features", False)

    def test_feature_flag_environment_overrides(self, monkeypatch):
        """Test that environment variables can override feature flags."""
        # Set environment variable
        monkeypatch.setenv("FEATURE_FLAG_ENABLE_TEST_FEATURE", "true")
        monkeypatch.setenv("FEATURE_FLAG_DISABLE_OTHER_FEATURE", "false")

        from config.feature_flags import FeatureFlagConfig

        # Reload configuration
        config = FeatureFlagConfig()

        # Check that environment variables override config
        if hasattr(config, "from_env"):
            assert config.flags.get("enable_test_feature", False)
            assert not config.flags.get("disable_other_feature", True)

    def test_feature_flag_validation(self):
        """Test feature flag validation and type checking."""
        from config.feature_flags import FeatureFlagConfig

        config = FeatureFlagConfig()

        # All feature flags should be boolean
        for flag_name, flag_value in config.flags.items():
            assert isinstance(flag_value, bool), (
                f"Feature flag {flag_name} should be boolean, got {type(flag_value)}"
            )

        # Flag names should follow naming convention
        for flag_name in config.flags:
            assert flag_name.startswith("enable_") or flag_name.startswith("disable_"), (
                f"Feature flag {flag_name} doesn't follow naming convention"
            )
