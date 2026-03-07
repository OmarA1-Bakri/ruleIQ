"""

# Constants


Integration Tests for Evidence API Endpoints

Tests the evidence API endpoints with real database interactions
and service integrations, ensuring proper data flow and validation.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from tests.conftest import assert_api_response_security

from tests.test_constants import (
    DEFAULT_LIMIT,
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_NOT_FOUND,
    HTTP_NO_CONTENT,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    HTTP_UNPROCESSABLE_ENTITY,
    MAX_RETRIES,
)


@pytest.mark.integration
@pytest.mark.api
class TestEvidenceEndpoints:
    """Test evidence API endpoints integration"""

    def test_create_evidence_item_success(
        self,
        client,
        authenticated_headers,
        db_session,
        sample_business_profile,
        sample_compliance_framework,
    ):
        """Test creating evidence item through API"""
        evidence_data = {
            "title": "Information Security Policy",
            "description": "Company-wide information security policy document",
            "control_id": "A.5.1.1",
            "framework_id": str(sample_compliance_framework.id),
            "business_profile_id": str(sample_business_profile.id),
            "source": "manual_upload",
            "tags": ["security", "policy", "governance"],
            "evidence_type": "policy_document",
        }
        response = client.post("/api/evidence", json=evidence_data, headers=authenticated_headers)
        assert response.status_code == HTTP_CREATED
        assert_api_response_security(response)
        response_data = response.json()
        assert response_data["title"] == evidence_data["title"]
        assert response_data["description"] == evidence_data["description"]
        assert response_data["control_id"] == evidence_data["control_id"]
        assert response_data["framework_id"] == evidence_data["framework_id"]
        assert (response_data["business_profile_id"] == evidence_data["business_profile_id"],)
        assert response_data["source"] == evidence_data["source"]
        assert "id" in response_data
        assert "created_at" in response_data
        assert "status" in response_data

    def test_create_evidence_item_validation_error(
        self, client, authenticated_headers, sample_business_profile, sample_compliance_framework
    ):
        """Test creating evidence item with invalid data"""
        invalid_data = {
            "title": "",
            "description": "x" * 5000,
            "control_id": "",
            "source": "",
            "framework_id": str(sample_compliance_framework.id),
            "business_profile_id": str(sample_business_profile.id),
            "evidence_type": "document",
        }
        response = client.post("/api/evidence", json=invalid_data, headers=authenticated_headers)
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        response_data = response.json()
        assert "detail" in response_data
        errors = response_data["detail"]
        error_fields = [error["loc"][-1] for error in errors]
        assert "title" in error_fields
        assert "control_id" in error_fields

    def test_create_evidence_item_unauthenticated(
        self, sample_compliance_framework, sample_business_profile
    ):
        """Test creating evidence item without authentication"""
        from fastapi.testclient import TestClient
        from main import app

        unauthenticated_client = TestClient(app)
        evidence_data = {
            "title": "Test Evidence",
            "description": "Test description",
            "control_id": "A.5.1.1",
            "framework_id": str(sample_compliance_framework.id),
            "business_profile_id": str(sample_business_profile.id),
            "source": "manual_upload",
            "evidence_type": "document",
        }
        response = unauthenticated_client.post("/api/evidence", json=evidence_data)
        assert response.status_code == HTTP_UNAUTHORIZED
        assert "Not authenticated" in response.json()["detail"]

    def test_get_evidence_items_success(
        self, client, authenticated_headers, evidence_item_instance
    ):
        """Test retrieving evidence items for authenticated user"""
        response = client.get("/api/evidence", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) >= 1
        evidence_item = response_data[0]
        assert "id" in evidence_item
        assert "title" in evidence_item
        assert "evidence_type" in evidence_item
        assert "status" in evidence_item
        assert "created_at" in evidence_item

    def test_get_evidence_items_empty(self, client, db_session):
        """Test retrieving evidence items when user has none"""
        from api.dependencies.auth import create_access_token
        from database.user import User

        empty_user = User(
            id=uuid4(),
            email=f"empty-test-{uuid4()}@example.com",
            hashed_password="fake_password_hash",
            is_active=True,
        )
        db_session.add(empty_user)
        db_session.commit()
        db_session.refresh(empty_user)
        token_data = {"sub": str(empty_user.id)}
        token = create_access_token(data=token_data, expires_delta=timedelta(minutes=30))
        empty_headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/evidence", headers=empty_headers)
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == 0

    def test_get_evidence_items_with_filtering(
        self, client, authenticated_headers, evidence_item_instance
    ):
        """Test retrieving evidence items with query filters"""
        response = client.get("/api/evidence?evidence_type=document", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert isinstance(response_data, list)
        for item in response_data:
            assert item["evidence_type"] == "document"
        response = client.get("/api/evidence?status=valid", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        response_data = response.json()
        for item in response_data:
            assert item["status"] == "valid"
        response = client.get("/api/evidence?framework=ISO27001", headers=authenticated_headers)
        assert response.status_code == HTTP_OK

    def test_get_evidence_item_by_id_success(
        self, client, authenticated_headers, evidence_item_instance
    ):
        """Test retrieving specific evidence item by ID"""
        evidence_id = evidence_item_instance.id
        response = client.get(f"/api/evidence/{evidence_id}", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        assert_api_response_security(response)
        response_data = response.json()
        assert response_data["id"] == str(evidence_id)
        assert response_data["title"] == evidence_item_instance.evidence_name
        assert response_data["evidence_type"] == evidence_item_instance.evidence_type

    def test_get_evidence_item_by_id_not_found(self, client, authenticated_headers):
        """Test retrieving non-existent evidence item"""
        non_existent_id = uuid4()
        response = client.get(f"/api/evidence/{non_existent_id}", headers=authenticated_headers)
        assert response.status_code == HTTP_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_evidence_item_unauthorized_access(
        self, client, another_authenticated_headers, evidence_item_instance
    ):
        """Test user cannot access another user's evidence"""
        evidence_id = evidence_item_instance.id
        response = client.get(f"/api/evidence/{evidence_id}", headers=another_authenticated_headers)
        assert response.status_code in [403, 404]
        if response.status_code == HTTP_FORBIDDEN:
            assert "access denied" in response.json()["detail"].lower()
        elif response.status_code == HTTP_NOT_FOUND:
            assert "not found" in response.json()["detail"].lower()

    def test_update_evidence_item_success(
        self, client, authenticated_headers, evidence_item_instance
    ):
        """Test updating evidence item"""
        evidence_id = evidence_item_instance.id
        update_data = {
            "title": "Updated Security Policy",
            "description": "Updated company information security policy",
            "status": "reviewed",
            "tags": ["security", "policy", "updated"],
        }
        response = client.put(
            f"/api/evidence/{evidence_id}", json=update_data, headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        assert_api_response_security(response)
        response_data = response.json()
        assert response_data["title"] == update_data["title"]
        assert response_data["description"] == update_data["description"]
        assert response_data["status"] == update_data["status"]
        assert "updated_at" in response_data

    def test_update_evidence_item_partial(
        self, client, authenticated_headers, evidence_item_instance
    ):
        """Test partial update of evidence item"""
        evidence_id = evidence_item_instance.id
        update_data = {"status": "expired", "notes": "Evidence expired due to age"}
        response = client.patch(
            f"/api/evidence/{evidence_id}", json=update_data, headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert response_data["status"] == update_data["status"]
        assert response_data["title"] == evidence_item_instance.evidence_name

    def test_delete_evidence_item_success(
        self, client, authenticated_headers, evidence_item_instance
    ):
        """Test deleting evidence item"""
        evidence_id = evidence_item_instance.id
        response = client.delete(f"/api/evidence/{evidence_id}", headers=authenticated_headers)
        assert response.status_code == HTTP_NO_CONTENT
        get_response = client.get(f"/api/evidence/{evidence_id}", headers=authenticated_headers)
        assert get_response.status_code == HTTP_NOT_FOUND

    def test_delete_evidence_item_unauthorized(
        self, client, another_authenticated_headers, evidence_item_instance
    ):
        """Test user cannot delete another user's evidence"""
        evidence_id = evidence_item_instance.id
        response = client.delete(
            f"/api/evidence/{evidence_id}", headers=another_authenticated_headers
        )
        assert response.status_code in [403, 404]

    def test_bulk_update_evidence_status(
        self,
        client,
        authenticated_headers,
        db_session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
    ):
        """Test bulk updating evidence status"""
        from database.evidence_item import EvidenceItem

        evidence_items = []
        evidence_ids = []
        for i in range(3):
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=sample_business_profile.id,
                framework_id=sample_compliance_framework.id,
                evidence_name=f"Test Evidence {i + 1}",
                description=f"Test evidence description {i + 1}",
                control_reference=f"A.5.1.{i + 1}",
                evidence_type="document",
                collection_method="manual",
            )
            evidence_items.append(evidence)
            db_session.add(evidence)
        db_session.commit()
        for evidence in evidence_items:
            evidence_ids.append(str(evidence.id))
        bulk_update_data = {
            "evidence_ids": evidence_ids,
            "status": "reviewed",
            "reason": "Quarterly review completed",
        }
        response = client.post(
            "/api/evidence/bulk-update", json=bulk_update_data, headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert response_data["updated_count"] == MAX_RETRIES
        assert response_data["failed_count"] == 0
        for evidence_id in evidence_ids:
            get_response = client.get(f"/api/evidence/{evidence_id}", headers=authenticated_headers)
            assert get_response.status_code == HTTP_OK
            assert get_response.json()["status"] == "reviewed"

    def test_get_evidence_statistics(self, client, authenticated_headers, evidence_item_instance):
        """Test retrieving evidence statistics"""
        response = client.get("/api/evidence/stats", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        assert_api_response_security(response)
        response_data = response.json()
        assert "total_evidence_items" in response_data
        assert "by_status" in response_data
        assert "by_type" in response_data
        assert "by_framework" in response_data
        assert "average_quality_score" in response_data
        assert response_data["total_evidence_items"] >= 1
        assert isinstance(response_data["by_status"], dict)
        assert isinstance(response_data["by_type"], dict)

    def test_search_evidence_items(self, client, authenticated_headers, evidence_item_instance):
        """Test searching evidence items"""
        search_params = {
            "q": "security",
            "evidence_type": "document",
            "status": "valid",
            "framework": "ISO27001",
        }
        response = client.get(
            "/api/evidence/search", params=search_params, headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert "results" in response_data
        assert "total_count" in response_data
        assert "page" in response_data
        assert "page_size" in response_data
        if response_data["results"]:
            result = response_data["results"][0]
            assert "id" in result
            assert "title" in result
            assert "relevance_score" in result


@pytest.mark.integration
@pytest.mark.api
class TestEvidenceValidationEndpoints:
    """Test evidence validation API endpoints"""

    def test_validate_evidence_quality(self, client, authenticated_headers):
        """Test evidence quality validation endpoint"""
        evidence_data = {
            "title": "Comprehensive Security Policy",
            "description": "Detailed information security policy covering ISO 27001 requirements",
            "evidence_type": "document",
            "file_content": "Detailed policy content with procedures and controls...",
            "metadata": {
                "document_type": "policy",
                "version": "2.0",
                "approval_date": "2024-01-01",
                "author": "Chief Security Officer",
            },
        }
        response = client.post(
            "/api/evidence/validate", json=evidence_data, headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        assert_api_response_security(response)
        response_data = response.json()
        assert "quality_score" in response_data
        assert "validation_results" in response_data
        assert "issues" in response_data
        assert "recommendations" in response_data
        assert 0 <= response_data["quality_score"] <= DEFAULT_LIMIT
        assert isinstance(response_data["validation_results"], dict)
        assert isinstance(response_data["issues"], list)
        assert isinstance(response_data["recommendations"], list)

    def test_identify_evidence_requirements(self, client, authenticated_headers):
        """Test evidence requirements identification endpoint"""
        request_data = {
            "framework_id": str(uuid4()),
            "control_ids": [str(uuid4()), str(uuid4())],
            "business_context": {
                "industry": "technology",
                "company_size": "small",
                "data_types": ["personal_data", "financial_data"],
            },
        }
        response = client.post(
            "/api/evidence/requirements", json=request_data, headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert isinstance(response_data, dict)
        assert "requirements" in response_data
        assert isinstance(response_data["requirements"], list)
        if response_data["requirements"]:
            requirement = response_data["requirements"][0]
            assert "control_id" in requirement
            assert "evidence_type" in requirement
            assert "title" in requirement
            assert "description" in requirement
            assert "automation_possible" in requirement

    def test_configure_evidence_automation(
        self, client, authenticated_headers, evidence_item_instance
    ):
        """Test configuring evidence automation"""
        automation_config = {
            "source_type": "google_workspace",
            "collection_frequency": "daily",
            "data_mapping": {
                "user_list": "$.users[*].primaryEmail",
                "admin_status": "$.users[*].isAdmin",
            },
            "credentials": {"oauth_token": "mock_token_for_testing"},
        }
        response = client.post(
            f"/api/evidence/{evidence_item_instance.id}/automation",
            json=automation_config,
            headers=authenticated_headers,
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert "configuration_successful" in response_data
        assert "automation_enabled" in response_data
        assert "test_connection" in response_data
        if response_data["configuration_successful"]:
            assert "next_collection" in response_data


@pytest.mark.integration
@pytest.mark.api
class TestEvidencePaginationAndSorting:
    """Test evidence API pagination and sorting"""

    def test_evidence_pagination(
        self,
        client,
        authenticated_headers,
        db_session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
    ):
        """Test evidence list pagination"""
        from database.evidence_item import EvidenceItem

        evidence_items = []
        for i in range(25):
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=sample_business_profile.id,
                framework_id=sample_compliance_framework.id,
                evidence_name=f"Evidence Item {i + 1:02d}",
                description=f"Description for evidence item {i + 1}",
                control_reference=f"A.5.1.{i + 1}",
                evidence_type="document",
                collection_method="manual",
            )
            evidence_items.append(evidence)
            db_session.add(evidence)
        db_session.commit()
        response = client.get("/api/evidence?page=1&page_size=10", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert len(response_data["results"]) == 10
        assert response_data["page"] == 1
        assert response_data["page_size"] == 10
        assert response_data["total_count"] >= 25
        expected_pages = (response_data["total_count"] + 9) // 10
        assert response_data["total_pages"] == expected_pages
        response = client.get("/api/evidence?page=2&page_size=10", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert len(response_data["results"]) == 10
        assert response_data["page"] == 2
        first_response = client.get(
            "/api/evidence?page=1&page_size=10", headers=authenticated_headers
        )
        total_pages = first_response.json()["total_pages"]
        response = client.get(
            f"/api/evidence?page={total_pages}&page_size=10", headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert 1 <= len(response_data["results"]) <= 10

    def test_evidence_sorting(
        self,
        client,
        authenticated_headers,
        db_session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
    ):
        """Test evidence list sorting"""
        from database.evidence_item import EvidenceItem

        evidence_items = []
        for i in range(5):
            created_time = datetime.now(timezone.utc) - timedelta(minutes=i)
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=sample_business_profile.id,
                framework_id=sample_compliance_framework.id,
                evidence_name=f"Evidence {chr(65 + i)}",
                description=f"Description {i + 1}",
                control_reference=f"A.5.1.{i + 1}",
                evidence_type="document",
                collection_method="manual",
                created_at=created_time,
            )
            evidence_items.append(evidence)
            db_session.add(evidence)
        db_session.commit()
        response = client.get(
            "/api/evidence?sort_by=title&sort_order=asc", headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        titles = [item["title"] for item in response_data["results"]]
        assert titles == sorted(titles)
        response = client.get(
            "/api/evidence?sort_by=title&sort_order=desc", headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        titles = [item["title"] for item in response_data["results"]]
        assert titles == sorted(titles, reverse=True)
        response = client.get(
            "/api/evidence?sort_by=created_at&sort_order=desc", headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        dates = [item["created_at"] for item in response_data["results"]]
        assert dates == sorted(dates, reverse=True)
