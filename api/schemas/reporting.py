"""

Pydantic schemas for reporting API endpoints, with strong typing for complex inputs.
"""
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from pydantic import BaseModel, Field, validator

class ReportFormat(str, Enum):
    PDF = 'pdf'
    JSON = 'json'
    HTML = 'html'
    CSV = 'csv'

class ReportType(str, Enum):
    EXECUTIVE_SUMMARY = 'executive_summary'
    GAP_ANALYSIS = 'gap_analysis'
    EVIDENCE_REPORT = 'evidence_report'
    AUDIT_READINESS = 'audit_readiness'
    COMPLIANCE_STATUS = 'compliance_status'
    CONTROL_MATRIX = 'control_matrix'
    RISK_ASSESSMENT = 'risk_assessment'

class ReportFrequency(str, Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    CUSTOM = 'custom'

class ReportParameters(BaseModel):
    """Structured model for report generation parameters."""
    frameworks: Optional[List[str]] = Field(None, description='List of compliance frameworks to include.')
    start_date: Optional[date] = Field(None, description="Start date for the report's data range.")
    end_date: Optional[date] = Field(None, description="End date for the report's data range.")
    include_evidence: bool = Field(False, description='Whether to attach detailed evidence to the report.')
    extra_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description='Additional key-value parameters for custom reports.')

    @validator('end_date', always=True)
    def validate_date_range(self, v, values) -> Any:
        if 'start_date' in values and v and values['start_date'] and (v < values['start_date']):
            raise ValueError('End date cannot be before start date.')
        return v

class ScheduleConfig(BaseModel):
    """Structured model for schedule configuration."""
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description='Day of the week for weekly reports (0=Monday, 6=Sunday).')
    day_of_month: Optional[int] = Field(None, ge=1, le=31, description='Day of the month for monthly reports.')
    time_of_day: str = Field('09:00', description='Time of day to send the report (HH:MM format).')
    cron_expression: Optional[str] = Field(None, description='A cron expression for custom scheduling.')

    @validator('cron_expression', always=True)
    def validate_cron(self, v, values) -> Any:
        if v and values.get('frequency') != ReportFrequency.CUSTOM:
            raise ValueError('cron_expression can only be set for custom frequency.')
        return v

class GenerateReportRequest(BaseModel):
    business_profile_id: UUID
    report_type: ReportType
    format: ReportFormat = ReportFormat.PDF
    parameters: ReportParameters = Field(default_factory=ReportParameters)

class ReportResponse(BaseModel):
    report_id: str
    report_type: ReportType
    format: ReportFormat
    content: Union[str, Dict[str, Any]]
    content_type: str
    generated_at: datetime
    size_bytes: Optional[int] = None

class CreateScheduleRequest(BaseModel):
    business_profile_id: UUID
    report_type: ReportType
    format: ReportFormat
    frequency: ReportFrequency
    recipients: List[str]
    parameters: ReportParameters = Field(default_factory=ReportParameters)
    schedule_config: ScheduleConfig = Field(default_factory=ScheduleConfig)

    @validator('recipients')
    def validate_recipients(self, v) -> Any:
        import re
        email_pattern = '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
        for email in v:
            if not re.match(email_pattern, email):
                raise ValueError(f'Invalid email address: {email}')
        return v

class ScheduleResponse(BaseModel):
    id: UUID
    business_profile_id: UUID
    report_type: ReportType
    format: ReportFormat
    frequency: ReportFrequency
    recipients: List[str]
    parameters: ReportParameters
    schedule_config: ScheduleConfig
    active: bool
    created_at: datetime
    updated_at: datetime
    last_execution: Optional[datetime] = None
    next_execution: Optional[datetime] = None

    class Config:
        from_attributes = True

class UpdateScheduleRequest(BaseModel):
    frequency: Optional[ReportFrequency] = None
    recipients: Optional[List[str]] = None
    parameters: Optional[ReportParameters] = None
    active: Optional[bool] = None
    schedule_config: Optional[ScheduleConfig] = None

    @validator('recipients')
    def validate_recipients(self, v) -> Any:
        if v is not None:
            import re
            email_pattern = '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
            for email in v:
                if not re.match(email_pattern, email):
                    raise ValueError(f'Invalid email address: {email}')
        return v

class ScheduleListResponse(BaseModel):
    schedules: List[ScheduleResponse]
    total: int

class ReportHistoryItem(BaseModel):
    report_id: str
    report_type: ReportType
    format: ReportFormat
    generated_at: datetime
    size_bytes: Optional[int] = None
    download_url: Optional[str] = None
    status: str

class ReportHistoryResponse(BaseModel):
    reports: List[ReportHistoryItem]
    total: int
    page: int
    per_page: int

class ReportStatsResponse(BaseModel):
    total_reports_generated: int
    reports_this_month: int
    active_schedules: int
    most_popular_report_type: str
    total_recipients: int
    success_rate: float
    by_report_type: Dict[str, int]
    by_frequency: Dict[str, int]

class ExecuteScheduleResponse(BaseModel):
    status: str
    task_id: Optional[str] = None
    schedule_id: str
    executed_at: datetime
    message: Optional[str] = None
