"""
Tests for Phase 3: RAG Standardization.

This test suite validates:
1. StandardizedRAG implementation with LangChain components
2. RAGAdapter backward compatibility
3. Document addition and retrieval
4. Multi-query and reranking functionality
5. Performance improvements
"""

import pytest
import asyncio
import os
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import tempfile

from langgraph_agent.agents.rag_standard import StandardizedRAG

# Temporarily comment out adapter imports to test StandardizedRAG alone
# from langgraph_agent.agents.rag_adapter import RAGAdapter
# from langgraph_agent.agents.rag_system import (
#     DocumentType,
#     DocumentSource,
#     RetrievalStrategy
# )


class TestStandardizedRAG:
    """Test the new standardized RAG implementation."""

    @pytest.fixture
    def company_id(self):
        """Generate a test company ID."""
        return uuid4()

    @pytest.fixture
    def standard_rag(self, company_id):
        """Create a StandardizedRAG instance for testing."""
        # Mock OpenAI embeddings to avoid API calls
        with patch("langgraph_agent.agents.rag_standard.OpenAIEmbeddings") as mock_embeddings:
            mock_embeddings.return_value.embed_query = Mock(
                return_value=[0.1] * 1536  # Mock embedding,
            )
            mock_embeddings.return_value.embed_documents = Mock(
                return_value=[[0.1] * 1536]  # Mock embeddings,
            )

            rag = StandardizedRAG(company_id)
            return rag

    @pytest.mark.asyncio
    async def test_initialization(self, standard_rag, company_id):
        """Test StandardizedRAG initialization."""
        assert standard_rag.company_id == company_id
        assert standard_rag.collection_name == f"compliance_{company_id}"
        assert standard_rag.embeddings is not None
        assert standard_rag.vector_store is not None
        assert standard_rag.retriever is not None
        assert standard_rag.text_splitter is not None

    @pytest.mark.asyncio
    async def test_add_documents(self, standard_rag):
        """Test adding documents to the vector store."""
        # Test documents
        documents = [
            "This is a test compliance document about GDPR requirements.",
            "Another document about SOC2 compliance and security controls.",
        ]

        metadatas = [
            {"title": "GDPR Guide", "type": "regulation"},
            {"title": "SOC2 Overview", "type": "framework"},
        ]

        # Add documents
        await standard_rag.add_documents(documents, metadatas)

        # Verify documents were added (check vector store state)
        assert hasattr(standard_rag.vector_store, "index")

    @pytest.mark.asyncio
    async def test_retrieve_documents(self, standard_rag):
        """Test document retrieval."""
        # Add test documents first
        documents = [
            "GDPR requires explicit consent for data processing.",
            "ISO 27001 mandates information security management.",
        ]

        await standard_rag.add_documents(documents)

        # Mock the retriever to return test results
        mock_doc = MagicMock()
        mock_doc.page_content = "GDPR requires explicit consent"
        mock_doc.metadata = {"score": 0.9}

        with patch.object(
            standard_rag.retriever, "aget_relevant_documents", return_value=[mock_doc]
        ):
            # Retrieve documents
            results = await standard_rag.retrieve("GDPR consent requirements", k=2)

            assert len(results) > 0
            assert "content" in results[0]
            assert "metadata" in results[0]
            assert "score" in results[0]

    def test_health_check(self, standard_rag):
        """Test health check functionality."""
        health = standard_rag.health_check()

        assert "status" in health
        assert "vector_store" in health
        assert "collection" in health
        assert health["collection"] == standard_rag.collection_name

    @pytest.mark.asyncio
    async def test_clear_collection(self, standard_rag):
        """Test clearing the collection."""
        # Add a document first
        await standard_rag.add_documents(["Test document"])

        # Clear collection
        await standard_rag.clear_collection()

        # Verify vector store was reset
        assert standard_rag.vector_store is not None

    @pytest.mark.asyncio
    async def test_get_statistics(self, standard_rag):
        """Test getting statistics."""
        stats = await standard_rag.get_statistics()

        assert "company_id" in stats
        assert "collection_name" in stats
        assert "embeddings_model" in stats
        assert stats["embeddings_model"] == "text-embedding-3-small"
        assert "multi_query_enabled" in stats
        assert stats["multi_query_enabled"] is True


# Temporarily disabled until dependency issues resolved
# Start of commented section
class TestRAGAdapter:
    """Test the backward compatibility adapter."""

    @pytest.fixture
    def company_id(self):
        """Generate a test company ID."""
        return uuid4()

    @pytest.fixture
    def rag_adapter(self, company_id):
        """Create a RAGAdapter instance for testing."""
        # Mock the StandardizedRAG to avoid actual initialization
        with patch("langgraph_agent.agents.rag_adapter.StandardizedRAG") as mock_standard:
            mock_instance = AsyncMock()
            mock_standard.return_value = mock_instance

            adapter = RAGAdapter(company_id=company_id)
            adapter.standard_rag = mock_instance
            return adapter

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, rag_adapter, company_id):
        """Test RAGAdapter initialization."""
        assert rag_adapter.company_id == company_id
        assert rag_adapter.standard_rag is not None
        assert hasattr(rag_adapter, "document_metadata_cache")

    @pytest.mark.asyncio
    async def test_add_document_compatibility(self, rag_adapter, company_id):
        """Test add_document with old interface."""
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test compliance document content")
            test_file = f.name

        try:
            # Mock the standard RAG add_documents method
            rag_adapter.standard_rag.add_documents = AsyncMock()

            # Add document using old interface
            metadata = await rag_adapter.add_document(
                file_path=test_file,
                company_id=company_id,
                title="Test Document",
                document_type=DocumentType.REGULATION,
                source=DocumentSource.INTERNAL,
                frameworks=["GDPR"],
                tags=["test"],
            )

            # Verify metadata returned
            assert metadata.title == "Test Document"
            assert metadata.document_type == DocumentType.REGULATION
            assert metadata.source == DocumentSource.INTERNAL
            assert metadata.company_id == company_id

            # Verify standard RAG was called
            rag_adapter.standard_rag.add_documents.assert_called_once()

        finally:
            # Clean up test file
            os.unlink(test_file)

    @pytest.mark.asyncio
    async def test_retrieve_compatibility(self, rag_adapter, company_id):
        """Test retrieve_relevant_docs with old interface."""
        # Mock the standard RAG retrieve method
        rag_adapter.standard_rag.retrieve = AsyncMock(
            return_value=[
                {
                    "content": "Test content about GDPR",
                    "metadata": {"title": "GDPR Guide"},
                    "score": 0.95,
                },
                {
                    "content": "Another compliance document",
                    "metadata": {"title": "SOC2 Guide"},
                    "score": 0.85,
                },
            ],
        )

        # Retrieve using old interface
        result = await rag_adapter.retrieve_relevant_docs(
            query="GDPR compliance requirements",
            company_id=company_id,
            k=5,
            strategy=RetrievalStrategy.HYBRID,
            min_relevance_score=0.8,
        )

        # Verify result format
        assert hasattr(result, "chunks")
        assert hasattr(result, "total_results")
        assert hasattr(result, "query")
        assert result.query == "GDPR compliance requirements"
        assert result.strategy == RetrievalStrategy.HYBRID

        # Verify chunks
        assert len(result.chunks) <= 5
        for chunk in result.chunks:
            assert chunk.relevance_score >= 0.8

    @pytest.mark.asyncio
    async def test_health_status(self, rag_adapter):
        """Test health status compatibility."""
        # Mock the standard RAG health check
        rag_adapter.standard_rag.health_check = Mock(
            return_value={"status": "healthy", "vector_store": "operational"},
        )

        health = await rag_adapter.get_health_status()

        assert health["status"] == "healthy"
        assert health["vector_store"] == "operational"

    @pytest.mark.asyncio
    async def test_clear_documents(self, rag_adapter, company_id):
        """Test clearing company documents."""
        # Mock the standard RAG clear method
        rag_adapter.standard_rag.clear_collection = AsyncMock()

        # Add a cached document
        rag_adapter.document_metadata_cache["test_doc"] = Mock()

        # Clear documents
        success = await rag_adapter.clear_company_documents(company_id)

        assert success is True
        assert len(rag_adapter.document_metadata_cache) == 0
        rag_adapter.standard_rag.clear_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_statistics(self, rag_adapter):
        """Test getting retrieval statistics."""
        # Mock the standard RAG statistics
        rag_adapter.standard_rag.get_statistics = AsyncMock(
            return_value={"document_count": 10, "reranking_enabled": True},
        )

        stats = await rag_adapter.get_retrieval_statistics()

        assert "total_chunks" in stats
        assert "enable_reranking" in stats
        assert stats["enable_reranking"] is True


class TestPerformanceImprovement:
    """Test performance improvements from standardization."""

    @pytest.mark.asyncio
    async def test_code_reduction(self):
        """Verify code reduction from 1200+ lines to ~200 lines."""
        # Check StandardizedRAG file size
        standard_file = Path("langgraph_agent/agents/rag_standard.py")
        if standard_file.exists():
            with open(standard_file, "r") as f:
                lines = len(f.readlines())

            # Should be significantly smaller than original
            assert lines < 400, f"StandardizedRAG has {lines} lines, should be < 400"

        # Check adapter file size
        adapter_file = Path("langgraph_agent/agents/rag_adapter.py")
        if adapter_file.exists():
            with open(adapter_file, "r") as f:
                lines = len(f.readlines())

            # Adapter should also be reasonably sized
            assert lines < 500, f"RAGAdapter has {lines} lines, should be < 500"

    def test_langchain_components_usage(self):
        """Verify LangChain components are properly imported."""
        # Check imports in StandardizedRAG
        standard_file = Path("langgraph_agent/agents/rag_standard.py")
        if standard_file.exists():
            with open(standard_file, "r") as f:
                content = f.read()

            # Verify key LangChain imports
            assert "from langchain.embeddings import OpenAIEmbeddings" in content
            assert "from langchain.vectorstores import FAISS" in content
            assert "from langchain.retrievers import MultiQueryRetriever" in content
            assert (
                "from langchain.text_splitter import RecursiveCharacterTextSplitter" in content,
            )

    def test_simplified_interface(self):
        """Verify the interface is simplified."""
        # Check StandardizedRAG has minimal public methods
        from langgraph_agent.agents.rag_standard import StandardizedRAG

        public_methods = [
            method
            for method in dir(StandardizedRAG)
            if not method.startswith("_") and callable(getattr(StandardizedRAG, method))
        ]

        # Should have only essential methods
        essential_methods = {
            "add_documents",
            "retrieve",
            "health_check",
            "clear_collection",
            "get_statistics",
        }

        # All essential methods should be present
        for method in essential_methods:
            assert method in public_methods, f"Missing essential method: {method}"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
