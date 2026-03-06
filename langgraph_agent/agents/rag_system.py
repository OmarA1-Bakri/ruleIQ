"""

Advanced RAG (Retrieval-Augmented Generation) system with document pipeline optimization.
Integrates with Graphiti memory manager for comprehensive knowledge retrieval.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
import hashlib
from pathlib import Path
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader, JSONLoader, CSVLoader
from ..core.constants import MODEL_CONFIG, RAG_CONFIG
from .memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Supported document types for processing."""

    PDF = "pdf"
    TXT = "txt"
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    HTML = "html"
    DOCX = "docx"
    XLSX = "xlsx"


class DocumentSource(str, Enum):
    """Document source types."""

    UPLOADED = "uploaded"
    REGULATION = "regulation"
    TEMPLATE = "template"
    GUIDANCE = "guidance"
    POLICY = "policy"
    EVIDENCE = "evidence"
    TRAINING = "training"


class RetrievalStrategy(str, Enum):
    """Document retrieval strategies."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    CONTEXTUAL = "contextual"
    TEMPORAL = "temporal"


@dataclass
class RAGConfig:
    """Configuration for RAG system."""

    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    top_k: int = 5
    similarity_threshold: float = 0.7
    use_reranking: bool = True
    max_context_length: int = 4000
    temperature: float = 0.7
    model_name: str = "gpt-4"
    embedding_model: str = "text-embedding-ada-002"
    collection_name: str = "compliance_docs"
    metadata_filters: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        if not 0 <= self.similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")


@dataclass
class DocumentMetadata:
    """Comprehensive document metadata."""

    document_id: str
    title: str
    document_type: DocumentType
    source: DocumentSource
    content_hash: str
    file_size_bytes: int
    page_count: Optional[int] = None
    language: str = "en"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    indexed_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: Optional[datetime] = None
    company_id: UUID = field(default_factory=UUID)
    access_level: str = "company"
    tags: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    compliance_areas: List[str] = field(default_factory=list)
    regulatory_version: Optional[str] = None
    processing_status: str = "pending"
    chunk_count: int = 0
    embedding_model: str = MODEL_CONFIG["embedding_model"]
    keywords: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "document_id": self.document_id,
            "title": self.title,
            "document_type": self.document_type.value,
            "source": self.source.value,
            "content_hash": self.content_hash,
            "file_size_bytes": self.file_size_bytes,
            "page_count": self.page_count,
            "language": self.language,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "indexed_at": self.indexed_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "company_id": str(self.company_id),
            "access_level": self.access_level,
            "tags": self.tags,
            "frameworks": self.frameworks,
            "compliance_areas": self.compliance_areas,
            "regulatory_version": self.regulatory_version,
            "processing_status": self.processing_status,
            "chunk_count": self.chunk_count,
            "embedding_model": self.embedding_model,
            "keywords": self.keywords,
            "entities": self.entities,
            "summary": self.summary,
        }


@dataclass
class DocumentChunk:
    """Individual document chunk with metadata."""

    chunk_id: str
    document_id: str
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    page_number: Optional[int] = None
    token_count: int = 0
    embedding: Optional[List[float]] = None
    preceding_context: Optional[str] = None
    following_context: Optional[str] = None
    section_title: Optional[str] = None
    relevance_score: float = 0.0
    last_retrieved: Optional[datetime] = None
    retrieval_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "page_number": self.page_number,
            "token_count": self.token_count,
            "embedding": self.embedding,
            "preceding_context": self.preceding_context,
            "following_context": self.following_context,
            "section_title": self.section_title,
            "relevance_score": self.relevance_score,
            "last_retrieved": self.last_retrieved.isoformat() if self.last_retrieved else None,
            "retrieval_count": self.retrieval_count,
        }


@dataclass
class RetrievalResult:
    """Result from document retrieval."""

    chunks: List[DocumentChunk]
    total_results: int
    query: str
    strategy: RetrievalStrategy
    retrieval_time_ms: int
    rerank_time_ms: Optional[int] = None
    avg_relevance_score: float = 0.0
    min_relevance_score: float = 0.0
    max_relevance_score: float = 0.0
    document_sources: List[DocumentSource] = field(default_factory=list)
    frameworks_covered: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "total_results": self.total_results,
            "query": self.query,
            "strategy": self.strategy.value,
            "retrieval_time_ms": self.retrieval_time_ms,
            "rerank_time_ms": self.rerank_time_ms,
            "avg_relevance_score": self.avg_relevance_score,
            "min_relevance_score": self.min_relevance_score,
            "max_relevance_score": self.max_relevance_score,
            "document_sources": [s.value for s in self.document_sources],
            "frameworks_covered": self.frameworks_covered,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }


class DocumentProcessor:
    """Advanced document processing pipeline."""

    def __init__(
        self,
        chunk_size: int = RAG_CONFIG["chunk_size"],
        chunk_overlap: int = RAG_CONFIG["chunk_overlap"],
        embedding_model: str = MODEL_CONFIG["embedding_model"],
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            separators=["\n\n", "\n", " ", ".", ",", "\u200b", "，", "、", "．", "。", ""],
        )
        self.loaders = {
            DocumentType.PDF: PyPDFLoader,
            DocumentType.TXT: TextLoader,
            DocumentType.JSON: JSONLoader,
            DocumentType.CSV: CSVLoader,
        }
        logger.info(f"DocumentProcessor initialized with chunk_size={chunk_size}")

    async def process_document(
        self, file_path: str, document_metadata: DocumentMetadata
    ) -> Tuple[DocumentMetadata, List[DocumentChunk]]:
        """
        Process a document into chunks with metadata.

        Args:
            file_path: Path to the document file
            document_metadata: Document metadata

        Returns:
            Tuple of updated metadata and document chunks
        """
        start_time = datetime.now(timezone.utc)
        try:
            document_type = document_metadata.document_type
            if document_type not in self.loaders:
                raise ValueError(f"Unsupported document type: {document_type}")
            loader_class = self.loaders[document_type]
            loader = loader_class(file_path)
            documents = await asyncio.to_thread(loader.load)
            full_content = "\n\n".join([doc.page_content for doc in documents])
            content_hash = hashlib.sha256(full_content.encode()).hexdigest()
            document_metadata.content_hash = content_hash
            text_chunks = self.text_splitter.split_text(full_content)
            chunks = []
            char_position = 0
            for i, chunk_text in enumerate(text_chunks):
                chunk_id = f"{document_metadata.document_id}_chunk_{i:04d}"
                start_char = full_content.find(chunk_text, char_position)
                if start_char == -1:
                    start_char = char_position
                end_char = start_char + len(chunk_text)
                char_position = end_char
                page_number = start_char // 2000 + 1 if document_type == DocumentType.PDF else None
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document_metadata.document_id,
                    content=chunk_text,
                    chunk_index=i,
                    start_char=start_char,
                    end_char=end_char,
                    page_number=page_number,
                    token_count=len(chunk_text.split()),
                )
                if i > 0:
                    chunk.preceding_context = text_chunks[i - 1][-100:]
                if i < len(text_chunks) - 1:
                    chunk.following_context = text_chunks[i + 1][:100]
                chunks.append(chunk)
            document_metadata.chunk_count = len(chunks)
            document_metadata.processing_status = "processed"
            document_metadata.indexed_at = datetime.now(timezone.utc)
            document_metadata.keywords = self._extract_keywords(full_content)
            document_metadata.entities = self._extract_entities(full_content)
            document_metadata.summary = self._generate_summary(full_content)
            processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            logger.info(
                f"Processed document {document_metadata.document_id}: {len(chunks)} chunks in {processing_time}ms"
            )
            return (document_metadata, chunks)
        except (OSError, ValueError, KeyError) as e:
            document_metadata.processing_status = "failed"
            logger.error(f"Failed to process document {document_metadata.document_id}: {e}")
            raise

    def _extract_keywords(self, content: str) -> List[str]:
        """Extract key terms from content (simple implementation)."""
        import re

        words = re.findall("\\b[a-zA-Z]{3,}\\b", content.lower())
        compliance_terms = [
            "gdpr",
            "privacy",
            "data",
            "protection",
            "compliance",
            "regulation",
            "consent",
            "processing",
            "controller",
            "processor",
            "breach",
            "rights",
            "subject",
            "personal",
            "sensitive",
            "security",
            "assessment",
            "impact",
            "policy",
            "procedure",
            "documentation",
        ]
        keywords = []
        for term in compliance_terms:
            if term in words:
                keywords.append(term)
        word_freq = {}
        for word in words:
            if len(word) >= 4 and word.isalpha():
                word_freq[word] = word_freq.get(word, 0) + 1
        frequent_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        keywords.extend([word for word, freq in frequent_words if word not in keywords])
        return keywords[:20]

    def _extract_entities(self, content: str) -> List[str]:
        """Extract named entities from content (simple implementation)."""
        import re

        entities = []
        org_patterns = [
            "\\b[A-Z][a-z]+ (?:Ltd|Limited|Inc|Corporation|Corp|Company|Co)\\b",
            "\\b(?:ICO|GDPR|ISO|NIST|FTC|SEC)\\b",
        ]
        for pattern in org_patterns:
            matches = re.findall(pattern, content)
            entities.extend(matches)
        date_pattern = "\\b\\d{1,2}[/-]\\d{1,2}[/-]\\d{2,4}\\b"
        dates = re.findall(date_pattern, content)
        entities.extend(dates[:5])
        return list(set(entities))[:15]

    def _generate_summary(self, content: str) -> str:
        """Generate a brief summary of the content."""
        sentences = content.split(". ")
        summary_sentences = sentences[:3]
        summary = ". ".join(summary_sentences)
        if len(summary) > 300:
            summary = summary[:297] + "..."
        return summary


class RAGSystem:
    """
    Advanced RAG system with document pipeline and retrieval optimization.

    Features:
    - Multi-strategy retrieval (semantic, keyword, hybrid)
    - Document processing pipeline
    - Integration with Graphiti memory system
    - Performance optimization and caching
    - Compliance-specific ranking
    """

    def __init__(
        self,
        memory_manager: MemoryManager,
        embeddings: Embeddings,
        vector_store: Optional[VectorStore] = None,
        enable_reranking: bool = True,
        cache_ttl_hours: int = 24,
    ) -> None:
        self.memory_manager = memory_manager
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.enable_reranking = enable_reranking
        self.cache_ttl_hours = cache_ttl_hours
        self.processor = DocumentProcessor()
        self.documents: Dict[str, DocumentMetadata] = {}
        self.chunks: Dict[str, DocumentChunk] = {}
        self.query_cache: Dict[str, Tuple[RetrievalResult, datetime]] = {}
        self.embedding_cache: Dict[str, List[float]] = {}
        self.retrieval_stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "avg_retrieval_time_ms": 0.0,
            "total_documents": 0,
            "total_chunks": 0,
        }
        logger.info("RAGSystem initialized with advanced retrieval capabilities")

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
        Add a document to the RAG system.

        Args:
            file_path: Path to the document file
            company_id: Company UUID for access control
            title: Document title
            document_type: Type of document
            source: Document source
            frameworks: Applicable compliance frameworks
            tags: Document tags
            metadata_override: Optional metadata overrides

        Returns:
            Document metadata after processing
        """
        try:
            document_id = f"doc_{uuid4()}"
            file_size = Path(file_path).stat().st_size
            metadata = DocumentMetadata(
                document_id=document_id,
                title=title,
                document_type=document_type,
                source=source,
                content_hash="",
                file_size_bytes=file_size,
                company_id=company_id,
                frameworks=frameworks or [],
                tags=tags or [],
            )
            if metadata_override:
                for key, value in metadata_override.items():
                    if hasattr(metadata, key):
                        setattr(metadata, key, value)
            processed_metadata, chunks = await self.processor.process_document(file_path, metadata)
            self.documents[document_id] = processed_metadata
            for chunk in chunks:
                self.chunks[chunk.chunk_id] = chunk
            await self._generate_chunk_embeddings(chunks)
            await self._store_document_in_memory(processed_metadata, chunks)
            self.retrieval_stats["total_documents"] += 1
            self.retrieval_stats["total_chunks"] += len(chunks)
            logger.info(f"Added document {document_id}: {len(chunks)} chunks processed")
            return processed_metadata
        except (OSError, KeyError, IndexError) as e:
            logger.error(f"Failed to add document: {e}")
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
        Retrieve relevant documents based on query.

        Args:
            query: Search query
            company_id: Company UUID for access control
            k: Number of results to return
            strategy: Retrieval strategy
            frameworks_filter: Filter by frameworks
            source_filter: Filter by document sources
            min_relevance_score: Minimum relevance threshold

        Returns:
            Retrieval results with ranked chunks
        """
        start_time = datetime.now(timezone.utc)
        cache_key = self._generate_cache_key(
            query, company_id, k, strategy, frameworks_filter, source_filter
        )
        if cache_key in self.query_cache:
            cached_result, cached_time = self.query_cache[cache_key]
            if (
                datetime.now(timezone.utc) - cached_time
            ).total_seconds() < self.cache_ttl_hours * 3600:
                self.retrieval_stats["cache_hits"] += 1
                logger.info(f"Cache hit for query: {query[:50]}...")
                return cached_result
        try:
            if strategy == RetrievalStrategy.SEMANTIC:
                chunks = await self._semantic_retrieval(query, company_id, k * 2)
            elif strategy == RetrievalStrategy.KEYWORD:
                chunks = await self._keyword_retrieval(query, company_id, k * 2)
            elif strategy == RetrievalStrategy.HYBRID:
                semantic_chunks = await self._semantic_retrieval(query, company_id, k)
                keyword_chunks = await self._keyword_retrieval(query, company_id, k)
                chunks = self._merge_results(semantic_chunks, keyword_chunks)
            elif strategy == RetrievalStrategy.CONTEXTUAL:
                chunks = await self._contextual_retrieval(query, company_id, k * 2)
            else:
                chunks = await self._semantic_retrieval(query, company_id, k * 2)
            filtered_chunks = self._apply_filters(
                chunks, company_id, frameworks_filter, source_filter
            )
            relevant_chunks = [
                chunk for chunk in filtered_chunks if chunk.relevance_score >= min_relevance_score
            ]
            if self.enable_reranking and len(relevant_chunks) > k:
                rerank_start = datetime.now(timezone.utc)
                relevant_chunks = await self._rerank_chunks(query, relevant_chunks)
                rerank_time = int(
                    (datetime.now(timezone.utc) - rerank_start).total_seconds() * 1000
                )
            else:
                rerank_time = None
            final_chunks = relevant_chunks[:k]
            for chunk in final_chunks:
                chunk.last_retrieved = datetime.now(timezone.utc)
                chunk.retrieval_count += 1
            retrieval_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            relevance_scores = [chunk.relevance_score for chunk in final_chunks]
            result = RetrievalResult(
                chunks=final_chunks,
                total_results=len(final_chunks),
                query=query,
                strategy=strategy,
                retrieval_time_ms=retrieval_time,
                rerank_time_ms=rerank_time,
                avg_relevance_score=sum(relevance_scores) / len(relevance_scores)
                if relevance_scores
                else 0.0,
                min_relevance_score=min(relevance_scores) if relevance_scores else 0.0,
                max_relevance_score=max(relevance_scores) if relevance_scores else 0.0,
                document_sources=list(
                    set([self.documents[chunk.document_id].source for chunk in final_chunks])
                ),
                frameworks_covered=list(
                    set(
                        [
                            fw
                            for chunk in final_chunks
                            for fw in self.documents[chunk.document_id].frameworks
                        ]
                    )
                ),
            )
            self.query_cache[cache_key] = (result, datetime.now(timezone.utc))
            self.retrieval_stats["total_queries"] += 1
            total_time = self.retrieval_stats["avg_retrieval_time_ms"] * (
                self.retrieval_stats["total_queries"] - 1
            )
            self.retrieval_stats["avg_retrieval_time_ms"] = (
                total_time + retrieval_time
            ) / self.retrieval_stats["total_queries"]
            logger.info(
                f"Retrieved {len(final_chunks)} chunks in {retrieval_time}ms using {strategy} strategy"
            )
            return result
        except (Exception, ValueError, KeyError) as e:
            logger.error(f"Retrieval failed: {e}")
            raise

    async def _semantic_retrieval(
        self, query: str, company_id: UUID, k: int
    ) -> List[DocumentChunk]:
        """Perform semantic similarity search."""
        try:
            query_embedding = await self._get_embedding(query)
            company_chunks = [
                chunk
                for chunk in self.chunks.values()
                if self.documents[chunk.document_id].company_id == company_id and chunk.embedding
            ]
            similarities = []
            for chunk in company_chunks:
                similarity = self._cosine_similarity(query_embedding, chunk.embedding)
                chunk.relevance_score = similarity
                similarities.append((chunk, similarity))
            similarities.sort(key=lambda x: x[1], reverse=True)
            return [chunk for chunk, _ in similarities[:k]]
        except (Exception, KeyError, IndexError) as e:
            logger.error(f"Semantic retrieval failed: {e}")
            return []

    async def _keyword_retrieval(self, query: str, company_id: UUID, k: int) -> List[DocumentChunk]:
        """Perform keyword-based search."""
        try:
            query_terms = set(query.lower().split())
            company_chunks = [
                chunk
                for chunk in self.chunks.values()
                if self.documents[chunk.document_id].company_id == company_id
            ]
            scored_chunks = []
            for chunk in company_chunks:
                content_terms = set(chunk.content.lower().split())
                matches = len(query_terms.intersection(content_terms))
                if matches > 0:
                    tf_score = matches / len(query_terms)
                    idf_boost = 1.0 + matches / len(content_terms)
                    chunk.relevance_score = tf_score * idf_boost
                    scored_chunks.append(chunk)
            scored_chunks.sort(key=lambda x: x.relevance_score, reverse=True)
            return scored_chunks[:k]
        except (Exception, KeyError, IndexError) as e:
            logger.error(f"Keyword retrieval failed: {e}")
            return []

    async def _contextual_retrieval(
        self, query: str, company_id: UUID, k: int
    ) -> List[DocumentChunk]:
        """Perform context-aware retrieval using memory system."""
        try:
            relevant_memories = await self.memory_manager.get_relevant_memories(
                company_id, query, max_results=k
            )
            chunks = []
            for memory in relevant_memories:
                if "chunk_" in memory.content:
                    import re

                    chunk_ids = re.findall("doc_[a-f0-9-]+_chunk_\\d{4}", memory.content)
                    for chunk_id in chunk_ids:
                        if chunk_id in self.chunks:
                            chunk = self.chunks[chunk_id]
                            chunk.relevance_score = 0.8
                            chunks.append(chunk)
            if not chunks:
                chunks = await self._semantic_retrieval(query, company_id, k)
            return chunks[:k]
        except (Exception, KeyError, IndexError) as e:
            logger.error(f"Contextual retrieval failed: {e}")
            return await self._semantic_retrieval(query, company_id, k)

    def _merge_results(
        self, semantic_chunks: List[DocumentChunk], keyword_chunks: List[DocumentChunk]
    ) -> List[DocumentChunk]:
        """Merge semantic and keyword search results."""
        merged = {}
        for chunk in semantic_chunks:
            merged[chunk.chunk_id] = chunk
            chunk.relevance_score = chunk.relevance_score * 0.7
        for chunk in keyword_chunks:
            if chunk.chunk_id in merged:
                merged[chunk.chunk_id].relevance_score += chunk.relevance_score * 0.3
            else:
                chunk.relevance_score = chunk.relevance_score * 0.3
                merged[chunk.chunk_id] = chunk
        result = list(merged.values())
        result.sort(key=lambda x: x.relevance_score, reverse=True)
        return result

    def _apply_filters(
        self,
        chunks: List[DocumentChunk],
        company_id: UUID,
        frameworks_filter: Optional[List[str]],
        source_filter: Optional[List[DocumentSource]],
    ) -> List[DocumentChunk]:
        """Apply filters to chunk results."""
        filtered = []
        for chunk in chunks:
            doc_metadata = self.documents[chunk.document_id]
            if doc_metadata.company_id != company_id:
                continue
            if frameworks_filter:
                if not any((fw in doc_metadata.frameworks for fw in frameworks_filter)):
                    continue
            if source_filter and doc_metadata.source not in source_filter:
                continue
            filtered.append(chunk)
        return filtered

    async def _rerank_chunks(self, query: str, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Rerank chunks for better relevance."""
        query_terms = set(query.lower().split())
        for chunk in chunks:
            content_lower = chunk.content.lower()
            position_scores = []
            for term in query_terms:
                pos = content_lower.find(term)
                if pos != -1:
                    position_score = 1.0 - pos / len(content_lower)
                    position_scores.append(position_score)
            term_frequency = sum((content_lower.count(term) for term in query_terms))
            frequency_score = term_frequency / len(chunk.content.split())
            position_bonus = sum(position_scores) / len(position_scores) if position_scores else 0
            rerank_score = (
                chunk.relevance_score * 0.7 + position_bonus * 0.2 + frequency_score * 0.1
            )
            chunk.relevance_score = rerank_score
        chunks.sort(key=lambda x: x.relevance_score, reverse=True)
        return chunks

    async def _generate_chunk_embeddings(self, chunks: List[DocumentChunk]) -> None:
        """Generate embeddings for document chunks."""
        try:
            for chunk in chunks:
                if not chunk.embedding:
                    chunk.embedding = await self._get_embedding(chunk.content)
            logger.info(f"Generated embeddings for {len(chunks)} chunks")
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to generate embeddings: {e}")

    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text with caching."""
        # Use SHA-256 instead of MD5 for security compliance, truncated for cache key compatibility
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        if text_hash in self.embedding_cache:
            return self.embedding_cache[text_hash]
        embedding = await asyncio.to_thread(self.embeddings.embed_query, text)
        self.embedding_cache[text_hash] = embedding
        return embedding

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        dot_product = sum((x * y for x, y in zip(a, b)))
        magnitude_a = math.sqrt(sum((x * x for x in a)))
        magnitude_b = math.sqrt(sum((x * x for x in b)))
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        return dot_product / (magnitude_a * magnitude_b)

    async def _store_document_in_memory(
        self, metadata: DocumentMetadata, chunks: List[DocumentChunk]
    ) -> None:
        """Store document information in memory manager."""
        try:
            episode_content = {
                "document_indexed": {
                    "document_id": metadata.document_id,
                    "title": metadata.title,
                    "document_type": metadata.document_type.value,
                    "source": metadata.source.value,
                    "frameworks": metadata.frameworks,
                    "tags": metadata.tags,
                    "chunk_count": len(chunks),
                    "summary": metadata.summary,
                    "keywords": metadata.keywords,
                    "entities": metadata.entities,
                }
            }
            await self.memory_manager.store_conversation(
                company_id=metadata.company_id,
                session_id=f"doc_index_{metadata.document_id}",
                user_message=f"Document indexed: {metadata.title}",
                agent_response=f"Successfully indexed {metadata.title} with {len(chunks)} chunks",
                context={"document_metadata": episode_content},
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to store document in memory: {e}")

    def _generate_cache_key(self, *args) -> str:
        """Generate cache key for query results."""
        key_string = str(args)
        # Use SHA-256 instead of MD5 for security compliance, truncated for cache key compatibility
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    async def get_document_by_id(self, document_id: str) -> Optional[DocumentMetadata]:
        """Get document metadata by ID."""
        return self.documents.get(document_id)

    async def get_document_chunks(self, document_id: str) -> List[DocumentChunk]:
        """Get all chunks for a document."""
        return [chunk for chunk in self.chunks.values() if chunk.document_id == document_id]

    async def delete_document(self, document_id: str, company_id: UUID) -> bool:
        """Delete a document and all its chunks."""
        try:
            if document_id not in self.documents:
                return False
            doc_metadata = self.documents[document_id]
            if doc_metadata.company_id != company_id:
                return False
            chunks_to_remove = [
                chunk_id
                for chunk_id, chunk in self.chunks.items()
                if chunk.document_id == document_id
            ]
            for chunk_id in chunks_to_remove:
                del self.chunks[chunk_id]
            del self.documents[document_id]
            self.retrieval_stats["total_documents"] -= 1
            self.retrieval_stats["total_chunks"] -= len(chunks_to_remove)
            logger.info(f"Deleted document {document_id} and {len(chunks_to_remove)} chunks")
            return True
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on RAG system."""
        health = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "statistics": self.retrieval_stats.copy(),
            "components": {},
        }
        try:
            if self.memory_manager:
                memory_health = await self.memory_manager.health_check()
                health["components"]["memory"] = memory_health
            try:
                test_embedding = await self._get_embedding("test")
                health["components"]["embeddings"] = "healthy" if test_embedding else "failed"
            except (KeyError, IndexError):
                health["components"]["embeddings"] = "failed"
                health["status"] = "degraded"
            health["cache_stats"] = {
                "query_cache_size": len(self.query_cache),
                "embedding_cache_size": len(self.embedding_cache),
            }
        except (Exception, KeyError, IndexError) as e:
            health["status"] = "degraded"
            health["error"] = str(e)
        return health

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics."""
        return {
            "documents": {
                "total": len(self.documents),
                "by_type": self._get_documents_by_type(),
                "by_source": self._get_documents_by_source(),
                "total_size_bytes": sum((doc.file_size_bytes for doc in self.documents.values())),
            },
            "chunks": {
                "total": len(self.chunks),
                "avg_size_chars": sum((len(chunk.content) for chunk in self.chunks.values()))
                / len(self.chunks)
                if self.chunks
                else 0,
                "total_tokens": sum((chunk.token_count for chunk in self.chunks.values())),
            },
            "retrieval": self.retrieval_stats.copy(),
            "cache": {
                "query_cache_size": len(self.query_cache),
                "embedding_cache_size": len(self.embedding_cache),
                "cache_hit_rate": self.retrieval_stats["cache_hits"]
                / max(self.retrieval_stats["total_queries"], 1),
            },
        }

    def _get_documents_by_type(self) -> Dict[str, int]:
        """Get document count by type."""
        type_counts = {}
        for doc in self.documents.values():
            doc_type = doc.document_type.value
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        return type_counts

    def _get_documents_by_source(self) -> Dict[str, int]:
        """Get document count by source."""
        source_counts = {}
        for doc in self.documents.values():
            source = doc.source.value
            source_counts[source] = source_counts.get(source, 0) + 1
        return source_counts
