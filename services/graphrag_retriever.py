"""
GraphRAG Retriever Service for Compliance Knowledge

This module implements the specialized retrieval agent that serves grounded context
to the IQ agent from the Neo4j compliance knowledge graph. It provides:
- Local GraphRAG for specific entity queries
- Global GraphRAG for cross-jurisdictional synthesis
- Hybrid retrieval combining graph traversal with vector search
- Temporal awareness via Graphiti framework integration
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import hashlib

from services.neo4j_service import Neo4jGraphRAGService
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)


class RetrievalMode(Enum):
    """Retrieval strategies for different query types"""

    LOCAL = "local"  # Specific entity queries
    GLOBAL = "global"  # Cross-jurisdictional synthesis
    HYBRID = "hybrid"  # Combined graph + vector search
    TEMPORAL = "temporal"  # Time-aware regulatory tracking


@dataclass
class ContextPack:
    """Structured context returned by the retriever"""

    query_id: str
    retrieval_mode: RetrievalMode
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    paths: List[List[str]]
    coverage_gaps: List[str]
    confidence_score: float
    sources: List[Dict[str, Any]]
    timestamp: datetime
    query_metadata: Dict[str, Any]


class GraphRAGRetriever:
    """
    Production-ready GraphRAG Retriever for Compliance Knowledge

    This retriever serves as the knowledge access layer for IQ, providing
    grounded, traceable context from the compliance knowledge graph.
    """

    # System prompt defining the retriever's behavior
    SYSTEM_PROMPT = """# GraphRAG Retriever for Compliance Knowledge

## Role
You are a specialized retrieval agent that serves grounded context from the Neo4j compliance knowledge graph. You DO NOT generate content - you ONLY retrieve and structure existing knowledge.  # noqa: E501

## Core Principles
1. **Retrieval-Only**: Return facts from the graph, never speculate
2. **Traceability**: Every piece of information must link to a graph node
3. **Coverage Awareness**: Explicitly identify gaps in knowledge
4. **Multi-Source**: Triangulate information from multiple nodes when available

## Retrieval Modes

### LOCAL GraphRAG
For specific entity queries (e.g., "GDPR Article 33 requirements"):
- Direct node lookup
- 1-2 hop traversal for related entities
- Return specific obligations, controls, evidence

### GLOBAL GraphRAG
For synthesis queries (e.g., "AML landscape across jurisdictions"):
- Cross-jurisdictional aggregation
- Pattern detection across multiple regulations
- Comparative analysis of requirements

### HYBRID Mode
For fuzzy queries requiring both precision and breadth:
- Vector similarity search + graph traversal
- Semantic matching with structural validation
- Ranked results by relevance and authority

### TEMPORAL Mode
For time-aware queries (e.g., "regulatory changes in 2024"):
- Version tracking of regulations
- Effective date filtering
- Amendment history traversal

## Query Processing Pipeline

1. **Parse Intent**: Identify jurisdiction, regulation, requirement type
2. **Select Mode**: Choose optimal retrieval strategy
3. **Execute Query**: Run Cypher/vector search
4. **Validate Results**: Ensure node existence and relationship integrity
5. **Structure Output**: Format as ContextPack with full traceability

## Output Format
Always return a ContextPack containing:
- Relevant nodes with properties
- Relationship paths showing connections
- Coverage gaps (what's missing)
- Confidence score based on source quality
- Full source attribution

## Constraints
- NEVER interpolate between data points
- NEVER guess at missing information
- ALWAYS indicate when requested information is not in graph
- ALWAYS prefer primary sources over secondary
"""

    def __init__(self, neo4j_service: Neo4jGraphRAGService) -> None:
        """Initialize the GraphRAG Retriever"""
        self.neo4j = neo4j_service
        self.embeddings = OpenAIEmbeddings()
        self.retrieval_cache = {}

    def get_system_prompt(self) -> str:
        """Return the retriever's system prompt"""
        return self.SYSTEM_PROMPT

    async def retrieve(
        self,
        query: str,
        mode: Optional[RetrievalMode] = None,
        jurisdiction: Optional[str] = None,
        max_nodes: int = 50,
    ) -> ContextPack:
        """
        Main retrieval method - routes queries to appropriate retrieval strategy

        Args:
            query: The compliance query to retrieve context for
            mode: Optional forced retrieval mode
            jurisdiction: Optional jurisdiction filter (UK, EU, US)
            max_nodes: Maximum nodes to return

        Returns:
            ContextPack with retrieved compliance knowledge
        """
        # Generate query ID
        # Use SHA-256 instead of MD5 for security compliance, truncated for query ID compatibility
        query_id = hashlib.sha256(f"{query}_{datetime.now(timezone.utc)}".encode()).hexdigest()[:12]

        # Determine retrieval mode if not specified
        if mode is None:
            mode = self._select_retrieval_mode(query)

        # Execute retrieval based on mode
        if mode == RetrievalMode.LOCAL:
            result = await self._local_retrieval(query, jurisdiction, max_nodes)
        elif mode == RetrievalMode.GLOBAL:
            result = await self._global_retrieval(query, jurisdiction, max_nodes)
        elif mode == RetrievalMode.HYBRID:
            result = await self._hybrid_retrieval(query, jurisdiction, max_nodes)
        elif mode == RetrievalMode.TEMPORAL:
            result = await self._temporal_retrieval(query, jurisdiction, max_nodes)
        else:
            raise ValueError(f"Unknown retrieval mode: {mode}")

        # Structure as ContextPack
        return ContextPack(
            query_id=query_id,
            retrieval_mode=mode,
            nodes=result.get("nodes", []),
            relationships=result.get("relationships", []),
            paths=result.get("paths", []),
            coverage_gaps=result.get("gaps", []),
            confidence_score=result.get("confidence", 0.0),
            sources=result.get("sources", []),
            timestamp=datetime.now(timezone.utc),
            query_metadata={
                "query": query,
                "jurisdiction": jurisdiction,
                "max_nodes": max_nodes,
            },
        )

    def _select_retrieval_mode(self, query: str) -> RetrievalMode:
        """Intelligently select retrieval mode based on query characteristics"""
        query_lower = query.lower()

        # Temporal indicators
        if any(
            term in query_lower
            for term in ["change", "update", "amend", "new", "2024", "2025", "recent"]
        ):
            return RetrievalMode.TEMPORAL

        # Global synthesis indicators
        if any(
            term in query_lower
            for term in [
                "across",
                "compare",
                "landscape",
                "all jurisdictions",
                "overview",
            ]
        ):
            return RetrievalMode.GLOBAL

        # Specific entity indicators
        if any(
            term in query_lower
            for term in ["article", "section", "requirement", "control for", "specific"]
        ):
            return RetrievalMode.LOCAL

        # Default to hybrid for ambiguous queries
        return RetrievalMode.HYBRID

    async def _local_retrieval(
        self, query: str, jurisdiction: Optional[str], max_nodes: int
    ) -> Dict[str, Any]:
        """
        Local GraphRAG - retrieve specific entities and their immediate context
        """
        # Parse query for specific regulation/requirement references
        cypher_query = """
        // Local retrieval for specific compliance entities
        MATCH (r:Regulation)-[:CONTAINS]->(req:Requirement)
        WHERE toLower(r.name) CONTAINS toLower($query_term)
           OR toLower(req.description) CONTAINS toLower($query_term)
        OPTIONAL MATCH (req)-[:SATISFIED_BY]->(c:Control)
        OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(e:Evidence)
        WITH r, req, collect(DISTINCT c) as controls, collect(DISTINCT e) as evidence
        LIMIT $max_nodes
        RETURN {
            regulation: {
                name: r.name,
                jurisdiction: r.jurisdiction,
                effective_date: r.effective_date,
                url: r.url,
            },
            requirement: {
                id: req.id,
                description: req.description,
                mandatory: req.mandatory,
                category: req.category,
            },
            controls: [c IN controls | {
                id: c.id,
                name: c.name,
                type: c.type,
                status: c.implementation_status
            }],
            evidence: [e IN evidence | {
                id: e.id,
                type: e.type,
                collected_at: e.collected_at
            }]
        } as result
        """

        params = {"query_term": query, "max_nodes": max_nodes}

        if jurisdiction:
            cypher_query = cypher_query.replace(
                "WHERE toLower(r.name)",
                "WHERE r.jurisdiction = $jurisdiction AND toLower(r.name)",
            )
            params["jurisdiction"] = jurisdiction

        results = await self.neo4j.execute_query(cypher_query, params)

        # Process results
        nodes = []
        relationships = []
        sources = []

        for record in results:
            result = record.get("result", {})

            # Add regulation node
            if result.get("regulation"):
                nodes.append({"type": "Regulation", "properties": result["regulation"]})
                sources.append(
                    {
                        "type": "primary",
                        "url": result["regulation"].get("url"),
                        "jurisdiction": result["regulation"].get("jurisdiction"),
                    },
                )

            # Add requirement node
            if result.get("requirement"):
                nodes.append(
                    {"type": "Requirement", "properties": result["requirement"]},
                )
                relationships.append(
                    {"type": "CONTAINS", "from": "Regulation", "to": "Requirement"},
                )

            # Add control nodes
            for control in result.get("controls", []):
                nodes.append({"type": "Control", "properties": control})
                relationships.append(
                    {"type": "SATISFIED_BY", "from": "Requirement", "to": "Control"},
                )

        # Identify gaps
        gaps = []
        if not results:
            gaps.append(f"No specific requirements found for query: {query}")
        elif not any(r.get("result", {}).get("controls") for r in results):
            gaps.append("Requirements identified but no controls implemented")

        return {
            "nodes": nodes,
            "relationships": relationships,
            "sources": sources,
            "gaps": gaps,
            "confidence": 0.9 if results else 0.1,
        }

    async def _global_retrieval(
        self, query: str, jurisdiction: Optional[str], max_nodes: int
    ) -> Dict[str, Any]:
        """
        Global GraphRAG - cross-jurisdictional synthesis and pattern detection
        """
        # Query for patterns across jurisdictions
        cypher_query = """
        // Global retrieval for cross-jurisdictional patterns
        MATCH (d:ComplianceDomain)-[:INCLUDES]->(r:Regulation)
        WHERE toLower(d.name) CONTAINS toLower($query_term)
           OR toLower(r.name) CONTAINS toLower($query_term)
        WITH d, collect(DISTINCT r) as regulations
        UNWIND regulations as reg
        MATCH (reg)-[:CONTAINS]->(req:Requirement)
        WITH d, reg, count(req) as req_count
        ORDER BY req_count DESC
        LIMIT $max_nodes
        RETURN {
            domain: d.name,
            regulations: collect(DISTINCT {
                name: reg.name,
                jurisdiction: reg.jurisdiction,
                requirement_count: req_count,
                effective_date: reg.effective_date
            })
        } as pattern
        """

        params = {"query_term": query, "max_nodes": max_nodes}

        results = await self.neo4j.execute_query(cypher_query, params)

        # Aggregate patterns
        patterns = {}
        nodes = []

        for record in results:
            pattern = record.get("pattern", {})
            domain = pattern.get("domain")

            if domain:
                if domain not in patterns:
                    patterns[domain] = {
                        "jurisdictions": set(),
                        "regulations": [],
                        "total_requirements": 0,
                    }

                for reg in pattern.get("regulations", []):
                    patterns[domain]["jurisdictions"].add(reg.get("jurisdiction"))
                    patterns[domain]["regulations"].append(reg)
                    patterns[domain]["total_requirements"] += reg.get(
                        "requirement_count",
                        0,
                    )

                nodes.append(
                    {
                        "type": "ComplianceDomain",
                        "properties": {
                            "name": domain,
                            "coverage": list(patterns[domain]["jurisdictions"]),
                        },
                    },
                )

        # Build synthesis
        synthesis = {
            "patterns_detected": len(patterns),
            "jurisdictions_covered": (
                list(set().union(*(p["jurisdictions"] for p in patterns.values())))
                if patterns
                else [],
            ),
            "domains": list(patterns.keys()),
        }

        return {
            "nodes": nodes,
            "relationships": [],
            "sources": [{"type": "synthesis", "patterns": synthesis}],
            "gaps": ["Limited cross-jurisdictional data"] if len(patterns) < 2 else [],
            "confidence": min(0.8, len(patterns) * 0.2),
        }

    async def _hybrid_retrieval(
        self, query: str, jurisdiction: Optional[str], max_nodes: int
    ) -> Dict[str, Any]:
        """
        Hybrid retrieval - combines vector similarity with graph traversal
        """
        # Get query embedding
        query_embedding = await self._get_embedding(query)

        # Vector similarity search
        vector_query = """
        // Hybrid retrieval with vector similarity
        CALL db.index.vector.queryNodes('compliance_embeddings', $k, $query_vector)
        YIELD node, score
        WHERE score > 0.7
        MATCH (node)-[r]-(connected)
        RETURN node, collect(DISTINCT {
            connected_node: connected,
            relationship: type(r),
            score: score
        }) as connections
        LIMIT $max_nodes
        """

        params = {
            "query_vector": query_embedding,
            "k": max_nodes,
            "max_nodes": max_nodes,
        }

        # Fallback to standard search if vector index doesn't exist
        try:
            results = await self.neo4j.execute_query(vector_query, params)
        except Exception as e:
            logger.warning(f"Vector search failed, falling back to text search: {e}")
            # Fallback to text-based search
            return await self._local_retrieval(query, jurisdiction, max_nodes)

        # Process hybrid results
        nodes = []
        relationships = []

        for record in results:
            node = record.get("node", {})
            connections = record.get("connections", [])

            nodes.append(
                {"type": node.get("label", "Unknown"), "properties": dict(node)},
            )

            for conn in connections:
                relationships.append(
                    {"type": conn.get("relationship"), "score": conn.get("score")},
                )

        return {
            "nodes": nodes,
            "relationships": relationships,
            "sources": [{"type": "hybrid", "method": "vector+graph"}],
            "gaps": [],
            "confidence": 0.75,
        }

    async def _temporal_retrieval(
        self, query: str, jurisdiction: Optional[str], max_nodes: int
    ) -> Dict[str, Any]:
        """
        Temporal retrieval - track regulatory changes over time
        """
        cypher_query = """
        // Temporal retrieval for regulatory changes
        MATCH (r:Regulation)
        WHERE r.last_updated > datetime('2024-01-01')
        OPTIONAL MATCH (r)-[:SUPERSEDES]->(old:Regulation)
        OPTIONAL MATCH (r)-[:AMENDS]->(amended:Regulation)
        WITH r, collect(DISTINCT old) as superseded, collect(DISTINCT amended) as amendments
        ORDER BY r.last_updated DESC
        LIMIT $max_nodes
        RETURN {
            current: {
                name: r.name,
                jurisdiction: r.jurisdiction,
                effective_date: r.effective_date,
                last_updated: r.last_updated,
            },
            superseded: [s IN superseded | s.name],
            amendments: [a IN amendments | {
                name: a.name,
                date: a.effective_date
            }],
            change_type: CASE
                WHEN size(superseded) > 0 THEN 'replacement'
                WHEN size(amendments) > 0 THEN 'amendment'
                ELSE 'new'
            END
        } as change
        """

        params = {"max_nodes": max_nodes}

        if jurisdiction:
            cypher_query = cypher_query.replace(
                "WHERE r.last_updated",
                "WHERE r.jurisdiction = $jurisdiction AND r.last_updated",
            )
            params["jurisdiction"] = jurisdiction

        results = await self.neo4j.execute_query(cypher_query, params)

        # Process temporal changes
        nodes = []
        changes = []

        for record in results:
            change = record.get("change", {})

            nodes.append(
                {
                    "type": "Regulation",
                    "properties": change.get("current", {}),
                    "temporal_metadata": {
                        "change_type": change.get("change_type"),
                        "superseded": change.get("superseded", []),
                        "amendments": change.get("amendments", []),
                    },
                },
            )

            changes.append(
                {
                    "regulation": change.get("current", {}).get("name"),
                    "type": change.get("change_type"),
                    "date": change.get("current", {}).get("last_updated"),
                },
            )

        return {
            "nodes": nodes,
            "relationships": [],
            "sources": [{"type": "temporal", "changes": changes}],
            "gaps": ["Historical data limited"] if len(results) < 5 else [],
            "confidence": 0.85,
        }

    async def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        try:
            embedding = await self.embeddings.aembed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return [0.0] * 1536  # Return zero vector as fallback

    async def validate_coverage(self, jurisdictions: List[str] = None) -> Dict[str, Any]:
        """
        Validate coverage of regulations across jurisdictions
        """
        if jurisdictions is None:
            jurisdictions = ["UK", "EU", "US"]
        coverage_query = """
        MATCH (r:Regulation)
        WITH r.jurisdiction as jurisdiction, count(r) as reg_count
        MATCH (req:Requirement)
        WITH jurisdiction, reg_count, count(req) as req_count
        MATCH (c:Control)
        WITH jurisdiction, reg_count, req_count, count(c) as control_count
        RETURN {
            jurisdiction: jurisdiction,
            regulations: reg_count,
            requirements: req_count,
            controls: control_count,
            coverage_ratio: toFloat(control_count) / toFloat(req_count)
        } as coverage
        """

        results = await self.neo4j.execute_query(coverage_query)

        coverage_report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "jurisdictions": {},
        }

        for record in results:
            cov = record.get("coverage", {})
            jurisdiction = cov.get("jurisdiction")
            if jurisdiction:
                coverage_report["jurisdictions"][jurisdiction] = {
                    "regulations": cov.get("regulations", 0),
                    "requirements": cov.get("requirements", 0),
                    "controls": cov.get("controls", 0),
                    "coverage_percentage": round(cov.get("coverage_ratio", 0) * 100, 2),
                }

        # Identify gaps
        for j in jurisdictions:
            if j not in coverage_report["jurisdictions"]:
                coverage_report["jurisdictions"][j] = {
                    "status": "NO_DATA",
                    "message": f"No regulations found for {j}",
                }

        return coverage_report
