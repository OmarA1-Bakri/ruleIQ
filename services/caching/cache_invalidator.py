"""Cache Invalidation module for intelligent cache management."""

from typing import List, Optional, Set, Pattern
import re
import logging
from .cache_manager import CacheManager
from .cache_keys import CacheKeyBuilder

logger = logging.getLogger(__name__)


class CacheInvalidator:
    """
    Intelligent cache invalidation for the RuleIQ caching system.

    Provides pattern-based, tag-based, and entity-based cache invalidation
    to ensure data consistency across the application.
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None) -> None:
        """
        Initialize the CacheInvalidator.

        Args:
            cache_manager: Optional CacheManager instance. If not provided,
                          a new instance will be created.
        """
        self.cache_manager = cache_manager or CacheManager()
        self._invalidation_patterns: Set[Pattern] = set()
        self._tag_mappings: dict = {}

    async def invalidate_by_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.

        Args:
            pattern: Regex pattern to match cache keys

        Returns:
            Number of cache entries invalidated
        """
        # Ensure cache manager is initialized
        if not self.cache_manager._initialized:
            await self.cache_manager.initialize()

        try:
            # Compile the pattern for efficient matching
            regex = re.compile(pattern)
            self._invalidation_patterns.add(regex)

            # Delegate to cache_manager's invalidate_pattern method
            invalidated_count = await self.cache_manager.invalidate_pattern(pattern)

            logger.info(
                f"Invalidated {invalidated_count} cache entries matching pattern: {pattern}"
            )

            return invalidated_count

        except re.error as e:
            logger.error(f"Invalid regex pattern {pattern}: {e}")
            raise ValueError(f"Invalid regex pattern: {pattern}") from e

    async def invalidate_by_tags(self, tags: List[str]) -> int:
        """
        Invalidate cache entries associated with specific tags.

        Args:
            tags: List of tags to invalidate

        Returns:
            Number of cache entries invalidated
        """
        # Ensure cache manager is initialized
        if not self.cache_manager._initialized:
            await self.cache_manager.initialize()

        invalidated_count = 0

        for tag in tags:
            if tag in self._tag_mappings:
                keys = self._tag_mappings[tag]
                for key in keys:
                    try:
                        await self.cache_manager.delete(key)
                        invalidated_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to invalidate key {key}: {e}")

                # Clear the tag mapping
                del self._tag_mappings[tag]

        logger.info(f"Invalidated {invalidated_count} cache entries for tags: {tags}")
        return invalidated_count

    async def invalidate_related(self, entity_type: str, entity_id: str) -> int:
        """
        Invalidate cache entries related to a specific entity.

        Args:
            entity_type: Type of entity (e.g., 'user', 'assessment', 'company')
            entity_id: Unique identifier of the entity

        Returns:
            Number of cache entries invalidated
        """
        # Build pattern for related cache entries
        base_key = f"{entity_type}:{entity_id}"

        # Invalidate direct entity cache
        primary_key = CacheKeyBuilder.build_namespaced_key(entity_type, entity_id)
        invalidated_count = 0

        try:
            await self.cache_manager.delete(primary_key)
            invalidated_count += 1
        except Exception as e:
            logger.debug(f"No primary cache entry for {primary_key}: {e}")

        # Invalidate related entries using pattern matching
        related_pattern = f"{base_key}:.*"
        invalidated_count += await self.invalidate_by_pattern(related_pattern)

        logger.info(f"Invalidated {invalidated_count} cache entries for {entity_type}:{entity_id}")
        return invalidated_count

    def register_tag(self, key: str, tags: List[str]) -> None:
        """
        Register cache key with tags for tag-based invalidation.

        Args:
            key: Cache key to register
            tags: Tags to associate with the key
        """
        for tag in tags:
            if tag not in self._tag_mappings:
                self._tag_mappings[tag] = set()
            self._tag_mappings[tag].add(key)

    def clear_all(self) -> None:
        """Clear all cache entries and reset invalidation state."""
        try:
            # Clear all cache entries
            logger.warning("Clearing all cache entries")
            self._invalidation_patterns.clear()
            self._tag_mappings.clear()
            # Note: Actual cache clearing would be implemented via cache_manager
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            raise
