"""

Logging Configuration for ComplianceGPT

This module sets up structured JSON logging for the application.
"""

import logging
import logging.config
import sys
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger
from api.context import request_id_var, user_id_var
from config.settings import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict) -> None:
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            log_record["timestamp"] = record.created
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname
        request_id = request_id_var.get()
        if request_id:
            log_record["request_id"] = request_id
        user_id = user_id_var.get()
        if user_id:
            log_record["user_id"] = str(user_id)


def get_logging_config(log_level: str) -> Dict[str, Any]:
    """Defines the logging configuration dictionary."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "config.logging_config.CustomJsonFormatter",
                "format": "%(timestamp)s %(level)s %(name)s %(message)s %(request_id)s %(user_id)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "json",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/app.log",
                "maxBytes": 10485760,
                "backupCount": 5,
                "formatter": "json",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/error.log",
                "maxBytes": 10485760,
                "backupCount": 5,
                "formatter": "json",
                "level": "ERROR",
            },
        },
        "root": {"handlers": ["console", "file", "error_file"], "level": log_level},
        "loggers": {
            "uvicorn": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
            "gunicorn": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
            "celery": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
            "api": {
                "handlers": ["console", "file", "error_file"],
                "level": "DEBUG",
                "propagate": False,
            },
            "services": {
                "handlers": ["console", "file", "error_file"],
                "level": "INFO",
                "propagate": False,
            },
            "database": {
                "handlers": ["file", "error_file"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }


def setup_logging() -> None:
    """Setup logging configuration based on environment settings."""
    log_level = settings.log_level.value
    logging_config = get_logging_config(log_level)
    logging.config.dictConfig(logging_config)
    logger = logging.getLogger(__name__)
    logger.info("Logging initialized with level %s" % log_level)


class ComplianceLogger:
    """A wrapper around the standard logger to provide structured logging for specific event types."""

    def __init__(self, name: str) -> None:
        self.logger = logging.getLogger(name)

    def log_user_action(
        self, user_id: str, action: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log user actions for audit purposes."""
        self.logger.info(
            "User action: %s" % action,
            extra={
                "event_type": "user_action",
                "user_id": user_id,
                "action": action,
                "details": details or {},
            },
        )

    def log_compliance_event(
        self, event_type: str, framework: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log compliance-related events."""
        self.logger.info(
            "Compliance event: %s" % event_type,
            extra={
                "event_type": "compliance_event",
                "compliance_framework": framework,
                "compliance_event_type": event_type,
                "details": details or {},
            },
        )

    def log_ai_interaction(
        self, model: str, prompt_type: str, tokens_used: Optional[int] = None
    ) -> None:
        """Log AI model interactions."""
        self.logger.info(
            "AI interaction with %s" % model,
            extra={
                "event_type": "ai_interaction",
                "ai_model": model,
                "prompt_type": prompt_type,
                "tokens_used": tokens_used,
            },
        )

    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Log errors with additional context."""
        self.logger.error(
            "Error: %s" % type(error).__name__,
            extra={
                "event_type": "error",
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context or {},
            },
            exc_info=True,
        )


def get_logger(name: str) -> logging.Logger:
    """Get a standard logger instance."""
    return logging.getLogger(name)
