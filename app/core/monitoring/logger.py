"""

Structured logging implementation with multiple handlers and levels.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Optional, Union
from enum import Enum
from pathlib import Path
import traceback
from contextvars import ContextVar

# Context variable for request tracking
request_id_context: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class LogLevel(str, Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredFormatter(logging.Formatter):
    """JSON structured formatter for production logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
            "process": record.process,
            "process_name": record.processName,
        }

        # Add request ID if available
        request_id = request_id_context.get()
        if request_id:
            log_data["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "getMessage",
            ]:
                log_data[key] = value

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for development console output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Build formatted message
        msg = f"{color}[{timestamp}] {record.levelname:8}{reset} | "
        msg += f"{record.name:20} | {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            msg += f"\n{color}{''.join(traceback.format_exception(*record.exc_info))}{reset}"

        return msg


class StructuredLogger:
    """Enhanced logger with structured logging capabilities."""

    def __init__(self, name: str, level: Union[str, LogLevel] = LogLevel.INFO) -> None:
        """Initialize structured logger."""
        self.logger = logging.getLogger(name)
        self.set_level(level)

    def set_level(self, level: Union[str, LogLevel]) -> None:
        """Set logging level."""
        if isinstance(level, str):
            level = LogLevel(level.upper())
        self.logger.setLevel(getattr(logging, level.value))

    def _log(self, level: str, message: str, **kwargs) -> None:
        """Internal logging method with structured data."""
        extra = {}

        # Extract special fields
        exc_info = kwargs.pop("exc_info", None)
        stack_info = kwargs.pop("stack_info", False)

        # Add all kwargs as extra fields
        extra.update(kwargs)

        # Get appropriate log method
        log_method = getattr(self.logger, level.lower())
        log_method(message, exc_info=exc_info, stack_info=stack_info, extra=extra)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._log("ERROR", message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self._log("CRITICAL", message, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """Log exception with traceback."""
        kwargs["exc_info"] = True
        self._log("ERROR", message, **kwargs)


def setup_logging(
    log_level: Union[str, LogLevel] = LogLevel.INFO,
    log_file: Optional[str] = None,
    json_logs: bool = False,
    colored_output: bool = True,
) -> None:
    """
    Setup application-wide logging configuration.

    Args:
        log_level: Logging level
        log_file: Optional log file path
        json_logs: Use JSON structured logging
        colored_output: Use colored console output (ignored if json_logs=True)
    """
    # Convert level if string
    if isinstance(log_level, str):
        log_level = LogLevel(log_level.upper())

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.value))

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.value))

    if json_logs:
        console_handler.setFormatter(StructuredFormatter())
    elif colored_output and sys.stdout.isatty():
        console_handler.setFormatter(ColoredFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)-8s | %(name)-20s | %(message)s")
        )

    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        # Create log directory if needed
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.value))

        if json_logs:
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter("[%(asctime)s] %(levelname)-8s | %(name)-20s | %(message)s")
            )

        root_logger.addHandler(file_handler)

    # Configure third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str, level: Optional[Union[str, LogLevel]] = None) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)
        level: Optional logging level override

    Returns:
        StructuredLogger instance
    """
    logger = StructuredLogger(name)
    if level:
        logger.set_level(level)
    return logger


def set_request_id(request_id: str) -> None:
    """Set request ID for current context."""
    request_id_context.set(request_id)


def get_request_id() -> Optional[str]:
    """Get current request ID."""
    return request_id_context.get()


def clear_request_id() -> None:
    """Clear request ID from context."""
    request_id_context.set(None)
