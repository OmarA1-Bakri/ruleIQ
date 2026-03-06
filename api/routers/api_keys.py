"""API Router for API Key Management"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from database.db_setup import get_db
from services.api_key_management import APIKeyManager, APIKeyType, APIKeyStatus
from api.dependencies.auth import get_current_active_user, get_api_key_auth
from database.user import User
from database.redis_client import get_redis_client

router = APIRouter(
    prefix="/api/v1/api-keys", tags=["API Keys"], responses={404: {"description": "Not found"}}
)


class CreateAPIKeyRequest(BaseModel):
    """Request model for creating an API key"""

    organization_name: str = Field(..., min_length=1, max_length=255)
    key_type: APIKeyType = Field(default=APIKeyType.STANDARD)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    allowed_ips: Optional[List[str]] = Field(default_factory=list)
    allowed_origins: Optional[List[str]] = Field(default_factory=list)
    scopes: Optional[List[str]] = Field(default_factory=list)
    rate_limit: Optional[int] = Field(None, ge=1, le=10000)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @validator("allowed_ips")
    def validate_ips(cls, v) -> Any:
        """Validate IP addresses and CIDR blocks"""
        import ipaddress

        for ip in v:
            try:
                if "/" in ip:
                    ipaddress.ip_network(ip)
                else:
                    ipaddress.ip_address(ip)
            except ValueError:
                raise ValueError(f"Invalid IP address or CIDR: {ip}")
        return v


class CreateAPIKeyResponse(BaseModel):
    """Response model for API key creation"""

    api_key: str = Field(..., description="The complete API key (only shown once)")
    key_id: str = Field(..., description="The key identifier")
    organization_id: str
    organization_name: str
    key_type: APIKeyType
    expires_at: Optional[datetime]
    scopes: List[str]
    rate_limit: int
    message: str = (
        "API key created successfully. Store this key securely - it cannot be retrieved again."
    )


class APIKeyInfo(BaseModel):
    """API key information (without secret)"""

    key_id: str
    organization_id: str
    organization_name: str
    key_type: APIKeyType
    status: APIKeyStatus
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    allowed_ips: List[str]
    allowed_origins: List[str]
    scopes: List[str]
    rate_limit: int
    rate_limit_window: int
    metadata: Dict[str, Any]


class RotateAPIKeyRequest(BaseModel):
    """Request model for rotating an API key"""

    expires_old_in_hours: int = Field(default=24, ge=1, le=168)


class UpdateAPIKeyRequest(BaseModel):
    """Request model for updating API key settings"""

    allowed_ips: Optional[List[str]] = None
    allowed_origins: Optional[List[str]] = None
    scopes: Optional[List[str]] = None
    rate_limit: Optional[int] = Field(None, ge=1, le=10000)
    metadata: Optional[Dict[str, Any]] = None


class APIKeyUsageStats(BaseModel):
    """API key usage statistics"""

    key_id: str
    period_days: int
    total_requests: int
    unique_ips: int
    endpoints: Dict[str, int]
    daily_usage: Dict[str, int]
    last_used: Optional[str]


@router.post("/", response_model=CreateAPIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> Any:
    """
    Create a new API key for B2B integrations.

    Requires admin role or organization owner privileges.
    """
    if current_user.role not in ["admin", "organization_owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create API keys",
        )
    manager = APIKeyManager(db, redis_client)
    try:
        api_key, key_id, metadata = await manager.generate_api_key(
            organization_id=current_user.organization_id or str(current_user.id),
            organization_name=request.organization_name,
            key_type=request.key_type,
            expires_in_days=request.expires_in_days,
            allowed_ips=request.allowed_ips,
            allowed_origins=request.allowed_origins,
            scopes=request.scopes,
            rate_limit=request.rate_limit,
            metadata=request.metadata,
        )
        return CreateAPIKeyResponse(
            api_key=api_key,
            key_id=key_id,
            organization_id=metadata.organization_id,
            organization_name=metadata.organization_name,
            key_type=metadata.key_type,
            expires_at=metadata.expires_at,
            scopes=metadata.scopes,
            rate_limit=metadata.rate_limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}",
        )


@router.get("/", response_model=List[APIKeyInfo])
async def list_api_keys(
    include_revoked: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> Any:
    """
    List all API keys for the current organization.
    """
    manager = APIKeyManager(db, redis_client)
    organization_id = current_user.organization_id or str(current_user.id)
    keys = await manager.list_organization_keys(organization_id, include_revoked)
    return [
        APIKeyInfo(
            key_id=key.key_id,
            organization_id=key.organization_id,
            organization_name=key.organization_name,
            key_type=key.key_type,
            status=key.status,
            created_at=key.created_at,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            allowed_ips=key.allowed_ips,
            allowed_origins=key.allowed_origins,
            scopes=key.scopes,
            rate_limit=key.rate_limit,
            rate_limit_window=key.rate_limit_window,
            metadata=key.key_metadata,
        )
        for key in keys
    ]


@router.get("/{key_id}", response_model=APIKeyInfo)
async def get_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> Any:
    """
    Get details of a specific API key.
    """
    manager = APIKeyManager(db, redis_client)
    metadata = await manager._load_key_metadata(key_id)
    if not metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    organization_id = current_user.organization_id or str(current_user.id)
    if metadata.organization_id != organization_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this API key"
        )
    return APIKeyInfo(
        key_id=metadata.key_id,
        organization_id=metadata.organization_id,
        organization_name=metadata.organization_name,
        key_type=metadata.key_type,
        status=metadata.status,
        created_at=metadata.created_at,
        expires_at=metadata.expires_at,
        last_used_at=metadata.last_used_at,
        allowed_ips=metadata.allowed_ips,
        allowed_origins=metadata.allowed_origins,
        scopes=metadata.scopes,
        rate_limit=metadata.rate_limit,
        rate_limit_window=metadata.rate_limit_window,
        metadata=metadata.metadata,
    )


@router.post("/{key_id}/rotate", response_model=CreateAPIKeyResponse)
async def rotate_api_key(
    key_id: str,
    request: RotateAPIKeyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> Any:
    """
    Rotate an API key, creating a new one and scheduling the old one for expiration.
    """
    manager = APIKeyManager(db, redis_client)
    metadata = await manager._load_key_metadata(key_id)
    if not metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    organization_id = current_user.organization_id or str(current_user.id)
    if metadata.organization_id != organization_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this API key"
        )
    try:
        new_api_key, new_key_id, new_metadata = await manager.rotate_api_key(
            key_id=key_id, expires_old_in_hours=request.expires_old_in_hours
        )
        return CreateAPIKeyResponse(
            api_key=new_api_key,
            key_id=new_key_id,
            organization_id=new_metadata.organization_id,
            organization_name=new_metadata.organization_name,
            key_type=new_metadata.key_type,
            expires_at=new_metadata.expires_at,
            scopes=new_metadata.scopes,
            rate_limit=new_metadata.rate_limit,
            message=f"API key rotated successfully. Old key will expire in {request.expires_old_in_hours} hours.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rotate API key: {str(e)}",
        )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    reason: str = "Manual revocation",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> Dict[str, Any]:
    """
    Revoke an API key immediately.
    """
    manager = APIKeyManager(db, redis_client)
    metadata = await manager._load_key_metadata(key_id)
    if not metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    organization_id = current_user.organization_id or str(current_user.id)
    if metadata.organization_id != organization_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this API key"
        )
    success = await manager.revoke_api_key(key_id, reason)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to revoke API key"
        )
    return {"message": f"API key {key_id} has been revoked"}


@router.post("/{key_id}/suspend")
async def suspend_api_key(
    key_id: str,
    reason: str = "Manual suspension",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> Dict[str, Any]:
    """
    Temporarily suspend an API key.
    """
    manager = APIKeyManager(db, redis_client)
    metadata = await manager._load_key_metadata(key_id)
    if not metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    organization_id = current_user.organization_id or str(current_user.id)
    if metadata.organization_id != organization_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this API key"
        )
    success = await manager.suspend_api_key(key_id, reason)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to suspend API key"
        )
    return {"message": f"API key {key_id} has been suspended"}


@router.post("/{key_id}/reactivate")
async def reactivate_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> Dict[str, Any]:
    """
    Reactivate a suspended API key.
    """
    manager = APIKeyManager(db, redis_client)
    metadata = await manager._load_key_metadata(key_id)
    if not metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    organization_id = current_user.organization_id or str(current_user.id)
    if metadata.organization_id != organization_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this API key"
        )
    success = await manager.reactivate_api_key(key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reactivate this API key (only suspended keys can be reactivated)",
        )
    return {"message": f"API key {key_id} has been reactivated"}


@router.get("/{key_id}/usage", response_model=APIKeyUsageStats)
async def get_api_key_usage(
    key_id: str,
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> Any:
    """
    Get usage statistics for an API key.
    """
    manager = APIKeyManager(db, redis_client)
    metadata = await manager._load_key_metadata(key_id)
    if not metadata:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    organization_id = current_user.organization_id or str(current_user.id)
    if metadata.organization_id != organization_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this API key"
        )
    stats = await manager.get_usage_statistics(key_id, days)
    return APIKeyUsageStats(**stats)


@router.get("/validate/test")
async def test_api_key_auth(
    request: Request,
    api_key_metadata: dict = Depends(get_api_key_auth),
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> Dict[str, Any]:
    """
    Test endpoint for API key authentication.

    Requires a valid API key in the X-API-Key header.
    """
    return {
        "message": "API key is valid",
        "api_key_prefix": x_api_key[:10] if x_api_key else None,
        "metadata": api_key_metadata,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
