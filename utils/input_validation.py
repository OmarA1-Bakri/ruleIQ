"""

Input validation utilities for secure API operations.
Prevents injection attacks and unauthorized field modifications.
"""

import re
from typing import Any, Dict, List, Optional
from uuid import UUID
from enum import Enum


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


class FieldType(Enum):
    """Supported field types for validation."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    UUID = "uuid"
    EMAIL = "email"
    URL = "url"
    DATETIME = "datetime"
    ENUM = "enum"
    LIST = "list"
    DICT = "dict"


class FieldValidator:
    """Validates individual field values."""

    # Common regex patterns
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    URL_PATTERN = re.compile(
        r"^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$",
    )
    UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )

    # Safe string pattern (alphanumeric, spaces, basic punctuation only)
    SAFE_STRING_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,!?()[\]{}:;"\']+$')

    @staticmethod
    def validate_string(
        value: Any,
        min_length: int = 0,
        max_length: int = 1000,
        allow_empty: bool = True,
        pattern: Optional[str] = None,
    ) -> str:
        """Validate string input with length and pattern checks."""
        if value is None:
            if allow_empty:
                return ""
            raise ValidationError("String value cannot be None")

        if not isinstance(value, str):
            value = str(value)

        # Strip whitespace
        value = value.strip()

        # Check empty string
        if not value and not allow_empty:
            raise ValidationError("String value cannot be empty")

        # Check length
        if len(value) < min_length:
            raise ValidationError(
                f"String must be at least {min_length} characters long",
            )
        if len(value) > max_length:
            raise ValidationError(
                f"String must be at most {max_length} characters long",
            )

        # Check for potentially dangerous characters
        if not FieldValidator.SAFE_STRING_PATTERN.match(value):
            raise ValidationError("String contains invalid characters")

        # Custom pattern validation
        if pattern and not re.match(pattern, value):
            raise ValidationError("String does not match required pattern")

        return value

    @staticmethod
    def validate_integer(
        value: Any, min_value: Optional[int] = None, max_value: Optional[int] = None
    ) -> int:
        """Validate integer input with range checks."""
        try:
            if isinstance(value, str):
                value = int(value)
            elif not isinstance(value, int):
                raise ValueError("Not an integer")
        except (ValueError, TypeError):
            raise ValidationError("Value must be a valid integer")

        if min_value is not None and value < min_value:
            raise ValidationError(f"Integer must be at least {min_value}")
        if max_value is not None and value > max_value:
            raise ValidationError(f"Integer must be at most {max_value}")

        return value

    @staticmethod
    def validate_float(
        value: Any, min_value: Optional[float] = None, max_value: Optional[float] = None
    ) -> float:
        """Validate float input with range checks."""
        try:
            if isinstance(value, str):
                value = float(value)
            elif not isinstance(value, (int, float)):
                raise ValueError("Not a number")
            value = float(value)
        except (ValueError, TypeError):
            raise ValidationError("Value must be a valid number")

        if min_value is not None and value < min_value:
            raise ValidationError(f"Number must be at least {min_value}")
        if max_value is not None and value > max_value:
            raise ValidationError(f"Number must be at most {max_value}")

        return value

    @staticmethod
    def validate_boolean(value: Any) -> bool:
        """Validate boolean input."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in ("true", "1", "yes", "on"):
                return True
            elif value.lower() in ("false", "0", "no", "off"):
                return False
        elif isinstance(value, int):
            return bool(value)

        raise ValidationError("Value must be a valid boolean")

    @staticmethod
    def validate_uuid(value: Any) -> UUID:
        """Validate UUID input."""
        if isinstance(value, UUID):
            return value

        if isinstance(value, str):
            if not FieldValidator.UUID_PATTERN.match(value):
                raise ValidationError("Invalid UUID format")
            try:
                return UUID(value)
            except ValueError:
                raise ValidationError("Invalid UUID value")

        raise ValidationError("Value must be a valid UUID")

    @staticmethod
    def validate_email(value: Any) -> str:
        """Validate email address."""
        if not isinstance(value, str):
            raise ValidationError("Email must be a string")

        value = value.strip().lower()
        if not FieldValidator.EMAIL_PATTERN.match(value):
            raise ValidationError("Invalid email format")

        return value

    @staticmethod
    def validate_url(value: Any) -> str:
        """Validate URL."""
        if not isinstance(value, str):
            raise ValidationError("URL must be a string")

        value = value.strip()
        if not FieldValidator.URL_PATTERN.match(value):
            raise ValidationError("Invalid URL format")

        return value

    @staticmethod
    def validate_enum(value: Any, allowed_values: List[str]) -> str:
        """Validate enum value against allowed list."""
        if not isinstance(value, str):
            value = str(value)

        if value not in allowed_values:
            raise ValidationError(f"Value must be one of: {', '.join(allowed_values)}")

        return value

    @staticmethod
    def validate_list(
        value: Any, max_items: int = 100, item_validator: Optional[callable] = None
    ) -> List[Any]:
        """Validate list input."""
        if not isinstance(value, list):
            raise ValidationError("Value must be a list")

        if len(value) > max_items:
            raise ValidationError(f"List cannot have more than {max_items} items")

        if item_validator:
            validated_items = []
            for i, item in enumerate(value):
                try:
                    validated_items.append(item_validator(item))
                except ValidationError as e:
                    raise ValidationError(f"Item {i}: {str(e)}")
            return validated_items

        return value

    @staticmethod
    def validate_dict(value: Any, max_keys: int = 50) -> Dict[str, Any]:
        """Validate dictionary input."""
        if not isinstance(value, dict):
            raise ValidationError("Value must be a dictionary")

        if len(value) > max_keys:
            raise ValidationError(f"Dictionary cannot have more than {max_keys} keys")

        # Validate keys are safe strings
        validated_dict = {}
        for key, val in value.items():
            try:
                safe_key = FieldValidator.validate_string(key, max_length=100)
                validated_dict[safe_key] = val
            except ValidationError as e:
                raise ValidationError(f"Dictionary key '{key}': {str(e)}")

        return validated_dict


class WhitelistValidator:
    """Validates input against predefined whitelists for secure field updates."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.field_definitions = self._get_field_definitions()

    def _get_field_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get field definitions for the model."""
        definitions = {
            "EvidenceItem": {
                "evidence_name": {
                    "type": FieldType.STRING,
                    "max_length": 200,
                    "min_length": 1,
                    "required": False,
                },
                "title": {  # Alias for evidence_name for API compatibility
                    "type": FieldType.STRING,
                    "max_length": 200,
                    "min_length": 1,
                    "required": False,
                },
                "description": {
                    "type": FieldType.STRING,
                    "max_length": 1000,
                    "min_length": 0,
                    "required": False,
                    "allow_empty": True,
                },
                "evidence_type": {
                    "type": FieldType.ENUM,
                    "allowed_values": [
                        "document",
                        "log",
                        "screenshot",
                        "certificate",
                        "policy",
                        "other",
                    ],
                    "required": False,
                },
                "status": {
                    "type": FieldType.ENUM,
                    "allowed_values": [
                        "pending",
                        "collected",
                        "in_review",
                        "approved",
                        "rejected",
                        "pending_review",
                        "reviewed",
                        "expired",
                        "not_started",
                        "in_progress",
                    ],
                    "required": False,
                },
                "tags": {
                    "type": FieldType.LIST,
                    "required": False,
                    "allow_empty": True,
                },
                "notes": {  # Alias for collection_notes
                    "type": FieldType.STRING,
                    "max_length": 2000,
                    "required": False,
                    "allow_empty": True,
                },
                "collection_notes": {
                    "type": FieldType.STRING,
                    "max_length": 2000,
                    "required": False,
                    "allow_empty": True,
                },
                "review_notes": {
                    "type": FieldType.STRING,
                    "max_length": 2000,
                    "required": False,
                    "allow_empty": True,
                },
                "control_reference": {
                    "type": FieldType.STRING,
                    "max_length": 100,
                    "min_length": 1,
                    "required": False,
                },
                "file_type": {
                    "type": FieldType.STRING,
                    "max_length": 20,
                    "min_length": 0,
                    "required": False,
                    "allow_empty": True,
                },
                "automation_source": {
                    "type": FieldType.STRING,
                    "max_length": 100,
                    "min_length": 0,
                    "required": False,
                    "allow_empty": True,
                },
            },
            "BusinessProfile": {
                "company_name": {
                    "type": FieldType.STRING,
                    "max_length": 200,
                    "min_length": 1,
                    "required": False,
                },
                "industry": {
                    "type": FieldType.STRING,
                    "max_length": 100,
                    "min_length": 1,
                    "required": False,
                },
                "employee_count": {
                    "type": FieldType.INTEGER,
                    "min_value": 1,
                    "max_value": 1000000,
                    "required": False,
                },
                "annual_revenue": {
                    "type": FieldType.STRING,
                    "max_length": 50,
                    "min_length": 0,
                    "required": False,
                    "allow_empty": True,
                },
                "country": {
                    "type": FieldType.STRING,
                    "max_length": 100,
                    "min_length": 2,
                    "required": False,
                },
                "data_sensitivity": {
                    "type": FieldType.ENUM,
                    "allowed_values": ["Low", "Moderate", "High", "Confidential"],
                    "required": False,
                },
                # Business characteristics
                "handles_personal_data": {"type": FieldType.BOOLEAN, "required": False},
                "processes_payments": {"type": FieldType.BOOLEAN, "required": False},
                "stores_health_data": {"type": FieldType.BOOLEAN, "required": False},
                "provides_financial_services": {
                    "type": FieldType.BOOLEAN,
                    "required": False,
                },
                "operates_critical_infrastructure": {
                    "type": FieldType.BOOLEAN,
                    "required": False,
                },
                "has_international_operations": {
                    "type": FieldType.BOOLEAN,
                    "required": False,
                },
                # Technology stack
                "cloud_providers": {
                    "type": FieldType.LIST,
                    "max_items": 20,
                    "required": False,
                },
                "saas_tools": {
                    "type": FieldType.LIST,
                    "max_items": 50,
                    "required": False,
                },
                "development_tools": {
                    "type": FieldType.LIST,
                    "max_items": 30,
                    "required": False,
                },
                # Current compliance state
                "existing_frameworks": {
                    "type": FieldType.LIST,
                    "max_items": 20,
                    "required": False,
                },
                "planned_frameworks": {
                    "type": FieldType.LIST,
                    "max_items": 20,
                    "required": False,
                },
                "compliance_budget": {
                    "type": FieldType.STRING,
                    "max_length": 50,
                    "min_length": 0,
                    "required": False,
                    "allow_empty": True,
                },
                "compliance_timeline": {
                    "type": FieldType.STRING,
                    "max_length": 50,
                    "min_length": 0,
                    "required": False,
                    "allow_empty": True,
                },
                # Assessment status
                "assessment_completed": {"type": FieldType.BOOLEAN, "required": False},
                "assessment_data": {
                    "type": FieldType.DICT,
                    "max_keys": 100,
                    "required": False,
                },
            },
            "User": {
                "name": {
                    "type": FieldType.STRING,
                    "max_length": 100,
                    "min_length": 1,
                    "required": False,
                },
                "email": {"type": FieldType.EMAIL, "required": False},
            },
        }

        return definitions.get(self.model_name, {})

    def validate_field(self, field_name: str, value: Any) -> Any:
        """Validate a single field value."""
        if field_name not in self.field_definitions:
            raise ValidationError(
                f"Field '{field_name}' is not allowed for updates on {self.model_name}",
            )

        field_def = self.field_definitions[field_name]
        field_type = field_def["type"]

        try:
            if field_type == FieldType.STRING:
                return FieldValidator.validate_string(
                    value,
                    min_length=field_def.get("min_length", 0),
                    max_length=field_def.get("max_length", 1000),
                    allow_empty=field_def.get("allow_empty", False),
                    pattern=field_def.get("pattern"),
                )
            elif field_type == FieldType.INTEGER:
                return FieldValidator.validate_integer(
                    value,
                    min_value=field_def.get("min_value"),
                    max_value=field_def.get("max_value"),
                )
            elif field_type == FieldType.FLOAT:
                return FieldValidator.validate_float(
                    value,
                    min_value=field_def.get("min_value"),
                    max_value=field_def.get("max_value"),
                )
            elif field_type == FieldType.BOOLEAN:
                return FieldValidator.validate_boolean(value)
            elif field_type == FieldType.UUID:
                return FieldValidator.validate_uuid(value)
            elif field_type == FieldType.EMAIL:
                return FieldValidator.validate_email(value)
            elif field_type == FieldType.URL:
                return FieldValidator.validate_url(value)
            elif field_type == FieldType.ENUM:
                return FieldValidator.validate_enum(value, field_def["allowed_values"])
            elif field_type == FieldType.LIST:
                return FieldValidator.validate_list(
                    value,
                    max_items=field_def.get("max_items", 100),
                    item_validator=field_def.get("item_validator"),
                )
            elif field_type == FieldType.DICT:
                return FieldValidator.validate_dict(
                    value,
                    max_keys=field_def.get("max_keys", 50),
                )
            else:
                raise ValidationError(f"Unsupported field type: {field_type}")

        except ValidationError as e:
            raise ValidationError(f"Field '{field_name}': {str(e)}")

    def validate_update_data(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all fields in update data against whitelist."""
        if not isinstance(update_data, dict):
            raise ValidationError("Update data must be a dictionary")

        if len(update_data) > 20:  # Reasonable limit for number of fields
            raise ValidationError("Too many fields in update data")

        validated_data = {}
        for field_name, value in update_data.items():
            validated_value = self.validate_field(field_name, value)
            validated_data[field_name] = validated_value

        return validated_data


class SecurityValidator:
    """Additional security validations."""

    # Dangerous patterns that should never appear in input
    DANGEROUS_PATTERNS = [
        r"<script[^>]*>.*?</script>",  # XSS
        r"javascript:",  # XSS
        r"on\w+\s*=",  # Event handlers
        r"eval\s*\(",  # Code execution
        r"exec\s*\(",  # Code execution
        r"system\s*\(",  # System calls
        r"__.*__",  # Python private attributes
        r"\.\./",  # Path traversal
        r"\.\.//",  # Path traversal
        r"union\s+select",  # SQL injection
        r"drop\s+table",  # SQL injection
        r"delete\s+from",  # SQL injection
        r"insert\s+into",  # SQL injection
        r"update\s+.*\s+set",  # SQL injection,
    ]

    @staticmethod
    def scan_for_dangerous_patterns(value: str) -> bool:
        """Scan input for dangerous patterns."""
        if not isinstance(value, str):
            return False

        value_lower = value.lower()
        for pattern in SecurityValidator.DANGEROUS_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def validate_no_dangerous_content(data: Dict[str, Any]) -> None:
        """Validate that input data contains no dangerous patterns."""

        def check_value(val) -> None:
            if isinstance(val, str):
                if SecurityValidator.scan_for_dangerous_patterns(val):
                    raise ValidationError(
                        "Input contains potentially dangerous content",
                    )
            elif isinstance(val, dict):
                for v in val.values():
                    check_value(v)
            elif isinstance(val, list):
                for v in val:
                    check_value(v)

        for value in data.values():
            check_value(value)


# Convenience function for evidence service
def validate_evidence_update(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate evidence item update data."""
    # Security scan first
    SecurityValidator.validate_no_dangerous_content(update_data)

    # Whitelist validation
    validator = WhitelistValidator("EvidenceItem")
    return validator.validate_update_data(update_data)


# Convenience function for business profile service
def validate_business_profile_update(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate business profile update data."""
    # Security scan first
    SecurityValidator.validate_no_dangerous_content(update_data)

    # Whitelist validation
    validator = WhitelistValidator("BusinessProfile")
    return validator.validate_update_data(update_data)


# Convenience function for user service
def validate_user_update(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate user update data."""
    # Security scan first
    SecurityValidator.validate_no_dangerous_content(update_data)

    # Whitelist validation
    validator = WhitelistValidator("User")
    return validator.validate_update_data(update_data)
