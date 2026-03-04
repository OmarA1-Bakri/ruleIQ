"""

Pydantic schemas for chat API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    """Request schema for sending a chat message."""

    message: str = Field(..., min_length=1, max_length=2000, description="The user's message")


class MessageResponse(BaseModel):
    """Response schema for a chat message."""

    id: UUID
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    metadata: Optional[Dict[str, Any]] = Field(None, alias="message_metadata")
    sequence_number: int
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class ConversationSummary(BaseModel):
    """Summary schema for a conversation."""

    id: UUID
    title: str
    status: str
    message_count: int
    last_message_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Response schema for a conversation with messages."""

    id: UUID
    title: str
    status: str
    messages: List[MessageResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateConversationRequest(BaseModel):
    """Request schema for creating a new conversation."""

    title: Optional[str] = Field(None, max_length=255, description="Optional conversation title")
    initial_message: Optional[str] = Field(
        None, max_length=2000, description="Optional initial message",
    )


class ConversationListResponse(BaseModel):
    """Response schema for listing conversations."""

    conversations: List[ConversationSummary]
    total: int
    page: int
    per_page: int


class EvidenceRecommendationRequest(BaseModel):
    """Request schema for getting evidence recommendations."""

    framework: Optional[str] = Field(
        None, description="Specific framework to get recommendations for",
    )


class EvidenceRecommendationResponse(BaseModel):
    """Response schema for evidence recommendations."""

    framework: str
    recommendations: str
    generated_at: datetime


class ComplianceAnalysisRequest(BaseModel):
    """Request schema for compliance gap analysis."""

    framework: str = Field(..., min_length=1, description="Framework to analyze")


class ComplianceAnalysisResponse(BaseModel):
    """Response schema for compliance analysis."""

    framework: str
    completion_percentage: float
    evidence_collected: int
    evidence_types: List[str]
    recent_activity: int
    recommendations: List[Dict[str, Any]]
    critical_gaps: List[str]
    risk_level: str


# Enhanced Recommendation Schemas
class ContextAwareRecommendationRequest(BaseModel):
    """Request schema for context-aware recommendations."""

    framework: str = Field(..., description="Framework to get recommendations for")
    context_type: str = Field(default="comprehensive", description="Type of context analysis")


class BusinessContextSummary(BaseModel):
    """Business context summary for recommendations."""

    company_name: str
    industry: str
    employee_count: int
    maturity_level: str


class CurrentStatusSummary(BaseModel):
    """Current compliance status summary."""

    completion_percentage: float
    evidence_collected: int
    critical_gaps_count: int


class RecommendationItem(BaseModel):
    """Individual recommendation item."""

    control_id: str
    title: str
    description: str
    priority: str
    effort_hours: int
    automation_possible: bool
    business_justification: str
    implementation_steps: List[str]
    priority_score: Optional[float] = None
    automation_guidance: Optional[str] = None


class EffortEstimation(BaseModel):
    """Effort estimation for recommendations."""

    total_hours: int
    high_priority_hours: int
    estimated_weeks: float
    quick_wins: int


class ContextAwareRecommendationResponse(BaseModel):
    """Response schema for context-aware recommendations."""

    framework: str
    business_context: BusinessContextSummary
    current_status: CurrentStatusSummary
    recommendations: List[RecommendationItem]
    next_steps: List[str]
    estimated_effort: EffortEstimation
    generated_at: str


# Workflow Schemas
class WorkflowGenerationRequest(BaseModel):
    """Request schema for workflow generation."""

    framework: str = Field(..., description="Framework for workflow generation")
    control_id: Optional[str] = Field(None, description="Specific control ID (optional)")
    workflow_type: str = Field(default="comprehensive", description="Type of workflow")


class WorkflowStep(BaseModel):
    """Individual workflow step."""

    step_id: str
    title: str
    description: str
    deliverables: List[str]
    responsible_role: str
    estimated_hours: int
    dependencies: List[str]
    tools_needed: List[str]
    validation_criteria: List[str]
    automation_opportunities: Optional[Dict[str, Any]] = None
    estimated_hours_with_automation: Optional[int] = None


class WorkflowPhase(BaseModel):
    """Workflow phase containing multiple steps."""

    phase_id: str
    title: str
    description: str
    estimated_hours: int
    steps: List[WorkflowStep]


class AutomationSummary(BaseModel):
    """Automation potential summary for workflow."""

    automation_percentage: float
    effort_savings_percentage: float
    manual_hours: int
    automated_hours: int
    hours_saved: int
    high_automation_steps: int
    total_steps: int


class WorkflowEffortEstimation(BaseModel):
    """Comprehensive effort estimation for workflow."""

    total_manual_hours: int
    total_automated_hours: int
    estimated_weeks_manual: float
    estimated_weeks_automated: float
    phases_count: int
    steps_count: int
    effort_savings: Dict[str, Any]


class WorkflowResponse(BaseModel):
    """Response schema for workflow generation."""

    workflow_id: str
    title: str
    description: str
    framework: str
    control_id: str
    created_at: str
    phases: List[WorkflowPhase]
    automation_summary: AutomationSummary
    effort_estimation: WorkflowEffortEstimation


# Policy Generation Schemas
class PolicyGenerationRequest(BaseModel):
    """Request schema for policy generation."""

    framework: str = Field(..., description="Framework for policy generation")
    policy_type: str = Field(..., description="Type of policy to generate")
    tone: str = Field(default="Professional", description="Policy tone")
    detail_level: str = Field(default="Standard", description="Level of detail")
    include_templates: bool = Field(default=True, description="Include implementation templates")
    geographic_scope: str = Field(default="Single location", description="Geographic scope")


class PolicySubsection(BaseModel):
    """Policy subsection."""

    subsection_id: str
    title: str
    content: str
    controls: List[str]


class PolicySection(BaseModel):
    """Policy section containing subsections."""

    section_id: str
    title: str
    content: str
    subsections: List[PolicySubsection]


class RoleResponsibility(BaseModel):
    """Role and responsibilities definition."""

    role: str
    responsibilities: List[str]


class PolicyProcedure(BaseModel):
    """Policy procedure definition."""

    procedure_id: str
    title: str
    steps: List[str]


class ComplianceRequirement(BaseModel):
    """Compliance requirement mapping."""

    requirement_id: str
    description: str
    control_reference: str


class BusinessContextInfo(BaseModel):
    """Business context information for policy."""

    company_name: str
    industry: str
    employee_count: int
    customization_applied: str


class ImplementationPhase(BaseModel):
    """Policy implementation phase."""

    phase: str
    duration_weeks: int
    activities: List[str]


class PolicyImplementationGuidance(BaseModel):
    """Implementation guidance for policy."""

    implementation_phases: List[ImplementationPhase]
    success_metrics: List[str]
    common_challenges: List[str]
    mitigation_strategies: List[str]


class ComplianceMapping(BaseModel):
    """Compliance mapping for policy."""

    framework: str
    policy_type: str
    mapped_controls: List[str]
    compliance_objectives: List[str]
    audit_considerations: List[str]


class PolicyResponse(BaseModel):
    """Response schema for policy generation."""

    policy_id: str
    title: str
    version: str
    effective_date: str
    framework: str
    policy_type: str
    created_at: str
    sections: List[PolicySection]
    roles_responsibilities: List[RoleResponsibility]
    procedures: List[PolicyProcedure]
    compliance_requirements: List[ComplianceRequirement]
    business_context: BusinessContextInfo
    implementation_guidance: PolicyImplementationGuidance
    compliance_mapping: ComplianceMapping
    implementation_notes: Optional[List[str]] = None


# Smart Guidance Schemas
class SmartGuidanceRequest(BaseModel):
    """Request schema for smart guidance."""

    framework: str = Field(..., description="Framework for guidance")
    guidance_type: str = Field(default="getting_started", description="Type of guidance needed")


class GuidanceCurrentStatus(BaseModel):
    """Current status for guidance."""

    completion_percentage: float
    maturity_level: str
    critical_gaps_count: int


class SmartGuidanceResponse(BaseModel):
    """Response schema for smart compliance guidance."""

    framework: str
    guidance_type: str
    current_status: GuidanceCurrentStatus
    personalized_roadmap: List[RecommendationItem]
    next_immediate_steps: List[str]
    effort_estimation: EffortEstimation
    quick_wins: List[RecommendationItem]
    automation_opportunities: List[RecommendationItem]
    generated_at: str
