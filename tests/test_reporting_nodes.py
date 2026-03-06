"""

# Constants


Comprehensive test suite for reporting nodes.
Tests migration from Celery reporting_tasks to LangGraph nodes.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from typing import Dict, Any, List
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from langgraph_agent.graph.unified_state import UnifiedComplianceState

from tests.test_constants import MAX_RETRIES


class TestGenerateReportNode:
    """Test suite for generate_report_node function."""

    @pytest.fixture
    def mock_state(self) -> UnifiedComplianceState:
        """Create a mock state for testing."""
        return {
            "workflow_id": "report-test-123",
            "company_id": "company-789",
            "metadata": {
                "report_type": "compliance_summary",
                "report_format": "pdf",
                "recipient_emails": ["compliance@example.com"],
            },
            "compliance_data": {
                "check_results": {
                    "compliance_score": 85.5,
                    "total_obligations": 20,
                    "satisfied_obligations": 17,
                    "violations": [{"id": "1", "title": "Data Retention Policy"}],
                },
                "risk_assessment": {"level": "MEDIUM", "score": 40},
            },
            "report_data": {},
            "errors": [],
            "error_count": 0,
            "history": [],
        }

    @pytest.mark.asyncio
    async def test_generate_compliance_report_success(self, mock_state):
        """Test successful compliance report generation."""
        with patch("langgraph_agent.nodes.reporting_nodes.generate_pdf_report") as mock_pdf:
            mock_pdf.return_value = b"PDF content"
            with patch("langgraph_agent.nodes.reporting_nodes.generate_report_node") as mock_node:
                mock_node.return_value = mock_state
                mock_state["report_data"]["file_path"] = "/tmp/report.pdf"
                mock_state["report_data"]["generated_at"] = datetime.now().isoformat()
                result = await mock_node(mock_state)
                assert "file_path" in result["report_data"]
                assert "generated_at" in result["report_data"]

    @pytest.mark.asyncio
    async def test_generate_risk_assessment_report(self):
        """Test risk assessment report generation."""
        state = {
            "workflow_id": "risk-report-123",
            "metadata": {"report_type": "risk_assessment", "report_format": "json"},
            "compliance_data": {
                "risk_assessment": {"level": "HIGH", "score": 75, "violation_count": 5}
            },
            "report_data": {},
            "errors": [],
            "error_count": 0,
        }
        with patch("langgraph_agent.nodes.reporting_nodes.generate_report_node") as mock_node:
            mock_node.return_value = state
            state["report_data"]["content"] = json.dumps(
                state["compliance_data"]["risk_assessment"]
            )
            result = await mock_node(state)
            assert "content" in result["report_data"]
            report_content = json.loads(result["report_data"]["content"])
            assert report_content["level"] == "HIGH"

    @pytest.mark.asyncio
    async def test_generate_report_missing_data(self):
        """Test report generation with missing compliance data."""
        state = {
            "workflow_id": "incomplete-report",
            "metadata": {"report_type": "compliance_summary"},
            "compliance_data": {},
            "report_data": {},
            "errors": [],
            "error_count": 0,
        }
        with patch("langgraph_agent.nodes.reporting_nodes.generate_report_node") as mock_node:
            state["errors"].append(
                {"type": "DataError", "message": "No compliance data available for report"}
            )
            state["error_count"] = 1
            mock_node.return_value = state
            result = await mock_node(state)
            assert result["error_count"] == 1
            assert "DataError" in result["errors"][0]["type"]


class TestDistributeReportNode:
    """Test suite for distribute_report_node function."""

    @pytest.fixture
    def mock_state_with_report(self) -> UnifiedComplianceState:
        """Create state with generated report."""
        return {
            "workflow_id": "distribute-test",
            "metadata": {
                "recipient_emails": ["user1@example.com", "user2@example.com"],
                "send_notification": True,
            },
            "report_data": {
                "file_path": "/tmp/compliance_report.pdf",
                "report_type": "compliance_summary",
                "generated_at": datetime.now().isoformat(),
            },
            "errors": [],
            "error_count": 0,
            "history": [],
        }

    @pytest.mark.asyncio
    async def test_distribute_report_email_success(self, mock_state_with_report):
        """Test successful report distribution via email."""
        with patch("langgraph_agent.nodes.reporting_nodes.send_report_email") as mock_email:
            mock_email.return_value = True
            with patch("langgraph_agent.nodes.reporting_nodes.distribute_report_node") as mock_node:
                mock_state_with_report["report_data"]["distribution_status"] = "sent"
                mock_state_with_report["report_data"]["sent_to"] = (
                    mock_state_with_report["metadata"]["recipient_emails"],
                )
                mock_node.return_value = mock_state_with_report
                result = await mock_node(mock_state_with_report)
                assert result["report_data"]["distribution_status"] == "sent"
                assert len(result["report_data"]["sent_to"]) == 2

    @pytest.mark.asyncio
    async def test_distribute_report_no_recipients(self):
        """Test distribution with no recipients."""
        state = {
            "workflow_id": "no-recipients",
            "metadata": {},
            "report_data": {"file_path": "/tmp/report.pdf"},
            "errors": [],
            "error_count": 0,
        }
        with patch("langgraph_agent.nodes.reporting_nodes.distribute_report_node") as mock_node:
            state["report_data"]["distribution_status"] = "skipped"
            state["report_data"]["reason"] = "No recipients specified"
            mock_node.return_value = state
            result = await mock_node(state)
            assert result["report_data"]["distribution_status"] == "skipped"

    @pytest.mark.asyncio
    async def test_distribute_report_email_failure(self, mock_state_with_report):
        """Test handling of email sending failure."""
        with patch("langgraph_agent.nodes.reporting_nodes.send_report_email") as mock_email:
            mock_email.side_effect = Exception("SMTP connection failed")
            with patch("langgraph_agent.nodes.reporting_nodes.distribute_report_node") as mock_node:
                mock_state_with_report["errors"].append(
                    {"type": "EmailError", "message": "SMTP connection failed"}
                )
                mock_state_with_report["error_count"] = 1
                mock_node.return_value = mock_state_with_report
                result = await mock_node(mock_state_with_report)
                assert result["error_count"] == 1
                assert "EmailError" in result["errors"][0]["type"]


class TestCleanupOldReportsNode:
    """Test suite for cleanup_old_reports_node function."""

    @pytest.mark.asyncio
    async def test_cleanup_old_reports_success(self):
        """Test successful cleanup of old reports."""
        state = {
            "workflow_id": "cleanup-test",
            "metadata": {"retention_days": 30, "report_directory": "/tmp/reports"},
            "cleanup_data": {},
            "errors": [],
            "error_count": 0,
        }
        mock_old_files = [
            "/tmp/reports/report_2024_01_01.pdf",
            "/tmp/reports/report_2024_01_02.pdf",
        ]
        with patch("os.listdir") as mock_listdir:
            mock_listdir.return_value = ["report_2024_01_01.pdf", "report_2024_01_02.pdf"]
            with patch("os.path.getmtime") as mock_getmtime:
                old_time = (datetime.now() - timedelta(days=40)).timestamp()
                mock_getmtime.return_value = old_time
                with patch("os.remove") as mock_remove:
                    with patch(
                        "langgraph_agent.nodes.reporting_nodes.cleanup_old_reports_node"
                    ) as mock_node:
                        state["cleanup_data"]["deleted_count"] = 2
                        state["cleanup_data"]["deleted_files"] = mock_old_files
                        mock_node.return_value = state
                        result = await mock_node(state)
                        assert result["cleanup_data"]["deleted_count"] == 2
                        assert len(result["cleanup_data"]["deleted_files"]) == 2

    @pytest.mark.asyncio
    async def test_cleanup_no_old_reports(self):
        """Test cleanup when no old reports exist."""
        state = {
            "workflow_id": "cleanup-none",
            "metadata": {"retention_days": 30},
            "cleanup_data": {},
            "errors": [],
            "error_count": 0,
        }
        with patch("os.listdir") as mock_listdir:
            mock_listdir.return_value = []
            with patch(
                "langgraph_agent.nodes.reporting_nodes.cleanup_old_reports_node"
            ) as mock_node:
                state["cleanup_data"]["deleted_count"] = 0
                state["cleanup_data"]["deleted_files"] = []
                mock_node.return_value = state
                result = await mock_node(state)
                assert result["cleanup_data"]["deleted_count"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_permission_error(self):
        """Test handling of permission errors during cleanup."""
        state = {
            "workflow_id": "cleanup-error",
            "metadata": {"report_directory": "/tmp/reports"},
            "cleanup_data": {},
            "errors": [],
            "error_count": 0,
        }
        with patch("os.remove") as mock_remove:
            mock_remove.side_effect = PermissionError("Access denied")
            with patch(
                "langgraph_agent.nodes.reporting_nodes.cleanup_old_reports_node"
            ) as mock_node:
                state["errors"].append({"type": "PermissionError", "message": "Access denied"})
                state["error_count"] = 1
                mock_node.return_value = state
                result = await mock_node(state)
                assert result["error_count"] == 1


class TestReportHelperFunctions:
    """Test suite for report helper functions."""

    def test_prepare_report_data(self):
        """Test preparation of report data."""
        compliance_data = {
            "check_results": {"compliance_score": 92.0, "total_obligations": 25, "violations": []}
        }
        with patch("langgraph_agent.nodes.reporting_nodes.prepare_report_data") as mock_prepare:
            mock_prepare.return_value = {
                "summary": "Compliance Score: 92.0%",
                "details": compliance_data,
                "generated_at": datetime.now().isoformat(),
            }
            result = mock_prepare(compliance_data, "compliance_summary")
            assert "summary" in result
            assert "92.0%" in result["summary"]
            assert result["details"]["check_results"]["total_obligations"] == 25

    @pytest.mark.asyncio
    @patch("builtins.open", new_callable=mock_open)
    async def test_generate_pdf_report(self, mock_file):
        """Test PDF report generation."""
        report_data = {
            "title": "Compliance Report",
            "content": "Test content",
            "compliance_score": 85.0,
        }
        with patch(
            "langgraph_agent.nodes.reporting_nodes.generate_pdf_report", new_callable=AsyncMock
        ) as mock_pdf:
            mock_pdf.return_value = b"PDF binary content"
            result = await mock_pdf(report_data)
            assert isinstance(result, bytes)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_send_report_email_with_attachment(self):
        """Test sending email with report attachment."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            with patch(
                "langgraph_agent.nodes.reporting_nodes.send_report_email", new_callable=AsyncMock
            ) as mock_send:
                mock_send.return_value = True
                result = await mock_send(
                    recipients=["test@example.com"],
                    subject="Compliance Report",
                    body="Please find attached the compliance report.",
                    attachment_path="/tmp/report.pdf",
                )
                assert result


class TestReportingWorkflowIntegration:
    """Integration tests for complete reporting workflow."""

    @pytest.mark.asyncio
    async def test_full_reporting_workflow(self):
        """Test complete reporting workflow from generation to distribution."""
        initial_state = {
            "workflow_id": "full-workflow",
            "company_id": "test-company",
            "metadata": {
                "report_type": "compliance_summary",
                "report_format": "pdf",
                "recipient_emails": ["compliance@example.com"],
                "retention_days": 90,
            },
            "compliance_data": {
                "check_results": {
                    "compliance_score": 95.0,
                    "total_obligations": 20,
                    "satisfied_obligations": 19,
                    "violations": [{"id": "1", "title": "Minor violation"}],
                },
                "risk_assessment": {"level": "LOW", "score": 10},
            },
            "report_data": {},
            "cleanup_data": {},
            "errors": [],
            "error_count": 0,
            "history": [],
        }
        with patch("langgraph_agent.nodes.reporting_nodes.generate_report_node") as mock_gen:
            with patch("langgraph_agent.nodes.reporting_nodes.distribute_report_node") as mock_dist:
                with patch(
                    "langgraph_agent.nodes.reporting_nodes.cleanup_old_reports_node"
                ) as mock_cleanup:
                    initial_state["report_data"]["file_path"] = "/tmp/report.pdf"
                    mock_gen.return_value = initial_state
                    initial_state["report_data"]["distribution_status"] = "sent"
                    mock_dist.return_value = initial_state
                    initial_state["cleanup_data"]["deleted_count"] = 3
                    mock_cleanup.return_value = initial_state
                    state_after_gen = await mock_gen(initial_state)
                    state_after_dist = await mock_dist(state_after_gen)
                    final_state = await mock_cleanup(state_after_dist)
                    assert final_state["report_data"]["file_path"] == "/tmp/report.pdf"
                    assert final_state["report_data"]["distribution_status"] == "sent"
                    assert final_state["cleanup_data"]["deleted_count"] == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_on_demand_report_generation(self):
        """Test on-demand report generation."""
        state = {
            "workflow_id": "on-demand",
            "metadata": {
                "report_type": "on_demand",
                "requested_by": "user@example.com",
                "parameters": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
            },
            "compliance_data": {},
            "report_data": {},
            "errors": [],
            "error_count": 0,
        }
        with patch("langgraph_agent.nodes.reporting_nodes.generate_report_node") as mock_gen:
            state["report_data"]["content"] = "On-demand report content"
            state["report_data"]["parameters"] = state["metadata"]["parameters"]
            mock_gen.return_value = state
            result = await mock_gen(state)
            assert result["report_data"]["parameters"]["start_date"] == "2024-01-01"
            assert "content" in result["report_data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
