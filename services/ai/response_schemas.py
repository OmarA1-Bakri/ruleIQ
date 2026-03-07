"""
AI Response Schema Definitions for ruleIQ Compliance Platform

This module defines TypedDict schemas for all AI response types to ensure
structured output validation and type safety across the platform.

Part of Phase 6: Response Schema Validation implementation.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

# =====================================================================
# Core Response Types and Enums
# =====================================================================


class SeverityLevel(str, Enum):
    """Severity levels for gaps, issues, and recommendations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PriorityLevel(str, Enum):
    """Priority levels for recommendations and actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


#     URGENT = "urgent"  # Unused variable


class ConfidenceLevel(str, Enum):
    """Confidence levels for AI assessments."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


#     VERY_HIGH = "very_high"  # Unused variable


class ImplementationEffort(str, Enum):
    """Implementation effort estimates."""

    #     MINIMAL = "minimal"  # < 1 week  # Unused variable
    LOW = "low"  # 1-2 weeks
    MEDIUM = "medium"  # 2-6 weeks
    HIGH = "high"  # 6-12 weeks


#     EXTENSIVE = "extensive"  # > 12 weeks  # Unused variable


class RiskLevel(str, Enum):
    """Risk assessment levels."""


#     LOW = "low"  # Unused variable
#     MEDIUM = "medium"  # Unused variable
#     HIGH = "high"  # Unused variable
#     CRITICAL = "critical"  # Unused variable


# =====================================================================
# Gap Analysis Schemas
# =====================================================================


class Gap(TypedDict):
    """Individual compliance gap identified in assessment."""

    id: str
    title: str
    description: str
    severity: SeverityLevel
    category: str
    framework_reference: str
    current_state: str
    target_state: str
    impact_description: str
    business_impact_score: float  # 0.0 - 1.0
    technical_complexity: float  # 0.0 - 1.0
    regulatory_requirement: bool
    estimated_effort: ImplementationEffort
    dependencies: List[str]
    affected_systems: List[str]
    stakeholders: List[str]


class GapAnalysisResponse(TypedDict):
    """Complete gap analysis response structure."""

    gaps: List[Gap]
    overall_risk_level: RiskLevel
    priority_order: List[str]  # Gap IDs in priority order
    estimated_total_effort: str
    critical_gap_count: int
    medium_high_gap_count: int
    compliance_percentage: float  # 0.0 - 100.0
    framework_coverage: Dict[str, float]  # Framework -> coverage %
    summary: str
    next_steps: List[str]


# =====================================================================
# Recommendation Schemas
# =====================================================================


class Recommendation(TypedDict):
    """Individual compliance recommendation."""

    id: str
    title: str
    description: str
    priority: PriorityLevel
    category: str
    framework_references: List[str]
    addresses_gaps: List[str]  # Gap IDs this addresses
    effort_estimate: ImplementationEffort
    implementation_timeline: str
    impact_score: float  # 0.0 - 1.0
    cost_estimate: Optional[str]
    resource_requirements: List[str]
    success_criteria: List[str]
    potential_challenges: List[str]
    mitigation_strategies: List[str]
    automation_potential: float  # 0.0 - 1.0
    roi_estimate: Optional[str]


class ImplementationPhase(TypedDict):
    """Implementation phase for recommendation rollout."""

    phase_number: int
    phase_name: str
    duration_weeks: int
    deliverables: List[str]
    dependencies: List[str]
    resources_required: List[str]
    success_criteria: List[str]


class ImplementationPlan(TypedDict):
    """Complete implementation plan for recommendations."""

    total_duration_weeks: int
    phases: List[ImplementationPhase]
    resource_allocation: Dict[str, str]
    budget_estimate: Optional[str]
    risk_factors: List[str]
    success_metrics: List[str]
    milestone_checkpoints: List[str]


class RecommendationResponse(TypedDict):
    """Complete recommendation response structure."""

    recommendations: List[Recommendation]
    implementation_plan: ImplementationPlan
    prioritization_rationale: str
    quick_wins: List[str]  # Recommendation IDs for quick wins
    long_term_initiatives: List[str]  # Recommendation IDs for long-term
    resource_summary: Dict[str, Any]
    timeline_overview: str
    success_metrics: List[str]


# =====================================================================
# Assessment Analysis Schemas
# =====================================================================


class ComplianceInsight(TypedDict):
    """Key compliance insight from assessment analysis."""

    insight_type: Literal["strength", "weakness", "opportunity", "threat"]
    title: str
    description: str
    impact_level: SeverityLevel
    framework_area: str
    actionable_steps: List[str]


class EvidenceRequirement(TypedDict):
    """Evidence requirement identified from assessment."""

    evidence_type: str
    description: str
    framework_reference: str
    priority: PriorityLevel
    collection_method: str
    automation_potential: float
    estimated_effort: ImplementationEffort
    validation_criteria: List[str]
    retention_period: Optional[str]


class RiskAssessment(TypedDict):
    """Risk assessment results."""

    overall_risk_level: RiskLevel
    risk_score: float  # 0.0 - 100.0
    top_risk_factors: List[str]
    risk_mitigation_priorities: List[str]
    regulatory_compliance_risk: float
    operational_risk: float
    reputational_risk: float
    financial_risk: float


class ComplianceMetrics(TypedDict):
    """Quantitative compliance metrics."""

    overall_compliance_score: float  # 0.0 - 100.0
    framework_scores: Dict[str, float]
    maturity_level: Literal["initial", "developing", "defined", "managed", "optimized"]
    coverage_percentage: float
    gap_count_by_severity: Dict[SeverityLevel, int]
    improvement_trend: Literal["improving", "stable", "declining"]


class AssessmentAnalysisResponse(TypedDict):
    """Complete assessment analysis response structure."""

    gaps: List[Gap]
    recommendations: List[Recommendation]
    risk_assessment: RiskAssessment
    compliance_insights: List[ComplianceInsight]
    evidence_requirements: List[EvidenceRequirement]
    compliance_metrics: ComplianceMetrics
    executive_summary: str
    detailed_findings: str
    next_steps: List[str]
    confidence_score: float  # 0.0 - 1.0


# =====================================================================
# Help and Guidance Schemas
# =====================================================================


class GuidanceResponse(TypedDict):
    """Response for assessment question help/guidance."""

    guidance: str
    confidence_score: float
    related_topics: List[str]
    follow_up_suggestions: List[str]
    source_references: List[str]
    examples: List[str]
    best_practices: List[str]
    common_pitfalls: List[str]
    implementation_tips: List[str]


class FollowUpQuestion(TypedDict):
    """Follow-up question for assessment completion."""

    question_id: str
    question_text: str
    category: str
    importance_level: PriorityLevel
    expected_answer_type: Literal["text", "boolean", "multiple_choice", "numeric"]
    context: str
    validation_criteria: List[str]


class FollowUpResponse(TypedDict):
    """Response for assessment follow-up questions."""

    follow_up_questions: List[FollowUpQuestion]
    recommendations: List[str]
    confidence_score: float
    assessment_completeness: float  # 0.0 - 1.0
    priority_areas: List[str]
    suggested_next_steps: List[str]


# =====================================================================
# Evidence and Workflow Schemas
# =====================================================================


class EvidenceItem(TypedDict):
    """Individual evidence item recommendation."""

    evidence_id: str
    title: str
    description: str
    framework_controls: List[str]
    collection_method: str
    automation_tools: List[str]
    effort_estimate: ImplementationEffort
    priority: PriorityLevel
    frequency: str  # "one-time", "quarterly", "annually", etc.
    owner_role: str
    validation_requirements: List[str]
    retention_period: str


class WorkflowStep(TypedDict):
    """Individual step in evidence collection workflow."""

    step_number: int
    title: str
    description: str
    estimated_duration: str
    assigned_role: str
    prerequisites: List[str]
    deliverables: List[str]
    validation_criteria: List[str]
    automation_opportunities: List[str]


class WorkflowPhase(TypedDict):
    """Phase in evidence collection workflow."""

    phase_number: int
    phase_name: str
    objective: str
    steps: List[WorkflowStep]
    estimated_duration: str
    success_criteria: List[str]
    dependencies: List[str]


class EvidenceWorkflow(TypedDict):
    """Complete evidence collection workflow."""

    workflow_id: str
    title: str
    description: str
    framework: str
    control_reference: str
    phases: List[WorkflowPhase]
    total_estimated_duration: str
    required_roles: List[str]
    automation_percentage: float
    complexity_level: Literal["simple", "moderate", "complex"]


# =====================================================================
# Policy Generation Schemas
# =====================================================================


class PolicySection(TypedDict):
    """Individual section of a generated policy."""

    section_number: str
    title: str
    content: str
    subsections: List[Dict[str, str]]
    compliance_references: List[str]
    implementation_notes: List[str]


class PolicyDocument(TypedDict):
    """Complete generated policy document."""

    policy_id: str
    title: str
    version: str
    effective_date: str
    framework_compliance: List[str]
    sections: List[PolicySection]
    approval_workflow: List[str]
    review_schedule: str
    related_documents: List[str]
    implementation_guidance: str


# =====================================================================
# Chat and Conversation Schemas
# =====================================================================


class IntentClassification(TypedDict):
    """User intent classification result."""

    intent_type: Literal[
        "evidence_query",
        "compliance_check",
        "guidance_request",
        "general_query",
        "assessment_help",
    ]
    confidence: float
    entities: Dict[str, List[str]]
    context_requirements: List[str]
    suggested_actions: List[str]


class ChatResponse(TypedDict):
    """General chat response structure."""

    response_text: str
    intent_classification: IntentClassification
    confidence_score: float
    follow_up_suggestions: List[str]
    related_resources: List[str]
    action_items: List[str]


# =====================================================================
# Meta Response Schemas
# =====================================================================


class ResponseMetadata(TypedDict):
    """Metadata for all AI responses."""

    response_id: str
    timestamp: str
    model_used: str
    processing_time_ms: int
    confidence_score: float
    schema_version: str
    validation_status: Literal["valid", "invalid", "partially_valid"]
    validation_errors: List[str]


class StructuredAIResponse(TypedDict):
    """Wrapper for all structured AI responses."""

    metadata: ResponseMetadata
    response_type: str
    payload: Union[
        GapAnalysisResponse,
        RecommendationResponse,
        AssessmentAnalysisResponse,
        GuidanceResponse,
        FollowUpResponse,
        ChatResponse,
        PolicyDocument,
        EvidenceWorkflow,
        Dict[str, Any],  # Fallback for custom responses,
    ]
    validation_passed: bool
    fallback_used: bool


# =====================================================================
# Error and Validation Schemas
# =====================================================================


class ValidationError(TypedDict):
    """Schema validation error details."""

    field_path: str
    error_type: str
    error_message: str
    expected_type: str
    actual_value: Any
    suggestion: Optional[str]


class SchemaValidationResult(TypedDict):
    """Result of schema validation operation."""

    is_valid: bool
    schema_name: str
    validation_errors: List[ValidationError]
    warnings: List[str]
    validation_timestamp: str
    corrected_data: Optional[Dict[str, Any]]


# =====================================================================
# Utility Type Aliases
# =====================================================================

# Union of all possible AI response types
AIResponseType = Union[
    GapAnalysisResponse,
    RecommendationResponse,
    AssessmentAnalysisResponse,
    GuidanceResponse,
    FollowUpResponse,
    ChatResponse,
    PolicyDocument,
    EvidenceWorkflow,
]

# Union of all structured response schemas
StructuredResponseSchema = Union[
    GapAnalysisResponse,
    RecommendationResponse,
    AssessmentAnalysisResponse,
    GuidanceResponse,
    FollowUpResponse,
]
