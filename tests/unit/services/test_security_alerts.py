"""
Unit tests for services/security_alerts.py — SecurityAlertService.

Database and SMTP interactions are mocked.
"""

import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.security_alerts import SecurityAlertService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(email="test@example.com"):
    user = MagicMock()
    user.id = uuid4()
    user.email = email
    return user


def _make_db(failed_count=0):
    mock_result = MagicMock()
    mock_result.scalar.return_value = failed_count
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

class TestThresholds:
    """Tests for threshold constants."""

    def test_failed_login_threshold(self):
        assert SecurityAlertService.FAILED_LOGIN_THRESHOLD == 3

    def test_failed_login_window(self):
        assert SecurityAlertService.FAILED_LOGIN_WINDOW == 15


# ---------------------------------------------------------------------------
# check_failed_logins
# ---------------------------------------------------------------------------

class TestCheckFailedLogins:
    """Tests for SecurityAlertService.check_failed_logins()."""

    @pytest.mark.asyncio
    async def test_below_threshold(self):
        db = _make_db(failed_count=2)
        user = _make_user()
        result = await SecurityAlertService.check_failed_logins(db, user, "192.168.1.1")
        assert result is False

    @pytest.mark.asyncio
    async def test_at_threshold(self):
        db = _make_db(failed_count=3)
        user = _make_user()
        result = await SecurityAlertService.check_failed_logins(db, user, "192.168.1.1")
        assert result is True

    @pytest.mark.asyncio
    async def test_above_threshold(self):
        db = _make_db(failed_count=10)
        user = _make_user()
        result = await SecurityAlertService.check_failed_logins(db, user, "192.168.1.1")
        assert result is True

    @pytest.mark.asyncio
    async def test_zero_failures(self):
        db = _make_db(failed_count=0)
        user = _make_user()
        result = await SecurityAlertService.check_failed_logins(db, user, "10.0.0.1")
        assert result is False

    @pytest.mark.asyncio
    async def test_null_count_treated_as_zero(self):
        mock_result = MagicMock()
        mock_result.scalar.return_value = None  # NULL from DB
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        user = _make_user()
        result = await SecurityAlertService.check_failed_logins(mock_db, user, "10.0.0.1")
        assert result is False


# ---------------------------------------------------------------------------
# send_failed_login_alert
# ---------------------------------------------------------------------------

class TestSendFailedLoginAlert:
    """Tests for SecurityAlertService.send_failed_login_alert()."""

    @pytest.mark.asyncio
    async def test_skips_when_smtp_not_configured(self):
        user = _make_user()
        # No SMTP_HOST set
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SMTP_HOST", None)
            os.environ.pop("SMTP_USER", None)
            os.environ.pop("SMTP_PASSWORD", None)
            # Should not raise, just log warning
            await SecurityAlertService.send_failed_login_alert(
                user=user, failed_attempts=5, ip_address="1.2.3.4"
            )

    @pytest.mark.asyncio
    async def test_sends_when_smtp_configured(self):
        user = _make_user("victim@example.com")
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.test.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "user",
            "SMTP_PASSWORD": "pass",
        }):
            with patch("services.security_alerts.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
                await SecurityAlertService.send_failed_login_alert(
                    user=user,
                    failed_attempts=5,
                    ip_address="1.2.3.4",
                    user_agent="Mozilla/5.0",
                )
                mock_send.assert_awaited_once()
                # Verify the send was called with correct SMTP params
                call_kwargs = mock_send.call_args[1]
                assert call_kwargs["hostname"] == "smtp.test.com"
                assert call_kwargs["port"] == 587

    @pytest.mark.asyncio
    async def test_handles_smtp_error_gracefully(self):
        user = _make_user("test@example.com")
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.test.com",
            "SMTP_USER": "user",
            "SMTP_PASSWORD": "pass",
        }):
            with patch(
                "services.security_alerts.aiosmtplib.send",
                new_callable=AsyncMock,
                side_effect=Exception("SMTP connection refused"),
            ):
                # Should not raise
                await SecurityAlertService.send_failed_login_alert(
                    user=user, failed_attempts=3, ip_address="1.1.1.1"
                )


# ---------------------------------------------------------------------------
# log_and_check_login_attempt
# ---------------------------------------------------------------------------

class TestLogAndCheckLoginAttempt:
    """Tests for SecurityAlertService.log_and_check_login_attempt()."""

    @pytest.mark.asyncio
    async def test_successful_login_logged(self):
        db = _make_db(failed_count=0)
        user = _make_user()
        await SecurityAlertService.log_and_check_login_attempt(
            db, user, success=True, ip_address="192.168.1.1"
        )
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failed_login_checks_threshold(self):
        # First call: add audit log (commit)
        # After commit, check_failed_logins is called: returns False (below threshold)
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1  # Below threshold
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        user = _make_user()
        await SecurityAlertService.log_and_check_login_attempt(
            mock_db, user, success=False, ip_address="192.168.1.1"
        )
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_audit_log_action_success(self):
        db = _make_db()
        user = _make_user()
        await SecurityAlertService.log_and_check_login_attempt(
            db, user, success=True, ip_address="10.0.0.1"
        )
        added_entry = db.add.call_args[0][0]
        assert added_entry.action == "login_success"
        assert added_entry.severity == "info"

    @pytest.mark.asyncio
    async def test_audit_log_action_failure(self):
        db = _make_db(failed_count=0)
        user = _make_user()
        await SecurityAlertService.log_and_check_login_attempt(
            db, user, success=False, ip_address="10.0.0.1"
        )
        added_entry = db.add.call_args[0][0]
        assert added_entry.action == "login_failure"
        assert added_entry.severity == "warning"


# ---------------------------------------------------------------------------
# send_password_change_notification
# ---------------------------------------------------------------------------

class TestSendPasswordChangeNotification:
    """Tests for SecurityAlertService.send_password_change_notification()."""

    @pytest.mark.asyncio
    async def test_skips_when_smtp_not_configured(self):
        user = _make_user()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SMTP_HOST", None)
            # Should not raise
            await SecurityAlertService.send_password_change_notification(
                user=user, ip_address="10.0.0.1"
            )
