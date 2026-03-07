"""
import logging


logger = logging.getLogger(__name__)
Comprehensive error handling with custom exceptions and handlers.
"""

import traceback
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
import asyncio

from .logger import get_logger, set_request_id

logger = get_logger(__name__)


class ApplicationError(Exception):
    """Base application error."""

    def __init__(
        self,
        message: str,
        code: str = "APPLICATION_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize application error."""
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "timestamp": self.timestamp,
            }
        }

    def to_response(self) -> JSONResponse:
        """Convert error to JSON response."""
        return JSONResponse(status_code=self.status_code, content=self.to_dict())


class ValidationError(ApplicationError):
    """Validation error."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs) -> None:
        """Initialize validation error."""
        details = {"field": field} if field else {}
        details.update(kwargs.get("details", {}))
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AuthenticationError(ApplicationError):
    """Authentication error."""

    def __init__(self, message: str = "Authentication required", **kwargs) -> None:
        """Initialize authentication error."""
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
            **kwargs,
        )


class AuthorizationError(ApplicationError):
    """Authorization error."""

    def __init__(self, message: str = "Insufficient permissions", **kwargs) -> None:
        """Initialize authorization error."""
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN,
            **kwargs,
        )


class NotFoundError(ApplicationError):
    """Resource not found error."""

    def __init__(self, resource: str, identifier: Any = None, **kwargs) -> None:
        """Initialize not found error."""
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"

        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={
                "resource": resource,
                "identifier": str(identifier) if identifier else None,
            },
            **kwargs,
        )


class ConflictError(ApplicationError):
    """Resource conflict error."""

    def __init__(self, message: str, **kwargs) -> None:
        """Initialize conflict error."""
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            **kwargs,
        )


class RateLimitError(ApplicationError):
    """Rate limit exceeded error."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs,
    ) -> None:
        """Initialize rate limit error."""
        details = {"retry_after": retry_after} if retry_after else {}
        details.update(kwargs.get("details", {}))
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class ExternalServiceError(ApplicationError):
    """External service error."""

    def __init__(self, service: str, message: str, **kwargs) -> None:
        """Initialize external service error."""
        super().__init__(
            message=f"External service error ({service}): {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"service": service},
            **kwargs,
        )


class ErrorHandler:
    """Error handler with context management."""

    def __init__(self) -> None:
        """Initialize error handler."""
        self.error_callbacks = []
        self.context = {}

    def add_context(self, **kwargs) -> None:
        """Add context information."""
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """Clear context information."""
        self.context.clear()

    def register_callback(self, callback: Callable[[Exception, Dict], None]) -> None:
        """Register error callback."""
        self.error_callbacks.append(callback)

    async def handle_error(
        self, error: Exception, request: Optional[Request] = None
    ) -> JSONResponse:
        """Handle error with logging and callbacks."""
        # Set request ID if available
        if request:
            request_id = request.headers.get("X-Request-ID", None)
            if request_id:
                set_request_id(request_id)

        # Build error context
        error_context = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            **self.context,
        }

        if request:
            error_context.update(
                {
                    "method": request.method,
                    "url": str(request.url),
                    "client": request.client.host if request.client else None,
                    "headers": dict(request.headers),
                }
            )

        # Log error
        if isinstance(error, ApplicationError):
            if error.status_code >= 500:
                logger.error(f"Application error: {error.message}", **error_context)
            else:
                logger.warning(f"Application error: {error.message}", **error_context)
        else:
            logger.error(f"Unhandled error: {str(error)}", exc_info=True, **error_context)

        # Execute callbacks
        for callback in self.error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error, error_context)
                else:
                    callback(error, error_context)
            except Exception as cb_error:
                logger.error(f"Error in error callback: {str(cb_error)}", exc_info=True)

        # Return response
        if isinstance(error, ApplicationError):
            return error.to_response()
        else:
            # Generic error response for unhandled exceptions
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An internal server error occurred",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )


class GlobalErrorHandler:
    """Global error handler for FastAPI."""

    def __init__(self, app: FastAPI) -> None:
        """Initialize global error handler."""
        self.app = app
        self.handler = ErrorHandler()
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register exception handlers."""
        # Application errors
        self.app.add_exception_handler(ApplicationError, self._handle_application_error)

        # Validation errors
        self.app.add_exception_handler(RequestValidationError, self._handle_validation_error)

        # HTTP exceptions
        self.app.add_exception_handler(StarletteHTTPException, self._handle_http_exception)

        # Database errors
        self.app.add_exception_handler(SQLAlchemyError, self._handle_database_error)

        # Generic exceptions
        self.app.add_exception_handler(Exception, self._handle_generic_error)

    async def _handle_application_error(
        self, request: Request, error: ApplicationError
    ) -> JSONResponse:
        """Handle application errors."""
        return await self.handler.handle_error(error, request)

    async def _handle_validation_error(
        self, request: Request, error: RequestValidationError
    ) -> JSONResponse:
        """Handle validation errors."""
        validation_error = ValidationError(
            message="Request validation failed", details={"errors": error.errors()}
        )
        return await self.handler.handle_error(validation_error, request)

    async def _handle_http_exception(
        self, request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        """Handle HTTP exceptions."""
        app_error = ApplicationError(
            message=error.detail, code="HTTP_ERROR", status_code=error.status_code
        )
        return await self.handler.handle_error(app_error, request)

    async def _handle_database_error(
        self, request: Request, error: SQLAlchemyError
    ) -> JSONResponse:
        """Handle database errors."""
        db_error = ApplicationError(
            message="Database operation failed",
            code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"db_error": str(error)},
        )
        return await self.handler.handle_error(db_error, request)

    async def _handle_generic_error(self, request: Request, error: Exception) -> JSONResponse:
        """Handle generic errors."""
        return await self.handler.handle_error(error, request)


def setup_error_handling(app: FastAPI) -> GlobalErrorHandler:
    """Setup global error handling for FastAPI app."""
    return GlobalErrorHandler(app)


async def custom_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Custom exception handler for middleware."""
    handler = ErrorHandler()
    return await handler.handle_error(exc, request)
