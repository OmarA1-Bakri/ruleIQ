"""
Unit tests for middleware.audit_logging.
"""

import importlib
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from middleware import audit_logging


@pytest.fixture
def reloaded_audit_logging():
    """Reload the module so each test starts from a clean singleton state."""
    return importlib.reload(audit_logging)


class TestAuditLoggerLazyInitialization:
    def test_module_singleton_is_lazy(self, reloaded_audit_logging):
        assert reloaded_audit_logging._audit_logger is None

        first = reloaded_audit_logging.get_audit_logger()
        second = reloaded_audit_logging.get_audit_logger()

        assert first is second
        assert reloaded_audit_logging._audit_logger is first

    @pytest.mark.asyncio
    async def test_flush_task_lock_is_created_lazily(self, reloaded_audit_logging):
        logger = reloaded_audit_logging.AuditLogger()
        sentinel_task = Mock()

        assert logger._flush_task_lock is None
        assert logger._flush_task_started is False

        with patch.object(reloaded_audit_logging.asyncio, "create_task", return_value=sentinel_task):
            await logger._start_flush_timer()
            await logger._start_flush_timer()

        assert logger._flush_task_lock is not None
        assert logger._flush_task_started is True
        assert logger._flush_task is sentinel_task

    @pytest.mark.asyncio
    async def test_shutdown_without_prior_start_is_safe(self, reloaded_audit_logging):
        logger = reloaded_audit_logging.AuditLogger()

        await logger.shutdown()

        assert logger._flush_task_lock is not None
        assert logger._flush_task is None
        assert logger._flush_task_started is False


class TestAuditLoggingHelpers:
    @pytest.mark.asyncio
    async def test_log_security_event_uses_lazy_singleton(self, reloaded_audit_logging):
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            headers={"user-agent": "pytest"},
        )
        mock_logger = AsyncMock()

        with patch.object(reloaded_audit_logging, "get_audit_logger", return_value=mock_logger) as getter:
            await reloaded_audit_logging.log_security_event(
                request,
                "TEST_EVENT",
                {"password": "secret", "nested": {"token": "abc"}},
            )

        getter.assert_called_once()
        mock_logger.log_event.assert_awaited_once()
        _, kwargs = mock_logger.log_event.await_args
        assert kwargs["event_type"] == "TEST_EVENT"
        assert kwargs["details"] == {"password": "secret", "nested": {"token": "abc"}}
        assert kwargs["ip_address"] == "127.0.0.1"
        assert kwargs["user_agent"] == "pytest"
