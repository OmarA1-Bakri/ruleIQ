"""

Sentry Integration for Proactive Monitoring

This module initializes the Sentry SDK to capture errors and performance data.
"""

import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from config.settings import settings

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    """Initialize the Sentry SDK."""
    if not settings.sentry_dsn:
        logger.warning("SENTRY_DSN not found, Sentry monitoring is disabled.")
        return

    try:
        sentry_logging = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR,  # Send errors as events
        )

        def before_send(event, hint):
            """Filter sensitive data before sending to Sentry."""
            # List of sensitive keys to filter
            sensitive_keys = [
                "password",
                "passwd",
                "pwd",
                "secret",
                "token",
                "api_key",
                "apikey",
                "auth",
                "authorization",
                "private_key",
                "privatekey",
                "access_token",
                "refresh_token",
                "bearer",
                "jwt",
                "session",
                "cookie",
                "csrf",
                "credit_card",
                "card_number",
                "cvv",
                "ssn",
            ]

            # Recursively filter sensitive data from the event
            def filter_dict(data):
                if isinstance(data, dict):
                    return {
                        k: "[FILTERED]"
                        if any(s in k.lower() for s in sensitive_keys)
                        else filter_dict(v)
                        for k, v in data.items()
                    }
                elif isinstance(data, list):
                    return [filter_dict(item) for item in data]
                elif isinstance(data, str):
                    # Filter URLs with potential secrets
                    if "http" in data and any(s in data.lower() for s in sensitive_keys):
                        return "[FILTERED_URL]"
                return data

            # Apply filtering to various event data
            if "extra" in event:
                event["extra"] = filter_dict(event["extra"])
            if "contexts" in event:
                event["contexts"] = filter_dict(event["contexts"])
            if "request" in event:
                if "data" in event["request"]:
                    event["request"]["data"] = filter_dict(event["request"]["data"])
                if "headers" in event["request"]:
                    event["request"]["headers"] = filter_dict(event["request"]["headers"])
                if "cookies" in event["request"]:
                    event["request"]["cookies"] = filter_dict(event["request"]["cookies"])

            return event

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment,
            integrations=[sentry_logging],
            traces_sample_rate=1.0,  # Capture 100% of transactions for performance monitoring
            profiles_sample_rate=1.0,  # Capture 100% of profiles for performance monitoring
            before_send=before_send,  # Apply sensitive data filtering
            send_default_pii=False,  # Don't send personally identifiable information
        )
        logger.info(f"Sentry initialized for environment: {settings.sentry_environment}")
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}", exc_info=True)
