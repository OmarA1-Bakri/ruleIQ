import uuid

# typing.Optional, List, and Dict were removed as they are not directly used in column definitions after refactor
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import (
    UUID as PG_UUID,
)  # Using JSONB for Dict/List[Dict]

from .db_setup import Base


class ReadinessAssessment(Base):
    """Compliance readiness assessments and scoring"""

    __tablename__ = "readiness_assessments"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Assuming user_id, business_profile_id, framework_id are foreign keys.
    # Replace 'users.id' etc. with actual table.column names if different.
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    business_profile_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("business_profiles.id"),
        nullable=False,
    )
    framework_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("compliance_frameworks.id"),
        nullable=False,
    )

    # Assessment metadata
    assessment_name = Column(String, nullable=False)
    framework_name = Column(
        String, nullable=False
    )  # Consider if this should be derived from framework_id
    assessment_type = Column(String, default="full")  # full, quick, targeted

    # Overall scoring
    overall_score = Column(Float, default=0.0)  # 0-100%
    policy_score = Column(Float, default=0.0)
    implementation_score = Column(Float, default=0.0)
    evidence_score = Column(Float, default=0.0)

    # Domain-specific scores
    domain_scores = Column(PG_JSONB, default=dict)  # Domain -> score mapping
    control_scores = Column(PG_JSONB, default=dict)  # Control -> score mapping

    # Gap analysis
    identified_gaps = Column(PG_JSONB, default=list)  # Gaps with details and priority
    remediation_plan = Column(PG_JSONB, default=list)  # Prioritized remediation actions
    quick_wins = Column(PG_JSONB, default=list)  # Easy improvements (stored as list of strings)

    # Timeline projections
    estimated_readiness_date = Column(DateTime, nullable=True)
    certification_timeline_weeks = Column(Integer, default=0)
    remaining_effort_hours = Column(Integer, default=0)

    # Recommendations
    priority_actions = Column(PG_JSONB, default=list)
    tool_recommendations = Column(PG_JSONB, default=list)
    training_recommendations = Column(PG_JSONB, default=list)

    # Assessment criteria
    assessment_criteria = Column(PG_JSONB, default=dict)
    weighting_factors = Column(PG_JSONB, default=dict)
    scoring_methodology = Column(String, default="weighted_average")

    # Progress tracking
    previous_score = Column(Float, nullable=True)
    score_trend = Column(String, default="stable")  # improving, declining, stable
    last_assessment_date = Column(DateTime, nullable=True)

    # Status
    status = Column(String, default="completed")  # in_progress, completed, expired
    assessment_notes = Column(String, default="")

    # Executive summary
    executive_summary = Column(String, default="")
    key_findings = Column(PG_JSONB, default=list)
    next_steps = Column(PG_JSONB, default=list)

    created_at = Column(
        DateTime, default=datetime.utcnow
    )  # Use datetime.utcnow for server-side UTC time
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
