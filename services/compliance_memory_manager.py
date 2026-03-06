"""

# Constants
CONFIDENCE_THRESHOLD = 0.8
HALF_RATIO = 0.5


Compliance Memory Manager for IQ Agent GraphRAG System

This module implements intelligent memory management for compliance analysis,
including conversation history, knowledge consolidation, and contextual retrieval.

Key Features:
- Conversation memory with compliance context
- Knowledge graph memory consolidation
- Temporal memory patterns for regulatory changes
- Multi-hop memory retrieval for complex compliance questions
- Memory pruning and optimization
- Compliance-specific memory clustering
"""

import logging
import json
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum
import numpy as np
from services.neo4j_service import Neo4jGraphRAGService
from services.compliance_retrieval_queries import QueryCategory

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memory in the compliance system"""


@dataclass
class MemoryNode:
    """Individual memory node structure"""

    id: str
    memory_type: MemoryType
    content: Dict[str, Any]
    timestamp: datetime
    importance_score: float
    access_count: int
    last_accessed: datetime
    tags: List[str]
    related_entities: List[str]
    confidence_score: float
    embedding: Optional[List[float]] = None


@dataclass
class MemoryCluster:
    """Cluster of related memories"""

    cluster_id: str
    theme: str
    memory_ids: List[str]
    centroid_embedding: List[float]
    importance_score: float
    created_at: datetime
    last_updated: datetime


@dataclass
class MemoryRetrievalResult:
    """Result of memory retrieval operation"""

    query_id: str
    retrieved_memories: List[MemoryNode]
    cluster_context: List[MemoryCluster]
    relevance_scores: List[float]
    total_memories_searched: int
    retrieval_strategy: str
    confidence_score: float


class ComplianceMemoryManager:
    """Advanced memory management for compliance intelligence"""

    def __init__(self, neo4j_service: Neo4jGraphRAGService) -> None:
        self.neo4j = neo4j_service
        self.memory_store: Dict[str, MemoryNode] = {}
        self.clusters: Dict[str, MemoryCluster] = {}
        self.max_memory_age_days = 365
        self.memory_importance_threshold = 0.3

    async def store_conversation_memory(
        self,
        user_query: str,
        agent_response: str,
        compliance_context: Dict[str, Any],
        importance_score: float = 0.5,
    ) -> str:
        """Store conversation memory with compliance context"""
        memory_id = self._generate_memory_id(user_query, agent_response)
        related_entities = self._extract_compliance_entities(compliance_context)
        tags = self._generate_tags(user_query, agent_response, compliance_context)
        memory_node = MemoryNode(
            id=memory_id,
            memory_type=MemoryType.CONVERSATION,
            content={
                "user_query": user_query,
                "agent_response": agent_response,
                "compliance_context": compliance_context,
                "query_category": compliance_context.get("query_category"),
                "regulations_mentioned": compliance_context.get("regulations", []),
                "risk_level": compliance_context.get("risk_level", "medium"),
            },
            timestamp=datetime.now(timezone.utc),
            importance_score=importance_score,
            access_count=0,
            last_accessed=datetime.now(timezone.utc),
            tags=tags,
            related_entities=related_entities,
            confidence_score=0.9,
        )
        self.memory_store[memory_id] = memory_node
        await self._update_memory_clusters(memory_node)
        await self._persist_memory_to_graph(memory_node)
        logger.info("Stored conversation memory: %s" % memory_id)
        return memory_id

    async def store_knowledge_graph_memory(
        self,
        graph_query_result: Dict[str, Any],
        query_category: QueryCategory,
        importance_score: float = 0.8,
    ) -> str:
        """Store knowledge graph query results as structured memory"""
        memory_id = self._generate_memory_id(str(graph_query_result), query_category.value)
        insights = self._extract_graph_insights(graph_query_result)
        memory_node = MemoryNode(
            id=memory_id,
            memory_type=MemoryType.KNOWLEDGE_GRAPH,
            content={
                "query_category": query_category.value,
                "graph_data": graph_query_result.get("data", []),
                "metadata": graph_query_result.get("metadata", {}),
                "insights": insights,
                "confidence_score": graph_query_result.get("confidence_score", 0.8),
            },
            timestamp=datetime.now(timezone.utc),
            importance_score=importance_score,
            access_count=0,
            last_accessed=datetime.now(timezone.utc),
            tags=[query_category.value, "graph_analysis", "structured_knowledge"],
            related_entities=self._extract_entities_from_graph_data(graph_query_result),
            confidence_score=graph_query_result.get("confidence_score", 0.8),
        )
        self.memory_store[memory_id] = memory_node
        await self._update_memory_clusters(memory_node)
        await self._persist_memory_to_graph(memory_node)
        logger.info("Stored knowledge graph memory: %s" % memory_id)
        return memory_id

    async def store_temporal_pattern_memory(
        self, pattern_data: Dict[str, Any], pattern_type: str, confidence_score: float
    ) -> str:
        """Store temporal compliance patterns"""
        memory_id = self._generate_memory_id(str(pattern_data), pattern_type)
        memory_node = MemoryNode(
            id=memory_id,
            memory_type=MemoryType.TEMPORAL_PATTERN,
            content={
                "pattern_type": pattern_type,
                "pattern_data": pattern_data,
                "time_range": pattern_data.get("time_range"),
                "trend_direction": pattern_data.get("trend_direction"),
                "significance_level": pattern_data.get("significance_level"),
                "prediction_horizon": pattern_data.get("prediction_horizon"),
            },
            timestamp=datetime.now(timezone.utc),
            importance_score=0.7,
            access_count=0,
            last_accessed=datetime.now(timezone.utc),
            tags=["temporal", "pattern", pattern_type, "predictive"],
            related_entities=pattern_data.get("related_entities", []),
            confidence_score=confidence_score,
        )
        self.memory_store[memory_id] = memory_node
        await self._update_memory_clusters(memory_node)
        await self._persist_memory_to_graph(memory_node)
        logger.info("Stored temporal pattern memory: %s" % memory_id)
        return memory_id

    async def retrieve_contextual_memories(
        self,
        query: str,
        context: Dict[str, Any],
        max_memories: int = 10,
        relevance_threshold: float = 0.5,
    ) -> MemoryRetrievalResult:
        """Retrieve contextually relevant memories for compliance analysis"""
        query_id = self._generate_memory_id(query, str(context))
        query_entities = self._extract_entities_from_text(query)
        query_tags = self._generate_tags_from_text(query)
        relevant_memories = []
        relevance_scores = []
        entity_memories = await self._retrieve_by_entities(query_entities)
        tag_memories = await self._retrieve_by_tags(query_tags)
        semantic_memories = await self._retrieve_by_semantic_similarity(query)
        temporal_memories = await self._retrieve_by_temporal_relevance(context)
        all_candidate_memories = set()
        all_candidate_memories.update(entity_memories)
        all_candidate_memories.update(tag_memories)
        all_candidate_memories.update(semantic_memories)
        all_candidate_memories.update(temporal_memories)
        for memory_id in all_candidate_memories:
            if memory_id not in self.memory_store:
                continue
            memory = self.memory_store[memory_id]
            relevance_score = self._calculate_memory_relevance(
                memory, query, query_entities, query_tags, context
            )
            if relevance_score >= relevance_threshold:
                relevant_memories.append(memory)
                relevance_scores.append(relevance_score)
                memory.access_count += 1
                memory.last_accessed = datetime.now(timezone.utc)
        sorted_pairs = sorted(
            zip(relevant_memories, relevance_scores), key=lambda x: x[1], reverse=True
        )
        if sorted_pairs:
            relevant_memories, relevance_scores = zip(*sorted_pairs)
            relevant_memories = list(relevant_memories)[:max_memories]
            relevance_scores = list(relevance_scores)[:max_memories]
        else:
            relevant_memories, relevance_scores = [], []
        cluster_context = await self._get_cluster_context(relevant_memories)
        return MemoryRetrievalResult(
            query_id=query_id,
            retrieved_memories=relevant_memories,
            cluster_context=cluster_context,
            relevance_scores=relevance_scores,
            total_memories_searched=len(all_candidate_memories),
            retrieval_strategy="multi_strategy_hybrid",
            confidence_score=np.mean(relevance_scores) if relevance_scores else 0.0,
        )

    async def consolidate_compliance_knowledge(self, time_window_days: int = 30) -> Dict[str, Any]:
        """Consolidate compliance knowledge from recent memories"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_window_days)
        recent_memories = [
            memory for memory in self.memory_store.values() if memory.timestamp >= cutoff_date
        ]
        domain_knowledge = {}
        regulation_insights = {}
        risk_patterns = {}
        for memory in recent_memories:
            content = memory.content
            if "compliance_context" in content:
                domains = content["compliance_context"].get("domains", [])
                for domain in domains:
                    if domain not in domain_knowledge:
                        domain_knowledge[domain] = {
                            "memories": [],
                            "risk_levels": [],
                            "recent_queries": [],
                        }
                    domain_knowledge[domain]["memories"].append(memory.id)
                    if "risk_level" in content:
                        domain_knowledge[domain]["risk_levels"].append(content["risk_level"])
            regulations = content.get("regulations_mentioned", [])
            for regulation in regulations:
                if regulation not in regulation_insights:
                    regulation_insights[regulation] = {
                        "mention_count": 0,
                        "contexts": [],
                        "risk_assessments": [],
                    }
                regulation_insights[regulation]["mention_count"] += 1
                regulation_insights[regulation]["contexts"].append(memory.id)
            if memory.memory_type == MemoryType.RISK_ASSESSMENT:
                risk_data = content.get("risk_data", {})
                risk_level = risk_data.get("level", "unknown")
                if risk_level not in risk_patterns:
                    risk_patterns[risk_level] = []
                risk_patterns[risk_level].append(memory.id)
        consolidation_result = {
            "consolidation_period": {
                "start_date": cutoff_date.isoformat(),
                "end_date": datetime.now(timezone.utc).isoformat(),
                "memories_analyzed": len(recent_memories),
            },
            "domain_analysis": self._analyze_domain_knowledge(domain_knowledge),
            "regulation_insights": self._analyze_regulation_insights(regulation_insights),
            "risk_pattern_analysis": self._analyze_risk_patterns(risk_patterns),
            "trending_topics": self._identify_trending_topics(recent_memories),
            "knowledge_gaps": self._identify_knowledge_gaps(recent_memories),
            "consolidation_score": self._calculate_consolidation_score(recent_memories),
        }
        await self.store_knowledge_graph_memory(
            consolidation_result, QueryCategory.REGULATORY_COVERAGE, importance_score=0.9
        )
        logger.info("Consolidated knowledge from %s memories" % len(recent_memories))
        return consolidation_result

    async def prune_old_memories(
        self, max_age_days: Optional[int] = None, min_importance_score: Optional[float] = None
    ) -> Dict[str, int]:
        """Prune old and low-importance memories"""
        max_age = max_age_days or self.max_memory_age_days
        min_importance = min_importance_score or self.memory_importance_threshold
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age)
        memories_to_remove = []
        for memory_id, memory in self.memory_store.items():
            should_remove = False
            if (
                memory.timestamp < cutoff_date
                or memory.importance_score < min_importance
                and memory.access_count < 2
                and memory.timestamp < datetime.now(timezone.utc) - timedelta(days=7)
            ):
                should_remove = True
            if (
                memory.memory_type in [MemoryType.COMPLIANCE_RULE, MemoryType.REGULATORY_CHANGE]
                or memory.importance_score > CONFIDENCE_THRESHOLD
            ):
                should_remove = False
            if should_remove:
                memories_to_remove.append(memory_id)
        removed_by_type = {}
        for memory_id in memories_to_remove:
            memory = self.memory_store[memory_id]
            memory_type = memory.memory_type.value
            if memory_type not in removed_by_type:
                removed_by_type[memory_type] = 0
            removed_by_type[memory_type] += 1
            del self.memory_store[memory_id]
            await self._remove_memory_from_graph(memory_id)
        await self._rebuild_clusters()
        pruning_result = {
            "total_removed": len(memories_to_remove),
            "removed_by_type": removed_by_type,
            "remaining_memories": len(self.memory_store),
            "pruning_criteria": {"max_age_days": max_age, "min_importance_score": min_importance},
        }
        logger.info("Pruned %s memories from store" % len(memories_to_remove))
        return pruning_result

    def _generate_memory_id(self, *args) -> str:
        """Generate unique memory ID from content"""
        content_hash = hashlib.sha256("".join(str(arg) for arg in args).encode()).hexdigest()
        return f"mem_{content_hash[:16]}"

    def _extract_compliance_entities(self, context: Dict[str, Any]) -> List[str]:
        """Extract compliance-related entities from context"""
        entities = []
        entities.extend(context.get("regulations", []))
        entities.extend(context.get("domains", []))
        entities.extend(context.get("jurisdictions", []))
        entities.extend(context.get("business_functions", []))
        return list(set(entities))

    def _generate_tags(
        self, user_query: str, agent_response: str, context: Dict[str, Any]
    ) -> List[str]:
        """Generate tags for memory indexing"""
        tags = []
        if "query_category" in context:
            tags.append(context["query_category"])
        if "risk_level" in context:
            tags.append(f"risk_{context['risk_level']}")
        for domain in context.get("domains", []):
            tags.append(f"domain_{domain.lower().replace(' ', '_')}")
        query_terms = self._extract_key_terms(user_query)
        tags.extend(query_terms)
        return list(set(tags))

    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text for tagging"""
        compliance_keywords = [
            "compliance",
            "regulation",
            "risk",
            "audit",
            "control",
            "gdpr",
            "aml",
            "kyc",
            "dora",
            "mifid",
            "requirement",
            "penalty",
            "enforcement",
            "jurisdiction",
            "assessment",
        ]
        text_lower = text.lower()
        found_terms = []
        for keyword in compliance_keywords:
            if keyword in text_lower:
                found_terms.append(keyword)
        return found_terms

    async def _update_memory_clusters(self, memory_node: MemoryNode) -> None:
        """Update memory clusters with new memory"""
        cluster_key = (
            f"{memory_node.memory_type.value}_{hash(tuple(sorted(memory_node.tags))) % 1000}",
        )
        if cluster_key not in self.clusters:
            self.clusters[cluster_key] = MemoryCluster(
                cluster_id=cluster_key,
                theme=memory_node.memory_type.value,
                memory_ids=[],
                centroid_embedding=[],
                importance_score=0.0,
                created_at=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc),
            )
        cluster = self.clusters[cluster_key]
        cluster.memory_ids.append(memory_node.id)
        cluster.last_updated = datetime.now(timezone.utc)
        cluster.importance_score = np.mean(
            [
                self.memory_store[mid].importance_score
                for mid in cluster.memory_ids
                if mid in self.memory_store
            ]
        )

    async def _persist_memory_to_graph(self, memory_node: MemoryNode) -> None:
        """Persist memory to Neo4j graph"""
        query = """
        CREATE (m:Memory {
            id: $id,
            memory_type: $memory_type,
            content: $content,
            timestamp: datetime($timestamp),
            importance_score: $importance_score,
            access_count: $access_count,
            tags: $tags,
            related_entities: $related_entities,
            confidence_score: $confidence_score
        })
        """
        await self.neo4j.execute_query(
            query,
            {
                "id": memory_node.id,
                "memory_type": memory_node.memory_type.value,
                "content": json.dumps(memory_node.content),
                "timestamp": memory_node.timestamp.isoformat(),
                "importance_score": memory_node.importance_score,
                "access_count": memory_node.access_count,
                "tags": memory_node.tags,
                "related_entities": memory_node.related_entities,
                "confidence_score": memory_node.confidence_score,
            },
        )

    async def _retrieve_by_entities(self, entities: List[str]) -> List[str]:
        """Retrieve memories by related entities"""
        return [
            memory_id
            for memory_id, memory in self.memory_store.items()
            if any(entity in memory.related_entities for entity in entities)
        ]

    async def _retrieve_by_tags(self, tags: List[str]) -> List[str]:
        """Retrieve memories by tags"""
        return [
            memory_id
            for memory_id, memory in self.memory_store.items()
            if any(tag in memory.tags for tag in tags)
        ]

    async def _retrieve_by_semantic_similarity(self, query: str) -> List[str]:
        """Retrieve memories by semantic similarity (placeholder)"""
        return []

    async def _retrieve_by_temporal_relevance(self, context: Dict[str, Any]) -> List[str]:
        """Retrieve temporally relevant memories"""
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        return [
            memory_id
            for memory_id, memory in self.memory_store.items()
            if memory.timestamp >= recent_cutoff and memory.access_count > 0
        ]

    def _calculate_memory_relevance(
        self,
        memory: MemoryNode,
        query: str,
        query_entities: List[str],
        query_tags: List[str],
        context: Dict[str, Any],
    ) -> float:
        """Calculate relevance score for memory retrieval"""
        relevance_score = 0.0
        entity_overlap = len(set(query_entities) & set(memory.related_entities))
        entity_score = entity_overlap / max(len(query_entities), 1) * 0.4
        relevance_score += entity_score
        tag_overlap = len(set(query_tags) & set(memory.tags))
        tag_score = tag_overlap / max(len(query_tags), 1) * 0.3
        relevance_score += tag_score
        importance_score = memory.importance_score * 0.2
        relevance_score += importance_score
        days_old = (datetime.now(timezone.utc) - memory.timestamp).days
        recency_score = max(0, (30 - days_old) / 30) * 0.1
        relevance_score += recency_score
        if memory.access_count > 2:
            relevance_score += 0.05
        return min(relevance_score, 1.0)

    def _extract_entities_from_text(self, text: str) -> List[str]:
        """Extract entities from text (simplified)"""
        return self._extract_key_terms(text)

    def _generate_tags_from_text(self, text: str) -> List[str]:
        """Generate tags from text"""
        return self._extract_key_terms(text)

    async def _get_cluster_context(self, memories: List[MemoryNode]) -> List[MemoryCluster]:
        """Get cluster context for retrieved memories"""
        memory_ids = [memory.id for memory in memories]
        relevant_clusters = []
        for cluster in self.clusters.values():
            if any(mid in cluster.memory_ids for mid in memory_ids):
                relevant_clusters.append(cluster)
        return relevant_clusters

    def _extract_graph_insights(self, graph_result: Dict[str, Any]) -> List[str]:
        """Extract key insights from graph query results"""
        insights = []
        metadata = graph_result.get("metadata", {})
        if "overall_coverage" in metadata:
            coverage = metadata["overall_coverage"]
            if coverage < HALF_RATIO:
                insights.append("Low compliance coverage detected")
            elif coverage > CONFIDENCE_THRESHOLD:
                insights.append("High compliance coverage achieved")
        if "critical_gaps" in metadata:
            critical_gaps = metadata["critical_gaps"]
            if critical_gaps > 0:
                insights.append(f"{critical_gaps} critical compliance gaps identified")
        return insights

    def _extract_entities_from_graph_data(self, graph_result: Dict[str, Any]) -> List[str]:
        """Extract entities from graph query results"""
        entities = []
        data = graph_result.get("data", [])
        for item in data:
            if isinstance(item, dict):
                if "regulation" in item:
                    entities.append(item["regulation"])
                if "domain" in item:
                    entities.append(item["domain"])
        return list(set(entities))

    def _analyze_domain_knowledge(self, domain_knowledge: Dict) -> Dict:
        """Analyze domain knowledge patterns"""
        analysis = {}
        for domain, data in domain_knowledge.items():
            risk_levels = data["risk_levels"]
            analysis[domain] = {
                "memory_count": len(data["memories"]),
                "dominant_risk_level": max(set(risk_levels), key=risk_levels.count)
                if risk_levels
                else "unknown",
                "query_frequency": len(data["recent_queries"]),
            }
        return analysis

    def _analyze_regulation_insights(self, regulation_insights: Dict) -> Dict:
        """Analyze regulation mention patterns"""
        analysis = {}
        for regulation, data in regulation_insights.items():
            analysis[regulation] = {
                "mention_frequency": data["mention_count"],
                "context_diversity": len(set(data["contexts"])),
                "attention_score": data["mention_count"] * len(set(data["contexts"])),
            }
        return analysis

    def _analyze_risk_patterns(self, risk_patterns: Dict) -> Dict:
        """Analyze risk assessment patterns"""
        total_assessments = sum(len(memories) for memories in risk_patterns.values())
        analysis = {
            "total_assessments": total_assessments,
            "risk_distribution": {
                level: (len(memories) / total_assessments if total_assessments > 0 else 0)
                for level, memories in risk_patterns.items()
            },
        }
        return analysis

    def _identify_trending_topics(self, memories: List[MemoryNode]) -> List[str]:
        """Identify trending compliance topics"""
        tag_frequency = {}
        for memory in memories:
            for tag in memory.tags:
                tag_frequency[tag] = tag_frequency.get(tag, 0) + 1
        sorted_tags = sorted(tag_frequency.items(), key=lambda x: x[1], reverse=True)
        return [tag for tag, freq in sorted_tags[:5]]

    def _identify_knowledge_gaps(self, memories: List[MemoryNode]) -> List[str]:
        """Identify potential knowledge gaps"""
        gaps = []
        domain_coverage = {}
        for memory in memories:
            entities = memory.related_entities
            for entity in entities:
                domain_coverage[entity] = domain_coverage.get(entity, 0) + 1
        avg_coverage = np.mean(list(domain_coverage.values())) if domain_coverage else 0
        for domain, coverage in domain_coverage.items():
            if coverage < avg_coverage * 0.5:
                gaps.append(f"Low coverage for {domain}")
        return gaps

    def _calculate_consolidation_score(self, memories: List[MemoryNode]) -> float:
        """Calculate overall knowledge consolidation score"""
        if not memories:
            return 0.0
        avg_importance = np.mean([memory.importance_score for memory in memories])
        memory_types = set(memory.memory_type for memory in memories)
        diversity_score = len(memory_types) / len(MemoryType)
        recent_memories = sum(
            1
            for memory in memories
            if memory.timestamp >= datetime.now(timezone.utc) - timedelta(days=7)
        )
        recency_score = recent_memories / len(memories)
        consolidation_score = avg_importance * 0.5 + diversity_score * 0.3 + recency_score * 0.2
        return round(consolidation_score, 3)

    async def _remove_memory_from_graph(self, memory_id: str) -> None:
        """Remove memory from Neo4j graph"""
        query = "MATCH (m:Memory {id: $id}) DETACH DELETE m"
        await self.neo4j.execute_query(query, {"id": memory_id})

    async def _rebuild_clusters(self) -> None:
        """Rebuild memory clusters after pruning"""
        valid_clusters = {}
        for cluster_id, cluster in self.clusters.items():
            valid_memory_ids = [mid for mid in cluster.memory_ids if mid in self.memory_store]
            if valid_memory_ids:
                cluster.memory_ids = valid_memory_ids
                cluster.last_updated = datetime.now(timezone.utc)
                valid_clusters[cluster_id] = cluster
        self.clusters = valid_clusters
