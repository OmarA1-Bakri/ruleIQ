"""
Tests for services.ai.validation_models module.

Covers all Pydantic validation models, enums, custom validators,
and validation utility functions.
"""

import pytest
from datetime import datetime, timezone

from services.ai.validation_models import (
    SeverityLevel,
    PriorityLevel,
    ImplementationEffort,
    RiskLevel,
    MaturityLevel,
    TrendDirection,
    InsightType,
    GapValidationModel,
    RecommendationValidationModel,
    ImplementationPhaseValidationModel,
    ImplementationPlanValidationModel,
    RiskAssessmentValidationModel,
    ComplianceInsightValidationModel,
    EvidenceRequirementValidationModel,
    ComplianceMetricsValidationModel,
    GapAnalysisValidationModel,
    RecommendationResponseValidationModel,
    AssessmentAnalysisValidationModel,
    GuidanceValidationModel,
    FollowUpQuestionValidationModel,
    FollowUpValidationModel,
    IntentClassificationValidationModel,
    ResponseMetadataValidationModel,
    validate_ai_response,
    create_validation_report,
)


# =====================================================================
# Enum Tests
# =====================================================================


class TestValidationEnums:
    def test_severity_level(self):
        assert SeverityLevel.LOW == "low"
        assert SeverityLevel.MEDIUM == "medium"
        assert SeverityLevel.HIGH == "high"
        assert SeverityLevel.CRITICAL == "critical"

    def test_priority_level(self):
        assert PriorityLevel.LOW == "low"
        assert PriorityLevel.MEDIUM == "medium"
        assert PriorityLevel.HIGH == "high"

    def test_implementation_effort(self):
        assert ImplementationEffort.LOW == "low"
        assert ImplementationEffort.MEDIUM == "medium"
        assert ImplementationEffort.HIGH == "high"

    def test_risk_level_maturity_values(self):
        assert RiskLevel.INITIAL == "initial"
        assert RiskLevel.DEVELOPING == "developing"
        assert RiskLevel.DEFINED == "defined"
        assert RiskLevel.MANAGED == "managed"
        assert RiskLevel.OPTIMIZED == "optimized"

    def test_maturity_level(self):
        assert MaturityLevel.INITIAL == "initial"
        assert MaturityLevel.OPTIMIZED == "optimized"

    def test_trend_direction(self):
        assert TrendDirection.IMPROVING == "improving"
        assert TrendDirection.STABLE == "stable"
        assert TrendDirection.DECLINING == "declining"

    def test_insight_type(self):
        assert InsightType.STRENGTH == "strength"
        assert InsightType.WEAKNESS == "weakness"
        assert InsightType.OPPORTUNITY == "opportunity"
        assert InsightType.THREAT == "threat"

    def test_enum_invalid_value(self):
        with pytest.raises(ValueError):
            SeverityLevel("invalid")


# =====================================================================
# Helper: minimal valid data builders
# =====================================================================


def _gap_data(**overrides):
    base = {
        "id": "gap_1",
        "title": "Test Gap",
        "description": "This is a test gap description with enough chars",
        "severity": "high",
        "category": "data_protection",
        "framework_reference": "GDPR Art. 32",
        "current_state": "No encryption",
        "target_state": "AES-256",
        "impact_description": "Risk of data breach",
        "business_impact_score": 0.8,
        "technical_complexity": 0.5,
        "regulatory_requirement": True,
        "estimated_effort": "medium",
    }
    base.update(overrides)
    return base


def _recommendation_data(**overrides):
    base = {
        "id": "rec_1",
        "title": "Implement encryption",
        "description": "Deploy AES-256 encryption for data at rest storage",
        "priority": "high",
        "category": "data_protection",
        "framework_references": ["GDPR Art. 32"],
        "effort_estimate": "medium",
        "implementation_timeline": "2-4 weeks",
        "impact_score": 0.9,
        "success_criteria": ["All data encrypted"],
    }
    base.update(overrides)
    return base


def _phase_data(**overrides):
    base = {
        "phase_number": 1,
        "phase_name": "Planning",
        "duration_weeks": 2,
        "deliverables": ["Architecture doc"],
        "success_criteria": ["Approved design"],
    }
    base.update(overrides)
    return base


def _risk_assessment_data(**overrides):
    base = {
        "overall_risk_level": "defined",
        "risk_score": 45.0,
        "top_risk_factors": ["No encryption"],
        "risk_mitigation_priorities": ["Deploy encryption"],
        "regulatory_compliance_risk": 60.0,
        "operational_risk": 30.0,
        "reputational_risk": 40.0,
        "financial_risk": 50.0,
    }
    base.update(overrides)
    return base


def _compliance_insight_data(**overrides):
    base = {
        "insight_type": "strength",
        "title": "Strong access controls",
        "description": "MFA deployed across all systems properly",
        "impact_level": "low",
        "framework_area": "Access Control",
        "actionable_steps": ["Maintain current controls"],
    }
    base.update(overrides)
    return base


def _evidence_requirement_data(**overrides):
    base = {
        "evidence_type": "policy_document",
        "description": "Data protection policy document required for audit",
        "framework_reference": "GDPR Art. 24",
        "priority": "high",
        "collection_method": "Document review",
        "automation_potential": 0.3,
        "estimated_effort": "low",
        "validation_criteria": ["Policy approved by DPO"],
    }
    base.update(overrides)
    return base


def _compliance_metrics_data(**overrides):
    base = {
        "overall_compliance_score": 72.5,
        "framework_scores": {"GDPR": 80.0},
        "maturity_level": "defined",
        "coverage_percentage": 75.0,
        "gap_count_by_severity": {},
        "improvement_trend": "improving",
    }
    base.update(overrides)
    return base


# =====================================================================
# GapValidationModel Tests
# =====================================================================


class TestGapValidationModel:
    def test_valid_gap(self):
        model = GapValidationModel(**_gap_data())
        assert model.id == "gap_1"
        assert model.severity == "high"
        assert model.business_impact_score == 0.8

    def test_id_prefix_auto_added(self):
        model = GapValidationModel(**_gap_data(id="my_gap"))
        assert model.id == "gap_my_gap"

    def test_id_already_prefixed(self):
        model = GapValidationModel(**_gap_data(id="gap_existing"))
        assert model.id == "gap_existing"

    def test_id_GAP_prefix_preserved(self):
        model = GapValidationModel(**_gap_data(id="GAP_123"))
        assert model.id == "GAP_123"

    def test_empty_id_rejected(self):
        with pytest.raises(Exception):
            GapValidationModel(**_gap_data(id=""))

    def test_title_too_long(self):
        with pytest.raises(Exception):
            GapValidationModel(**_gap_data(title="X" * 201))

    def test_description_too_short(self):
        with pytest.raises(Exception):
            GapValidationModel(**_gap_data(description="short"))

    def test_business_impact_score_out_of_range(self):
        with pytest.raises(Exception):
            GapValidationModel(**_gap_data(business_impact_score=1.5))

    def test_business_impact_score_negative(self):
        with pytest.raises(Exception):
            GapValidationModel(**_gap_data(business_impact_score=-0.1))

    def test_technical_complexity_bounds(self):
        model = GapValidationModel(**_gap_data(technical_complexity=0.0))
        assert model.technical_complexity == 0.0
        model = GapValidationModel(**_gap_data(technical_complexity=1.0))
        assert model.technical_complexity == 1.0

    def test_optional_lists_default_empty(self):
        model = GapValidationModel(**_gap_data())
        assert model.dependencies == []
        assert model.affected_systems == []
        assert model.stakeholders == []

    def test_with_optional_lists(self):
        model = GapValidationModel(
            **_gap_data(
                dependencies=["dep1"],
                affected_systems=["sys1"],
                stakeholders=["DPO"],
            )
        )
        assert model.dependencies == ["dep1"]

    def test_invalid_severity(self):
        with pytest.raises(Exception):
            GapValidationModel(**_gap_data(severity="extreme"))

    def test_invalid_effort(self):
        with pytest.raises(Exception):
            GapValidationModel(**_gap_data(estimated_effort="massive"))


# =====================================================================
# RecommendationValidationModel Tests
# =====================================================================


class TestRecommendationValidationModel:
    def test_valid_recommendation(self):
        model = RecommendationValidationModel(**_recommendation_data())
        assert model.id == "rec_1"
        assert model.priority == "high"

    def test_id_prefix_auto_added(self):
        model = RecommendationValidationModel(**_recommendation_data(id="my_rec"))
        assert model.id == "rec_my_rec"

    def test_id_REC_prefix_preserved(self):
        model = RecommendationValidationModel(**_recommendation_data(id="REC_456"))
        assert model.id == "REC_456"

    def test_framework_references_required(self):
        with pytest.raises(Exception):
            RecommendationValidationModel(**_recommendation_data(framework_references=[]))

    def test_impact_score_bounds(self):
        model = RecommendationValidationModel(**_recommendation_data(impact_score=0.0))
        assert model.impact_score == 0.0
        model = RecommendationValidationModel(**_recommendation_data(impact_score=1.0))
        assert model.impact_score == 1.0

    def test_impact_score_out_of_range(self):
        with pytest.raises(Exception):
            RecommendationValidationModel(**_recommendation_data(impact_score=1.1))

    def test_automation_potential_default(self):
        model = RecommendationValidationModel(**_recommendation_data())
        assert model.automation_potential == 0.0

    def test_success_criteria_required(self):
        with pytest.raises(Exception):
            RecommendationValidationModel(**_recommendation_data(success_criteria=[]))

    def test_optional_cost_estimate(self):
        model = RecommendationValidationModel(**_recommendation_data(cost_estimate="£10K"))
        assert model.cost_estimate == "£10K"

    def test_optional_roi_estimate(self):
        model = RecommendationValidationModel(**_recommendation_data(roi_estimate="3x"))
        assert model.roi_estimate == "3x"


# =====================================================================
# ImplementationPhaseValidationModel Tests
# =====================================================================


class TestImplementationPhaseValidationModel:
    def test_valid_phase(self):
        model = ImplementationPhaseValidationModel(**_phase_data())
        assert model.phase_number == 1
        assert model.duration_weeks == 2

    def test_phase_number_must_be_ge_1(self):
        with pytest.raises(Exception):
            ImplementationPhaseValidationModel(**_phase_data(phase_number=0))

    def test_duration_must_be_ge_1(self):
        with pytest.raises(Exception):
            ImplementationPhaseValidationModel(**_phase_data(duration_weeks=0))

    def test_deliverables_required(self):
        with pytest.raises(Exception):
            ImplementationPhaseValidationModel(**_phase_data(deliverables=[]))

    def test_success_criteria_required(self):
        with pytest.raises(Exception):
            ImplementationPhaseValidationModel(**_phase_data(success_criteria=[]))

    def test_optional_lists_default_empty(self):
        model = ImplementationPhaseValidationModel(**_phase_data())
        assert model.dependencies == []
        assert model.resources_required == []


# =====================================================================
# ImplementationPlanValidationModel Tests
# =====================================================================


class TestImplementationPlanValidationModel:
    def test_valid_plan(self):
        plan = ImplementationPlanValidationModel(
            total_duration_weeks=4,
            phases=[_phase_data()],
            success_metrics=["Done"],
        )
        assert plan.total_duration_weeks == 4
        assert len(plan.phases) == 1

    def test_consecutive_phase_numbers(self):
        plan = ImplementationPlanValidationModel(
            total_duration_weeks=8,
            phases=[
                _phase_data(phase_number=1),
                _phase_data(phase_number=2, phase_name="Execution"),
            ],
            success_metrics=["Done"],
        )
        assert len(plan.phases) == 2

    def test_non_consecutive_phase_numbers_rejected(self):
        with pytest.raises(Exception):
            ImplementationPlanValidationModel(
                total_duration_weeks=8,
                phases=[
                    _phase_data(phase_number=1),
                    _phase_data(phase_number=3, phase_name="Skipped"),
                ],
                success_metrics=["Done"],
            )

    def test_duplicate_phase_numbers_rejected(self):
        with pytest.raises(Exception):
            ImplementationPlanValidationModel(
                total_duration_weeks=4,
                phases=[
                    _phase_data(phase_number=1),
                    _phase_data(phase_number=1, phase_name="Duplicate"),
                ],
                success_metrics=["Done"],
            )

    def test_phases_required(self):
        with pytest.raises(Exception):
            ImplementationPlanValidationModel(
                total_duration_weeks=4,
                phases=[],
                success_metrics=["Done"],
            )

    def test_success_metrics_required(self):
        with pytest.raises(Exception):
            ImplementationPlanValidationModel(
                total_duration_weeks=4,
                phases=[_phase_data()],
                success_metrics=[],
            )


# =====================================================================
# RiskAssessmentValidationModel Tests
# =====================================================================


class TestRiskAssessmentValidationModel:
    def test_valid_assessment(self):
        model = RiskAssessmentValidationModel(**_risk_assessment_data())
        assert model.risk_score == 45.0

    def test_risk_score_bounds(self):
        model = RiskAssessmentValidationModel(**_risk_assessment_data(risk_score=0.0))
        assert model.risk_score == 0.0
        model = RiskAssessmentValidationModel(**_risk_assessment_data(risk_score=100.0))
        assert model.risk_score == 100.0

    def test_risk_score_out_of_range(self):
        with pytest.raises(Exception):
            RiskAssessmentValidationModel(**_risk_assessment_data(risk_score=101.0))

    def test_risk_score_negative(self):
        with pytest.raises(Exception):
            RiskAssessmentValidationModel(**_risk_assessment_data(risk_score=-1.0))

    def test_all_risk_types_validated(self):
        with pytest.raises(Exception):
            RiskAssessmentValidationModel(
                **_risk_assessment_data(regulatory_compliance_risk=101.0)
            )
        with pytest.raises(Exception):
            RiskAssessmentValidationModel(**_risk_assessment_data(operational_risk=-1.0))

    def test_top_risk_factors_required(self):
        with pytest.raises(Exception):
            RiskAssessmentValidationModel(**_risk_assessment_data(top_risk_factors=[]))


# =====================================================================
# ComplianceInsightValidationModel Tests
# =====================================================================


class TestComplianceInsightValidationModel:
    def test_valid_insight(self):
        model = ComplianceInsightValidationModel(**_compliance_insight_data())
        assert model.insight_type == "strength"

    def test_all_insight_types(self):
        for it in ["strength", "weakness", "opportunity", "threat"]:
            model = ComplianceInsightValidationModel(
                **_compliance_insight_data(insight_type=it)
            )
            assert model.insight_type == it

    def test_invalid_insight_type(self):
        with pytest.raises(Exception):
            ComplianceInsightValidationModel(
                **_compliance_insight_data(insight_type="invalid")
            )

    def test_actionable_steps_required(self):
        with pytest.raises(Exception):
            ComplianceInsightValidationModel(
                **_compliance_insight_data(actionable_steps=[])
            )


# =====================================================================
# EvidenceRequirementValidationModel Tests
# =====================================================================


class TestEvidenceRequirementValidationModel:
    def test_valid_requirement(self):
        model = EvidenceRequirementValidationModel(**_evidence_requirement_data())
        assert model.evidence_type == "policy_document"

    def test_automation_potential_bounds(self):
        model = EvidenceRequirementValidationModel(
            **_evidence_requirement_data(automation_potential=0.0)
        )
        assert model.automation_potential == 0.0
        model = EvidenceRequirementValidationModel(
            **_evidence_requirement_data(automation_potential=1.0)
        )
        assert model.automation_potential == 1.0

    def test_automation_potential_out_of_range(self):
        with pytest.raises(Exception):
            EvidenceRequirementValidationModel(
                **_evidence_requirement_data(automation_potential=1.1)
            )


# =====================================================================
# ComplianceMetricsValidationModel Tests
# =====================================================================


class TestComplianceMetricsValidationModel:
    def test_valid_metrics(self):
        model = ComplianceMetricsValidationModel(**_compliance_metrics_data())
        assert model.overall_compliance_score == 72.5

    def test_score_out_of_range(self):
        with pytest.raises(Exception):
            ComplianceMetricsValidationModel(
                **_compliance_metrics_data(overall_compliance_score=101.0)
            )

    def test_framework_scores_validated(self):
        with pytest.raises(Exception):
            ComplianceMetricsValidationModel(
                **_compliance_metrics_data(framework_scores={"GDPR": 150.0})
            )

    def test_framework_scores_negative(self):
        with pytest.raises(Exception):
            ComplianceMetricsValidationModel(
                **_compliance_metrics_data(framework_scores={"GDPR": -1.0})
            )

    def test_gap_count_non_negative(self):
        model = ComplianceMetricsValidationModel(
            **_compliance_metrics_data(gap_count_by_severity={"high": 3})
        )
        assert model.gap_count_by_severity == {"high": 3}

    def test_maturity_levels(self):
        for level in ["initial", "developing", "defined", "managed", "optimized"]:
            model = ComplianceMetricsValidationModel(
                **_compliance_metrics_data(maturity_level=level)
            )
            assert model.maturity_level == level

    def test_trend_directions(self):
        for trend in ["improving", "stable", "declining"]:
            model = ComplianceMetricsValidationModel(
                **_compliance_metrics_data(improvement_trend=trend)
            )
            assert model.improvement_trend == trend


# =====================================================================
# GapAnalysisValidationModel Tests
# =====================================================================


class TestGapAnalysisValidationModel:
    def test_valid_gap_analysis(self):
        gap = _gap_data()
        model = GapAnalysisValidationModel(
            gaps=[gap],
            overall_risk_level="defined",
            priority_order=["gap_1"],
            estimated_total_effort="6 months effort total",
            critical_gap_count=1,
            medium_high_gap_count=0,
            compliance_percentage=65.0,
            summary="Several critical gaps identified in the analysis period",
            next_steps=["Address critical gaps first"],
        )
        assert model.compliance_percentage == 65.0
        assert model.critical_gap_count == 1

    def test_priority_order_must_match_gaps(self):
        gap = _gap_data()
        with pytest.raises(Exception):
            GapAnalysisValidationModel(
                gaps=[gap],
                overall_risk_level="defined",
                priority_order=["gap_nonexistent"],
                estimated_total_effort="6 months effort total",
                critical_gap_count=0,
                medium_high_gap_count=0,
                compliance_percentage=65.0,
                summary="Several critical gaps identified in the analysis",
                next_steps=["Step 1"],
            )

    def test_framework_coverage_validated(self):
        gap = _gap_data()
        with pytest.raises(Exception):
            GapAnalysisValidationModel(
                gaps=[gap],
                overall_risk_level="defined",
                priority_order=["gap_1"],
                estimated_total_effort="6 month effort",
                critical_gap_count=0,
                medium_high_gap_count=0,
                compliance_percentage=65.0,
                framework_coverage={"GDPR": 150.0},
                summary="Several gaps with framework coverage issues",
                next_steps=["Fix"],
            )


# =====================================================================
# RecommendationResponseValidationModel Tests
# =====================================================================


class TestRecommendationResponseValidationModel:
    def test_valid_response(self):
        model = RecommendationResponseValidationModel(
            recommendations=[_recommendation_data()],
            implementation_plan={
                "total_duration_weeks": 4,
                "phases": [_phase_data()],
                "success_metrics": ["Done"],
            },
            prioritization_rationale="Based on risk analysis and business impact",
            timeline_overview="4 weeks total implementation timeline",
            success_metrics=["All gaps closed"],
        )
        assert len(model.recommendations) == 1

    def test_quick_wins_validated(self):
        with pytest.raises(Exception):
            RecommendationResponseValidationModel(
                recommendations=[_recommendation_data()],
                implementation_plan={
                    "total_duration_weeks": 4,
                    "phases": [_phase_data()],
                    "success_metrics": ["Done"],
                },
                prioritization_rationale="Based on risk analysis and business impact",
                quick_wins=["nonexistent_rec"],
                timeline_overview="4 weeks total effort for implementation",
                success_metrics=["All gaps closed"],
            )


# =====================================================================
# IntentClassificationValidationModel Tests
# =====================================================================


class TestIntentClassificationValidationModel:
    def test_valid_classification(self):
        model = IntentClassificationValidationModel(
            intent_type="compliance_check",
            confidence=0.95,
            entities={"frameworks": ["GDPR"]},
        )
        assert model.intent_type == "compliance_check"
        assert model.confidence == 0.95

    def test_all_intent_types(self):
        for it in [
            "evidence_query",
            "compliance_check",
            "guidance_request",
            "general_query",
            "assessment_help",
        ]:
            model = IntentClassificationValidationModel(
                intent_type=it,
                confidence=0.8,
                entities={},
            )
            assert model.intent_type == it

    def test_invalid_intent_type(self):
        with pytest.raises(Exception):
            IntentClassificationValidationModel(
                intent_type="invalid_type",
                confidence=0.8,
                entities={},
            )

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            IntentClassificationValidationModel(
                intent_type="compliance_check",
                confidence=1.5,
                entities={},
            )


# =====================================================================
# ResponseMetadataValidationModel Tests
# =====================================================================


class TestResponseMetadataValidationModel:
    def test_valid_metadata(self):
        model = ResponseMetadataValidationModel(
            response_id="resp_1",
            timestamp="2024-01-01T00:00:00Z",
            model_used="gemini-pro",
            processing_time_ms=1500,
            confidence_score=0.9,
            schema_version="1.0",
            validation_status="valid",
        )
        assert model.model_used == "gemini-pro"

    def test_invalid_timestamp(self):
        with pytest.raises(Exception):
            ResponseMetadataValidationModel(
                response_id="resp_1",
                timestamp="not-a-date",
                model_used="gemini-pro",
                processing_time_ms=100,
                confidence_score=0.9,
                schema_version="1.0",
                validation_status="valid",
            )

    def test_validation_status_values(self):
        for status in ["valid", "invalid", "partially_valid"]:
            model = ResponseMetadataValidationModel(
                response_id="resp_1",
                timestamp="2024-06-15T12:00:00+00:00",
                model_used="gemini-pro",
                processing_time_ms=100,
                confidence_score=0.9,
                schema_version="1.0",
                validation_status=status,
            )
            assert model.validation_status == status

    def test_processing_time_non_negative(self):
        with pytest.raises(Exception):
            ResponseMetadataValidationModel(
                response_id="resp_1",
                timestamp="2024-01-01T00:00:00Z",
                model_used="gemini-pro",
                processing_time_ms=-1,
                confidence_score=0.9,
                schema_version="1.0",
                validation_status="valid",
            )


# =====================================================================
# validate_ai_response Tests
# =====================================================================


class TestValidateAiResponse:
    def test_unknown_response_type(self):
        is_valid, errors, model = validate_ai_response({}, "unknown_type")
        assert is_valid is False
        assert "Unknown response type: unknown_type" in errors
        assert model is None

    def test_valid_intent_classification(self):
        data = {
            "intent_type": "compliance_check",
            "confidence": 0.95,
            "entities": {"frameworks": ["GDPR"]},
        }
        is_valid, errors, model = validate_ai_response(data, "intent_classification")
        assert is_valid is True
        assert errors == []
        assert model is not None

    def test_invalid_data_returns_errors(self):
        data = {"intent_type": "invalid", "confidence": 2.0, "entities": {}}
        is_valid, errors, model = validate_ai_response(data, "intent_classification")
        assert is_valid is False
        assert len(errors) > 0
        assert model is None

    def test_valid_guidance(self):
        data = {
            "guidance": "You should implement encryption for all data at rest to comply with GDPR",
            "confidence_score": 0.9,
            "related_topics": ["encryption"],
            "follow_up_suggestions": ["Review key management"],
            "source_references": ["GDPR Art. 32"],
        }
        is_valid, errors, model = validate_ai_response(data, "guidance")
        assert is_valid is True


# =====================================================================
# create_validation_report Tests
# =====================================================================


class TestCreateValidationReport:
    def test_valid_report(self):
        data = {
            "intent_type": "compliance_check",
            "confidence": 0.95,
            "entities": {},
        }
        report = create_validation_report(data, "intent_classification")
        assert report["is_valid"] is True
        assert report["error_count"] == 0
        assert report["response_type"] == "intent_classification"
        assert report["schema_version"] == "1.0.0"
        assert report["has_model"] is True
        assert "validated_at" in report

    def test_invalid_report(self):
        report = create_validation_report({}, "intent_classification")
        assert report["is_valid"] is False
        assert report["error_count"] > 0
        assert report["has_model"] is False

    def test_unknown_type_report(self):
        report = create_validation_report({}, "nonexistent_type")
        assert report["is_valid"] is False
        assert "Unknown response type" in report["validation_errors"][0]


# =====================================================================
# FollowUpQuestionValidationModel Tests
# =====================================================================


class TestFollowUpQuestionValidationModel:
    def test_valid_question(self):
        model = FollowUpQuestionValidationModel(
            question_id="q_1",
            question_text="Do you process special category health data?",
            category="data_classification",
            importance_level="high",
            expected_answer_type="boolean",
            context="Determines special category requirements",
        )
        assert model.question_id == "q_1"

    def test_answer_types(self):
        for at in ["text", "boolean", "multiple_choice", "numeric"]:
            model = FollowUpQuestionValidationModel(
                question_id="q_1",
                question_text="Sample question text longer than 10",
                category="general",
                importance_level="low",
                expected_answer_type=at,
                context="Context",
            )
            assert model.expected_answer_type == at


class TestFollowUpValidationModel:
    def test_valid_followup(self):
        model = FollowUpValidationModel(
            follow_up_questions=[],
            recommendations=["Review data categories"],
            confidence_score=0.8,
            assessment_completeness=0.6,
            priority_areas=["data_classification"],
            suggested_next_steps=["Complete survey"],
        )
        assert model.confidence_score == 0.8
        assert model.assessment_completeness == 0.6

    def test_suggested_next_steps_required(self):
        with pytest.raises(Exception):
            FollowUpValidationModel(
                follow_up_questions=[],
                recommendations=["Review"],
                confidence_score=0.8,
                assessment_completeness=0.6,
                priority_areas=["data"],
                suggested_next_steps=[],
            )
