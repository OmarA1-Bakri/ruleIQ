"""Comprehensive error handling utilities for ruleIQ API."""
import logging
import traceback
from typing import Dict, Any, Optional, List, NoReturn
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
logger = logging.getLogger(__name__)


class RuleIQException(Exception):
    """Base exception class for ruleIQ application."""

    def __init__(self, message: str, error_code: str='GENERAL_ERROR',
        status_code: int=500, details: Optional[Dict[str, Any]]=None) ->None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class ValidationException(RuleIQException):
    """Exception for validation errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]]=None
        ) ->None:
        super().__init__(message=message, error_code='VALIDATION_ERROR',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details)


class AuthenticationException(RuleIQException):
    """Exception for authentication errors."""

    def __init__(self, message: str='Authentication required') ->None:
        super().__init__(message=message, error_code='AUTHENTICATION_ERROR',
            status_code=status.HTTP_401_UNAUTHORIZED)


class AuthorizationException(RuleIQException):
    """Exception for authorization errors."""

    def __init__(self, message: str='Access denied') ->None:
        super().__init__(message=message, error_code='AUTHORIZATION_ERROR',
            status_code=status.HTTP_403_FORBIDDEN)


class ResourceNotFoundException(RuleIQException):
    """Exception for resource not found errors."""

    def __init__(self, resource: str, identifier: Optional[str]=None) ->None:
        message = f'{resource} not found'
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(message=message, error_code='RESOURCE_NOT_FOUND',
            status_code=status.HTTP_404_NOT_FOUND, details={'resource':
            resource, 'identifier': identifier})


class DatabaseException(RuleIQException):
    """Exception for database-related errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]]=None
        ) ->None:
        super().__init__(message=message, error_code='DATABASE_ERROR',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, details=details)


class IntegrationException(RuleIQException):
    """Exception for third-party integration errors."""

    def __init__(self, service: str, message: str, details: Optional[Dict[
        str, Any]]=None) ->None:
        super().__init__(message=
            f'Integration error with {service}: {message}', error_code=
            'INTEGRATION_ERROR', status_code=status.HTTP_502_BAD_GATEWAY,
            details={'service': service, **(details or {})})


class RateLimitException(RuleIQException):
    """Exception for rate limiting errors."""

    def __init__(self, retry_after: Optional[int]=None) ->None:
        details = {}
        if retry_after:
            details['retry_after'] = retry_after
        super().__init__(message='Rate limit exceeded', error_code=
            'RATE_LIMIT_EXCEEDED', status_code=status.
            HTTP_429_TOO_MANY_REQUESTS, details=details)


class SecurityException(RuleIQException):
    """Exception for security-related errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]]=None
        ) ->None:
        super().__init__(message=message, error_code='SECURITY_ERROR',
            status_code=status.HTTP_403_FORBIDDEN, details=details)


class ErrorHandler:
    """Centralized error handling for the application."""

    @staticmethod
    def create_error_response(exception: Exception, request: Optional[
        Request]=None) ->Dict[str, Any]:
        """Create a standardized error response."""
        if isinstance(exception, RuleIQException):
            return {'error': {'code': exception.error_code, 'message':
                exception.message, 'status_code': exception.status_code,
                'details': exception.details}}
        elif isinstance(exception, ValidationError):
            return {'error': {'code': 'VALIDATION_ERROR', 'message':
                'Invalid request data', 'status_code': status.
                HTTP_422_UNPROCESSABLE_ENTITY, 'details': {
                'validation_errors': exception.errors()}}}
        elif isinstance(exception, HTTPException):
            return {'error': {'code': 'HTTP_ERROR', 'message': exception.
                detail, 'status_code': exception.status_code, 'details': {}}}
        else:
            logger.error('Unexpected error: %s' % str(exception), extra={
                'error': str(exception), 'traceback': traceback.format_exc(
                ), 'request_path': request.url.path if request else None,
                'request_method': request.method if request else None})
            return {'error': {'code': 'INTERNAL_SERVER_ERROR', 'message':
                'An unexpected error occurred', 'status_code': status.
                HTTP_500_INTERNAL_SERVER_ERROR, 'details': {}}}

    @staticmethod
    def log_error(exception: Exception, request: Optional[Request]=None,
        user_id: Optional[str]=None) ->None:
        """Log error with context."""
        log_data = {'error_type': type(exception).__name__, 'error_message':
            str(exception), 'user_id': user_id, 'request_path': request.url
            .path if request else None, 'request_method': request.method if
            request else None, 'user_agent': request.headers.get(
            'user-agent') if request else None, 'ip_address': request.
            client.host if request else None}
        if isinstance(exception, RuleIQException):
            log_data.update({'error_code': exception.error_code, 'details':
                exception.details})
        logger.error('Application error: %s' % str(exception), extra=
            log_data, exc_info=True)

    @staticmethod
    def sanitize_error_details(details: Dict[str, Any]) ->Dict[str, Any]:
        """Sanitize error details to prevent information leakage."""
        sensitive_keys = ['password', 'token', 'secret', 'key',
            'credential', 'auth', 'private', 'sensitive', 'confidential']

        def sanitize_dict(data: Dict[str, Any]) ->Dict[str, Any]:
            sanitized = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys
                    ):
                    sanitized[key] = '[REDACTED]'
                elif isinstance(value, dict):
                    sanitized[key] = sanitize_dict(value)
                elif isinstance(value, list):
                    sanitized[key] = [(sanitize_dict(item) if isinstance(
                        item, dict) else item) for item in value]
                else:
                    sanitized[key] = value
            return sanitized
        return sanitize_dict(details)


async def global_exception_handler(request: Request, exception: Exception
    ) ->JSONResponse:
    """Global exception handler for FastAPI."""
    user_id = getattr(request.state, 'user_id', None)
    ErrorHandler.log_error(exception, request, user_id)
    error_response = ErrorHandler.create_error_response(exception, request)
    if 'details' in error_response['error']:
        error_response['error']['details'
            ] = ErrorHandler.sanitize_error_details(error_response['error']
            ['details'])
    status_code = error_response['error']['status_code']
    return JSONResponse(status_code=status_code, content=error_response)


class ValidationUtils:
    """Utility functions for validation and error handling."""

    @staticmethod
    def validate_uuid(uuid_str: str, field_name: str='id') ->str:
        """Validate and return UUID string."""
        import uuid
        try:
            return str(uuid.UUID(uuid_str))
        except ValueError:
            raise ValidationException(f'Invalid {field_name} format',
                details={'field': field_name, 'value': uuid_str})

    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields:
        List[str]) ->None:
        """Validate that required fields are present."""
        missing_fields = [field for field in required_fields if field not in
            data or data[field] is None or data[field] == '']
        if missing_fields:
            raise ValidationException('Missing required fields', details={
                'missing_fields': missing_fields})

    @staticmethod
    def validate_enum_value(value: str, valid_values: List[str], field_name:
        str) ->str:
        """Validate that value is in allowed enum values."""
        if value not in valid_values:
            raise ValidationException(f'Invalid {field_name} value',
                details={'field': field_name, 'value': value,
                'allowed_values': valid_values})
        return value


class SecurityErrorHandler:
    """Security-focused error handling."""

    @staticmethod
    def handle_authentication_error(details: Optional[Dict[str, Any]]=None
        ) ->NoReturn:
        """Handle authentication errors securely."""
        logger.warning('Authentication attempt failed', extra={'details':
            ErrorHandler.sanitize_error_details(details or {})})
        raise AuthenticationException()

    @staticmethod
    def handle_authorization_error(resource: str, action: str, user_id:
        Optional[str]=None) ->NoReturn:
        """Handle authorization errors securely."""
        logger.warning('Authorization attempt failed', extra={'resource':
            resource, 'action': action, 'user_id': user_id})
        raise AuthorizationException(f'Access denied to {resource}')

    @staticmethod
    def handle_rate_limit_error(retry_after: Optional[int]=None) ->NoReturn:
        """Handle rate limiting errors."""
        logger.warning('Rate limit exceeded', extra={'retry_after':
            retry_after})
        raise RateLimitException(retry_after)


ERROR_TEMPLATES = {'DATABASE_CONNECTION_FAILED': {'code':
    'DATABASE_CONNECTION_FAILED', 'message':
    'Unable to connect to the database', 'status_code': status.
    HTTP_503_SERVICE_UNAVAILABLE}, 'EXTERNAL_SERVICE_UNAVAILABLE': {'code':
    'EXTERNAL_SERVICE_UNAVAILABLE', 'message':
    'External service is temporarily unavailable', 'status_code': status.
    HTTP_503_SERVICE_UNAVAILABLE}, 'INVALID_CREDENTIALS': {'code':
    'INVALID_CREDENTIALS', 'message': 'Invalid authentication credentials',
    'status_code': status.HTTP_401_UNAUTHORIZED}, 'RESOURCE_CONFLICT': {
    'code': 'RESOURCE_CONFLICT', 'message': 'Resource conflict detected',
    'status_code': status.HTTP_409_CONFLICT}}


def create_error_template(code: str, message: str, status_code: int,
    details: Optional[Dict[str, Any]]=None) ->RuleIQException:
    """Create error from template."""
    template = ERROR_TEMPLATES.get(code)
    if template:
        return RuleIQException(message=template['message'], error_code=
            template['code'], status_code=template['status_code'], details=
            details)
    return RuleIQException(message=message, error_code=code, status_code=
        status_code, details=details)
