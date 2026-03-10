"""Sentry integration for error tracking and performance monitoring."""

import os
from typing import Any, Dict, Optional, Generator
from contextlib import contextmanager
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
import logging
from .logger import get_logger

logger = get_logger(__name__)


class SentryConfig:
    """Sentry configuration."""

    def __init__(
        self,
        dsn: Optional[str] = None,
        environment: str = "development",
        release: Optional[str] = None,
        sample_rate: float = 1.0,
        traces_sample_rate: float = 0.1,
        profiles_sample_rate: float = 0.1,
        attach_stacktrace: bool = True,
        send_default_pii: bool = False,
        debug: bool = False,
    ) -> None:
        """Initialize Sentry configuration."""
        self.dsn = dsn or os.getenv("SENTRY_DSN")
        self.environment = environment or os.getenv("ENVIRONMENT", "development")
        self.release = release or os.getenv("RELEASE_VERSION")
        self.sample_rate = sample_rate
        self.traces_sample_rate = traces_sample_rate
        self.profiles_sample_rate = profiles_sample_rate
        self.attach_stacktrace = attach_stacktrace
        self.send_default_pii = send_default_pii
        self.debug = debug


def setup_sentry(config: Optional[SentryConfig] = None) -> bool:
    """
    Setup Sentry error tracking and performance monitoring.

    Args:
        config: Sentry configuration

    Returns:
        True if Sentry was initialized successfully
    """
    if not config:
        config = SentryConfig()
    if not config.dsn:
        logger.warning("Sentry DSN not configured, skipping Sentry initialization")
        return False
    try:
        integrations = [
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes=[400, 401, 403, 404, 405, 422, 429, 500, 502, 503, 504],
            ),
            SqlalchemyIntegration(),
            RedisIntegration(),
            AioHttpIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ]
        sentry_sdk.init(
            dsn=config.dsn,
            environment=config.environment,
            release=config.release,
            sample_rate=config.sample_rate,
            traces_sample_rate=config.traces_sample_rate,
            profiles_sample_rate=config.profiles_sample_rate,
            attach_stacktrace=config.attach_stacktrace,
            send_default_pii=config.send_default_pii,
            debug=config.debug,
            integrations=integrations,
            before_send=before_send_filter,
            before_send_transaction=before_send_transaction_filter,
        )
        sentry_sdk.set_tag("app", "ruleiq")
        sentry_sdk.set_tag("component", "backend")
        logger.info(f"Sentry initialized for environment: {config.environment}")
        return True
    except (OSError, requests.RequestException, KeyError) as e:
        logger.error(f"Failed to initialize Sentry: {str(e)}")
        return False


def before_send_filter(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Filter events before sending to Sentry.

    Args:
        event: The event dictionary
        hint: Additional information about the event

    Returns:
        The event or None to drop it
    """
    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]
        skip_exceptions = ["KeyboardInterrupt", "SystemExit", "GeneratorExit"]
        if exc_type.__name__ in skip_exceptions:
            return None
        if hasattr(exc_value, "status_code") and exc_value.status_code == 404:
            if "request" in event:
                url = event["request"].get("url", "")
                skip_paths = ["/favicon.ico", "/robots.txt", "/.well-known/"]
                if any((path in url for path in skip_paths)):
                    return None
    if "request" in event:
        if "headers" in event["request"]:
            sensitive_headers = ["authorization", "cookie", "x-api-key", "x-auth-token"]
            for header in sensitive_headers:
                if header in event["request"]["headers"]:
                    event["request"]["headers"][header] = "[REDACTED]"
        if "query_string" in event["request"]:
            sensitive_params = ["token", "api_key", "secret", "password"]
            query_string = event["request"]["query_string"]
            for param in sensitive_params:
                if param in query_string:
                    event["request"]["query_string"] = "[REDACTED]"
    return event


def before_send_transaction_filter(
    event: Dict[str, Any], hint: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Filter transactions before sending to Sentry.

    Args:
        event: The transaction event
        hint: Additional information

    Returns:
        The event or None to drop it
    """
    if "transaction" in event:
        skip_transactions = ["/health", "/healthz", "/ready", "/metrics"]
        if any((path in event["transaction"] for path in skip_transactions)):
            return None
    return event


def capture_exception(exception: Optional[Exception] = None, **kwargs) -> Optional[str]:
    """
    Capture an exception and send to Sentry.

    Args:
        exception: The exception to capture
        **kwargs: Additional context

    Returns:
        Event ID if sent successfully
    """
    try:
        with sentry_sdk.push_scope() as scope:
            for key, value in kwargs.items():
                scope.set_extra(key, value)
            event_id = sentry_sdk.capture_exception(exception)
            if event_id:
                logger.debug(f"Exception sent to Sentry: {event_id}")
            return event_id
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to send exception to Sentry: {str(e)}")
        return None


def capture_message(message: str, level: str = "info", **kwargs) -> Optional[str]:
    """
    Capture a message and send to Sentry.

    Args:
        message: The message to capture
        level: Log level (debug, info, warning, error, fatal)
        **kwargs: Additional context

    Returns:
        Event ID if sent successfully
    """
    try:
        with sentry_sdk.push_scope() as scope:
            for key, value in kwargs.items():
                scope.set_extra(key, value)
            event_id = sentry_sdk.capture_message(message, level=level)
            if event_id:
                logger.debug(f"Message sent to Sentry: {event_id}")
            return event_id
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to send message to Sentry: {str(e)}")
        return None


def set_user_context(
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    **kwargs,
) -> None:
    """
    Set user context for Sentry.

    Args:
        user_id: User ID
        username: Username
        email: User email
        ip_address: IP address
        **kwargs: Additional user data
    """
    user_data = {"id": user_id, "username": username, "email": email, "ip_address": ip_address}
    user_data.update(kwargs)
    user_data = {k: v for k, v in user_data.items() if v is not None}
    sentry_sdk.set_user(user_data)


def set_context(name: str, context: Dict[str, Any]) -> None:
    """
    Set additional context for Sentry.

    Args:
        name: Context name
        context: Context data
    """
    sentry_sdk.set_context(name, context)


def set_tag(key: str, value: str) -> None:
    """
    Set a tag for Sentry.

    Args:
        key: Tag key
        value: Tag value
    """
    sentry_sdk.set_tag(key, value)


def add_breadcrumb(
    message: str,
    category: Optional[str] = None,
    level: str = "info",
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Add a breadcrumb for Sentry.

    Args:
        message: Breadcrumb message
        category: Category (e.g., 'auth', 'database')
        level: Level (debug, info, warning, error, critical)
        data: Additional data
    """
    sentry_sdk.add_breadcrumb(message=message, category=category, level=level, data=data)


@contextmanager
def sentry_transaction(operation: str, name: str, **kwargs) -> Generator[Any, None, None]:
    """
    Context manager for Sentry transactions.

    Args:
        operation: Operation type (e.g., 'http', 'task')
        name: Transaction name
        **kwargs: Additional transaction data

    Yields:
        Transaction object
    """
    transaction = sentry_sdk.start_transaction(op=operation, name=name, **kwargs)
    try:
        with sentry_sdk.configure_scope() as scope:
            scope.set_span(transaction)
        yield transaction
    except (ValueError, TypeError):
        transaction.set_status("internal_error")
        raise
    else:
        transaction.set_status("ok")
    finally:
        transaction.finish()


@contextmanager
def sentry_span(operation: str, description: str) -> Generator[Any, None, None]:
    """
    Context manager for Sentry spans.

    Args:
        operation: Operation type
        description: Span description

    Yields:
        Span object
    """
    span = sentry_sdk.start_span(op=operation, description=description)
    try:
        yield span
    except (ValueError, TypeError):
        span.set_status("internal_error")
        raise
    else:
        span.set_status("ok")
    finally:
        span.finish()
