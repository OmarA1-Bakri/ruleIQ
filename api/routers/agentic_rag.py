"""

# Constants
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_SERVICE_UNAVAILABLE = 503


FastAPI router for Agentic RAG endpoints
Provides seamless integration with LangGraph and Pydantic AI documentation
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import logging
from services.agentic_rag import AgenticRAGSystem, AgenticRAGResponse
from api.dependencies.auth import get_current_active_user
from database.user import User
from api.middleware.rate_limiter import rate_limit
from api.schemas.base import StandardResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Agentic RAG"])


class DocumentationQueryRequest(BaseModel):
    query: str = Field(
        ..., min_length=1, max_length=1000, description="Question about LangGraph or Pydantic AI"
    )
    source_filter: Optional[str] = Field(
        None, description="Filter by source: 'langgraph', 'pydantic_ai', etc."
    )
    query_type: str = Field(
        "documentation", description="Type of query: 'documentation', 'code_examples', 'hybrid'"
    )
    max_results: int = Field(5, ge=1, le=20, description="Maximum number of results to return")


class ProcessDocumentationRequest(BaseModel):
    force_reprocess: bool = Field(False, description="Force reprocessing even if already indexed")


class FrameworkGuidanceRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200, description="Topic to get guidance on")
    framework: str = Field(..., description="Framework: 'langgraph' or 'pydantic_ai'")


_rag_system = None


def get_rag_system() -> AgenticRAGSystem:
    """Get or create the RAG system instance"""
    global _rag_system
    if _rag_system is None:
        _rag_system = AgenticRAGSystem()
    return _rag_system


@router.post(
    "/find-examples",
    response_model=StandardResponse[AgenticRAGResponse],
    dependencies=[Depends(rate_limit(requests_per_minute=20))],
)
async def find_code_examples(
    request: FrameworkGuidanceRequest,
    current_user: User = Depends(get_current_active_user),
    rag_system: AgenticRAGSystem = Depends(get_rag_system),
) -> StandardResponse[AgenticRAGResponse]:
    """
    Find specific code examples for a task

    Searches specifically through extracted code examples to find:
    - Implementation patterns for specific tasks
    - Working code snippets you can adapt
    - Examples of best practices in action
    """
    try:
        if not rag_system.use_agentic_rag:
            raise HTTPException(
                status_code=HTTP_SERVICE_UNAVAILABLE,
                detail="Code example search requires agentic RAG to be enabled",
            )
        example_query = f"Show me code examples for: {request.topic}"
        result = await rag_system.query_documentation(
            query=example_query,
            source_filter=request.framework,
            query_type="code_examples",
            max_results=5,
        )
        return StandardResponse(
            success=True, data=result, message=f"Found {len(result.sources)} relevant code examples"
        )
    except Exception as e:
        logger.error("Error finding examples: %s" % str(e))
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail=f"Failed to find examples: {str(e)}"
        )


@router.post(
    "/fact-check",
    response_model=Dict[str, Any],
    summary="Fact-check a RAG response",
    description="Run fact-checking and self-criticism analysis on a RAG response",
)
async def fact_check_response(
    request: DocumentationQueryRequest,
    quick_check: bool = Query(True, description="Use quick fact-check for faster response"),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Fact-check a RAG response using the self-critic system

    Args:
        request: The query and optional source filter
        quick_check: Whether to use quick fact-checking (default: True)

    Returns:
        Fact-check results with validation and quality scores
    """
    try:
        logger.info("Fact-checking request for query: %s" % request.query)
        from services.agentic_integration import get_agentic_service

        agentic_service = await get_agentic_service()
        rag_response = await agentic_service.query_documentation(
            query=request.query,
            source_filter=request.source_filter,
            query_type=getattr(request, "query_type", "documentation"),
        )
        fact_check_result = await agentic_service.fact_check_response(
            response_text=rag_response["answer"],
            sources=rag_response["sources"],
            original_query=request.query,
            quick_check=quick_check,
        )
        return {
            "success": True,
            "rag_response": rag_response,
            "fact_check": fact_check_result,
            "analysis": {
                "query": request.query,
                "fact_check_type": fact_check_result.get("fact_check_type", "quick"),
                "approved": fact_check_result["approved"],
                "confidence": fact_check_result["confidence"],
                "recommendations": fact_check_result.get("recommendations", []),
            },
        }
    except Exception as e:
        logger.error("Error in fact-check endpoint: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail=f"Fact-checking failed: {str(e)}"
        )


@router.post(
    "/query-with-validation",
    response_model=Dict[str, Any],
    summary="Query documentation with automatic validation",
    description="Query RAG system with built-in fact-checking and validation",
)
async def query_with_validation(
    request: DocumentationQueryRequest,
    enable_fact_check: bool = Query(True, description="Enable fact-checking validation"),
    quick_validation: bool = Query(True, description="Use quick validation for better performance"),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Query documentation with automatic fact-checking validation

    This endpoint combines RAG querying with validation to provide
    high-quality, fact-checked responses suitable for production use.

    Args:
        request: The query parameters
        enable_fact_check: Whether to run fact-checking (default: True)
        quick_validation: Use quick validation for better performance (default: True)

    Returns:
        RAG response with validation results and trust scores
    """
    try:
        logger.info("Validated query request: %s" % request.query)
        from services.agentic_integration import get_agentic_service

        agentic_service = await get_agentic_service()
        result = await agentic_service.query_documentation_with_validation(
            query=request.query,
            source_filter=request.source_filter,
            query_type=getattr(request, "query_type", "documentation"),
            enable_fact_check=enable_fact_check,
            quick_validation=quick_validation,
        )
        return {
            "success": True,
            "query": request.query,
            "answer": result["answer"],
            "confidence": result["confidence"],
            "trust_score": result["trust_score"],
            "approved_for_use": result["approved_for_use"],
            "sources": result["sources"],
            "processing_time": result["processing_time"],
            "validation": result["validation"],
            "metadata": {
                "query_type": result["query_type"],
                "fact_check_enabled": enable_fact_check,
                "validation_type": "quick" if quick_validation else "comprehensive",
            },
        }
    except Exception as e:
        logger.error("Error in validated query endpoint: %s" % e)
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail=f"Validated query failed: {str(e)}"
        )
