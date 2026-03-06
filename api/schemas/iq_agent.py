"""

IQ Agent Schemas for GraphRAG Compliance Intelligence

Pydantic schemas for IQ agent API endpoints including:
- Compliance queries and analysis requests
- GraphRAG response structures
- Memory management operations
- Risk assessment and reporting
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from api.schemas.base import BaseSchema, StandardResponse


class ComplianceQueryRequest(BaseSchema):
    """Request schema for compliance queries to IQ agent"""

    query: str = Field(
        ...,
        description="Natural language compliance query",
        min_length=1,
        max_length=2000,
        example="What are the GDPR compliance gaps for our data processing activities?",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context for the query (regulations, business functions, etc.)",
        example={
            "business_functions": ["data_processing", "customer_onboarding"],
            "regulations": ["GDPR", "DPA2018"],
            "risk_tolerance": "high",
        },
    )
    include_graph_analysis: bool = Field(
        default=True,
        description="Whether to include detailed graph analysis in response",
    )
    include_recommendations: bool = Field(
        default=True,
        description="Whether to include actionable recommendations",
    )


class GraphContext(BaseSchema):
    """Graph analysis context from IQ's GraphRAG processing"""

    nodes_traversed: int = Field(..., description="Number of graph nodes analyzed")
    patterns_detected: List[Dict[str, Any]] = Field(
        ...,
        description="Compliance patterns detected during analysis",
    )
    memories_accessed: List[str] = Field(..., description="IDs of relevant memories accessed")
    learnings_applied: int = Field(..., description="Number of learning insights applied")


class ComplianceSummary(BaseSchema):
    """High-level compliance status summary"""

    risk_posture: str = Field(..., description="Overall risk posture", example="HIGH")
    compliance_score: float = Field(
        ...,
        description="Overall compliance coverage score (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    top_gaps: List[str] = Field(..., description="Top compliance gaps identified", max_items=5)
    immediate_actions: List[str] = Field(..., description="Immediate actions required", max_items=5)


class ActionPlan(BaseSchema):
    """Individual action in compliance plan"""

    action_id: str = Field(..., description="Unique action identifier")
    action_type: str = Field(..., description="Type of action")
    target: str = Field(..., description="Action target/objective")
    priority: str = Field(..., description="Action priority level")
    regulation: str = Field(..., description="Related regulation code")
    risk_level: str = Field(..., description="Associated risk level")
    cost_estimate: float = Field(..., description="Estimated implementation cost")
    timeline: str = Field(..., description="Estimated timeline")
    graph_reference: str = Field(..., description="Reference to graph node/relationship")


class ComplianceArtifacts(BaseSchema):
    """Detailed compliance analysis artifacts"""

    compliance_posture: Dict[str, Any] = Field(
        ...,
        description="Detailed compliance posture analysis",
    )
    action_plan: List[ActionPlan] = Field(..., description="Prioritized action plan")
    risk_assessment: Dict[str, Any] = Field(..., description="Risk assessment details")


class ComplianceEvidence(BaseSchema):
    """Evidence of compliance controls and execution"""

    controls_executed: int = Field(..., description="Number of controls executed")
    evidence_stored: int = Field(..., description="Number of evidence items stored")
    metrics_updated: int = Field(..., description="Number of metrics updated")


class NextAction(BaseSchema):
    """Next recommended action"""

    action: str = Field(..., description="Action description")
    priority: str = Field(..., description="Priority level")
    owner: str = Field(..., description="Responsible party")
    graph_reference: str = Field(..., description="Graph reference")


class IQAgentResponse(BaseSchema):
    """Complete IQ agent response with GraphRAG analysis"""

    status: str = Field(..., description="Response status")
    timestamp: str = Field(..., description="Response timestamp")

    summary: ComplianceSummary = Field(..., description="High-level compliance summary")
    artifacts: ComplianceArtifacts = Field(..., description="Detailed compliance artifacts")
    graph_context: GraphContext = Field(..., description="Graph analysis context")
    evidence: ComplianceEvidence = Field(..., description="Evidence and execution details")
    next_actions: List[NextAction] = Field(..., description="Recommended next actions", max_items=5)
    llm_response: str = Field(..., description="Natural language response from IQ")


class MemoryStoreRequest(BaseSchema):
    """Request to store memory in IQ's knowledge base"""

    memory_type: str = Field(
        ...,
        description="Type of memory to store",
        example="compliance_insight",
    )
    content: Dict[str, Any] = Field(..., description="Memory content to store")
    importance_score: float = Field(
        default=0.5,
        description="Importance score for memory retention",
        ge=0.0,
        le=1.0,
    )
    tags: Optional[List[str]] = Field(default=None, description="Tags for memory categorization")


class MemoryRetrievalRequest(BaseSchema):
    """Request to retrieve memories from IQ's knowledge base"""

    query: str = Field(..., description="Query for memory retrieval")
    max_memories: int = Field(
        default=10,
        description="Maximum number of memories to retrieve",
        ge=1,
        le=50,
    )
    relevance_threshold: float = Field(
        default=0.5,
        description="Minimum relevance threshold",
        ge=0.0,
        le=1.0,
    )


class MemoryNode(BaseSchema):
    """Individual memory node structure"""

    id: str = Field(..., description="Memory identifier")
    memory_type: str = Field(..., description="Type of memory")
    content: Dict[str, Any] = Field(..., description="Memory content")
    timestamp: datetime = Field(..., description="Memory creation timestamp")
    importance_score: float = Field(..., description="Importance score")
    access_count: int = Field(..., description="Number of times accessed")
    tags: List[str] = Field(..., description="Memory tags")
    confidence_score: float = Field(..., description="Confidence score")


class MemoryRetrievalResponse(BaseSchema):
    """Response from memory retrieval operation"""

    query_id: str = Field(..., description="Query identifier")
    retrieved_memories: List[MemoryNode] = Field(..., description="Retrieved memory nodes")
    relevance_scores: List[float] = Field(
        ...,
        description="Relevance scores for retrieved memories",
    )
    total_memories_searched: int = Field(..., description="Total number of memories searched")
    retrieval_strategy: str = Field(..., description="Strategy used for retrieval")
    confidence_score: float = Field(..., description="Overall confidence in results")


class GraphInitializationRequest(BaseSchema):
    """Request to initialize compliance graph"""

    clear_existing: bool = Field(default=False, description="Whether to clear existing graph data")
    load_sample_data: bool = Field(
        default=True,
        description="Whether to load sample compliance data",
    )


class GraphInitializationResponse(BaseSchema):
    """Response from graph initialization"""

    status: str = Field(..., description="Initialization status")
    timestamp: str = Field(..., description="Initialization timestamp")
    nodes_created: Dict[str, int] = Field(..., description="Count of nodes created by type")
    relationships_created: int = Field(..., description="Number of relationships created")
    message: str = Field(..., description="Status message")


class HealthCheckResponse(BaseSchema):
    """IQ agent health check response"""

    status: str = Field(..., description="Agent status")
    neo4j_connected: bool = Field(..., description="Neo4j connection status")
    graph_statistics: Dict[str, Any] = Field(..., description="Graph database statistics")
    memory_statistics: Dict[str, Any] = Field(..., description="Memory system statistics")
    last_query_time: Optional[datetime] = Field(
        default=None,
        description="Time of last query processed",
    )


# Response type aliases for FastAPI
ComplianceQueryResponse = StandardResponse[IQAgentResponse]
MemoryStoreResponse = StandardResponse[Dict[str, str]]
MemoryRetrievalResponseWrapper = StandardResponse[MemoryRetrievalResponse]
GraphInitializationResponseWrapper = StandardResponse[GraphInitializationResponse]
IQHealthCheckResponse = StandardResponse[HealthCheckResponse]
