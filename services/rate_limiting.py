"""

Rate limiting service for AI features.
Implements per-user daily limits for SMB users.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from database.user import User
from database.rbac import AuditLog
import json
from fastapi import HTTPException, status


class RateLimitService:
    """Service for managing AI feature rate limits."""

    # Daily limits for SMB users
    LIMITS = {
        "ai_assessment": {"daily": 10, "window": "24h"},
        "ai_policy_generation": {"daily": 5, "window": "24h"},
        "ai_compliance_check": {"daily": 20, "window": "24h"},
        "ai_recommendation": {"daily": 15, "window": "24h"},
    }

    @classmethod
    async def check_rate_limit(
        cls, db: AsyncSession, user: User, feature: str, check_only: bool = False
    ) -> Dict[str, any]:
        """
        Check if user has exceeded rate limit for a feature.

        Args:
            db: Database session
            user: Current user
            feature: Feature name (e.g., 'ai_assessment', 'ai_policy_generation')
            check_only: If True, only check usage without raising exception

        Returns:
            Dict with 'allowed' bool and usage details

        Raises:
            HTTPException: If rate limit exceeded (unless check_only=True)
        """
        if feature not in cls.LIMITS:
            # No rate limit for this feature
            return {"allowed": True, "limit": None, "used": 0, "remaining": None}

        limit_config = cls.LIMITS[feature]
        daily_limit = limit_config["daily"]

        # Calculate time window (last 24 hours)
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=24)

        # Count usage in the window from audit logs
        stmt = select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.user_id == user.id,
                AuditLog.action == f"{feature}_request",
                AuditLog.timestamp >= window_start,
            ),
        )

        result = await db.execute(stmt)
        usage_count = result.scalar() or 0

        remaining = daily_limit - usage_count
        allowed = usage_count < daily_limit

        # Calculate reset time
        reset_time = window_start + timedelta(hours=24)

        if not allowed and not check_only:
            # Calculate when the oldest request will expire
            oldest_stmt = (
                select(AuditLog.timestamp)
                .where(
                    and_(
                        AuditLog.user_id == user.id,
                        AuditLog.action == f"{feature}_request",
                        AuditLog.timestamp >= window_start,
                    ),
                )
                .order_by(AuditLog.timestamp)
                .limit(1),
            )

            oldest_result = await db.execute(oldest_stmt)
            oldest_request = oldest_result.scalar()

            if oldest_request:
                reset_time = oldest_request + timedelta(hours=24)
                reset_in_seconds = int((reset_time - now).total_seconds())
            else:
                reset_in_seconds = 0

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "feature": feature,
                    "limit": daily_limit,
                    "used": usage_count,
                    "reset_in_seconds": reset_in_seconds,
                    "reset_at": (now + timedelta(seconds=reset_in_seconds)).isoformat(),
                },
            )

        return {
            "allowed": allowed,
            "daily_limit": daily_limit,
            "used_today": usage_count,
            "remaining": remaining,
            "reset_time": reset_time,
            "window": "24h",
        }

    @classmethod
    async def track_usage(
        cls, db: AsyncSession, user: User, feature: str, metadata: Optional[Dict] = None
    ) -> None:
        """
        Track usage of an AI feature for rate limiting.

        Args:
            db: Database session
            user: Current user
            feature: Feature name
            metadata: Optional metadata to store
        """
        # Create audit log entry for tracking
        audit_entry = AuditLog(
            user_id=user.id,
            action=f"{feature}_request",
            resource_type="rate_limit",
            resource_id=feature,
            details=json.dumps(
                {
                    "feature": feature,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **(metadata or {}),
                },
            ),
            severity="info",
            timestamp=datetime.now(timezone.utc),
        )

        db.add(audit_entry)
        await db.commit()

    @classmethod
    async def get_usage_stats(cls, db: AsyncSession, user: User) -> Dict[str, any]:
        """
        Get usage statistics for all rate-limited features.

        Args:
            db: Database session
            user: Current user

        Returns:
            Dict with usage stats for each feature
        """
        stats = {}
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=24)

        for feature, config in cls.LIMITS.items():
            # Count usage for this feature
            stmt = select(func.count(AuditLog.id)).where(
                and_(
                    AuditLog.user_id == user.id,
                    AuditLog.action == f"{feature}_request",
                    AuditLog.timestamp >= window_start,
                ),
            )

            result = await db.execute(stmt)
            usage_count = result.scalar() or 0

            stats[feature] = {
                "limit": config["daily"],
                "used": usage_count,
                "remaining": config["daily"] - usage_count,
                "window": config["window"],
                "percentage_used": (
                    round((usage_count / config["daily"]) * 100, 1) if config["daily"] > 0 else 0,
                ),
            }

        return {
            "user_id": str(user.id),
            "period": "24h",
            "measured_at": now.isoformat(),
            "features": stats,
        }

    @classmethod
    async def reset_user_limits(
        cls, db: AsyncSession, user: User, feature: Optional[str] = None
    ) -> None:
        """
        Reset rate limits for a user (admin function).

        Args:
            db: Database session
            user: User to reset limits for
            feature: Optional specific feature to reset, or None for all
        """
        # This would typically be restricted to admin users
        # For now, we'll just clear the relevant audit log entries

        window_start = datetime.now(timezone.utc) - timedelta(hours=24)

        if feature:
            # Reset specific feature
            stmt = select(AuditLog).where(
                and_(
                    AuditLog.user_id == user.id,
                    AuditLog.action == f"{feature}_request",
                    AuditLog.timestamp >= window_start,
                ),
            )
        else:
            # Reset all features
            actions = [f"{f}_request" for f in cls.LIMITS]
            stmt = select(AuditLog).where(
                and_(
                    AuditLog.user_id == user.id,
                    AuditLog.action.in_(actions),
                    AuditLog.timestamp >= window_start,
                ),
            )

        result = await db.execute(stmt)
        entries = result.scalars().all()

        for entry in entries:
            await db.delete(entry)

        await db.commit()
