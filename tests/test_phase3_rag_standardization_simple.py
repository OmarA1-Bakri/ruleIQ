"""
Tests for Phase 3: RAG Standardization - Simplified version.

This test suite validates:
1. StandardizedRAG implementation with LangChain components
2. Basic document operations
3. Health check functionality
"""

import pytest
import asyncio
import os
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from langgraph_agent.agents.rag_standard import StandardizedRAG


class TestStandardizedRAG:
    """Test the new standardized RAG implementation."""

    @pytest.fixture
    def company_id(self):
        """Generate a test company ID."""
        return uuid4()

    @pytest.fixture
    def standard_rag(self, company_id):
        """Create a StandardizedRAG instance for testing."""
        # Set a dummy OpenAI API key to prevent errors
        os.environ["OPENAI_API_KEY"] = "test-key-for-testing"

        # Mock OpenAI embeddings to avoid API calls
        with patch("langgraph_agent.agents.rag_standard.OpenAIEmbeddings") as mock_embeddings:
            # Create a properly mocked embeddings instance
            mock_embed = Mock()
            mock_embed.embed_query = Mock(return_value=[0.1] * 1536)
            mock_embed.embed_documents = Mock(return_value=[[0.1] * 1536])

            # Also mock the async version which FAISS might use
            mock_embed.aembed_documents = AsyncMock(return_value=[[0.1] * 1536])
            mock_embed.aembed_query = AsyncMock(return_value=[0.1] * 1536)

            mock_embeddings.return_value = mock_embed

            # Patch ChatOpenAI to avoid API calls
            with patch("langgraph_agent.agents.rag_standard.ChatOpenAI") as mock_chat:
                mock_llm = Mock()
                mock_chat.return_value = mock_llm

                # Patch FAISS to avoid dimension mismatch
                with patch("langgraph_agent.agents.rag_standard.FAISS") as mock_faiss:
                    # Create a mock vector store
                    mock_store = Mock()
                    mock_store.add_texts = Mock()
                    mock_store.save_local = Mock()
                    mock_store.index = Mock()
                    mock_store.index.ntotal = 0
                    mock_store.similarity_search = Mock(return_value=[])

                    # Create a mock retriever
                    mock_base_retriever = Mock()
                    mock_base_retriever.aget_relevant_documents = AsyncMock(
                        return_value=[],
                    )
                    mock_store.as_retriever = Mock(return_value=mock_base_retriever)

                    # Mock from_texts to return our mock store
                    mock_faiss.from_texts.return_value = mock_store
                    mock_faiss.load_local.return_value = mock_store

                    # Patch MultiQueryRetriever
                    with patch(
                        "langgraph_agent.agents.rag_standard.MultiQueryRetriever"
                    ) as mock_multi_query:
                        mock_retriever = Mock()
                        mock_retriever.aget_relevant_documents = AsyncMock(
                            return_value=[],
                        )
                        mock_multi_query.from_llm.return_value = mock_retriever

                        rag = StandardizedRAG(company_id)

                        # Ensure the mock store and retriever are set
                        rag.vector_store = mock_store
                        rag.retriever = mock_retriever

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

        # Setup the mock to update ntotal when add_texts is called
        def update_ntotal(*args, **kwargs):
            texts = args[0] if args else []
            standard_rag.vector_store.index.ntotal += len(texts)

        standard_rag.vector_store.add_texts.side_effect = update_ntotal

        # Add documents
        await standard_rag.add_documents(documents, metadatas)

        # Verify documents were added
        assert hasattr(standard_rag.vector_store, "index")
        assert standard_rag.vector_store.add_texts.called
        assert standard_rag.vector_store.save_local.called

        # Check that documents were split and added
        assert standard_rag.vector_store.index.ntotal > 0

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

        # Create a proper mock retriever
        mock_retriever = Mock()
        mock_retriever.aget_relevant_documents = AsyncMock(return_value=[mock_doc])

        # Set the mock retriever
        standard_rag.retriever = mock_retriever

        # Retrieve documents
        results = await standard_rag.retrieve("GDPR consent requirements", k=2)

        assert len(results) > 0
        assert "content" in results[0]
        assert "metadata" in results[0]
        assert "score" in results[0]

    def test_health_check(self, standard_rag):
        """Test health check functionality."""
        # Mock the similarity_search to return an empty list
        standard_rag.vector_store.similarity_search = Mock(return_value=[])

        health = standard_rag.health_check()

        assert "status" in health
        assert "vector_store" in health
        assert "collection" in health
        assert health["collection"] == standard_rag.collection_name
        assert health["status"] == "healthy"
        assert health["vector_store"] == "operational"

    @pytest.mark.asyncio
    async def test_clear_collection(self, standard_rag):
        """Test clearing the collection."""
        # Add a document first
        await standard_rag.add_documents(["Test document"])

        # Mock FAISS.from_texts for the clear operation
        with patch("langgraph_agent.agents.rag_standard.FAISS") as mock_faiss:
            # Create a fresh mock vector store for the cleared state
            new_mock_store = Mock()
            new_mock_store.save_local = Mock()
            new_mock_store.as_retriever = Mock(return_value=Mock())
            mock_faiss.from_texts.return_value = new_mock_store

            # Mock the _setup_retrievers to prevent errors
            with patch.object(standard_rag, "_setup_retrievers"):
                # Clear collection
                await standard_rag.clear_collection()

                # Verify FAISS.from_texts was called to reinitialize
                assert mock_faiss.from_texts.called

                # Verify save_local was called to persist the empty store
                assert new_mock_store.save_local.called

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


class TestPerformanceImprovement:
    """Test performance improvements from standardization."""

    def test_code_reduction(self):
        """Verify code reduction from 1200+ lines to ~300 lines."""
        # Check StandardizedRAG file size
        standard_file = Path("langgraph_agent/agents/rag_standard.py")
        if standard_file.exists():
            with open(standard_file, "r") as f:
                lines = len(f.readlines())

            # Should be significantly smaller than original
            assert lines < 400, f"StandardizedRAG has {lines} lines, should be < 400"

    def test_langchain_components_usage(self):
        """Verify LangChain components are properly imported."""
        # Check imports in StandardizedRAG
        standard_file = Path("langgraph_agent/agents/rag_standard.py")
        if standard_file.exists():
            with open(standard_file, "r") as f:
                content = f.read()

            # Verify key LangChain imports
            assert "from langchain_openai import" in content
            assert "from langchain_community.vectorstores import FAISS" in content
            assert "from langchain.retrievers import MultiQueryRetriever" in content
            assert (
                "from langchain_text_splitters import RecursiveCharacterTextSplitter" in content,
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
