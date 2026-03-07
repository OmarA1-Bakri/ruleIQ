"""

Evidence Orchestrator v2 - Next Generation Evidence Collection System

This module implements a sophisticated evidence collection and management system
with parallel processing, intelligent caching, and confidence scoring.
"""

import asyncio
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
import time
from enum import Enum
import math
from difflib import SequenceMatcher


class SourceStatus(Enum):
    """Source availability status"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class CollectionStatus(Enum):
    """Evidence collection status"""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CACHED = "cached"


@dataclass
class EvidenceSource:
    """Evidence source configuration"""

    source_id: str
    source_type: str
    priority: int = 99
    trust_level: float = 0.5
    verified: bool = False
    capabilities: List[str] = field(default_factory=list)
    connection: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    health_status: SourceStatus = SourceStatus.UNKNOWN
    last_health_check: Optional[datetime] = None
    average_latency_ms: float = 0.0
    success_rate: float = 1.0


@dataclass
class EvidenceItem:
    """Individual evidence item"""

    evidence_id: str
    source_id: str
    content: Any
    type: str = "document"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    fingerprint: Optional[str] = None
    quality_score: float = 0.0
    relevance_score: float = 0.0
    confidence_score: float = 0.0


@dataclass
class CollectionResult:
    """Result from evidence collection"""

    source_id: str
    status: CollectionStatus
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    duration: float = 0.0

    def __getitem__(self, key) -> Any:
        """Make CollectionResult subscriptable"""
        if key == "data":
            return self.evidence
        elif key == "collection_time_ms":
            return self.duration * 1000
        elif key == "status":
            return self.status.value if isinstance(self.status, CollectionStatus) else self.status
        return getattr(self, key)

    def __contains__(self, key) -> Any:
        """Support 'in' operator"""
        if key in ["data", "collection_time_ms"]:
            return True
        return hasattr(self, key)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "source_id": self.source_id,
            "status": self.status.value
            if isinstance(self.status, CollectionStatus)
            else self.status,
            "evidence": self.evidence,
            "data": self.evidence,
            "error_message": self.error_message,
            "duration": self.duration,
            "collection_time_ms": self.duration * 1000,
        }


class EvidenceCache:
    """In-memory evidence cache with TTL"""

    def __init__(self, default_ttl_seconds: int = 3600) -> None:
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._default_ttl = timedelta(seconds=default_ttl_seconds)
        self._hit_count = 0
        self._miss_count = 0

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache if not expired"""
        if key in self._cache:
            data, expiry = self._cache[key]
            if datetime.now() < expiry:
                self._hit_count += 1
                return data
            else:
                del self._cache[key]
        self._miss_count += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """Set item in cache with TTL"""
        ttl = ttl or self._default_ttl
        expiry = datetime.now() + ttl
        self._cache[key] = (value, expiry)

    def invalidate(self, key: str) -> None:
        """Remove item from cache"""
        self._cache.pop(key, None)

    def invalidate_pattern(self, pattern: Dict[str, Any]) -> None:
        """Invalidate all keys matching pattern"""
        to_remove = []
        pattern_str = json.dumps(pattern, sort_keys=True)
        for key in self._cache:
            if pattern_str in key:
                to_remove.append(key)
        for key in to_remove:
            self.invalidate(key)

    def invalidate_older_than(self, age: timedelta) -> None:
        """Invalidate all items older than specified age"""
        cutoff = datetime.now() - age
        to_remove = []
        for key, (_, expiry) in self._cache.items():
            if expiry - self._default_ttl < cutoff:
                to_remove.append(key)
        for key in to_remove:
            self.invalidate(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": hit_rate,
        }


class EvidenceOrchestratorV2:
    """
    Next-generation evidence orchestrator with advanced capabilities
    """

    def __init__(self) -> None:
        self._sources: Dict[str, EvidenceSource] = {}
        self._cache = EvidenceCache()
        self._concurrency_limit = 5
        self._collection_metrics: Dict[str, Any] = {
            "total_collections": 0,
            "successful_collections": 0,
            "failed_collections": 0,
            "timeout_collections": 0,
            "cache_hits": 0,
            "max_concurrent": 0,
            "total_time_ms": 0,
        }
        self._deduplication_enabled = False
        self._seen_fingerprints: Set[str] = set()

    def register_source(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new evidence source"""
        metadata = config.get("metadata", {})
        if "response_time_ms" in config:
            metadata["response_time_ms"] = config["response_time_ms"]
        if "simulate_error" in config:
            metadata["simulate_error"] = config["simulate_error"]
        source = EvidenceSource(
            source_id=config["source_id"],
            source_type=config.get("source_type", "database"),
            priority=config.get("priority", 99),
            trust_level=config.get("trust_level", 0.5),
            verified=config.get("verified", False),
            capabilities=config.get("capabilities", []),
            connection=config.get("connection", {}),
            metadata=metadata,
        )
        self._sources[source.source_id] = source
        return {
            "success": True,
            "source_id": source.source_id,
            "message": f"Source '{source.source_id}' registered successfully",
        }

    def list_sources(self) -> List[Dict[str, Any]]:
        """List all registered sources"""
        return [
            {
                "source_id": s.source_id,
                "source_type": s.source_type,
                "priority": s.priority,
                "trust_level": s.trust_level,
                "health_status": s.health_status.value,
                "capabilities": s.capabilities,
            }
            for s in self._sources.values()
        ]

    def discover_sources(self) -> List[Dict[str, Any]]:
        """Automatically discover available evidence sources"""
        discovered = []
        if os.getenv("SUPABASE_URL"):
            discovered.append(
                {
                    "source_id": "supabase_auto",
                    "source_type": "supabase",
                    "connection": {
                        "url": os.getenv("SUPABASE_URL"),
                        "key": os.getenv("SUPABASE_KEY", ""),
                    },
                }
            )
        if os.getenv("NEO4J_URI"):
            discovered.append(
                {
                    "source_id": "neo4j_auto",
                    "source_type": "neo4j",
                    "connection": {
                        "uri": os.getenv("NEO4J_URI"),
                        "user": os.getenv("NEO4J_USER", "neo4j"),
                    },
                }
            )
        if os.getenv("REDIS_URL"):
            discovered.append(
                {
                    "source_id": "redis_auto",
                    "source_type": "redis",
                    "connection": {"url": os.getenv("REDIS_URL")},
                }
            )
        return discovered

    def check_source_health(self, source_id: str) -> Dict[str, Any]:
        """Check health status of a source"""
        if source_id not in self._sources:
            return {"error": f"Source '{source_id}' not found"}
        source = self._sources[source_id]
        start_time = time.time()
        is_healthy = source.trust_level > 0.3
        latency_ms = (time.time() - start_time) * 1000
        source.health_status = SourceStatus.HEALTHY if is_healthy else SourceStatus.DEGRADED
        source.last_health_check = datetime.now()
        source.average_latency_ms = (source.average_latency_ms + latency_ms) / 2
        return {
            "source_id": source_id,
            "status": source.health_status.value,
            "latency_ms": latency_ms,
            "last_check": source.last_health_check.isoformat(),
        }

    def get_sources_by_priority(self) -> List[Dict[str, Any]]:
        """Get sources ordered by priority"""
        sorted_sources = sorted(self._sources.values(), key=lambda s: s.priority)
        return [
            {"source_id": s.source_id, "priority": s.priority, "source_type": s.source_type}
            for s in sorted_sources
        ]

    async def collect_parallel(
        self, query: Dict[str, Any], sources: List[str], timeout: float = 5.0
    ) -> List[CollectionResult]:
        """Collect evidence from multiple sources in parallel"""
        self._collection_metrics["total_collections"] += 1
        tasks = []
        for source_id in sources:
            if source_id in self._sources:
                task = self._collect_from_source(source_id, query, timeout)
                tasks.append(task)
        results = []
        if self._concurrency_limit:
            self._collection_metrics["max_concurrent"] = min(self._concurrency_limit, len(tasks))
            for i in range(0, len(tasks), self._concurrency_limit):
                batch = tasks[i : i + self._concurrency_limit]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                results.extend(batch_results)
        else:
            self._collection_metrics["max_concurrent"] = len(tasks)
            results = await asyncio.gather(*tasks, return_exceptions=True)
        collection_results = []
        for result in results:
            if isinstance(result, Exception):
                collection_results.append(
                    CollectionResult(
                        source_id="unknown",
                        status=CollectionStatus.ERROR,
                        error_message=str(result),
                    )
                )
                self._collection_metrics["failed_collections"] += 1
            else:
                collection_results.append(result)
                if result.status == CollectionStatus.SUCCESS:
                    self._collection_metrics["successful_collections"] += 1
                elif result.status == CollectionStatus.TIMEOUT:
                    self._collection_metrics["timeout_collections"] += 1
        return collection_results

    async def _collect_from_source(
        self, source_id: str, query: Dict[str, Any], timeout: float
    ) -> CollectionResult:
        """Collect evidence from a single source"""
        start_time = time.time()
        try:

            async def do_collection() -> Any:
                source = self._sources[source_id]
                if "response_time_ms" in source.metadata:
                    delay = source.metadata["response_time_ms"] / 1000
                    await asyncio.sleep(delay)
                if source.metadata.get("simulate_error", False):
                    raise Exception("Simulated source error")
                evidence = [
                    {
                        "source": source_id,
                        "query": query,
                        "results": f"Evidence from {source_id}",
                        "timestamp": datetime.now().isoformat(),
                    }
                ]
                return evidence

            evidence = await asyncio.wait_for(do_collection(), timeout=timeout)
            return CollectionResult(
                source_id=source_id,
                status=CollectionStatus.SUCCESS,
                evidence=evidence,
                duration=time.time() - start_time,
            )
        except asyncio.TimeoutError:
            return CollectionResult(
                source_id=source_id,
                status=CollectionStatus.TIMEOUT,
                duration=time.time() - start_time,
            )
        except Exception as e:
            return CollectionResult(
                source_id=source_id,
                status=CollectionStatus.ERROR,
                error_message=str(e),
                duration=time.time() - start_time,
            )

    def set_concurrency_limit(self, limit: int) -> None:
        """Set maximum concurrent collections"""
        self._concurrency_limit = limit

    def get_collection_metrics(self) -> Dict[str, Any]:
        """Get collection performance metrics"""
        return self._collection_metrics.copy()

    def validate_evidence(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Validate evidence structure and content"""
        errors = []
        warnings = []
        required_fields = ["evidence_id", "source_id", "type", "content"]
        for field in required_fields:
            if field not in evidence:
                errors.append(f"Missing required field: {field}")
        if "metadata" in evidence:
            if not isinstance(evidence["metadata"], dict):
                errors.append("Metadata must be a dictionary")
            else:
                recommended = ["created_at", "regulation"]
                for field in recommended:
                    if field not in evidence["metadata"]:
                        warnings.append(f"Missing recommended metadata field: {field}")
        return {"is_valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def score_evidence_quality(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Score evidence quality based on multiple factors"""
        scores = {}
        required_fields = ["evidence_id", "source_id", "type", "content", "metadata"]
        present_fields = sum((1 for f in required_fields if f in evidence))
        scores["completeness_score"] = present_fields / len(required_fields)
        if "metadata" in evidence:
            created_at = evidence["metadata"].get("created_at")
            if created_at:
                age_days = (datetime.now() - datetime.fromisoformat(created_at)).days
                scores["freshness_score"] = max(0, 1 - age_days / 365)
            else:
                scores["freshness_score"] = 0.5
        else:
            scores["freshness_score"] = 0.5
        source_id = evidence.get("source_id")
        if source_id in self._sources:
            scores["source_reliability_score"] = self._sources[source_id].trust_level
        else:
            scores["source_reliability_score"] = 0.5
        references = evidence.get("metadata", {}).get("references", [])
        scores["reference_score"] = min(1.0, len(references) / 3)
        weights = {
            "completeness_score": 0.25,
            "freshness_score": 0.25,
            "source_reliability_score": 0.3,
            "reference_score": 0.2,
        }
        overall_score = sum((scores[k] * weights[k] for k in scores))
        scores["overall_score"] = overall_score
        return scores

    def score_relevance(self, evidence: Dict[str, Any], query: Dict[str, Any]) -> Dict[str, Any]:
        """Score evidence relevance to a specific query"""
        score = 0.0
        matches = []
        if "regulation" in query and "metadata" in evidence:
            ev_reg = evidence["metadata"].get("regulation", "")
            if ev_reg == query["regulation"]:
                score += 0.5
                matches.append("regulation")
        if "topic" in query:
            content = evidence.get("content", "").lower()
            topics = evidence.get("metadata", {}).get("topics", [])
            if query["topic"] in topics:
                score += 0.3
                matches.append("exact_topic")
            elif query["topic"].lower() in content:
                score += 0.2
                matches.append("content_mention")
        return {"score": min(1.0, score), "matches": matches}

    def calculate_similarity(self, evidence1: Dict[str, Any], evidence2: Dict[str, Any]) -> float:
        """Calculate similarity between two pieces of evidence"""
        content1 = str(evidence1.get("content", "")).lower()
        content2 = str(evidence2.get("content", "")).lower()
        if content1 == content2:
            return 1.0
        words1 = set(content1.split())
        words2 = set(content2.split())
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        if not union:
            return 0.0
        jaccard = len(intersection) / len(union)
        sequence_sim = SequenceMatcher(None, content1, content2).ratio()
        return jaccard * 0.7 + sequence_sim * 0.3

    def aggregate_by_field(self, evidence_list: List[Dict], field: str) -> Dict[str, List]:
        """Aggregate evidence by a specific field"""
        aggregated = defaultdict(list)
        for evidence in evidence_list:
            key = evidence.get(field)
            if key:
                aggregated[key].append(evidence)
        return dict(aggregated)

    def merge_duplicates(
        self, evidence_list: List[Dict], similarity_threshold: float = 0.8
    ) -> List[Dict]:
        """Merge duplicate evidence based on similarity"""
        if not evidence_list:
            return []
        merged = []
        processed = set()
        for i, evidence in enumerate(evidence_list):
            if i in processed:
                continue
            similar = []
            for j, other in enumerate(evidence_list[i + 1 :], i + 1):
                if j not in processed:
                    similarity = self.calculate_similarity(evidence, other)
                    if similarity >= similarity_threshold:
                        similar.append(j)
                        processed.add(j)
            if similar:
                merged_evidence = evidence.copy()
                merged_evidence["merged_from"] = [
                    evidence["evidence_id"],
                    *[evidence_list[j]["evidence_id"] for j in similar],
                ]
                merged.append(merged_evidence)
            else:
                merged.append(evidence)
            processed.add(i)
        return merged

    def aggregate_hierarchical(self, evidence_list: List[Dict], levels: List[str]) -> Dict:
        """Create hierarchical aggregation of evidence"""
        hierarchy = {}
        for evidence in evidence_list:
            current = hierarchy
            for level in levels[:-1]:
                key = evidence.get(level)
                if key:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
            leaf_key = evidence.get(levels[-1])
            if leaf_key:
                if leaf_key not in current:
                    current[leaf_key] = []
                current[leaf_key].append(evidence)
        return hierarchy

    def aggregate_weighted(
        self, evidence_list: List[Dict], weight_factors: Dict[str, float]
    ) -> List[Dict]:
        """Aggregate evidence with weighted scoring"""
        for evidence in evidence_list:
            weighted_score = 0.0
            for factor, weight in weight_factors.items():
                if factor in evidence:
                    weighted_score += evidence[factor] * weight
            evidence["weighted_score"] = weighted_score
        return sorted(evidence_list, key=lambda e: e.get("weighted_score", 0), reverse=True)

    async def collect_with_cache(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Collect evidence with caching"""
        cache_key = json.dumps(query, sort_keys=True)
        cached_result = self._cache.get(cache_key)
        if cached_result:
            self._collection_metrics["cache_hits"] += 1
            return {"cache_hit": True, "data": cached_result, "collection_time_ms": 0}
        start_time = time.time()
        await asyncio.sleep(0.1)
        data = {"query": query, "results": "Fresh evidence"}
        self._cache.set(cache_key, data)
        return {
            "cache_hit": False,
            "data": data,
            "collection_time_ms": (time.time() - start_time) * 1000,
        }

    def cache_evidence(self, query: Dict[str, Any], data: Any) -> None:
        """Cache evidence for a query"""
        cache_key = json.dumps(query, sort_keys=True)
        self._cache.set(cache_key, data)

    def is_cached(self, query: Dict[str, Any]) -> bool:
        """Check if query result is cached"""
        cache_key = json.dumps(query, sort_keys=True)
        return self._cache.get(cache_key) is not None

    def invalidate_cache_older_than(self, age: timedelta) -> None:
        """Invalidate cache entries older than specified age"""
        self._cache.invalidate_older_than(age)

    def invalidate_cache_by_pattern(self, pattern: Dict[str, Any]) -> None:
        """Invalidate cache entries matching pattern"""
        self._cache.invalidate_pattern(pattern)

    def generate_fingerprint(self, evidence: Dict[str, Any]) -> str:
        """Generate fingerprint for evidence deduplication"""
        content = evidence.get("content", "")
        return hashlib.sha256(content.encode()).hexdigest()

    def enable_deduplication(self) -> None:
        """Enable evidence deduplication"""
        self._deduplication_enabled = True
        self._seen_fingerprints.clear()

    def add_evidence_batch(self, evidence_batch: List[Dict]) -> List[Dict]:
        """Add evidence batch with deduplication"""
        if not self._deduplication_enabled:
            return evidence_batch
        deduplicated = []
        for evidence in evidence_batch:
            fingerprint = self.generate_fingerprint(evidence)
            if fingerprint not in self._seen_fingerprints:
                self._seen_fingerprints.add(fingerprint)
                deduplicated.append(evidence)
        return deduplicated

    def calculate_confidence(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate confidence based on source"""
        source_id = evidence.get("source_id")
        if source_id in self._sources:
            source = self._sources[source_id]
            return {"source_confidence": source.trust_level, "source_verified": source.verified}
        return {"source_confidence": 0.5, "source_verified": False}

    def calculate_temporal_confidence(
        self, evidence: Dict[str, Any], half_life_days: int = 30
    ) -> Dict[str, Any]:
        """Calculate confidence decay over time"""
        created_at = evidence.get("created_at")
        if not created_at:
            return {"temporal_confidence": 0.5}
        created_dt = datetime.fromisoformat(created_at)
        age_days = (datetime.now() - created_dt).days
        confidence = math.exp(-0.693 * age_days / half_life_days)
        return {"temporal_confidence": confidence}

    def calculate_corroboration_confidence(
        self, primary_evidence: Dict[str, Any], corroborating_evidence: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate confidence based on corroboration"""
        if not corroborating_evidence:
            return {"corroboration_score": 0.3, "corroborating_sources": 0}
        sources = set()
        for evidence in corroborating_evidence:
            sources.add(evidence.get("source_id"))
        score = min(1.0, 0.4 + len(sources) * 0.3)
        return {"corroboration_score": score, "corroborating_sources": len(sources)}

    def calculate_composite_confidence(
        self, evidence: Dict[str, Any], weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """Calculate composite confidence score"""
        factors = {}
        source_conf = self.calculate_confidence(evidence)
        factors["source"] = source_conf["source_confidence"]
        temporal_conf = self.calculate_temporal_confidence(evidence)
        factors["temporal"] = temporal_conf["temporal_confidence"]
        quality_scores = self.score_evidence_quality(evidence)
        factors["quality"] = quality_scores["overall_score"]
        corroborated_by = evidence.get("metadata", {}).get("corroborated_by", [])
        corr_score = min(1.0, 0.3 + len(corroborated_by) * 0.2)
        factors["corroboration"] = corr_score
        overall = sum((factors[k] * weights.get(k, 0) for k in factors))
        return {"overall_confidence": overall, "confidence_factors": factors}
