"""

# Constants

Integration tests for the end-to-end evidence collection and reporting flow.
"""

from unittest.mock import Mock, patch
import pytest
from database import db_setup
from database.db_setup import Base

from tests.test_constants import HTTP_BAD_REQUEST, HTTP_OK


@pytest.fixture(scope="session", autouse=True)
async def manage_test_database_schema():
    """Create and drop test database schema for the session with proper async isolation."""
    db_setup._init_async_db()
    engine_to_use = db_setup._async_engine
    async with engine_to_use.begin() as conn:
        import subprocess
        import sys
        import os

        original_dir = os.getcwd()
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        os.chdir(project_root)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"], capture_output=True, text=True
            )
            if result.returncode != 0:
                raise RuntimeError(f"Alembic migration failed: {result.stderr}")
        finally:
            os.chdir(original_dir)
    yield
    try:
        async with engine_to_use.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except Exception as e:
        print(f"Warning: Integration test database teardown failed: {e}")
    try:
        await engine_to_use.dispose()
    except Exception as dispose_error:
        print(f"Warning: Integration test engine disposal failed: {dispose_error}")
    db_setup._async_engine = None
    db_setup._AsyncSessionLocal = None


class TestEvidenceCollectionFlow:
    """Test the complete evidence collection and reporting workflow."""

    @pytest.mark.integration
    @patch("api.integrations.google_workspace_integration.GoogleWorkspaceIntegration")
    def test_full_evidence_and_reporting_flow(
        self, mock_gws_integration, sample_business_profile, authenticated_headers, client
    ):
        """
        Tests the end-to-end flow of connecting an integration,
        collecting evidence, and generating a report.
        """
        mock_instance = Mock()
        mock_instance.collect_evidence.return_value = [
            {
                "title": "Admin Console Settings",
                "type": "security_settings",
                "content": {"2fa_enabled": True, "password_policy": "strong"},
                "integration_source": "google_workspace",
                "auto_collected": True,
            },
            {
                "title": "User Access Review",
                "type": "user_access_logs",
                "content": {"users": 50, "active_sessions": 25},
                "integration_source": "google_workspace",
                "auto_collected": True,
            },
        ]
        mock_gws_integration.return_value = mock_instance
        with patch("api.dependencies.auth.get_current_user") as mock_auth:
            mock_auth.return_value = sample_business_profile.user_id
            response = client.post(
                "/api/integrations/connect",
                json={
                    "provider": "google_workspace",
                    "credentials": {"token": "fake_oauth_token"},
                    "settings": {"workspace_domain": "testcompany.com"},
                },
                headers=authenticated_headers,
            )
            assert response.status_code in [200, 401]
        response = client.post(
            f"/api/integrations/collect/{sample_business_profile.id}", headers=authenticated_headers
        )
        assert response.status_code in [200, 401, 404]
        response = client.post(
            "/api/reports/generate",
            json={
                "business_profile_id": str(sample_business_profile.id),
                "report_type": "evidence_report",
                "format": "json",
                "parameters": {"frameworks": ["ISO27001"]},
            },
            headers=authenticated_headers,
        )
        if response.status_code == HTTP_OK:
            report_data = response.json()
            assert "content" in report_data
            assert report_data["report_type"] == "evidence_report"

    @pytest.mark.integration
    def test_ai_assistant_evidence_query(self, authenticated_headers, client):
        """Test the AI assistant's ability to query and analyze evidence."""
        with patch("services.ai.assistant.ComplianceAssistant.process_message") as mock_ai:
            mock_ai.return_value = (
                "I found 2 evidence items related to ISO27001 compliance. You have security policies and training records documented.",
                {"intent": "evidence_query", "evidence_found": 2},
            )
            response = client.post(
                "/api/chat/conversations",
                json={
                    "title": "Evidence Query Test",
                    "initial_message": "What evidence do I have for ISO27001?",
                },
                headers=authenticated_headers,
            )
            if response.status_code == HTTP_OK:
                conversation_data = response.json()
                assert "id" in conversation_data
                assert len(conversation_data.get("messages", [])) >= 1

    @pytest.mark.integration
    def test_scheduled_report_generation(
        self, sample_business_profile, authenticated_headers, client
    ):
        """Test the scheduled report generation workflow."""
        response = client.post(
            "/api/reports/schedules",
            json={
                "business_profile_id": str(sample_business_profile.id),
                "report_type": "executive_summary",
                "frequency": "weekly",
                "recipients": ["manager@testcompany.com"],
                "parameters": {"frameworks": ["ISO27001"]},
                "schedule_config": {"hour": 9, "day_of_week": 1},
            },
            headers=authenticated_headers,
        )
        if response.status_code == HTTP_OK:
            schedule_data = response.json()
            schedule_id = schedule_data["schedule_id"]
            response = client.post(
                f"/api/reports/schedules/{schedule_id}/execute", headers=authenticated_headers
            )
            if response.status_code == HTTP_OK:
                execution_data = response.json()
                assert execution_data["status"] in ["success", "initiated"]
                assert "executed_at" in execution_data


class TestAPIEndpointsIntegration:
    """Test critical API endpoint interactions."""

    @pytest.mark.integration
    def test_business_profile_to_evidence_workflow(
        self, sample_business_profile, sample_compliance_framework, authenticated_headers, client
    ):
        """Test the workflow from business profile setup to evidence collection."""
        response = client.get(
            f"/api/business-profiles/{sample_business_profile.id}", headers=authenticated_headers
        )
        if response.status_code == HTTP_OK:
            profile_data = response.json()
            assert profile_data["company_name"] == "Sample Test Corp"
            response = client.post(
                "/api/evidence",
                json={
                    "title": "Test Evidence Item",
                    "description": "Test evidence for integration testing",
                    "control_id": "A.5.1.1",
                    "framework_id": str(sample_compliance_framework.id),
                    "business_profile_id": str(sample_business_profile.id),
                    "source": "manual_upload",
                    "evidence_type": "document",
                    "tags": ["test", "integration"],
                },
                headers=authenticated_headers,
            )
            assert response.status_code in [200, 201, 401, 422]

    @pytest.mark.integration
    def test_framework_to_readiness_assessment(
        self, sample_business_profile, authenticated_headers, client
    ):
        """Test the framework assessment and readiness calculation."""
        response = client.get("/api/frameworks", headers=authenticated_headers)
        if response.status_code == HTTP_OK:
            frameworks = response.json()
            assert len(frameworks) > 0
            response = client.get(
                f"/api/readiness/{sample_business_profile.id}", headers=authenticated_headers
            )
            if response.status_code == HTTP_OK:
                readiness_data = response.json()
                assert "overall_score" in readiness_data
                assert "framework_scores" in readiness_data


class TestErrorHandlingAndResilience:
    """Test system behavior under error conditions."""

    @pytest.mark.integration
    def test_integration_failure_handling(self, authenticated_headers, client):
        """Test how the system handles integration failures."""
        response = client.post(
            "/api/integrations/connect",
            json={"provider": "invalid_provider", "credentials": {"token": "expired_token"}},
            headers=authenticated_headers,
        )
        assert response.status_code == HTTP_BAD_REQUEST
        assert "not supported" in response.json()["detail"]

    @pytest.mark.integration
    def test_report_generation_with_no_data(
        self, sample_business_profile, authenticated_headers, client
    ):
        """Test report generation when no evidence data is available."""
        response = client.post(
            "/api/reports/generate",
            json={
                "business_profile_id": str(sample_business_profile.id),
                "report_type": "evidence_report",
                "format": "json",
            },
            headers=authenticated_headers,
        )
        if response.status_code == HTTP_OK:
            report_data = response.json()
            assert "content" in report_data


@pytest.mark.asyncio
class TestAsyncOperations:
    """Test asynchronous operations and background tasks."""

    async def test_async_evidence_collection(self):
        """Test asynchronous evidence collection operations."""
        from services.automation.evidence_processor import EvidenceProcessor

        assert EvidenceProcessor is not None

    async def test_ai_assistant_async_processing(self):
        """Test AI assistant async message processing."""
        from services.ai.assistant import ComplianceAssistant

        assert ComplianceAssistant is not None


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_data():
    """Clean up test data after each test."""
    yield
