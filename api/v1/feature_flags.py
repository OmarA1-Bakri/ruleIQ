"""
Feature Flags Management API
Provides RESTful endpoints for managing and evaluating feature flags
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.db_setup import get_db_session
from services.feature_flag_service import get_feature_flag_service
from models.feature_flags import (
    FeatureFlag as FeatureFlagModel,
    FeatureFlagAudit,
    FeatureFlagStatus,
)
from middleware.jwt_auth_v2 import jwt_required


# Router configuration
router = APIRouter(
    prefix="/api/v1/feature-flags",
    tags=["feature-flags"],
    responses={404: {"description": "Not found"}},
)


# Request/Response Models
class FeatureFlagCreateRequest(BaseModel):
    """Request model for creating a feature flag"""

    name: str = Field(..., description="Unique name of the feature flag")
    description: Optional[str] = Field(None, description="Description of the feature flag")
    enabled: bool = Field(False, description="Whether the flag is enabled")
    percentage: float = Field(0.0, ge=0.0, le=100.0, description="Percentage rollout (0-100)")
    whitelist: List[str] = Field(default_factory=list, description="User IDs to always enable")
    blacklist: List[str] = Field(default_factory=list, description="User IDs to always disable")
    environment_overrides: Dict[str, bool] = Field(
        default_factory=dict, description="Environment-specific overrides"
    )
    environments: List[str] = Field(
        default_factory=lambda: ["development"], description="Allowed environments"
    )
    expires_at: Optional[datetime] = Field(None, description="Expiration time")
    starts_at: Optional[datetime] = Field(None, description="Start time")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class FeatureFlagUpdateRequest(BaseModel):
    """Request model for updating a feature flag"""

    description: Optional[str] = None
    enabled: Optional[bool] = None
    percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    whitelist: Optional[List[str]] = None
    blacklist: Optional[List[str]] = None
    environment_overrides: Optional[Dict[str, bool]] = None
    environments: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    starts_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    reason: Optional[str] = Field(None, description="Reason for update")


class FeatureFlagResponse(BaseModel):
    """Response model for feature flag"""

    id: UUID
    name: str
    description: Optional[str]
    enabled: bool
    status: str
    percentage: float
    whitelist: List[str]
    blacklist: List[str]
    environment_overrides: Dict[str, bool]
    environments: List[str]
    expires_at: Optional[datetime]
    starts_at: Optional[datetime]
    tags: List[str]
    metadata: Dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]


class FeatureFlagEvaluationRequest(BaseModel):
    """Request model for evaluating a feature flag"""

    user_id: Optional[str] = Field(None, description="User ID for evaluation")
    environment: str = Field("production", description="Environment for evaluation")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for evaluation")


class FeatureFlagEvaluationResponse(BaseModel):
    """Response model for feature flag evaluation"""

    flag_name: str
    enabled: bool
    reason: str
    user_id: Optional[str]
    environment: str
    evaluation_time_ms: float


class FeatureFlagBulkEvaluationRequest(BaseModel):
    """Request model for evaluating multiple feature flags"""

    flag_names: List[str] = Field(..., description="List of flag names to evaluate")
    user_id: Optional[str] = Field(None, description="User ID for evaluation")
    environment: str = Field("production", description="Environment for evaluation")


class FeatureFlagBulkEvaluationResponse(BaseModel):
    """Response model for bulk feature flag evaluation"""

    evaluations: Dict[str, bool]
    reasons: Dict[str, str]
    total_time_ms: float


# API Endpoints
@router.get("/", response_model=List[FeatureFlagResponse])
async def list_feature_flags(
    environment: Optional[str] = Query(None, description="Filter by environment"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    db: Session = Depends(get_db_session),
):
    """
    List all feature flags with optional filtering
    """
    try:
        query = db.query(FeatureFlagModel)

        # Apply filters
        if environment:
            query = query.filter(FeatureFlagModel.environments.contains([environment]))

        if tag:
            query = query.filter(FeatureFlagModel.tags.contains([tag]))

        if enabled is not None:
            query = query.filter(FeatureFlagModel.enabled == enabled)

        # Pagination
        query.count()
        flags = query.offset(skip).limit(limit).all()

        # Convert to response models
        response = []
        for flag in flags:
            response.append(
                FeatureFlagResponse(
                    id=flag.id,
                    name=flag.name,
                    description=flag.description,
                    enabled=flag.enabled,
                    status=flag.status or FeatureFlagStatus.DISABLED.value,
                    percentage=flag.percentage,
                    whitelist=flag.whitelist or [],
                    blacklist=flag.blacklist or [],
                    environment_overrides=flag.environment_overrides or {},
                    environments=flag.environments or [],
                    expires_at=flag.expires_at,
                    starts_at=flag.starts_at,
                    tags=flag.tags or [],
                    metadata=flag.metadata or {},
                    version=flag.version,
                    created_at=flag.created_at,
                    updated_at=flag.updated_at,
                    created_by=flag.created_by,
                    updated_by=flag.updated_by,
                )
            )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing feature flags: {str(e)}")


@router.get("/{flag_name}", response_model=FeatureFlagResponse)
async def get_feature_flag(flag_name: str, db: Session = Depends(get_db_session)):
    """
    Get a specific feature flag by name
    """
    try:
        flag = db.query(FeatureFlagModel).filter_by(name=flag_name).first()

        if not flag:
            raise HTTPException(status_code=404, detail=f"Feature flag '{flag_name}' not found")

        return FeatureFlagResponse(
            id=flag.id,
            name=flag.name,
            description=flag.description,
            enabled=flag.enabled,
            status=flag.status or FeatureFlagStatus.DISABLED.value,
            percentage=flag.percentage,
            whitelist=flag.whitelist or [],
            blacklist=flag.blacklist or [],
            environment_overrides=flag.environment_overrides or {},
            environments=flag.environments or [],
            expires_at=flag.expires_at,
            starts_at=flag.starts_at,
            tags=flag.tags or [],
            metadata=flag.metadata or {},
            version=flag.version,
            created_at=flag.created_at,
            updated_at=flag.updated_at,
            created_by=flag.created_by,
            updated_by=flag.updated_by,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving feature flag: {str(e)}")


@router.post("/", response_model=FeatureFlagResponse, status_code=201)
@jwt_required
async def create_feature_flag(
    request: Request, flag_request: FeatureFlagCreateRequest, db: Session = Depends(get_db_session)
):
    """
    Create a new feature flag
    Requires authentication
    """
    try:
        # Get current user
        current_user = request.state.user
        user_id = str(current_user.get("sub", "system"))

        # Check if flag already exists
        existing = db.query(FeatureFlagModel).filter_by(name=flag_request.name).first()
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Feature flag '{flag_request.name}' already exists"
            )

        # Create new flag
        flag = FeatureFlagModel(
            name=flag_request.name,
            description=flag_request.description,
            enabled=flag_request.enabled,
            status=FeatureFlagStatus.ENABLED.value
            if flag_request.enabled
            else FeatureFlagStatus.DISABLED.value,
            percentage=flag_request.percentage,
            whitelist=flag_request.whitelist,
            blacklist=flag_request.blacklist,
            environment_overrides=flag_request.environment_overrides,
            environments=flag_request.environments,
            expires_at=flag_request.expires_at,
            starts_at=flag_request.starts_at,
            tags=flag_request.tags,
            metadata=flag_request.metadata,
            created_by=user_id,
            updated_by=user_id,
        )

        db.add(flag)

        # Create audit log
        audit = FeatureFlagAudit(
            feature_flag_id=flag.id,
            action="created",
            new_state=flag_request.dict(),
            user_id=user_id,
            reason="Initial creation",
        )
        db.add(audit)

        db.commit()
        db.refresh(flag)

        # Invalidate cache
        service = get_feature_flag_service()
        await service.invalidate_cache(flag.name)

        return FeatureFlagResponse(
            id=flag.id,
            name=flag.name,
            description=flag.description,
            enabled=flag.enabled,
            status=flag.status,
            percentage=flag.percentage,
            whitelist=flag.whitelist,
            blacklist=flag.blacklist,
            environment_overrides=flag.environment_overrides,
            environments=flag.environments,
            expires_at=flag.expires_at,
            starts_at=flag.starts_at,
            tags=flag.tags,
            metadata=flag.metadata,
            version=flag.version,
            created_at=flag.created_at,
            updated_at=flag.updated_at,
            created_by=flag.created_by,
            updated_by=flag.updated_by,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating feature flag: {str(e)}")


@router.put("/{flag_name}", response_model=FeatureFlagResponse)
@jwt_required
async def update_feature_flag(
    request: Request,
    flag_name: str,
    flag_update: FeatureFlagUpdateRequest,
    db: Session = Depends(get_db_session),
):
    """
    Update an existing feature flag
    Requires authentication
    """
    try:
        # Get current user
        current_user = request.state.user
        user_id = str(current_user.get("sub", "system"))

        # Get existing flag
        flag = db.query(FeatureFlagModel).filter_by(name=flag_name).first()
        if not flag:
            raise HTTPException(status_code=404, detail=f"Feature flag '{flag_name}' not found")

        # Store previous state for audit
        previous_state = {
            "enabled": flag.enabled,
            "percentage": flag.percentage,
            "whitelist": flag.whitelist,
            "blacklist": flag.blacklist,
            "environment_overrides": flag.environment_overrides,
            "environments": flag.environments,
            "expires_at": flag.expires_at.isoformat() if flag.expires_at else None,
            "starts_at": flag.starts_at.isoformat() if flag.starts_at else None,
        }

        # Update fields if provided
        update_data = flag_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field != "reason" and value is not None:
                setattr(flag, field, value)

        # Update status based on enabled state
        if "enabled" in update_data:
            flag.status = (
                FeatureFlagStatus.ENABLED.value
                if flag.enabled
                else FeatureFlagStatus.DISABLED.value
            )

        # Update metadata
        flag.updated_at = datetime.utcnow()
        flag.updated_by = user_id
        flag.version += 1

        # Create audit log
        audit = FeatureFlagAudit(
            feature_flag_id=flag.id,
            action="updated",
            previous_state=previous_state,
            new_state=update_data,
            changes=update_data,
            user_id=user_id,
            reason=flag_update.reason or "Manual update via API",
        )
        db.add(audit)

        db.commit()
        db.refresh(flag)

        # Invalidate cache
        service = get_feature_flag_service()
        await service.invalidate_cache(flag.name)

        return FeatureFlagResponse(
            id=flag.id,
            name=flag.name,
            description=flag.description,
            enabled=flag.enabled,
            status=flag.status,
            percentage=flag.percentage,
            whitelist=flag.whitelist,
            blacklist=flag.blacklist,
            environment_overrides=flag.environment_overrides,
            environments=flag.environments,
            expires_at=flag.expires_at,
            starts_at=flag.starts_at,
            tags=flag.tags,
            metadata=flag.metadata,
            version=flag.version,
            created_at=flag.created_at,
            updated_at=flag.updated_at,
            created_by=flag.created_by,
            updated_by=flag.updated_by,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating feature flag: {str(e)}")


@router.delete("/{flag_name}", status_code=204)
@jwt_required
async def delete_feature_flag(
    request: Request, flag_name: str, db: Session = Depends(get_db_session)
):
    """
    Delete a feature flag
    Requires authentication
    """
    try:
        # Get current user
        current_user = request.state.user
        user_id = str(current_user.get("sub", "system"))

        # Get existing flag
        flag = db.query(FeatureFlagModel).filter_by(name=flag_name).first()
        if not flag:
            raise HTTPException(status_code=404, detail=f"Feature flag '{flag_name}' not found")

        # Create final audit log
        audit = FeatureFlagAudit(
            feature_flag_id=flag.id,
            action="deleted",
            previous_state={
                "name": flag.name,
                "enabled": flag.enabled,
                "percentage": flag.percentage,
            },
            user_id=user_id,
            reason="Deleted via API",
        )
        db.add(audit)

        # Delete the flag (cascade will delete related records)
        db.delete(flag)
        db.commit()

        # Invalidate cache
        service = get_feature_flag_service()
        await service.invalidate_cache(flag_name)

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting feature flag: {str(e)}")


@router.post("/{flag_name}/evaluate", response_model=FeatureFlagEvaluationResponse)
async def evaluate_feature_flag(flag_name: str, evaluation_request: FeatureFlagEvaluationRequest):
    """
    Evaluate a feature flag for a specific user and context
    Does not require authentication for public evaluation
    """
    try:
        import time

        start_time = time.perf_counter()

        service = get_feature_flag_service()

        enabled, reason = await service.is_enabled_for_user(
            flag_name=flag_name,
            user_id=evaluation_request.user_id,
            environment=evaluation_request.environment,
            context=evaluation_request.context,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return FeatureFlagEvaluationResponse(
            flag_name=flag_name,
            enabled=enabled,
            reason=reason,
            user_id=evaluation_request.user_id,
            environment=evaluation_request.environment,
            evaluation_time_ms=elapsed_ms,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error evaluating feature flag: {str(e)}")


@router.post("/evaluate-bulk", response_model=FeatureFlagBulkEvaluationResponse)
async def evaluate_feature_flags_bulk(evaluation_request: FeatureFlagBulkEvaluationRequest):
    """
    Evaluate multiple feature flags at once
    Optimized for performance with parallel evaluation
    """
    try:
        import time
        import asyncio

        start_time = time.perf_counter()
        service = get_feature_flag_service()

        # Evaluate all flags in parallel
        tasks = []
        for flag_name in evaluation_request.flag_names:
            task = service.is_enabled_for_user(
                flag_name=flag_name,
                user_id=evaluation_request.user_id,
                environment=evaluation_request.environment,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        evaluations = {}
        reasons = {}

        for flag_name, result in zip(evaluation_request.flag_names, results):
            if isinstance(result, Exception):
                evaluations[flag_name] = False
                reasons[flag_name] = "error"
            else:
                enabled, reason = result
                evaluations[flag_name] = enabled
                reasons[flag_name] = reason

        total_time_ms = (time.perf_counter() - start_time) * 1000

        return FeatureFlagBulkEvaluationResponse(
            evaluations=evaluations, reasons=reasons, total_time_ms=total_time_ms
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error evaluating feature flags: {str(e)}")


@router.get("/{flag_name}/audit", response_model=List[Dict[str, Any]])
@jwt_required
async def get_feature_flag_audit_trail(
    request: Request,
    flag_name: str,
    limit: int = Query(50, ge=1, le=500, description="Number of audit entries to return"),
    db: Session = Depends(get_db_session),
):
    """
    Get audit trail for a specific feature flag
    Requires authentication
    """
    try:
        # Get the flag
        flag = db.query(FeatureFlagModel).filter_by(name=flag_name).first()
        if not flag:
            raise HTTPException(status_code=404, detail=f"Feature flag '{flag_name}' not found")

        # Get audit logs
        audits = (
            db.query(FeatureFlagAudit)
            .filter_by(feature_flag_id=flag.id)
            .order_by(FeatureFlagAudit.created_at.desc())
            .limit(limit)
            .all()
        )

        # Convert to response
        response = []
        for audit in audits:
            response.append(
                {
                    "id": str(audit.id),
                    "action": audit.action,
                    "changes": audit.changes,
                    "previous_state": audit.previous_state,
                    "new_state": audit.new_state,
                    "user_id": audit.user_id,
                    "user_email": audit.user_email,
                    "reason": audit.reason,
                    "created_at": audit.created_at.isoformat(),
                }
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audit trail: {str(e)}")


@router.get("/metrics/{flag_name}")
@jwt_required
async def get_feature_flag_metrics(
    request: Request,
    flag_name: str,
    hours: int = Query(24, ge=1, le=168, description="Number of hours of metrics to retrieve"),
):
    """
    Get usage metrics for a specific feature flag
    Requires authentication
    """
    try:
        service = get_feature_flag_service()

        # Get metrics from Redis
        metrics = {}
        now = datetime.utcnow()

        for hour in range(hours):
            timestamp = now - timedelta(hours=hour)
            metrics_key = f"ff:metrics:{flag_name}:{timestamp.strftime('%Y%m%d%H')}"

            hour_metrics = service.redis.hgetall(metrics_key)
            if hour_metrics:
                metrics[timestamp.strftime("%Y-%m-%d %H:00")] = {
                    k: int(v) for k, v in hour_metrics.items()
                }

        return {"flag_name": flag_name, "period_hours": hours, "metrics": metrics}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving metrics: {str(e)}")
