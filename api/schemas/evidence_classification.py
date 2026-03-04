"""

Pydantic schemas for evidence classification API endpoints.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceClassificationRequest(BaseModel):
    """Request schema for evidence classification."""

    evidence_id: UUID = Field(..., description="ID of the evidence to classify")
    force_reclassify: bool = Field(
        False, description="Force reclassification even if already classified",
    )


class EvidenceClassificationResponse(BaseModel):
    """Response schema for evidence classification."""

    evidence_id: UUID
    current_type: str
    ai_classification: Dict[str, Any] = Field(..., description="AI classification results")
    apply_suggestion: bool = Field(..., description="Whether to apply the AI suggestion")
    confidence: int = Field(..., ge=0, le=100, description="Classification confidence score")
    suggested_controls: List[str] = Field(
        default_factory=list, description="Suggested compliance controls",
    )
    reasoning: str = Field(..., description="AI reasoning for classification")


class BulkClassificationRequest(BaseModel):
    """Request schema for bulk evidence classification."""

    evidence_ids: List[UUID] = Field(
        ..., min_items=1, max_items=50, description="List of evidence IDs to classify",
    )
    force_reclassify: bool = Field(
        False, description="Force reclassification even if already classified",
    )
    apply_high_confidence: bool = Field(
        True, description="Automatically apply high-confidence suggestions",
    )
    confidence_threshold: int = Field(
        70, ge=50, le=100, description="Minimum confidence to auto-apply",
    )


class ClassificationResult(BaseModel):
    """Individual classification result for bulk operations."""

    evidence_id: UUID
    success: bool
    current_type: str
    suggested_type: Optional[str] = None
    confidence: Optional[int] = None
    suggested_controls: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    error: Optional[str] = None
    applied: bool = Field(False, description="Whether the suggestion was applied")


class BulkClassificationResponse(BaseModel):
    """Response schema for bulk evidence classification."""

    total_processed: int
    successful_classifications: int
    failed_classifications: int
    auto_applied: int = Field(0, description="Number of suggestions automatically applied")
    results: List[ClassificationResult]


class ControlMappingRequest(BaseModel):
    """Request schema for control mapping suggestions."""

    evidence_id: UUID
    frameworks: List[str] = Field(
        default=["ISO27001", "SOC2", "GDPR"], description="Target frameworks",
    )


class ControlMappingResponse(BaseModel):
    """Response schema for control mapping suggestions."""

    evidence_id: UUID
    evidence_type: str
    framework_mappings: Dict[str, List[str]] = Field(
        ..., description="Control mappings by framework",
    )
    confidence_scores: Dict[str, int] = Field(..., description="Confidence scores by framework")
    reasoning: str


class ClassificationStatsResponse(BaseModel):
    """Response schema for classification statistics."""

    total_evidence: int
    classified_evidence: int
    unclassified_evidence: int
    classification_accuracy: float = Field(
        ..., ge=0, le=100, description="Overall classification accuracy",
    )
    type_distribution: Dict[str, int] = Field(..., description="Distribution of evidence types")
    confidence_distribution: Dict[str, int] = Field(
        ..., description="Distribution of confidence scores",
    )
    recent_classifications: int = Field(..., description="Classifications in last 30 days")
