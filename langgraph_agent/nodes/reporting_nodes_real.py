"""

Real reporting nodes implementation with actual service integration.
Connects to real ReportGenerator, PDFGenerator, and ReportScheduler services.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import UUID
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import smtplib
import aiofiles

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from langgraph_agent.graph.state import ComplianceAgentState
from database.business_profile import BusinessProfile as BusinessProfileModel
from database.user import User as UserModel
from database.compliance_framework import (
    ComplianceFramework as ComplianceFrameworkModel,
)
from services.reporting.report_generator import ReportGenerator
from services.reporting.pdf_generator import PDFGenerator
from services.reporting.report_scheduler import ReportScheduler
from database.report_schedule import ReportSchedule as ReportScheduleModel
from config.settings import settings
from core.exceptions import NotFoundException, DatabaseException, BusinessLogicException

logger = logging.getLogger(__name__)


def _send_email_directly(
    recipients: List[str],
    subject: str,
    body: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """
    Send email directly without Celery (migration complete).

    Args:
        recipients: List of email addresses
        subject: Email subject
        body: Email body content
        attachments: Optional list of attachments

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get SMTP configuration from settings
        smtp_host = getattr(settings, "SMTP_HOST", "localhost")
        smtp_port = getattr(settings, "SMTP_PORT", 587)
        smtp_user = getattr(settings, "SMTP_USER", "")
        smtp_password = getattr(settings, "SMTP_PASSWORD", "")
        smtp_from = getattr(settings, "SMTP_FROM", "noreply@ruleiq.com")

        # Create message
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        # Add body
        msg.attach(MIMEText(body, "plain"))

        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment["content"])
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition", f"attachment; filename={attachment['filename']}"
                )
                msg.attach(part)

        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_user and smtp_password:
                server.starttls()
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(f"Email sent successfully to {recipients}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


async def get_user_for_profile(db: AsyncSession, profile: BusinessProfileModel) -> UserModel:
    """Get the user associated with a business profile."""
    result = await db.execute(select(UserModel).where(UserModel.id == profile.user_id))
    user = result.scalars().first()
    if not user:
        raise NotFoundException(f"User not found for profile {profile.id}")
    return user


async def get_default_framework(db: AsyncSession) -> ComplianceFrameworkModel:
    """Get a default compliance framework (first available)."""
    result = await db.execute(select(ComplianceFrameworkModel).limit(1))
    framework = result.scalars().first()
    if not framework:
        raise NotFoundException("No compliance frameworks found in database")
    return framework


async def generate_scheduled_reports_node(
    state: ComplianceAgentState,
) -> ComplianceAgentState:
    """
    Generate and distribute scheduled reports for all active schedules.

    This node:
    - Fetches all active report schedules from database
    - Generates reports using ReportGenerator service
    - Creates PDF versions using PDFGenerator
    - Distributes via email
    - Updates schedule status

    Args:
        state: Current workflow state with database session

    Returns:
        Updated state with report generation results
    """
    logger.info(f"Starting scheduled report generation for workflow {state.get('workflow_id')}")

    # Get database session from state
    db = state.get("db_session")
    if not db:
        logger.error("No database session in state")
        state["errors"].append(
            {
                "type": "DatabaseError",
                "message": "Database session not available",
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        return state

    try:
        # Get all active schedules
        scheduler = ReportScheduler(db)
        active_schedules = await scheduler.get_active_schedules()

        logger.info(f"Found {len(active_schedules)} active report schedules")

        reports_generated = 0
        reports_failed = 0

        for schedule in active_schedules:
            try:
                # Check if schedule should run now based on frequency
                if not should_run_schedule(schedule):
                    logger.debug(f"Schedule {schedule.id} not due yet")
                    continue

                # Generate the report
                report_generator = ReportGenerator(db)
                report_data = await report_generator.generate_report(
                    user_id=schedule.user_id,
                    business_profile_id=schedule.business_profile_id,
                    report_type=schedule.report_type,
                    parameters=schedule.parameters,
                )

                # Generate PDF if requested
                pdf_content = None
                if schedule.report_format == "pdf":
                    pdf_generator = PDFGenerator()
                    pdf_content = await pdf_generator.generate_pdf(report_data)

                    # Save PDF file
                    filename = (
                        f"{schedule.report_type.replace(' ', '_')}_"
                        f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
                    )
                    file_path = await save_report_file(pdf_content, filename)
                    report_data["file_path"] = file_path

                # Send email with report
                if schedule.recipients:
                    await send_scheduled_report_email(
                        recipients=schedule.recipients,
                        report_type=schedule.report_type,
                        report_data=report_data,
                        pdf_content=pdf_content,
                    )

                # Update schedule status
                await scheduler.update_schedule_status(
                    schedule_id=schedule.id,
                    status="success",
                    distribution_successful=True,
                )

                reports_generated += 1
                logger.info(f"Successfully generated report for schedule {schedule.id}")

            except Exception as e:
                logger.error(f"Failed to generate report for schedule {schedule.id}: {e}")
                await scheduler.update_schedule_status(
                    schedule_id=schedule.id,
                    status="failed",
                    distribution_successful=False,
                )
                reports_failed += 1

        # Update state with results
        state["report_data"]["scheduled_reports"] = {
            "processed": len(active_schedules),
            "generated": reports_generated,
            "failed": reports_failed,
            "timestamp": datetime.now().isoformat(),
        }

        # Add to history
        state["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "scheduled_reports_generated",
                "reports_generated": reports_generated,
                "reports_failed": reports_failed,
            }
        )

        logger.info(
            f"Scheduled report generation complete: {reports_generated} generated, {reports_failed} failed"
        )

    except Exception as e:
        logger.error(f"Error in scheduled report generation: {e}")
        state["errors"].append(
            {
                "type": "ScheduledReportError",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        raise

    return state


async def generate_on_demand_report_node(
    state: ComplianceAgentState,
) -> ComplianceAgentState:
    """
    Generate an on-demand report for a specific business profile.

    This node:
    - Generates a report based on user request
    - Supports multiple report types and formats
    - Distributes to specified recipients

    Args:
        state: Current workflow state with report request

    Returns:
        Updated state with generated report
    """
    logger.info(f"Starting on-demand report generation for workflow {state.get('workflow_id')}")

    # Get database session
    db = state.get("db_session")
    if not db:
        logger.error("No database session in state")
        state["errors"].append(
            {
                "type": "DatabaseError",
                "message": "Database session not available",
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        return state

    # Extract report parameters from metadata
    metadata = state.get("metadata", {})
    user_id = metadata.get("user_id")
    profile_id = metadata.get("business_profile_id")
    report_type = metadata.get("report_type", "compliance_status")
    report_format = metadata.get("report_format", "pdf")
    recipients = metadata.get("recipient_emails", [])
    parameters = metadata.get("report_parameters", {})

    if not user_id or not profile_id:
        logger.error("Missing user_id or business_profile_id for on-demand report")
        state["errors"].append(
            {
                "type": "ValidationError",
                "message": "user_id and business_profile_id are required",
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        return state

    try:
        # Generate the report
        report_generator = ReportGenerator(db)
        report_data = await report_generator.generate_report(
            user_id=UUID(user_id),
            business_profile_id=UUID(profile_id),
            report_type=report_type,
            parameters=parameters,
        )

        # Generate output format
        if report_format == "pdf":
            pdf_generator = PDFGenerator()
            pdf_content = await pdf_generator.generate_pdf(report_data)

            # Save PDF file
            filename = (
                f"{report_type.replace(' ', '_')}_"
                f"{profile_id}_"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            file_path = await save_report_file(pdf_content, filename)
            state["report_data"]["file_path"] = file_path
            state["report_data"]["format"] = "pdf"

            # Send to recipients if specified
            if recipients:
                await send_on_demand_report_email(
                    recipients=recipients,
                    report_type=report_type,
                    report_data=report_data,
                    pdf_path=file_path,
                )
                state["report_data"]["distributed"] = True
                state["report_data"]["recipients"] = recipients

        elif report_format == "json":
            # Return JSON data
            state["report_data"]["content"] = report_data
            state["report_data"]["format"] = "json"

        else:
            raise ValueError(f"Unsupported report format: {report_format}")

        # Update state with report metadata
        state["report_data"]["report_type"] = report_type
        state["report_data"]["generated_at"] = datetime.now().isoformat()
        state["report_data"]["business_profile_id"] = profile_id
        state["report_data"]["status"] = "completed"

        # Add to history
        state["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "on_demand_report_generated",
                "report_type": report_type,
                "format": report_format,
                "distributed": bool(recipients),
            }
        )

        logger.info(f"On-demand report generated successfully for profile {profile_id}")

    except NotFoundException as e:
        logger.error(f"Not found error generating on-demand report: {e}")
        state["errors"].append(
            {
                "type": "NotFoundException",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        raise

    except (DatabaseException, BusinessLogicException) as e:
        logger.error(f"Error generating on-demand report: {e}")
        state["errors"].append(
            {
                "type": e.__class__.__name__,
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        raise

    except Exception as e:
        logger.error(f"Unexpected error generating on-demand report: {e}")
        state["errors"].append(
            {
                "type": "ReportGenerationError",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        raise

    return state


async def send_summary_notifications_node(
    state: ComplianceAgentState,
) -> ComplianceAgentState:
    """
    Send summary notifications about report activity to users.

    This node:
    - Aggregates report activity for each user
    - Sends summary emails with report statistics
    - Tracks notification status

    Args:
        state: Current workflow state

    Returns:
        Updated state with notification results
    """
    logger.info(f"Starting summary notifications for workflow {state.get('workflow_id')}")

    # Get database session
    db = state.get("db_session")
    if not db:
        logger.error("No database session in state")
        state["errors"].append(
            {
                "type": "DatabaseError",
                "message": "Database session not available",
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        return state

    try:
        scheduler = ReportScheduler(db)
        active_schedules = await scheduler.get_active_schedules()

        # Group schedules by user
        user_summaries = {}
        for schedule in active_schedules:
            user_id = str(schedule.user_id)
            if user_id not in user_summaries:
                user_summaries[user_id] = {
                    "schedules": [],
                    "total_reports": 0,
                    "user": None,
                }

            user_summaries[user_id]["schedules"].append(schedule)
            user_summaries[user_id]["total_reports"] += 1

            # Get user details if not already fetched
            if not user_summaries[user_id]["user"]:
                # Check if user is already on the schedule object
                if hasattr(schedule, "owner") and schedule.owner:
                    user_summaries[user_id]["user"] = schedule.owner
                else:
                    # Fetch from database if not available
                    user_result = await db.execute(
                        select(UserModel).where(UserModel.id == schedule.user_id)
                    )
                    user = user_result.scalars().first()
                    user_summaries[user_id]["user"] = user

        # Send notifications
        notifications_sent = 0
        notifications_failed = 0

        for user_id, summary in user_summaries.items():
            user = summary["user"]
            if not user or not user.email:
                logger.warning(f"No email for user {user_id}, skipping notification")
                continue

            try:
                # Prepare summary content
                summary_content = prepare_summary_content(summary)

                # Send email
                await send_summary_email(
                    recipient=user.email,
                    user_name=user.username or user.email,
                    summary_content=summary_content,
                )

                notifications_sent += 1
                logger.info(f"Sent summary notification to {user.email}")

            except Exception as e:
                logger.error(f"Failed to send summary to {user.email}: {e}")
                notifications_failed += 1

        # Update state with results
        state["notification_data"] = {
            "type": "summary",
            "sent": notifications_sent,
            "failed": notifications_failed,
            "total_users": len(user_summaries),
            "timestamp": datetime.now().isoformat(),
        }

        # Add to history
        state["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "summary_notifications_sent",
                "notifications_sent": notifications_sent,
                "notifications_failed": notifications_failed,
            }
        )

        logger.info(
            f"Summary notifications complete: {notifications_sent} sent, {notifications_failed} failed"
        )

    except Exception as e:
        logger.error(f"Error sending summary notifications: {e}")
        state["errors"].append(
            {
                "type": "NotificationError",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        raise

    return state


def should_run_schedule(schedule: ReportScheduleModel) -> bool:
    """
    Check if a schedule should run now based on frequency and last run time.

    Args:
        schedule: Report schedule to check

    Returns:
        True if schedule should run now
    """
    if not schedule.active:
        return False

    now = datetime.now(timezone.utc)

    # If never run, should run
    if not schedule.last_run:
        return True

    # Check based on frequency
    if schedule.frequency == "daily":
        return (now - schedule.last_run).days >= 1
    elif schedule.frequency == "weekly":
        return (now - schedule.last_run).days >= 7
    elif schedule.frequency == "monthly":
        return (now - schedule.last_run).days >= 30

    return False


async def save_report_file(content: bytes, filename: str) -> str:
    """
    Save report content to file.

    Args:
        content: Report content as bytes
        filename: Name for the report file

    Returns:
        Full path to saved file
    """
    report_dir = Path(getattr(settings, "REPORT_DIRECTORY", "/tmp/reports"))
    report_dir.mkdir(parents=True, exist_ok=True)

    file_path = report_dir / filename

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    return str(file_path)


async def send_scheduled_report_email(
    recipients: List[str],
    report_type: str,
    report_data: Dict[str, Any],
    pdf_content: Optional[bytes] = None,
) -> bool:
    """
    Send scheduled report email to recipients.

    Args:
        recipients: List of email addresses
        report_type: Type of report
        report_data: Report data dictionary
        pdf_content: Optional PDF content to attach

    Returns:
        True if email sent successfully
    """
    try:
        subject = f"Scheduled Report: {report_type}"

        # Extract key metrics from report data
        metrics = report_data.get("key_metrics", {})
        compliance_score = metrics.get("overall_compliance_score", "N/A")

        body = f"""
        Dear Compliance Team,

        Your scheduled {report_type} report has been generated.

        Report Summary:
        - Generated: {report_data.get("generated_at", datetime.now().isoformat())}
        - Overall Compliance Score: {compliance_score}%
        - Report Type: {report_type}

        Please find the detailed report attached (if applicable).

        Best regards,
        Compliance Monitoring System
        """

        # Send using configured email service
        return await send_email_with_attachment(
            recipients=recipients,
            subject=subject,
            body=body,
            attachment_data=pdf_content,
            attachment_name=(f"{report_type.replace(' ', '_')}.pdf" if pdf_content else None),
        )

    except Exception as e:
        logger.error(f"Failed to send scheduled report email: {e}")
        return False


async def send_on_demand_report_email(
    recipients: List[str],
    report_type: str,
    report_data: Dict[str, Any],
    pdf_path: Optional[str] = None,
) -> bool:
    """
    Send on-demand report email to recipients.

    Args:
        recipients: List of email addresses
        report_type: Type of report
        report_data: Report data dictionary
        pdf_path: Optional path to PDF file

    Returns:
        True if email sent successfully
    """
    try:
        subject = f"On-Demand Report: {report_type}"

        body = f"""
        Dear User,

        Your requested {report_type} report has been generated.

        Report Details:
        - Generated: {report_data.get("generated_at", datetime.now().isoformat())}
        - Report Title: {report_data.get("report_title", report_type)}

        {report_data.get("summary", "Please see the attached report for details.")}

        Best regards,
        Compliance Monitoring System
        """

        # Read PDF file if provided
        attachment_data = None
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                attachment_data = f.read()

        return await send_email_with_attachment(
            recipients=recipients,
            subject=subject,
            body=body,
            attachment_data=attachment_data,
            attachment_name=os.path.basename(pdf_path) if pdf_path else None,
        )

    except Exception as e:
        logger.error(f"Failed to send on-demand report email: {e}")
        return False


def prepare_summary_content(summary: Dict[str, Any]) -> str:
    """
    Prepare summary content for notification email.

    Args:
        summary: User summary data

    Returns:
        Formatted summary content
    """
    schedules = summary["schedules"]
    total_reports = summary["total_reports"]

    schedule_details = []
    for schedule in schedules[:5]:  # Limit to first 5
        schedule_details.append(f"  - {schedule.report_type} ({schedule.frequency})")

    if len(schedules) > 5:
        schedule_details.append(f"  ... and {len(schedules) - 5} more")

    return f"""
    Report Activity Summary

    You have {total_reports} active report schedule(s):

    {chr(10).join(schedule_details)}

    All reports are being generated and distributed according to schedule.
    """


async def send_summary_email(recipient: str, user_name: str, summary_content: str) -> bool:
    """
    Send summary notification email to user.

    Args:
        recipient: Email address
        user_name: User's name
        summary_content: Summary content

    Returns:
        True if email sent successfully
    """
    try:
        subject = "Your Compliance Report Summary"

        body = f"""
        Dear {user_name},

        {summary_content}

        If you have any questions or need to adjust your report schedules,
        please log in to the compliance portal.

        Best regards,
        Compliance Monitoring System
        """

        return await send_email_with_attachment(recipients=[recipient], subject=subject, body=body)

    except Exception as e:
        logger.error(f"Failed to send summary email: {e}")
        return False


async def send_email_with_attachment(
    recipients: List[str],
    subject: str,
    body: str,
    attachment_data: Optional[bytes] = None,
    attachment_name: Optional[str] = None,
) -> bool:
    """
    Send email with optional attachment using the synchronous email sender.

    Args:
        recipients: List of email addresses
        subject: Email subject
        body: Email body
        attachment_data: Optional attachment data
        attachment_name: Optional attachment filename

    Returns:
        True if email sent successfully
    """
    attachments = []
    if attachment_data and attachment_name:
        attachments.append({"filename": attachment_name, "content": attachment_data})

    # Send email directly (Celery migration complete)
    return _send_email_directly(recipients, subject, body, attachments if attachments else None)
