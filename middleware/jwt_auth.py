"""
JWT Authentication Middleware for RuleIQ API

This middleware provides comprehensive JWT authentication with:
- Token validation and blacklisting
- Rate limiting for auth endpoints
- Token refresh mechanism
- Security headers
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
from api.dependencies.auth import (
    is_token_blacklisted,
    SECRET_KEY,
    ALGORITHM
)

logger = logging.getLogger(__name__)

class JWTAuthMiddleware:
    """
    Enhanced JWT Authentication Middleware with comprehensive security features.

    Features:
    - Token validation with blacklist checking
    - Public and protected route management
    - Rate limiting for authentication endpoints
    - Token expiry warnings
    - Security event logging
    """

    # Define public paths that don't require authentication
    PUBLIC_PATH_PATTERNS = [
        r'^/docs.*',
        r'^/redoc.*',
        r'^/openapi\.json$',
        r'^/health$',
        r'^/api/v1/health.*',
        r'^/$',  # Root endpoint
        r'^/api/v1/auth/login$',
        r'^/api/v1/auth/register$',
        r'^/api/v1/auth/token$',
        r'^/api/v1/auth/refresh$',
        r'^/api/v1/auth/forgot-password$',
        r'^/api/v1/auth/reset-password$',
        r'^/api/v1/auth/google.*',  # Google OAuth
        r'^/api/v1/freemium.*',  # Freemium endpoints
        r'^/api/test-utils.*',  # Test utilities (dev only)
    ]

    # Critical routes requiring strict authentication (20% coverage target)
    CRITICAL_PROTECTED_ROUTES = [
        # User management endpoints
        r'^/api/v1/users.*',
        # Admin endpoints
        r'^/api/v1/api/admin.*',
        r'^/api/v1/admin.*',
        # Data export endpoints
        r'^/api/v1/reports/export.*',
        r'^/api/v1/evidence/export.*',
        r'^/api/v1/audit-export.*',
        # Settings and configuration
        r'^/api/v1/settings.*',
        r'^/api/v1/business-profiles.*',
        # Payment and billing
        r'^/api/v1/payments.*',
        # API key management
        r'^/api/v1/api-keys.*',
        # Webhook management
        r'^/api/v1/webhooks.*',
        # Secrets vault
        r'^/api/v1/secrets.*',
        # Compliance and assessments (write operations)
        r'^/api/v1/assessments.*',
        r'^/api/v1/compliance.*',
        r'^/api/v1/policies.*',
        # AI endpoints (cost-sensitive)
        r'^/api/v1/ai/.*',
        r'^/api/v1/iq-agent.*',
        r'^/api/v1/agentic-rag.*',
        # Integration management
        r'^/api/v1/integrations.*',
        # Dashboard data
        r'^/api/dashboard$',
        r'^/api/v1/dashboard.*',
        # Monitoring and security
        r'^/api/v1/monitoring.*',
        r'^/api/v1/security.*',
        r'^/api/v1/performance.*',
    ]

    def __init__(
        self,
        enable_strict_mode: bool = True,
        enable_rate_limiting: bool = True,
        enable_audit_logging: bool = True,
        custom_public_paths: Optional[List[str]] = None,
        custom_protected_paths: Optional[List[str]] = None
    ) -> None:
        """
        Initialize JWT middleware with configuration options.

        Args:
            enable_strict_mode: Enforce authentication on all non-public routes
            enable_rate_limiting: Enable rate limiting for auth endpoints
            enable_audit_logging: Log authentication events
            custom_public_paths: Additional public path patterns
            custom_protected_paths: Additional protected path patterns
        """
        self.enable_strict_mode = enable_strict_mode
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_audit_logging = enable_audit_logging

        # Compile regex patterns for efficiency
        self.public_patterns = [
            re.compile(pattern) for pattern in self.PUBLIC_PATH_PATTERNS
        ]
        if custom_public_paths:
            self.public_patterns.extend([
                re.compile(pattern) for pattern in custom_public_paths
            ])

        self.protected_patterns = [
            re.compile(pattern) for pattern in self.CRITICAL_PROTECTED_ROUTES
        ]
        if custom_protected_paths:
            self.protected_patterns.extend([
                re.compile(pattern) for pattern in custom_protected_paths
            ])

        # Rate limiting storage (in production, use Redis)
        self.auth_attempts: Dict[str, List[float]] = {}
        self.rate_limit_window = 60  # 1 minute
        self.max_auth_attempts = settings.auth_rate_limit_per_minute

    def is_public_path(self, path: str) -> bool:
        """Check if a path is public and doesn't require authentication."""
        return any(pattern.match(path) for pattern in self.public_patterns)

    def is_critical_path(self, path: str) -> bool:
        """Check if a path is critical and requires strict authentication."""
        return any(pattern.match(path) for pattern in self.protected_patterns)

    def check_rate_limit(self, identifier: str) -> bool:
        """
        Check if rate limit is exceeded for an identifier.

        Args:
            identifier: Client IP or user ID

        Returns:
            True if rate limit exceeded, False otherwise
        """
        if not self.enable_rate_limiting:
            return False

        current_time = time.time()

        # Clean up old attempts
        if identifier in self.auth_attempts:
            self.auth_attempts[identifier] = [
                t for t in self.auth_attempts[identifier]
                if current_time - t < self.rate_limit_window
            ]

        # Check current attempts
        attempts = self.auth_attempts.get(identifier, [])
        if len(attempts) >= self.max_auth_attempts:
            return True

        # Record new attempt
        if identifier not in self.auth_attempts:
            self.auth_attempts[identifier] = []
        self.auth_attempts[identifier].append(current_time)

        return False

    async def validate_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token with comprehensive checks.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            # Check if token is blacklisted
            if await is_token_blacklisted(token):
                logger.warning("Attempted use of blacklisted token")
                return None

            # Decode and validate token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

            # Validate token type
            if payload.get('type') != 'access':
                logger.warning(f"Invalid token type: {payload.get('type')}")
                return None

            # Check expiration
            exp = payload.get('exp')
            if exp:
                exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
                current_time = datetime.now(timezone.utc)

                if exp_datetime < current_time:
                    logger.info("Token expired")
                    return None

                # Warn if token is about to expire (5 minutes)
                time_until_expiry = (exp_datetime - current_time).total_seconds()
                if time_until_expiry < 300:
                    logger.warning(f"Token expires in {time_until_expiry} seconds")

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
        details: Optional[Dict[str, Any]] = None
    ):
        """Log authentication events for audit purposes."""
        if not self.enable_audit_logging:
            return

        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'event_type': event_type,
            'success': success,
            'path': request.url.path,
            'method': request.method,
            'client_ip': request.client.host if request.client else None,
            'user_agent': request.headers.get('User-Agent'),
            'user_id': user_id,
            'details': details or {}
        }

        if success:
            logger.info(f"Auth event: {log_entry}")
        else:
            logger.warning(f"Auth failure: {log_entry}")

    async def __call__(self, request: Request, call_next):
        """
        Process request through JWT authentication middleware.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response after authentication processing
        """
        path = request.url.path

        # Skip authentication for public paths
        if self.is_public_path(path):
            return await call_next(request)

        # Check if this is a critical protected route
        is_critical = self.is_critical_path(path)

        # Extract token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            if is_critical or self.enable_strict_mode:
                await self.log_auth_event(
                    request, 'MISSING_TOKEN', False,
                    details={'reason': 'No Authorization header'}
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={'detail': 'Authentication required'},
                    headers={'WWW-Authenticate': 'Bearer'}
                )
            # Allow non-critical routes without auth if not in strict mode
            return await call_next(request)

        # Extract and validate token
        token = auth_header.replace('Bearer ', '').strip()

        # Check rate limiting for authentication endpoints
        if path.startswith('/api/v1/auth/'):
            client_ip = request.client.host if request.client else 'unknown'
            if self.check_rate_limit(client_ip):
                await self.log_auth_event(
                    request, 'RATE_LIMIT_EXCEEDED', False,
                    details={'client_ip': client_ip}
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={'detail': 'Too many authentication attempts. Please try again later.'}
                )

        # Validate token
        payload = await self.validate_jwt_token(token)
        if not payload:
            await self.log_auth_event(
                request, 'INVALID_TOKEN', False,
                details={'reason': 'Token validation failed'}
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={'detail': 'Invalid or expired token'},
                headers={'WWW-Authenticate': 'Bearer'}
            )

        # Store user information in request state
        request.state.user_id = payload.get('sub')
        request.state.token_payload = payload
        request.state.is_authenticated = True

        # Log successful authentication
        await self.log_auth_event(
            request, 'AUTHENTICATION_SUCCESS', True,
            user_id=request.state.user_id
        )

        # Process request
        response = await call_next(request)

        # Add security headers to response
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'

        # Add token expiry warning header if applicable
        exp = payload.get('exp')
        if exp:
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            current_time = datetime.now(timezone.utc)
            time_until_expiry = (exp_datetime - current_time).total_seconds()

            if time_until_expiry < 300:  # Less than 5 minutes
                response.headers['X-Token-Expires-In'] = str(int(time_until_expiry))
                response.headers['X-Token-Refresh-Recommended'] = 'true'

        return response


def get_jwt_middleware(**kwargs) -> JWTAuthMiddleware:
    """Factory function to create JWT middleware instance."""
    return JWTAuthMiddleware(**kwargs)
