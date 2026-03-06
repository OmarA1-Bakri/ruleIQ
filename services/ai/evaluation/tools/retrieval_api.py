"""Golden Dataset Retrieval API for AI Evaluation.

This module provides a REST API for querying the golden dataset using
semantic similarity search powered by Neo4j vector indexes.
"""

import os
import sys
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import requests
import uvicorn

# Add parent directory to path for imports
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
    ),
)

from services.ai.evaluation.tools.ingestion_fixed import GoldenDatasetIngestion, EmbeddingService

# Constants
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_NOT_FOUND = 404


class SearchRequest(BaseModel):
    """Request model for similarity search."""

    query: str = Field(..., description="Search query text")
    limit: int = Field(5, description="Maximum number of results", ge=1, le=20)
    min_score: float = Field(0.7, description="Minimum similarity score", ge=0.0, le=1.0)
    source_filter: Optional[str] = Field(None, description="Filter by source origin")


class SearchResult(BaseModel):
    """Response model for search results."""

    chunk_id: str
    doc_id: str
    content: str
    score: float
    source: str
    metadata: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    """Complete search response."""

    query: str
    results: List[SearchResult]
    total_results: int
    processing_time_ms: float


class IngestionRequest(BaseModel):
    """Request model for data ingestion."""

    file_path: str = Field(..., description="Path to golden dataset JSON file")


class IngestionResponse(BaseModel):
    """Response model for ingestion results."""

    success: bool
    documents_processed: int
    chunks_created: int
    embeddings_generated: int
    errors: List[str] = []


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    neo4j_connected: bool
    embedding_model: str
    vector_index_ready: bool


app = FastAPI(
    title="Golden Dataset Retrieval API",
    description="API for querying and managing golden datasets for AI evaluation",
    version="1.0.0",
)
ingestion_service = GoldenDatasetIngestion()
embedding_service = EmbeddingService()


@app.get("/health", response_model=HealthResponse)
async def health_check() -> Any:
    """Check health status of the API and dependencies."""
    try:
        driver = ingestion_service.neo4j.get_driver()
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            neo4j_connected = result.single() is not None
            index_result = session.run(
                """
                SHOW INDEXES
                WHERE name = 'golden_chunk_embeddings'
            """
            )
            vector_index_ready = len(list(index_result)) > 0
    except (ValueError, TypeError):
        neo4j_connected = False
        vector_index_ready = False
    return HealthResponse(
        status="healthy" if neo4j_connected else "degraded",
        neo4j_connected=neo4j_connected,
        embedding_model=embedding_service.model_name,
        vector_index_ready=vector_index_ready,
    )


@app.post("/search", response_model=SearchResponse)
async def search_golden_dataset(request: SearchRequest) -> Any:
    """Search the golden dataset using semantic similarity."""
    import time

    start_time = time.time()
    try:
        raw_results = ingestion_service.search_similar(query=request.query, limit=request.limit)
        filtered_results = []
        for result in raw_results:
            if result["score"] >= request.min_score:
                if request.source_filter is None or result["source"] == request.source_filter:
                    filtered_results.append(
                        SearchResult(
                            chunk_id=result["chunk_id"],
                            doc_id=result["doc_id"],
                            content=result["content"],
                            score=result["score"],
                            source=result["source"],
                        )
                    )
        processing_time = (time.time() - start_time) * 1000
        return SearchResponse(
            query=request.query,
            results=filtered_results,
            total_results=len(filtered_results),
            processing_time_ms=processing_time,
        )
    except (requests.RequestException, Exception, KeyError) as e:
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail=f"Search failed: {str(e)}"
        )


@app.post("/ingest", response_model=IngestionResponse)
async def ingest_golden_dataset(request: IngestionRequest) -> Any:
    """Ingest a new golden dataset from JSON file."""
    try:
        if not os.path.exists(request.file_path):
            raise HTTPException(
                status_code=HTTP_NOT_FOUND, detail=f"File not found: {request.file_path}"
            )
        result = ingestion_service.ingest_from_file(request.file_path)
        return IngestionResponse(
            success=result["success"],
            documents_processed=result["documents_processed"],
            chunks_created=result["chunks_created"],
            embeddings_generated=result["embeddings_generated"],
            errors=result.get("errors", []),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=HTTP_NOT_FOUND, detail=str(e))
    except (OSError, requests.RequestException, KeyError) as e:
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {str(e)}"
        )


@app.get("/stats")
async def get_dataset_statistics() -> Dict[str, Any]:
    """Get statistics about the golden dataset."""
    try:
        driver = ingestion_service.neo4j.get_driver()
        with driver.session() as session:
            doc_result = session.run(
                """
                MATCH (d:GoldenDocument)
                RETURN count(d) as document_count
            """
            )
            doc_count = doc_result.single()["document_count"]
            chunk_result = session.run(
                """
                MATCH (c:GoldenChunk)
                RETURN count(c) as chunk_count
            """
            )
            chunk_count = chunk_result.single()["chunk_count"]
            source_result = session.run(
                """
                MATCH (d:GoldenDocument)
                RETURN DISTINCT d.source as source
            """
            )
            sources = [record["source"] for record in source_result]
            docs_result = session.run(
                """
                MATCH (d:GoldenDocument)
                RETURN d.doc_id as doc_id, d.source as source
                ORDER BY d.doc_id
            """
            )
            documents = [{"doc_id": r["doc_id"], "source": r["source"]} for r in docs_result]
            return {
                "document_count": doc_count,
                "chunk_count": chunk_count,
                "unique_sources": sources,
                "documents": documents,
                "embedding_dimension": embedding_service.dimension,
                "embedding_model": embedding_service.model_name,
            }
    except (KeyError, IndexError) as e:
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail=f"Failed to get statistics: {str(e)}"
        )


@app.delete("/clear")
async def clear_golden_dataset() -> Dict[str, Any]:
    """Clear all golden dataset data from Neo4j."""
    try:
        driver = ingestion_service.neo4j.get_driver()
        with driver.session() as session:
            result = session.run(
                """
                MATCH (d:GoldenDocument)
                DETACH DELETE d
            """
            )
            session.run(
                """
                MATCH (c:GoldenChunk)
                WHERE NOT (()-[:HAS_CHUNK]->(c))
                DELETE c
            """
            )
            return {
                "message": "Golden dataset cleared successfully",
                "deleted_documents": result.consume().counters.nodes_deleted,
            }
    except (KeyError, IndexError) as e:
        raise HTTPException(
            status_code=HTTP_INTERNAL_SERVER_ERROR, detail=f"Failed to clear dataset: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
