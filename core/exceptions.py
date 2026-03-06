"""

Defines the custom exception hierarchy for the application.

This module provides a structured way to handle application-specific errors,
ensuring that exceptions are meaningful and can be handled gracefully by the
application's error handlers.
"""

from typing import Optional


class ApplicationException(Exception):
    """Base class for all custom exceptions in this application."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# --- Database and ORM Exceptions ---


class DatabaseException(ApplicationException):
    """Raised for general database-related errors."""

    def __init__(self, message: str = "A database error occurred.", status_code: int = 500) -> None:
        super().__init__(message, status_code)


class NotFoundException(DatabaseException):
    """Raised when a specific database record is not found."""

    def __init__(self, entity_name: str, entity_id: any) -> None:
        message = f"{entity_name} with ID '{entity_id}' not found."
        super().__init__(message, status_code=404)


class DuplicateEntryException(DatabaseException):
    """Raised when a unique constraint is violated."""

    def __init__(self, entity_name: str, conflicting_field: str) -> None:
        message = f"A {entity_name} with that {conflicting_field} already exists."
        super().__init__(message, status_code=409)


# --- Authentication and Authorization Exceptions ---


class NotAuthenticatedException(ApplicationException):
    """Raised when a user is not authenticated for a required action."""

    def __init__(self, message: str = "Could not validate credentials") -> None:
        super().__init__(message, status_code=401)


# --- Business Logic and Service Exceptions ---


class BusinessLogicException(ApplicationException):
    """Raised for errors in business logic or service layers."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message, status_code)


class ValidationException(BusinessLogicException):
    """Raised for input validation errors."""

    def __init__(self, message: str = "Invalid input provided.") -> None:
        super().__init__(message, status_code=422)


class AuthorizationException(BusinessLogicException):
    """Raised for authorization or permission errors."""

    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(message, status_code=403)


# --- Integration and External Service Exceptions ---


class IntegrationException(ApplicationException):
    """Raised for errors related to third-party integrations."""

    def __init__(
        self,
        provider: str,
        message: str = "An error occurred with an external service.",
    ) -> None:
        full_message = f"[{provider}] {message}"
        super().__init__(full_message, status_code=502)


class AIException(ApplicationException):
    """Raised for errors related to AI model interactions."""

    def __init__(
        self,
        message: str = "An error occurred while communicating with the AI service.",
    ) -> None:
        super().__init__(message, status_code=503)


# --- API Specific Exceptions ---


class APIError(ApplicationException):
    """Base class for API related errors."""

    def __init__(self, message: str = "An API error occurred.", status_code: int = 500) -> None:
        super().__init__(message, status_code)


class ValidationAPIError(APIError):
    """Raised for API input validation errors."""

    def __init__(
        self,
        message: str = "Invalid input provided to API.",
        details: Optional[any] = None,
    ) -> None:
        super().__init__(message, status_code=422)
        self.details = details


class NotFoundAPIError(APIError):
    """Raised when a resource is not found via an API endpoint."""

    def __init__(self, entity_name: str, entity_id: any) -> None:
        message = f"{entity_name} with ID '{entity_id}' not found via API."
        super().__init__(message, status_code=404)
