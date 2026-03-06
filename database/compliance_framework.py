from typing import Any, Dict
import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from .db_setup import Base


class ComplianceFramework(Base):
    """Compliance frameworks and their requirements"""

    __tablename__ = "compliance_frameworks"
    __table_args__ = (
        CheckConstraint(
            "version ~ '^[0-9]+\\.[0-9]+(\\.[0-9]+)?$'",
            name="ck_compliance_frameworks_version_format",
        ),
    )
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    applicable_indu = Column(PG_JSONB, default=list)
    employee_thresh = Column(Integer, nullable=True)
    revenue_thresho = Column(String, nullable=True)
    geographic_scop = Column(PG_JSONB, default=lambda: ["UK"])
    key_requirement = Column(PG_JSONB, default=list)
    control_domains = Column(PG_JSONB, default=list)
    evidence_types = Column(PG_JSONB, default=list)
    relevance_facto = Column(PG_JSONB, default=dict)
    complexity_scor = Column(Integer, default=1)
    implementation_ = Column(Integer, default=12)
    estimated_cost_ = Column(String, default="£5,000-£25,000")
    policy_template = Column(Text, default="")
    control_templat = Column(PG_JSONB, default=dict)
    evidence_templa = Column(PG_JSONB, default=dict)
    is_active = Column(Boolean, default=True)
    version = Column(String, default="1.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    evidence_items = relationship("EvidenceItem", back_populates="framework")

    def to_dict(self) -> Dict[str, Any]:
        """Convert framework to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "controls": [],
        }
