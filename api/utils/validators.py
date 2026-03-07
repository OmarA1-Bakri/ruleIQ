from typing import Any
import re
import bleach

# Constants
DEFAULT_LIMIT = 100

EMAIL_REGEX = re.compile("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
SAFE_STRING_REGEX = re.compile("^[a-zA-Z0-9\\s\\-_.,!?]+$")
UUID_REGEX = re.compile("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class InputValidators:
    """Common input validation functions"""

    @staticmethod
    def sanitize_html(value: str) -> str:
        """Remove dangerous HTML tags"""
        allowed_tags = ["b", "i", "u", "em", "strong", "p", "br", "ul", "li", "ol"]
        return bleach.clean(value, tags=allowed_tags, strip=True)

    @staticmethod
    def validate_email(email: str) -> str:
        if not EMAIL_REGEX.match(email):
            raise ValueError("Invalid email format")
        return email.lower().strip()

    @staticmethod
    def validate_safe_string(value: str, max_length: int = 255) -> str:
        """Validate string contains only safe characters"""
        if len(value) > max_length:
            raise ValueError(f"String exceeds maximum length of {max_length}")
        cleaned = bleach.clean(value, tags=[], strip=True)
        return cleaned.strip()

    @staticmethod
    def validate_company_name(value: str) -> str:
        """Validate company name"""
        if not value or len(value.strip()) < 2:
            raise ValueError("Company name must be at least 2 characters")
        if len(value) > DEFAULT_LIMIT:
            raise ValueError("Company name must not exceed 100 characters")
        return InputValidators.validate_safe_string(value, 100)

    @staticmethod
    def validate_url(url: str) -> str:
        """Validate URL format"""
        url_regex = re.compile(
            "^https?://(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\\.)+[A-Z]{2,6}\\.?|localhost|\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})(?::\\d+)?(?:/?|[/?]\\S+)$",
            re.IGNORECASE,
        )
        if not url_regex.match(url):
            raise ValueError("Invalid URL format")
        return url

    @staticmethod
    def validate_employee_count(value: int) -> int:
        """Validate employee count"""
        if value < 1:
            raise ValueError("Employee count must be at least 1")
        if value > 1000000:
            raise ValueError("Employee count seems unrealistic")
        return value


def email_validator(cls, v) -> Any:
    return InputValidators.validate_email(v)


def safe_string_validator(max_length: int = 255) -> Any:

    def validator(cls, v) -> Any:
        return InputValidators.validate_safe_string(v, max_length)

    return validator


def company_name_validator(cls, v) -> Any:
    return InputValidators.validate_company_name(v)


def url_validator(cls, v) -> Any:
    return InputValidators.validate_url(v)
