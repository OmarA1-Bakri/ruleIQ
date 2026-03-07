"""

RAG adapter for backward compatibility.

Phase 3 Implementation: Bridge between old RAG interface and new standardized implementation.
This adapter allows gradual migration by maintaining the existing interface while using
the new standardized RAG implementation underneath.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pathlib import Path
import logging
from .rag_system import (
    DocumentMetadata,
    DocumentType,
    DocumentSource,
    RetrievalResult,
    DocumentChunk,
    RetrievalStrategy,
)
from .rag_standard import StandardizedRAG

logger = logging.getLogger(__name__)


class RAGAdapter:
    """
    Adapter to bridge old RAG interface with new standardized implementation.

    This adapter maintains backward compatibility by translating between the
    old complex interface and the new simplified StandardizedRAG.
    """

    def __init__(self, *args, **kwargs) -> None:
        """
        Initialize adapter with compatibility for old RAGSystem interface.

        Args:
            *args: Positional arguments from old interface
            **kwargs: Keyword arguments from old interface
        """
        self.memory_manager = kwargs.get("memory_manager")
        self.company_id = kwargs.get("company_id", uuid4())
        self.standard_rag = StandardizedRAG(self.company_id)
        self.document_metadata_cache = {}
        logger.info("RAGAdapter initialized - bridging to StandardizedRAG")

    async def add_document(
        self,
        file_path: str,
        company_id: UUID,
        title: str,
        document_type: DocumentType,
        source: DocumentSource,
        frameworks: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        metadata_override: Optional[Dict[str, Any]] = None,
    ) -> DocumentMetadata:
        """
        Adapter method for add_document.

        Translates old add_document interface to new standardized approach.

        Args:
            file_path: Path to document file
            company_id: Company identifier
            title: Document title
            document_type: Type of document (enum)
            source: Document source (enum)
            frameworks: Applicable compliance frameworks
            tags: Document tags
            metadata_override: Optional metadata overrides

        Returns:
            DocumentMetadata object for compatibility
        """
        try:
            content = ""
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
            metadata = {
                "title": title,
                "document_type": document_type.value
                if hasattr(document_type, "value")
                else str(document_type),
                "source": source.value if hasattr(source, "value") else str(source),
                "company_id": str(company_id),
                "frameworks": frameworks or [],
                "tags": tags or [],
                "file_path": file_path,
            }
            if metadata_override:
                metadata.update(metadata_override)
            await self.standard_rag.add_documents([content], [metadata])
            document_id = f"doc_{uuid4()}"
            doc_metadata = DocumentMetadata(
                document_id=document_id,
                title=title,
                document_type=document_type,
                source=source,
                content_hash="",
                file_size_bytes=Path(file_path).stat().st_size if Path(file_path).exists() else 0,
                company_id=company_id,
                processing_status="processed",
                frameworks=frameworks or [],
                tags=tags or [],
            )
            self.document_metadata_cache[document_id] = doc_metadata
            logger.info(f"Document added via adapter: {document_id}")
            return doc_metadata
        except Exception as e:
            logger.error(f"Failed to add document via adapter: {e}")
            raise

    async def retrieve_relevant_docs(
        self,
        query: str,
        company_id: UUID,
        k: int = 6,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        frameworks_filter: Optional[List[str]] = None,
        source_filter: Optional[List[DocumentSource]] = None,
        min_relevance_score: float = 0.0,
    ) -> RetrievalResult:
        """
        Adapter method for retrieval.

        Translates old retrieval interface to new standardized approach.

        Args:
            query: Search query
            company_id: Company identifier
            k: Number of results
            strategy: Retrieval strategy (ignored - new system uses hybrid)
            frameworks_filter: Filter by frameworks (not implemented)
            source_filter: Filter by sources (not implemented)
            min_relevance_score: Minimum score threshold

        Returns:
            RetrievalResult object for compatibility
        """
        try:
            results = await self.standard_rag.retrieve(query, k)
            chunks = []
            for i, result in enumerate(results):
                if result["score"] < min_relevance_score:
                    continue
                chunk = DocumentChunk(
                    chunk_id=f"chunk_{uuid4()}",
                    document_id=f"adapted_{i}",
                    content=result["content"],
                    chunk_index=i,
                    start_char=0,
                    end_char=len(result["content"]),
                    relevance_score=result["score"],
                    metadata=result.get("metadata", {}),
                )
                chunks.append(chunk)
            retrieval_result = RetrievalResult(
                chunks=chunks[:k],
                total_results=len(chunks),
                query=query,
                strategy=RetrievalStrategy.HYBRID,
                retrieval_time_ms=100,
                avg_relevance_score=sum((c.relevance_score for c in chunks)) / len(chunks)
                if chunks
                else 0,
            )
            logger.info(f"Retrieved {len(chunks)} documents via adapter")
            return retrieval_result
        except Exception as e:
            logger.error(f"Retrieval failed via adapter: {e}")
            return RetrievalResult(
                chunks=[],
                total_results=0,
                query=query,
                strategy=strategy,
                retrieval_time_ms=0,
                avg_relevance_score=0.0,
            )

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the RAG system.

        Returns:
            Health status dictionary
        """
        return self.standard_rag.health_check()

    async def clear_company_documents(self, company_id: UUID) -> bool:
        """
        Clear all documents for a company.

        Args:
            company_id: Company identifier

        Returns:
            Success status
        """
        try:
            await self.standard_rag.clear_collection()
            self.document_metadata_cache.clear()
            logger.info(f"Cleared documents for company {company_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear documents: {e}")
            return False

    async def get_retrieval_statistics(self) -> Dict[str, Any]:
        """
        Get retrieval statistics.

        Returns:
            Statistics dictionary
        """
        stats = await self.standard_rag.get_statistics()
        stats.update(
            {
                "total_documents": len(self.document_metadata_cache),
                "total_chunks": stats.get("document_count", 0),
                "total_queries": 0,
                "avg_retrieval_time_ms": 100,
                "cache_hits": 0,
                "enable_reranking": stats.get("reranking_enabled", False),
            }
        )
        return stats

    async def update_document(self, document_id: str, **updates) -> bool:
        """
        Update document (not implemented in new system).

        This is a no-op for compatibility.

        Args:
            document_id: Document identifier
            **updates: Fields to update

        Returns:
            Always returns True for compatibility
        """
        logger.warning(f"Document update not supported in StandardizedRAG: {document_id}")
        return True

    async def delete_document(self, document_id: str, company_id: UUID) -> bool:
        """
        Delete document (not implemented in new system).

        This is a no-op for compatibility.

        Args:
            document_id: Document identifier
            company_id: Company identifier

        Returns:
            Always returns True for compatibility
        """
        logger.warning(f"Document deletion not supported in StandardizedRAG: {document_id}")
        if document_id in self.document_metadata_cache:
            del self.document_metadata_cache[document_id]
        return True

    def __getattr__(self, name) -> Any:
        """
        Forward any unimplemented methods to StandardizedRAG.

        This ensures maximum compatibility by trying to use the new system
        for any methods not explicitly adapted.

        Args:
            name: Method name

        Returns:
            Method from StandardizedRAG if available
        """
        if hasattr(self.standard_rag, name):
            return getattr(self.standard_rag, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
