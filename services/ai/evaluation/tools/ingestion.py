"""Golden Dataset ingestion tool for Neo4j."""

import logging

logger = logging.getLogger(__name__)
from typing import List, Dict, Any
import json
from datetime import datetime
import numpy as np
from services.ai.evaluation.schemas.common import GoldenDoc, GoldenChunk, SourceMeta
from services.ai.evaluation.infrastructure.neo4j_setup import Neo4jConnection


class DocumentProcessor:
    """Process and validate golden dataset documents."""

    def load_golden_dataset(self, file_path: str) -> List[GoldenDoc]:
        """Load golden dataset from JSON file."""
        import os

        safe_path = os.path.abspath(os.path.normpath(file_path))
        if not safe_path.startswith(os.path.abspath(".")):
            raise ValueError("Invalid file path: attempted path traversal")
        with open(safe_path, "r") as f:
            data = json.load(f)
        documents = []
        for doc_data in data.get("documents", []):
            source_meta_data = doc_data.get("source_meta", {})
            if "fetched_at" in source_meta_data:
                source_meta_data["fetched_at"] = datetime.fromisoformat(
                    source_meta_data["fetched_at"].replace("Z", "+00:00")
                )
            source_meta = SourceMeta(**source_meta_data)
            doc = GoldenDoc(
                doc_id=doc_data["doc_id"],
                content=doc_data["content"],
                source_meta=source_meta,
                reg_citations=doc_data.get("reg_citations"),
                expected_outcomes=doc_data.get("expected_outcomes"),
            )
            documents.append(doc)
        return documents

    def validate_document(self, doc: Any) -> bool:
        """Validate document schema."""
        if isinstance(doc, GoldenDoc):
            return True
        if isinstance(doc, dict):
            try:
                if "doc_id" not in doc or "content" not in doc:
                    raise ValueError("Missing required fields")
                GoldenDoc(**doc)
                return True
            except (ValueError, TypeError):
                raise ValueError("Invalid document structure")
        return False

    def preprocess_content(self, content: str) -> str:
        """Preprocess document content."""
        import re

        content = re.sub("\\s+", " ", content)
        content = content.strip()
        content = re.sub("([.!?])\\s+", "\\1 ", content)
        return content


class ChunkProcessor:
    """Process documents into chunks for embedding."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 100) -> None:
        """Initialize chunk processor."""
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(self, doc: GoldenDoc) -> List[GoldenChunk]:
        """Chunk a document into smaller pieces."""
        content = doc.content
        chunks = []
        chunk_index = 0
        text_length = len(content)
        position = 0
        while position < text_length:
            chunk_end = min(position + self.chunk_size, text_length)
            chunk_content = content[position:chunk_end]
            chunk = GoldenChunk(
                chunk_id=f"{doc.doc_id}_chunk_{chunk_index}",
                doc_id=doc.doc_id,
                chunk_index=chunk_index,
                content=chunk_content,
                source_meta=doc.source_meta,
                reg_citations=doc.reg_citations,
                expected_outcomes=doc.expected_outcomes,
            )
            chunks.append(chunk)
            chunk_index += 1
            if chunk_end < text_length:
                position = chunk_end - self.overlap
            else:
                break
        return chunks


class EmbeddingGenerator:
    """Generate embeddings for documents and chunks."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        """Initialize embedding model."""
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = 384

    def generate_embedding(self, text: str, normalize: bool = False) -> List[float]:
        """Generate embedding for a single text."""
        embedding = self.model.encode([text], convert_to_tensor=False)[0]
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()
        if normalize:
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = (np.array(embedding) / norm).tolist()
        return embedding

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = self.model.encode(texts, convert_to_tensor=False)
        result = []
        for embedding in embeddings:
            if isinstance(embedding, np.ndarray):
                result.append(embedding.tolist())
            else:
                result.append(embedding)
        return result


class GraphIngestion:
    """Ingest documents and chunks into Neo4j."""

    def __init__(self) -> None:
        """Initialize Neo4j connection."""
        self.connection = Neo4jConnection()

    def ingest_document(self, doc: GoldenDoc, embedding: List[float]) -> bool:
        """Ingest a document into Neo4j."""
        query = """
        CREATE (d:Document {
            doc_id: $doc_id,
            content: $content,
            embedding: $embedding,
            source_origin: $source_origin,
            source_domain: $source_domain,
            source_trust_score: $source_trust_score,
            source_sha256: $source_sha256,
            fetched_at: $fetched_at
        })
        RETURN d
        """
        params = {
            "doc_id": doc.doc_id,
            "content": doc.content,
            "embedding": embedding,
            "source_origin": doc.source_meta.origin,
            "source_domain": doc.source_meta.domain,
            "source_trust_score": doc.source_meta.trust_score,
            "source_sha256": doc.source_meta.sha256,
            "fetched_at": doc.source_meta.fetched_at.isoformat()
            if doc.source_meta.fetched_at
            else None,
        }
        try:
            self.connection.execute_query(query, params)
            return True
        except Exception as e:
            logger.info("Error ingesting document: %s" % e)
            return False

    def ingest_chunk(self, chunk: GoldenChunk, embedding: List[float]) -> bool:
        """Ingest a chunk into Neo4j."""
        create_chunk_query = """
        CREATE (c:Chunk {
            chunk_id: $chunk_id,
            doc_id: $doc_id,
            chunk_index: $chunk_index,
            content: $content,
            embedding: $embedding,
            source_origin: $source_origin,
            source_domain: $source_domain,
            source_trust_score: $source_trust_score,
            source_sha256: $source_sha256,
            fetched_at: $fetched_at
        })
        RETURN c
        """
        create_relationship_query = """
        MATCH (d:Document {doc_id: $doc_id})
        MATCH (c:Chunk {chunk_id: $chunk_id})
        CREATE (d)-[:HAS_CHUNK]->(c)
        RETURN d, c
        """
        params = {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "embedding": embedding,
            "source_origin": chunk.source_meta.origin,
            "source_domain": chunk.source_meta.domain,
            "source_trust_score": chunk.source_meta.trust_score,
            "source_sha256": chunk.source_meta.sha256,
            "fetched_at": chunk.source_meta.fetched_at.isoformat()
            if chunk.source_meta.fetched_at
            else None,
        }
        try:
            self.connection.execute_query(create_chunk_query, params)
            rel_params = {"doc_id": chunk.doc_id, "chunk_id": chunk.chunk_id}
            self.connection.execute_query(
                create_relationship_query,
                rel_params,
            )
            return True
        except Exception as e:
            logger.info("Error ingesting chunk: %s" % e)
            return False

    def create_chunk_relationships(self, chunks: List[GoldenChunk]) -> bool:
        """Create relationships between chunks."""
        if not chunks:
            return True
        sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)
        for i in range(len(sorted_chunks) - 1):
            current_chunk = sorted_chunks[i]
            next_chunk = sorted_chunks[i + 1]
            if current_chunk.doc_id == next_chunk.doc_id:
                query = """
                MATCH (c1:Chunk {chunk_id: $current_chunk_id})
                MATCH (c2:Chunk {chunk_id: $next_chunk_id})
                CREATE (c1)-[:NEXT]->(c2)
                RETURN c1, c2
                """
                params = {
                    "current_chunk_id": current_chunk.chunk_id,
                    "next_chunk_id": next_chunk.chunk_id,
                }
                try:
                    self.connection.execute_query(query, params)
                except Exception as e:
                    logger.info("Error creating chunk relationship: %s" % e)
                    return False
        return True


class GoldenDatasetIngestion:
    """Complete ingestion pipeline for golden datasets."""

    def __init__(self) -> None:
        """Initialize all components."""
        self.doc_processor = DocumentProcessor()
        self.chunk_processor = ChunkProcessor()
        self.embedding_generator = EmbeddingGenerator()
        self.graph_ingestion = GraphIngestion()

    def ingest_from_file(self, file_path: str) -> Dict[str, Any]:
        """Ingest a golden dataset file into Neo4j."""
        result = {"success": False, "documents_processed": 0, "chunks_created": 0, "errors": []}
        try:
            documents = self.doc_processor.load_golden_dataset(file_path)
            for doc in documents:
                try:
                    doc.content = self.doc_processor.preprocess_content(doc.content)
                    if not self.doc_processor.validate_document(doc):
                        result["errors"].append(f"Invalid document: {doc.doc_id}")
                        continue
                    doc_embedding = self.embedding_generator.generate_embedding(doc.content)
                    if not self.graph_ingestion.ingest_document(doc, doc_embedding):
                        result["errors"].append(f"Failed to ingest document: {doc.doc_id}")
                        continue
                    chunks = self.chunk_processor.chunk_document(doc)
                    chunk_texts = [chunk.content for chunk in chunks]
                    chunk_embeddings = self.embedding_generator.generate_embeddings_batch(
                        chunk_texts
                    )
                    for chunk, embedding in zip(chunks, chunk_embeddings):
                        if self.graph_ingestion.ingest_chunk(chunk, embedding):
                            result["chunks_created"] += 1
                        else:
                            result["errors"].append(f"Failed to ingest chunk: {chunk.chunk_id}")
                    if chunks:
                        self.graph_ingestion.create_chunk_relationships(chunks)
                    result["documents_processed"] += 1
                except (KeyError, IndexError) as e:
                    result["errors"].append(f"Error processing document {doc.doc_id}: {str(e)}")
            result["success"] = result["documents_processed"] > 0
        except (KeyError, IndexError) as e:
            result["errors"].append(f"Error loading file: {str(e)}")
        return result
