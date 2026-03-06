"""
Token Blacklist Service for JWT Invalidation

Story 1.1: JWT Validation - Task 3: Token Blacklisting
Provides Redis-based token blacklisting for logout and token invalidation.
"""

import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import redis
import logging
from contextlib import contextmanager

from config.settings import settings

logger = logging.getLogger(__name__)


class TokenBlacklistService:
    """
    Manages JWT token blacklisting using Redis for fast lookups.

    Features:
    - Add tokens to blacklist on logout
    - Check if token is blacklisted
    - Automatic expiry cleanup
    - Performance optimized with Redis sets
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None) -> None:
        """Initialize the token blacklist service."""
        self.redis_client = redis_client or self._get_redis_client()
        self.blacklist_prefix = "token_blacklist:"
        self.blacklist_set_key = "token_blacklist:active"
        self.stats_key = "token_blacklist:stats"

    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client with connection pooling."""
        pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            max_connections=50,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        return redis.Redis(connection_pool=pool, decode_responses=True)

    def add_to_blacklist(
        self,
        token_jti: str,
        expiry: datetime,
        user_id: Optional[str] = None,
        reason: str = "logout",
    ) -> bool:
        """
        Add a token to the blacklist.

        Args:
            token_jti: JWT ID (jti claim) to blacklist
            expiry: Token expiry time for auto-cleanup
            user_id: Optional user ID for audit trail
            reason: Reason for blacklisting

        Returns:
            True if successfully blacklisted
        """
        try:
            # Calculate TTL for automatic cleanup
            ttl = int((expiry - datetime.now(timezone.utc)).total_seconds())
            if ttl <= 0:
                logger.debug(f"Token {token_jti} already expired, not blacklisting")
                return True

            # Create blacklist entry
            blacklist_data = {
                "jti": token_jti,
                "blacklisted_at": datetime.now(timezone.utc).isoformat(),
                "expiry": expiry.isoformat(),
                "user_id": user_id,
                "reason": reason,
            }

            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()

            # Store blacklist entry with TTL
            entry_key = f"{self.blacklist_prefix}{token_jti}"
            pipe.setex(entry_key, ttl, json.dumps(blacklist_data))

            # Add to active set for fast lookups
            pipe.sadd(self.blacklist_set_key, token_jti)

            # Update statistics
            pipe.hincrby(self.stats_key, "total_blacklisted", 1)
            pipe.hincrby(self.stats_key, f"reason:{reason}", 1)

            # Execute pipeline
            results = pipe.execute()

            logger.info(f"Token {token_jti} blacklisted for user {user_id}, reason: {reason}")

            # Schedule cleanup of expired entry from set
            self._schedule_cleanup(token_jti, ttl)

            return all(results)

        except redis.RedisError as e:
            logger.error(f"Redis error blacklisting token {token_jti}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error blacklisting token {token_jti}: {e}")
            return False

    def is_blacklisted(self, token_jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token_jti: JWT ID to check

        Returns:
            True if token is blacklisted
        """
        try:
            # Fast check using set membership
            is_in_set = self.redis_client.sismember(self.blacklist_set_key, token_jti)

            if is_in_set:
                # Verify entry still exists (handle race conditions)
                entry_key = f"{self.blacklist_prefix}{token_jti}"
                if self.redis_client.exists(entry_key):
                    # Update hit counter
                    self.redis_client.hincrby(self.stats_key, "check_hits", 1)
                    return True
                else:
                    # Entry expired, remove from set
                    self.redis_client.srem(self.blacklist_set_key, token_jti)

            # Update miss counter
            self.redis_client.hincrby(self.stats_key, "check_misses", 1)
            return False

        except redis.RedisError as e:
            logger.error(f"Redis error checking blacklist for {token_jti}: {e}")
            # Fail open for availability (configurable)
            return (
                settings.BLACKLIST_FAIL_CLOSED
                if hasattr(settings, "BLACKLIST_FAIL_CLOSED")
                else False
            )
        except Exception as e:
            logger.error(f"Unexpected error checking blacklist for {token_jti}: {e}")
            return False

    def remove_from_blacklist(self, token_jti: str) -> bool:
        """
        Remove a token from the blacklist (admin action).

        Args:
            token_jti: JWT ID to remove

        Returns:
            True if successfully removed
        """
        try:
            pipe = self.redis_client.pipeline()

            # Remove entry
            entry_key = f"{self.blacklist_prefix}{token_jti}"
            pipe.delete(entry_key)

            # Remove from set
            pipe.srem(self.blacklist_set_key, token_jti)

            # Update stats
            pipe.hincrby(self.stats_key, "total_removed", 1)

            results = pipe.execute()

            if results[0] or results[1]:
                logger.info(f"Token {token_jti} removed from blacklist")
                return True
            return False

        except redis.RedisError as e:
            logger.error(f"Redis error removing {token_jti} from blacklist: {e}")
            return False

    def _schedule_cleanup(self, token_jti: str, ttl: int):
        """Schedule cleanup of expired token from set."""
        # This would integrate with APScheduler or Celery
        # For now, rely on lazy cleanup during checks
        pass

    def cleanup_expired(self) -> int:
        """
        Clean up expired entries from the active set.

        Returns:
            Number of entries cleaned up
        """
        try:
            cleaned = 0

            # Get all tokens in active set
            active_tokens = self.redis_client.smembers(self.blacklist_set_key)

            for token_jti in active_tokens:
                entry_key = f"{self.blacklist_prefix}{token_jti}"

                # Check if entry still exists
                if not self.redis_client.exists(entry_key):
                    # Entry expired, remove from set
                    self.redis_client.srem(self.blacklist_set_key, token_jti)
                    cleaned += 1

            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} expired tokens from blacklist")
                self.redis_client.hincrby(self.stats_key, "total_cleaned", cleaned)

            return cleaned

        except redis.RedisError as e:
            logger.error(f"Redis error during cleanup: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get blacklist statistics."""
        try:
            stats = self.redis_client.hgetall(self.stats_key)
            stats["active_count"] = self.redis_client.scard(self.blacklist_set_key)
            return {k: int(v) if isinstance(v, str) and v.isdigit() else v for k, v in stats.items()}
        except redis.RedisError:
            return {}

    def clear_all(self) -> bool:
        """Clear all blacklisted tokens (admin action)."""
        try:
            # Get all keys
            pattern = f"{self.blacklist_prefix}*"
            keys = list(self.redis_client.scan_iter(match=pattern))

            if keys:
                # Delete all blacklist entries
                self.redis_client.delete(*keys)

            # Clear the active set
            self.redis_client.delete(self.blacklist_set_key)

            # Reset stats
            self.redis_client.delete(self.stats_key)

            logger.warning("All blacklisted tokens cleared")
            return True

        except redis.RedisError as e:
            logger.error(f"Redis error clearing blacklist: {e}")
            return False


# Global instance for easy access
_blacklist_service: Optional[TokenBlacklistService] = None


def get_blacklist_service() -> TokenBlacklistService:
    """Get the global blacklist service instance."""
    global _blacklist_service
    if _blacklist_service is None:
        _blacklist_service = TokenBlacklistService()
    return _blacklist_service


@contextmanager
def blacklist_transaction():
    """Context manager for blacklist operations."""
    service = get_blacklist_service()
    try:
        yield service
    except Exception as e:
        logger.error(f"Blacklist transaction error: {e}")
        raise
