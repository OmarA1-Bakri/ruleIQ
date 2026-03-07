"""Golden Dataset ingestion tool for Neo4j - Requires NEO4J_* environment variables."""

import logging
import os

logger = logging.getLogger(__name__)

from typing import List, Dict, Any
import json
from datetime import datetime
import numpy as np
import re
from services.ai.evaluation.schemas.common import GoldenDoc, GoldenChunk, SourceMeta


# Define a simple mock Neo4j driver for testing purposes
class MockNeo4jDriver:
    def session(self):
        return MockSession()

    def run(self, *args: Any, **kwargs: Any) -> Any:
        class MockResult:
            def __iter__(self_inner):
                return iter([])

        return MockResult()

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockSession:
    def run(self, *args: Any, **kwargs: Any) -> Any:
        class MockResult:
            def __iter__(self):
                return iter([])

        return MockResult()

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class Neo4jConnectionFixed:
    """Fixed Neo4j connection with proper error handling.

    Requires NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD environment variables.
    Falls back to mock driver for testing if credentials are not provided.
    """

    def __init__(self) -> None:
        self._driver = None

    def _initialize_driver(self):
        """Initialize the Neo4j driver."""
        if self._driver is None:
            try:
                from neo4j import GraphDatabase

                self.uri = os.getenv("NEO4J_URI")
                self.user = os.getenv("NEO4J_USER")
                self.password = os.getenv("NEO4J_PASSWORD")

                # Validate required environment variables
                if not self.uri or not self.user or not self.password:
                    logger.error(
                        "Neo4j credentials not found in environment. "
                        "Required: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD"
                    )
                    # Fall back to mock driver for testing without credentials
                    logger.info("Using mock Neo4j driver (no credentials provided)")
                    self._driver = MockNeo4jDriver()
                    return

                logger.info("[Neo4jConnectionFixed] Connecting to: %s" % self.uri)
                self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            except (ImportError, ModuleNotFoundError):
                # For testing without neo4j installed
                logger.info("neo4j not installed, using mock driver")
                self._driver = MockNeo4jDriver()

    def session(self):
        """Get a session from the driver."""
        self._initialize_driver()
        if self._driver is None:
            raise RuntimeError("Failed to initialize Neo4j driver")
        return self._driver.session()

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run a query using the driver."""
        self._initialize_driver()
        if self._driver is None:
            raise RuntimeError("Failed to initialize Neo4j driver")
        with self._driver.session() as session:
            return session.run(*args, **kwargs)

    def get_driver(self) -> Any:
        """Get Neo4j driver instance."""
        self._initialize_driver()
        return self._driver

    def close(self) -> None:
        """Close the driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None


class DocumentProcessor:
    """Process and validate golden dataset documents."""

    def load_golden_dataset(self, file_path: str) -> List[GoldenDoc]:
        """Load golden dataset from JSON file."""
        import os

        safe_path = os.path.abspath(os.path.normpath(file_path))
        base_dir = os.path.abspath(".")
        # Use os.path.commonpath for robust path traversal prevention
        if os.path.commonpath([base_dir, safe_path]) != base_dir:
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
                reg_citations=doc_data.get("reg_citations", []),
                expected_outcomes=doc_data.get("expected_outcomes", []),
            )
            documents.append(doc)
        return documents

    def validate_document(self, doc: Any) -> bool:
        """Validate document schema."""
        if isinstance(doc, GoldenDoc):
            return bool(doc.doc_id and doc.content)
        return False


class EmbeddingService:
    """Generate embeddings for golden dataset with batch processing support."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", batch_size: int = 32) -> None:
        """Initialize with local sentence-transformers model.

        Args:
            model_name: Name of the sentence-transformers model to use
            batch_size: Maximum batch size for encoding multiple texts
        """
        self.model_name = model_name
        self.model = None
        self.dimension = None  # Will be dynamically determined
        self.batch_size = batch_size
        self._load_model()  # Load model during initialization

    def _load_model(self):
        """Load the model and determine embedding dimension."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(self.model_name)
                # Dynamically determine embedding dimension
                test_embedding = self.model.encode("test", normalize_embeddings=True)
                self.dimension = len(test_embedding)
                logger.info(
                    "✅ Loaded embedding model: %s (dimension: %d)"
                    % (self.model_name, self.dimension)
                )
            except (ImportError, ModuleNotFoundError):
                logger.info("⚠️ sentence-transformers not installed, using mock embeddings")
                self.model = None
                self.dimension = 384  # Fallback dimension for mock embeddings

    def generate_embedding(self, texts: str | List[str]) -> List[float] | List[List[float]]:
        """Generate embeddings for single text or batch of texts.

        Args:
            texts: Single text string or list of text strings

        Returns:
            Single embedding (if input was string) or list of embeddings (if input was list)
        """
        # If input is a single string, convert to a list for uniform batch processing.
        # This ensures that downstream code always works with a list, and we convert
        # back at the end if needed.
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]

        all_embeddings = []

        if self.model:
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                # Batch encode with normalization
                batch_embeddings = self.model.encode(
                    batch,
                    normalize_embeddings=True,
                    batch_size=min(self.batch_size, len(batch)),
                    show_progress_bar=False,
                )
                # Ensure consistent shape and convert to list
                for embedding in batch_embeddings:
                    all_embeddings.append(embedding.tolist())
        else:
            # Generate mock embeddings with consistent dimension
            dimension = self.dimension or 384  # Fallback to 384 if None
            all_embeddings = [np.random.rand(dimension).tolist() for _ in texts]

        # Return single embedding if input was single text
        if is_single:
            return all_embeddings[0]
        return all_embeddings


class ChunkingService:
    """Chunk documents for golden dataset."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        """Initialize chunking parameters.

        Args:
            chunk_size: Size of each chunk in characters
            overlap: Number of characters to overlap between chunks

        Raises:
            ValueError: If overlap >= chunk_size
        """
        if overlap >= chunk_size:
            raise ValueError(f"Overlap ({overlap}) must be less than chunk_size ({chunk_size})")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.processor = DocumentProcessor()
        self.embedding_service = EmbeddingService()
        self.neo4j = Neo4jConnectionFixed()

    def chunk_document(self, doc: GoldenDoc) -> List[GoldenChunk]:
        """Chunk a GoldenDoc document into smaller pieces, preferring sentence boundaries detected by a regex-based helper method.

        Args:
            doc (GoldenDoc): Document to chunk

        Returns:
            List[GoldenChunk]: List of document chunks
        """
        content = doc.content
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(content):
            end = self._find_chunk_end(content, start)
            chunk_text = content[start:end].strip()

            if chunk_text:
                chunks.append(
                    GoldenChunk(
                        chunk_id=f"{doc.doc_id}_chunk_{chunk_index}",
                        doc_id=doc.doc_id,
                        content=chunk_text,
                        chunk_index=chunk_index,
                        source_meta=doc.source_meta,
                        reg_citations=getattr(doc, "reg_citations", None),
                        expected_outcomes=getattr(doc, "expected_outcomes", None),
                    )
                )
                chunk_index += 1

            # Calculate next start position with overlap
            if end < len(content):
                next_start = min(start + self.chunk_size - self.overlap, len(content))
            else:
                next_start = end

            if next_start <= start:
                logger.warning("Chunking stalled, advancing by one character.")
                next_start = start + 1

            start = next_start

        return chunks

    def _find_chunk_end(self, content: str, start: int) -> int:
        """Find the end index for a chunk, preferring sentence boundaries."""
        sentence_endings = re.compile(r"[.!?]\s+")
        end = min(start + self.chunk_size, len(content))
        if end < len(content):
            search_start = min(start + int(self.chunk_size * 0.8), end - 1)
            search_text = content[search_start:end] if search_start < end else ""
            matches = list(sentence_endings.finditer(search_text))
            if matches:
                end = search_start + matches[-1].end()
            else:
                last_space = content.rfind(" ", start, end)
                if last_space != -1 and last_space > start:
                    end = last_space
        return end

    def _load_and_validate_documents(self, file_path: str) -> List[GoldenDoc]:
        """Load and validate documents from file.

        Args:
            file_path: Path to the golden dataset JSON file

        Returns:
            List of validated GoldenDoc instances

        Raises:
            ValueError: If documents are invalid
        """
        documents = self.processor.load_golden_dataset(file_path)
        logger.info("📚 Loaded %s documents", len(documents))

        # Validate all documents
        validated_docs = []
        for doc in documents:
            if self.processor.validate_document(doc):
                validated_docs.append(doc)
            else:
                logger.warning("Invalid document skipped: %s", doc.doc_id)

        return validated_docs

    def _generate_embeddings(self, chunks: List[GoldenChunk]) -> List[List[float]]:
        """Generate embeddings for document chunks.

        Args:
            chunks: List of document chunks

        Returns:
            List of embedding vectors
        """
        if not chunks:
            return []

        # Extract text from chunks for batch processing
        chunk_texts = [chunk.content for chunk in chunks]

        # Generate embeddings in batch
        embeddings = self.embedding_service.generate_embedding(chunk_texts)

        # Ensure we always return List[List[float]]
        if isinstance(embeddings, list) and len(embeddings) > 0:
            # Check if we got a single embedding (List[float]) instead of batch (List[List[float]])
            if isinstance(embeddings[0], (int, float)):
                # Single embedding returned as List[float], wrap it in a list
                embeddings = [embeddings]

        # Type-safe conversion to ensure correct return type
        result: List[List[float]] = []
        for emb in embeddings:
            if isinstance(emb, list) and len(emb) > 0 and isinstance(emb[0], (int, float)):
                # This is a single embedding (List[float])
                emb_typed: List[float] = emb  # type: ignore
                result.append(emb_typed)
            elif isinstance(emb, list) and len(emb) > 0 and isinstance(emb[0], list):
                # This is already a list of embeddings (List[List[float]])
                # Type cast to ensure proper typing
                emb_list: List[List[float]] = emb  # type: ignore
                result.extend(emb_list)
            # This shouldn't happen but handle gracefully
            elif not isinstance(emb, list):
                result.append([float(emb)])
            else:
                # emb is a list but not matching expected patterns
                emb_typed: List[float] = emb  # type: ignore
                result.append(emb_typed)

        logger.info("Generated %d embeddings", len(result))
        return result

    def _ensure_vector_index(self) -> None:
        """Ensure Neo4j vector index exists."""
        driver = self.neo4j.get_driver()
        with driver.session() as session:
            try:
                session.run(
                    """
                    CREATE VECTOR INDEX golden_chunk_embeddings IF NOT EXISTS
                    FOR (c:GoldenChunk)
                    ON (c.embedding)
                    OPTIONS {
                        indexConfig: {
                            `vector.dimensions`: 384,
                            `vector.similarity_function`: 'cosine',
                        },
                    }
                """,
                )
                logger.info("✅ Vector index verified")
            except Exception as e:
                logger.info("⚠️ Index check: %s" % e)

    def _write_document_to_neo4j(self, doc: GoldenDoc) -> None:
        """Write document to Neo4j database.

        Args:
            doc: Document to write
        """
        driver = self.neo4j.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (d:GoldenDocument {doc_id: $doc_id})
                SET d.content = $content,
                    d.source = $source,
                    d.created_at = datetime()
            """,
                doc_id=doc.doc_id,
                content=doc.content,
                source=doc.source_meta.origin if doc.source_meta else "unknown",
            )

    def _write_chunks_to_neo4j(
        self, doc_id: str, chunks: List[GoldenChunk], embeddings: List[List[float]]
    ) -> int:
        """Write chunks and embeddings to Neo4j database using batch insertion.

        Args:
            doc_id: Parent document ID
            chunks: List of document chunks
            embeddings: List of embedding vectors

        Returns:
            Number of chunks created
        """
        if not chunks:
            return 0

        driver = self.neo4j.get_driver()

        # Prepare chunk data for batch insertion
        chunk_data = [
            {
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "embedding": embedding,
                "chunk_index": chunk.chunk_index,
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]

        with driver.session() as session:
            result = session.run(
                """
                // Ensure document exists
                MATCH (d:GoldenDocument {doc_id: $doc_id})

                // Batch process all chunks with UNWIND
                UNWIND $chunks AS chunk_data

                // Use MERGE to ensure idempotency (no duplicates on re-ingestion)
                MERGE (c:GoldenChunk {chunk_id: chunk_data.chunk_id})
                SET c.content = chunk_data.content,
                    c.embedding = chunk_data.embedding,
                    c.chunk_index = chunk_data.chunk_index,
                    c.created_at = datetime()

                // Create relationship if it doesn't exist
                MERGE (d)-[:HAS_CHUNK]->(c)

                RETURN count(c) as chunks_created
                """,
                doc_id=doc_id,
                chunks=chunk_data,
            )

            # Get the count of chunks created from the query result
            for record in result:
                return record["chunks_created"]

        return 0

    def _process_single_document(self, doc: GoldenDoc) -> Dict[str, Any]:
        """Process a single document through the ingestion pipeline.

        Args:
            doc: Document to process

        Returns:
            Processing result dictionary
        """
        result = {"success": False, "chunks_created": 0, "embeddings_generated": 0, "error": None}

        try:
            # Chunk the document
            chunks = self.chunk_document(doc)

            # Generate embeddings
            embeddings = self._generate_embeddings(chunks)
            result["embeddings_generated"] = len(embeddings)

            # Prepare chunk data for batch insertion
            chunk_data = [
                {
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "embedding": embedding,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk, embedding in zip(chunks, embeddings)
            ]

            # Write document and chunks in a single transaction for better performance
            driver = self.neo4j.get_driver()
            with driver.session() as session:
                tx_result = session.run(
                    """
                    // First merge the document
                    MERGE (d:GoldenDocument {doc_id: $doc_id})
                    SET d.content = $content,
                        d.source = $source,
                        d.created_at = datetime()

                    // Then batch process all chunks with UNWIND
                    WITH d
                    UNWIND $chunks AS chunk_data

                    // Use MERGE to ensure idempotency
                    MERGE (c:GoldenChunk {chunk_id: chunk_data.chunk_id})
                    SET c.content = chunk_data.content,
                        c.embedding = chunk_data.embedding,
                        c.chunk_index = chunk_data.chunk_index,
                        c.created_at = datetime()

                    // Create relationship if it doesn't exist
                    MERGE (d)-[:HAS_CHUNK]->(c)

                    RETURN count(c) as chunks_created
                    """,
                    doc_id=doc.doc_id,
                    content=doc.content,
                    source=doc.source_meta.origin if doc.source_meta else "unknown",
                    chunks=chunk_data,
                )

                # Get the count of chunks created from the query result
                for record in tx_result:
                    result["chunks_created"] = record["chunks_created"]

            result["success"] = True
            logger.info(
                "✅ Processed document: %s with %d chunks", doc.doc_id, result["chunks_created"]
            )

        except (ValueError, RuntimeError, ConnectionError) as e:
            result["error"] = f"Failed to process document {doc.doc_id}: {str(e)}"
            logger.error(result["error"])

        return result

    def ingest_from_file(self, file_path: str) -> Dict[str, Any]:
        """Ingest golden dataset from file.

        Args:
            file_path: Path to the golden dataset JSON file

        Returns:
            Ingestion result summary
        """
        result = {
            "success": False,
            "documents_processed": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
            "errors": [],
        }

        try:
            # Load and validate documents
            documents = self._load_and_validate_documents(file_path)

            if not documents:
                logger.error("No valid documents found in file")
                result["errors"].append("No valid documents found in file")
                return result

            # Ensure vector index exists
            self._ensure_vector_index()
            # Process each document
            for doc in documents:
                doc_result = self._process_single_document(doc)

                if doc_result["success"]:
                    result["documents_processed"] += 1
                    result["chunks_created"] += doc_result["chunks_created"]
                    result["embeddings_generated"] += doc_result["embeddings_generated"]
                elif doc_result["error"]:
                    result["errors"].append(doc_result["error"])

            result["success"] = result["documents_processed"] > 0
            if not result["success"]:
                result["errors"].append("No valid documents found in file")

        except (ValueError, RuntimeError, IOError) as e:
            result["errors"].append(f"Ingestion pipeline error: {str(e)}")
            logger.error("❌ Pipeline error: %s", e)

        return result

    def search_similar(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar chunks using vector similarity."""
        query_embedding = self.embedding_service.generate_embedding(query)
        driver = self.neo4j.get_driver()
        results = []
        with driver.session() as session:
            result = session.run(
                """
                CALL db.index.vector.queryNodes(
                    'golden_chunk_embeddings',
                    $limit,
                    $query_embedding
                ) YIELD node, score
                MATCH (d:GoldenDocument)-[:HAS_CHUNK]->(node)
                RETURN node.chunk_id as chunk_id,
                       node.content as content,
                       d.doc_id as doc_id,
                       d.source as source,
                       score
                ORDER BY score DESC
            """,
                limit=limit,
                query_embedding=query_embedding,
            )
            for record in result:
                results.append(
                    {
                        "chunk_id": record["chunk_id"],
                        "content": record["content"],
                        "doc_id": record["doc_id"],
                        "source": record["source"],
                        "score": record["score"],
                    }
                )
        return results
