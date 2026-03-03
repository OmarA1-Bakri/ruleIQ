"""
Pydantic Validation Models for AI Response Schema Validation

This module provides runtime validation models using Pydantic to ensure
AI responses conform to expected schemas and provide type safety.

Part of Phase 6: Response Schema Validation implementation.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, validator

# =====================================================================
# Validation Enums
# =====================================================================


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PriorityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
#     URGENT = "urgent"  # Unused variable


class ImplementationEffort(str, Enum):
#     MINIMAL = "minimal"  # Unused variable
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
#     EXTENSIVE = "extensive"  # Unused variable


class RiskLevel(str, Enum):
#     LOW = "low"  # Unused variable
#     MEDIUM = "medium"  # Unused variable
#     HIGH = "high"  # Unused variable
#     CRITICAL = "critical"  # Unused variable


    """Maturity levels for compliance programs"""
    INITIAL = "initial"
    DEVELOPING = "developing"
    DEFINED = "defined"
    MANAGED = "managed"
    OPTIMIZED = "optimized"


class MaturityLevel(str, Enum):
    INITIAL = "initial"
    DEVELOPING = "developing"
    DEFINED = "defined"
    MANAGED = "managed"
    OPTIMIZED = "optimized"


class TrendDirection(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


class InsightType(str, Enum):
    STRENGTH = "strength"
    WEAKNESS = "weakness"
    OPPORTUNITY = "opportunity"
    THREAT = "threat"


# =====================================================================
# Core Validation Models
# =====================================================================


class GapValidationModel(BaseModel):
    """Validation model for compliance gaps."""

    id: str = Field(..., min_length=1, description="Unique gap identifier")
    title: str = Field(..., min_length=1, max_length=200, description="Gap title")
    description: str = Field(..., min_length=10, description="Detailed gap description")
    severity: SeverityLevel = Field(..., description="Gap severity level")
    category: str = Field(..., min_length=1, description="Gap category")
    framework_reference: str = Field(
        ..., min_length=1, description="Framework reference",
    )
    current_state: str = Field(
        ..., min_length=1, description="Current compliance state",
    )
    target_state: str = Field(..., min_length=1, description="Target compliance state")
    impact_description: str = Field(..., min_length=1, description="Impact description")
    business_impact_score: float = Field(
        ..., ge=0.0, le=1.0, description="Business impact score",
    )
    technical_complexity: float = Field(
        ..., ge=0.0, le=1.0, description="Technical complexity score",
    )
    regulatory_requirement: bool = Field(
        ..., description="Whether this is a regulatory requirement",
    )
    estimated_effort: ImplementationEffort = Field(
        ..., description="Estimated implementation effort",
    )
    dependencies: List[str] = Field(
        default_factory=list, description="List of dependencies",
    )
    affected_systems: List[str] = Field(
        default_factory=list, description="List of affected systems",
    )
    stakeholders: List[str] = Field(
        default_factory=list, description="List of stakeholders",
    )

    @validator("id")
    def validate_gap_id(self, v):
        if not v.startswith(("gap_", "GAP_")):
            return f"gap_{v}"
        return v

    class Config:
        use_enum_values = True


class RecommendationValidationModel(BaseModel):
    """Validation model for compliance recommendations."""

    id: str = Field(..., min_length=1, description="Unique recommendation identifier")
    title: str = Field(
        ..., min_length=1, max_length=200, description="Recommendation title",
    )
    description: str = Field(
        ..., min_length=10, description="Detailed recommendation description",
    )
    priority: PriorityLevel = Field(..., description="Recommendation priority")
    category: str = Field(..., min_length=1, description="Recommendation category")
    framework_references: List[str] = Field(
        ..., min_items=1, description="Framework references",
    )
    addresses_gaps: List[str] = Field(
        default_factory=list, description="Gap IDs this addresses",
    )
    effort_estimate: ImplementationEffort = Field(
        ..., description="Implementation effort estimate",
    )
    implementation_timeline: str = Field(
        ..., min_length=1, description="Implementation timeline",
    )
    impact_score: float = Field(
        ..., ge=0.0, le=1.0, description="Implementation impact score",
    )
    cost_estimate: Optional[str] = Field(None, description="Cost estimate")
    resource_requirements: List[str] = Field(
        default_factory=list, description="Required resources",
    )
    success_criteria: List[str] = Field(
        ..., min_items=1, description="Success criteria",
    )
    potential_challenges: List[str] = Field(
        default_factory=list, description="Potential challenges",
    )
    mitigation_strategies: List[str] = Field(
        default_factory=list, description="Mitigation strategies",
    )
    automation_potential: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Automation potential",
    )
    roi_estimate: Optional[str] = Field(None, description="ROI estimate")

    @validator("id")
    def validate_recommendation_id(self, v):
        if not v.startswith(("rec_", "REC_")):
            return f"rec_{v}"
        return v

    class Config:
        use_enum_values = True


class ImplementationPhaseValidationModel(BaseModel):
    """Validation model for implementation phases."""

    phase_number: int = Field(..., ge=1, description="Phase number")
    phase_name: str = Field(..., min_length=1, description="Phase name")
    duration_weeks: int = Field(..., ge=1, description="Duration in weeks")
    deliverables: List[str] = Field(..., min_items=1, description="Phase deliverables")
    dependencies: List[str] = Field(
        default_factory=list, description="Phase dependencies",
    )
    resources_required: List[str] = Field(
        default_factory=list, description="Required resources",
    )
    success_criteria: List[str] = Field(
        ..., min_items=1, description="Success criteria",
    )


class ImplementationPlanValidationModel(BaseModel):
    """Validation model for implementation plans."""

    total_duration_weeks: int = Field(..., ge=1, description="Total duration in weeks")
    phases: List[ImplementationPhaseValidationModel] = Field(
        ..., min_items=1, description="Implementation phases",
    )
    resource_allocation: Dict[str, str] = Field(
        default_factory=dict, description="Resource allocation",
    )
    budget_estimate: Optional[str] = Field(None, description="Budget estimate")
    risk_factors: List[str] = Field(default_factory=list, description="Risk factors")
    success_metrics: List[str] = Field(..., min_items=1, description="Success metrics")
    milestone_checkpoints: List[str] = Field(
        default_factory=list, description="Milestone checkpoints",
    )

    @validator("phases")
    def validate_phase_numbers(self, v):
        phase_numbers = [p.phase_number for p in v]
        if len(set(phase_numbers)) != len(phase_numbers):
            raise ValueError("Phase numbers must be unique")
        if sorted(phase_numbers) != list(range(1, len(phase_numbers) + 1)):
            raise ValueError("Phase numbers must be consecutive starting from 1")
        return v


class RiskAssessmentValidationModel(BaseModel):
    """Validation model for risk assessments."""

    overall_risk_level: RiskLevel = Field(..., description="Overall risk level")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Risk score")
    top_risk_factors: List[str] = Field(
        ..., min_items=1, description="Top risk factors",
    )
    risk_mitigation_priorities: List[str] = Field(
        ..., min_items=1, description="Risk mitigation priorities",
    )
    regulatory_compliance_risk: float = Field(
        ..., ge=0.0, le=100.0, description="Regulatory compliance risk",
    )
    operational_risk: float = Field(
        ..., ge=0.0, le=100.0, description="Operational risk",
    )
    reputational_risk: float = Field(
        ..., ge=0.0, le=100.0, description="Reputational risk",
    )
    financial_risk: float = Field(..., ge=0.0, le=100.0, description="Financial risk")

    class Config:
        use_enum_values = True


class ComplianceInsightValidationModel(BaseModel):
    """Validation model for compliance insights."""

    insight_type: InsightType = Field(..., description="Type of insight")
    title: str = Field(..., min_length=1, max_length=200, description="Insight title")
    description: str = Field(..., min_length=10, description="Insight description")
    impact_level: SeverityLevel = Field(..., description="Impact level")
    framework_area: str = Field(..., min_length=1, description="Framework area")
    actionable_steps: List[str] = Field(
        ..., min_items=1, description="Actionable steps",
    )

    class Config:
        use_enum_values = True


class EvidenceRequirementValidationModel(BaseModel):
    """Validation model for evidence requirements."""

    evidence_type: str = Field(..., min_length=1, description="Evidence type")
    description: str = Field(..., min_length=10, description="Evidence description")
    framework_reference: str = Field(
        ..., min_length=1, description="Framework reference",
    )
    priority: PriorityLevel = Field(..., description="Collection priority")
    collection_method: str = Field(..., min_length=1, description="Collection method")
    automation_potential: float = Field(
        ..., ge=0.0, le=1.0, description="Automation potential",
    )
    estimated_effort: ImplementationEffort = Field(..., description="Estimated effort")
    validation_criteria: List[str] = Field(
        ..., min_items=1, description="Validation criteria",
    )
    retention_period: Optional[str] = Field(None, description="Retention period")

    class Config:
        use_enum_values = True


class ComplianceMetricsValidationModel(BaseModel):
    """Validation model for compliance metrics."""

    overall_compliance_score: float = Field(
        ..., ge=0.0, le=100.0, description="Overall compliance score",
    )
    framework_scores: Dict[str, float] = Field(
        default_factory=dict, description="Framework-specific scores",
    )
    maturity_level: MaturityLevel = Field(..., description="Maturity level")
    coverage_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Coverage percentage",
    )
    gap_count_by_severity: Dict[SeverityLevel, int] = Field(
        default_factory=dict, description="Gap count by severity",
    )
    improvement_trend: TrendDirection = Field(..., description="Improvement trend")

    @validator("framework_scores")
    def validate_framework_scores(self, v):
        for framework, score in v.items():
            if not (0.0 <= score <= 100.0):
                raise ValueError(
                    f"Framework score for {framework} must be between 0.0 and 100.0",
                )
        return v

    @validator("gap_count_by_severity")
    def validate_gap_counts(self, v):
        for severity, count in v.items():
            if count < 0:
                raise ValueError(f"Gap count for {severity} must be non-negative")
        return v

    class Config:
        use_enum_values = True


# =====================================================================
# Composite Response Models
# =====================================================================


class GapAnalysisValidationModel(BaseModel):
    """Validation model for gap analysis responses."""

    gaps: List[GapValidationModel] = Field(..., description="List of identified gaps")
    overall_risk_level: RiskLevel = Field(..., description="Overall risk level")
    priority_order: List[str] = Field(..., description="Gap IDs in priority order")
    estimated_total_effort: str = Field(
        ..., min_length=1, description="Total effort estimate",
    )
    critical_gap_count: int = Field(..., ge=0, description="Count of critical gaps")
    medium_high_gap_count: int = Field(
        ..., ge=0, description="Count of medium/high gaps",
    )
    compliance_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Compliance percentage",
    )
    framework_coverage: Dict[str, float] = Field(
        default_factory=dict, description="Framework coverage",
    )
    summary: str = Field(..., min_length=10, description="Executive summary")
    next_steps: List[str] = Field(
        ..., min_items=1, description="Recommended next steps",
    )

    @validator("priority_order")
    def validate_priority_order(self, v, values):
        if "gaps" in values:
            gap_ids = {gap.id for gap in values["gaps"]}
            priority_ids = set(v)
            if priority_ids != gap_ids:
                raise ValueError("Priority order must include all gap IDs")
        return v

    @validator("framework_coverage")
    def validate_framework_coverage(self, v):
        for framework, coverage in v.items():
            if not (0.0 <= coverage <= 100.0):
                raise ValueError(
                    f"Framework coverage for {framework} must be between 0.0 and 100.0",
                )
        return v

    class Config:
        use_enum_values = True


class RecommendationResponseValidationModel(BaseModel):
    """Validation model for recommendation responses."""

    recommendations: List[RecommendationValidationModel] = Field(
        ..., min_items=1, description="List of recommendations",
    )
    implementation_plan: ImplementationPlanValidationModel = Field(
        ..., description="Implementation plan",
    )
    prioritization_rationale: str = Field(
        ..., min_length=10, description="Prioritization rationale",
    )
    quick_wins: List[str] = Field(
        default_factory=list, description="Quick win recommendation IDs",
    )
    long_term_initiatives: List[str] = Field(
        default_factory=list, description="Long-term initiative IDs",
    )
    resource_summary: Dict[str, Any] = Field(
        default_factory=dict, description="Resource summary",
    )
    timeline_overview: str = Field(..., min_length=10, description="Timeline overview")
    success_metrics: List[str] = Field(..., min_items=1, description="Success metrics")

    @validator("quick_wins", "long_term_initiatives")
    def validate_recommendation_ids(self, v, values, field):
        if "recommendations" in values:
            recommendation_ids = {rec.id for rec in values["recommendations"]}
            invalid_ids = set(v) - recommendation_ids
            if invalid_ids:
                raise ValueError(
                    f"Invalid recommendation IDs in {field.name}: {invalid_ids}",
                )
        return v


class AssessmentAnalysisValidationModel(BaseModel):
    """Validation model for comprehensive assessment analysis."""

    gaps: List[GapValidationModel] = Field(..., description="Identified gaps")
    recommendations: List[RecommendationValidationModel] = Field(
        ..., description="Recommendations",
    )
    risk_assessment: RiskAssessmentValidationModel = Field(
        ..., description="Risk assessment",
    )
    compliance_insights: List[ComplianceInsightValidationModel] = Field(
        ..., description="Compliance insights",
    )
    evidence_requirements: List[EvidenceRequirementValidationModel] = Field(
        ..., description="Evidence requirements",
    )
    compliance_metrics: ComplianceMetricsValidationModel = Field(
        ..., description="Compliance metrics",
    )
    executive_summary: str = Field(..., min_length=50, description="Executive summary")
    detailed_findings: str = Field(..., min_length=100, description="Detailed findings")
    next_steps: List[str] = Field(..., min_items=1, description="Next steps")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Analysis confidence score",
    )


class GuidanceValidationModel(BaseModel):
    """Validation model for guidance responses."""

    guidance: str = Field(..., min_length=50, description="Main guidance content")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Guidance confidence score",
    )
    related_topics: List[str] = Field(..., description="Related topics")
    follow_up_suggestions: List[str] = Field(..., description="Follow-up suggestions")
    source_references: List[str] = Field(..., description="Source references")
    examples: List[str] = Field(default_factory=list, description="Examples")
    best_practices: List[str] = Field(
        default_factory=list, description="Best practices",
    )
    common_pitfalls: List[str] = Field(
        default_factory=list, description="Common pitfalls",
    )
    implementation_tips: List[str] = Field(
        default_factory=list, description="Implementation tips",
    )


class FollowUpQuestionValidationModel(BaseModel):
    """Validation model for follow-up questions."""

    question_id: str = Field(..., min_length=1, description="Question identifier")
    question_text: str = Field(..., min_length=10, description="Question text")
    category: str = Field(..., min_length=1, description="Question category")
    importance_level: PriorityLevel = Field(..., description="Question importance")
    expected_answer_type: Literal["text", "boolean", "multiple_choice", "numeric"] = (
        Field(..., description="Expected answer type"),
    )
    context: str = Field(..., min_length=1, description="Question context")
    validation_criteria: List[str] = Field(
        default_factory=list, description="Validation criteria",
    )

    class Config:
        use_enum_values = True


class FollowUpValidationModel(BaseModel):
    """Validation model for follow-up responses."""

    follow_up_questions: List[FollowUpQuestionValidationModel] = Field(
        ..., description="Follow-up questions",
    )
    recommendations: List[str] = Field(..., description="Immediate recommendations")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Response confidence",
    )
    assessment_completeness: float = Field(
        ..., ge=0.0, le=1.0, description="Assessment completeness",
    )
    priority_areas: List[str] = Field(..., description="Priority areas")
    suggested_next_steps: List[str] = Field(
        ..., min_items=1, description="Suggested next steps",
    )


class IntentClassificationValidationModel(BaseModel):
    """Validation model for intent classification."""

    intent_type: Literal[
        "evidence_query",
        "compliance_check",
        "guidance_request",
        "general_query",
        "assessment_help",
    ] = Field(..., description="Classified intent type")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Classification confidence",
    )
    entities: Dict[str, List[str]] = Field(..., description="Extracted entities")
    context_requirements: List[str] = Field(
        default_factory=list, description="Context requirements",
    )
    suggested_actions: List[str] = Field(
        default_factory=list, description="Suggested actions",
    )


# =====================================================================
# Response Metadata Models
# =====================================================================


class ResponseMetadataValidationModel(BaseModel):
    """Validation model for response metadata."""

    response_id: str = Field(..., min_length=1, description="Response identifier")
    timestamp: str = Field(..., description="Response timestamp")
    model_used: str = Field(..., min_length=1, description="AI model used")
    processing_time_ms: int = Field(
        ..., ge=0, description="Processing time in milliseconds",
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence",
    )
    schema_version: str = Field(..., min_length=1, description="Schema version")
    validation_status: Literal["valid", "invalid", "partially_valid"] = Field(
        ..., description="Validation status",
    )
    validation_errors: List[str] = Field(
        default_factory=list, description="Validation errors",
    )

    @validator("timestamp")
    def validate_timestamp(self, v):
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Timestamp must be in ISO format")
        return v


class StructuredAIResponseValidationModel(BaseModel):
    """Validation model for structured AI responses."""

    metadata: ResponseMetadataValidationModel = Field(
        ..., description="Response metadata",
    )
    response_type: str = Field(..., min_length=1, description="Response type")
    payload: Union[
        GapAnalysisValidationModel,
        RecommendationResponseValidationModel,
        AssessmentAnalysisValidationModel,
        GuidanceValidationModel,
        FollowUpValidationModel,
        IntentClassificationValidationModel,
        Dict[str, Any],
    ] = Field(..., description="Response payload")
    validation_passed: bool = Field(..., description="Whether validation passed")
    fallback_used: bool = Field(default=False, description="Whether fallback was used")


# =====================================================================
# Validation Functions
# =====================================================================


def validate_ai_response(
    response_data: Dict[str, Any], response_type: str
) -> tuple[bool, List[str], Optional[BaseModel]]:
    """
    Validate AI response against appropriate schema.

    Args:
        response_data: Raw AI response data
        response_type: Type of response to validate against

    Returns:
        Tuple of (is_valid, errors, validated_model)
    """
    validation_models = {
        "gap_analysis": GapAnalysisValidationModel,
        "recommendations": RecommendationResponseValidationModel,
        "assessment_analysis": AssessmentAnalysisValidationModel,
        "guidance": GuidanceValidationModel,
        "followup": FollowUpValidationModel,
        "intent_classification": IntentClassificationValidationModel,
    }

    model_class = validation_models.get(response_type)
    if not model_class:
        return False, [f"Unknown response type: {response_type}"], None

    try:
        validated_model = model_class(**response_data)
        return True, [], validated_model
    except Exception as e:
        errors = []
        if hasattr(e, "errors"):
            for error in e.errors():
                errors.append(
                    f"{'.'.join(str(x) for x in error['loc'])}: {error['msg']}",
                )
        else:
            errors.append(str(e))
        return False, errors, None


def create_validation_report(
    response_data: Dict[str, Any], response_type: str
) -> Dict[str, Any]:
    """Create a detailed validation report for an AI response."""
    is_valid, errors, validated_model = validate_ai_response(
        response_data, response_type,
    )

    return {
        "is_valid": is_valid,
        "response_type": response_type,
        "validation_errors": errors,
        "error_count": len(errors),
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0.0",
        "has_model": validated_model is not None,
    }
