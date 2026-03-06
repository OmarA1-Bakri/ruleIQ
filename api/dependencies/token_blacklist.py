"""
import logging


logger = logging.getLogger(__name__)
Enhanced Redis-based token blacklist implementation with security features.

This module provides comprehensive token blacklisting capabilities including:
- Distributed Redis-based token storage
- Automatic cleanup and TTL management
- Security metrics and monitoring
- Token pattern analysis for threat detection
- Bulk operations for administrative use
"""

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from config.cache import get_cache_manager
from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()
BLACKLIST_PREFIX = "blacklist"
BLACKLIST_METRICS_KEY = "blacklist:metrics"
BLACKLIST_SUSPICIOUS_PATTERNS_KEY = "blacklist:suspicious_patterns"
DEFAULT_TOKEN_TTL = 3600 * 24 * 7


@dataclass
class BlacklistEntry:
    """Represents a blacklisted token entry."""

    token_hash: str
    reason: str
    blacklisted_at: datetime
    expires_at: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class BlacklistMetrics:
    """Metrics for token blacklist operations."""

    total_blacklisted: int = 0
    blacklisted_today: int = 0
    expired_tokens_cleaned: int = 0
    suspicious_patterns_detected: int = 0
    bulk_operations_count: int = 0
    last_cleanup: Optional[datetime] = None


class EnhancedTokenBlacklist:
    """Enhanced Redis-based token blacklist with security features."""

    def __init__(self) -> None:
        self.cache_manager = None
        self.metrics = BlacklistMetrics()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the blacklist manager."""
        if self._initialized:
            return
        self.cache_manager = await get_cache_manager()
        await self._load_metrics()
        self._initialized = True
        logger.info("Enhanced token blacklist initialized")

    async def _ensure_initialized(self) -> None:
        """Ensure the blacklist manager is initialized."""
        if not self._initialized:
            await self.initialize()

    def _generate_token_hash(self, token: str) -> str:
        """Generate a secure hash of the token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _generate_cache_key(self, token_hash: str) -> str:
        """Generate cache key for token."""
        return f"{BLACKLIST_PREFIX}:{token_hash}"

    async def blacklist_token(
        self,
        token: str,
        reason: str = "logout",
        ttl: Optional[int] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Add a token to the blacklist with comprehensive metadata.

        Args:
            token: The JWT token to blacklist
            reason: Reason for blacklisting (logout, security_breach, etc.)
            ttl: Time to live in seconds (default: 7 days)
            user_id: User ID associated with the token
            session_id: Session ID associated with the token
            ip_address: IP address of the request
            user_agent: User agent of the request
            metadata: Additional metadata

        Returns:
            bool: True if successfully blacklisted
        """
        await self._ensure_initialized()
        try:
            token_hash = self._generate_token_hash(token)
            cache_key = self._generate_cache_key(token_hash)
            if ttl is None:
                ttl = DEFAULT_TOKEN_TTL
            entry = BlacklistEntry(
                token_hash=token_hash,
                reason=reason,
                blacklisted_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata,
            )
            entry_data = {
                **asdict(entry),
                "blacklisted_at": entry.blacklisted_at.isoformat(),
                "expires_at": entry.expires_at.isoformat(),
            }
            await self.cache_manager.set(cache_key, json.dumps(entry_data), ttl=ttl)
            await self._update_metrics("blacklisted")
            await self._analyze_blacklist_patterns(entry)
            logger.info(
                "Token blacklisted: hash=%s..., reason=%s, user_id=%s"
                % (token_hash[:8], reason, user_id)
            )
            return True
        except Exception as e:
            logger.error("Failed to blacklist token: %s" % e)
            return False

    async def is_token_blacklisted(self, token: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token: The JWT token to check

        Returns:
            bool: True if token is blacklisted
        """
        await self._ensure_initialized()
        try:
            token_hash = self._generate_token_hash(token)
            cache_key = self._generate_cache_key(token_hash)
            entry_data = await self.cache_manager.get(cache_key)
            return entry_data is not None
        except Exception as e:
            logger.error("Failed to check token blacklist status: %s" % e)
            return False

    async def get_blacklist_entry(self, token: str) -> Optional[BlacklistEntry]:
        """
        Get detailed blacklist entry for a token.

        Args:
            token: The JWT token to check

        Returns:
            BlacklistEntry if found, None otherwise
        """
        await self._ensure_initialized()
        try:
            token_hash = self._generate_token_hash(token)
            cache_key = self._generate_cache_key(token_hash)
            entry_data = await self.cache_manager.get(cache_key)
            if not entry_data:
                return None
            data = json.loads(entry_data)
            data["blacklisted_at"] = datetime.fromisoformat(data["blacklisted_at"])
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
            return BlacklistEntry(**data)
        except Exception as e:
            logger.error("Failed to get blacklist entry: %s" % e)
            return None

    async def remove_token_from_blacklist(self, token: str) -> bool:
        """
        Remove a token from the blacklist (administrative use).

        Args:
            token: The JWT token to remove

        Returns:
            bool: True if successfully removed
        """
        await self._ensure_initialized()
        try:
            token_hash = self._generate_token_hash(token)
            cache_key = self._generate_cache_key(token_hash)
            result = await self.cache_manager.delete(cache_key)
            if result:
                logger.info("Token removed from blacklist: hash=%s..." % token_hash[:8])
            return result
        except Exception as e:
            logger.error("Failed to remove token from blacklist: %s" % e)
            return False

    async def blacklist_user_tokens(
        self,
        user_id: str,
        reason: str = "security_action",
        exclude_current_token: Optional[str] = None,
    ) -> int:
        """
        Blacklist all tokens for a specific user (security action).

        Args:
            user_id: User ID whose tokens should be blacklisted
            reason: Reason for mass blacklisting
            exclude_current_token: Token to exclude from blacklisting (optional)

        Returns:
            int: Number of tokens blacklisted
        """
        await self._ensure_initialized()
        try:
            logger.warning(
                "Mass token blacklist requested for user %s - requires token registry implementation"
                % user_id
            )
            await self._update_metrics("bulk_operation")
            return 0
        except Exception as e:
            logger.error("Failed to blacklist user tokens: %s" % e)
            return 0

    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens from the blacklist.

        Returns:
            int: Number of tokens cleaned up
        """
        await self._ensure_initialized()
        try:
            pattern = f"{BLACKLIST_PREFIX}:*"
            cleaned_count = 0
            keys = await self.cache_manager.redis_client.keys(pattern)
            for key in keys:
                entry_data = await self.cache_manager.get(key)
                if entry_data:
                    data = json.loads(entry_data)
                    expires_at = datetime.fromisoformat(data["expires_at"])
                    if expires_at < datetime.now(timezone.utc):
                        await self.cache_manager.delete(key)
                        cleaned_count += 1
            await self._update_metrics("cleanup", cleaned_count)
            logger.info("Cleaned up %s expired tokens" % cleaned_count)
            return cleaned_count
        except Exception as e:
            logger.error("Failed to cleanup expired tokens: %s" % e)
            return 0

    async def get_blacklist_statistics(self) -> Dict:
        """
        Get comprehensive blacklist statistics.

        Returns:
            Dict: Statistics about the blacklist
        """
        await self._ensure_initialized()
        try:
            pattern = f"{BLACKLIST_PREFIX}:*"
            current_count = len(await self.cache_manager.redis_client.keys(pattern))
            return {
                "current_blacklisted_tokens": current_count,
                "total_blacklisted": self.metrics.total_blacklisted,
                "blacklisted_today": self.metrics.blacklisted_today,
                "expired_tokens_cleaned": self.metrics.expired_tokens_cleaned,
                "suspicious_patterns_detected": self.metrics.suspicious_patterns_detected,
                "bulk_operations_count": self.metrics.bulk_operations_count,
                "last_cleanup": self.metrics.last_cleanup.isoformat()
                if self.metrics.last_cleanup
                else None,
            }
        except Exception as e:
            logger.error("Failed to get blacklist statistics: %s" % e)
            return {}

    async def _update_metrics(self, operation: str, count: int = 1) -> None:
        """Update blacklist metrics."""
        try:
            if operation == "blacklisted":
                self.metrics.total_blacklisted += count
                self.metrics.blacklisted_today += count
            elif operation == "cleanup":
                self.metrics.expired_tokens_cleaned += count
                self.metrics.last_cleanup = datetime.now(timezone.utc)
            elif operation == "suspicious_pattern":
                self.metrics.suspicious_patterns_detected += count
            elif operation == "bulk_operation":
                self.metrics.bulk_operations_count += count
            await self._save_metrics()
        except Exception as e:
            logger.error("Failed to update metrics: %s" % e)

    async def _save_metrics(self) -> None:
        """Save metrics to Redis."""
        try:
            metrics_data = {
                **asdict(self.metrics),
                "last_cleanup": self.metrics.last_cleanup.isoformat()
                if self.metrics.last_cleanup
                else None,
            }
            await self.cache_manager.set(BLACKLIST_METRICS_KEY, json.dumps(metrics_data), ttl=86400)
        except Exception as e:
            logger.error("Failed to save metrics: %s" % e)

    async def _load_metrics(self) -> None:
        """Load metrics from Redis."""
        try:
            metrics_data = await self.cache_manager.get(BLACKLIST_METRICS_KEY)
            if metrics_data:
                data = json.loads(metrics_data)
                if data.get("last_cleanup"):
                    data["last_cleanup"] = datetime.fromisoformat(data["last_cleanup"])
                self.metrics = BlacklistMetrics(**data)
        except Exception as e:
            logger.error("Failed to load metrics: %s" % e)
            self.metrics = BlacklistMetrics()

    async def _analyze_blacklist_patterns(self, entry: BlacklistEntry) -> None:
        """Analyze blacklist patterns for security threats."""
        try:
            if entry.ip_address and entry.user_id:
                recent_pattern_key = f"pattern:{entry.ip_address}:{entry.user_id}"
                count = await self.cache_manager.get(recent_pattern_key) or 0
                count = int(count) + 1
                if count > 10:
                    await self._update_metrics("suspicious_pattern")
                    logger.warning(
                        "Suspicious blacklist pattern detected: IP=                             %s, User=%s"
                        % (entry.ip_address, entry.user_id)
                    )
                await self.cache_manager.set(recent_pattern_key, str(count), ttl=3600)
        except Exception as e:
            logger.error("Failed to analyze blacklist patterns: %s" % e)


_token_blacklist = EnhancedTokenBlacklist()


async def get_token_blacklist() -> EnhancedTokenBlacklist:
    """Get the global token blacklist instance."""
    await _token_blacklist._ensure_initialized()
    return _token_blacklist


async def blacklist_token(
    token: str, reason: str = "logout", ttl: Optional[int] = None, **kwargs
) -> bool:
    """Backwards compatible blacklist token function."""
    blacklist = await get_token_blacklist()
    return await blacklist.blacklist_token(token, reason, ttl, **kwargs)


async def is_token_blacklisted(token: str) -> bool:
    """Backwards compatible token check function."""
    blacklist = await get_token_blacklist()
    return await blacklist.is_token_blacklisted(token)
