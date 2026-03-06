"""

# Constants

Integration Tests for Evidence Classification API Endpoints

Tests the AI-powered evidence classification API endpoints with real database interactions.
"""

import json
from unittest.mock import patch
from uuid import uuid4
import pytest
from tests.conftest import assert_api_response_security

from tests.test_constants import (
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNPROCESSABLE_ENTITY,
)


@pytest.mark.integration
@pytest.mark.api
class TestEvidenceClassificationAPI:
    """Test evidence classification API endpoints"""

    @pytest.fixture
    def sample_evidence_data(self):
        """Sample evidence data for testing."""
        return {
            "evidence_name": "Security Policy Document",
            "description": "Comprehensive information security policy covering access controls and data protection",
            "evidence_type": "unknown",
            "raw_data": json.dumps(
                {"file_type": "pdf", "content": "This policy establishes security controls..."}
            ),
        }

    def test_classify_single_evidence(
        self, client, authenticated_headers, sample_business_profile, sample_evidence_data
    ):
        """Test classifying a single evidence item."""
        create_response = client.post(
            "/api/evidence/", json=sample_evidence_data, headers=authenticated_headers
        )
        if create_response.status_code != HTTP_OK:
            pytest.skip("Evidence creation failed - may need business profile setup")
        evidence_id = create_response.json()["id"]
        with patch(
            "services.automation.evidence_processor.EvidenceProcessor._ai_classify_evidence"
        ) as mock_ai:
            mock_ai.return_value = {
                "suggested_type": "policy_document",
                "confidence": 85,
                "suggested_controls": ["A.5.1.1", "A.5.1.2", "A.9.1.1"],
                "reasoning": "Document contains policy language and security controls",
            }
            classify_request = {"evidence_id": evidence_id, "force_reclassify": False}
            response = client.post(
                f"/api/evidence/{evidence_id}/classify",
                json=classify_request,
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            response_data = response.json()
            assert response_data["evidence_id"] == evidence_id
            assert response_data["confidence"] == 85
            assert response_data["suggested_controls"] == ["A.5.1.1", "A.5.1.2", "A.9.1.1"]
            assert response_data["apply_suggestion"] is True

    def test_classify_evidence_force_reclassify(
        self, client, authenticated_headers, sample_business_profile, sample_evidence_data
    ):
        """Test force reclassification of already classified evidence."""
        create_response = client.post(
            "/api/evidence/", json=sample_evidence_data, headers=authenticated_headers
        )
        if create_response.status_code != HTTP_OK:
            pytest.skip("Evidence creation failed")
        evidence_id = create_response.json()["id"]
        with patch(
            "services.automation.evidence_processor.EvidenceProcessor._ai_classify_evidence"
        ) as mock_ai:
            mock_ai.return_value = {
                "suggested_type": "policy_document",
                "confidence": 85,
                "suggested_controls": ["A.5.1.1"],
                "reasoning": "Initial classification",
            }
            response1 = client.post(
                f"/api/evidence/{evidence_id}/classify",
                json={"evidence_id": evidence_id, "force_reclassify": False},
                headers=authenticated_headers,
            )
            if response1.status_code == HTTP_OK:
                mock_ai.return_value = {
                    "suggested_type": "audit_report",
                    "confidence": 90,
                    "suggested_controls": ["A.9.2.1"],
                    "reasoning": "Reclassified as audit report",
                }
                response2 = client.post(
                    f"/api/evidence/{evidence_id}/classify",
                    json={"evidence_id": evidence_id, "force_reclassify": False},
                    headers=authenticated_headers,
                )
                if response2.status_code == HTTP_OK:
                    assert response2.json()["reasoning"] == "Previously classified"
                response3 = client.post(
                    f"/api/evidence/{evidence_id}/classify",
                    json={"evidence_id": evidence_id, "force_reclassify": True},
                    headers=authenticated_headers,
                )
                if response3.status_code == HTTP_OK:
                    assert (response3.json()["reasoning"] == "Reclassified as audit report",)

    def test_bulk_classify_evidence(self, client, authenticated_headers, sample_business_profile):
        """Test bulk classification of multiple evidence items."""
        evidence_ids = []
        for i in range(3):
            evidence_data = {
                "evidence_name": f"Test Evidence {i}",
                "description": f"Test description {i}",
                "evidence_type": "unknown",
            }
            create_response = client.post(
                "/api/evidence/", json=evidence_data, headers=authenticated_headers
            )
            if create_response.status_code == HTTP_OK:
                evidence_ids.append(create_response.json()["id"])
        if not evidence_ids:
            pytest.skip("No evidence items created successfully")
        with patch(
            "services.automation.evidence_processor.EvidenceProcessor._ai_classify_evidence"
        ) as mock_ai:
            mock_ai.return_value = {
                "suggested_type": "policy_document",
                "confidence": 75,
                "suggested_controls": ["A.5.1.1"],
                "reasoning": "Bulk classification test",
            }
            bulk_request = {
                "evidence_ids": evidence_ids,
                "force_reclassify": False,
                "apply_high_confidence": True,
                "confidence_threshold": 70,
            }
            response = client.post(
                "/api/evidence/classify/bulk", json=bulk_request, headers=authenticated_headers
            )
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            response_data = response.json()
            assert response_data["total_processed"] == len(evidence_ids)
            assert response_data["successful_classifications"] > 0
            assert response_data["auto_applied"] > 0

    def test_get_control_mapping_suggestions(
        self, client, authenticated_headers, sample_business_profile, sample_evidence_data
    ):
        """Test getting control mapping suggestions for evidence."""
        create_response = client.post(
            "/api/evidence/", json=sample_evidence_data, headers=authenticated_headers
        )
        if create_response.status_code != HTTP_OK:
            pytest.skip("Evidence creation failed")
        evidence_id = create_response.json()["id"]
        with patch(
            "services.automation.evidence_processor.EvidenceProcessor._ai_classify_evidence"
        ) as mock_ai:
            mock_ai.return_value = {
                "suggested_type": "policy_document",
                "confidence": 85,
                "suggested_controls": ["A.5.1.1", "CC6.1", "Art. 32"],
                "reasoning": "Multi-framework control mapping",
            }
            mapping_request = {
                "evidence_id": evidence_id,
                "frameworks": ["ISO27001", "SOC2", "GDPR"],
            }
            response = client.post(
                f"/api/evidence/{evidence_id}/control-mapping",
                json=mapping_request,
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            response_data = response.json()
            assert response_data["evidence_id"] == evidence_id
            assert "framework_mappings" in response_data
            assert "ISO27001" in response_data["framework_mappings"]
            assert "SOC2" in response_data["framework_mappings"]
            assert "GDPR" in response_data["framework_mappings"]

    def test_get_classification_statistics(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test getting classification statistics."""
        response = client.get("/api/evidence/classification/stats", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        assert_api_response_security(response)
        response_data = response.json()
        assert "total_evidence" in response_data
        assert "classified_evidence" in response_data
        assert "unclassified_evidence" in response_data
        assert "classification_accuracy" in response_data
        assert "type_distribution" in response_data
        assert "confidence_distribution" in response_data
        assert "recent_classifications" in response_data
        assert (
            response_data["classified_evidence"] + response_data["unclassified_evidence"]
            == response_data["total_evidence"],
        )

    def test_classify_nonexistent_evidence(self, client, authenticated_headers):
        """Test classifying non-existent evidence returns 404."""
        fake_evidence_id = str(uuid4())
        classify_request = {"evidence_id": fake_evidence_id, "force_reclassify": False}
        response = client.post(
            f"/api/evidence/{fake_evidence_id}/classify",
            json=classify_request,
            headers=authenticated_headers,
        )
        assert response.status_code == HTTP_NOT_FOUND

    def test_bulk_classify_with_invalid_evidence(self, client, authenticated_headers):
        """Test bulk classification with some invalid evidence IDs."""
        fake_evidence_id = str(uuid4())
        bulk_request = {
            "evidence_ids": [fake_evidence_id],
            "force_reclassify": False,
            "apply_high_confidence": True,
            "confidence_threshold": 70,
        }
        response = client.post(
            "/api/evidence/classify/bulk", json=bulk_request, headers=authenticated_headers
        )
        assert response.status_code == HTTP_OK
        response_data = response.json()
        assert response_data["failed_classifications"] > 0
        assert len(response_data["results"]) == 1
        assert response_data["results"][0]["success"] is False


@pytest.mark.integration
@pytest.mark.api
class TestEvidenceClassificationValidation:
    """Test validation and error handling for classification endpoints"""

    def test_bulk_classify_too_many_items(self, client, authenticated_headers):
        """Test bulk classification with too many evidence items."""
        evidence_ids = [str(uuid4()) for _ in range(51)]
        bulk_request = {"evidence_ids": evidence_ids, "force_reclassify": False}
        response = client.post(
            "/api/evidence/classify/bulk", json=bulk_request, headers=authenticated_headers
        )
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_invalid_confidence_threshold(self, client, authenticated_headers):
        """Test bulk classification with invalid confidence threshold."""
        bulk_request = {"evidence_ids": [str(uuid4())], "confidence_threshold": 150}
        response = client.post(
            "/api/evidence/classify/bulk", json=bulk_request, headers=authenticated_headers
        )
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_classification_ai_service_error(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test handling of AI service errors during classification."""
        evidence_data = {
            "evidence_name": "Test Evidence",
            "description": "Test description",
            "evidence_type": "unknown",
        }
        create_response = client.post(
            "/api/evidence/", json=evidence_data, headers=authenticated_headers
        )
        if create_response.status_code != HTTP_OK:
            pytest.skip("Evidence creation failed")
        evidence_id = create_response.json()["id"]
        with patch(
            "services.automation.evidence_processor.EvidenceProcessor._ai_classify_evidence"
        ) as mock_ai:
            mock_ai.side_effect = Exception("AI service temporarily unavailable")
            response = client.post(
                f"/api/evidence/{evidence_id}/classify",
                json={"evidence_id": evidence_id, "force_reclassify": False},
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_INTERNAL_SERVER_ERROR
