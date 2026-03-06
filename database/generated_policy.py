from typing import Any
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from .db_setup import Base


class GeneratedPolicy(Base):
    """AI-generated compliance policies and procedures"""

    __tablename__ = "generated_policies"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    business_profil = Column(
        PG_UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False
    )
    framework_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("compliance_frameworks.id"), nullable=False
    )
    policy_name = Column(String, nullable=False)
    framework_name = Column(String, nullable=False)
    policy_type = Column(String, default="comprehensive")
    generation_prompt = Column(Text, nullable=False)
    generation_model = Column(String, default="openai/gpt-4o-mini")
    generation_time_seconds = Column(Float, nullable=False)
    policy_content = Column(Text, nullable=False)
    procedures = Column(PG_JSONB, default=list)
    tool_recommendations = Column(PG_JSONB, default=list)
    sections = Column(PG_JSONB, default=list)
    controls = Column(PG_JSONB, default=list)
    responsibilities = Column(PG_JSONB, default=dict)
    word_count = Column(Integer, default=0)
    estimated_reading_time = Column(Integer, default=0)
    compliance_coverage = Column(Float, default=0.0)
    status = Column(String, default="draft")
    review_notes = Column(Text, default="")
    generated_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def content(self) -> Any:
        """Alias for policy_content for backward compatibility"""
        return self.policy_content
