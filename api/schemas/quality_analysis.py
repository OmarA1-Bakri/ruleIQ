"""

Pydantic schemas for quality analysis and duplicate detection API endpoints.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class QualityScoreBreakdown(BaseModel):
    """Quality score breakdown by dimension."""

    completeness: float = Field(..., ge=0, le=100, description="Completeness score")
    clarity: float = Field(..., ge=0, le=100, description="Clarity score")
    currency: float = Field(..., ge=0, le=100, description="Currency/freshness score")
    verifiability: float = Field(..., ge=0, le=100, description="Verifiability score")
    relevance: float = Field(..., ge=0, le=100, description="Relevance score")
    sufficiency: float = Field(..., ge=0, le=100, description="Sufficiency score")


class TraditionalScoreBreakdown(BaseModel):
    """Traditional algorithmic score breakdown."""

    completeness: float = Field(..., ge=0, le=100)
    freshness: float = Field(..., ge=0, le=100)
    content_quality: float = Field(..., ge=0, le=100)
    relevance: float = Field(..., ge=0, le=100)


class AIAnalysisResult(BaseModel):
    """AI-powered quality analysis result."""

    scores: QualityScoreBreakdown
    overall_score: float = Field(..., ge=0, le=100, description="Overall AI quality score")
    strengths: List[str] = Field(default_factory=list, description="Identified strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Identified weaknesses")
    recommendations: List[str] = Field(
        default_factory=list,
        description="Improvement recommendations",
    )
    ai_confidence: int = Field(..., ge=0, le=100, description="AI analysis confidence")


class QualityAnalysisResponse(BaseModel):
    """Response schema for evidence quality analysis."""

    evidence_id: UUID
    evidence_name: str
    overall_score: float = Field(..., ge=0, le=100, description="Final combined quality score")
    traditional_scores: TraditionalScoreBreakdown
    ai_analysis: AIAnalysisResult
    scoring_method: str = Field(..., description="Method used for scoring")
    confidence: int = Field(..., ge=0, le=100, description="Overall analysis confidence")
    analysis_timestamp: str = Field(..., description="ISO timestamp of analysis")


class DuplicateCandidate(BaseModel):
    """Potential duplicate evidence candidate."""

    candidate_id: UUID
    candidate_name: str
    similarity_score: float = Field(..., ge=0, le=100, description="Semantic similarity score")
    similarity_type: str = Field(..., description="Type of similarity detected")
    reasoning: str = Field(..., description="AI reasoning for similarity")
    recommendation: str = Field(..., description="Recommended action")


class DuplicateDetectionRequest(BaseModel):
    """Request schema for duplicate detection."""

    evidence_id: UUID = Field(..., description="ID of evidence to check for duplicates")
    similarity_threshold: float = Field(
        80.0,
        ge=50,
        le=100,
        description="Minimum similarity threshold",
    )
    max_candidates: int = Field(
        20,
        ge=1,
        le=100,
        description="Maximum number of candidates to check",
    )


class DuplicateDetectionResponse(BaseModel):
    """Response schema for duplicate detection."""

    evidence_id: UUID
    evidence_name: str
    duplicates_found: int = Field(..., description="Number of potential duplicates found")
    duplicates: List[DuplicateCandidate]
    analysis_timestamp: str = Field(..., description="ISO timestamp of analysis")


class DuplicateGroup(BaseModel):
    """Group of duplicate evidence items."""

    primary_evidence: Dict[str, Any] = Field(..., description="Primary evidence item info")
    duplicates: List[DuplicateCandidate]
    group_size: int = Field(..., description="Total items in duplicate group")
    highest_similarity: float = Field(
        ...,
        ge=0,
        le=100,
        description="Highest similarity score in group",
    )


class BatchDuplicateDetectionRequest(BaseModel):
    """Request schema for batch duplicate detection."""

    evidence_ids: List[UUID] = Field(
        ...,
        min_items=2,
        max_items=100,
        description="Evidence IDs to analyze",
    )
    similarity_threshold: float = Field(
        80.0,
        ge=50,
        le=100,
        description="Minimum similarity threshold",
    )


class BatchDuplicateDetectionResponse(BaseModel):
    """Response schema for batch duplicate detection."""

    total_items: int = Field(..., description="Total evidence items analyzed")
    duplicate_groups: List[DuplicateGroup]
    potential_duplicates: int = Field(..., description="Total potential duplicate items found")
    unique_items: int = Field(..., description="Number of unique items")
    analysis_summary: str = Field(..., description="Summary of duplicate analysis")
    analysis_timestamp: str = Field(..., description="ISO timestamp of analysis")


class QualityBenchmarkRequest(BaseModel):
    """Request schema for quality benchmarking."""

    framework: Optional[str] = Field(None, description="Compliance framework to benchmark against")
    evidence_type: Optional[str] = Field(None, description="Specific evidence type to benchmark")


class QualityBenchmarkResponse(BaseModel):
    """Response schema for quality benchmarking."""

    user_average_score: float = Field(..., ge=0, le=100, description="User's average quality score")
    benchmark_score: float = Field(..., ge=0, le=100, description="Benchmark average score")
    percentile_rank: float = Field(..., ge=0, le=100, description="User's percentile rank")
    score_distribution: Dict[str, int] = Field(..., description="Distribution of scores")
    improvement_areas: List[str] = Field(default_factory=list, description="Areas for improvement")
    top_performers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top performing evidence examples",
    )


class QualityTrendRequest(BaseModel):
    """Request schema for quality trend analysis."""

    days: int = Field(30, ge=7, le=365, description="Number of days to analyze")
    evidence_type: Optional[str] = Field(None, description="Filter by evidence type")


class QualityTrendResponse(BaseModel):
    """Response schema for quality trend analysis."""

    period_days: int = Field(..., description="Analysis period in days")
    trend_direction: str = Field(..., description="Overall trend direction")
    average_score_change: float = Field(..., description="Change in average score")
    daily_scores: List[Dict[str, Any]] = Field(..., description="Daily quality score data")
    insights: List[str] = Field(
        default_factory=list,
        description="Key insights from trend analysis",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations based on trends",
    )
