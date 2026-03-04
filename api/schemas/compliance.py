"""

Compliance framework schemas for API validation.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum

class FrameworkCategory(str, Enum):
    """Categories of compliance frameworks"""
    DATA_PROTECTION = 'Data Protection'
    FINANCIAL_SERVICES = 'Financial Services'
    HEALTHCARE = 'Healthcare'
    CYBERSECURITY = 'Cybersecurity'
    GENERAL = 'General'

class GeographicRegion(str, Enum):
    """Geographic regions for frameworks"""
    UK = 'UK'
    ENGLAND = 'England'
    SCOTLAND = 'Scotland'
    WALES = 'Wales'
    NORTHERN_IRELAND = 'Northern Ireland'
    EU = 'EU'
    GLOBAL = 'Global'

class UKFrameworkSchema(BaseModel):
    """Schema for UK compliance framework creation/update"""
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10)
    category: FrameworkCategory
    applicable_industries: List[str] = Field(default_factory=list)
    employee_threshold: Optional[int] = Field(None, ge=1)
    revenue_threshold: Optional[str] = None
    geographic_scope: List[GeographicRegion] = Field(default=[GeographicRegion.UK])
    key_requirements: List[str] = Field(default_factory=list)
    control_domains: List[str] = Field(default_factory=list)
    evidence_types: List[str] = Field(default_factory=list)
    relevance_factors: Dict[str, Any] = Field(default_factory=dict)
    complexity_score: int = Field(default=1, ge=1, le=10)
    implementation_time_weeks: int = Field(default=12, ge=1, le=104)
    estimated_cost_range: str = Field(default='£5,000-£25,000')
    policy_template: str = Field(default='')
    control_templates: Dict[str, Any] = Field(default_factory=dict)
    evidence_templates: Dict[str, Any] = Field(default_factory=dict)
    version: str = Field(default='1.0', pattern='^\\d+\\.\\d+(\\.\\d+)?$')
    is_active: bool = Field(default=True)

    @validator('geographic_scope')
    def validate_uk_scope(cls, v) -> Any:
        """Ensure at least one UK region is included"""
        uk_regions = {GeographicRegion.UK, GeographicRegion.ENGLAND, GeographicRegion.SCOTLAND, GeographicRegion.WALES, GeographicRegion.NORTHERN_IRELAND}
        if not set(v) & uk_regions:
            raise ValueError('UK frameworks must include at least one UK region')
        return v

    class Config:
        use_enum_values = True

class FrameworkResponse(BaseModel):
    """Response schema for framework data"""
    id: str
    name: str
    display_name: str
    description: str
    category: str
    geographic_scope: List[str]
    complexity_score: int
    version: str
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

class FrameworkListResponse(BaseModel):
    """Response schema for framework list"""
    frameworks: List[FrameworkResponse]
    total_count: int
    filtered_count: int
    region: Optional[str] = None
    category: Optional[str] = None

class FrameworkLoadRequest(BaseModel):
    """Request schema for bulk loading frameworks"""
    frameworks: List[UKFrameworkSchema]
    overwrite_existing: bool = Field(default=False)

    @validator('frameworks')
    def validate_frameworks_not_empty(cls, v) -> Any:
        if not v:
            raise ValueError('At least one framework must be provided')
        return v

class FrameworkLoadResponse(BaseModel):
    """Response schema for framework loading result"""
    success: bool
    loaded_count: int
    skipped_count: int
    error_count: int
    loaded_frameworks: List[str]
    skipped_frameworks: List[str]
    errors: List[str]
    total_processed: int

class FrameworkQueryParams(BaseModel):
    """Query parameters for framework filtering"""
    region: Optional[str] = Field(None, description='Filter by geographic region')
    category: Optional[str] = Field(None, description='Filter by framework category')
    industry: Optional[str] = Field(None, description='Filter by applicable industry')
    complexity_min: Optional[int] = Field(None, ge=1, le=10)
    complexity_max: Optional[int] = Field(None, ge=1, le=10)
    active_only: bool = Field(True, description='Include only active frameworks')

    @validator('complexity_max')
    def validate_complexity_range(cls, v, values) -> Any:
        if v is not None and 'complexity_min' in values and (values['complexity_min'] is not None):
            if v < values['complexity_min']:
                raise ValueError('complexity_max must be >= complexity_min')
        return v
