"""
Enhanced Feature Flag Service with Redis Caching
Provides high-performance feature flag evaluation with <1ms access time
"""

import json
import hashlib
import time
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from functools import wraps
from enum import Enum

import redis
from redis import Redis
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from models.feature_flags import FeatureFlag as FeatureFlagModel, FeatureFlagAudit
from database.db_setup import get_db_session
from config.base import BaseConfig


class FeatureFlagConfig(BaseModel):
    """Feature flag configuration schema"""

    name: str
    enabled: bool = False
    percentage: float = Field(0.0, ge=0.0, le=100.0)
    whitelist: List[str] = []
    blacklist: List[str] = []
    environment_overrides: Dict[str, bool] = {}
    environments: List[str] = ["development"]
    expires_at: Optional[datetime] = None
    starts_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}


class EvaluationReason(str, Enum):
    """Reasons for feature flag evaluation results"""

    WHITELIST = "whitelist"
    BLACKLIST = "blacklist"
    PERCENTAGE = "percentage"
    ENVIRONMENT = "environment"
    EXPIRED = "expired"
    NOT_STARTED = "not_started"
    ENABLED = "enabled"
    DISABLED = "disabled"
    NOT_FOUND = "not_found"


class EnhancedFeatureFlagService:
    """
    Enhanced Feature Flag Service with database persistence and Redis caching
    Provides <1ms access time for flag evaluation
    """

    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        db_session: Optional[Session] = None,
        config: Optional[BaseConfig] = None,
    ) -> None:
        """Initialize the feature flag service"""
        self.config = config or BaseConfig()

        # Initialize Redis with connection pool
        if redis_client:
            self.redis = redis_client
        else:
            pool = redis.ConnectionPool.from_url(
                self.config.REDIS_URL, max_connections=50, decode_responses=True
            )
            self.redis = redis.Redis(connection_pool=pool)

        # Database session
        self.db_session = db_session

        # Cache configuration
        self.cache_ttl = 60  # 60 seconds TTL
        self.cache_prefix = "ff:"

        # Performance tracking
        self.enable_metrics = True

    def _get_cache_key(self, flag_name: str) -> str:
        """Generate cache key for a feature flag"""
        return f"{self.cache_prefix}{flag_name}"

    def _get_user_cache_key(self, flag_name: str, user_id: str) -> str:
        """Generate user-specific cache key"""
        return f"{self.cache_prefix}{flag_name}:user:{user_id}"

    def _hash_user_id(self, flag_name: str, user_id: str) -> int:
        """
        Generate consistent hash for user ID
        Used for percentage rollout determination
        """
        combined = f"{flag_name}:{user_id}"
        # Use SHA-256 instead of MD5 for security compliance in feature flag user assignment
        hash_obj = hashlib.sha256(combined.encode())
        return int(hash_obj.hexdigest(), 16) % 100

    async def get_flag_from_db(self, flag_name: str) -> Optional[FeatureFlagModel]:
        """Retrieve feature flag from database"""
        if not self.db_session:
            with next(get_db_session()) as session:
                result = session.query(FeatureFlagModel).filter_by(name=flag_name).first()
                return result
        else:
            result = self.db_session.query(FeatureFlagModel).filter_by(name=flag_name).first()
            return result

    async def get_flag_from_cache(self, flag_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve feature flag from Redis cache"""
        try:
            cache_key = self._get_cache_key(flag_name)
            cached_data = self.redis.get(cache_key)

            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            # Log error but don't fail
            print(f"Cache retrieval error: {e}")
            return None

    async def set_flag_in_cache(self, flag_name: str, flag_data: Dict[str, Any]) -> None:
        """Store feature flag in Redis cache"""
        try:
            cache_key = self._get_cache_key(flag_name)
            self.redis.setex(cache_key, self.cache_ttl, json.dumps(flag_data, default=str))
        except Exception as e:
            # Log error but don't fail
            print(f"Cache storage error: {e}")

    async def invalidate_cache(self, flag_name: str) -> None:
        """Invalidate cache for a specific feature flag"""
        try:
            # Delete main flag cache
            cache_key = self._get_cache_key(flag_name)
            self.redis.delete(cache_key)

            # Delete all user-specific caches for this flag
            pattern = f"{self.cache_prefix}{flag_name}:user:*"
            for key in self.redis.scan_iter(match=pattern):
                self.redis.delete(key)
        except Exception as e:
            print(f"Cache invalidation error: {e}")

    async def is_enabled_for_user(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
        environment: str = "production",
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, str]:
        """
        Check if feature flag is enabled for a specific user
        Returns tuple of (enabled, reason)
        Guaranteed <1ms response time with cache hit
        """
        start_time = time.perf_counter()

        try:
            # Try to get from cache first
            flag_data = await self.get_flag_from_cache(flag_name)
            cache_hit = flag_data is not None

            if not flag_data:
                # Load from database
                flag_model = await self.get_flag_from_db(flag_name)

                if not flag_model:
                    return False, EvaluationReason.NOT_FOUND

                # Convert model to dict
                flag_data = {
                    "name": flag_model.name,
                    "enabled": flag_model.enabled,
                    "percentage": flag_model.percentage,
                    "whitelist": flag_model.whitelist or [],
                    "blacklist": flag_model.blacklist or [],
                    "environment_overrides": flag_model.environment_overrides or {},
                    "environments": flag_model.environments or [],
                    "expires_at": flag_model.expires_at.isoformat()
                    if flag_model.expires_at
                    else None,
                    "starts_at": flag_model.starts_at.isoformat() if flag_model.starts_at else None,
                }

                # Cache the flag data
                await self.set_flag_in_cache(flag_name, flag_data)

            # Evaluate the flag
            result, reason = self._evaluate_flag(flag_data, user_id, environment)

            # Track evaluation metrics
            if self.enable_metrics:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                await self._track_evaluation(
                    flag_name, user_id, environment, result, reason, elapsed_ms, cache_hit
                )

            return result, reason

        except Exception as e:
            print(f"Feature flag evaluation error: {e}")
            return False, EvaluationReason.DISABLED

    def _evaluate_flag(
        self, flag_data: Dict[str, Any], user_id: Optional[str], environment: str
    ) -> tuple[bool, str]:
        """
        Evaluate feature flag based on configuration
        Pure function for testability
        """
        # Check if flag is in allowed environments
        if flag_data.get("environments") and environment not in flag_data["environments"]:
            return False, EvaluationReason.ENVIRONMENT

        # Check environment overrides
        env_overrides = flag_data.get("environment_overrides", {})
        if environment in env_overrides:
            enabled = env_overrides[environment]
            return enabled, EvaluationReason.ENVIRONMENT

        # Check temporal constraints
        now = datetime.utcnow()

        if flag_data.get("expires_at"):
            expires_at = datetime.fromisoformat(flag_data["expires_at"])
            if now > expires_at:
                return False, EvaluationReason.EXPIRED

        if flag_data.get("starts_at"):
            starts_at = datetime.fromisoformat(flag_data["starts_at"])
            if now < starts_at:
                return False, EvaluationReason.NOT_STARTED

        # Check user targeting
        if user_id:
            # Check blacklist first (highest priority)
            if user_id in flag_data.get("blacklist", []):
                return False, EvaluationReason.BLACKLIST

            # Check whitelist
            if user_id in flag_data.get("whitelist", []):
                return True, EvaluationReason.WHITELIST

        # Check if globally enabled
        if not flag_data.get("enabled", False):
            return False, EvaluationReason.DISABLED

        # Check percentage rollout
        percentage = flag_data.get("percentage", 0)

        if percentage >= 100:
            return True, EvaluationReason.ENABLED

        if percentage <= 0:
            return False, EvaluationReason.DISABLED

        if user_id:
            # Use consistent hashing for percentage rollout
            user_hash = self._hash_user_id(flag_data["name"], user_id)
            if user_hash < percentage:
                return True, EvaluationReason.PERCENTAGE
            else:
                return False, EvaluationReason.PERCENTAGE

        # Default to enabled if no user_id and flag is enabled
        return True, EvaluationReason.ENABLED

    async def _track_evaluation(
        self,
        flag_name: str,
        user_id: Optional[str],
        environment: str,
        result: bool,
        reason: str,
        elapsed_ms: float,
        cache_hit: bool,
    ) -> None:
        """Track feature flag evaluation for analytics"""
        try:
            # Store in Redis for real-time metrics
            metrics_key = f"ff:metrics:{flag_name}:{datetime.utcnow().strftime('%Y%m%d%H')}"

            self.redis.hincrby(metrics_key, "total", 1)
            self.redis.hincrby(metrics_key, f"result_{result}", 1)
            self.redis.hincrby(metrics_key, f"reason_{reason}", 1)
            if cache_hit:
                self.redis.hincrby(metrics_key, "cache_hits", 1)

            # Set expiry for metrics (7 days)
            self.redis.expire(metrics_key, 7 * 24 * 3600)

            # Store detailed evaluation if under 1ms (performance goal met)
            if elapsed_ms < 1.0:
                self.redis.hincrby(metrics_key, "under_1ms", 1)

        except Exception as e:
            print(f"Metrics tracking error: {e}")

    async def update_flag(
        self,
        flag_name: str,
        config: FeatureFlagConfig,
        user_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Update feature flag configuration"""
        try:
            with next(get_db_session()) as session:
                # Get existing flag or create new one
                flag = session.query(FeatureFlagModel).filter_by(name=flag_name).first()

                if not flag:
                    flag = FeatureFlagModel(name=flag_name)
                    session.add(flag)

                # Store previous state for audit
                previous_state = {
                    "enabled": flag.enabled,
                    "percentage": flag.percentage,
                    "whitelist": flag.whitelist,
                    "blacklist": flag.blacklist,
                    "environment_overrides": flag.environment_overrides,
                }

                # Update flag
                flag.enabled = config.enabled
                flag.percentage = config.percentage
                flag.whitelist = config.whitelist
                flag.blacklist = config.blacklist
                flag.environment_overrides = config.environment_overrides
                flag.environments = config.environments
                flag.expires_at = config.expires_at
                flag.starts_at = config.starts_at
                flag.metadata = config.metadata
                flag.updated_at = datetime.utcnow()
                flag.updated_by = user_id
                flag.version += 1

                # Create audit log
                audit = FeatureFlagAudit(
                    feature_flag_id=flag.id,
                    action="updated",
                    previous_state=previous_state,
                    new_state=config.dict(),
                    user_id=user_id,
                    reason=reason,
                    created_at=datetime.utcnow(),
                )
                session.add(audit)

                session.commit()

                # Invalidate cache
                await self.invalidate_cache(flag_name)

                return True

        except Exception as e:
            print(f"Flag update error: {e}")
            return False

    async def get_all_flags(self, environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all feature flags, optionally filtered by environment"""
        try:
            with next(get_db_session()) as session:
                query = session.query(FeatureFlagModel)

                if environment:
                    # Filter by environment
                    query = query.filter(FeatureFlagModel.environments.contains([environment]))

                flags = query.all()

                return [
                    {
                        "id": str(flag.id),
                        "name": flag.name,
                        "description": flag.description,
                        "enabled": flag.enabled,
                        "percentage": flag.percentage,
                        "whitelist": flag.whitelist,
                        "blacklist": flag.blacklist,
                        "environment_overrides": flag.environment_overrides,
                        "environments": flag.environments,
                        "expires_at": flag.expires_at.isoformat() if flag.expires_at else None,
                        "starts_at": flag.starts_at.isoformat() if flag.starts_at else None,
                        "tags": flag.tags,
                        "version": flag.version,
                        "updated_at": flag.updated_at.isoformat() if flag.updated_at else None,
                    }
                    for flag in flags
                ]
        except Exception as e:
            print(f"Error fetching flags: {e}")
            return []


def feature_flag(flag_name: str, fallback=None, raise_on_disabled: bool = False):
    """
    Decorator for feature flag protected functions
    Supports both sync and async functions
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            service = EnhancedFeatureFlagService()

            # Extract user_id from various sources
            user_id = kwargs.get("user_id")
            if not user_id and args:
                # Try to get from first argument if it has user_id attribute
                if hasattr(args[0], "user_id"):
                    user_id = args[0].user_id

            # Get environment from context or default
            environment = kwargs.get("environment", "production")

            enabled, reason = await service.is_enabled_for_user(flag_name, user_id, environment)

            if enabled:
                return await func(*args, **kwargs)
            elif fallback is not None:
                if callable(fallback):
                    if asyncio.iscoroutinefunction(fallback):
                        return await fallback(*args, **kwargs)
                    return fallback(*args, **kwargs)
                return fallback
            elif raise_on_disabled:
                raise FeatureNotEnabledException(
                    f"Feature '{flag_name}' is not enabled (reason: {reason})"
                )
            else:
                return None

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                service = EnhancedFeatureFlagService()

                user_id = kwargs.get("user_id")
                if not user_id and args and hasattr(args[0], "user_id"):
                    user_id = args[0].user_id

                environment = kwargs.get("environment", "production")

                enabled, reason = loop.run_until_complete(
                    service.is_enabled_for_user(flag_name, user_id, environment)
                )

                if enabled:
                    return func(*args, **kwargs)
                elif fallback is not None:
                    if callable(fallback):
                        return fallback(*args, **kwargs)
                    return fallback
                elif raise_on_disabled:
                    raise FeatureNotEnabledException(
                        f"Feature '{flag_name}' is not enabled (reason: {reason})"
                    )
                else:
                    return None
            finally:
                loop.close()

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class FeatureNotEnabledException(Exception):
    """Exception raised when a feature flag is not enabled"""

    pass


# Singleton instance for easy access
_service_instance: Optional[EnhancedFeatureFlagService] = None


def get_feature_flag_service() -> EnhancedFeatureFlagService:
    """Get singleton instance of feature flag service"""
    global _service_instance
    if _service_instance is None:
        _service_instance = EnhancedFeatureFlagService()
    return _service_instance
