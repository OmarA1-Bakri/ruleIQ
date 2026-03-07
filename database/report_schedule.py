"""
ORM model for storing report schedule configurations.
"""

from typing import Any, Dict
import uuid
from datetime import datetime
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .db_setup import Base


class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    business_profile_id = Column(
        UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False
    )
    report_type = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    parameters = Column(JSON, nullable=True, default=lambda: {})
    recipients = Column(JSON, nullable=False, default=lambda: [])
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    owner = relationship("User", back_populates="report_schedules")
    business_profile = relationship("BusinessProfile")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "business_profile_id": str(self.business_profile_id),
            "report_type": self.report_type,
            "frequency": self.frequency,
            "parameters": self.parameters,
            "recipients": self.recipients,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
        }
