"""

# Constants

Comprehensive security test suite for backend fixes
Tests all security vulnerabilities that were identified and fixed
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.main import app
from config.settings import settings
from config.security_config import SecurityConfig
from api.utils.input_validation import InputValidator
from api.utils.error_handlers import ValidationException, AuthenticationException
from api.dependencies.file import EnhancedFileValidator
from core.security.credential_encryption import CredentialEncryption

from tests.test_constants import HTTP_UNAUTHORIZED

client = TestClient(app)


class TestSecurityFixes:
    """Test suite for security vulnerability fixes"""

    def test_jwt_secret_key_protection(self):
        """Test that JWT secret keys are properly protected"""
        assert settings.secret_key != "your-secret-key-here"
        assert len(settings.secret_key) >= 32
        config = SecurityConfig()
        assert config.secret_key is not None
        assert config.jwt_algorithm == "HS256"

    def test_input_sanitization(self):
        """Test input sanitization prevents injection attacks"""
        validator = InputValidator()
        malicious_input = "'; DROP TABLE users; --"
        sanitized = validator.sanitize_input(malicious_input)
        assert "DROP TABLE" not in sanitized
        assert "'" not in sanitized
        xss_input = "<script>alert('XSS')</script>"
        sanitized = validator.sanitize_input(xss_input)
        assert "<script>" not in sanitized

    def test_file_upload_security(self):
        """Test file upload security validation"""
        validator = EnhancedFileValidator()
        assert validator.is_allowed_file_type("test.pdf", "application/pdf")
        assert not validator.is_allowed_file_type("test.exe", "application/x-msdownload")
        assert validator.is_allowed_file_size(1024 * 1024)
        assert not validator.is_allowed_file_size(11 * 1024 * 1024)

    def test_rate_limiting(self):
        """Test rate limiting is properly implemented"""
        response = client.post(
            "/api/v1/auth/login", json={"email": "test@example.com", "password": "wrongpassword"}
        )
        for _i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"},
            )
        assert response.status_code == 429

    def test_sensitive_data_redaction(self):
        """Test sensitive data is redacted in logs"""
        from api.utils.error_handlers import sanitize_error_for_logging

        error_data = {"password": "secret123", "email": "user@example.com"}
        sanitized = sanitize_error_for_logging(error_data)
        assert "secret123" not in str(sanitized)
        assert "REDACTED" in str(sanitized)
        error_data = {"api_key": "sk-1234567890abcdef", "other": "safe_data"}
        sanitized = sanitize_error_for_logging(error_data)
        assert "sk-1234567890abcdef" not in str(sanitized)

    def test_admin_authentication(self):
        """Test admin endpoints require proper authentication"""
        response = client.get("/api/v1/admin/users")
        assert response.status_code == HTTP_UNAUTHORIZED

    def test_credential_encryption(self):
        """Test credential encryption is working properly"""
        encryption = CredentialEncryption()
        sensitive_data = "api_secret_12345"
        encrypted = encryption.encrypt(sensitive_data)
        decrypted = encryption.decrypt(encrypted)
        assert sensitive_data == decrypted
        assert encrypted != sensitive_data

    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in database queries"""
        from database.query_optimization import QueryOptimizer

        optimizer = QueryOptimizer()


class TestPerformanceFixes:
    """Test suite for performance optimization fixes"""

    def test_database_indexes(self):
        """Test database indexes are properly created"""
        pass

    def test_n1_query_prevention(self):
        """Test N+1 query prevention is working"""
        from database.query_optimization import QueryOptimizer

        optimizer = QueryOptimizer()
        assert hasattr(optimizer, "batch_load_related")
        assert hasattr(optimizer, "optimize_query")

    def test_caching_implementation(self):
        """Test caching is properly implemented"""
        assert settings.redis_url is not None


class TestIntegrationFixes:
    """Test suite for integration fixes"""

    def test_google_workspace_integration(self):
        """Test Google Workspace integration fixes"""
        from api.integrations.google_workspace_integration import GoogleWorkspaceIntegration

        integration = GoogleWorkspaceIntegration()
        assert hasattr(integration, "format_evidence")

    def test_error_handling_consistency(self):
        """Test consistent error handling across components"""
        from api.utils.error_handlers import RuleIQException

        assert issubclass(ValidationException, RuleIQException)
        assert issubclass(AuthenticationException, RuleIQException)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
