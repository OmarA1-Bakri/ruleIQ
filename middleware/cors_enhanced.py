"""
Enhanced CORS Middleware with Production-Ready Security
Implements proper CORS handling with environment-specific configuration
"""

from typing import Optional, Callable
from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging
from config.security_settings import get_security_settings, SecurityEnvironment

logger = logging.getLogger(__name__)


class EnhancedCORSMiddleware(BaseHTTPMiddleware):
    """
    Enhanced CORS middleware with production-ready security features
    - Environment-specific configuration
    - WebSocket CORS support
    - Vary: Origin header for proper caching
    - Preflight request optimization
    """

    def __init__(
        self, app: ASGIApp, environment: Optional[SecurityEnvironment] = None, **kwargs
    ) -> None:
        super().__init__(app)
        self.security_settings = get_security_settings()
        self.environment = environment or self.security_settings.environment
        self.cors_config = self.security_settings.get_cors_config()

        # Get configuration from security settings
        self.allowed_origins = self.cors_config["allow_origins"]
        self.allowed_methods = self.cors_config["allow_methods"]
        self.allowed_headers = self.cors_config["allow_headers"]
        self.exposed_headers = self.cors_config["expose_headers"]
        self.allow_credentials = self.cors_config["allow_credentials"]
        self.max_age = self.cors_config["max_age"]

        # WebSocket origins
        if self.environment == SecurityEnvironment.DEVELOPMENT:
            self.websocket_origins = [
                "ws://localhost:3000",
                "ws://localhost:8000",
                "ws://127.0.0.1:3000",
            ]
        else:
            self.websocket_origins = self.security_settings.cors.websocket_origins

        logger.info(f"CORS initialized for environment: {self.environment}")
        logger.debug(f"Allowed origins: {self.allowed_origins}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process CORS headers for each request"""

        # Get origin from request
        origin = request.headers.get("origin")

        # Handle WebSocket upgrade requests
        if request.headers.get("upgrade") == "websocket":
            return await self._handle_websocket_cors(request, call_next, origin)

        # Handle preflight requests
        if request.method == "OPTIONS":
            return await self._handle_preflight(request, origin)

        # Process regular requests
        response = await call_next(request)

        # Add CORS headers if origin is allowed
        if origin and self._is_origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"

            # Add exposed headers
            if self.exposed_headers:
                response.headers["Access-Control-Expose-Headers"] = ", ".join(self.exposed_headers)

        # Always add Vary: Origin header for proper caching
        existing_vary = response.headers.get("Vary", "")
        if existing_vary:
            if "Origin" not in existing_vary:
                response.headers["Vary"] = f"{existing_vary}, Origin"
        else:
            response.headers["Vary"] = "Origin"

        return response

    async def _handle_preflight(self, request: Request, origin: Optional[str]) -> Response:
        """Handle CORS preflight requests"""

        if not origin or not self._is_origin_allowed(origin):
            # Return 403 for disallowed origins
            return Response(content="CORS origin not allowed", status_code=403)

        # Build preflight response
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": ", ".join(self.allowed_methods),
            "Access-Control-Allow-Headers": ", ".join(self.allowed_headers),
            "Access-Control-Max-Age": str(self.max_age),
            "Vary": "Origin",
        }

        if self.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"

        # Check if requested method is allowed
        requested_method = request.headers.get("Access-Control-Request-Method")
        if requested_method and requested_method not in self.allowed_methods:
            return Response(content=f"Method {requested_method} not allowed", status_code=403)

        # Check if requested headers are allowed
        requested_headers = request.headers.get("Access-Control-Request-Headers")
        if requested_headers:
            for header in requested_headers.split(","):
                header = header.strip()
                if header.lower() not in [h.lower() for h in self.allowed_headers]:
                    logger.warning(f"Requested header not allowed: {header}")

        return Response(content="", status_code=204, headers=headers)

    async def _handle_websocket_cors(
        self, request: Request, call_next: Callable, origin: Optional[str]
    ) -> Response:
        """Handle CORS for WebSocket connections"""

        # Check if WebSocket origin is allowed
        if origin:
            # Convert ws:// to http:// and wss:// to https:// for comparison
            http_origin = origin.replace("ws://", "http://").replace("wss://", "https://")
            ws_origin = origin.replace("http://", "ws://").replace("https://", "wss://")

            if http_origin not in self.allowed_origins and ws_origin not in self.websocket_origins:
                logger.warning(f"WebSocket connection rejected from origin: {origin}")
                return Response(content="WebSocket origin not allowed", status_code=403)

        # Allow the WebSocket upgrade
        return await call_next(request)

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is in allowed list"""

        # In development, be more permissive
        if self.environment == SecurityEnvironment.DEVELOPMENT:
            if any(
                origin.startswith(prefix) for prefix in ["http://localhost", "http://127.0.0.1"]
            ):
                return True

        # Exact match for production
        return origin in self.allowed_origins


def setup_cors(app: ASGIApp, environment: Optional[SecurityEnvironment] = None) -> ASGIApp:
    """
    Setup CORS middleware with proper configuration

    Args:
        app: The ASGI application
        environment: Optional environment override

    Returns:
        The app with CORS middleware configured
    """
    security_settings = get_security_settings()
    env = environment or security_settings.environment

    if env == SecurityEnvironment.PRODUCTION:
        # Use our enhanced middleware in production
        app.add_middleware(EnhancedCORSMiddleware, environment=env)
        logger.info("Using enhanced CORS middleware for production")
    else:
        # Use FastAPI's built-in CORS for development/testing
        cors_config = security_settings.get_cors_config()
        app.add_middleware(
            FastAPICORSMiddleware,
            allow_origins=cors_config["allow_origins"],
            allow_methods=cors_config["allow_methods"],
            allow_headers=cors_config["allow_headers"],
            expose_headers=cors_config["expose_headers"],
            allow_credentials=cors_config["allow_credentials"],
            max_age=cors_config["max_age"],
        )
        logger.info(f"Using standard CORS middleware for {env}")

    return app
