"""
Unit tests for api/utils/input_validation.py — InputValidator class and
convenience functions.

No external dependencies — pure validation logic.
"""

import os
import pytest

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from api.utils.input_validation import (
    ValidationError,
    InputValidator,
    sanitize_input,
    validate_email,
    validate_uuid,
    validate_password,
)


# ---------------------------------------------------------------------------
# sanitize_string
# ---------------------------------------------------------------------------

class TestSanitizeString:
    """Tests for InputValidator.sanitize_string()."""

    def test_normal_string(self):
        result = InputValidator.sanitize_string("hello world")
        assert result == "hello world"

    def test_strips_whitespace(self):
        result = InputValidator.sanitize_string("  hello  ")
        assert result == "hello"

    def test_html_escapes(self):
        result = InputValidator.sanitize_string("<b>bold</b>")
        assert "<b>" not in result
        assert "&lt;b&gt;" in result

    def test_removes_null_bytes(self):
        result = InputValidator.sanitize_string("hello\x00world")
        assert "\x00" not in result

    def test_too_long(self):
        with pytest.raises(ValidationError, match="too long"):
            InputValidator.sanitize_string("a" * 2000, max_length=1000)

    def test_non_string_raises(self):
        with pytest.raises(ValidationError, match="string"):
            InputValidator.sanitize_string(12345)


# ---------------------------------------------------------------------------
# validate_email
# ---------------------------------------------------------------------------

class TestValidateEmail:
    """Tests for InputValidator.validate_email()."""

    def test_valid_email(self):
        result = InputValidator.validate_email("user@example.com")
        assert "user@example.com" in result

    def test_empty_email(self):
        with pytest.raises(ValidationError, match="required"):
            InputValidator.validate_email("")

    def test_invalid_format(self):
        with pytest.raises(ValidationError, match="format"):
            InputValidator.validate_email("not-an-email")


# ---------------------------------------------------------------------------
# validate_uuid
# ---------------------------------------------------------------------------

class TestValidateUUID:
    """Tests for InputValidator.validate_uuid()."""

    def test_valid_uuid(self):
        result = InputValidator.validate_uuid("550e8400-e29b-41d4-a716-446655440000")
        assert "550e8400" in result

    def test_empty_uuid(self):
        with pytest.raises(ValidationError, match="required"):
            InputValidator.validate_uuid("")

    def test_invalid_uuid(self):
        with pytest.raises(ValidationError, match="UUID"):
            InputValidator.validate_uuid("not-a-uuid")


# ---------------------------------------------------------------------------
# validate_url
# ---------------------------------------------------------------------------

class TestValidateURL:
    """Tests for InputValidator.validate_url()."""

    def test_valid_http_url(self):
        result = InputValidator.validate_url("https://example.com")
        assert result == "https://example.com"

    def test_empty_url(self):
        with pytest.raises(ValidationError, match="required"):
            InputValidator.validate_url("")

    def test_no_scheme(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_url("example.com")

    def test_allowed_schemes(self):
        with pytest.raises(ValidationError, match="scheme"):
            InputValidator.validate_url("ftp://example.com", allowed_schemes=["https"])


# ---------------------------------------------------------------------------
# validate_password
# ---------------------------------------------------------------------------

class TestValidatePassword:
    """Tests for InputValidator.validate_password()."""

    def test_valid_password(self):
        result = InputValidator.validate_password("StrongP@ss1")
        assert result == "StrongP@ss1"

    def test_empty_password(self):
        with pytest.raises(ValidationError, match="required"):
            InputValidator.validate_password("")

    def test_too_short(self):
        with pytest.raises(ValidationError, match="8 characters"):
            InputValidator.validate_password("Aa1!")

    def test_too_long(self):
        with pytest.raises(ValidationError, match="too long"):
            InputValidator.validate_password("A" * 200)

    def test_no_uppercase(self):
        with pytest.raises(ValidationError, match="uppercase"):
            InputValidator.validate_password("strongp@ss1")

    def test_no_lowercase(self):
        with pytest.raises(ValidationError, match="lowercase"):
            InputValidator.validate_password("STRONGP@SS1")

    def test_no_digit(self):
        with pytest.raises(ValidationError, match="digit"):
            InputValidator.validate_password("StrongP@ss!")

    def test_no_special(self):
        with pytest.raises(ValidationError, match="special"):
            InputValidator.validate_password("StrongPass1")


# ---------------------------------------------------------------------------
# SQL injection detection
# ---------------------------------------------------------------------------

class TestSQLInjection:
    """Tests for InputValidator.validate_no_sql_injection()."""

    def test_clean_input(self):
        result = InputValidator.validate_no_sql_injection("hello world")
        assert result == "hello world"

    def test_detects_union_select(self):
        with pytest.raises(ValidationError, match="SQL"):
            InputValidator.validate_no_sql_injection("1 UNION SELECT * FROM users")

    def test_detects_drop_table(self):
        with pytest.raises(ValidationError, match="SQL"):
            InputValidator.validate_no_sql_injection("1; DROP TABLE users")

    def test_empty_returns_empty(self):
        result = InputValidator.validate_no_sql_injection("")
        assert result == ""


# ---------------------------------------------------------------------------
# XSS detection
# ---------------------------------------------------------------------------

class TestXSSDetection:
    """Tests for InputValidator.validate_no_xss()."""

    def test_clean_input(self):
        result = InputValidator.validate_no_xss("hello world")
        assert result == "hello world"

    def test_detects_script_tag(self):
        with pytest.raises(ValidationError, match="HTML"):
            InputValidator.validate_no_xss("<script>alert(1)</script>")

    def test_detects_javascript_protocol(self):
        with pytest.raises(ValidationError, match="HTML"):
            InputValidator.validate_no_xss("javascript:void(0)")

    def test_detects_event_handler(self):
        with pytest.raises(ValidationError, match="HTML"):
            InputValidator.validate_no_xss('onclick=alert(1)')

    def test_empty_returns_empty(self):
        result = InputValidator.validate_no_xss("")
        assert result == ""


# ---------------------------------------------------------------------------
# validate_json
# ---------------------------------------------------------------------------

class TestValidateJSON:
    """Tests for InputValidator.validate_json()."""

    def test_valid_json(self):
        result = InputValidator.validate_json({"key": "value"})
        assert result == {"key": "value"}

    def test_non_dict_raises(self):
        with pytest.raises(ValidationError, match="JSON"):
            InputValidator.validate_json("not a dict")

    def test_nested_sanitization(self):
        result = InputValidator.validate_json({"nested": {"key": "  value  "}})
        assert result["nested"]["key"] == "value"


# ---------------------------------------------------------------------------
# validate_file_name
# ---------------------------------------------------------------------------

class TestValidateFileName:
    """Tests for InputValidator.validate_file_name()."""

    def test_valid_filename(self):
        result = InputValidator.validate_file_name("report.pdf")
        assert result == "report.pdf"

    def test_empty_filename(self):
        with pytest.raises(ValidationError, match="required"):
            InputValidator.validate_file_name("")

    def test_path_traversal_stripped(self):
        result = InputValidator.validate_file_name("../../etc/passwd")
        # Path traversal chars are removed
        assert ".." not in result
        assert "/" not in result

    def test_too_long(self):
        with pytest.raises(ValidationError, match="too long"):
            InputValidator.validate_file_name("a" * 300)


# ---------------------------------------------------------------------------
# validate_integer / validate_float
# ---------------------------------------------------------------------------

class TestValidateInteger:
    """Tests for InputValidator.validate_integer()."""

    def test_valid(self):
        assert InputValidator.validate_integer(42) == 42

    def test_string_conversion(self):
        assert InputValidator.validate_integer("42") == 42

    def test_invalid(self):
        with pytest.raises(ValidationError, match="integer"):
            InputValidator.validate_integer("abc")

    def test_min_value(self):
        with pytest.raises(ValidationError, match="at least"):
            InputValidator.validate_integer(1, min_value=5)

    def test_max_value(self):
        with pytest.raises(ValidationError, match="at most"):
            InputValidator.validate_integer(100, max_value=50)


class TestValidateFloat:
    """Tests for InputValidator.validate_float()."""

    def test_valid(self):
        assert InputValidator.validate_float(3.14) == 3.14

    def test_invalid(self):
        with pytest.raises(ValidationError, match="number"):
            InputValidator.validate_float("abc")


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_sanitize_input(self):
        result = sanitize_input("  hello  ")
        assert result == "hello"

    def test_validate_email_convenience(self):
        result = validate_email("user@example.com")
        assert "user@example.com" in result

    def test_validate_uuid_convenience(self):
        result = validate_uuid("550e8400-e29b-41d4-a716-446655440000")
        assert "550e8400" in result

    def test_validate_password_convenience(self):
        result = validate_password("StrongP@ss1")
        assert result == "StrongP@ss1"
