"""
Enhanced JWT Authentication Middleware v2 for RuleIQ API

SECURITY FIX (SEC-001): Resolves authentication bypass vulnerability
- All non-public routes require valid JWT authentication
- No bypass allowed for undefined routes
- Explicit exempt paths only (login, register, health)
- Feature flag controlled rollout
"""

import time
from typing import Optional, Dict, Any, List
from fastapi import Request, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt, ExpiredSignatureError
from datetime import datetime, timezone
import logging
import re

from config.settings import settings
from api.dependencies.auth import is_token_blacklisted, SECRET_KEY, ALGORITHM

logger = logging.getLogger(__name__)


class JWTAuthMiddlewareV2:
    """
    Secure JWT Authentication Middleware v2 with vulnerability fix.

    Security Improvements:
    - NO authentication bypass for undefined routes
    - Strict authentication enforcement by default
    - Explicit public paths only
    - Feature flag controlled deployment
    """

    # SECURITY FIX: Minimal public paths - only truly exempt endpoints
    PUBLIC_PATH_PATTERNS = [
        # Documentation (read-only)
        r"^/docs.*",
        r"^/redoc.*",
        r"^/openapi\.json$",
        # Health checks (no sensitive data)
        r"^/health$",
        r"^/api/v1/health$",
        r"^/api/v1/health/.*",
        r"^/api/v1/ping$",
        r"^/$",  # Root endpoint
        # Authentication endpoints (must be public for login)
        r"^/api/v1/auth/login$",
        r"^/api/v1/auth/register$",
        r"^/api/v1/auth/token$",
        r"^/api/v1/auth/refresh$",
        r"^/api/v1/auth/forgot-password$",
        r"^/api/v1/auth/reset-password$",
        r"^/api/v1/auth/google/.*",  # Google OAuth flow
        # Freemium endpoints (public by design)
        r"^/api/v1/freemium/leads$",
        r"^/api/v1/freemium/sessions$",
        r"^/api/v1/freemium/messages$",
        # Test utilities (only in non-production)
        r"^/api/test-utils/.*",  # Will be filtered by environment check
    ]

    # High-value endpoints requiring extra logging
    HIGH_VALUE_ENDPOINTS = [
        r"^/api/v1/admin/.*",
        r"^/api/v1/payments/.*",
        r"^/api/v1/api-keys/.*",
        r"^/api/v1/secrets/.*",
        r"^/api/v1/users/.*/delete$",
        r"^/api/v1/export/.*",
        r"^/api/v1/settings/.*",
    ]

    def __init__(
        self,
        enable_strict_mode: bool = True,  # SECURITY FIX: Default to strict
        enable_rate_limiting: bool = True,
        enable_audit_logging: bool = True,
        enable_performance_monitoring: bool = True,
        custom_public_paths: Optional[List[str]] = None,
        test_mode: bool = False,
    ) -> None:
        """
        Initialize JWT middleware v2 with secure defaults.

        Args:
            enable_strict_mode: ALWAYS enforce authentication (default: True)
            enable_rate_limiting: Enable rate limiting for auth endpoints
            enable_audit_logging: Log authentication events
            enable_performance_monitoring: Track middleware performance
            custom_public_paths: Additional public paths (use with caution)
            test_mode: Enable test mode for unit testing
        """
        self.enable_strict_mode = enable_strict_mode
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_audit_logging = enable_audit_logging
        self.enable_performance_monitoring = enable_performance_monitoring
        self.test_mode = test_mode

        # Filter test utilities in production
        public_patterns = self.PUBLIC_PATH_PATTERNS.copy()
        if settings.is_production and not test_mode:
            public_patterns = [p for p in public_patterns if not p.startswith(r"^/api/test-utils")]

        # Compile regex patterns for efficiency
        self.public_patterns = [re.compile(pattern) for pattern in public_patterns]

        # Add custom public paths (with warning)
        if custom_public_paths:
            logger.warning(f"Adding custom public paths: {custom_public_paths}")
            self.public_patterns.extend([re.compile(pattern) for pattern in custom_public_paths])

        # Compile high-value endpoint patterns
        self.high_value_patterns = [re.compile(pattern) for pattern in self.HIGH_VALUE_ENDPOINTS]

        # Rate limiting storage (production should use Redis)
        self.auth_attempts: Dict[str, List[float]] = {}
        self.rate_limit_window = 60  # 1 minute
        self.max_auth_attempts = settings.auth_rate_limit_per_minute

        # Performance metrics
        self.performance_metrics: Dict[str, List[float]] = {}

    def is_public_path(self, path: str) -> bool:
        """Check if a path is public and doesn't require authentication."""
        is_public = any(pattern.match(path) for pattern in self.public_patterns)
        if is_public:
            logger.debug(f"Path {path} identified as public")
        return is_public

    def is_high_value_endpoint(self, path: str) -> bool:
        """Check if endpoint is high-value and requires extra logging."""
        return any(pattern.match(path) for pattern in self.high_value_patterns)

    def check_rate_limit(self, identifier: str) -> bool:
        """
        Check if rate limit is exceeded for an identifier.

        Args:
            identifier: Client IP or user ID

        Returns:
            True if rate limit exceeded, False otherwise
        """
        if not self.enable_rate_limiting or self.test_mode:
            return False

        current_time = time.time()

        # Clean up old attempts
        if identifier in self.auth_attempts:
            self.auth_attempts[identifier] = [
                t
                for t in self.auth_attempts[identifier]
                if current_time - t < self.rate_limit_window
            ]

        # Check current attempts
        attempts = self.auth_attempts.get(identifier, [])
        if len(attempts) >= self.max_auth_attempts:
            logger.warning(f"Rate limit exceeded for {identifier}")
            return True

        # Record new attempt
        if identifier not in self.auth_attempts:
            self.auth_attempts[identifier] = []
        self.auth_attempts[identifier].append(current_time)

        return False

    async def validate_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token with comprehensive security checks.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            # SECURITY: Check if token is blacklisted
            if not self.test_mode and await is_token_blacklisted(token):
                logger.warning("Attempted use of blacklisted token")
                return None

            # Decode and validate token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

            # SECURITY: Validate token type
            token_type = payload.get("type", "access")
            if token_type != "access":
                logger.warning(f"Invalid token type: {token_type}")
                return None

            # SECURITY: Check expiration
            exp = payload.get("exp")
            if exp:
                exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
                current_time = datetime.now(timezone.utc)

                if exp_datetime < current_time:
                    logger.info("Token expired")
                    return None

                # Warn if token is about to expire (5 minutes)
                time_until_expiry = (exp_datetime - current_time).total_seconds()
                if time_until_expiry < 300:
                    logger.warning(f"Token expires in {time_until_expiry:.0f} seconds")

            # SECURITY: Validate required claims
            if not payload.get("sub"):
                logger.warning("Token missing 'sub' claim")
                return None

            return payload

        except ExpiredSignatureError:
            logger.info("Token signature expired")
            return None
        except JWTError as e:
            logger.error(f"JWT validation error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error validating token: {e}")
            return None

    async def log_auth_event(
        self,
        request: Request,
        event_type: str,
        success: bool,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log authentication events for security audit."""
        if not self.enable_audit_logging or self.test_mode:
            return

        # Extra logging for high-value endpoints
        is_high_value = self.is_high_value_endpoint(request.url.path)

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "success": success,
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("User-Agent"),
            "user_id": user_id,
            "high_value": is_high_value,
            "details": details or {},
        }

        if success:
            if is_high_value:
                logger.info(f"HIGH VALUE Auth event: {log_entry}")
            else:
                logger.info(f"Auth event: {log_entry}")
        else:
            logger.warning(f"Auth failure: {log_entry}")

    def track_performance(self, path: str, duration: float):
        """Track middleware performance metrics."""
        if not self.enable_performance_monitoring or self.test_mode:
            return

        if path not in self.performance_metrics:
            self.performance_metrics[path] = []

        # Keep last 100 measurements
        self.performance_metrics[path].append(duration)
        if len(self.performance_metrics[path]) > 100:
            self.performance_metrics[path].pop(0)

        # Log if performance degrades
        if duration > 0.01:  # 10ms threshold
            logger.warning(f"Slow auth middleware for {path}: {duration * 1000:.2f}ms")

    async def __call__(self, request: Request, call_next):
        """
        Process request through secure JWT authentication middleware.

        SECURITY FIX: No bypass for undefined routes - all non-public routes require auth.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response after authentication processing
        """
        start_time = time.time()
        path = request.url.path

        # Check if this is a public path
        if self.is_public_path(path):
            # Public paths don't require authentication
            response = await call_next(request)
            self.track_performance(path, time.time() - start_time)
            return response

        # SECURITY FIX: ALL non-public paths MUST have authentication
        # No more bypass for "non-critical" routes

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # SECURITY: No token = no access (strict enforcement)
            await self.log_auth_event(
                request,
                "MISSING_TOKEN",
                False,
                details={"reason": "No Authorization header", "strict_mode": True},
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required", "error_code": "AUTH_REQUIRED"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract token
        token = auth_header.replace("Bearer ", "").strip()

        # Check rate limiting for authentication endpoints
        if path.startswith("/api/v1/auth/"):
            client_ip = request.client.host if request.client else "unknown"
            if self.check_rate_limit(client_ip):
                await self.log_auth_event(
                    request, "RATE_LIMIT_EXCEEDED", False, details={"client_ip": client_ip}
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many authentication attempts. Please try again later.",
                        "retry_after": self.rate_limit_window,
                    },
                )

        # Validate token
        payload = await self.validate_jwt_token(token)
        if not payload:
            await self.log_auth_event(
                request,
                "INVALID_TOKEN",
                False,
                details={"reason": "Token validation failed", "path": path},
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token", "error_code": "INVALID_TOKEN"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Store user information in request state
        request.state.user_id = payload.get("sub")
        request.state.token_payload = payload
        request.state.is_authenticated = True
        request.state.auth_method = "jwt_v2"

        # Log successful authentication
        await self.log_auth_event(
            request,
            "AUTHENTICATION_SUCCESS",
            True,
            user_id=request.state.user_id,
            details={"high_value": self.is_high_value_endpoint(path)},
        )

        # Process request
        response = await call_next(request)

        # Add security headers to response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Auth-Version"] = "v2"

        # Add token expiry warning header if applicable
        exp = payload.get("exp")
        if exp:
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            current_time = datetime.now(timezone.utc)
            time_until_expiry = (exp_datetime - current_time).total_seconds()

            if time_until_expiry < 300:  # Less than 5 minutes
                response.headers["X-Token-Expires-In"] = str(int(time_until_expiry))
                response.headers["X-Token-Refresh-Recommended"] = "true"

        # Track performance
        self.track_performance(path, time.time() - start_time)

        return response


def get_jwt_middleware_v2(**kwargs) -> JWTAuthMiddlewareV2:
    """
    Factory function to create JWT middleware v2 instance.

    This version includes the security fix for SEC-001.
    """
    return JWTAuthMiddlewareV2(**kwargs)
