"""

Evidence Collection Plan Schemas

Pydantic models for evidence collection planning API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CollectionPlanCreate(BaseModel):
    """Request model for creating a collection plan."""

    framework: str = Field(..., description="Compliance framework (ISO27001, GDPR, SOC2, etc.)")
    target_completion_weeks: Optional[int] = Field(
        12, ge=1, le=52, description="Target completion timeframe in weeks",
    )
    include_existing_evidence: Optional[bool] = Field(
        False, description="Include analysis of existing evidence",
    )


class AutomationOpportunities(BaseModel):
    """Automation opportunities analysis."""

    total_tasks: int
    automatable_tasks: int
    automation_percentage: float
    effort_savings_hours: float
    effort_savings_percentage: float
    recommended_tools: List[str]


class EvidenceTaskResponse(BaseModel):
    """Response model for an evidence collection task."""

    task_id: str
    framework: str
    control_id: str
    evidence_type: str
    title: str
    description: str
    priority: str
    automation_level: str
    estimated_effort_hours: float
    dependencies: List[str] = []
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str
    created_at: datetime
    metadata: Dict[str, Any] = {}


class CollectionPlanResponse(BaseModel):
    """Response model for a collection plan."""

    plan_id: str
    business_profile_id: str
    framework: str
    total_tasks: int
    estimated_total_hours: float
    completion_target_date: datetime
    tasks: List[EvidenceTaskResponse]
    automation_opportunities: AutomationOpportunities
    created_at: datetime


class CollectionPlanSummary(BaseModel):
    """Summary model for collection plan listing."""

    plan_id: str
    framework: str
    total_tasks: int
    completed_tasks: int
    estimated_total_hours: float
    completion_target_date: datetime
    status: str
    created_at: datetime


class TaskStatusUpdate(BaseModel):
    """Request model for updating task status."""

    status: str = Field(
        ...,
        description="New status: pending, in_progress, completed, blocked, cancelled",
    )
    completion_notes: Optional[str] = Field(None, description="Notes about task completion")


class AutomationRecommendation(BaseModel):
    """Automation recommendation for evidence collection."""

    evidence_type: str
    automation_level: str
    effort_reduction: str
    success_rate: str
    recommended_tools: List[str]


class AutomationRecommendationsResponse(BaseModel):
    """Response model for automation recommendations."""

    framework: str
    automation_opportunities: List[AutomationRecommendation]
    recommended_tools: List[str]
    estimated_time_savings: float
