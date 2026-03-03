"""
from __future__ import annotations
import logging


logger = logging.getLogger(__name__)
Monitoring middleware for FastAPI applications.
"""

import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .logger import get_logger, set_request_id, clear_request_id
from .metrics import track_request, get_metrics_collector

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to all requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID to request and response."""
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Set request ID in context
        set_request_id(request_id)

        # Store in request state
        request.state.request_id = request_id

        try:
            # Process request
            response = await call_next(request)

            # Add request ID to response
            response.headers["X-Request-ID"] = request_id

            return response
        finally:
            # Clear request ID from context
            clear_request_id()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response."""
        # Get request ID
        request_id = getattr(request.state, "request_id", "unknown")

        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            client=request.client.host if request.client else None,
            request_id=request_id,
        )

        # Track start time
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_seconds=duration,
                request_id=request_id,
            )

            # Add timing header
            response.headers["X-Response-Time"] = f"{duration:.3f}s"

            return response

        except Exception:
            # Calculate duration
            duration = time.time() - start_time

            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                method=request.method,
                path=request.url.path,
                duration_seconds=duration,
                request_id=request_id,
                exc_info=True,
            )

            raise


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Collect request metrics."""
        # Track start time
        start_time = time.time()

        # Get metrics collector
        collector = get_metrics_collector()

        # Increment active connections
        active_connections = collector.get_metric("active_connections")
        if active_connections:
            active_connections.increment()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Track request metrics
            track_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration=duration,
            )

            return response

        finally:
            # Decrement active connections
            if active_connections:
                active_connections.decrement()


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware for performance monitoring."""

    def __init__(self, app: ASGIApp, slow_request_threshold: float = 1.0) -> None:
        """Initialize performance middleware."""
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request performance."""
        start_time = time.time()

        # Track memory before request
        import psutil

        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB

        try:
            # Process request
            response = await call_next(request)

            # Calculate metrics
            duration = time.time() - start_time
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_delta = memory_after - memory_before

            # Log slow requests
            if duration > self.slow_request_threshold:
                logger.warning(
                    f"Slow request detected: {request.method} {request.url.path}",
                    method=request.method,
                    path=request.url.path,
                    duration_seconds=duration,
                    memory_delta_mb=memory_delta,
                    threshold_seconds=self.slow_request_threshold,
                )

            # Add performance headers
            response.headers["X-Process-Time"] = f"{duration:.3f}s"
            response.headers["X-Memory-Delta"] = f"{memory_delta:.2f}MB"

            return response

        except Exception:
            duration = time.time() - start_time
            logger.error(
                f"Request failed after {duration:.3f}s",
                method=request.method,
                path=request.url.path,
                duration_seconds=duration,
                exc_info=True,
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        # Add CSP header for HTML responses
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://api.openai.com https://*.supabase.co;"
            )

        return response


def setup_middleware(
    app: FastAPI,
    enable_cors: bool = True,
    enable_request_id: bool = True,
    enable_logging: bool = True,
    enable_metrics: bool = True,
    enable_performance: bool = True,
    enable_security_headers: bool = True,
    slow_request_threshold: float = 1.0,
) -> None:
    """
    Setup monitoring middleware for FastAPI app.

    Args:
        app: FastAPI application
        enable_cors: Enable CORS middleware
        enable_request_id: Enable request ID middleware
        enable_logging: Enable logging middleware
        enable_metrics: Enable metrics middleware
        enable_performance: Enable performance middleware
        enable_security_headers: Enable security headers middleware
        slow_request_threshold: Threshold for slow request warnings
    """
    # CORS middleware (should be first)
    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure based on environment
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "X-Response-Time", "X-Process-Time"],
        )

    # Security headers
    if enable_security_headers:
        app.add_middleware(SecurityHeadersMiddleware)

    # Performance monitoring
    if enable_performance:
        app.add_middleware(
            PerformanceMiddleware, slow_request_threshold=slow_request_threshold
        )

    # Metrics collection
    if enable_metrics:
        app.add_middleware(MetricsMiddleware)

    # Request/Response logging
    if enable_logging:
        app.add_middleware(LoggingMiddleware)

    # Request ID tracking (should be last to be first in chain)
    if enable_request_id:
        app.add_middleware(RequestIDMiddleware)

    logger.info("Monitoring middleware configured")
