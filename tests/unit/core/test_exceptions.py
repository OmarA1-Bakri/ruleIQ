"""
Unit tests for core/exceptions.py — Custom exception hierarchy.

Tests exception classes, status codes, messages, and inheritance.
"""

import os
import pytest

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from core.exceptions import (
    ApplicationException,
    DatabaseException,
    NotFoundException,
    DuplicateEntryException,
    NotAuthenticatedException,
    BusinessLogicException,
    ValidationException,
    AuthorizationException,
    IntegrationException,
    AIException,
    APIError,
    ValidationAPIError,
    NotFoundAPIError,
)


# ---------------------------------------------------------------------------
# ApplicationException (base)
# ---------------------------------------------------------------------------

class TestApplicationException:
    """Tests for the base ApplicationException."""

    def test_default_status_code(self):
        exc = ApplicationException("Something went wrong")
        assert exc.status_code == 500
        assert exc.message == "Something went wrong"

    def test_custom_status_code(self):
        exc = ApplicationException("Bad request", status_code=400)
        assert exc.status_code == 400

    def test_str_representation(self):
        exc = ApplicationException("error message")
        assert str(exc) == "error message"

    def test_inherits_from_exception(self):
        assert issubclass(ApplicationException, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ApplicationException) as exc_info:
            raise ApplicationException("test")
        assert exc_info.value.message == "test"


# ---------------------------------------------------------------------------
# Database exceptions
# ---------------------------------------------------------------------------

class TestDatabaseException:
    """Tests for DatabaseException."""

    def test_default_message(self):
        exc = DatabaseException()
        assert exc.message == "A database error occurred."
        assert exc.status_code == 500

    def test_custom_message(self):
        exc = DatabaseException("Connection failed")
        assert exc.message == "Connection failed"

    def test_inherits_from_application(self):
        assert issubclass(DatabaseException, ApplicationException)


class TestNotFoundException:
    """Tests for NotFoundException."""

    def test_message_format(self):
        exc = NotFoundException("User", "abc-123")
        assert "User" in exc.message
        assert "abc-123" in exc.message
        assert exc.status_code == 404

    def test_inherits_from_database(self):
        assert issubclass(NotFoundException, DatabaseException)


class TestDuplicateEntryException:
    """Tests for DuplicateEntryException."""

    def test_message_format(self):
        exc = DuplicateEntryException("User", "email")
        assert "User" in exc.message
        assert "email" in exc.message
        assert exc.status_code == 409

    def test_inherits_from_database(self):
        assert issubclass(DuplicateEntryException, DatabaseException)


# ---------------------------------------------------------------------------
# Authentication exceptions
# ---------------------------------------------------------------------------

class TestNotAuthenticatedException:
    """Tests for NotAuthenticatedException."""

    def test_default_message(self):
        exc = NotAuthenticatedException()
        assert "credentials" in exc.message.lower()
        assert exc.status_code == 401

    def test_custom_message(self):
        exc = NotAuthenticatedException("Token expired")
        assert exc.message == "Token expired"
        assert exc.status_code == 401

    def test_inherits_from_application(self):
        assert issubclass(NotAuthenticatedException, ApplicationException)


# ---------------------------------------------------------------------------
# Business logic exceptions
# ---------------------------------------------------------------------------

class TestBusinessLogicException:
    """Tests for BusinessLogicException."""

    def test_default_status_code(self):
        exc = BusinessLogicException("Invalid operation")
        assert exc.status_code == 400

    def test_inherits_from_application(self):
        assert issubclass(BusinessLogicException, ApplicationException)


class TestValidationException:
    """Tests for ValidationException."""

    def test_default_message(self):
        exc = ValidationException()
        assert exc.status_code == 422

    def test_custom_message(self):
        exc = ValidationException("Field X is invalid")
        assert exc.message == "Field X is invalid"

    def test_inherits_from_business_logic(self):
        assert issubclass(ValidationException, BusinessLogicException)


class TestAuthorizationException:
    """Tests for AuthorizationException."""

    def test_default_message(self):
        exc = AuthorizationException()
        assert "permission" in exc.message.lower()
        assert exc.status_code == 403

    def test_inherits_from_business_logic(self):
        assert issubclass(AuthorizationException, BusinessLogicException)


# ---------------------------------------------------------------------------
# Integration exceptions
# ---------------------------------------------------------------------------

class TestIntegrationException:
    """Tests for IntegrationException."""

    def test_message_includes_provider(self):
        exc = IntegrationException("Stripe", "Payment failed")
        assert "[Stripe]" in exc.message
        assert "Payment failed" in exc.message
        assert exc.status_code == 502

    def test_inherits_from_application(self):
        assert issubclass(IntegrationException, ApplicationException)


class TestAIException:
    """Tests for AIException."""

    def test_default_message(self):
        exc = AIException()
        assert "AI" in exc.message
        assert exc.status_code == 503

    def test_custom_message(self):
        exc = AIException("Model timeout")
        assert exc.message == "Model timeout"

    def test_inherits_from_application(self):
        assert issubclass(AIException, ApplicationException)


# ---------------------------------------------------------------------------
# API exceptions
# ---------------------------------------------------------------------------

class TestAPIError:
    """Tests for APIError."""

    def test_default(self):
        exc = APIError()
        assert exc.status_code == 500

    def test_custom(self):
        exc = APIError("Rate limited", status_code=429)
        assert exc.status_code == 429

    def test_inherits_from_application(self):
        assert issubclass(APIError, ApplicationException)


class TestValidationAPIError:
    """Tests for ValidationAPIError."""

    def test_status_code(self):
        exc = ValidationAPIError()
        assert exc.status_code == 422

    def test_details(self):
        exc = ValidationAPIError("Bad input", details={"field": "name"})
        assert exc.details == {"field": "name"}

    def test_inherits_from_api_error(self):
        assert issubclass(ValidationAPIError, APIError)


class TestNotFoundAPIError:
    """Tests for NotFoundAPIError."""

    def test_message_format(self):
        exc = NotFoundAPIError("Assessment", "xyz-789")
        assert "Assessment" in exc.message
        assert "xyz-789" in exc.message
        assert exc.status_code == 404

    def test_inherits_from_api_error(self):
        assert issubclass(NotFoundAPIError, APIError)
