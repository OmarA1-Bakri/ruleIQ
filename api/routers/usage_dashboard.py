"""
import requests

Usage Dashboard API for SMB owners.
Provides visibility into AI feature usage and remaining limits.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from api.dependencies.auth import get_current_active_user, require_auth
from api.dependencies.database import get_async_db
from database.user import User
from database.rbac import AuditLog
from services.rate_limiting import RateLimitService
import json
router = APIRouter(tags=['Usage Dashboard'])

class UsageStats(BaseModel):
    """Usage statistics for a feature."""
    feature: str
    used_today: int
    daily_limit: int
    remaining: int
    reset_time: datetime

class UsageHistory(BaseModel):
    """Historical usage entry."""
    timestamp: datetime
    feature: str
    action: str
    metadata: Optional[Dict] = None

class UsageDashboardResponse(BaseModel):
    """Complete usage dashboard response."""
    current_usage: List[UsageStats]
    recent_activity: List[UsageHistory]
    usage_by_day: Dict[str, int]
    most_used_features: List[Dict[str, Any]]

@router.get('/usage/dashboard', response_model=UsageDashboardResponse)
@require_auth
async def get_usage_dashboard(current_user: User=Depends(get_current_active_user), db: AsyncSession=Depends(get_async_db), days: int=7) -> Any:
    """
    Get comprehensive usage dashboard for the current user.

    Shows:
    - Current daily usage and limits for all AI features
    - Recent activity history
    - Usage trends over time
    - Most frequently used features
    """
    current_usage = []
    for feature, _limits in RateLimitService.LIMITS.items():
        usage_info = await RateLimitService.check_rate_limit(db, current_user, feature, check_only=True)
        stats = UsageStats(feature=feature.replace('_', ' ').title(), used_today=usage_info['used_today'], daily_limit=usage_info['daily_limit'], remaining=usage_info['remaining'], reset_time=usage_info['reset_time'])
        current_usage.append(stats)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(AuditLog).where(and_(AuditLog.user_id == current_user.id, AuditLog.action.like('rate_limit:%'), AuditLog.timestamp >= cutoff_date)).order_by(AuditLog.timestamp.desc()).limit(50)
    result = await db.execute(stmt)
    audit_logs = result.scalars().all()
    recent_activity = []
    for log in audit_logs:
        try:
            metadata = json.loads(log.metadata) if log.metadata else {}
            history = UsageHistory(timestamp=log.timestamp, feature=log.action.replace('rate_limit:', '').replace('_', ' ').title(), action=metadata.get('action', 'usage'), metadata=metadata)
            recent_activity.append(history)
        except (json.JSONDecodeError, requests.RequestException):
            continue
    usage_by_day = {}
    for log in audit_logs:
        day_key = log.timestamp.strftime('%Y-%m-%d')
        usage_by_day[day_key] = usage_by_day.get(day_key, 0) + 1
    feature_counts = {}
    for log in audit_logs:
        feature = log.action.replace('rate_limit:', '')
        feature_counts[feature] = feature_counts.get(feature, 0) + 1
    most_used_features = [{'feature': k.replace('_', ' ').title(), 'count': v} for k, v in sorted(feature_counts.items(), key=lambda x: x[1], reverse=True)[:5]]
    return UsageDashboardResponse(current_usage=current_usage, recent_activity=recent_activity, usage_by_day=usage_by_day, most_used_features=most_used_features)

@router.get('/usage/limits', response_model=Dict[str, Dict])
@require_auth
async def get_usage_limits(current_user: User=Depends(get_current_active_user)) -> Any:
    """
    Get all available feature limits for the current user.

    Returns the daily limits for all AI features.
    """
    limits = {}
    for feature, config in RateLimitService.LIMITS.items():
        limits[feature.replace('_', ' ').title()] = {'daily_limit': config['daily'], 'window': config['window'], 'description': _get_feature_description(feature)}
    return limits

@router.get('/usage/feature/{feature}', response_model=UsageStats)
@require_auth
async def get_feature_usage(feature: str, current_user: User=Depends(get_current_active_user), db: AsyncSession=Depends(get_async_db)) -> Any:
    """
    Get detailed usage statistics for a specific feature.

    Args:
        feature: Feature name (e.g., 'ai_assessment', 'ai_policy_generation')
    """
    feature_key = feature.lower().replace(' ', '_')
    if feature_key not in RateLimitService.LIMITS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Feature '{feature}' not found")
    usage_info = await RateLimitService.check_rate_limit(db, current_user, feature_key, check_only=True)
    return UsageStats(feature=feature.replace('_', ' ').title(), used_today=usage_info['used_today'], daily_limit=usage_info['daily_limit'], remaining=usage_info['remaining'], reset_time=usage_info['reset_time'])

@router.post('/usage/reset-demo')
@require_auth
async def reset_demo_usage(current_user: User=Depends(get_current_active_user), db: AsyncSession=Depends(get_async_db)) -> Dict[str, Any]:
    """
    Reset usage counters for demo/testing purposes.

    NOTE: This endpoint should be removed or restricted in production.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    stmt = select(AuditLog).where(and_(AuditLog.user_id == current_user.id, AuditLog.action.like('rate_limit:%'), AuditLog.timestamp >= cutoff))
    result = await db.execute(stmt)
    logs_to_delete = result.scalars().all()
    for log in logs_to_delete:
        await db.delete(log)
    await db.commit()
    return {'message': 'Usage counters reset successfully', 'deleted_entries': len(logs_to_delete)}

def _get_feature_description(feature: str) -> str:
    """Get human-readable description for a feature."""
    descriptions = {'ai_assessment': 'AI-powered assessment help and question assistance', 'ai_policy_generation': 'Generate compliance policies using AI', 'ai_compliance_check': 'Validate policies against compliance frameworks', 'ai_recommendation': 'Get personalized compliance recommendations'}
    return descriptions.get(feature, 'AI feature usage')
