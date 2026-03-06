"""
Security middleware for ruleIQ platform
Implements OWASP security best practices
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import re
import hashlib
import secrets
from typing import Optional


class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware"""

    def __init__(self, app, **kwargs) -> None:
        super().__init__(app)
        self.sql_injection_patterns = [
            r"(\'|\"|\;|\-\-|\||\*|\=|\\x00|\\n|\\r|\\t)",
            r"(union|select|insert|update|delete|drop|create|alter|exec|execute|script|javascript)",
        ]
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
        ]

    async def dispatch(self, request: Request, call_next):
        # 1. Add security headers
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        # 2. Remove sensitive headers
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        return response

    def validate_input(self, input_str: str) -> bool:
        """Validate input against SQL injection and XSS patterns"""
        if not input_str:
            return True

        input_lower = input_str.lower()

        # Check for SQL injection
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, input_lower):
                return False

        # Check for XSS
        for pattern in self.xss_patterns:
            if re.search(pattern, input_lower, re.IGNORECASE):
                return False

        return True


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """Authorization middleware for resource access control"""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public endpoints
        public_paths = ["/health", "/docs", "/openapi.json", "/auth/login"]

        if request.url.path in public_paths:
            return await call_next(request)

        # Extract and validate JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401, content={"detail": "Missing or invalid authorization header"}
            )

        # Token validation would go here
        # For now, pass through to next middleware
        return await call_next(request)


def generate_secure_secret(length: int = 32) -> str:
    """Generate cryptographically secure secret"""
    return secrets.token_urlsafe(length)


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hash password with salt"""
    if not salt:
        salt = secrets.token_hex(32)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,  # iterations
    )

    return password_hash.hex(), salt
