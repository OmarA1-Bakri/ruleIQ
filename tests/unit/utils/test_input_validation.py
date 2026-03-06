"""
Unit tests for utils/input_validation.py — FieldValidator, WhitelistValidator,
SecurityValidator, and convenience functions.

No external dependencies — pure validation logic.
"""

import os
import pytest
from uuid import UUID, uuid4

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from utils.input_validation import (
    ValidationError,
    FieldType,
    FieldValidator,
    WhitelistValidator,
    SecurityValidator,
    validate_evidence_update,
    validate_business_profile_update,
    validate_user_update,
)


# ---------------------------------------------------------------------------
# FieldType enum
# ---------------------------------------------------------------------------

class TestFieldType:
    """Tests for FieldType enum values."""

    def test_all_types_exist(self):
        assert FieldType.STRING.value == "string"
        assert FieldType.INTEGER.value == "integer"
        assert FieldType.FLOAT.value == "float"
        assert FieldType.BOOLEAN.value == "boolean"
        assert FieldType.UUID.value == "uuid"
        assert FieldType.EMAIL.value == "email"
        assert FieldType.URL.value == "url"
        assert FieldType.DATETIME.value == "datetime"
        assert FieldType.ENUM.value == "enum"
        assert FieldType.LIST.value == "list"
        assert FieldType.DICT.value == "dict"


# ---------------------------------------------------------------------------
# FieldValidator — string
# ---------------------------------------------------------------------------

class TestValidateString:
    """Tests for FieldValidator.validate_string()."""

    def test_valid_string(self):
        result = FieldValidator.validate_string("hello world")
        assert result == "hello world"

    def test_strips_whitespace(self):
        result = FieldValidator.validate_string("  hello  ")
        assert result == "hello"

    def test_none_with_allow_empty(self):
        result = FieldValidator.validate_string(None, allow_empty=True)
        assert result == ""

    def test_none_without_allow_empty(self):
        with pytest.raises(ValidationError):
            FieldValidator.validate_string(None, allow_empty=False)

    def test_empty_string_not_allowed(self):
        with pytest.raises(ValidationError):
            FieldValidator.validate_string("", allow_empty=False)

    def test_too_short(self):
        with pytest.raises(ValidationError, match="at least"):
            FieldValidator.validate_string("ab", min_length=5)

    def test_too_long(self):
        with pytest.raises(ValidationError, match="at most"):
            FieldValidator.validate_string("a" * 101, max_length=100)

    def test_converts_non_string(self):
        result = FieldValidator.validate_string(123)
        assert result == "123"

    def test_invalid_characters(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            FieldValidator.validate_string("<script>alert('xss')</script>")


# ---------------------------------------------------------------------------
# FieldValidator — integer
# ---------------------------------------------------------------------------

class TestValidateInteger:
    """Tests for FieldValidator.validate_integer()."""

    def test_valid_int(self):
        assert FieldValidator.validate_integer(42) == 42

    def test_string_to_int(self):
        assert FieldValidator.validate_integer("42") == 42

    def test_invalid_value(self):
        with pytest.raises(ValidationError, match="integer"):
            FieldValidator.validate_integer("not_a_number")

    def test_min_value(self):
        with pytest.raises(ValidationError, match="at least"):
            FieldValidator.validate_integer(3, min_value=5)

    def test_max_value(self):
        with pytest.raises(ValidationError, match="at most"):
            FieldValidator.validate_integer(100, max_value=50)


# ---------------------------------------------------------------------------
# FieldValidator — float
# ---------------------------------------------------------------------------

class TestValidateFloat:
    """Tests for FieldValidator.validate_float()."""

    def test_valid_float(self):
        assert FieldValidator.validate_float(3.14) == 3.14

    def test_int_to_float(self):
        assert FieldValidator.validate_float(5) == 5.0

    def test_string_to_float(self):
        assert FieldValidator.validate_float("3.14") == 3.14

    def test_invalid_value(self):
        with pytest.raises(ValidationError, match="number"):
            FieldValidator.validate_float("not_a_number")

    def test_min_value(self):
        with pytest.raises(ValidationError):
            FieldValidator.validate_float(1.0, min_value=5.0)

    def test_max_value(self):
        with pytest.raises(ValidationError):
            FieldValidator.validate_float(100.0, max_value=50.0)


# ---------------------------------------------------------------------------
# FieldValidator — boolean
# ---------------------------------------------------------------------------

class TestValidateBoolean:
    """Tests for FieldValidator.validate_boolean()."""

    def test_true(self):
        assert FieldValidator.validate_boolean(True) is True

    def test_false(self):
        assert FieldValidator.validate_boolean(False) is False

    def test_string_true(self):
        for val in ["true", "1", "yes", "on"]:
            assert FieldValidator.validate_boolean(val) is True

    def test_string_false(self):
        for val in ["false", "0", "no", "off"]:
            assert FieldValidator.validate_boolean(val) is False

    def test_int_truthy(self):
        assert FieldValidator.validate_boolean(1) is True
        assert FieldValidator.validate_boolean(0) is False

    def test_invalid(self):
        with pytest.raises(ValidationError, match="boolean"):
            FieldValidator.validate_boolean("maybe")


# ---------------------------------------------------------------------------
# FieldValidator — UUID
# ---------------------------------------------------------------------------

class TestValidateUUID:
    """Tests for FieldValidator.validate_uuid()."""

    def test_valid_uuid_string(self):
        uid = str(uuid4())
        result = FieldValidator.validate_uuid(uid)
        assert isinstance(result, UUID)

    def test_uuid_object(self):
        uid = uuid4()
        result = FieldValidator.validate_uuid(uid)
        assert result == uid

    def test_invalid_uuid(self):
        with pytest.raises(ValidationError, match="UUID"):
            FieldValidator.validate_uuid("not-a-uuid")

    def test_non_string_non_uuid(self):
        with pytest.raises(ValidationError, match="UUID"):
            FieldValidator.validate_uuid(12345)


# ---------------------------------------------------------------------------
# FieldValidator — email
# ---------------------------------------------------------------------------

class TestValidateEmail:
    """Tests for FieldValidator.validate_email()."""

    def test_valid_email(self):
        result = FieldValidator.validate_email("user@example.com")
        assert result == "user@example.com"

    def test_email_lowercased(self):
        result = FieldValidator.validate_email("User@Example.COM")
        assert result == "user@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError, match="email"):
            FieldValidator.validate_email("not-an-email")

    def test_non_string(self):
        with pytest.raises(ValidationError):
            FieldValidator.validate_email(12345)


# ---------------------------------------------------------------------------
# FieldValidator — enum
# ---------------------------------------------------------------------------

class TestValidateEnum:
    """Tests for FieldValidator.validate_enum()."""

    def test_valid_value(self):
        assert FieldValidator.validate_enum("low", ["low", "medium", "high"]) == "low"

    def test_invalid_value(self):
        with pytest.raises(ValidationError, match="one of"):
            FieldValidator.validate_enum("extreme", ["low", "medium", "high"])


# ---------------------------------------------------------------------------
# FieldValidator — list
# ---------------------------------------------------------------------------

class TestValidateList:
    """Tests for FieldValidator.validate_list()."""

    def test_valid_list(self):
        result = FieldValidator.validate_list([1, 2, 3])
        assert result == [1, 2, 3]

    def test_non_list(self):
        with pytest.raises(ValidationError, match="list"):
            FieldValidator.validate_list("not a list")

    def test_too_many_items(self):
        with pytest.raises(ValidationError, match="more than"):
            FieldValidator.validate_list(list(range(200)), max_items=100)


# ---------------------------------------------------------------------------
# FieldValidator — dict
# ---------------------------------------------------------------------------

class TestValidateDict:
    """Tests for FieldValidator.validate_dict()."""

    def test_valid_dict(self):
        result = FieldValidator.validate_dict({"key": "value"})
        assert result == {"key": "value"}

    def test_non_dict(self):
        with pytest.raises(ValidationError, match="dictionary"):
            FieldValidator.validate_dict("not a dict")

    def test_too_many_keys(self):
        big_dict = {f"key{i}": i for i in range(60)}
        with pytest.raises(ValidationError, match="more than"):
            FieldValidator.validate_dict(big_dict, max_keys=50)


# ---------------------------------------------------------------------------
# WhitelistValidator
# ---------------------------------------------------------------------------

class TestWhitelistValidator:
    """Tests for WhitelistValidator."""

    def test_unknown_model_has_no_fields(self):
        wv = WhitelistValidator("NonExistentModel")
        assert wv.field_definitions == {}

    def test_evidence_item_fields_exist(self):
        wv = WhitelistValidator("EvidenceItem")
        assert "evidence_name" in wv.field_definitions
        assert "status" in wv.field_definitions

    def test_disallowed_field_raises(self):
        wv = WhitelistValidator("EvidenceItem")
        with pytest.raises(ValidationError, match="not allowed"):
            wv.validate_field("hacker_field", "value")

    def test_validate_update_data_rejects_non_dict(self):
        wv = WhitelistValidator("EvidenceItem")
        with pytest.raises(ValidationError, match="dictionary"):
            wv.validate_update_data("not a dict")

    def test_validate_update_data_too_many_fields(self):
        wv = WhitelistValidator("EvidenceItem")
        big_data = {f"field_{i}": "val" for i in range(25)}
        with pytest.raises(ValidationError, match="Too many"):
            wv.validate_update_data(big_data)

    def test_valid_evidence_update(self):
        wv = WhitelistValidator("EvidenceItem")
        result = wv.validate_update_data({"status": "pending"})
        assert result["status"] == "pending"


# ---------------------------------------------------------------------------
# SecurityValidator
# ---------------------------------------------------------------------------

class TestSecurityValidator:
    """Tests for SecurityValidator."""

    def test_clean_input(self):
        assert SecurityValidator.scan_for_dangerous_patterns("hello world") is False

    def test_detects_script_tag(self):
        assert SecurityValidator.scan_for_dangerous_patterns("<script>alert(1)</script>") is True

    def test_detects_javascript_protocol(self):
        assert SecurityValidator.scan_for_dangerous_patterns("javascript:void(0)") is True

    def test_detects_sql_injection(self):
        assert SecurityValidator.scan_for_dangerous_patterns("1; DROP TABLE users") is True

    def test_detects_path_traversal(self):
        assert SecurityValidator.scan_for_dangerous_patterns("../../etc/passwd") is True

    def test_detects_python_dunder(self):
        assert SecurityValidator.scan_for_dangerous_patterns("__import__('os')") is True

    def test_non_string_returns_false(self):
        assert SecurityValidator.scan_for_dangerous_patterns(12345) is False

    def test_validate_no_dangerous_content_clean(self):
        # Should not raise
        SecurityValidator.validate_no_dangerous_content({"name": "safe value"})

    def test_validate_no_dangerous_content_raises(self):
        with pytest.raises(ValidationError, match="dangerous"):
            SecurityValidator.validate_no_dangerous_content(
                {"name": "<script>alert(1)</script>"}
            )

    def test_validate_nested_dict(self):
        with pytest.raises(ValidationError, match="dangerous"):
            SecurityValidator.validate_no_dangerous_content(
                {"outer": {"inner": "javascript:void(0)"}}
            )

    def test_validate_nested_list(self):
        with pytest.raises(ValidationError, match="dangerous"):
            SecurityValidator.validate_no_dangerous_content(
                {"items": ["safe", "<script>bad</script>"]}
            )


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_validate_evidence_update_valid(self):
        result = validate_evidence_update({"status": "approved"})
        assert result["status"] == "approved"

    def test_validate_evidence_update_dangerous_content(self):
        with pytest.raises(ValidationError, match="dangerous"):
            validate_evidence_update({"evidence_name": "<script>xss</script>"})

    def test_validate_evidence_update_disallowed_field(self):
        with pytest.raises(ValidationError, match="not allowed"):
            validate_evidence_update({"hacker_field": "value"})

    def test_validate_business_profile_update_valid(self):
        result = validate_business_profile_update({"company_name": "Acme Corp"})
        assert result["company_name"] == "Acme Corp"

    def test_validate_user_update_valid(self):
        result = validate_user_update({"name": "John Smith"})
        assert result["name"] == "John Smith"

    def test_validate_user_update_email(self):
        result = validate_user_update({"email": "Test@Example.COM"})
        assert result["email"] == "test@example.com"
