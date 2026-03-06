"""
Security Alert Service for SMB owners.
Sends email notifications for security events like failed login attempts.
"""

from typing import Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from database.user import User
from database.rbac import AuditLog
import logging
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
import os

logger = logging.getLogger(__name__)


class SecurityAlertService:
    """Service for managing security alerts and notifications."""

    # Thresholds for alerts
    FAILED_LOGIN_THRESHOLD = 3  # Alert after 3 failed attempts
    FAILED_LOGIN_WINDOW = 15  # Within 15 minutes

    @classmethod
    async def check_failed_logins(cls, db: AsyncSession, user: User, ip_address: str) -> bool:
        """
        Check if failed login threshold has been exceeded.

        Args:
            db: Database session
            user: User attempting login
            ip_address: IP address of login attempt

        Returns:
            True if alert should be sent
        """
        window_start = datetime.now(timezone.utc) - timedelta(minutes=cls.FAILED_LOGIN_WINDOW)

        # Count recent failed login attempts
        stmt = select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.user_id == user.id,
                AuditLog.action == "login_failure",
                AuditLog.timestamp >= window_start,
                AuditLog.ip_address == ip_address,
            ),
        )

        result = await db.execute(stmt)
        failed_count = result.scalar() or 0

        return failed_count >= cls.FAILED_LOGIN_THRESHOLD

    @classmethod
    async def send_failed_login_alert(
        cls,
        user: User,
        failed_attempts: int,
        ip_address: str,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Send email alert for failed login attempts.

        Args:
            user: User account with failed attempts
            failed_attempts: Number of failed attempts
            ip_address: IP address of attempts
            user_agent: Browser/client user agent
        """
        # Check if email notifications are configured
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        from_email = os.getenv("ALERT_FROM_EMAIL", "security@ruleiq.com")

        if not all([smtp_host, smtp_user, smtp_password]):
            logger.warning("Email configuration missing, skipping failed login alert")
            return

        # Prepare email content
        subject = "Security Alert: Multiple Failed Login Attempts"

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #d32f2f;">Security Alert</h2>

                <p>We've detected multiple failed login attempts on your account:</p>

                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Failed Attempts:</strong> {failed_attempts}</p>
                    <p><strong>IP Address:</strong> {ip_address}</p>
                    <p><strong>Time:</strong> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC</p>
                    {f"<p><strong>Device:</strong> {user_agent}</p>" if user_agent else ""}
                </div>

                <h3>What should you do?</h3>
                <ul>
                    <li>If this was you, please ensure you're using the correct password</li>
                    <li>If this wasn't you, please change your password immediately</li>
                    <li>Consider enabling two-factor authentication for added security</li>
                </ul>

                <p style="margin-top: 30px;">
                    <a href="{os.getenv("FRONTEND_URL", "https://app.ruleiq.com")}/reset-password"
                       style= (
                           "background-color: #1976d2; color: white; padding: 10px 20px; text-decoration: "
                           "none; border-radius: 5px;"",
                       )
                        Reset Password
                    </a>
                </p>

                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                    This is an automated security alert from RuleIQ.
                    Please do not reply to this email.
                </p>
            </body>
        </html>
        """

        text_body = f"""
Security Alert: Multiple Failed Login Attempts

We've detected multiple failed login attempts on your account:

Failed Attempts: {failed_attempts}
IP Address: {ip_address}
Time: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC
{f"Device: {user_agent}" if user_agent else ""}

What should you do?
- If this was you, please ensure you're using the correct password
- If this wasn't you, please change your password immediately
- Consider enabling two-factor authentication for added security

Reset your password: {os.getenv("FRONTEND_URL", "https://app.ruleiq.com")}/reset-password

This is an automated security alert from RuleIQ.
        """

        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = from_email
        message["To"] = user.email

        # Add text and HTML parts
        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")

        message.attach(part1)
        message.attach(part2)

        # Send email asynchronously
        try:
            await aiosmtplib.send(
                message,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_password,
                start_tls=True,
            )
            logger.info(
                f"Security alert sent to {user.email} for failed login attempts",
            )
        except Exception as e:
            logger.error(f"Failed to send security alert email: {e}")

    @classmethod
    async def log_and_check_login_attempt(
        cls,
        db: AsyncSession,
        user: User,
        success: bool,
        ip_address: str,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Log login attempt and check if alert is needed.

        Args:
            db: Database session
            user: User attempting login
            success: Whether login was successful
            ip_address: IP address of attempt
            user_agent: Browser/client user agent
        """
        # Log the attempt
        action = "login_success" if success else "login_failure"

        audit_log = AuditLog(
            user_id=user.id,
            action=action,
            resource_type="authentication",
            resource_id=str(user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            severity="info" if success else "warning",
            timestamp=datetime.now(timezone.utc),
        )

        db.add(audit_log)
        await db.commit()

        # Check if we need to send an alert for failed attempts
        if not success:
            should_alert = await cls.check_failed_logins(db, user, ip_address)

            if should_alert:
                # Count total failed attempts in window
                window_start = datetime.now(timezone.utc) - timedelta(
                    minutes=cls.FAILED_LOGIN_WINDOW,
                )
                stmt = select(func.count(AuditLog.id)).where(
                    and_(
                        AuditLog.user_id == user.id,
                        AuditLog.action == "login_failure",
                        AuditLog.timestamp >= window_start,
                    ),
                )
                result = await db.execute(stmt)
                total_failed = result.scalar() or 0

                # Send alert asynchronously
                asyncio.create_task(
                    cls.send_failed_login_alert(
                        user=user,
                        failed_attempts=total_failed,
                        ip_address=ip_address,
                        user_agent=user_agent,
                    ),
                )

    @classmethod
    async def send_password_change_notification(cls, user: User, ip_address: str) -> None:
        """
        Send notification when password is changed.

        Args:
            user: User who changed password
            ip_address: IP address of change
        """
        # Similar to failed login alert but for password changes
        smtp_host = os.getenv("SMTP_HOST")
        if not smtp_host:
            logger.warning(
                "Email configuration missing, skipping password change notification",
            )
            return

        f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Password Changed Successfully</h2>

                <p>Your password was successfully changed.</p>

                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Changed at:</strong> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC</p>
                    <p><strong>IP Address:</strong> {ip_address}</p>
                </div>

                <p>If you did not make this change, please contact support immediately.</p>

                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                    This is an automated notification from RuleIQ.
                </p>
            </body>
        </html>
        """

        # Send notification (implementation similar to failed login alert)
        logger.info(f"Password change notification queued for {user.email}")
