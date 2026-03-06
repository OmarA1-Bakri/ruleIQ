"""
Functional tests for ComplianceAnalysisService

These tests verify that ported methods actually work with real logic,
not just structural verification.

These are unit tests with complete mocking - no database required.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

# Mark all tests in this module as not requiring database
pytestmark = [pytest.mark.unit, pytest.mark.anyio]

from services.ai.domains.compliance_service import ComplianceAnalysisService


@pytest.fixture
def mock_response_generator():
    """Mock response generator that simulates AI response."""
    generator = Mock()
    generator.generate_simple = AsyncMock(
        return_value='{"completion_percentage": 65, "recommendations": [], "critical_gaps": ["Documentation"], "risk_level": "Medium"}'
    )
    return generator


@pytest.fixture
def mock_context_manager():
    """Mock context manager with realistic business data."""
    manager = AsyncMock()
    manager.get_conversation_context.return_value = {
        "business_profile": {
            "company_name": "Test Corp",
            "industry": "Technology",
            "employee_count": 50,
        },
        "recent_evidence": [
            {"evidence_type": "policy", "updated_at": "2025-01-01"},
            {"evidence_type": "procedure", "updated_at": "2025-01-02"},
            {"evidence_type": "policy", "updated_at": None},
        ],
    }
    return manager


@pytest.fixture
def compliance_service(mock_response_generator, mock_context_manager):
    """Create compliance service with mocks."""
    return ComplianceAnalysisService(mock_response_generator, mock_context_manager)


class TestAnalyzeEvidenceGapFunctional:
    """Functional tests for analyze_evidence_gap method."""

    async def test_analyze_evidence_gap_calls_context_manager(
        self, compliance_service, mock_context_manager
    ):
        """Verify method calls context manager to get business context."""
        business_id = uuid4()

        await compliance_service.analyze_evidence_gap(
            business_profile_id=business_id, framework="GDPR"
        )

        # Verify context manager was called
        mock_context_manager.get_conversation_context.assert_called_once()
        call_kwargs = mock_context_manager.get_conversation_context.call_args[1]

        # Should be called with the business_profile_id
        assert call_kwargs["business_profile_id"] == business_id

    async def test_analyze_evidence_gap_calls_response_generator(
        self, compliance_service, mock_response_generator
    ):
        """Verify method calls response generator with correct parameters."""
        business_id = uuid4()

        await compliance_service.analyze_evidence_gap(
            business_profile_id=business_id, framework="ISO27001"
        )

        # Verify response generator was called
        mock_response_generator.generate_simple.assert_called_once()
        call_kwargs = mock_response_generator.generate_simple.call_args[1]

        assert "system_prompt" in call_kwargs
        assert "compliance expert" in call_kwargs["system_prompt"].lower()
        assert call_kwargs["task_type"] == "compliance_analysis"
        assert call_kwargs["context"]["framework"] == "ISO27001"

    async def test_analyze_evidence_gap_returns_correct_format(self, compliance_service):
        """Verify method returns data in expected format."""
        business_id = uuid4()

        result = await compliance_service.analyze_evidence_gap(
            business_profile_id=business_id, framework="GDPR"
        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "framework" in result
        assert result["framework"] == "GDPR"
        assert "completion_percentage" in result
        assert "evidence_collected" in result
        assert "evidence_types" in result
        assert "recent_activity" in result
        assert "recommendations" in result
        assert "critical_gaps" in result
        assert "risk_level" in result

    async def test_analyze_evidence_gap_parses_json_response(
        self, compliance_service, mock_response_generator
    ):
        """Verify AI JSON response is parsed correctly."""
        json_response = '{"completion_percentage": 75, "recommendations": [{"type": "doc", "priority": "high"}], "critical_gaps": ["Gap1", "Gap2"], "risk_level": "High"}'
        mock_response_generator.generate_simple.return_value = json_response

        business_id = uuid4()

        result = await compliance_service.analyze_evidence_gap(
            business_profile_id=business_id, framework="SOC2"
        )

        # Verify parsed values from JSON
        assert result["completion_percentage"] == 75
        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["type"] == "doc"
        assert len(result["critical_gaps"]) == 2
        assert result["risk_level"] == "High"

    async def test_analyze_evidence_gap_handles_non_json_response(
        self, compliance_service, mock_response_generator
    ):
        """Verify fallback when AI returns non-JSON text."""
        mock_response_generator.generate_simple.return_value = "This is just text, not JSON"

        business_id = uuid4()

        result = await compliance_service.analyze_evidence_gap(
            business_profile_id=business_id, framework="GDPR"
        )

        # Should use fallback values
        assert result["completion_percentage"] == 30
        assert len(result["recommendations"]) == 3  # Fallback recommendations
        assert "documentation" in result["recommendations"][0]["type"]

    async def test_analyze_evidence_gap_counts_evidence(
        self, compliance_service, mock_context_manager
    ):
        """Verify method correctly counts evidence items."""
        business_id = uuid4()

        result = await compliance_service.analyze_evidence_gap(
            business_profile_id=business_id, framework="GDPR"
        )

        # Should count 3 evidence items from mock context
        assert result["evidence_collected"] == 3

    async def test_analyze_evidence_gap_summarizes_evidence_types(self, compliance_service):
        """Verify method summarizes evidence types correctly."""
        business_id = uuid4()

        result = await compliance_service.analyze_evidence_gap(
            business_profile_id=business_id, framework="GDPR"
        )

        # Should have 2 types: policy and procedure
        assert len(result["evidence_types"]) == 2
        assert "policy" in result["evidence_types"]
        assert "procedure" in result["evidence_types"]

    async def test_analyze_evidence_gap_counts_recent_activity(self, compliance_service):
        """Verify method counts items with updated_at timestamps."""
        business_id = uuid4()

        result = await compliance_service.analyze_evidence_gap(
            business_profile_id=business_id, framework="GDPR"
        )

        # Should count 2 items with updated_at (one has None)
        assert result["recent_activity"] == 2

    async def test_analyze_evidence_gap_with_different_frameworks(self, compliance_service):
        """Verify method works with different frameworks."""
        frameworks = ["GDPR", "ISO27001", "SOC2", "HIPAA"]

        business_id = uuid4()

        for framework in frameworks:
            result = await compliance_service.analyze_evidence_gap(
                business_profile_id=business_id, framework=framework
            )

            assert result["framework"] == framework


class TestAnalyzeEvidenceGapErrorHandling:
    """Test error handling in analyze_evidence_gap."""

    async def test_handles_context_manager_failure(self, compliance_service, mock_context_manager):
        """Verify proper exception handling when context manager fails."""
        business_id = uuid4()

        # Make context manager raise exception
        mock_context_manager.get_conversation_context.side_effect = Exception("Context error")

        # Should return fallback response, not raise
        result = await compliance_service.analyze_evidence_gap(
            business_profile_id=business_id, framework="GDPR"
        )

        assert result["framework"] == "GDPR"
        assert result["completion_percentage"] == 30
        assert "Analysis unavailable" in result["critical_gaps"]

    async def test_handles_response_generator_failure(
        self, compliance_service, mock_response_generator
    ):
        """Verify proper exception handling when AI generation fails."""
        # Make response generator fail
        mock_response_generator.generate_simple.side_effect = Exception("API timeout")

        business_id = uuid4()

        # Should return fallback response
        result = await compliance_service.analyze_evidence_gap(
            business_profile_id=business_id, framework="GDPR"
        )

        assert result["framework"] == "GDPR"
        assert result["completion_percentage"] == 30
        assert len(result["recommendations"]) == 3


class TestGenerateComplianceMappingFunctional:
    """Functional tests for generate_compliance_mapping method."""

    def test_generate_compliance_mapping_iso27001(self, compliance_service):
        """Verify mapping generation for ISO27001."""
        policy = {"title": "Information Security Policy"}

        result = compliance_service.generate_compliance_mapping(
            policy=policy, framework="ISO27001", policy_type="information_security"
        )

        assert result["framework"] == "ISO27001"
        assert result["policy_type"] == "information_security"
        assert "A.5.1.1" in result["mapped_controls"]
        assert "A.5.1.2" in result["mapped_controls"]
        assert len(result["compliance_objectives"]) > 0
        assert len(result["audit_considerations"]) > 0

    def test_generate_compliance_mapping_gdpr(self, compliance_service):
        """Verify mapping generation for GDPR."""
        policy = {"title": "Data Protection Policy"}

        result = compliance_service.generate_compliance_mapping(
            policy=policy, framework="GDPR", policy_type="data_protection"
        )

        assert result["framework"] == "GDPR"
        assert "Art. 5" in result["mapped_controls"]
        assert "Art. 6" in result["mapped_controls"]
        assert "Art. 7" in result["mapped_controls"]

    def test_generate_compliance_mapping_soc2(self, compliance_service):
        """Verify mapping generation for SOC2."""
        policy = {"title": "Security Policy"}

        result = compliance_service.generate_compliance_mapping(
            policy=policy, framework="SOC2", policy_type="security"
        )

        assert result["framework"] == "SOC2"
        assert "CC6.1" in result["mapped_controls"]
        assert "CC6.2" in result["mapped_controls"]

    def test_generate_compliance_mapping_unknown_framework(self, compliance_service):
        """Verify behavior with unknown framework."""
        policy = {"title": "Security Policy"}

        result = compliance_service.generate_compliance_mapping(
            policy=policy, framework="UNKNOWN", policy_type="security"
        )

        # Should return empty controls but still valid structure
        assert result["framework"] == "UNKNOWN"
        assert result["mapped_controls"] == []
        assert len(result["compliance_objectives"]) > 0


class TestEvidenceTypesSummary:
    """Test evidence types summary helper."""

    def test_get_evidence_types_summary_empty(self, compliance_service):
        """Verify summary with no evidence."""
        result = compliance_service._get_evidence_types_summary([])

        assert result == {}

    def test_get_evidence_types_summary_single_type(self, compliance_service):
        """Verify summary with single evidence type."""
        evidence = [
            {"evidence_type": "policy"},
            {"evidence_type": "policy"},
            {"evidence_type": "policy"},
        ]

        result = compliance_service._get_evidence_types_summary(evidence)

        assert result == {"policy": 3}

    def test_get_evidence_types_summary_multiple_types(self, compliance_service):
        """Verify summary with multiple evidence types."""
        evidence = [
            {"evidence_type": "policy"},
            {"evidence_type": "procedure"},
            {"evidence_type": "policy"},
            {"evidence_type": "training"},
            {"evidence_type": "procedure"},
        ]

        result = compliance_service._get_evidence_types_summary(evidence)

        assert result == {"policy": 2, "procedure": 2, "training": 1}

    def test_get_evidence_types_summary_unknown_type(self, compliance_service):
        """Verify summary handles missing evidence_type."""
        evidence = [
            {"evidence_type": "policy"},
            {},  # Missing evidence_type
            {"other_field": "value"},  # Missing evidence_type
        ]

        result = compliance_service._get_evidence_types_summary(evidence)

        assert result == {"policy": 1, "unknown": 2}


class TestValidationMethods:
    """Test static validation methods."""

    def test_validate_accuracy_gdpr_fact(self, compliance_service):
        """Verify GDPR fact checking."""
        response = "Organizations must notify within 72 hours of a breach."

        result = compliance_service.validate_accuracy(response, "GDPR")

        assert result["accuracy_score"] > 0.8
        assert len(result["fact_checks"]) > 0
        assert result["fact_checks"][0]["verified"] is True

    def test_validate_accuracy_non_gdpr(self, compliance_service):
        """Verify validation for non-GDPR frameworks."""
        response = "Organizations must have security policies."

        result = compliance_service.validate_accuracy(response, "ISO27001")

        assert result["accuracy_score"] == 0.8  # Default

    def test_detect_hallucination_suspicious_costs(self, compliance_service):
        """Verify hallucination detection for suspicious cost claims."""
        # Pattern: €\d+,\d+.*registration.*fee
        response = "GDPR compliance requires a €5,500 registration fee annually."

        result = compliance_service.detect_hallucination(response)

        assert result["hallucination_detected"] is True
        assert len(result["suspicious_claims"]) > 0
        assert result["confidence"] > 0

    def test_detect_hallucination_clean_response(self, compliance_service):
        """Verify clean responses don't trigger hallucination detection."""
        response = "GDPR requires data protection impact assessments."

        result = compliance_service.detect_hallucination(response)

        assert result["hallucination_detected"] is False
        assert len(result["suspicious_claims"]) == 0
        assert result["recommendation"] == "Appears accurate"
