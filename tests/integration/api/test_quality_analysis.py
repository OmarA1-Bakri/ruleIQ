"""

# Constants

Integration Tests for Quality Analysis API Endpoints

Tests the AI-powered quality analysis and duplicate detection API endpoints.
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
class TestQualityAnalysisAPI:
    """Test quality analysis API endpoints"""

    @pytest.fixture
    def sample_evidence_data(self):
        """Sample evidence data for testing."""
        return {
            "evidence_name": "Information Security Policy",
            "description": "Comprehensive security policy covering access controls, data protection, and incident response procedures",
            "evidence_type": "policy_document",
            "raw_data": json.dumps(
                {
                    "file_type": "pdf",
                    "content": "This policy establishes comprehensive security controls...",
                }
            ),
        }

    def test_get_evidence_quality_analysis(
        self, client, authenticated_headers, sample_business_profile, sample_evidence_data
    ):
        """Test getting AI-powered quality analysis for evidence."""
        create_response = client.post(
            "/api/evidence/", json=sample_evidence_data, headers=authenticated_headers
        )
        if create_response.status_code != HTTP_OK:
            pytest.skip("Evidence creation failed")
        evidence_id = create_response.json()["id"]
        with patch(
            "services.automation.quality_scorer.QualityScorer.calculate_enhanced_score"
        ) as mock_analysis:
            mock_analysis.return_value = {
                "overall_score": 82.5,
                "traditional_scores": {
                    "completeness": 85,
                    "freshness": 90,
                    "content_quality": 80,
                    "relevance": 85,
                },
                "ai_analysis": {
                    "scores": {
                        "completeness": 85,
                        "clarity": 90,
                        "currency": 80,
                        "verifiability": 75,
                        "relevance": 95,
                        "sufficiency": 80,
                    },
                    "overall_score": 84,
                    "strengths": ["Clear documentation", "Comprehensive coverage"],
                    "weaknesses": ["Could include more examples"],
                    "recommendations": [
                        "Add implementation examples",
                        "Include compliance checklist",
                    ],
                    "ai_confidence": 85,
                },
                "scoring_method": "enhanced_ai",
                "confidence": 85,
                "analysis_timestamp": "2024-01-01T00:00:00",
            }
            response = client.get(
                f"/api/evidence/{evidence_id}/quality-analysis", headers=authenticated_headers
            )
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            response_data = response.json()
            assert response_data["evidence_id"] == evidence_id
            assert response_data["overall_score"] == 82.5
            assert response_data["scoring_method"] == "enhanced_ai"
            assert response_data["confidence"] == 85
            assert len(response_data["ai_analysis"]["strengths"]) == 2
            assert len(response_data["ai_analysis"]["recommendations"]) == 2

    def test_detect_evidence_duplicates(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test semantic duplicate detection for evidence."""
        evidence_data_1 = {
            "evidence_name": "Security Policy v1",
            "description": "Information security policy covering access controls",
            "evidence_type": "policy_document",
        }
        evidence_data_2 = {
            "evidence_name": "Security Policy v2",
            "description": "Updated information security policy with access controls",
            "evidence_type": "policy_document",
        }
        create_response_1 = client.post(
            "/api/evidence/", json=evidence_data_1, headers=authenticated_headers
        )
        create_response_2 = client.post(
            "/api/evidence/", json=evidence_data_2, headers=authenticated_headers
        )
        if create_response_1.status_code != HTTP_OK or create_response_2.status_code != HTTP_OK:
            pytest.skip("Evidence creation failed")
        evidence_id_1 = create_response_1.json()["id"]
        with patch(
            "services.automation.quality_scorer.QualityScorer.detect_semantic_duplicates"
        ) as mock_detection:
            mock_detection.return_value = [
                {
                    "candidate_id": create_response_2.json()["id"],
                    "candidate_name": "Security Policy v2",
                    "similarity_score": 85,
                    "similarity_type": "substantial_overlap",
                    "reasoning": "Both are security policies with similar content and structure",
                    "recommendation": "review_manually",
                }
            ]
            duplicate_request = {
                "evidence_id": evidence_id_1,
                "similarity_threshold": 80,
                "max_candidates": 20,
            }
            response = client.post(
                f"/api/evidence/{evidence_id_1}/duplicate-detection",
                json=duplicate_request,
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            response_data = response.json()
            assert response_data["evidence_id"] == evidence_id_1
            assert response_data["duplicates_found"] == 1
            assert len(response_data["duplicates"]) == 1
            assert response_data["duplicates"][0]["similarity_score"] == 85

    def test_batch_duplicate_detection(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test batch duplicate detection across multiple evidence items."""
        evidence_items = []
        for i in range(3):
            evidence_data = {
                "evidence_name": f"Test Evidence {i}",
                "description": f"Test description for evidence {i}",
                "evidence_type": "policy_document",
            }
            create_response = client.post(
                "/api/evidence/", json=evidence_data, headers=authenticated_headers
            )
            if create_response.status_code == HTTP_OK:
                evidence_items.append(create_response.json()["id"])
        if len(evidence_items) < 2:
            pytest.skip("Insufficient evidence items created")
        with patch(
            "services.automation.quality_scorer.QualityScorer.batch_duplicate_detection"
        ) as mock_batch:
            mock_batch.return_value = {
                "total_items": len(evidence_items),
                "duplicate_groups": [
                    {
                        "primary_evidence": {
                            "id": evidence_items[0],
                            "name": "Test Evidence 0",
                            "type": "policy_document",
                        },
                        "duplicates": [
                            {
                                "candidate_id": evidence_items[1],
                                "candidate_name": "Test Evidence 1",
                                "similarity_score": 82,
                                "similarity_type": "substantial_overlap",
                                "reasoning": "Similar test evidence",
                                "recommendation": "merge",
                            }
                        ],
                        "group_size": 2,
                        "highest_similarity": 82,
                    }
                ],
                "potential_duplicates": 1,
                "unique_items": 2,
                "analysis_summary": "Found 1 duplicate group with 1 potential duplicate",
            }
            batch_request = {"evidence_ids": evidence_items, "similarity_threshold": 80}
            response = client.post(
                "/api/evidence/duplicate-detection/batch",
                json=batch_request,
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            response_data = response.json()
            assert response_data["total_items"] == len(evidence_items)
            assert response_data["potential_duplicates"] == 1
            assert response_data["unique_items"] == 2
            assert len(response_data["duplicate_groups"]) == 1

    def test_get_quality_benchmark(self, client, authenticated_headers, sample_business_profile):
        """Test quality benchmarking endpoint."""
        evidence_data = {
            "evidence_name": "Test Evidence",
            "description": "Test description for benchmarking",
            "evidence_type": "policy_document",
        }
        create_response = client.post(
            "/api/evidence/", json=evidence_data, headers=authenticated_headers
        )
        if create_response.status_code != HTTP_OK:
            pytest.skip("Evidence creation failed")
        response = client.get("/api/evidence/quality/benchmark", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        assert_api_response_security(response)
        response_data = response.json()
        assert "user_average_score" in response_data
        assert "benchmark_score" in response_data
        assert "percentile_rank" in response_data
        assert "score_distribution" in response_data
        assert "improvement_areas" in response_data
        assert "top_performers" in response_data

    def test_get_quality_trends(self, client, authenticated_headers, sample_business_profile):
        """Test quality trend analysis endpoint."""
        evidence_data = {
            "evidence_name": "Test Evidence",
            "description": "Test description for trend analysis",
            "evidence_type": "policy_document",
        }
        create_response = client.post(
            "/api/evidence/", json=evidence_data, headers=authenticated_headers
        )
        if create_response.status_code != HTTP_OK:
            pytest.skip("Evidence creation failed")
        response = client.get("/api/evidence/quality/trends?days=30", headers=authenticated_headers)
        assert response.status_code == HTTP_OK
        assert_api_response_security(response)
        response_data = response.json()
        assert "period_days" in response_data
        assert "trend_direction" in response_data
        assert "average_score_change" in response_data
        assert "daily_scores" in response_data
        assert "insights" in response_data
        assert "recommendations" in response_data

    def test_quality_analysis_nonexistent_evidence(self, client, authenticated_headers):
        """Test quality analysis for non-existent evidence returns 404."""
        fake_evidence_id = str(uuid4())
        response = client.get(
            f"/api/evidence/{fake_evidence_id}/quality-analysis", headers=authenticated_headers
        )
        assert response.status_code == HTTP_NOT_FOUND

    def test_duplicate_detection_insufficient_evidence(self, client, authenticated_headers):
        """Test batch duplicate detection with insufficient evidence."""
        batch_request = {"evidence_ids": [str(uuid4())], "similarity_threshold": 80}
        response = client.post(
            "/api/evidence/duplicate-detection/batch",
            json=batch_request,
            headers=authenticated_headers,
        )
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        response_data = response.json()
        assert "detail" in response_data


@pytest.mark.integration
@pytest.mark.api
class TestQualityAnalysisValidation:
    """Test validation and error handling for quality analysis endpoints"""

    def test_duplicate_detection_invalid_threshold(self, client, authenticated_headers):
        """Test duplicate detection with invalid similarity threshold."""
        duplicate_request = {
            "evidence_id": str(uuid4()),
            "similarity_threshold": 150,
            "max_candidates": 20,
        }
        response = client.post(
            f"/api/evidence/{uuid4()}/duplicate-detection",
            json=duplicate_request,
            headers=authenticated_headers,
        )
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_batch_duplicate_detection_too_many_items(self, client, authenticated_headers):
        """Test batch duplicate detection with too many evidence items."""
        evidence_ids = [str(uuid4()) for _ in range(101)]
        batch_request = {"evidence_ids": evidence_ids, "similarity_threshold": 80}
        response = client.post(
            "/api/evidence/duplicate-detection/batch",
            json=batch_request,
            headers=authenticated_headers,
        )
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_quality_trends_invalid_days(self, client, authenticated_headers):
        """Test quality trends with invalid day range."""
        response = client.get(
            "/api/evidence/quality/trends?days=500", headers=authenticated_headers
        )
        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_quality_analysis_ai_service_error(
        self, client, authenticated_headers, sample_business_profile
    ):
        """Test handling of AI service errors during quality analysis."""
        evidence_data = {
            "evidence_name": "Test Evidence",
            "description": "Test description",
            "evidence_type": "policy_document",
        }
        create_response = client.post(
            "/api/evidence/", json=evidence_data, headers=authenticated_headers
        )
        if create_response.status_code != HTTP_OK:
            pytest.skip("Evidence creation failed")
        evidence_id = create_response.json()["id"]
        with patch(
            "services.automation.quality_scorer.QualityScorer.calculate_enhanced_score"
        ) as mock_analysis:
            mock_analysis.side_effect = Exception("AI service temporarily unavailable")
            response = client.get(
                f"/api/evidence/{evidence_id}/quality-analysis", headers=authenticated_headers
            )
            assert response.status_code == HTTP_INTERNAL_SERVER_ERROR
