"""

Reporting nodes - migrated from Celery reporting_tasks.
Implements report generation, distribution, and cleanup functionality.
"""

import logging
import os
import json
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import aiofiles

from langgraph_agent.graph.unified_state import UnifiedComplianceState
from langgraph_agent.utils.cost_tracking import track_node_cost
from config.settings import settings

logger = logging.getLogger(__name__)


@track_node_cost(node_name="generate_report_node", model_name="gpt-4")
async def generate_report_node(state: UnifiedComplianceState) -> UnifiedComplianceState:
    """
    Generate compliance or risk assessment reports.

    Migrated from workers/reporting_tasks.py::generate_report_on_demand

    This node:
    - Prepares report data from compliance check results
    - Generates reports in various formats (PDF, JSON, HTML)
    - Stores report metadata for distribution

    Args:
        state: Current workflow state with compliance data

    Returns:
        Updated state with generated report data
    """
    logger.info(f"Starting report generation for workflow {state.get('workflow_id')}")

    # Extract report parameters
    report_type = state.get("metadata", {}).get("report_type", "compliance_summary")
    report_format = state.get("metadata", {}).get("report_format", "pdf")
    company_id = state.get("company_id")

    if not state.get("compliance_data"):
        logger.warning("No compliance data available for report generation")
        state["errors"].append(
            {
                "type": "DataError",
                "message": "No compliance data available for report",
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        return state

    try:
        # Prepare report data based on type
        report_content = prepare_report_data(
            compliance_data=state["compliance_data"], report_type=report_type
        )

        # Generate report in specified format
        if report_format == "pdf":
            report_bytes = await generate_pdf_report(report_content)
            file_path = await save_report_file(
                report_bytes,
                f"compliance_report_{company_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            )
            state["report_data"]["file_path"] = file_path
            state["report_data"]["format"] = "pdf"

        elif report_format == "json":
            report_json = json.dumps(report_content, indent=2)
            file_path = await save_report_file(
                report_json.encode(),
                f"compliance_report_{company_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )
            state["report_data"]["file_path"] = file_path
            state["report_data"]["format"] = "json"
            state["report_data"]["content"] = report_json

        elif report_format == "html":
            report_html = generate_html_report(report_content)
            file_path = await save_report_file(
                report_html.encode(),
                f"compliance_report_{company_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            )
            state["report_data"]["file_path"] = file_path
            state["report_data"]["format"] = "html"

        else:
            raise ValueError(f"Unsupported report format: {report_format}")

        # Update state with report metadata
        state["report_data"]["report_type"] = report_type
        state["report_data"]["generated_at"] = datetime.now().isoformat()
        state["report_data"]["company_id"] = company_id

        # Add to history
        state["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "report_generated",
                "report_type": report_type,
                "format": report_format,
                "file_path": state["report_data"].get("file_path"),
            }
        )

        logger.info(f"Report generated successfully: {state['report_data'].get('file_path')}")

    except Exception as e:
        logger.error(f"Error generating report: {e}")
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


async def distribute_report_node(
    state: UnifiedComplianceState,
) -> UnifiedComplianceState:
    """
    Distribute generated reports to recipients.

    Migrated from workers/reporting_tasks.py::generate_and_distribute_report

    This node:
    - Sends reports via email to specified recipients
    - Handles attachment of report files
    - Tracks distribution status

    Args:
        state: Current workflow state with generated report

    Returns:
        Updated state with distribution status
    """
    logger.info(f"Starting report distribution for workflow {state.get('workflow_id')}")

    # Check if report was generated
    if not state.get("report_data", {}).get("file_path"):
        logger.warning("No report file available for distribution")
        state["report_data"]["distribution_status"] = "skipped"
        state["report_data"]["reason"] = "No report file generated"
        return state

    # Get recipients
    recipients = state.get("metadata", {}).get("recipient_emails", [])

    if not recipients:
        logger.info("No recipients specified, skipping distribution")
        state["report_data"]["distribution_status"] = "skipped"
        state["report_data"]["reason"] = "No recipients specified"
        return state

    try:
        # Prepare email content
        subject = (
            f"Compliance Report - {state.get('report_data', {}).get('report_type', 'Summary')}"
        )
        company_id = state.get("company_id", "Unknown")

        body = f"""
        Dear Compliance Team,

        Please find attached the latest compliance report for company {company_id}.

        Report Details:
        - Type: {state.get("report_data", {}).get("report_type")}
        - Generated: {state.get("report_data", {}).get("generated_at")}
        - Format: {state.get("report_data", {}).get("format")}

        Compliance Summary:
        - Score: {state.get("compliance_data", {}).get("check_results", {}).get("compliance_score", "N/A")}%
        - Risk Level: {state.get("compliance_data", {}).get("risk_assessment", {}).get("level", "N/A")}

        Best regards,
        Compliance Monitoring System
        """

        # Send email with attachment
        success = await send_report_email(
            recipients=recipients,
            subject=subject,
            body=body,
            attachment_path=state["report_data"]["file_path"],
        )

        if success:
            state["report_data"]["distribution_status"] = "sent"
            state["report_data"]["sent_to"] = recipients
            state["report_data"]["sent_at"] = datetime.now().isoformat()

            # Add to history
            state["history"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "action": "report_distributed",
                    "recipients": recipients,
                    "status": "success",
                }
            )

            logger.info(f"Report distributed to {len(recipients)} recipients")
        else:
            raise Exception("Failed to send report email")

    except Exception as e:
        logger.error(f"Error distributing report: {e}")
        state["errors"].append(
            {
                "type": "EmailError",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        state["report_data"]["distribution_status"] = "failed"
        raise

    return state


async def cleanup_old_reports_node(
    state: UnifiedComplianceState,
) -> UnifiedComplianceState:
    """
    Clean up old report files based on retention policy.

    Migrated from workers/reporting_tasks.py::cleanup_old_reports

    This node:
    - Identifies reports older than retention period
    - Deletes expired report files
    - Tracks cleanup statistics

    Args:
        state: Current workflow state

    Returns:
        Updated state with cleanup results
    """
    logger.info(f"Starting report cleanup for workflow {state.get('workflow_id')}")

    # Get retention settings
    retention_days = state.get("metadata", {}).get("retention_days", 90)
    report_directory = state.get("metadata", {}).get(
        "report_directory", getattr(settings, "REPORT_DIRECTORY", "/tmp/reports")
    )

    # Initialize cleanup data
    state["cleanup_data"] = state.get("cleanup_data", {})

    try:
        report_path = Path(report_directory)
        if not report_path.exists():
            logger.info(f"Report directory does not exist: {report_directory}")
            state["cleanup_data"]["deleted_count"] = 0
            state["cleanup_data"]["deleted_files"] = []
            return state

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        deleted_files = []
        deleted_count = 0

        # Iterate through report files
        for file_path in report_path.glob("*"):
            if file_path.is_file():
                # Check file age
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                if file_mtime < cutoff_date:
                    try:
                        file_path.unlink()
                        deleted_files.append(str(file_path))
                        deleted_count += 1
                        logger.debug(f"Deleted old report: {file_path}")
                    except PermissionError as pe:
                        logger.warning(f"Permission denied deleting {file_path}: {pe}")
                        state["errors"].append(
                            {
                                "type": "PermissionError",
                                "message": f"Cannot delete {file_path}: {pe}",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                        state["error_count"] += 1

        # Update state with cleanup results
        state["cleanup_data"]["deleted_count"] = deleted_count
        state["cleanup_data"]["deleted_files"] = deleted_files
        state["cleanup_data"]["retention_days"] = retention_days
        state["cleanup_data"]["cleanup_timestamp"] = datetime.now().isoformat()

        # Add to history
        state["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "old_reports_cleaned",
                "deleted_count": deleted_count,
                "retention_days": retention_days,
            }
        )

        logger.info(f"Cleanup completed: deleted {deleted_count} old reports")

    except Exception as e:
        logger.error(f"Error during report cleanup: {e}")
        state["errors"].append(
            {
                "type": "CleanupError",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        raise

    return state


def prepare_report_data(compliance_data: Dict[str, Any], report_type: str) -> Dict[str, Any]:
    """
    Prepare report data based on report type.

    Args:
        compliance_data: Compliance check and risk assessment data
        report_type: Type of report to generate

    Returns:
        Formatted report data
    """
    report_data = {
        "generated_at": datetime.now().isoformat(),
        "report_type": report_type,
    }

    if report_type == "compliance_summary":
        check_results = compliance_data.get("check_results", {})
        report_data.update(
            {
                "title": "Compliance Summary Report",
                "summary": f"Compliance Score: {check_results.get('compliance_score', 0):.1f}%",
                "details": {
                    "compliance_score": check_results.get("compliance_score"),
                    "total_obligations": check_results.get("total_obligations"),
                    "satisfied_obligations": check_results.get("satisfied_obligations"),
                    "violations": check_results.get("violations", []),
                    "regulation": check_results.get("regulation"),
                },
            }
        )

    elif report_type == "risk_assessment":
        risk_data = compliance_data.get("risk_assessment", {})
        report_data.update(
            {
                "title": "Risk Assessment Report",
                "summary": f"Risk Level: {risk_data.get('level', 'UNKNOWN')}",
                "details": risk_data,
            }
        )

    elif report_type == "detailed":
        report_data.update(
            {
                "title": "Detailed Compliance Report",
                "summary": "Complete compliance and risk analysis",
                "details": compliance_data,
            }
        )

    else:
        # Default to including all data
        report_data.update(
            {
                "title": f"Report - {report_type}",
                "summary": "Generated report",
                "details": compliance_data,
            }
        )

    return report_data


async def generate_pdf_report(report_data: Dict[str, Any]) -> bytes:
    """
    Generate PDF report from report data.

    Note: This is a simplified implementation. In production,
    use a proper PDF generation library like reportlab or weasyprint.

    Args:
        report_data: Formatted report data

    Returns:
        PDF content as bytes
    """
    # For now, create a simple text representation
    # In production, use reportlab or similar PDF library

    pdf_content = f"""
    {report_data.get("title", "Compliance Report")}
    {"=" * 50}

    Generated: {report_data.get("generated_at")}

    {report_data.get("summary", "")}

    Details:
    {json.dumps(report_data.get("details", {}), indent=2)}
    """

    # In production, convert to actual PDF
    # For now, return as bytes
    return pdf_content.encode()


def generate_html_report(report_data: Dict[str, Any]) -> str:
    """
    Generate HTML report from report data.

    Args:
        report_data: Formatted report data

    Returns:
        HTML content as string
    """
    details_html = ""
    details = report_data.get("details", {})

    if isinstance(details, dict):
        for key, value in details.items():
            if isinstance(value, (list, dict)):
                value = f"<pre>{json.dumps(value, indent=2)}</pre>"
            details_html += f"<tr><td><strong>{key}</strong></td><td>{value}</td></tr>"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{report_data.get("title", "Report")}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; }}
            td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            pre {{ background-color: #f5f5f5; padding: 10px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>{report_data.get("title", "Report")}</h1>
        <p><strong>Generated:</strong> {report_data.get("generated_at")}</p>
        <h2>Summary</h2>
        <p>{report_data.get("summary", "")}</p>
        <h2>Details</h2>
        <table>
            {details_html}
        </table>
    </body>
    </html>
    """

    return html_content


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


async def send_report_email(
    recipients: List[str],
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
) -> bool:
    """
    Send report email to recipients.

    Args:
        recipients: List of email addresses
        subject: Email subject
        body: Email body text
        attachment_path: Optional path to report file to attach

    Returns:
        True if email sent successfully
    """
    try:
        # Get email configuration from settings
        smtp_host = getattr(settings, "SMTP_HOST", "localhost")
        smtp_port = getattr(settings, "SMTP_PORT", 587)
        smtp_user = getattr(settings, "SMTP_USER", None)
        smtp_password = getattr(settings, "SMTP_PASSWORD", None)
        from_email = getattr(settings, "FROM_EMAIL", "compliance@example.com")

        # Create message
        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        # Add body
        msg.attach(MIMEText(body, "plain"))

        # Add attachment if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(attachment_path)}",
                )
                msg.attach(part)

        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_user and smtp_password:
                server.starttls()
                server.login(smtp_user, smtp_password)

            text = msg.as_string()
            server.sendmail(from_email, recipients, text)

        logger.info(f"Email sent to {len(recipients)} recipients")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise


async def reporting_node(state: UnifiedComplianceState) -> UnifiedComplianceState:
    """
    Main reporting node that orchestrates report generation and distribution.

    This is the main entry point for the reporting workflow in the LangGraph.
    It coordinates between generate_report_node and distribute_report_node.

    Args:
        state: Current state with compliance data and reporting requirements

    Returns:
        Updated state with report data and distribution status
    """
    logger.info(f"Starting reporting workflow for workflow_id: {state.get('workflow_id')}")

    try:
        # Step 1: Generate the report
        state = await generate_report_node(state)

        # Check if report generation succeeded
        if state.get("error_count", 0) > 0:
            logger.error("Report generation failed, skipping distribution")
            return state

        # Step 2: Distribute the report if requested
        if state.get("metadata", {}).get("distribute_report", True):
            state = await distribute_report_node(state)
        else:
            logger.info("Report distribution skipped as per configuration")

        # Step 3: Cleanup old reports if configured
        if state.get("metadata", {}).get("cleanup_old_reports", False):
            state = await cleanup_old_reports_node(state)

        # Add completion status to history
        history = state.get("history", [])
        history.append(
            {
                "step": "reporting_complete",
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
            }
        )
        state["history"] = history

        logger.info(f"Reporting workflow completed for workflow_id: {state.get('workflow_id')}")

    except Exception as e:
        logger.error(f"Error in reporting workflow: {str(e)}")
        errors = state.get("errors", [])
        errors.append(
            {
                "type": "ReportingWorkflowError",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["errors"] = errors
        state["error_count"] = state.get("error_count", 0) + 1

    return state
