"""
Security Headers Middleware for comprehensive HTTP header security
"""

from typing import Optional, Dict, List, Any
from fastapi import Request, Response
from starlette.datastructures import MutableHeaders
from fastapi.responses import JSONResponse
import secrets
from datetime import datetime, timezone


class SecurityHeadersMiddleware:
    """Middleware to add comprehensive security headers to all responses"""

    def __init__(
        self,
        app,
        csp_enabled: bool = True,
        cors_enabled: bool = True,
        custom_csp: Optional[str] = None,
        nonce_enabled: bool = True,
        report_uri: Optional[str] = None,
    ) -> None:
        """
        Initialize security headers middleware

        Args:
            app: FastAPI application instance
            csp_enabled: Enable Content Security Policy
            cors_enabled: Enable CORS headers
            custom_csp: Custom CSP directive string
            nonce_enabled: Generate CSP nonces for inline scripts
            report_uri: URI for CSP violation reports
        """
        self.app = app
        self.csp_enabled = csp_enabled
        self.cors_enabled = cors_enabled
        self.custom_csp = custom_csp
        self.nonce_enabled = nonce_enabled
        self.report_uri = report_uri

        # Default CSP directives
        self.default_csp = {
            "default-src": ["'self'"],
            "script-src": [
                "'self'",
                "'unsafe-inline'" if not nonce_enabled else "'nonce-{nonce}'",
            ],
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:", "https:"],
            "font-src": ["'self'", "data:"],
            "connect-src": ["'self'"],
            "media-src": ["'self'"],
            "object-src": ["'none'"],
            "frame-src": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "frame-ancestors": ["'none'"],
            "upgrade-insecure-requests": [],
        }

        # CORS configuration
        self.cors_config = {
            "allowed_origins": ["https://app.ruleiq.com"],
            "allowed_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allowed_headers": ["Content-Type", "Authorization", "X-Request-ID"],
            "max_age": 86400,
            "allow_credentials": True,
        }

    async def __call__(self, scope, receive, send):
        """
        ASGI middleware interface

        Args:
            scope: ASGI connection scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create request object
        request = Request(scope, receive=receive)

        # Generate CSP nonce if enabled
        nonce = None
        if self.nonce_enabled and self.csp_enabled:
            nonce = self._generate_nonce()
            request.state.csp_nonce = nonce

        # Store the response status for other middleware
        response_status = None

        async def send_wrapper(message):
            """Wrapper to add headers to response"""
            nonlocal response_status

            if message["type"] == "http.response.start":
                # Store status code
                response_status = message.get("status", 200)

                headers = MutableHeaders(scope=message)

                # Create a mock response object for header manipulation
                class HeaderResponse:
                    def __init__(self) -> None:
                        self.headers = headers
                        self.status_code = response_status

                response = HeaderResponse()

                # Add security headers
                self._add_basic_security_headers(response)

                if self.csp_enabled:
                    self._add_csp_header(response, nonce)

                if self.cors_enabled:
                    self._add_cors_headers(request, response)

                # Add additional security headers
                self._add_advanced_security_headers(response)

            await send(message)

        # Call the next app with wrapped send
        await self.app(scope, receive, send_wrapper)

    def _add_basic_security_headers(self, response: Response) -> None:
        """Add basic security headers"""
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS (HTTP Strict Transport Security)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

    def _add_csp_header(self, response: Response, nonce: Optional[str] = None) -> None:
        """
        Add Content Security Policy header

        Args:
            response: HTTP response
            nonce: CSP nonce for inline scripts
        """
        if self.custom_csp:
            csp_header = self.custom_csp
        else:
            csp_directives = []
            for directive, values in self.default_csp.items():
                if values:
                    # Replace nonce placeholder if present
                    processed_values = []
                    for value in values:
                        if "{nonce}" in value and nonce:
                            processed_values.append(value.format(nonce=nonce))
                        else:
                            processed_values.append(value)
                    csp_directives.append(f"{directive} {' '.join(processed_values)}")
                else:
                    csp_directives.append(directive)

            # Add report URI if configured
            if self.report_uri:
                csp_directives.append(f"report-uri {self.report_uri}")

            csp_header = "; ".join(csp_directives)

        response.headers["Content-Security-Policy"] = csp_header

    def _add_cors_headers(self, request: Request, response: Response) -> None:
        """
        Add CORS headers based on configuration

        Args:
            request: HTTP request
            response: HTTP response
        """
        origin = request.headers.get("Origin")

        # Check if origin is allowed
        if (
            origin in self.cors_config["allowed_origins"]
            or "*" in self.cors_config["allowed_origins"]
        ):
            response.headers["Access-Control-Allow-Origin"] = origin or "*"

        # Add other CORS headers
        response.headers["Access-Control-Allow-Methods"] = ", ".join(
            self.cors_config["allowed_methods"]
        )
        response.headers["Access-Control-Allow-Headers"] = ", ".join(
            self.cors_config["allowed_headers"]
        )
        response.headers["Access-Control-Max-Age"] = str(self.cors_config["max_age"])

        if self.cors_config["allow_credentials"]:
            response.headers["Access-Control-Allow-Credentials"] = "true"

        # Handle preflight requests
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
            response.status_code = 204

    def _add_advanced_security_headers(self, response: Response) -> None:
        """Add advanced security headers"""
        # Expect-CT for Certificate Transparency
        response.headers["Expect-CT"] = "max-age=86400, enforce"

        # Cross-Origin headers
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # Cache control for sensitive content
        if response.status_code == 200:
            # Don't cache sensitive data
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

    def _generate_nonce(self) -> str:
        """Generate a secure CSP nonce"""
        return secrets.token_urlsafe(16)

    def update_csp_directive(self, directive: str, values: List[str]) -> None:
        """
        Update a specific CSP directive

        Args:
            directive: CSP directive name
            values: List of values for the directive
        """
        self.default_csp[directive] = values

    def add_allowed_origin(self, origin: str) -> None:
        """
        Add an allowed CORS origin

        Args:
            origin: Origin URL to allow
        """
        if origin not in self.cors_config["allowed_origins"]:
            self.cors_config["allowed_origins"].append(origin)

    def remove_allowed_origin(self, origin: str) -> None:
        """
        Remove an allowed CORS origin

        Args:
            origin: Origin URL to remove
        """
        if origin in self.cors_config["allowed_origins"]:
            self.cors_config["allowed_origins"].remove(origin)

    def get_security_report(self) -> Dict[str, Any]:
        """
        Get a report of current security header configuration

        Returns:
            Dictionary with security configuration details
        """
        return {
            "csp_enabled": self.csp_enabled,
            "cors_enabled": self.cors_enabled,
            "nonce_enabled": self.nonce_enabled,
            "csp_directives": self.default_csp,
            "cors_config": self.cors_config,
            "report_uri": self.report_uri,
        }


class CSPViolationHandler:
    """Handler for CSP violation reports"""

    def __init__(self, storage_backend: Optional[Any] = None) -> None:
        """
        Initialize CSP violation handler

        Args:
            storage_backend: Optional storage backend for violations
        """
        self.storage_backend = storage_backend
        self.violations: List[Dict[str, Any]] = []

    async def handle_violation(self, request: Request) -> JSONResponse:
        """
        Handle CSP violation report

        Args:
            request: HTTP request containing violation report

        Returns:
            JSON response acknowledging receipt
        """
        try:
            # Parse violation report
            violation_data = await request.json()

            # Extract CSP report
            csp_report = violation_data.get("csp-report", {})

            # Create violation record
            violation = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "document_uri": csp_report.get("document-uri"),
                "blocked_uri": csp_report.get("blocked-uri"),
                "violated_directive": csp_report.get("violated-directive"),
                "effective_directive": csp_report.get("effective-directive"),
                "original_policy": csp_report.get("original-policy"),
                "disposition": csp_report.get("disposition"),
                "script_sample": csp_report.get("script-sample"),
                "status_code": csp_report.get("status-code"),
                "referrer": csp_report.get("referrer"),
                "source_file": csp_report.get("source-file"),
                "line_number": csp_report.get("line-number"),
                "column_number": csp_report.get("column-number"),
            }

            # Store violation
            self.violations.append(violation)

            # Persist if storage backend available
            if self.storage_backend:
                await self._persist_violation(violation)

            # Log violation
            self._log_violation(violation)

            return JSONResponse(status_code=204, content={"status": "received"})

        except Exception as e:
            return JSONResponse(status_code=400, content={"error": str(e)})

    async def _persist_violation(self, violation: Dict[str, Any]) -> None:
        """Persist violation to storage backend"""
        if self.storage_backend:
            # Implementation depends on storage backend
            pass

    def _log_violation(self, violation: Dict[str, Any]) -> None:
        """Log CSP violation for monitoring"""
        import logging

        logger = logging.getLogger(__name__)

        logger.warning(
            f"CSP Violation: {violation['violated_directive']} - "
            f"Blocked: {violation['blocked_uri']} - "
            f"Document: {violation['document_uri']}"
        )

    def get_violations_summary(self) -> Dict[str, Any]:
        """
        Get summary of CSP violations

        Returns:
            Dictionary with violation statistics
        """
        if not self.violations:
            return {"total": 0, "violations": []}

        # Group by directive
        by_directive = {}
        for violation in self.violations:
            directive = violation.get("violated_directive", "unknown")
            if directive not in by_directive:
                by_directive[directive] = 0
            by_directive[directive] += 1

        # Group by blocked URI
        by_blocked = {}
        for violation in self.violations:
            blocked = violation.get("blocked_uri", "unknown")
            if blocked not in by_blocked:
                by_blocked[blocked] = 0
            by_blocked[blocked] += 1

        return {
            "total": len(self.violations),
            "by_directive": by_directive,
            "by_blocked_uri": by_blocked,
            "recent": (self.violations[-10:] if len(self.violations) > 10 else self.violations),
        }


def create_security_headers_middleware(
    app, config: Optional[Dict[str, Any]] = None
) -> SecurityHeadersMiddleware:
    """
    Factory function to create configured security headers middleware

    Args:
        app: FastAPI application
        config: Optional configuration dictionary

    Returns:
        Configured SecurityHeadersMiddleware instance
    """
    config = config or {}

    return SecurityHeadersMiddleware(
        app=app,
        csp_enabled=config.get("csp_enabled", True),
        cors_enabled=config.get("cors_enabled", True),
        custom_csp=config.get("custom_csp"),
        nonce_enabled=config.get("nonce_enabled", True),
        report_uri=config.get("report_uri"),
    )
