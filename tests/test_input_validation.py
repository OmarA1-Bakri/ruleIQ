"""
Tests for input validation utilities
"""

import pytest
from uuid import uuid4

from utils.input_validation import (
    FieldValidator,
    WhitelistValidator,
    SecurityValidator,
    ValidationError,
    validate_evidence_update,
    validate_business_profile_update,
)


class TestFieldValidator:
    """Test individual field validators."""

    def test_validate_string_success(self):
        """Test successful string validation."""
        result = FieldValidator.validate_string(
            "Hello World",
            min_length=1,
            max_length=20,
        )
        assert result == "Hello World"

    def test_validate_string_length_error(self):
        """Test string length validation error."""
        with pytest.raises(ValidationError, match="must be at least"):
            FieldValidator.validate_string("Hi", min_length=5)

        with pytest.raises(ValidationError, match="must be at most"):
            FieldValidator.validate_string("This is way too long" * 10, max_length=20)

    def test_validate_string_dangerous_chars(self):
        """Test rejection of dangerous characters."""
        with pytest.raises(ValidationError, match="invalid characters"):
            FieldValidator.validate_string("<script>alert('xss')</script>")

    def test_validate_integer_success(self):
        """Test successful integer validation."""
        assert FieldValidator.validate_integer("42") == 42
        assert FieldValidator.validate_integer(42) == 42

    def test_validate_integer_range_error(self):
        """Test integer range validation."""
        with pytest.raises(ValidationError, match="must be at least"):
            FieldValidator.validate_integer(5, min_value=10)

    def test_validate_boolean_success(self):
        """Test boolean validation."""
        assert FieldValidator.validate_boolean(True) is True
        assert FieldValidator.validate_boolean("true") is True
        assert FieldValidator.validate_boolean("false") is False
        assert FieldValidator.validate_boolean(1) is True

    def test_validate_uuid_success(self):
        """Test UUID validation."""
        test_uuid = uuid4()
        assert FieldValidator.validate_uuid(str(test_uuid)) == test_uuid
        assert FieldValidator.validate_uuid(test_uuid) == test_uuid

    def test_validate_uuid_error(self):
        """Test UUID validation error."""
        with pytest.raises(ValidationError, match="Invalid UUID"):
            FieldValidator.validate_uuid("not-a-uuid")

    def test_validate_email_success(self):
        """Test email validation."""
        result = FieldValidator.validate_email("user@example.com")
        assert result == "user@example.com"

    def test_validate_email_error(self):
        """Test email validation error."""
        with pytest.raises(ValidationError, match="Invalid email"):
            FieldValidator.validate_email("not-an-email")

    def test_validate_enum_success(self):
        """Test enum validation."""
        result = FieldValidator.validate_enum(
            "pending",
            ["pending", "approved", "rejected"],
        )
        assert result == "pending"

    def test_validate_enum_error(self):
        """Test enum validation error."""
        with pytest.raises(ValidationError, match="must be one of"):
            FieldValidator.validate_enum("invalid", ["pending", "approved"])


class TestSecurityValidator:
    """Test security pattern detection."""

    def test_scan_for_dangerous_patterns(self):
        """Test detection of dangerous patterns."""
        dangerous_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "onclick=alert('xss')",
            "eval(malicious_code)",
            "DROP TABLE users",
            "UNION SELECT * FROM passwords",
            "../../../etc/passwd",
            "__import__('os').system('rm -rf /')",
        ]

        for dangerous_input in dangerous_inputs:
            assert SecurityValidator.scan_for_dangerous_patterns(dangerous_input), (
                f"Failed to detect dangerous pattern: {dangerous_input}"
            )

    def test_safe_patterns(self):
        """Test that safe patterns are not flagged."""
        safe_inputs = [
            "This is a normal description",
            "Evidence for ISO 27001 compliance",
            "Document contains policy information",
            "Version 1.2.3 updated on 2024-01-01",
        ]

        for safe_input in safe_inputs:
            assert not SecurityValidator.scan_for_dangerous_patterns(safe_input), (
                f"Incorrectly flagged safe input: {safe_input}"
            )

    def test_validate_no_dangerous_content(self):
        """Test comprehensive dangerous content validation."""
        safe_data = {
            "title": "Evidence Document",
            "description": "This is a safe description",
            "status": "pending",
        }

        # Should not raise exception
        SecurityValidator.validate_no_dangerous_content(safe_data)

        dangerous_data = {
            "title": "Evidence Document",
            "description": "<script>alert('xss')</script>",
            "status": "pending",
        }

        with pytest.raises(ValidationError, match="dangerous content"):
            SecurityValidator.validate_no_dangerous_content(dangerous_data)


class TestWhitelistValidator:
    """Test whitelist-based validation."""

    def test_evidence_item_validation_success(self):
        """Test successful evidence item validation."""
        validator = WhitelistValidator("EvidenceItem")

        valid_data = {
            "evidence_name": "Test Evidence",
            "description": "This is a test description",
            "evidence_type": "document",
            "status": "pending",
        }

        result = validator.validate_update_data(valid_data)
        assert result["evidence_name"] == "Test Evidence"
        assert result["evidence_type"] == "document"

    def test_evidence_item_validation_invalid_field(self):
        """Test rejection of invalid fields."""
        validator = WhitelistValidator("EvidenceItem")

        invalid_data = {
            "evidence_name": "Test Evidence",
            "malicious_field": "should be rejected",
        }

        with pytest.raises(ValidationError, match="not allowed for updates"):
            validator.validate_update_data(invalid_data)

    def test_evidence_item_validation_invalid_enum(self):
        """Test rejection of invalid enum values."""
        validator = WhitelistValidator("EvidenceItem")

        invalid_data = {"evidence_type": "malicious_type"}

        with pytest.raises(ValidationError, match="must be one of"):
            validator.validate_update_data(invalid_data)

    def test_business_profile_validation_success(self):
        """Test successful business profile validation."""
        validator = WhitelistValidator("BusinessProfile")

        valid_data = {
            "company_name": "Test Company",
            "industry": "Technology",
            "employee_count": 50,
            "data_sensitivity": "Medium",
        }

        result = validator.validate_update_data(valid_data)
        assert result["company_name"] == "Test Company"
        assert result["employee_count"] == 50

    def test_business_profile_validation_invalid_field(self):
        """Test rejection of invalid business profile fields."""
        validator = WhitelistValidator("BusinessProfile")

        invalid_data = {
            "company_name": "Test Company",
            "secret_admin_field": "should be rejected",
        }

        with pytest.raises(ValidationError, match="not allowed for updates"):
            validator.validate_update_data(invalid_data)


class TestConvenienceFunctions:
    """Test convenience validation functions."""

    def test_validate_evidence_update_success(self):
        """Test successful evidence update validation."""
        valid_data = {
            "evidence_name": "Test Evidence",
            "description": "Safe description",
            "status": "approved",
        }

        result = validate_evidence_update(valid_data)
        assert result["evidence_name"] == "Test Evidence"

    def test_validate_evidence_update_security_error(self):
        """Test evidence update with security violation."""
        dangerous_data = {
            "evidence_name": "Test Evidence",
            "description": "<script>alert('xss')</script>",
        }

        with pytest.raises(ValidationError, match="dangerous content"):
            validate_evidence_update(dangerous_data)

    def test_validate_evidence_update_whitelist_error(self):
        """Test evidence update with whitelist violation."""
        invalid_data = {
            "evidence_name": "Test Evidence",
            "admin_only_field": "should be rejected",
        }

        with pytest.raises(ValidationError, match="not allowed"):
            validate_evidence_update(invalid_data)

    def test_validate_business_profile_update_success(self):
        """Test successful business profile update validation."""
        valid_data = {"company_name": "Test Company", "employee_count": 100}

        result = validate_business_profile_update(valid_data)
        assert result["company_name"] == "Test Company"

    def test_validate_business_profile_update_error(self):
        """Test business profile update with validation error."""
        invalid_data = {
            "company_name": "Test Company",
            "employee_count": "not a number",
        }

        with pytest.raises(ValidationError):
            validate_business_profile_update(invalid_data)


class TestAttackScenarios:
    """Test against real attack scenarios."""

    def test_sql_injection_attempt(self):
        """Test SQL injection prevention."""
        attack_data = {
            "evidence_name": "'; DROP TABLE evidence_items; --",
            "description": "UNION SELECT * FROM users WHERE admin=true",
        }

        with pytest.raises(ValidationError, match="dangerous content"):
            validate_evidence_update(attack_data)

    def test_xss_injection_attempt(self):
        """Test XSS injection prevention."""
        attack_data = {
            "evidence_name": "Test <script>alert('XSS')</script>",
            "description": "javascript:alert('XSS')",
        }

        with pytest.raises(ValidationError, match="dangerous content"):
            validate_evidence_update(attack_data)

    def test_path_traversal_attempt(self):
        """Test path traversal prevention."""
        attack_data = {
            "evidence_name": "../../../etc/passwd",
            "description": "../../admin/secrets.txt",
        }

        with pytest.raises(ValidationError, match="dangerous content"):
            validate_evidence_update(attack_data)

    def test_code_execution_attempt(self):
        """Test code execution prevention."""
        attack_data = {
            "evidence_name": "__import__('os').system('rm -rf /')",
            "description": "eval(malicious_code())",
        }

        with pytest.raises(ValidationError, match="dangerous content"):
            validate_evidence_update(attack_data)

    def test_field_injection_attempt(self):
        """Test field injection prevention."""
        attack_data = {
            "evidence_name": "Normal Evidence",
            "is_admin": True,  # Try to inject admin field
            "user_role": "admin",  # Try to inject role field,
        }

        with pytest.raises(ValidationError, match="not allowed"):
            validate_evidence_update(attack_data)

    def test_massive_payload_attempt(self):
        """Test against massive payload attacks."""
        attack_data = {
            "evidence_name": "A" * 10000,  # Very long string
            "description": "B" * 50000,
        }

        with pytest.raises(ValidationError, match="must be at most"):
            validate_evidence_update(attack_data)

    def test_nested_object_attack(self):
        """Test against nested object injection."""
        attack_data = {
            "evidence_name": "Test Evidence",
            "metadata": {
                "admin": True,
                "permissions": ["admin", "read", "write"],
                "dangerous_code": "<script>alert('xss')</script>",
            },
        }

        # This should be rejected either for dangerous content or whitelist violation
        with pytest.raises(ValidationError):
            validate_evidence_update(attack_data)
