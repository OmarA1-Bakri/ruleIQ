"""
CORS Configuration Middleware for RuleIQ API

Story 1.3: CORS Configuration Implementation
Provides secure, environment-specific CORS configuration for frontend-backend communication.
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response


logger = logging.getLogger(__name__)


class CORSConfig:
    """
    CORS configuration manager with environment-specific settings.

    Features:
    - Environment-specific origin configuration
    - No wildcards in production
    - Proper preflight handling
    - Credentials support for JWT auth
    - Custom header exposure
    """

    # Development origins
    ORIGINS_DEV = [
        "http://localhost:3000",  # Next.js default
        "http://localhost:3001",  # Alternative port
        "http://127.0.0.1:3000",  # IP-based access
        "http://localhost:5173",  # Vite default
        "http://localhost:8080",  # Alternative dev
    ]

    # Staging origins
    ORIGINS_STAGING = [
        "https://staging.ruleiq.com",
        "https://staging-app.ruleiq.com",
        "https://preview.ruleiq.com",
    ]

    # Production origins
    ORIGINS_PROD = [
        "https://app.ruleiq.com",
        "https://www.ruleiq.com",
        "https://ruleiq.com",
    ]

    # Allowed HTTP methods
    ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]

    # Allowed request headers
    ALLOWED_HEADERS = [
        "Accept",
        "Accept-Language",
        "Content-Type",
        "Content-Language",
        "Authorization",
        "X-Request-ID",
        "X-CSRF-Token",
        "X-Requested-With",
        "Cache-Control",
        "Pragma",
    ]

    # Headers to expose to frontend
    EXPOSED_HEADERS = [
        # Pagination headers
        "X-Total-Count",
        "X-Page-Count",
        "X-Current-Page",
        "X-Per-Page",
        # Rate limit headers (from Story 1.2)
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
        # Custom application headers
        "X-Request-ID",
        "X-Response-Time",
        "X-Version",
        # File download headers
        "Content-Disposition",
        "Content-Length",
    ]

    def __init__(self) -> None:
        """Initialize CORS configuration."""
        self.environment = self._get_environment()
        self.allowed_origins = self._get_allowed_origins()
        self.allow_credentials = True  # Required for JWT cookies
        self.max_age = 3600  # 1 hour preflight cache

        # Validate configuration
        self._validate_config()

        logger.info(
            f"CORS initialized for {self.environment} environment with "
            f"{len(self.allowed_origins)} allowed origins"
        )

    def _get_environment(self) -> str:
        """Get current environment."""
        env = os.getenv("ENVIRONMENT", "development").lower()

        # Map common environment names
        env_map = {
            "dev": "development",
            "develop": "development",
            "prod": "production",
            "live": "production",
            "stage": "staging",
        }

        return env_map.get(env, env)

    def _get_allowed_origins(self) -> List[str]:
        """Get allowed origins based on environment."""
        # Check for environment variable override
        env_origins = os.getenv("CORS_ORIGINS")
        if env_origins:
            try:
                # Parse JSON array
                origins = json.loads(env_origins)
                if isinstance(origins, list):
                    logger.info(f"Using CORS origins from environment: {origins}")
                    return origins
            except json.JSONDecodeError:
                # Try comma-separated
                origins = [o.strip() for o in env_origins.split(",")]
                logger.info(f"Using CORS origins from environment: {origins}")
                return origins

        # Use default based on environment
        if self.environment == "development":
            return self.ORIGINS_DEV
        elif self.environment == "staging":
            return self.ORIGINS_STAGING
        elif self.environment == "production":
            return self.ORIGINS_PROD
        else:
            # Unknown environment, use dev with warning
            logger.warning(f"Unknown environment '{self.environment}', using dev origins")
            return self.ORIGINS_DEV

    def _validate_config(self):
        """Validate CORS configuration for security."""
        # Check for wildcards in production
        if self.environment == "production":
            for origin in self.allowed_origins:
                if origin == "*" or origin.startswith("http://"):
                    raise ValueError(
                        f"Insecure origin '{origin}' not allowed in production. "
                        "Use HTTPS and specific domains only."
                    )

        # Warn about wildcards in any environment
        if "*" in self.allowed_origins:
            logger.warning(
                "Wildcard origin (*) detected in CORS configuration. "
                "This is a security risk and should be avoided."
            )

        # Validate origin formats
        for origin in self.allowed_origins:
            if origin != "*":
                try:
                    parsed = urlparse(origin)
                    if not parsed.scheme or not parsed.netloc:
                        raise ValueError(f"Invalid origin format: {origin}")
                except Exception as e:
                    raise ValueError(f"Invalid origin '{origin}': {e}")

    def is_origin_allowed(self, origin: str) -> bool:
        """
        Check if an origin is allowed.

        Args:
            origin: Origin header value

        Returns:
            True if origin is allowed
        """
        if not origin:
            return False

        # Check exact match
        if origin in self.allowed_origins:
            return True

        # Check for wildcard (not recommended)
        if "*" in self.allowed_origins:
            logger.warning(f"Allowing origin '{origin}' due to wildcard configuration")
            return True

        # Check for subdomain patterns (if configured)
        for allowed in self.allowed_origins:
            if allowed.startswith("*."):
                # Pattern like *.example.com
                domain = allowed[2:]
                parsed_origin = urlparse(origin)
                if parsed_origin.netloc.endswith(domain):
                    return True

        return False

    def get_cors_headers(self, origin: str) -> Dict[str, str]:
        """
        Get CORS headers for response.

        Args:
            origin: Request origin

        Returns:
            Dictionary of CORS headers
        """
        headers = {}

        if self.is_origin_allowed(origin):
            headers["Access-Control-Allow-Origin"] = origin
            headers["Vary"] = "Origin"

            if self.allow_credentials:
                headers["Access-Control-Allow-Credentials"] = "true"

        return headers

    def get_preflight_headers(self, origin: str) -> Dict[str, str]:
        """
        Get headers for preflight response.

        Args:
            origin: Request origin

        Returns:
            Dictionary of preflight headers
        """
        headers = self.get_cors_headers(origin)

        if headers:
            # Add preflight-specific headers
            headers["Access-Control-Allow-Methods"] = ", ".join(self.ALLOWED_METHODS)
            headers["Access-Control-Allow-Headers"] = ", ".join(self.ALLOWED_HEADERS)
            headers["Access-Control-Expose-Headers"] = ", ".join(self.EXPOSED_HEADERS)
            headers["Access-Control-Max-Age"] = str(self.max_age)

        return headers

    def to_middleware_kwargs(self) -> Dict[str, Any]:
        """
        Get kwargs for FastAPI CORSMiddleware.

        Returns:
            Dictionary of middleware configuration
        """
        return {
            "allow_origins": self.allowed_origins,
            "allow_credentials": self.allow_credentials,
            "allow_methods": self.ALLOWED_METHODS,
            "allow_headers": self.ALLOWED_HEADERS,
            "expose_headers": self.EXPOSED_HEADERS,
            "max_age": self.max_age,
        }


class EnhancedCORSMiddleware:
    """
    Enhanced CORS middleware with logging and security features.

    Wraps FastAPI's CORSMiddleware with additional functionality:
    - CORS violation logging
    - Origin spoofing detection
    - Debug mode for development
    """

    def __init__(self, app, config: Optional[CORSConfig] = None) -> None:
        """Initialize enhanced CORS middleware."""
        self.app = app
        self.config = config or CORSConfig()
        self.debug = self.config.environment == "development"

        # Track CORS violations for monitoring
        self.violation_count = 0
        self.last_violations = []

    async def __call__(self, request: Request, call_next):
        """Process request with CORS handling."""
        origin = request.headers.get("origin")

        # Check for preflight request
        if request.method == "OPTIONS":
            return self._handle_preflight(request)

        # Check origin validity
        if origin and not self.config.is_origin_allowed(origin):
            self._log_cors_violation(request, origin)

        # Process request
        response = await call_next(request)

        # Add CORS headers to response
        if origin:
            cors_headers = self.config.get_cors_headers(origin)
            for header, value in cors_headers.items():
                response.headers[header] = value

        return response

    def _handle_preflight(self, request: Request) -> Response:
        """Handle preflight OPTIONS request."""
        origin = request.headers.get("origin")

        if not origin:
            # No origin, return basic response
            return Response(status_code=200)

        if not self.config.is_origin_allowed(origin):
            # Origin not allowed, log and return error
            self._log_cors_violation(request, origin, is_preflight=True)

            if self.debug:
                # In debug, return detailed error
                return Response(
                    status_code=403,
                    content=f"CORS error: Origin '{origin}' not allowed. "
                    f"Allowed origins: {self.config.allowed_origins}",
                )
            else:
                # In production, return generic error
                return Response(status_code=403)

        # Origin allowed, return preflight response
        headers = self.config.get_preflight_headers(origin)

        return Response(status_code=200, headers=headers)

    def _log_cors_violation(self, request: Request, origin: str, is_preflight: bool = False):
        """Log CORS violation for monitoring."""
        self.violation_count += 1

        violation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "origin": origin,
            "path": request.url.path,
            "method": request.method,
            "is_preflight": is_preflight,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

        # Keep last 100 violations in memory
        self.last_violations.append(violation)
        if len(self.last_violations) > 100:
            self.last_violations.pop(0)

        # Log the violation
        logger.warning(
            f"CORS violation: Origin '{origin}' not allowed for "
            f"{request.method} {request.url.path} from {violation['client_ip']}"
        )

        # In debug mode, provide more details
        if self.debug:
            logger.debug(f"CORS violation details: {violation}")
            logger.debug(f"Allowed origins: {self.config.allowed_origins}")

    def get_stats(self) -> Dict[str, Any]:
        """Get CORS statistics."""
        return {
            "violation_count": self.violation_count,
            "recent_violations": self.last_violations[-10:],
            "allowed_origins": self.config.allowed_origins,
            "environment": self.config.environment,
        }


def create_cors_middleware(app) -> CORSMiddleware:
    """
    Create and configure CORS middleware for FastAPI app.

    Args:
        app: FastAPI application instance

    Returns:
        Configured CORSMiddleware
    """
    config = CORSConfig()

    # Use FastAPI's built-in CORSMiddleware with our configuration
    return CORSMiddleware(app, **config.to_middleware_kwargs())


def setup_cors(app):
    """
    Setup CORS for FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Create configuration
    config = CORSConfig()

    # Log configuration
    logger.info(
        f"Setting up CORS for {config.environment} environment:\n"
        f"  Allowed origins: {config.allowed_origins}\n"
        f"  Allow credentials: {config.allow_credentials}\n"
        f"  Max age: {config.max_age}s"
    )

    # Add middleware to app
    app.add_middleware(CORSMiddleware, **config.to_middleware_kwargs())
