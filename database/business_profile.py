import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from .db_setup import Base


class BusinessProfile(Base):
    """Business profile information for compliance assessment"""

    __tablename__ = "business_profiles"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True
    )  # Assuming one profile per user

    # Basic company information
    company_name = Column(String, nullable=False)
    industry = Column(String, nullable=False)
    employee_count = Column(Integer, nullable=False)
    annual_revenue = Column(
        String, nullable=True
    )  # Consider Numeric/Decimal or specific range type
    country = Column(String, default="UK")
    data_sensitivity = Column(
        String, default="Low", nullable=False
    )  # Re-added for framework relevance calculation

    # Business characteristics (full column names after migration)
    handles_personal_data = Column(Boolean, nullable=False)
    processes_payments = Column(Boolean, nullable=False)
    stores_health_data = Column(Boolean, nullable=False)
    provides_financial_services = Column(Boolean, nullable=False)
    operates_critical_infrastructure = Column(Boolean, nullable=False)
    has_international_operations = Column(Boolean, nullable=False)

    # Technology stack (full column names after migration)
    cloud_providers = Column(PG_JSONB, default=list)  # AWS, Azure, GCP, etc.
    saas_tools = Column(PG_JSONB, default=list)  # Office 365, Salesforce, etc.
    development_tools = Column(PG_JSONB, default=list)  # GitHub, GitLab, etc.

    # Current compliance state (full column names after migration)
    existing_frameworks = Column(PG_JSONB, default=list)  # Currently compliant with
    planned_frameworks = Column(PG_JSONB, default=list)  # Planning to achieve
    compliance_budget = Column(String, nullable=True)  # Consider Numeric/Decimal
    compliance_timeline = Column(String, nullable=True)

    # Assessment status (full column names after migration)
    assessment_completed = Column(Boolean, default=False)
    assessment_data = Column(PG_JSONB, default=dict)  # Store questionnaire responses

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="business_profiles")
    evidence_items = relationship("EvidenceItem", back_populates="business_profile")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "name": self.company_name,
            "company_name": self.company_name,
            "industry": self.industry,
            "employee_count": self.employee_count,
            "annual_revenue": self.annual_revenue,
            "country": self.country,
            "data_sensitivity": self.data_sensitivity,
            "handles_personal_data": self.handles_personal_data,
            "processes_payments": self.processes_payments,
            "stores_health_data": self.stores_health_data,
            "provides_financial_services": self.provides_financial_services,
            "operates_critical_infrastructure": self.operates_critical_infrastructure,
            "has_international_operations": self.has_international_operations,
            "existing_frameworks": self.existing_frameworks or [],
            "planned_frameworks": self.planned_frameworks or [],
            "cloud_providers": self.cloud_providers or [],
            "saas_tools": self.saas_tools or [],
            "development_tools": self.development_tools or [],
            "compliance_budget": self.compliance_budget,
            "compliance_timeline": self.compliance_timeline,
            "assessment_completed": self.assessment_completed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
