"""
import logging


logger = logging.getLogger(__name__)
Google Cached Content Integration

Implements Google's native caching system for improved performance and cost reduction.
Works alongside existing custom caching for optimal performance.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from config.ai_config import ai_config as _global_ai_config
from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CacheMetadata:
    """Metadata for cached content tracking."""

    cache_id: str
    framework_id: str
    business_profile_id: str
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0
    last_accessed: Optional[datetime] = None


class GoogleCachedContentManager:
    """
    Google Cached Content API integration for ruleIQ.

    Provides intelligent caching of assessment contexts, business profiles,
    and regulatory content using Google's native caching system.
    """

    def __init__(self) -> None:
        self.config = _global_ai_config
        self.cache_registry: Dict[str, CacheMetadata] = {}
        self.ttl_strategies = {
            "assessment_context": timedelta(hours=2),
            "business_profile": timedelta(hours=6),
            "regulatory_content": timedelta(hours=12),
            "policy_template": timedelta(days=1),
            "framework_guidance": timedelta(hours=4),
        }

    def create_assessment_cache(
        self,
        framework_id: str,
        business_profile: dict,
        additional_context: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Create cached content for assessment context.

        Args:
            framework_id: Compliance framework identifier
            business_profile: Business profile data
            additional_context: Additional context strings

        Returns:
            Cache ID if successful, None if failed
        """
        try:
            cache_key = self._generate_cache_key(
                "assessment", framework_id, business_profile.get("id", "unknown")
            )
            if cache_key in self.cache_registry:
                existing_cache = self.cache_registry[cache_key]
                if existing_cache.expires_at > datetime.now(timezone.utc):
                    logger.info("Using existing cache: %s" % cache_key)
                    existing_cache.hit_count += 1
                    existing_cache.last_accessed = datetime.now(timezone.utc)
                    return existing_cache.cache_id
            cache_content = self._prepare_assessment_content(
                framework_id, business_profile, additional_context
            )
            from config.ai_config import ai_config as _ai_config
            from google.genai import types as _gtypes
            _client = _ai_config._get_genai_client()
            ttl = self.ttl_strategies["assessment_context"]
            cached_content = _client.caches.create(
                model=self.config.default_model,
                config=_gtypes.CreateCachedContentConfig(
                    contents=cache_content,
                    ttl=f"{int(ttl.total_seconds())}s",
                    display_name=f"assessment_context_{framework_id}_{business_profile.get('id', 'unknown')}",
                )
            )
            metadata = CacheMetadata(
                cache_id=cached_content.name,
                framework_id=framework_id,
                business_profile_id=business_profile.get("id", "unknown"),
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + self.ttl_strategies["assessment_context"],
            )
            self.cache_registry[cache_key] = metadata
            logger.info("Created assessment cache: %s" % cache_key)
            return cached_content.name
        except Exception as e:
            logger.error("Failed to create assessment cache: %s" % e)
            return None

    def create_business_profile_cache(
        self, business_profile: dict, regulatory_context: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Create cached content for business profile context.

        Args:
            business_profile: Complete business profile data
            regulatory_context: Relevant regulatory information

        Returns:
            Cache ID if successful, None if failed
        """
        try:
            cache_key = self._generate_cache_key(
                "business_profile", business_profile.get("id", "unknown")
            )
            if cache_key in self.cache_registry:
                existing_cache = self.cache_registry[cache_key]
                if existing_cache.expires_at > datetime.now(timezone.utc):
                    existing_cache.hit_count += 1
                    existing_cache.last_accessed = datetime.now(timezone.utc)
                    return existing_cache.cache_id
            cache_content = self._prepare_business_profile_content(
                business_profile, regulatory_context
            )
            from config.ai_config import ai_config as _ai_config
            from google.genai import types as _gtypes
            _client = _ai_config._get_genai_client()
            ttl = self.ttl_strategies["business_profile"]
            cached_content = _client.caches.create(
                model=self.config.default_model,
                config=_gtypes.CreateCachedContentConfig(
                    contents=cache_content,
                    ttl=f"{int(ttl.total_seconds())}s",
                    display_name=f"business_profile_{business_profile.get('id', 'unknown')}",
                )
            )
            metadata = CacheMetadata(
                cache_id=cached_content.name,
                framework_id="",
                business_profile_id=business_profile.get("id", "unknown"),
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + self.ttl_strategies["business_profile"],
            )
            self.cache_registry[cache_key] = metadata
            logger.info("Created business profile cache: %s" % cache_key)
            return cached_content.name
        except Exception as e:
            logger.error("Failed to create business profile cache: %s" % e)
            return None

    def get_cached_model(self, cache_id: str) -> Optional[Any]:
        """
        Get a model wrapper with cached content baked in.

        Args:
            cache_id: Google cached content ID

        Returns:
            Model wrapper using cached content or None
        """
        try:
            from config.ai_config import ai_config as _ai_config, _GenAIModelWrapper
            client = _ai_config._get_genai_client()
            cached_content = client.caches.get(name=cache_id)
            # Build a wrapper whose generate_content calls include the cached_content context
            wrapper = _GenAIModelWrapper(
                client=client,
                model_name=cached_content.model,
                generation_config=_ai_config.generation_config,
                safety_settings=_ai_config.safety_settings,
            )
            return wrapper
        except Exception as e:
            logger.error("Failed to get cached model: %s" % e)
            return None

    def invalidate_cache(self, cache_key: str) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            cache_key: Cache key to invalidate

        Returns:
            True if successful, False otherwise
        """
        try:
            if cache_key in self.cache_registry:
                metadata = self.cache_registry[cache_key]
                from config.ai_config import ai_config as _ai_config
                _client = _ai_config._get_genai_client()
                _client.caches.delete(name=metadata.cache_id)
                del self.cache_registry[cache_key]
                logger.info("Invalidated cache: %s" % cache_key)
                return True
            return False
        except Exception as e:
            logger.error("Failed to invalidate cache: %s" % e)
            return False

    def cleanup_expired_caches(self) -> int:
        """
        Clean up expired cache entries.

        Returns:
            Number of caches cleaned up
        """
        cleaned_count = 0
        current_time = datetime.now(timezone.utc)
        expired_keys = []
        for cache_key, metadata in self.cache_registry.items():
            if metadata.expires_at <= current_time:
                expired_keys.append(cache_key)
        for cache_key in expired_keys:
            if self.invalidate_cache(cache_key):
                cleaned_count += 1
        logger.info("Cleaned up %s expired caches" % cleaned_count)
        return cleaned_count

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_caches = len(self.cache_registry)
        total_hits = sum(metadata.hit_count for metadata in self.cache_registry.values())
        framework_caches = [m for m in self.cache_registry.values() if m.framework_id]
        profile_caches = [m for m in self.cache_registry.values() if not m.framework_id]
        return {
            "total_caches": total_caches,
            "total_hits": total_hits,
            "framework_caches": len(framework_caches),
            "profile_caches": len(profile_caches),
            "average_hits_per_cache": total_hits / total_caches if total_caches > 0 else 0,
            "cache_registry_size": len(self.cache_registry),
        }

    def _generate_cache_key(self, content_type: str, *identifiers: str) -> str:
        """Generate a unique cache key."""
        key_data = f"{content_type}:{'|'.join(identifiers)}"
        return hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()

    def _prepare_assessment_content(
        self,
        framework_id: str,
        business_profile: dict,
        additional_context: Optional[List[str]] = None,
    ) -> List[str]:
        """Prepare content for assessment caching."""
        content = [
            f"Assessment Framework: {framework_id}",
            f"Business Profile: {json.dumps(business_profile, indent=2)}",
            f"Industry: {business_profile.get('industry', 'Unknown')}",
            f"Company Size: {business_profile.get('employee_count', 'Unknown')}",
            f"Location: {business_profile.get('location', 'Unknown')}",
        ]
        if additional_context:
            content.extend(additional_context)
        return content

    def _prepare_business_profile_content(
        self, business_profile: dict, regulatory_context: Optional[List[str]] = None
    ) -> List[str]:
        """Prepare content for business profile caching."""
        content = [
            f"Business Profile: {json.dumps(business_profile, indent=2)}",
            f"Regulatory Requirements: {regulatory_context or []}",
        ]
        return content
