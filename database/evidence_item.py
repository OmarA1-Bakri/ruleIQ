from typing import Any, Dict
import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship
from .db_setup import Base


class EvidenceItem(Base):
    """Evidence collection tracking for compliance audits"""

    __tablename__ = "evidence_items"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    business_profile_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False
    )
    framework_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("compliance_frameworks.id"), nullable=False
    )
    evidence_name = Column(String, nullable=False)
    evidence_type = Column(String, nullable=False)
    control_reference = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    required_for_audit = Column(Boolean, default=True)
    collection_frequency = Column(String, default="once")
    collection_method = Column(String, default="manual")
    automation_source = Column(String, nullable=True)
    automation_guidance = Column(Text, default="")
    file_path = Column(String, nullable=True)
    file_type = Column(String, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    status = Column(String, default="not_started")
    collection_notes = Column(Text, default="")
    review_notes = Column(Text, default="")
    collected_by = Column(String, nullable=True)
    collected_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    priority = Column(String, default="medium")
    effort_estimate = Column(String, default="2-4 hours")
    audit_section = Column(String, default="")
    compliance_score_impact = Column(Float, default=0.0)
    ai_metadata = Column(PG_JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="evidence_items")
    business_profile = relationship("BusinessProfile", back_populates="evidence_items")
    framework = relationship("ComplianceFramework", back_populates="evidence_items")

    def to_dict(self) -> Dict[str, Any]:
        """Convert EvidenceItem to dictionary for serialization."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "business_profile_id": str(self.business_profile_id),
            "framework_id": str(self.framework_id),
            "evidence_name": self.evidence_name,
            "evidence_type": self.evidence_type,
            "control_reference": self.control_reference,
            "description": self.description,
            "required_for_audit": self.required_for_audit,
            "collection_frequency": self.collection_frequency,
            "collection_method": self.collection_method,
            "automation_source": self.automation_source,
            "automation_guidance": self.automation_guidance,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
            "status": self.status,
            "collection_notes": self.collection_notes,
            "review_notes": self.review_notes,
            "collected_by": self.collected_by,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "priority": self.priority,
            "effort_estimate": self.effort_estimate,
            "audit_section": self.audit_section,
            "compliance_score_impact": self.compliance_score_impact,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def title(self) -> Any:
        """Property to map 'title' field from API to 'evidence_name' in database."""
        return self.evidence_name

    @title.setter
    def title(self, value) -> None:
        """Setter to map 'title' field from API to 'evidence_name' in database."""
        self.evidence_name = value
