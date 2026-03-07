"""Cache Warming module for preloading frequently accessed data."""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Set
from datetime import datetime
from .cache_manager import CacheManager
from .cache_keys import CacheKeyBuilder

logger = logging.getLogger(__name__)


class CacheWarmer:
    """
    Cache warming utility for preloading frequently accessed data.

    Provides scheduled and on-demand cache warming to improve performance
    by ensuring critical data is available in cache before requests arrive.
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None) -> None:
        """
        Initialize the CacheWarmer.

        Args:
            cache_manager: Optional CacheManager instance. If not provided,
                          a new instance will be created.
        """
        self.cache_manager = cache_manager or CacheManager()
        self._warming_tasks: Set[asyncio.Task] = set()
        self._is_warming = False

    async def warm_cache_keys(self, keys: List[str], data_fetchers: Dict[str, Callable]) -> int:
        """
        Warm specific cache keys with provided data fetchers.

        Args:
            keys: List of cache keys to warm
            data_fetchers: Dictionary mapping keys to async functions that fetch the data

        Returns:
            Number of successfully warmed cache entries
        """
        if not self.cache_manager._initialized:
            await self.cache_manager.initialize()

        warmed_count = 0
        self._is_warming = True

        try:
            for key in keys:
                if key not in data_fetchers:
                    logger.warning(f"No data fetcher provided for key: {key}")
                    continue

                try:
                    fetcher = data_fetchers[key]
                    data = await fetcher() if asyncio.iscoroutinefunction(fetcher) else fetcher()

                    if data is not None:
                        await self.cache_manager.set(key, data)
                        warmed_count += 1
                        logger.debug(f"Successfully warmed cache key: {key}")
                    else:
                        logger.warning(f"Data fetcher returned None for key: {key}")

                except Exception as e:
                    logger.error(f"Failed to warm cache key {key}: {e}")

        finally:
            self._is_warming = False

        logger.info(f"Warmed {warmed_count}/{len(keys)} cache entries")
        return warmed_count

    async def warm_by_pattern(self, pattern: str, data_fetcher: Callable[[str], Any]) -> int:
        """
        Warm cache entries matching a pattern.

        Args:
            pattern: Pattern to match cache keys (e.g., "user:*:profile")
            data_fetcher: Async function that takes a key and returns the data

        Returns:
            Number of successfully warmed cache entries
        """
        if not self.cache_manager._initialized:
            await self.cache_manager.initialize()

        warmed_count = 0
        self._is_warming = True

        try:
            # In a real implementation, this would scan Redis for matching keys
            # For now, we'll just log the intent
            logger.info(f"Warming cache entries matching pattern: {pattern}")

            # This is a placeholder - actual implementation would:
            # 1. Scan Redis for keys matching the pattern
            # 2. For each key, call the data_fetcher
            # 3. Store the result in cache

        finally:
            self._is_warming = False

        return warmed_count

    async def schedule_background_warming(
        self, warming_config: Dict[str, Any], interval_seconds: int = 300
    ) -> asyncio.Task:
        """
        Schedule periodic background cache warming.

        Args:
            warming_config: Configuration for what to warm
            interval_seconds: Interval between warming runs (default 5 minutes)

        Returns:
            Asyncio task handle for the background warming
        """

        async def _warming_loop():
            """Internal warming loop."""
            while True:
                try:
                    await asyncio.sleep(interval_seconds)

                    if self._is_warming:
                        logger.debug("Skipping warming run - already in progress")
                        continue

                    # Extract keys and fetchers from config
                    keys = warming_config.get("keys", [])
                    data_fetchers = warming_config.get("fetchers", {})

                    if keys and data_fetchers:
                        await self.warm_cache_keys(keys, data_fetchers)

                except asyncio.CancelledError:
                    logger.info("Background warming task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in background warming loop: {e}")

        task = asyncio.create_task(_warming_loop())
        self._warming_tasks.add(task)
        task.add_done_callback(self._warming_tasks.discard)

        logger.info(f"Scheduled background warming with {interval_seconds}s interval")
        return task

    async def warm_startup_cache(self, startup_keys: List[str]) -> int:
        """
        Warm critical cache entries during application startup.

        Args:
            startup_keys: List of cache keys critical for startup

        Returns:
            Number of successfully warmed entries
        """
        logger.info(f"Starting startup cache warming for {len(startup_keys)} keys")

        # For startup warming, we'll use simplified data fetchers
        # In a real implementation, these would be provided by the application
        data_fetchers = {key: lambda k=key: f"startup_data_for_{k}" for key in startup_keys}

        return await self.warm_cache_keys(startup_keys, data_fetchers)

    async def stop_warming(self) -> None:
        """Stop all background warming tasks."""
        for task in self._warming_tasks:
            task.cancel()

        if self._warming_tasks:
            await asyncio.gather(*self._warming_tasks, return_exceptions=True)

        self._warming_tasks.clear()
        logger.info("All warming tasks stopped")

    @property
    def is_warming(self) -> bool:
        """Check if cache warming is currently in progress."""
        return self._is_warming

    async def warm_user_cache(self, user_id: str) -> None:
        """
        Warm all user-related cache entries.

        Args:
            user_id: User ID to warm cache for
        """
        keys = [
            CacheKeyBuilder.build_user_key(user_id),
            CacheKeyBuilder.build_user_key(user_id, "profile"),
            CacheKeyBuilder.build_user_key(user_id, "settings"),
            CacheKeyBuilder.build_user_key(user_id, "permissions"),
        ]

        # Simplified data fetchers for demonstration
        data_fetchers = {
            key: lambda k=key: {
                "cached": True,
                "key": k,
                "timestamp": datetime.utcnow().isoformat(),
            }
            for key in keys
        }

        await self.warm_cache_keys(keys, data_fetchers)

    async def warm_business_cache(self, business_id: str) -> None:
        """
        Warm all business-related cache entries.

        Args:
            business_id: Business ID to warm cache for
        """
        keys = [
            CacheKeyBuilder.build_business_key(business_id),
            CacheKeyBuilder.build_business_key(business_id, "profile"),
            CacheKeyBuilder.build_business_key(business_id, "assessments"),
            CacheKeyBuilder.build_business_key(business_id, "compliance"),
        ]

        # Simplified data fetchers for demonstration
        data_fetchers = {
            key: lambda k=key: {
                "cached": True,
                "key": k,
                "timestamp": datetime.utcnow().isoformat(),
            }
            for key in keys
        }

        await self.warm_cache_keys(keys, data_fetchers)
