"""

IQ Agent API Router - GraphRAG Compliance Intelligence

Endpoints for interacting with IQ, the autonomous compliance orchestrator:
- Natural language compliance queries with graph analysis
- Memory management and knowledge retrieval
- Graph initialization and health monitoring
- Real-time compliance insights and recommendations
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies.auth import get_current_active_user
from api.dependencies.database import get_async_db
from api.middleware.ai_rate_limiter import ai_analysis_rate_limit
from api.schemas.iq_agent import (
    ComplianceQueryRequest,
    ComplianceQueryResponse,
    GraphInitializationRequest,
    GraphInitializationResponseWrapper,
    HealthCheckResponse,
    IQAgentResponse,
    IQHealthCheckResponse,
    MemoryRetrievalRequest,
    MemoryRetrievalResponseWrapper,
    MemoryStoreRequest,
    MemoryStoreResponse,
)
from database.user import User
from services.iq_agent import create_iq_agent, IQComplianceAgent
from services.neo4j_service import Neo4jGraphRAGService
from services.compliance_graph_initializer import initialize_compliance_graph
from services.ai.exceptions import AIServiceException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["IQ Agent - GraphRAG Intelligence"])
_iq_agent: Optional[IQComplianceAgent] = None
_neo4j_service: Optional[Neo4jGraphRAGService] = None


async def get_iq_agent() -> IQComplianceAgent:
    """Get or create IQ agent instance"""
    global _iq_agent, _neo4j_service
    if _iq_agent is None:
        try:
            _neo4j_service = Neo4jGraphRAGService()
            await _neo4j_service.connect()
            _iq_agent = await create_iq_agent(_neo4j_service)
            logger.info("IQ Agent initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize IQ Agent: %s" % str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"IQ Agent initialization failed: {str(e)}",
            )
    return _iq_agent


async def get_neo4j_service() -> Neo4jGraphRAGService:
    """Get Neo4j service instance"""
    global _neo4j_service
    if _neo4j_service is None:
        try:
            _neo4j_service = Neo4jGraphRAGService()
            await _neo4j_service.connect()
        except Exception as e:
            logger.error("Failed to initialize Neo4j service: %s" % str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Neo4j service initialization failed: {str(e)}",
            )
    return _neo4j_service


@router.post(
    "/query",
    response_model=ComplianceQueryResponse,
    summary="Query IQ Agent for Compliance Analysis",
    description="""
    Submit a natural language compliance query to IQ for comprehensive GraphRAG analysis.

    IQ leverages Neo4j graph database to provide:
    - Compliance gap analysis across regulations
    - Risk convergence detection and mitigation
    - Cross-jurisdictional impact assessment
    - Temporal regulatory change analysis
    - Enforcement learning from historical cases
    - Prioritized action plans with cost estimates

    Example queries:
    - "What are our GDPR compliance gaps in customer data processing?"
    - "How does the new DORA regulation affect our operational risk controls?"
    - "What enforcement patterns should we be aware of for 6AMLD compliance?"
    """,
    responses={
        (200): {"description": "Successful compliance analysis"},
        (400): {"description": "Invalid query format"},
        (503): {"description": "IQ Agent service unavailable"},
        (429): {"description": "Rate limit exceeded"},
    },
    dependencies=[Depends(ai_analysis_rate_limit)],
)
async def query_compliance_analysis(
    request: ComplianceQueryRequest,
    background_tasks: BackgroundTasks,
    iq_agent: IQComplianceAgent = Depends(get_iq_agent),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> ComplianceQueryResponse:
    """
    Process compliance query through IQ's GraphRAG intelligence loop
    """
    try:
        logger.info(
            "Processing compliance query from user %s: %s..."
            % (current_user.id, request.query[:100])
        )
        result = await iq_agent.process_query(user_query=request.query, context=request.context)
        iq_response = IQAgentResponse(
            status=result["status"],
            timestamp=result["timestamp"],
            summary=result["summary"],
            artifacts=result["artifacts"],
            graph_context=result["graph_context"],
            evidence=result["evidence"],
            next_actions=result["next_actions"],
            llm_response=result["llm_response"],
        )
        background_tasks.add_task(
            _log_query_metrics,
            user_id=current_user.id,
            query=request.query,
            response_status=result["status"],
            nodes_traversed=result["graph_context"]["nodes_traversed"],
        )
        return ComplianceQueryResponse(
            success=True, data=iq_response, message="Compliance analysis completed successfully"
        )
    except AIServiceException as e:
        logger.error("AI service error in compliance query: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI analysis failed: {str(e)}"
        )
    except Exception as e:
        logger.error("Unexpected error in compliance query: %s" % str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during compliance analysis",
        )


@router.post(
    "/memory/store",
    response_model=MemoryStoreResponse,
    summary="Store Knowledge in IQ's Memory",
    description="""
    Store compliance insights, patterns, or knowledge in IQ's persistent memory system.

    Memory types supported:
    - compliance_insight: Key compliance findings or patterns
    - enforcement_case: Lessons from enforcement actions
    - regulatory_change: Updates to regulations or requirements
    - risk_assessment: Risk analysis results
    - best_practice: Compliance best practices and guidelines
    """,
)
async def store_compliance_memory(
    request: MemoryStoreRequest,
    iq_agent: IQComplianceAgent = Depends(get_iq_agent),
    current_user: User = Depends(get_current_active_user),
) -> MemoryStoreResponse:
    """
    Store knowledge in IQ's memory system for future retrieval
    """
    try:
        memory_id = await iq_agent.memory_manager.store_conversation_memory(
            user_query=f"Knowledge storage by {current_user.email}",
            agent_response=str(request.content),
            compliance_context=request.content,
            importance_score=request.importance_score,
        )
        return MemoryStoreResponse(
            success=True,
            data={"memory_id": memory_id, "status": "stored"},
            message="Knowledge stored successfully in IQ's memory",
        )
    except Exception as e:
        logger.error("Error storing compliance memory: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store memory: {str(e)}",
        )


@router.post(
    "/memory/retrieve",
    response_model=MemoryRetrievalResponseWrapper,
    summary="Retrieve Relevant Memories",
    description="""
    Retrieve relevant memories from IQ's knowledge base based on query context.

    Uses sophisticated retrieval strategies:
    - Entity-based matching for regulations, domains, jurisdictions
    - Tag-based categorical retrieval
    - Semantic similarity matching
    - Temporal relevance scoring
    - Multi-strategy hybrid ranking
    """,
)
async def retrieve_compliance_memories(
    request: MemoryRetrievalRequest,
    iq_agent: IQComplianceAgent = Depends(get_iq_agent),
    current_user: User = Depends(get_current_active_user),
) -> MemoryRetrievalResponseWrapper:
    """
    Retrieve contextually relevant memories from IQ's knowledge base
    """
    try:
        result = await iq_agent.memory_manager.retrieve_contextual_memories(
            query=request.query,
            context={},
            max_memories=request.max_memories,
            relevance_threshold=request.relevance_threshold,
        )
        return MemoryRetrievalResponseWrapper(
            success=True,
            data=result,
            message=f"Retrieved {len(result.retrieved_memories)} relevant memories",
        )
    except Exception as e:
        logger.error("Error retrieving compliance memories: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve memories: {str(e)}",
        )


@router.post(
    "/graph/initialize",
    response_model=GraphInitializationResponseWrapper,
    summary="Initialize Compliance Graph",
    description="""
    Initialize or refresh the Neo4j compliance graph with CCO playbook data.

    This endpoint:
    - Creates graph schema with 20+ node types
    - Loads compliance domains, regulations, requirements, controls
    - Establishes relationships between entities
    - Populates enforcement cases and risk assessments
    - Sets up temporal patterns for regulatory changes

    **Warning**: This operation may take several minutes and will affect ongoing queries.
    """,
)
async def initialize_compliance_graph_endpoint(
    request: GraphInitializationRequest,
    background_tasks: BackgroundTasks,
    neo4j_service: Neo4jGraphRAGService = Depends(get_neo4j_service),
    current_user: User = Depends(get_current_active_user),
) -> GraphInitializationResponseWrapper:
    """
    Initialize compliance graph with CCO data
    """
    try:
        logger.info("Initializing compliance graph - user: %s" % current_user.email)
        background_tasks.add_task(
            _initialize_graph_background,
            clear_existing=request.clear_existing,
            load_sample_data=request.load_sample_data,
        )
        return GraphInitializationResponseWrapper(
            success=True,
            data={
                "status": "initiated",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "nodes_created": {},
                "relationships_created": 0,
                "message": "Graph initialization started in background",
            },
            message="Compliance graph initialization initiated",
        )
    except Exception as e:
        logger.error("Error initiating graph initialization: %s" % str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize graph: {str(e)}",
        )


@router.get(
    "/health",
    response_model=IQHealthCheckResponse,
    summary="IQ Agent Health Check",
    description="""
    Comprehensive health check for IQ agent and its dependencies:
    - Neo4j graph database connectivity
    - Graph statistics and node counts
    - Memory system status
    - Recent query performance
    - Agent operational status
    """,
)
async def iq_agent_health_check(
    include_stats: bool = Query(
        default=True, description="Include detailed statistics in response"
    ),
) -> IQHealthCheckResponse:
    """
    Health check for IQ agent and GraphRAG infrastructure
    """
    try:
        neo4j_connected = False
        graph_stats = {}
        try:
            neo4j_service = await get_neo4j_service()
            await neo4j_service.test_connection()
            neo4j_connected = True
            if include_stats:
                graph_stats = await neo4j_service.get_graph_statistics()
        except Exception as e:
            logger.warning("Neo4j health check failed: %s" % str(e))
        agent_status = "healthy"
        memory_stats = {}
        last_query_time = None
        try:
            iq_agent = await get_iq_agent()
            if include_stats:
                memory_stats = {
                    "total_memories": len(iq_agent.memory_manager.memory_store),
                    "clusters": len(iq_agent.memory_manager.clusters),
                    "memory_types": list(
                        set(
                            memory.memory_type.value
                            for memory in iq_agent.memory_manager.memory_store.values()
                        )
                    ),
                }
        except Exception as e:
            logger.warning("IQ agent health check failed: %s" % str(e))
            agent_status = "degraded"
        if neo4j_connected and agent_status == "healthy":
            overall_status = "healthy"
        elif neo4j_connected or agent_status == "healthy":
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        health_response = HealthCheckResponse(
            status=overall_status,
            neo4j_connected=neo4j_connected,
            graph_statistics=graph_stats,
            memory_statistics=memory_stats,
            last_query_time=last_query_time,
        )
        return IQHealthCheckResponse(
            success=True, data=health_response, message=f"IQ Agent status: {overall_status}"
        )
    except Exception as e:
        logger.error("Health check error: %s" % str(e))
        return IQHealthCheckResponse(
            success=False,
            data=HealthCheckResponse(
                status="error", neo4j_connected=False, graph_statistics={}, memory_statistics={}
            ),
            message=f"Health check failed: {str(e)}",
        )


@router.get(
    "/status",
    summary="IQ Agent Status Summary",
    description="""
    Quick status check for IQ agent operational readiness.
    Lightweight endpoint for monitoring and load balancer health checks.
    """,
)
async def iq_agent_status() -> Dict[str, Any]:
    """
    Quick status check for monitoring
    """
    try:
        await get_neo4j_service()
        await get_iq_agent()
        return {
            "status": "operational",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "IQ",
            "version": "1.0.0",
        }
    except Exception as e:
        logger.error("Status check failed: %s" % str(e))
        return {
            "status": "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "IQ",
            "error": str(e),
        }


async def _log_query_metrics(
    user_id: UUID, query: str, response_status: str, nodes_traversed: int
) -> None:
    """Log query metrics for monitoring"""
    try:
        logger.info(
            "IQ Query Metrics - User: %s, Status: %s, Nodes: %s, Query Length: %s"
            % (user_id, response_status, nodes_traversed, len(query))
        )
    except Exception as e:
        logger.error("Failed to log query metrics: %s" % str(e))


async def _initialize_graph_background(
    clear_existing: bool = False, load_sample_data: bool = True
) -> None:
    """Initialize compliance graph in background"""
    try:
        logger.info("Starting background graph initialization")
        result = await initialize_compliance_graph()
        logger.info("Graph initialization completed: %s" % result["status"])
    except Exception as e:
        logger.error("Background graph initialization failed: %s" % str(e))


async def cleanup_iq_agent() -> None:
    """Cleanup IQ agent resources on shutdown"""
    global _iq_agent, _neo4j_service
    try:
        if _neo4j_service:
            await _neo4j_service.close()
            logger.info("Neo4j service closed")
        _iq_agent = None
        _neo4j_service = None
    except Exception as e:
        logger.error("Error during IQ agent cleanup: %s" % str(e))
