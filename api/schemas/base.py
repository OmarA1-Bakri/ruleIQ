"""

Base schemas for ComplianceGPT API

Common schemas and base classes used across the API.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BaseSchema(BaseModel):
    """Base schema with common configuration"""

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


from typing import TypeVar, Generic

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """Standard response wrapper for API endpoints"""

    success: bool = Field(default=True, description="Indicates if the request was successful")
    data: Optional[T] = Field(default=None, description="The response data")
    message: Optional[str] = Field(default=None, description="Optional message")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Error details if any")

    class Config:
        from_attributes = True


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields"""

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class IDMixin(BaseModel):
    """Mixin for ID field"""

    id: UUID = Field(..., description="Unique identifier")


class BaseResponse(BaseSchema):
    """Base response schema"""

    success: bool = Field(default=True, description="Operation success status")
    message: Optional[str] = Field(default=None, description="Response message")


class ErrorResponse(BaseSchema):
    """Error response schema"""

    error: Dict[str, Any] = Field(..., description="Error details")


class PaginationParams(BaseSchema):
    """Pagination parameters"""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    size: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseResponse):
    """Paginated response schema"""

    data: list = Field(..., description="Response data")
    pagination: Dict[str, Any] = Field(..., description="Pagination metadata")


class HealthCheckResponse(BaseSchema):
    """Health check response with database monitoring"""

    status: str = Field(..., description="Service status (healthy, warning, degraded, error)")
    message: Optional[str] = Field(default=None, description="Status message")
    timestamp: Optional[str] = Field(default=None, description="Check timestamp")
    version: str = Field(default="1.0.0", description="API version")
    database: Optional[Dict[str, Any]] = Field(default=None, description="Database monitoring data")


class APIInfoResponse(BaseSchema):
    """API information response"""

    message: str = Field(..., description="API name")
    version: str = Field(..., description="API version")
    status: str = Field(..., description="API status")
