"""
Centralized security validation module for the RuleIQ API.

This module consolidates and enhances existing validation utilities
to provide comprehensive security validation for all API endpoints.
"""

import re
import json
from typing import Any, Dict, List
from pathlib import Path
from fastapi import HTTPException, Request, UploadFile, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import ValidationError

# Import existing validators
from utils.input_validation import validate_evidence_update
from api.utils.input_validation import sanitize_input, InputValidator
import contextlib

# Enhanced dangerous pattern detection - categorized for contextual use
DANGEROUS_PATTERNS_SQL = [
    # SQL Injection patterns - more specific to avoid false positives
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC|EXECUTE)\b.*\b(FROM|INTO|WHERE|TABLE)\b)",
    r"(\bOR\b\s+\d+\s*=\s*\d+|\bAND\b\s+\d+\s*=\s*\d+)",  # More specific: OR 1=1 pattern
    r"('.*\bOR\b.*'='|'.*\bAND\b.*'=')",
    r"(--\s*$|\/\*.*\*\/)",  # SQL comments at end of line or multiline
]

DANGEROUS_PATTERNS_NOSQL = [
    # NoSQL Injection patterns
    r"(\$ne|\$gt|\$lt|\$gte|\$lte|\$in|\$nin|\$exists|\$regex)",
    r"(\{.*\$where.*:.*\})",
]

DANGEROUS_PATTERNS_XSS = [
    # XSS patterns
    r"(<script[^>]*>.*?<\/script>)",
    r"(javascript:|onerror=|onclick=|onload=|onmouseover=)",
    r"(<iframe|<embed|<object|<applet)",
    r"(document\.cookie|window\.location|document\.write)",
]

DANGEROUS_PATTERNS_CMD = [
    # Command Injection patterns - combined with shell metacharacters
    r"(;\s*(cat|ls|wget|curl|bash|sh|cmd|powershell)\b)",
    r"(\|\s*(cat|ls|wget|curl|bash|sh|cmd|powershell)\b)",
    r"(&&\s*(cat|ls|wget|curl|bash|sh|cmd|powershell)\b)",
    r"(\$\(.*\)|\`.*\`)",  # Command substitution
]

DANGEROUS_PATTERNS_PATH = [
    # Path Traversal patterns
    r"(\.\.\/|\.\.\\|%2e%2e%2f|%252e%252e%252f)",
    r"(\/etc\/passwd|\/etc\/shadow|C:\\Windows\\System32)",
]

DANGEROUS_PATTERNS_XXE = [
    # XML/XXE Injection patterns
    r"(<!DOCTYPE[^>]*\[.*\]>)",
    r"(<!ENTITY[^>]*>)",
    r"(SYSTEM\s+[\"']file:)",
]

DANGEROUS_PATTERNS_TEMPLATE = [
    # Server-Side Template Injection - be careful with these
    r"(\{\{.*(__|\.|config|request|application).*\}\})",  # More specific Jinja2/Django
    r"(\{%.*import.*%\}|\{%.*include.*%\})",  # Template imports/includes
    r"(#set\(|#foreach\(|<#|FreeMarker)",
]

# Combined patterns for strict mode
DANGEROUS_PATTERNS = (
    DANGEROUS_PATTERNS_SQL +
    DANGEROUS_PATTERNS_NOSQL +
    DANGEROUS_PATTERNS_XSS +
    DANGEROUS_PATTERNS_CMD +
    DANGEROUS_PATTERNS_PATH +
    DANGEROUS_PATTERNS_XXE +
    DANGEROUS_PATTERNS_TEMPLATE
)

# Allowed MIME types for file uploads
ALLOWED_MIME_TYPES = {
    'application/pdf': ['.pdf'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/gif': ['.gif'],
    'text/plain': ['.txt'],
    'text/csv': ['.csv'],
    'application/vnd.ms-excel': ['.xls'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'application/msword': ['.doc'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
}

# Maximum file size (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


class SecurityValidator:
    """Enhanced security validation for API requests."""

    @staticmethod
    def validate_no_dangerous_content(content: str, field_name: str = "content", mode: str = "strict") -> str:
        """
        Validate that content doesn't contain dangerous patterns.

        Args:
            content: The content to validate
            field_name: Name of the field being validated
            mode: Validation mode - 'strict' (all patterns) or 'lenient' (reduced patterns)

        Returns:
            Sanitized content

        Raises:
            HTTPException: If dangerous patterns are detected
        """
        if not content:
            return content

        # Convert to string if needed
        content_str = str(content).lower()

        # Select pattern sets based on mode
        if mode == "lenient":
            # For lenient mode, only check critical patterns
            patterns_to_check = (
                DANGEROUS_PATTERNS_SQL +
                DANGEROUS_PATTERNS_PATH +
                DANGEROUS_PATTERNS_XXE
            )
        elif mode == "xss_only":
            # For UI-rendered fields
            patterns_to_check = DANGEROUS_PATTERNS_XSS
        else:  # strict mode
            patterns_to_check = DANGEROUS_PATTERNS

        # Check for dangerous patterns
        for pattern in patterns_to_check:
            if re.search(pattern, content_str, re.IGNORECASE | re.DOTALL):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {field_name}: contains potentially dangerous content"
                )

        # Sanitize and return
        return sanitize_input(content)

    @staticmethod
    def validate_json_payload(payload: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """
        Validate JSON payload for security threats.

        Args:
            payload: JSON payload to validate
            max_depth: Maximum nesting depth allowed

        Returns:
            Validated payload

        Raises:
            HTTPException: If payload contains security threats
        """
        def check_depth(obj: Any, current_depth: int = 0) -> None:
            if current_depth > max_depth:
                raise HTTPException(
                    status_code=400,
                    detail="JSON payload exceeds maximum nesting depth"
                )

            if isinstance(obj, dict):
                for key, value in obj.items():
                    # Validate keys
                    SecurityValidator.validate_no_dangerous_content(str(key), "JSON key")
                    check_depth(value, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)
            elif isinstance(obj, str):
                # Validate string values
                SecurityValidator.validate_no_dangerous_content(obj, "JSON value")

        check_depth(payload)
        return payload

    @staticmethod
    async def validate_file_upload(file: UploadFile) -> tuple[UploadFile, int]:
        """
        Validate uploaded file for security.

        Args:
            file: Uploaded file to validate

        Returns:
            Tuple of (Validated file, computed file size in bytes)

        Raises:
            HTTPException: If file fails validation
        """
        # Check file size using multiple methods
        file_size = None

        # Method 1: Try to get from file.size attribute if available
        if hasattr(file, 'size') and file.size is not None:
            file_size = file.size

        # Method 2: Try to get from headers
        elif hasattr(file, 'headers') and file.headers:
            content_length = file.headers.get('content-length')
            if content_length:
                with contextlib.suppress(ValueError, TypeError):
                    file_size = int(content_length)

        # Method 3: Fallback to reading up to MAX_FILE_SIZE + 1 bytes
        if file_size is None:
            try:
                # Read up to MAX_FILE_SIZE + 1 bytes to check if it exceeds limit
                chunk = await file.read(MAX_FILE_SIZE + 1)
                file_size = len(chunk)
                # Reset file position for downstream consumers
                await file.seek(0)
            except Exception:
                # If we still can't determine size, set to 0 (will be checked later)
                file_size = 0

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE} bytes"
            )

        # Check MIME type
        if file.content_type:
            if file.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type {file.content_type} is not allowed"
                )

            # Check file extension
            if file.filename:
                file_ext = Path(file.filename).suffix.lower()
                allowed_exts = ALLOWED_MIME_TYPES.get(file.content_type, [])
                if file_ext not in allowed_exts:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File extension {file_ext} doesn't match content type {file.content_type}"
                    )

        # Validate filename
        if file.filename:
            SecurityValidator.validate_no_dangerous_content(file.filename, "filename")

        return file, file_size

    @staticmethod
    def validate_query_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate query parameters for security.

        Args:
            params: Query parameters to validate

        Returns:
            Validated parameters

        Raises:
            HTTPException: If parameters contain security threats
        """
        validated = {}
        for key, value in params.items():
            # Validate parameter name
            clean_key = SecurityValidator.validate_no_dangerous_content(key, "parameter name")

            # Validate parameter value
            if isinstance(value, list):
                clean_value = [SecurityValidator.validate_no_dangerous_content(str(v), f"parameter {key}") for v in value]
            else:
                clean_value = SecurityValidator.validate_no_dangerous_content(str(value), f"parameter {key}")

            validated[clean_key] = clean_value

        return validated

    @staticmethod
    def validate_headers(headers: Dict[str, str], sensitive_headers: List[str] = None) -> Dict[str, str]:
        """
        Validate HTTP headers for security.

        Args:
            headers: Headers to validate
            sensitive_headers: List of headers that should be redacted

        Returns:
            Validated headers with sensitive values redacted
        """
        if sensitive_headers is None:
            sensitive_headers = ['authorization', 'cookie', 'x-api-key', 'x-auth-token']

        validated = {}
        for key, value in headers.items():
            # Validate header name
            clean_key = SecurityValidator.validate_no_dangerous_content(key, "header name")

            # Redact sensitive headers
            if key.lower() in sensitive_headers:
                validated[clean_key] = "***REDACTED***"
            else:
                # Validate header value
                clean_value = SecurityValidator.validate_no_dangerous_content(value, f"header {key}")
                validated[clean_key] = clean_value

        return validated


# FastAPI dependency functions
async def validate_request_security(request: Request) -> None:
    """
    FastAPI dependency to validate request security.

    Can be used in router endpoints:
    ```python
    @router.post("/endpoint", dependencies=[Depends(validate_request_security)])
    async def endpoint():
        pass
    ```
    """
    # Validate headers
    SecurityValidator.validate_headers(dict(request.headers))

    # Validate query parameters
    if request.query_params:
        SecurityValidator.validate_query_params(dict(request.query_params))

    # Validate path parameters
    if request.path_params:
        SecurityValidator.validate_query_params(request.path_params)


async def validate_json_request(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency to validate JSON request body.

    Usage:
    ```python
    @router.post("/endpoint")
    async def endpoint(validated_data: Dict = Depends(validate_json_request)):
        pass
    ```
    """
    try:
        body = await request.json()
        return SecurityValidator.validate_json_payload(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Request validation failed: {str(e)}")


async def validate_file_upload_dependency(file: UploadFile) -> UploadFile:
    """
    FastAPI dependency to validate file uploads.

    Usage:
    ```python
    @router.post("/upload")
    async def upload(file: UploadFile = Depends(validate_file_upload_dependency)):
        pass
    ```
    """
    return SecurityValidator.validate_file_upload(file)


def validate_auth_request(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> str:
    """
    FastAPI dependency to validate authentication requests.

    Usage:
    ```python
    @router.post("/secure")
    async def secure(token: str = Depends(validate_auth_request)):
        pass
    ```
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials")

    # Validate token format
    token = credentials.credentials
    SecurityValidator.validate_no_dangerous_content(token, "authentication token")

    # Additional token validation can be added here
    # e.g., JWT format validation, expiry check, etc.

    return token


# Model-specific validation dependencies
async def validate_evidence_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate evidence-specific data."""
    # Use existing evidence validation
    validated = validate_evidence_update(data)

    # Additional evidence-specific validation
    if 'file_path' in data:
        SecurityValidator.validate_no_dangerous_content(data['file_path'], 'file_path')

    if 'framework' in data:
        SecurityValidator.validate_no_dangerous_content(data['framework'], 'framework')

    return validated


async def validate_business_profile_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate business profile data."""
    validated = {}

    # Validate each field
    for field, value in data.items():
        if isinstance(value, str):
            validated[field] = SecurityValidator.validate_no_dangerous_content(value, field)
        elif isinstance(value, dict):
            validated[field] = SecurityValidator.validate_json_payload(value)
        elif isinstance(value, list):
            validated[field] = [
                SecurityValidator.validate_no_dangerous_content(str(item), f"{field} item")
                if isinstance(item, str) else item
                for item in value
            ]
        else:
            validated[field] = value

    return validated


async def validate_integration_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate integration configuration data."""
    # Whitelist of allowed providers
    ALLOWED_PROVIDERS = [
        'slack', 'teams', 'google', 'microsoft', 'okta', 'auth0',
        'salesforce', 'jira', 'github', 'gitlab', 'bitbucket'
    ]

    validated = {}

    # Validate provider
    if 'provider' in data:
        provider = data['provider'].lower()
        if provider not in ALLOWED_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider: {provider}. Allowed providers: {', '.join(ALLOWED_PROVIDERS)}"
            )
        validated['provider'] = provider

    # Validate credentials (ensure they're encrypted)
    if 'credentials' in data:
        # Don't validate the actual credential values as they should be encrypted
        # Just ensure the structure is valid
        if not isinstance(data['credentials'], dict):
            raise HTTPException(status_code=400, detail="Invalid credentials format")
        validated['credentials'] = data['credentials']

    # Validate webhook URLs
    if 'webhook_url' in data:
        try:
            validated['webhook_url'] = InputValidator.validate_url(data['webhook_url'])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Validate other fields
    for field in ['name', 'description', 'settings']:
        if field in data:
            validated[field] = SecurityValidator.validate_no_dangerous_content(str(data[field]), field)

    return validated


# Unified error handling
def handle_validation_error(error: ValidationError) -> HTTPException:
    """
    Convert Pydantic ValidationError to HTTPException with sanitized message.

    Args:
        error: Pydantic validation error

    Returns:
        HTTPException with sanitized error message
    """
    # Sanitize error messages to prevent information leakage
    errors = []
    for err in error.errors():
        location = " -> ".join(str(loc) for loc in err['loc'])
        message = err['msg']
        errors.append(f"{location}: {message}")

    return HTTPException(
        status_code=400,
        detail=f"Validation failed: {'; '.join(errors)}"
    )


# Export main components
__all__ = [
    'SecurityValidator',
    'validate_request_security',
    'validate_json_request',
    'validate_file_upload_dependency',
    'validate_auth_request',
    'validate_evidence_data',
    'validate_business_profile_data',
    'validate_integration_data',
    'handle_validation_error',
    'InputValidator',  # Re-export from utils
    'validate_evidence_update',  # Re-export from api.utils
    'sanitize_input',  # Re-export from api.utils
]
