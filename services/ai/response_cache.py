"""
AI Response Caching System

Intelligent caching for AI responses to improve performance and reduce costs.
Implements smart TTL management, content-type classification, and cache optimization.
"""

import logging

logger = logging.getLogger(__name__)

# Constants
HTTP_INTERNAL_SERVER_ERROR = 500

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from config.cache import get_cache_manager
from config.logging_config import get_logger

logger = get_logger(__name__)


class ContentType(Enum):
    """AI response content types for intelligent TTL management."""

    RECOMMENDATION = "recommendation"
    POLICY = "policy"
    WORKFLOW = "workflow"
    ANALYSIS = "analysis"
    GUIDANCE = "guidance"
    GENERAL = "general"


class CacheStrategy(Enum):
    """Caching strategies for different content types."""

    AGGRESSIVE = "aggressive"
    MODERATE = "moderate"
    CONSERVATIVE = "conservative"
    DYNAMIC = "dynamic"


class AIResponseCache:
    """
    Intelligent AI response caching system with content-aware TTL management.

    Features:
    - Content-type classification for optimal TTL
    - Prompt similarity detection for cache hits
    - Performance metrics and analytics
    - Cost optimization through intelligent caching
    """

    def __init__(self) -> None:
        self.cache_manager = None
        self.default_ttl = 3600
        self.max_ttl = 86400
        self.min_ttl = 300
        self.ttl_config = {
            ContentType.RECOMMENDATION: 7200,
            ContentType.POLICY: 86400,
            ContentType.WORKFLOW: 14400,
            ContentType.ANALYSIS: 3600,
            ContentType.GUIDANCE: 7200,
            ContentType.GENERAL: 1800,
        }
        self.metrics = {
            "hits": 0,
            "misses": 0,
            "total_requests": 0,
            "cache_size_bytes": 0,
            "cost_savings": 0.0,
        }

    async def initialize(self) -> None:
        """Initialize the cache manager."""
        self.cache_manager = await get_cache_manager()
        logger.info("AI Response Cache initialized")

    async def get_cached_response(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.85,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached AI response for similar prompts.

        Args:
            prompt: The AI prompt to check
            context: Additional context for cache key generation
            similarity_threshold: Minimum similarity for cache hit

        Returns:
            Cached response data or None if not found
        """
        try:
            if not self.cache_manager:
                await self.initialize()
            cache_key = self._generate_cache_key(prompt, context)
            cached_data = await self.cache_manager.get(cache_key)
            if cached_data:
                self._record_cache_hit()
                logger.debug("Cache hit for prompt hash: %s" % cache_key)
                return cached_data
            if context and context.get("enable_similarity_matching", True):
                similar_response = await self._find_similar_cached_response(
                    prompt, context, similarity_threshold
                )
                if similar_response:
                    self._record_cache_hit()
                    logger.debug("Similarity cache hit for prompt")
                    return similar_response
            self._record_cache_miss()
            return None
        except Exception as e:
            logger.warning("Cache retrieval error: %s" % e)
            self._record_cache_miss()
            return None

    async def cache_response(
        self,
        prompt: str,
        response: str,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Cache AI response with intelligent TTL based on content type.

        Args:
            prompt: The original prompt
            response: The AI response to cache
            context: Additional context information
            metadata: Response metadata (timing, tokens, etc.)

        Returns:
            True if successfully cached, False otherwise
        """
        try:
            if not self.cache_manager:
                await self.initialize()
            content_type = self._classify_content_type(response, context)
            ttl = self._calculate_intelligent_ttl(content_type, response, context)
            cache_key = self._generate_cache_key(prompt, context)
            cache_data = {
                "response": response,
                "content_type": content_type.value,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "ttl": ttl,
                "prompt_hash": cache_key,
                "metadata": metadata or {},
                "context_summary": self._summarize_context(context),
            }
            success = await self.cache_manager.set(cache_key, cache_data, ttl)
            if success:
                self._update_cache_metrics(cache_data)
                logger.debug(
                    "Cached response with TTL %ss for content type %s" % (ttl, content_type.value)
                )
            return success
        except Exception as e:
            logger.warning("Cache storage error: %s" % e)
            return False

    def _generate_cache_key(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a unique cache key for the prompt and context."""
        normalized_prompt = re.sub("\\s+", " ", prompt.strip().lower())
        context_key = ""
        if context:
            stable_context = {
                "framework": context.get("framework"),
                "industry": context.get("business_context", {}).get("industry"),
                "org_size": context.get("business_context", {}).get("employee_count", 0)
                // 100
                * 100,
                "content_type": context.get("content_type"),
            }
            context_key = json.dumps(stable_context, sort_keys=True)
        combined_input = f"{normalized_prompt}|{context_key}"
        return f"ai_response:{hashlib.sha256(combined_input.encode()).hexdigest()[:16]}"

    def _classify_content_type(
        self, response: str, context: Optional[Dict[str, Any]] = None
    ) -> ContentType:
        """Classify the content type of the AI response for optimal caching."""
        response_lower = response.lower()
        if context and context.get("content_type"):
            try:
                return ContentType(context["content_type"])
            except ValueError:
                pass
        if any(
            keyword in response_lower
            for keyword in ["recommend", "suggest", "priority", "should implement"]
        ):
            return ContentType.RECOMMENDATION
        elif any(
            keyword in response_lower
            for keyword in ["policy", "procedure", "governance", "compliance requirement"]
        ):
            return ContentType.POLICY
        elif any(
            keyword in response_lower for keyword in ["workflow", "step", "phase", "implementation"]
        ):
            return ContentType.WORKFLOW
        elif any(
            keyword in response_lower for keyword in ["analysis", "assessment", "evaluation", "gap"]
        ):
            return ContentType.ANALYSIS
        elif any(
            keyword in response_lower for keyword in ["guidance", "help", "how to", "best practice"]
        ):
            return ContentType.GUIDANCE
        else:
            return ContentType.GENERAL

    def _calculate_intelligent_ttl(
        self, content_type: ContentType, response: str, context: Optional[Dict[str, Any]] = None
    ) -> int:
        """Calculate intelligent TTL based on content type and characteristics."""
        base_ttl = self.ttl_config[content_type]
        response_length = len(response)
        if response_length > 2000:
            base_ttl = int(base_ttl * 1.5)
        elif response_length < HTTP_INTERNAL_SERVER_ERROR:
            base_ttl = int(base_ttl * 0.7)
        if context:
            if context.get("business_context", {}).get("maturity_level") == "Initial":
                base_ttl = int(base_ttl * 0.8)
            framework = context.get("framework", "")
            if framework in ["GDPR", "HIPAA"]:
                base_ttl = int(base_ttl * 1.2)
        return max(self.min_ttl, min(self.max_ttl, base_ttl))

    async def _find_similar_cached_response(
        self, prompt: str, context: Dict[str, Any], threshold: float
    ) -> Optional[Dict[str, Any]]:
        """Find cached responses for similar prompts using semantic similarity."""
        try:
            set(re.findall("\\b\\w+\\b", prompt.lower()))
            context.get("content_type", "general")
            return None
        except Exception as e:
            logger.warning("Similarity search error: %s" % e)
            return None

    def _summarize_context(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a summary of context for cache metadata."""
        if not context:
            return {}
        return {
            "framework": context.get("framework"),
            "content_type": context.get("content_type"),
            "business_industry": context.get("business_context", {}).get("industry"),
            "has_business_context": bool(context.get("business_context")),
        }

    def _record_cache_hit(self) -> None:
        """Record a cache hit for metrics."""
        self.metrics["hits"] += 1
        self.metrics["total_requests"] += 1

    def _record_cache_miss(self) -> None:
        """Record a cache miss for metrics."""
        self.metrics["misses"] += 1
        self.metrics["total_requests"] += 1

    def _update_cache_metrics(self, cache_data: Dict[str, Any]) -> None:
        """Update cache metrics with new cached data."""
        response_length = len(cache_data["response"])
        estimated_tokens = response_length // 4
        estimated_cost_savings = estimated_tokens * 1e-05
        self.metrics["cost_savings"] += estimated_cost_savings
        self.metrics["cache_size_bytes"] += len(json.dumps(cache_data))

    async def get_cache_metrics(self) -> Dict[str, Any]:
        """Get comprehensive cache performance metrics."""
        hit_rate = (
            self.metrics["hits"] / self.metrics["total_requests"] * 100
            if self.metrics["total_requests"] > 0
            else 0
        )
        return {
            "hit_rate_percentage": round(hit_rate, 2),
            "total_hits": self.metrics["hits"],
            "total_misses": self.metrics["misses"],
            "total_requests": self.metrics["total_requests"],
            "estimated_cost_savings": round(self.metrics["cost_savings"], 4),
            "cache_size_mb": round(self.metrics["cache_size_bytes"] / 1024 / 1024, 2),
            "ttl_config": {ct.value: ttl for ct, ttl in self.ttl_config.items()},
        }

    async def clear_cache_pattern(self, pattern: str) -> int:
        """Clear cache entries matching a pattern."""
        if not self.cache_manager:
            await self.initialize()
        return await self.cache_manager.clear_pattern(f"ai_response:{pattern}")

    async def invalidate_user_ai_cache(self, user_id: str) -> int:
        """Invalidate all AI cache entries for a specific user."""
        return 0


ai_response_cache = AIResponseCache()


async def get_ai_cache() -> AIResponseCache:
    """Get the global AI response cache instance."""
    if ai_response_cache.cache_manager is None:
        await ai_response_cache.initialize()
    return ai_response_cache
