"""Tests for api.schemas.ai_policy — enums, Pydantic models, validators."""
import pytest
from datetime import datetime, timezone

from api.schemas.ai_policy import (
    PolicyType,
    CustomizationLevel,
    TargetAudience,
    BusinessContext,
    PolicyGenerationRequest,
    PolicyRefinementRequest,
    PolicyValidationResult,
    PolicyGenerationResponse,
    PolicyRefinementResponse,
    PolicyTemplate,
    PolicyTemplatesResponse,
    CircuitBreakerStatus,
    AIProviderMetrics,
    PolicyGenerationMetrics,
    PolicyStreamingChunk,
    PolicyStreamingMetadata,
)


# ── Enums ────────────────────────────────────────────────────────

class TestPolicyEnums:
    def test_policy_type_values(self):
        assert PolicyType.PRIVACY_POLICY is not None
        assert PolicyType.INFORMATION_SECURITY_POLICY is not None
        assert PolicyType.DATA_RETENTION_POLICY is not None
        assert PolicyType.INCIDENT_RESPONSE_POLICY is not None
        assert PolicyType.ACCESS_CONTROL_POLICY is not None
        assert PolicyType.BUSINESS_CONTINUITY_POLICY is not None
        assert len(PolicyType) == 6

    def test_customization_level_values(self):
        assert CustomizationLevel.BASIC is not None
        assert CustomizationLevel.STANDARD is not None
        assert CustomizationLevel.DETAILED is not None
        assert CustomizationLevel.COMPREHENSIVE is not None
        assert len(CustomizationLevel) == 4

    def test_target_audience_values(self):
        assert TargetAudience.GENERAL_PUBLIC is not None
        assert TargetAudience.EMPLOYEES is not None
        assert TargetAudience.CUSTOMERS is not None
        assert TargetAudience.REGULATORS is not None
        assert TargetAudience.TECHNICAL_STAFF is not None
        assert len(TargetAudience) == 5


# ── BusinessContext ──────────────────────────────────────────────

class TestBusinessContext:
    def test_minimal(self):
        r = BusinessContext(organization_name="Acme", industry="tech")
        assert r.organization_name == "Acme"
        assert r.employee_count is None
        assert r.processes_personal_data is True
        assert r.data_types == []
        assert r.third_party_processors is False
        assert r.cross_border_transfers is False

    def test_full(self):
        r = BusinessContext(
            organization_name="Big Corp", industry="finance",
            employee_count=500, annual_revenue="£10M",
            geographic_operations=["UK", "EU"],
            processes_personal_data=True, data_types=["PII"],
            data_retention_period="7 years",
            third_party_processors=True, cross_border_transfers=True,
            cloud_services=["AWS"], security_certifications=["ISO27001"],
            existing_policies=["Privacy Policy"],
        )
        assert r.employee_count == 500
        assert len(r.geographic_operations) == 2

    def test_empty_org_name(self):
        with pytest.raises(Exception):
            BusinessContext(organization_name="", industry="tech")

    def test_employee_count_zero(self):
        with pytest.raises(Exception):
            BusinessContext(organization_name="X", industry="Y", employee_count=0)

    def test_employee_count_max(self):
        r = BusinessContext(organization_name="X", industry="Y", employee_count=1000000)
        assert r.employee_count == 1000000

    def test_employee_count_over_max(self):
        with pytest.raises(Exception):
            BusinessContext(organization_name="X", industry="Y", employee_count=1000001)


# ── PolicyGenerationRequest ──────────────────────────────────────

class TestPolicyGenerationRequest:
    def test_defaults(self):
        biz = BusinessContext(organization_name="X", industry="Y")
        r = PolicyGenerationRequest(
            framework_id="gdpr", business_context=biz,
            policy_type=PolicyType.PRIVACY_POLICY,
        )
        assert r.customization_level == CustomizationLevel.STANDARD
        assert r.target_audience == TargetAudience.GENERAL_PUBLIC
        assert r.include_templates is True
        assert r.language == "en-GB"

    def test_valid_language_en_us(self):
        biz = BusinessContext(organization_name="X", industry="Y")
        r = PolicyGenerationRequest(
            framework_id="gdpr", business_context=biz,
            policy_type=PolicyType.PRIVACY_POLICY,
            language="en-US",
        )
        assert r.language == "en-US"

    def test_invalid_language(self):
        biz = BusinessContext(organization_name="X", industry="Y")
        with pytest.raises(Exception):
            PolicyGenerationRequest(
                framework_id="gdpr", business_context=biz,
                policy_type=PolicyType.PRIVACY_POLICY,
                language="fr-FR",
            )


# ── PolicyRefinementRequest ──────────────────────────────────────

class TestPolicyRefinementRequest:
    def test_valid(self):
        r = PolicyRefinementRequest(
            original_policy="x" * 50, feedback=["Fix intro"],
            framework_id="gdpr",
        )
        assert r.refinement_type == "general"

    def test_short_policy(self):
        with pytest.raises(Exception):
            PolicyRefinementRequest(
                original_policy="short", feedback=["Fix"],
                framework_id="gdpr",
            )

    def test_valid_refinement_types(self):
        for rtype in ["general", "legal", "technical", "formatting"]:
            r = PolicyRefinementRequest(
                original_policy="x" * 50, feedback=["Fix"],
                framework_id="gdpr", refinement_type=rtype,
            )
            assert r.refinement_type == rtype

    def test_invalid_refinement_type(self):
        with pytest.raises(Exception):
            PolicyRefinementRequest(
                original_policy="x" * 50, feedback=["Fix"],
                framework_id="gdpr", refinement_type="invalid",
            )


# ── PolicyValidationResult ───────────────────────────────────────

class TestPolicyValidationResult:
    def test_valid(self):
        r = PolicyValidationResult(is_valid=True, compliance_score=0.95)
        assert r.errors == []
        assert r.warnings == []
        assert r.suggestions == []
        assert r.missing_sections == []

    def test_score_boundaries(self):
        PolicyValidationResult(is_valid=True, compliance_score=0.0)
        PolicyValidationResult(is_valid=True, compliance_score=1.0)

    def test_score_out_of_range(self):
        with pytest.raises(Exception):
            PolicyValidationResult(is_valid=True, compliance_score=1.1)


# ── PolicyGenerationResponse ────────────────────────────────────

class TestPolicyGenerationResponse:
    def test_minimal(self):
        r = PolicyGenerationResponse(
            success=True, policy_content="Policy text here",
            confidence_score=0.9, provider_used="google",
            generated_sections=["intro"], compliance_checklist=["check1"],
        )
        assert r.error_message is None
        assert r.was_cached is False
        assert r.validation_result is None

    def test_full(self):
        vr = PolicyValidationResult(is_valid=True, compliance_score=0.8)
        r = PolicyGenerationResponse(
            success=True, policy_content="Content",
            confidence_score=0.85, provider_used="openai",
            generated_sections=["s1", "s2"], compliance_checklist=["c1"],
            error_message=None, fallback_content="Fallback",
            was_cached=True, generation_time_ms=1500,
            validation_result=vr, estimated_cost=0.05, tokens_used=1000,
        )
        assert r.was_cached is True
        assert r.tokens_used == 1000


# ── PolicyRefinementResponse ────────────────────────────────────

class TestPolicyRefinementResponse:
    def test_valid(self):
        r = PolicyRefinementResponse(
            success=True, refined_content="Refined text",
            changes_made=["Updated intro"], confidence_score=0.9,
            provider_used="google",
        )
        assert r.generation_time_ms is None


# ── PolicyTemplate ──────────────────────────────────────────────

class TestPolicyTemplate:
    def test_valid(self):
        r = PolicyTemplate(
            id="t1", name="Privacy Template", description="Basic privacy",
            policy_type=PolicyType.PRIVACY_POLICY,
            framework_compatibility=["GDPR"], sections=["Intro", "Scope"],
            customization_options={"tone": ["formal", "informal"]},
        )
        assert r.language == "en-GB"


# ── PolicyTemplatesResponse ─────────────────────────────────────

class TestPolicyTemplatesResponse:
    def test_valid(self):
        r = PolicyTemplatesResponse(
            templates=[], total_count=0,
            supported_frameworks=["GDPR"], supported_languages=["en-GB"],
        )
        assert r.total_count == 0


# ── CircuitBreakerStatus ────────────────────────────────────────

class TestCircuitBreakerStatus:
    def test_defaults(self):
        r = CircuitBreakerStatus(google_status="closed", openai_status="closed")
        assert r.failure_count == 0
        assert r.last_failure_time is None


# ── AIProviderMetrics ───────────────────────────────────────────

class TestAIProviderMetrics:
    def test_defaults(self):
        r = AIProviderMetrics(provider="google")
        assert r.requests_total == 0
        assert r.requests_successful == 0
        assert r.average_response_time_ms == 0.0
        assert r.total_cost == 0.0


# ── PolicyGenerationMetrics ─────────────────────────────────────

class TestPolicyGenerationMetrics:
    def test_valid(self):
        cb = CircuitBreakerStatus(google_status="open", openai_status="closed")
        r = PolicyGenerationMetrics(circuit_breaker_status=cb)
        assert r.total_policies_generated == 0
        assert r.success_rate == 0.0
        assert r.cost_savings_percentage == 0.0

    def test_success_rate_range(self):
        cb = CircuitBreakerStatus(google_status="closed", openai_status="closed")
        with pytest.raises(Exception):
            PolicyGenerationMetrics(circuit_breaker_status=cb, success_rate=1.1)


# ── PolicyStreamingChunk ────────────────────────────────────────

class TestPolicyStreamingChunk:
    def test_valid(self):
        r = PolicyStreamingChunk(
            chunk_id="c1", content="Some content",
        )
        assert r.chunk_type == "content"
        assert r.section_name is None
        assert r.timestamp  # auto-generated
        assert r.progress is None

    def test_progress_range(self):
        r = PolicyStreamingChunk(
            chunk_id="c1", content="X", progress=0.5,
        )
        assert r.progress == 0.5

    def test_progress_out_of_range(self):
        with pytest.raises(Exception):
            PolicyStreamingChunk(chunk_id="c1", content="X", progress=1.5)


# ── PolicyStreamingMetadata ─────────────────────────────────────

class TestPolicyStreamingMetadata:
    def test_valid(self):
        r = PolicyStreamingMetadata(
            session_id="s1", policy_type=PolicyType.PRIVACY_POLICY,
            framework_id="gdpr", organization_name="Acme",
        )
        assert r.stream_type == "policy_generation"
        assert r.estimated_sections == 5
        assert r.provider == "google"
        assert r.started_at  # auto-generated
