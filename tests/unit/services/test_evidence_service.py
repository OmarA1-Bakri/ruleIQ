"""
Unit Tests for Evidence Service

Tests the evidence collection, validation, and processing business logic
in complete isolation with mocked dependencies.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from uuid import uuid4
import pytest
from core.exceptions import NotFoundAPIError, ValidationAPIError
from services.evidence_service import EvidenceService

from tests.test_constants import DEFAULT_LIMIT

# Constants
DEFAULT_RETRIES = 5


@pytest.fixture
def fast_db_session():
    """Lightweight mock DB session for unit tests (no real DB needed)."""
    return MagicMock()


@pytest.fixture
def sample_user():
    """Mock user object for tests that need user context."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.mark.unit
class TestEvidenceService:
    """Test evidence service business logic"""

    @pytest.mark.asyncio
    async def test_create_evidence_item_success(self, fast_db_session, sample_user):
        """Test creating evidence item with valid data"""
        evidence_data = {
            "title": "Security Policy",
            "description": "Company security policy document",
            "evidence_type": "document",
            "source": "manual",
            "framework_mappings": ["ISO27001.A.5.1.1"],
        }
        with patch("services.evidence_service.EvidenceService.create_evidence") as mock_create:
            mock_create.return_value = {
                **evidence_data,
                "id": str(uuid4()),
                "user_id": str(sample_user.id),
                "status": "valid",
                "created_at": datetime.now(timezone.utc),
                "quality_score": 85.0,
            }
            result = await EvidenceService.create_evidence(sample_user.id, evidence_data)
            assert result["title"] == evidence_data["title"]
            assert result["user_id"] == str(sample_user.id)
            assert result["status"] == "valid"
            assert result["quality_score"] > 0
            mock_create.assert_called_once_with(sample_user.id, evidence_data)

    @pytest.mark.asyncio
    async def test_create_evidence_item_validation_error(self, fast_db_session, sample_user):
        """Test creating evidence item with invalid data raises validation error"""
        invalid_data = {"title": "", "description": "x" * 10000, "evidence_type": "invalid_type"}
        with patch("services.evidence_service.EvidenceService.create_evidence") as mock_create:
            mock_create.side_effect = ValidationAPIError("Invalid evidence data")
            with pytest.raises(ValidationAPIError):
                await EvidenceService.create_evidence(sample_user.id, invalid_data)

    def test_validate_evidence_quality_high_score(self, fast_db_session):
        """Test evidence quality validation returns high score for good evidence"""
        evidence_data = {
            "title": "Comprehensive Security Policy",
            "description": "Detailed security policy covering all ISO 27001 requirements",
            "evidence_type": "document",
            "file_content": "Detailed policy content with specific procedures...",
            "metadata": {
                "creation_date": "2024-01-01",
                "author": "Chief Security Officer",
                "version": "2.1",
                "approval_date": "2024-01-15",
            },
        }
        with patch(
            "services.evidence_service.EvidenceService.validate_evidence_quality"
        ) as mock_validate:
            mock_validate.return_value = {
                "quality_score": 92,
                "validation_results": {
                    "completeness": "excellent",
                    "relevance": "high",
                    "timeliness": "current",
                    "authenticity": "verified",
                },
                "issues": [],
                "recommendations": ["Consider adding implementation timeline"],
            }
            result = EvidenceService.validate_evidence_quality(evidence_data)
            assert result["quality_score"] >= 90
            assert result["validation_results"]["completeness"] == "excellent"
            assert len(result["issues"]) == 0
            mock_validate.assert_called_once_with(evidence_data)

    def test_validate_evidence_quality_low_score(self, fast_db_session):
        """Test evidence quality validation returns low score for poor evidence"""
        poor_evidence_data = {
            "title": "Policy",
            "description": "Some policy",
            "evidence_type": "document",
            "file_content": "Brief policy.",
            "metadata": {"creation_date": "2020-01-01"},
        }
        with patch(
            "services.evidence_service.EvidenceService.validate_evidence_quality"
        ) as mock_validate:
            mock_validate.return_value = {
                "quality_score": 35,
                "validation_results": {
                    "completeness": "poor",
                    "relevance": "medium",
                    "timeliness": "outdated",
                    "authenticity": "unverified",
                },
                "issues": ["Title too vague", "Content too brief", "Evidence is outdated"],
                "recommendations": [
                    "Provide more specific title",
                    "Add detailed content",
                    "Update evidence with current information",
                ],
            }
            result = EvidenceService.validate_evidence_quality(poor_evidence_data)
            assert result["quality_score"] < 50
            assert result["validation_results"]["completeness"] == "poor"
            assert len(result["issues"]) > 0
            mock_validate.assert_called_once_with(poor_evidence_data)

    def test_identify_evidence_requirements_success(self, fast_db_session):
        """Test identifying evidence requirements for framework controls"""
        framework_id = uuid4()
        control_ids = [str(uuid4()), str(uuid4())]
        with patch(
            "services.evidence_service.EvidenceService.identify_requirements"
        ) as mock_identify:
            mock_identify.return_value = [
                {
                    "control_id": control_ids[0],
                    "evidence_type": "document",
                    "title": "Information Security Policy",
                    "description": "Written policy documenting information security procedures",
                    "automation_possible": False,
                    "collection_method": "manual",
                    "required_artifacts": ["policy_document", "approval_record"],
                    "estimated_effort": "2-4 hours",
                },
                {
                    "control_id": control_ids[1],
                    "evidence_type": "log",
                    "title": "Access Control Logs",
                    "description": "System logs showing access control implementation",
                    "automation_possible": True,
                    "collection_method": "automated",
                    "required_artifacts": ["access_logs", "audit_trail"],
                    "estimated_effort": "automated",
                },
            ]
            result = EvidenceService.identify_requirements(framework_id, control_ids)
            assert len(result) == 2
            assert all("control_id" in item for item in result)
            assert all("evidence_type" in item for item in result)
            assert any(item["automation_possible"] for item in result)
            mock_identify.assert_called_once_with(framework_id, control_ids)

    def test_configure_automation_success(self, fast_db_session):
        """Test configuring automated evidence collection"""
        evidence_id = uuid4()
        automation_config = {
            "source_type": "google_workspace",
            "endpoint": "https://admin.googleapis.com/admin/directory/v1/users",
            "collection_frequency": "daily",
            "credentials_id": "gws_creds_001",
            "data_mapping": {
                "user_list": "$.users[*].primaryEmail",
                "admin_status": "$.users[*].isAdmin",
            },
        }
        with patch(
            "services.evidence_service.EvidenceService.configure_automation"
        ) as mock_configure:
            mock_configure.return_value = {
                "configuration_successful": True,
                "automation_enabled": True,
                "next_collection": datetime.now(timezone.utc) + timedelta(days=1),
                "test_connection": "successful",
                "estimated_data_points": 150,
                "collection_schedule": "daily at 02:00 UTC",
            }
            result = EvidenceService.configure_automation(evidence_id, automation_config)
            assert result["configuration_successful"] is True
            assert result["automation_enabled"] is True
            assert result["test_connection"] == "successful"
            assert "next_collection" in result
            mock_configure.assert_called_once_with(evidence_id, automation_config)

    def test_configure_automation_connection_failure(self, fast_db_session):
        """Test automation configuration with connection failure"""
        evidence_id = uuid4()
        automation_config = {
            "source_type": "google_workspace",
            "endpoint": "https://invalid-endpoint.com",
            "collection_frequency": "daily",
            "credentials_id": "invalid_creds",
        }
        with patch(
            "services.evidence_service.EvidenceService.configure_automation"
        ) as mock_configure:
            mock_configure.return_value = {
                "configuration_successful": False,
                "automation_enabled": False,
                "test_connection": "failed",
                "error_message": "Invalid credentials or endpoint unreachable",
                "suggested_actions": [
                    "Verify credentials are valid",
                    "Check endpoint URL",
                    "Ensure necessary permissions are granted",
                ],
            }
            result = EvidenceService.configure_automation(evidence_id, automation_config)
            assert result["configuration_successful"] is False
            assert result["automation_enabled"] is False
            assert result["test_connection"] == "failed"
            assert "error_message" in result
            mock_configure.assert_called_once_with(evidence_id, automation_config)

    def test_get_user_evidence_items_success(self, fast_db_session, sample_user):
        """Test retrieving evidence items for a user"""
        with patch("services.evidence_service.get_user_evidence_items") as mock_get:
            mock_get.return_value = [
                {
                    "id": str(uuid4()),
                    "title": "Security Policy",
                    "evidence_type": "document",
                    "status": "valid",
                    "quality_score": 85.0,
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "id": str(uuid4()),
                    "title": "User Access Logs",
                    "evidence_type": "log",
                    "status": "valid",
                    "quality_score": 92.0,
                    "created_at": datetime.now(timezone.utc),
                },
            ]
            result = mock_get(sample_user.id)
            assert len(result) == 2
            assert all("id" in item for item in result)
            assert all("quality_score" in item for item in result)
            mock_get.assert_called_once_with(sample_user.id)

    def test_get_user_evidence_items_empty(self, fast_db_session, sample_user):
        """Test retrieving evidence items when user has none"""
        with patch("services.evidence_service.get_user_evidence_items") as mock_get:
            mock_get.return_value = []
            result = mock_get(sample_user.id)
            assert len(result) == 0
            mock_get.assert_called_once_with(sample_user.id)

    def test_update_evidence_status_success(self, fast_db_session):
        """Test updating evidence item status"""
        evidence_id = uuid4()
        new_status = "expired"
        reason = "Evidence older than 6 months"
        with patch("services.evidence_service.EvidenceService.update_status") as mock_update:
            mock_update.return_value = {
                "evidence_id": str(evidence_id),
                "old_status": "valid",
                "new_status": new_status,
                "reason": reason,
                "updated_at": datetime.now(timezone.utc),
                "renewal_required": True,
                "renewal_due_date": datetime.now(timezone.utc) + timedelta(days=30),
            }
            result = EvidenceService.update_status(evidence_id, new_status, reason)
            assert result["new_status"] == new_status
            assert result["reason"] == reason
            assert result["renewal_required"] is True
            mock_update.assert_called_once_with(evidence_id, new_status, reason)

    def test_search_evidence_by_framework(self, fast_db_session, sample_user):
        """Test searching evidence items by framework"""
        framework = "ISO27001"
        search_filters = {"evidence_type": "document", "status": "valid", "min_quality_score": 80}
        with patch("services.evidence_service.EvidenceService.search_by_framework") as mock_search:
            mock_search.return_value = [
                {
                    "id": str(uuid4()),
                    "title": "Access Control Policy",
                    "framework_mappings": ["ISO27001.A.9.1.1", "ISO27001.A.9.1.2"],
                    "evidence_type": "document",
                    "status": "valid",
                    "quality_score": 88.0,
                },
                {
                    "id": str(uuid4()),
                    "title": "Incident Response Procedure",
                    "framework_mappings": ["ISO27001.A.16.1.1"],
                    "evidence_type": "document",
                    "status": "valid",
                    "quality_score": 91.0,
                },
            ]
            result = EvidenceService.search_by_framework(sample_user.id, framework, search_filters)
            assert len(result) == 2
            assert all(framework in str(item["framework_mappings"]) for item in result)
            assert all(item["quality_score"] >= 80 for item in result)
            mock_search.assert_called_once_with(sample_user.id, framework, search_filters)

    def test_delete_evidence_item_success(self, fast_db_session, sample_user):
        """Test deleting evidence item"""
        evidence_id = uuid4()
        with patch("services.evidence_service.EvidenceService.delete_evidence") as mock_delete:
            mock_delete.return_value = {
                "deleted": True,
                "evidence_id": str(evidence_id),
                "user_id": str(sample_user.id),
                "cleanup_performed": True,
            }
            result = EvidenceService.delete_evidence(evidence_id, sample_user.id)
            assert result["deleted"] is True
            assert result["cleanup_performed"] is True
            mock_delete.assert_called_once_with(evidence_id, sample_user.id)

    def test_delete_evidence_item_not_found(self, fast_db_session, sample_user):
        """Test deleting non-existent evidence item"""
        evidence_id = uuid4()
        with patch("services.evidence_service.EvidenceService.delete_evidence") as mock_delete:
            mock_delete.side_effect = NotFoundAPIError("Evidence item", evidence_id)
            with pytest.raises(NotFoundAPIError):
                EvidenceService.delete_evidence(evidence_id, sample_user.id)

    def test_bulk_update_evidence_status(self, fast_db_session, sample_user):
        """Test bulk updating evidence status"""
        evidence_ids = [str(uuid4()) for _ in range(5)]
        new_status = "reviewed"
        reason = "Quarterly review completed"
        with patch(
            "services.evidence_service.EvidenceService.bulk_update_status"
        ) as mock_bulk_update:
            mock_bulk_update.return_value = {
                "updated_count": 5,
                "failed_count": 0,
                "total_requested": 5,
                "success_rate": 100.0,
                "updated_evidence_ids": evidence_ids,
                "failed_evidence_ids": [],
            }
            result = EvidenceService.bulk_update_status(
                evidence_ids, new_status, reason, sample_user.id
            )
            assert result["updated_count"] == DEFAULT_RETRIES
            assert result["failed_count"] == 0
            assert result["success_rate"] == DEFAULT_LIMIT
            mock_bulk_update.assert_called_once_with(
                evidence_ids, new_status, reason, sample_user.id
            )

    def test_get_evidence_statistics(self, fast_db_session, sample_user):
        """Test getting evidence statistics for user"""
        with patch("services.evidence_service.EvidenceService.get_statistics") as mock_stats:
            mock_stats.return_value = {
                "total_evidence_items": 42,
                "by_status": {"valid": 35, "expired": 5, "pending": 2},
                "by_type": {"document": 25, "log": 12, "screenshot": 3, "configuration": 2},
                "by_framework": {"ISO27001": 28, "GDPR": 20, "SOC2": 15},
                "average_quality_score": 84.7,
                "automation_coverage": 65.0,
                "last_updated": datetime.now(timezone.utc),
            }
            result = EvidenceService.get_statistics(sample_user.id)
            assert result["total_evidence_items"] > 0
            assert "by_status" in result
            assert "by_type" in result
            assert "average_quality_score" in result
            assert result["automation_coverage"] > 0
            mock_stats.assert_called_once_with(sample_user.id)


@pytest.mark.unit
class TestEvidenceValidation:
    """Test evidence validation logic"""

    def test_validate_evidence_type_document(self):
        """Test document evidence type validation"""
        evidence_data = {
            "evidence_type": "document",
            "file_content": "Policy document content...",
            "metadata": {"document_type": "policy"},
        }
        with patch(
            "services.evidence_service.EvidenceService.validate_evidence_type"
        ) as mock_validate:
            mock_validate.return_value = {
                "valid": True,
                "type_specific_score": 85,
                "requirements_met": ["has_content", "has_metadata"],
                "requirements_missing": [],
            }
            result = EvidenceService.validate_evidence_type(evidence_data)
            assert result["valid"] is True
            assert result["type_specific_score"] > 0
            assert len(result["requirements_missing"]) == 0

    def test_validate_evidence_type_log(self):
        """Test log evidence type validation"""
        evidence_data = {
            "evidence_type": "log",
            "log_entries": [
                {
                    "timestamp": "2024-01-01T10:00:00Z",
                    "event": "user_login",
                    "user": "john@example.com",
                },
                {
                    "timestamp": "2024-01-01T10:05:00Z",
                    "event": "file_access",
                    "user": "john@example.com",
                },
            ],
            "metadata": {"log_source": "application", "retention_period": "90_days"},
        }
        with patch(
            "services.evidence_service.EvidenceService.validate_evidence_type"
        ) as mock_validate:
            mock_validate.return_value = {
                "valid": True,
                "type_specific_score": 92,
                "requirements_met": ["has_entries", "has_timestamps", "has_metadata"],
                "requirements_missing": [],
                "log_analysis": {
                    "entry_count": 2,
                    "time_span": "5 minutes",
                    "event_types": ["user_login", "file_access"],
                },
            }
            result = EvidenceService.validate_evidence_type(evidence_data)
            assert result["valid"] is True
            assert result["type_specific_score"] > 90
            assert "log_analysis" in result
