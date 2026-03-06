"""

Pydantic models for LangGraph compliance agent.
Defines strict schemas for compliance domain objects and safety fallbacks.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class ComplianceFramework(str, Enum):
    """Supported compliance frameworks."""

    GDPR = "GDPR"
    UK_GDPR = "UK_GDPR"
    DPA_2018 = "DPA_2018"
    PECR = "PECR"
    ISO_27001 = "ISO_27001"
    NIST_CYBERSECURITY = "NIST_Cybersecurity"
    PCI_DSS = "PCI_DSS"
    SOX = "SOX"
    FCA_HANDBOOK = "FCA_Handbook"


class BusinessSector(str, Enum):
    """Business sectors for compliance profiling."""

    RETAIL = "retail"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    TECHNOLOGY = "technology"
    MANUFACTURING = "manufacturing"
    EDUCATION = "education"
    HOSPITALITY = "hospitality"
    PROFESSIONAL_SERVICES = "professional_services"
    CONSTRUCTION = "construction"
    TRANSPORT = "transport"


class RiskLevel(str, Enum):
    """Risk assessment levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceType(str, Enum):
    """Types of compliance evidence."""

    POLICY_DOCUMENT = "policy_document"
    TRAINING_RECORD = "training_record"
    AUDIT_LOG = "audit_log"
    CERTIFICATE = "certificate"
    ASSESSMENT_REPORT = "assessment_report"
    PROCEDURE_DOCUMENT = "procedure_document"
    INCIDENT_REPORT = "incident_report"
    CONTRACT = "contract"


class ComplianceProfile(BaseModel):
    """Business compliance profile and requirements."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    company_id: UUID
    business_name: str = Field(..., min_length=1, max_length=200)
    sector: BusinessSector
    frameworks: List[ComplianceFramework] = Field(min_length=1)
    data_processing_activities: List[str] = Field(default_factory=list)
    geographical_scope: List[str] = Field(default_factory=list)
    employee_count: Optional[int] = Field(None, ge=1)
    annual_revenue: Optional[float] = Field(None, ge=0)
    risk_tolerance: RiskLevel = RiskLevel.MEDIUM
    has_dpo: bool = False
    has_privacy_policy: bool = False
    has_security_policy: bool = False
    has_incident_response: bool = False
    last_assessment_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("frameworks")
    @classmethod
    def validate_frameworks(cls, v) -> Any:
        if not v:
            raise ValueError("At least one compliance framework is required")
        return v

    @model_validator(mode="after")
    def validate_profile(self) -> Any:
        if (
            ComplianceFramework.GDPR in self.frameworks
            or ComplianceFramework.UK_GDPR in self.frameworks
        ):
            if not self.geographical_scope:
                raise ValueError("Geographical scope required for GDPR compliance")
        return self


class Obligation(BaseModel):
    """Individual compliance obligation or requirement."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    obligation_id: str = Field(..., min_length=1)
    framework: ComplianceFramework
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    mandatory: bool = True
    risk_level: RiskLevel = RiskLevel.MEDIUM
    implementation_guidance: Optional[str] = None
    applicable_sectors: List[BusinessSector] = Field(default_factory=list)
    company_size_threshold: Optional[int] = None
    revenue_threshold: Optional[float] = None
    legal_reference: Optional[str] = None
    article_reference: Optional[str] = None
    citation_url: Optional[str] = None
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    @field_validator("obligation_id")
    @classmethod
    def validate_obligation_id(cls, v) -> Any:
        parts = v.split("_")
        if len(parts) < 3:
            raise ValueError("Obligation ID must follow format: FRAMEWORK_CATEGORY_NUMBER")
        return v


class EvidenceItem(BaseModel):
    """Compliance evidence or documentation."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    evidence_id: UUID = Field(default_factory=uuid4)
    company_id: UUID
    title: str = Field(..., min_length=1, max_length=200)
    evidence_type: EvidenceType
    description: Optional[str] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = Field(None, ge=0)
    content_hash: Optional[str] = None
    created_by: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    related_obligations: List[str] = Field(default_factory=list)
    frameworks: List[ComplianceFramework] = Field(default_factory=list)
    verified: bool = False
    verification_date: Optional[datetime] = None
    verification_notes: Optional[str] = None

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v) -> Any:
        if v and (not v.startswith(("http://", "https://", "/"))):
            raise ValueError("File path must be absolute or URL")
        return v


class LegalReviewTicket(BaseModel):
    """Legal review request and tracking."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    ticket_id: UUID = Field(default_factory=uuid4)
    company_id: UUID
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    requested_by: UUID
    priority: RiskLevel = RiskLevel.MEDIUM
    due_date: Optional[datetime] = None
    content_type: str = Field(..., min_length=1)
    content_id: Optional[str] = None
    content_summary: Optional[str] = None
    assigned_to: Optional[UUID] = None
    status: str = Field(default="pending")
    review_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v) -> Any:
        allowed_statuses = ["pending", "in_review", "approved", "rejected", "cancelled"]
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of: {allowed_statuses}")
        return v


class SafeFallbackResponse(BaseModel):
    """Standardized fallback response for validation failures and errors."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    status: str = Field(default="needs_review", pattern="^needs_review$")
    error_message: str = Field(..., min_length=1, max_length=500)
    error_details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    company_id: Optional[UUID] = None
    thread_id: Optional[str] = None
    node_name: Optional[str] = None
    suggested_action: Optional[str] = None
    retry_after_seconds: Optional[int] = Field(None, ge=0)

    @field_validator("error_details")
    @classmethod
    def validate_error_details(cls, v) -> Any:
        sensitive_keys = ["password", "token", "secret", "key", "credential"]
        for key in v:
            if any((sens in key.lower() for sens in sensitive_keys)):
                raise ValueError(f"Error details cannot contain sensitive key: {key}")
        return v


class GraphMessage(BaseModel):
    """Message format for LangGraph state."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class RouteDecision(BaseModel):
    """Router decision with confidence and reasoning."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    route: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., min_length=1)
    method: str = Field(..., pattern="^(rules|classifier|llm)$")
    input_text: str = Field(..., min_length=1)
    company_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ComplianceAnalysisRequest(BaseModel):
    """Request for compliance analysis."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    company_id: UUID
    business_profile: Dict[str, Any] = Field(..., min_length=1)
    frameworks: List[str] = Field(default_factory=list)
    analysis_type: str = Field(default="basic", pattern="^(basic|full|detailed)$")
    priority: RiskLevel = RiskLevel.MEDIUM
    include_recommendations: bool = True
    include_evidence_mapping: bool = False


class ComplianceAnalysisResponse(BaseModel):
    """Response from compliance analysis."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    company_id: UUID
    applicable_frameworks: List[str] = Field(default_factory=list)
    compliance_score: float = Field(..., ge=0.0, le=1.0)
    priority_obligations: List[str] = Field(default_factory=list)
    risk_areas: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    detailed_analysis: Dict[str, Any] = Field(default_factory=dict)
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    analysis_version: str = Field(default="1.0")


def get_model_schemas() -> Dict[str, Dict[str, Any]]:
    """Export JSON schemas for all models."""
    return {
        "ComplianceProfile": ComplianceProfile.model_json_schema(),
        "Obligation": Obligation.model_json_schema(),
        "EvidenceItem": EvidenceItem.model_json_schema(),
        "LegalReviewTicket": LegalReviewTicket.model_json_schema(),
        "SafeFallbackResponse": SafeFallbackResponse.model_json_schema(),
        "GraphMessage": GraphMessage.model_json_schema(),
        "RouteDecision": RouteDecision.model_json_schema(),
    }


def get_compliance_profile_schema() -> Dict[str, Any]:
    """Get JSON schema for ComplianceProfile."""
    return ComplianceProfile.model_json_schema()


def get_obligation_schema() -> Dict[str, Any]:
    """Get JSON schema for Obligation."""
    return Obligation.model_json_schema()


def get_evidence_schema() -> Dict[str, Any]:
    """Get JSON schema for EvidenceItem."""
    return EvidenceItem.model_json_schema()


def get_legal_review_schema() -> Dict[str, Any]:
    """Get JSON schema for LegalReviewTicket."""
    return LegalReviewTicket.model_json_schema()


def get_safe_fallback_schema() -> Dict[str, Any]:
    """Get JSON schema for SafeFallbackResponse."""
    return SafeFallbackResponse.model_json_schema()
