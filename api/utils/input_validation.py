"""

Comprehensive input validation and sanitization utilities for ruleIQ backend
"""

import re
import html
from typing import Any, Dict, List
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails"""

    pass


class InputValidator:
    """Comprehensive input validation and sanitization"""

    # Common patterns
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE,
    )
    URL_PATTERN = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        re.compile(
            r"\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b",
            re.IGNORECASE,
        ),
        re.compile(r"--|#|/\*|\*/", re.IGNORECASE),
        re.compile(r"\b(or|and)\b\s+\d+\s*=\s*\d+", re.IGNORECASE),
        re.compile(r'\'|"|`', re.IGNORECASE),
    ]

    # XSS patterns
    XSS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
        re.compile(r"<iframe[^>]*>.*?</iframe>", re.IGNORECASE),
        re.compile(r"<object[^>]*>.*?</object>", re.IGNORECASE),
    ]

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            raise ValidationError("Input must be a string")

        # Remove leading/trailing whitespace
        value = value.strip()

        # Check length
        if len(value) > max_length:
            raise ValidationError(f"String too long (max {max_length} characters)")

        # HTML escape
        value = html.escape(value)

        # Remove null bytes
        value = value.replace("\x00", "")

        return value

    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email address"""
        if not email:
            raise ValidationError("Email is required")

        email = InputValidator.sanitize_string(email, 254)

        if not InputValidator.EMAIL_PATTERN.match(email):
            raise ValidationError("Invalid email format")

        return email

    @staticmethod
    def validate_uuid(uuid_str: str) -> str:
        """Validate UUID format"""
        if not uuid_str:
            raise ValidationError("UUID is required")

        uuid_str = InputValidator.sanitize_string(uuid_str, 36)

        if not InputValidator.UUID_PATTERN.match(uuid_str):
            raise ValidationError("Invalid UUID format")

        return uuid_str

    @staticmethod
    def validate_url(url: str, allowed_schemes: List[str] = None) -> str:
        """Validate URL format and scheme"""
        if not url:
            raise ValidationError("URL is required")

        url = InputValidator.sanitize_string(url, 2048)

        try:
            parsed = urlparse(url)

            if not parsed.scheme:
                raise ValidationError("URL must have a scheme")

            if allowed_schemes and parsed.scheme not in allowed_schemes:
                raise ValidationError(f"URL scheme must be one of: {', '.join(allowed_schemes)}")

            if not parsed.netloc:
                raise ValidationError("URL must have a domain")

            return url

        except Exception as e:
            raise ValidationError(f"Invalid URL: {e}")

    @staticmethod
    def validate_password(password: str) -> str:
        """Validate password strength"""
        if not password:
            raise ValidationError("Password is required")

        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long")

        if len(password) > 128:
            raise ValidationError("Password too long")

        # Check for complexity
        if not re.search(r"[A-Z]", password):
            raise ValidationError("Password must contain at least one uppercase letter")

        if not re.search(r"[a-z]", password):
            raise ValidationError("Password must contain at least one lowercase letter")

        if not re.search(r"\d", password):
            raise ValidationError("Password must contain at least one digit")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError("Password must contain at least one special character")

        return password

    @staticmethod
    def validate_no_sql_injection(value: str) -> str:
        """Check for SQL injection attempts"""
        if not value:
            return value

        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                raise ValidationError("Input contains potentially dangerous SQL")

        return value

    @staticmethod
    def validate_no_xss(value: str) -> str:
        """Check for XSS attempts"""
        if not value:
            return value

        for pattern in InputValidator.XSS_PATTERNS:
            if pattern.search(value):
                raise ValidationError("Input contains potentially dangerous HTML/JavaScript")

        return value

    @staticmethod
    def validate_json(data: Any) -> Dict[str, Any]:
        """Validate JSON data"""
        if not isinstance(data, dict):
            raise ValidationError("Data must be a JSON object")

        # Recursively sanitize string values
        def sanitize_dict(obj: Any) -> Any:
            if isinstance(obj, str):
                return InputValidator.sanitize_string(obj)
            elif isinstance(obj, dict):
                return {k: sanitize_dict(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_dict(item) for item in obj]
            else:
                return obj

        return sanitize_dict(data)

    @staticmethod
    def validate_file_name(file_name: str) -> str:
        """Validate file name"""
        if not file_name:
            raise ValidationError("File name is required")

        # Remove path traversal attempts
        file_name = file_name.replace("..", "").replace("/", "").replace("\\", "")

        # Check for valid characters
        if not re.match(r"^[a-zA-Z0-9._-]+$", file_name):
            raise ValidationError("File name contains invalid characters")

        # Check length
        if len(file_name) > 255:
            raise ValidationError("File name too long")

        return file_name

    @staticmethod
    def validate_integer(value: Any, min_value: int = None, max_value: int = None) -> int:
        """Validate integer input"""
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise ValidationError("Input must be an integer")

        if min_value is not None and int_value < min_value:
            raise ValidationError(f"Value must be at least {min_value}")

        if max_value is not None and int_value > max_value:
            raise ValidationError(f"Value must be at most {max_value}")

        return int_value

    @staticmethod
    def validate_float(value: Any, min_value: float = None, max_value: float = None) -> float:
        """Validate float input"""
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            raise ValidationError("Input must be a number")

        if min_value is not None and float_value < min_value:
            raise ValidationError(f"Value must be at least {min_value}")

        if max_value is not None and float_value > max_value:
            raise ValidationError(f"Value must be at most {max_value}")

        return float_value


# Convenience functions
def sanitize_input(value: str, max_length: int = 1000) -> str:
    """Quick string sanitization"""
    return InputValidator.sanitize_string(value, max_length)


def validate_email(email: str) -> str:
    """Quick email validation"""
    return InputValidator.validate_email(email)


def validate_uuid(uuid_str: str) -> str:
    """Quick UUID validation"""
    return InputValidator.validate_uuid(uuid_str)


def validate_password(password: str) -> str:
    """Quick password validation"""
    return InputValidator.validate_password(password)
