"""
Enhanced JWT Authentication Middleware with comprehensive route protection.
Provides 100% coverage for all protected routes with proper exemptions.
"""

import re
from typing import List, Optional, Dict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import jwt
from jwt.exceptions import InvalidTokenError
import logging
from datetime import datetime
from functools import lru_cache

from core.config import settings

logger = logging.getLogger(__name__)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive JWT authentication middleware with route protection.
    Ensures 100% coverage of protected routes with proper exemptions.
    """

    # Public routes that don't require authentication
    PUBLIC_ROUTES = {
        # Auth endpoints
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/token",
        "/api/auth/refresh",
        "/api/google-auth/login",
        "/api/google-auth/callback",
        # Health checks
        "/health",
        "/api/health",
        "/api/monitoring/health",
        "/api/freemium/health",
        "/api/iq-agent/health",
        "/api/secrets-vault/status",
        # Public freemium endpoints
        "/api/freemium/leads",
        "/api/freemium/sessions",
        # Webhooks (validated differently)
        "/api/webhooks/stripe",
        "/api/webhooks/github",
        "/api/webhooks/sendgrid",
        # Documentation
        "/docs",
        "/redoc",
        "/openapi.json",
        # Static files
        "/favicon.ico",
    }

    # Patterns for public routes
    PUBLIC_PATTERNS = [
        re.compile(r"^/api/freemium/sessions/[^/]+$"),  # Session token endpoints
        re.compile(r"^/api/freemium/sessions/[^/]+/.*$"),
        re.compile(r"^/api/webhooks/custom/.*$"),
        re.compile(r"^/_next/.*$"),  # Next.js static files
        re.compile(r"^/static/.*$"),  # Static files
    ]

    # Routes requiring special permissions (admin, etc)
    ADMIN_ROUTES = {
        "/api/admin",
        "/api/rbac-auth/admin",
        "/api/test-utils",
    }

    # Pattern for admin routes
    ADMIN_PATTERNS = [
        re.compile(r"^/api/admin/.*$"),
        re.compile(r"^/api/rbac-auth/admin/.*$"),
        re.compile(r"^/api/test-utils/.*$"),
    ]

    def __init__(self, app, secret_key: Optional[str] = None) -> None:
        super().__init__(app)
        self.secret_key = secret_key or settings.SECRET_KEY
        self.algorithm = "HS256"
        self.token_cache: Dict[str, Dict] = {}
        self.cache_ttl = 300  # 5 minutes

    async def dispatch(self, request: Request, call_next):
        """Process each request through JWT validation."""

        # Check if route is public
        if self._is_public_route(request.url.path):
            return await call_next(request)

        # Extract token
        token = self._extract_token(request)
        if not token:
            return self._unauthorized_response("Authentication required")

        # Validate token
        try:
            payload = self._validate_token(token)
            if not payload:
                return self._unauthorized_response("Invalid token")

            # Check token expiration
            if self._is_token_expired(payload):
                return self._unauthorized_response("Token expired")

            # Check if route requires admin permissions
            if self._is_admin_route(request.url.path):
                if not self._has_admin_permission(payload):
                    return self._forbidden_response("Admin access required")

            # Add user info to request state
            request.state.user = payload
            request.state.user_id = payload.get("sub") or payload.get("user_id")
            request.state.token = token

            # Log successful authentication
            self._log_access(request, payload, True)

        except InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return self._unauthorized_response("Invalid token")
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return self._unauthorized_response("Authentication failed")

        # Process request
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

    def _is_public_route(self, path: str) -> bool:
        """Check if route is public and doesn't require authentication."""
        # Check exact matches
        if path in self.PUBLIC_ROUTES:
            return True

        # Check patterns
        return any(pattern.match(path) for pattern in self.PUBLIC_PATTERNS)

    def _is_admin_route(self, path: str) -> bool:
        """Check if route requires admin permissions."""
        # Check exact matches
        if any(path.startswith(route) for route in self.ADMIN_ROUTES):
            return True

        # Check patterns
        return any(pattern.match(path) for pattern in self.ADMIN_PATTERNS)

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from request."""
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]

        # Check cookies (for web clients)
        token = request.cookies.get("access_token")
        if token:
            return token

        # Check query parameters (for WebSocket connections)
        token = request.query_params.get("token")
        if token:
            return token

        return None

    @lru_cache(maxsize=100)
    def _validate_token(self, token: str) -> Optional[Dict]:
        """Validate JWT token and return payload."""
        try:
            # Check cache first
            if token in self.token_cache:
                cached = self.token_cache[token]
                if cached["expires"] > datetime.utcnow().timestamp():
                    return cached["payload"]
                else:
                    del self.token_cache[token]

            # Validate token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Cache valid token
            self.token_cache[token] = {
                "payload": payload,
                "expires": datetime.utcnow().timestamp() + self.cache_ttl,
            }

            return payload

        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return None

    def _is_token_expired(self, payload: Dict) -> bool:
        """Check if token is expired."""
        exp = payload.get("exp")
        if not exp:
            return True

        return datetime.utcnow().timestamp() > exp

    def _has_admin_permission(self, payload: Dict) -> bool:
        """Check if user has admin permissions."""
        # Check roles
        roles = payload.get("roles", [])
        if "admin" in roles or "super_admin" in roles:
            return True

        # Check permissions
        permissions = payload.get("permissions", [])
        if "admin" in permissions or "admin_roles" in permissions:
            return True

        # Check is_admin flag
        return payload.get("is_admin", False)

    def _unauthorized_response(self, detail: str = "Unauthorized") -> Response:
        """Return 401 Unauthorized response."""
        return Response(
            content=f'{{"detail": "{detail}"}}',
            status_code=401,
            headers={"WWW-Authenticate": "Bearer", "Content-Type": "application/json"},
        )

    def _forbidden_response(self, detail: str = "Forbidden") -> Response:
        """Return 403 Forbidden response."""
        return Response(
            content=f'{{"detail": "{detail}"}}',
            status_code=403,
            headers={"Content-Type": "application/json"},
        )

    def _log_access(self, request: Request, user: Dict, success: bool):
        """Log access attempts for audit purposes."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user.get("sub") or user.get("user_id"),
            "username": user.get("username"),
            "path": request.url.path,
            "method": request.method,
            "success": success,
            "ip": request.client.host if request.client else "unknown",
        }

        if success:
            logger.info(f"Access granted: {log_entry}")
        else:
            logger.warning(f"Access denied: {log_entry}")


class JWTRateLimiter:
    """Rate limiter for JWT-authenticated endpoints."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[float]] = {}

    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user has exceeded rate limit."""
        now = datetime.utcnow().timestamp()
        minute_ago = now - 60

        if user_id not in self.requests:
            self.requests[user_id] = []

        # Remove old requests
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id] if req_time > minute_ago
        ]

        # Check limit
        if len(self.requests[user_id]) >= self.requests_per_minute:
            return False

        # Add current request
        self.requests[user_id].append(now)
        return True


def setup_jwt_middleware(app):
    """Setup JWT middleware on FastAPI app."""
    middleware = JWTAuthMiddleware(app)
    app.add_middleware(JWTAuthMiddleware)
    logger.info("JWT authentication middleware configured")
    return middleware
