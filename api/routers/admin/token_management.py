"""
Admin endpoints for token blacklist management.

Provides administrative tools for:
- Viewing blacklist statistics
- Managing blacklisted tokens
- Analyzing security patterns
- Performing maintenance operations
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.dependencies.auth import get_current_active_user
from api.dependencies.token_blacklist import get_token_blacklist
from database.user import User

# Constants
MAX_ITEMS = 1000
PATTERN_KEY_PREFIX = "pattern:"
PATTERN_TTL_SECONDS = 3600

router = APIRouter(prefix="/api/v1/admin/tokens", tags=["admin", "token-management"])


class BlacklistStatsResponse(BaseModel):
    """Response model for blacklist statistics."""

    current_blacklisted_tokens: int
    total_blacklisted: int
    blacklisted_today: int
    expired_tokens_cleaned: int
    suspicious_patterns_detected: int
    bulk_operations_count: int
    last_cleanup: Optional[str]


class BlacklistEntryResponse(BaseModel):
    """Response model for blacklist entry details."""

    token_hash: str
    reason: str
    blacklisted_at: str
    expires_at: str
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: Optional[Dict]


class TokenActionRequest(BaseModel):
    """Request model for token actions."""

    token: str
    reason: Optional[str] = "administrative_action"


class BulkTokenActionRequest(BaseModel):
    """Request model for bulk token actions."""

    user_id: str
    reason: str = "security_action"
    exclude_current_token: Optional[str] = None


def require_admin_role(current_user: User = Depends(get_current_active_user)) -> User:
    """Require admin role for access."""
    if not hasattr(current_user, "role") or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return current_user


def _decode_cache_value(value: Any) -> Any:
    """Decode cache payloads that may be stored as JSON strings."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _normalize_blacklist_entry(value: Any) -> Optional[Dict[str, Any]]:
    """Normalize a raw cache payload into a blacklist entry payload."""
    decoded = _decode_cache_value(value)
    if not isinstance(decoded, dict):
        return None
    return decoded


def _ttl_to_age_seconds(ttl_seconds: Optional[int]) -> Optional[int]:
    """Approximate event age from the remaining TTL."""
    if ttl_seconds is None or ttl_seconds < 0:
        return None
    return max(PATTERN_TTL_SECONDS - ttl_seconds, 0)


@router.get("/statistics", response_model=BlacklistStatsResponse)
async def get_blacklist_statistics(admin_user: User = Depends(require_admin_role)) -> Any:
    """Get comprehensive blacklist statistics."""
    blacklist = await get_token_blacklist()
    stats = await blacklist.get_blacklist_statistics()
    return BlacklistStatsResponse(**stats)


@router.get("/entry/{token_hash}", response_model=BlacklistEntryResponse)
async def get_blacklist_entry(
    token_hash: str, admin_user: User = Depends(require_admin_role)
) -> Optional[BlacklistEntryResponse]:
    """Get details for a specific blacklisted token by hash."""
    blacklist = await get_token_blacklist()
    cache_key = blacklist._generate_cache_key(token_hash)
    entry = _normalize_blacklist_entry(await blacklist.cache_manager.get(cache_key))
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blacklisted token entry not found",
        )
    return BlacklistEntryResponse(**entry)


@router.post("/blacklist")
async def blacklist_token_admin(
    request: TokenActionRequest, admin_user: User = Depends(require_admin_role)
) -> Dict[str, Any]:
    """Administratively blacklist a token."""
    blacklist = await get_token_blacklist()
    success = await blacklist.blacklist_token(
        token=request.token,
        reason=request.reason,
        user_id=str(admin_user.id),
        metadata={"admin_action": True, "admin_user": str(admin_user.id)},
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to blacklist token"
        )
    return {"message": "Token successfully blacklisted", "reason": request.reason}


@router.delete("/blacklist")
async def remove_token_from_blacklist(
    request: TokenActionRequest, admin_user: User = Depends(require_admin_role)
) -> Dict[str, Any]:
    """Remove a token from the blacklist."""
    blacklist = await get_token_blacklist()
    success = await blacklist.remove_token_from_blacklist(request.token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Token not found in blacklist"
        )
    return {"message": "Token removed from blacklist"}


@router.post("/blacklist/user")
async def blacklist_user_tokens(
    request: BulkTokenActionRequest, admin_user: User = Depends(require_admin_role)
) -> Dict[str, Any]:
    """Blacklist all tokens for a specific user."""
    blacklist = await get_token_blacklist()
    count = await blacklist.blacklist_user_tokens(
        user_id=request.user_id,
        reason=request.reason,
        exclude_current_token=request.exclude_current_token,
    )
    return {
        "message": f"Blacklisted {count} tokens for user {request.user_id}",
        "tokens_blacklisted": count,
        "reason": request.reason,
    }


@router.post("/cleanup")
async def cleanup_expired_tokens(admin_user: User = Depends(require_admin_role)) -> Dict[str, Any]:
    """Manually trigger cleanup of expired tokens."""
    blacklist = await get_token_blacklist()
    cleaned_count = await blacklist.cleanup_expired_tokens()
    return {
        "message": f"Cleaned up {cleaned_count} expired tokens",
        "tokens_cleaned": cleaned_count,
        "cleanup_time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health")
async def get_blacklist_health(admin_user: User = Depends(require_admin_role)) -> Dict[str, Any]:
    """Get health status of the token blacklist system."""
    try:
        blacklist = await get_token_blacklist()
        stats = await blacklist.get_blacklist_statistics()
        health_status = "healthy"
        issues = []
        if stats.get("blacklisted_today", 0) > MAX_ITEMS:
            health_status = "warning"
            issues.append("High blacklist volume detected")
        if stats.get("suspicious_patterns_detected", 0) > 10:
            health_status = "warning"
            issues.append("Multiple suspicious patterns detected")
        return {
            "status": health_status,
            "issues": issues,
            "statistics": stats,
            "last_check": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "error",
            "issues": [f"Blacklist system error: {str(e)}"],
            "last_check": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/patterns")
async def get_suspicious_patterns(
    hours: int = Query(24, description="Hours to look back for patterns"),
    admin_user: User = Depends(require_admin_role),
) -> Dict[str, Any]:
    """Get analysis of suspicious blacklisting patterns."""
    blacklist = await get_token_blacklist()
    cache_manager = blacklist.cache_manager
    patterns: list[Dict[str, Any]] = []
    requested_window_seconds = max(hours, 1) * 3600

    if cache_manager.redis_client:
        keys = await cache_manager.redis_client.keys(f"{PATTERN_KEY_PREFIX}*")
        for key in keys[:MAX_ITEMS]:
            raw_value = await cache_manager.get(key)
            ttl_seconds = await cache_manager.redis_client.ttl(key)
            age_seconds = _ttl_to_age_seconds(ttl_seconds)
            if age_seconds is not None and age_seconds > requested_window_seconds:
                continue
            _, ip_address, user_id = key.split(":", 2)
            patterns.append(
                {
                    "ip_address": ip_address,
                    "user_id": user_id,
                    "events": int(_decode_cache_value(raw_value) or 0),
                    "observed_age_seconds": age_seconds,
                    "expires_in_seconds": ttl_seconds,
                }
            )
    else:
        now = datetime.now(timezone.utc)
        for key, cache_entry in list(cache_manager.memory_cache.items())[:MAX_ITEMS]:
            if not key.startswith(PATTERN_KEY_PREFIX):
                continue
            _, ip_address, user_id = key.split(":", 2)
            expires_at = cache_entry.get("expires_at")
            ttl_seconds = None
            if expires_at is not None:
                ttl_seconds = max(int((expires_at - now).total_seconds()), 0)
            age_seconds = _ttl_to_age_seconds(ttl_seconds)
            if age_seconds is not None and age_seconds > requested_window_seconds:
                continue
            patterns.append(
                {
                    "ip_address": ip_address,
                    "user_id": user_id,
                    "events": int(_decode_cache_value(cache_entry.get("value")) or 0),
                    "observed_age_seconds": age_seconds,
                    "expires_in_seconds": ttl_seconds,
                }
            )

    patterns.sort(key=lambda item: item["events"], reverse=True)
    suspicious = [pattern for pattern in patterns if pattern["events"] >= 10]
    recommendations = []
    if suspicious:
        recommendations.append("Review repeated blacklist events from the same IP and user pair.")
    if any(pattern["events"] >= 25 for pattern in patterns):
        recommendations.append("Consider temporarily blocking the highest-volume source IPs.")
    if not recommendations:
        recommendations.append("No elevated blacklist pattern activity detected in the observable window.")

    return {
        "analysis_period_hours": hours,
        "observable_window_hours": 1,
        "patterns_detected": len(patterns),
        "suspicious_patterns": len(suspicious),
        "patterns": patterns,
        "recommendations": recommendations,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
