"""

Standardized RAG system using LangChain components.

Phase 3 Implementation: Replace custom RAG with standard LangChain components.
This module provides a simplified RAG system that:
- Uses FAISS for vector storage
- Implements multi-query retrieval for query expansion
- Includes reranking for better relevance
- Maintains compatibility with existing interfaces
"""

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.retrievers import (
    MultiQueryRetriever,
    ContextualCompressionRetriever,
)
from langchain.retrievers.document_compressors import CohereRerank
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
import os

logger = logging.getLogger(__name__)


class StandardizedRAG:
    """Simplified RAG system using LangChain components."""

    def __init__(self, company_id: UUID, collection_name: Optional[str] = None) -> None:
        """
        Initialize with standard components.

        Args:
            company_id: Company identifier for data isolation
            collection_name: Optional collection name for vector store
        """
        self.company_id = company_id
        self.collection_name = collection_name or f"compliance_{company_id}"

        # Initialize embeddings with OpenAI
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

        # Initialize vector store
        self._initialize_vector_store()

        # Setup retrievers
        self._setup_retrievers()

        # Text splitter for documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", ". ", " ", ""]
        )

        logger.info(f"StandardizedRAG initialized for company {company_id}")

    def _initialize_vector_store(self):
        """Initialize or load vector store."""
        vectorstore_path = f"./vectorstores/{self.collection_name}"

        try:
            # Try to load existing vector store
            if os.path.exists(vectorstore_path):
                self.vector_store = FAISS.load_local(
                    vectorstore_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
                logger.info(f"Loaded existing vector store: {self.collection_name}")
            else:
                # Create new vector store with initialization document
                self.vector_store = FAISS.from_texts(
                    ["Initialization document for compliance RAG system"],
                    self.embeddings,
                    metadatas=[{"company_id": str(self.company_id), "type": "init"}],
                )
                # Create directory if needed
                os.makedirs(os.path.dirname(vectorstore_path), exist_ok=True)
                logger.info(f"Created new vector store: {self.collection_name}")
        except Exception as e:
            logger.warning(f"Could not load vector store, creating new: {e}")
            # Create new if loading fails
            self.vector_store = FAISS.from_texts(
                ["Initialization document for compliance RAG system"],
                self.embeddings,
                metadatas=[{"company_id": str(self.company_id), "type": "init"}],
            )

    def _setup_retrievers(self):
        """Setup retriever pipeline with multi-query and reranking."""
        # Base retriever with high k for reranking
        base_retriever = self.vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"score_threshold": 0.5, "k": 20},
        )

        # Multi-query for query expansion
        llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")

        multi_query_retriever = MultiQueryRetriever.from_llm(
            retriever=base_retriever, llm=llm, parser_key="lines"
        )

        # Check if Cohere API key is available for reranking
        if os.getenv("COHERE_API_KEY"):
            # Reranking for better relevance
            compressor = CohereRerank(model="rerank-english-v2.0", top_n=5)

            self.retriever = ContextualCompressionRetriever(
                base_compressor=compressor, base_retriever=multi_query_retriever
            )
            logger.info("Retriever pipeline configured with multi-query and reranking")
        else:
            # Fallback to multi-query without reranking
            self.retriever = multi_query_retriever
            logger.warning("Cohere API key not found, using multi-query without reranking")

    async def add_documents(
        self, documents: List[str], metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Add documents to vector store.

        Args:
            documents: List of document contents to add
            metadatas: Optional metadata for each document
        """
        # Split documents into chunks
        texts = []
        metas = []

        for i, doc in enumerate(documents):
            chunks = self.text_splitter.split_text(doc)
            texts.extend(chunks)

            # Extend metadata for each chunk
            if metadatas and i < len(metadatas):
                chunk_meta = metadatas[i].copy()
                chunk_meta["company_id"] = str(self.company_id)
                chunk_meta["chunk_count"] = len(chunks)
                # Add chunk index to each chunk's metadata
                for j in range(len(chunks)):
                    chunk_meta_copy = chunk_meta.copy()
                    chunk_meta_copy["chunk_index"] = j
                    metas.append(chunk_meta_copy)
            else:
                # Default metadata if none provided
                for j in range(len(chunks)):
                    metas.append(
                        {
                            "company_id": str(self.company_id),
                            "chunk_index": j,
                            "chunk_count": len(chunks),
                        }
                    )

        # Add to vector store
        self.vector_store.add_texts(texts, metadatas=metas)

        # Save vector store
        vectorstore_path = f"./vectorstores/{self.collection_name}"
        os.makedirs(os.path.dirname(vectorstore_path), exist_ok=True)
        self.vector_store.save_local(vectorstore_path)

        logger.info(f"Added {len(texts)} chunks from {len(documents)} documents")

    async def retrieve(self, query: str, k: Optional[int] = 5) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of relevant documents with content and metadata
        """
        try:
            # Use the configured retriever pipeline
            docs = await self.retriever.aget_relevant_documents(query)

            # Convert to dict format and limit to k results
            results = []
            for doc in docs[:k]:
                # Extract relevance score if available
                score = 0.0
                if hasattr(doc, "metadata") and "relevance_score" in doc.metadata:
                    score = doc.metadata["relevance_score"]
                elif hasattr(doc, "metadata") and "score" in doc.metadata:
                    score = doc.metadata["score"]

                results.append(
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata if hasattr(doc, "metadata") else {},
                        "score": score,
                    }
                )

            logger.info(f"Retrieved {len(results)} documents for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            # Return empty results on error
            return []

    def health_check(self) -> Dict[str, Any]:
        """
        Simple health check.

        Returns:
            Health status of the RAG system
        """
        try:
            # Test retrieval with simple query
            self.vector_store.similarity_search("test", k=1)

            # Get document count if available
            doc_count = "unknown"
            if hasattr(self.vector_store, "index") and hasattr(self.vector_store.index, "ntotal"):
                doc_count = self.vector_store.index.ntotal

            return {
                "status": "healthy",
                "vector_store": "operational",
                "document_count": doc_count,
                "collection": self.collection_name,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "collection": self.collection_name,
            }

    async def clear_collection(self) -> None:
        """Clear all documents from the collection."""
        try:
            # Reinitialize with empty vector store
            self.vector_store = FAISS.from_texts(
                ["Initialization document for compliance RAG system"],
                self.embeddings,
                metadatas=[{"company_id": str(self.company_id), "type": "init"}],
            )

            # Save empty vector store
            vectorstore_path = f"./vectorstores/{self.collection_name}"
            os.makedirs(os.path.dirname(vectorstore_path), exist_ok=True)
            self.vector_store.save_local(vectorstore_path)

            # Reinitialize retrievers
            self._setup_retrievers()

            logger.info(f"Cleared collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            raise

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get RAG system statistics.

        Returns:
            Statistics about the current state
        """
        try:
            doc_count = 0
            if hasattr(self.vector_store, "index") and hasattr(self.vector_store.index, "ntotal"):
                doc_count = self.vector_store.index.ntotal

            return {
                "company_id": str(self.company_id),
                "collection_name": self.collection_name,
                "document_count": doc_count,
                "embeddings_model": "text-embedding-3-small",
                "reranking_enabled": bool(os.getenv("COHERE_API_KEY")),
                "multi_query_enabled": True,
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {
                "error": str(e),
                "company_id": str(self.company_id),
                "collection_name": self.collection_name,
            }
