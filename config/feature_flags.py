"""
Feature Flags System for RuleIQ
Enables safe rollout of new features with gradual deployment
"""

from typing import Optional, List
from pydantic import BaseModel, Field
import redis
import json
from functools import wraps
from datetime import datetime
import asyncio


class FeatureFlag(BaseModel):
    """Feature flag configuration"""

    name: str
    enabled: bool = False
    percentage: int = Field(0, ge=0, le=100)  # Percentage rollout
    whitelist: List[str] = []  # User IDs to always enable
    blacklist: List[str] = []  # User IDs to always disable
    environments: List[str] = ["development"]  # Enabled environments
    expires_at: Optional[datetime] = None


class FeatureFlagService:
    """Service for managing feature flags"""

    def __init__(self, redis_client: Optional[redis.Redis] = None) -> None:
        self.redis = redis_client or redis.Redis(host="localhost", port=6379, decode_responses=True)
        self.cache_ttl = 60  # 60 second cache

    def is_enabled(
        self, flag_name: str, user_id: Optional[str] = None, environment: str = "production"
    ) -> bool:
        """Check if feature flag is enabled for user"""

        # Try to get from cache first
        cache_key = f"ff:{flag_name}"
        cached = self.redis.get(cache_key)

        if cached:
            flag = FeatureFlag(**json.loads(cached))
        else:
            # Load from configuration
            flag = self._load_flag(flag_name)
            if flag:
                # Cache for 60 seconds
                self.redis.setex(cache_key, self.cache_ttl, flag.json())

        if not flag:
            return False

        # Check environment
        if environment not in flag.environments:
            return False

        # Check expiration
        if flag.expires_at and datetime.now() > flag.expires_at:
            return False

        # Check blacklist
        if user_id and user_id in flag.blacklist:
            return False

        # Check whitelist
        if user_id and user_id in flag.whitelist:
            return True

        # Check global enable
        if flag.enabled and flag.percentage == 100:
            return True

        # Check percentage rollout
        if flag.enabled and user_id:
            # Consistent hashing for user
            hash_val = hash(f"{flag_name}:{user_id}") % 100
            return hash_val < flag.percentage

        return flag.enabled

    def _load_flag(self, flag_name: str) -> Optional[FeatureFlag]:
        """Load flag configuration from database or config"""
        # In production, load from database
        # For now, return default configurations

        default_flags = {
            # SECURITY FIX: Auth middleware v2 feature flag for SEC-001
            "AUTH_MIDDLEWARE_V2_ENABLED": FeatureFlag(
                name="AUTH_MIDDLEWARE_V2_ENABLED",
                enabled=True,
                percentage=100,  # Start with 100% in dev/test, gradual in prod
                environments=["development", "testing", "staging", "production"],
                whitelist=[],  # Add specific user IDs for testing
                blacklist=[],  # Emergency kill switch - add user IDs to disable
            ),
            "new_dashboard": FeatureFlag(
                name="new_dashboard",
                enabled=True,
                percentage=50,  # 50% rollout
                environments=["development", "staging", "production"],
            ),
            "ai_assistant": FeatureFlag(
                name="ai_assistant",
                enabled=True,
                percentage=10,  # 10% rollout
                whitelist=["admin_user_id"],
                environments=["development", "staging"],
            ),
            "advanced_analytics": FeatureFlag(
                name="advanced_analytics", enabled=False, environments=["development"]
            ),
        }

        return default_flags.get(flag_name)


def feature_flag(flag_name: str):
    """Decorator for feature flag protected code"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            service = FeatureFlagService()
            user_id = kwargs.get("user_id") or (args[0].user_id if args else None)

            if service.is_enabled(flag_name, user_id):
                return await func(*args, **kwargs)
            else:
                # Return fallback or raise exception
                raise FeatureNotEnabledException(f"Feature {flag_name} is not enabled")

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            service = FeatureFlagService()
            user_id = kwargs.get("user_id") or (args[0].user_id if args else None)

            if service.is_enabled(flag_name, user_id):
                return func(*args, **kwargs)
            else:
                raise FeatureNotEnabledException(f"Feature {flag_name} is not enabled")

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class FeatureNotEnabledException(Exception):
    """Exception raised when feature is not enabled"""

    pass


# Usage example:
# @feature_flag("new_dashboard")
# async def get_dashboard_data(user_id: str):
#     return {"data": "new dashboard"}
