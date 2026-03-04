"""

AI Policy Generation schemas for API validation.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime, timezone

class PolicyType(str, Enum):
    """Types of policies that can be generated"""
    PRIVACY_POLICY = 'privacy_policy'
    INFORMATION_SECURITY_POLICY = 'information_security_policy'
    DATA_RETENTION_POLICY = 'data_retention_policy'
    INCIDENT_RESPONSE_POLICY = 'incident_response_policy'
    ACCESS_CONTROL_POLICY = 'access_control_policy'
    BUSINESS_CONTINUITY_POLICY = 'business_continuity_policy'

class CustomizationLevel(str, Enum):
    """Levels of policy customization"""
    BASIC = 'basic'
    STANDARD = 'standard'
    DETAILED = 'detailed'
    COMPREHENSIVE = 'comprehensive'

class TargetAudience(str, Enum):
    """Target audience for the policy"""
    GENERAL_PUBLIC = 'general_public'
    EMPLOYEES = 'employees'
    CUSTOMERS = 'customers'
    REGULATORS = 'regulators'
    TECHNICAL_STAFF = 'technical_staff'

class BusinessContext(BaseModel):
    """Business context for policy customization"""
    organization_name: str = Field(..., min_length=1, max_length=200)
    industry: str = Field(..., min_length=1, max_length=100)
    employee_count: Optional[int] = Field(None, ge=1, le=1000000)
    annual_revenue: Optional[str] = None
    geographic_operations: List[str] = Field(default_factory=list)
    processes_personal_data: bool = Field(default=True)
    data_types: List[str] = Field(default_factory=list)
    data_retention_period: Optional[str] = None
    third_party_processors: bool = Field(default=False)
    cross_border_transfers: bool = Field(default=False)
    cloud_services: List[str] = Field(default_factory=list)
    security_certifications: List[str] = Field(default_factory=list)
    existing_policies: List[str] = Field(default_factory=list)

class PolicyGenerationRequest(BaseModel):
    """Request schema for policy generation"""
    framework_id: str = Field(..., description='ID of the compliance framework')
    business_context: BusinessContext
    policy_type: PolicyType
    customization_level: CustomizationLevel = Field(default=CustomizationLevel.STANDARD)
    target_audience: TargetAudience = Field(default=TargetAudience.GENERAL_PUBLIC)
    include_templates: bool = Field(default=True)
    language: str = Field(default='en-GB', description='Policy language (ISO 639-1)')

    @validator('language')
    def validate_language(cls, v) -> Any:
        supported_languages = ['en-GB', 'en-US']
        if v not in supported_languages:
            raise ValueError(f'Language {v} not supported. Supported: {supported_languages}')
        return v

class PolicyRefinementRequest(BaseModel):
    """Request schema for policy refinement"""
    original_policy: str = Field(..., min_length=50)
    feedback: List[str] = Field(..., min_items=1, max_items=10)
    framework_id: str
    refinement_type: str = Field(default='general', pattern='^(general|legal|technical|formatting)$')

class PolicyValidationResult(BaseModel):
    """Result of policy validation"""
    is_valid: bool
    compliance_score: float = Field(ge=0.0, le=1.0)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    missing_sections: List[str] = Field(default_factory=list)

class PolicyGenerationResponse(BaseModel):
    """Response schema for policy generation"""
    success: bool
    policy_content: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    provider_used: str
    generated_sections: List[str]
    compliance_checklist: List[str]
    error_message: Optional[str] = None
    fallback_content: Optional[str] = None
    was_cached: bool = Field(default=False)
    generation_time_ms: Optional[int] = None
    validation_result: Optional[PolicyValidationResult] = None
    estimated_cost: Optional[float] = None
    tokens_used: Optional[int] = None

class PolicyRefinementResponse(BaseModel):
    """Response schema for policy refinement"""
    success: bool
    refined_content: str
    changes_made: List[str]
    confidence_score: float = Field(ge=0.0, le=1.0)
    provider_used: str
    error_message: Optional[str] = None
    generation_time_ms: Optional[int] = None
    estimated_cost: Optional[float] = None

class PolicyTemplate(BaseModel):
    """Schema for policy templates"""
    id: str
    name: str
    description: str
    policy_type: PolicyType
    framework_compatibility: List[str]
    sections: List[str]
    customization_options: Dict[str, Any]
    language: str = Field(default='en-GB')

class PolicyTemplatesResponse(BaseModel):
    """Response schema for available policy templates"""
    templates: List[PolicyTemplate]
    total_count: int
    supported_frameworks: List[str]
    supported_languages: List[str]

class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status for AI providers"""
    google_status: str
    openai_status: str
    last_failure_time: Optional[str] = None
    failure_count: int = Field(default=0)
    next_retry_time: Optional[str] = None

class AIProviderMetrics(BaseModel):
    """Metrics for AI provider performance"""
    provider: str
    requests_total: int = Field(default=0)
    requests_successful: int = Field(default=0)
    requests_failed: int = Field(default=0)
    average_response_time_ms: float = Field(default=0.0)
    average_confidence_score: float = Field(default=0.0)
    total_cost: float = Field(default=0.0)
    last_24h_requests: int = Field(default=0)

class PolicyGenerationMetrics(BaseModel):
    """Overall policy generation metrics"""
    total_policies_generated: int = Field(default=0)
    success_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    average_generation_time_ms: float = Field(default=0.0)
    cache_hit_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    provider_metrics: List[AIProviderMetrics] = Field(default_factory=list)
    circuit_breaker_status: CircuitBreakerStatus
    cost_savings_percentage: float = Field(ge=0.0, le=100.0, default=0.0)
    monthly_cost_trend: List[float] = Field(default_factory=list)

class PolicyStreamingChunk(BaseModel):
    """Individual chunk of streaming policy generation data."""
    chunk_id: str = Field(..., description='Unique identifier for this chunk')
    content: str = Field(..., description='Text content of this chunk')
    chunk_type: str = Field(default='content', description='Type of chunk: content, metadata, section_header, complete, error')
    section_name: Optional[str] = Field(None, description='Name of the policy section being generated')
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description='Progress percentage (0.0 to 1.0)')

class PolicyStreamingMetadata(BaseModel):
    """Metadata for streaming policy generation response."""
    session_id: str = Field(..., description='Unique session identifier')
    policy_type: PolicyType = Field(..., description='Type of policy being generated')
    framework_id: str = Field(..., description='Framework ID for the policy')
    organization_name: str = Field(..., description='Organization name')
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stream_type: str = Field(default='policy_generation', description='Type of stream')
    estimated_sections: int = Field(default=5, description='Estimated number of sections')
    provider: str = Field(default='google', description='AI provider being used')
