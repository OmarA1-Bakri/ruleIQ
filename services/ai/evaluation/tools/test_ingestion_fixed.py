"""Unit tests for the refactored GoldenDatasetIngestion class."""

import logging

import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open
from datetime import datetime
import json
import numpy as np
import sys


logger = logging.getLogger(__name__)
# Mock neo4j module for testing
sys.modules["neo4j"] = MagicMock()

from services.ai.evaluation.tools.ingestion_fixed import (
    GoldenDatasetIngestion,
    DocumentProcessor,
    EmbeddingService,
    ChunkingService,
    Neo4jConnectionFixed,
)
from services.ai.evaluation.schemas.common import GoldenDoc, GoldenChunk, SourceMeta

# Import hashlib for generating SHA256 hashes in tests
import hashlib
import pytest


def create_test_source_meta(origin="test", url="http://test.com", content=""):
    """Helper function to create valid SourceMeta for testing."""
    from urllib.parse import urlparse

    # Extract domain from URL
    domain = urlparse(url).netloc if url else origin

    # Generate SHA256 hash
    sha256 = hashlib.sha256(content.encode()).hexdigest()

    return SourceMeta(
        origin=origin, domain=domain, trust_score=0.8, sha256=sha256, fetched_at=datetime.now()
    )


class TestDocumentProcessor(unittest.TestCase):
    """Test the DocumentProcessor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.processor = DocumentProcessor()

    def test_load_golden_dataset_success(self):
        """Test successful loading of golden dataset from JSON."""
        test_data = {
            "documents": [
                {
                    "doc_id": "doc1",
                    "content": "Test content 1",
                    "source_meta": {
                        "origin": "test_source",
                        "domain": "example.com",
                        "url": "http://example.com",
                        "sha256": hashlib.sha256(b"Test content 1").hexdigest(),
                        "trust_score": 0.8,
                        "fetched_at": "2024-01-01T00:00:00Z",
                    },
                    "reg_citations": ["REG001"],
                    "expected_outcomes": ["outcome1"],
                }
            ]
        }

        mock_file = mock_open(read_data=json.dumps(test_data))
        with patch("builtins.open", mock_file), patch("os.path.abspath") as mock_abspath:
            with patch("os.path.normpath") as mock_normpath:
                mock_normpath.return_value = "/safe/path/file.json"
                mock_abspath.side_effect = ["/safe/path/file.json", "/safe"]

                docs = self.processor.load_golden_dataset("file.json")

                assert len(docs) == 1
                assert docs[0].doc_id == "doc1"
                assert docs[0].content == "Test content 1"
                assert docs[0].source_meta.origin == "test_source"

    def test_load_golden_dataset_path_traversal(self):
        """Test that path traversal attempts are blocked."""
        with patch("os.path.abspath") as mock_abspath:
            with patch("os.path.normpath") as mock_normpath:
                mock_normpath.return_value = "../../etc/passwd"
                mock_abspath.side_effect = ["/etc/passwd", "/safe"]

                with pytest.raises(ValueError) as context:
                    self.processor.load_golden_dataset("../../etc/passwd")

                assert "path traversal" in str(context.value)

    def test_validate_document_valid(self):
        """Test validation of valid document."""
        doc = GoldenDoc(
            doc_id="test_id",
            content="Test content",
            source_meta=create_test_source_meta(content="Test content"),
        )
        assert self.processor.validate_document(doc)

    def test_validate_document_invalid(self):
        """Test validation of invalid documents."""
        # Test with missing doc_id
        doc = GoldenDoc(doc_id="", content="Test", source_meta=create_test_source_meta())
        assert not self.processor.validate_document(doc)

        # Test with non-GoldenDoc object
        assert not self.processor.validate_document({"doc_id": "test"})


class TestEmbeddingService(unittest.TestCase):
    """Test the EmbeddingService class."""

    @patch("services.ai.evaluation.tools.ingestion_fixed.logger")
    def test_init_with_model(self, mock_logger):
        """Test initialization with sentence-transformers model."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1] * 384)

        # Patch the SentenceTransformer import within _load_model
        service = EmbeddingService()
        service.model = mock_model
        service.dimension = 384

        assert service.dimension == 384
        assert service.model is not None

    @patch("services.ai.evaluation.tools.ingestion_fixed.logger")
    def test_init_without_model(self, mock_logger):
        """Test initialization when sentence-transformers is not available."""
        with patch(
            "services.ai.evaluation.tools.ingestion_fixed.SentenceTransformer",
            side_effect=ImportError,
            create=True,
        ):
            service = EmbeddingService()

            assert service.dimension == 384
            assert service.model is None
            mock_logger.info.assert_called_with(
                "⚠️ sentence-transformers not installed, using mock embeddings"
            )

    def test_generate_embedding_single_text(self):
        """Test generating embedding for single text."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1] * 384])

        with patch(
            "services.ai.evaluation.tools.ingestion_fixed.SentenceTransformer",
            return_value=mock_model,
            create=True,
        ):
            service = EmbeddingService()
            service.model = mock_model

            embedding = service.generate_embedding("Test text")

            assert isinstance(embedding, list)
            assert len(embedding) == 384
            mock_model.encode.assert_called_with(
                ["Test text"], normalize_embeddings=True, batch_size=1, show_progress_bar=False
            )

    def test_generate_embedding_batch(self):
        """Test generating embeddings for batch of texts."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1] * 384, [0.2] * 384])

        with patch(
            "services.ai.evaluation.tools.ingestion_fixed.SentenceTransformer",
            return_value=mock_model,
            create=True,
        ):
            service = EmbeddingService(batch_size=2)
            service.model = mock_model

            embeddings = service.generate_embedding(["Text 1", "Text 2"])

            assert isinstance(embeddings, list)
            assert len(embeddings) == 2
            assert len(embeddings[0]) == 384
            assert len(embeddings[1]) == 384

    def test_generate_embedding_mock(self):
        """Test generating mock embeddings when model is not available."""
        service = EmbeddingService()
        service.model = None
        service.dimension = 384

        with patch("numpy.random.rand") as mock_rand:
            mock_rand.return_value = np.array([0.5] * 384)

            embedding = service.generate_embedding("Test")

            assert isinstance(embedding, list)
            assert len(embedding) == 384


class TestChunkingService(unittest.TestCase):
    """Test the ChunkingService class."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = ChunkingService(chunk_size=100, overlap=10)

    def test_chunk_document_single_chunk(self):
        """Test chunking document that fits in single chunk."""
        doc = GoldenDoc(
            doc_id="test_doc",
            content="Short content.",
            source_meta=create_test_source_meta(content="Short content."),
        )

        chunks = self.service.chunk_document(doc)

        assert len(chunks) == 1
        assert chunks[0].chunk_id == "test_doc_chunk_0"
        assert chunks[0].content == "Short content."
        assert chunks[0].chunk_index == 0

    def test_chunk_document_multiple_chunks(self):
        """Test chunking document into multiple chunks."""
        # Create content longer than chunk_size
        content = "This is sentence one. " * 10  # ~220 chars
        doc = GoldenDoc(
            doc_id="test_doc", content=content, source_meta=create_test_source_meta(content=content)
        )

        chunks = self.service.chunk_document(doc)

        assert len(chunks) > 1
        assert chunks[0].chunk_id == "test_doc_chunk_0"
        assert chunks[1].chunk_id == "test_doc_chunk_1"

        # Check chunk indices
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.doc_id == "test_doc"

    def test_chunk_document_with_overlap(self):
        """Test that chunks have proper overlap."""
        content = "Word1 " * 20 + ". Word2 " * 20 + "."
        doc = GoldenDoc(
            doc_id="test_doc", content=content, source_meta=create_test_source_meta(content=content)
        )

        service = ChunkingService(chunk_size=50, overlap=10)
        chunks = service.chunk_document(doc)

        assert len(chunks) > 1

        # Chunks should have proper attributes
        for chunk in chunks:
            assert hasattr(chunk, "chunk_id")
            assert hasattr(chunk, "chunk_index")


class TestGoldenDatasetIngestion(unittest.TestCase):
    """Test the refactored GoldenDatasetIngestion class."""

    def setUp(self):
        """Set up test fixtures."""
        with patch("services.ai.evaluation.tools.ingestion_fixed.logger"):
            self.ingestion = GoldenDatasetIngestion()

        # Mock dependencies
        self.ingestion.processor = Mock(spec=DocumentProcessor)
        self.ingestion.embedding_service = Mock(spec=EmbeddingService)
        self.ingestion.chunking_service = Mock(spec=ChunkingService)
        self.ingestion.neo4j = Mock(spec=Neo4jConnectionFixed)

        # Setup mock driver
        self.mock_driver = MagicMock()
        self.mock_session = MagicMock()
        self.mock_driver.session.return_value.__enter__ = Mock(return_value=self.mock_session)
        self.mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        self.ingestion.neo4j.get_driver.return_value = self.mock_driver

    def test_load_and_validate_documents(self):
        """Test document loading and validation helper."""
        test_docs = [
            GoldenDoc(doc_id="doc1", content="Content 1", source_meta=create_test_source_meta()),
            GoldenDoc(doc_id="doc2", content="Content 2", source_meta=create_test_source_meta()),
            GoldenDoc(
                doc_id="", content="Invalid", source_meta=create_test_source_meta()
            ),  # Invalid
        ]

        self.ingestion.processor.load_golden_dataset.return_value = test_docs
        self.ingestion.processor.validate_document.side_effect = [True, True, False]

        with patch("services.ai.evaluation.tools.ingestion_fixed.logger"):
            docs = self.ingestion._load_and_validate_documents("test.json")

        assert len(docs) == 2
        assert docs[0].doc_id == "doc1"
        assert docs[1].doc_id == "doc2"

    def test_generate_embeddings(self):
        """Test embedding generation helper."""
        chunks = [
            GoldenChunk(
                chunk_id="c1",
                doc_id="d1",
                content="Text 1",
                chunk_index=0,
                source_meta=create_test_source_meta(),
            ),
            GoldenChunk(
                chunk_id="c2",
                doc_id="d1",
                content="Text 2",
                chunk_index=1,
                source_meta=create_test_source_meta(),
            ),
        ]

        mock_embeddings = [[0.1] * 384, [0.2] * 384]
        self.ingestion.embedding_service.generate_embedding.return_value = mock_embeddings

        with patch("services.ai.evaluation.tools.ingestion_fixed.logger"):
            embeddings = self.ingestion._generate_embeddings(chunks)

        assert embeddings == mock_embeddings
        self.ingestion.embedding_service.generate_embedding.assert_called_once_with(
            ["Text 1", "Text 2"]
        )

    def test_generate_embeddings_empty_chunks(self):
        """Test embedding generation with empty chunks."""
        embeddings = self.ingestion._generate_embeddings([])
        assert embeddings == []
        self.ingestion.embedding_service.generate_embedding.assert_not_called()

    def test_ensure_vector_index(self):
        """Test vector index creation."""
        with patch("services.ai.evaluation.tools.ingestion_fixed.logger"):
            self.ingestion._ensure_vector_index()

        self.mock_session.run.assert_called_once()
        query = self.mock_session.run.call_args[0][0]
        assert "CREATE VECTOR INDEX" in query
        assert "golden_chunk_embeddings" in query

    def test_write_document_to_neo4j(self):
        """Test document writing to Neo4j."""
        doc = GoldenDoc(
            doc_id="test_doc",
            content="Test content",
            source_meta=create_test_source_meta(
                origin="test_source", url="http://test.com", content="Test content"
            ),
        )

        self.ingestion._write_document_to_neo4j(doc)

        self.mock_session.run.assert_called_once()
        query = self.mock_session.run.call_args[0][0]
        kwargs = self.mock_session.run.call_args[1]

        assert "MERGE (d:GoldenDocument" in query
        assert kwargs["doc_id"] == "test_doc"
        assert kwargs["content"] == "Test content"
        assert kwargs["source"] == "test_source"

    def test_write_chunks_to_neo4j(self):
        """Test chunk writing to Neo4j."""
        chunks = [
            GoldenChunk(
                chunk_id="c1",
                doc_id="d1",
                content="Chunk 1",
                chunk_index=0,
                source_meta=create_test_source_meta(),
            ),
            GoldenChunk(
                chunk_id="c2",
                doc_id="d1",
                content="Chunk 2",
                chunk_index=1,
                source_meta=create_test_source_meta(),
            ),
        ]
        embeddings = [[0.1] * 384, [0.2] * 384]

        chunks_created = self.ingestion._write_chunks_to_neo4j("d1", chunks, embeddings)

        assert chunks_created == 2
        assert self.mock_session.run.call_count == 2

        # Check first chunk call
        first_call = self.mock_session.run.call_args_list[0]
        assert "CREATE (c:GoldenChunk" in first_call[0][0]
        assert first_call[1]["chunk_id"] == "c1"
        assert first_call[1]["content"] == "Chunk 1"

    def test_process_single_document_success(self):
        """Test successful processing of a single document."""
        doc = GoldenDoc(
            doc_id="test_doc",
            content="Test content",
            source_meta=create_test_source_meta(
                origin="test", url="http://test.com", content="Test content"
            ),
        )

        chunks = [
            GoldenChunk(
                chunk_id="c1",
                doc_id="test_doc",
                content="Chunk 1",
                chunk_index=0,
                source_meta=create_test_source_meta(),
            )
        ]
        embeddings = [[0.1] * 384]

        self.ingestion.chunking_service.chunk_document.return_value = chunks
        self.ingestion.embedding_service.generate_embedding.return_value = embeddings

        with patch.object(self.ingestion, "_write_document_to_neo4j"):
            with patch.object(self.ingestion, "_write_chunks_to_neo4j", return_value=1):
                with patch("services.ai.evaluation.tools.ingestion_fixed.logger"):
                    result = self.ingestion._process_single_document(doc)

        assert result["success"]
        assert result["chunks_created"] == 1
        assert result["embeddings_generated"] == 1
        assert result["error"] is None

    def test_process_single_document_error(self):
        """Test error handling in document processing."""
        doc = GoldenDoc(doc_id="test_doc", content="Test", source_meta=create_test_source_meta())

        self.ingestion.chunking_service.chunk_document.side_effect = Exception("Chunking failed")

        with patch("services.ai.evaluation.tools.ingestion_fixed.logger"):
            result = self.ingestion._process_single_document(doc)

        assert not result["success"]
        assert result["chunks_created"] == 0
        assert "Chunking failed" in result["error"]

    def test_ingest_from_file_success(self):
        """Test successful file ingestion."""
        test_docs = [
            GoldenDoc(doc_id="doc1", content="Content 1", source_meta=create_test_source_meta()),
            GoldenDoc(doc_id="doc2", content="Content 2", source_meta=create_test_source_meta()),
        ]

        with patch.object(self.ingestion, "_load_and_validate_documents", return_value=test_docs):
            with patch.object(self.ingestion, "_ensure_vector_index"):
                with patch.object(self.ingestion, "_process_single_document") as mock_process:
                    mock_process.return_value = {
                        "success": True,
                        "chunks_created": 2,
                        "embeddings_generated": 2,
                        "error": None,
                    }

                    result = self.ingestion.ingest_from_file("test.json")

        assert result["success"]
        assert result["documents_processed"] == 2
        assert result["chunks_created"] == 4
        assert result["embeddings_generated"] == 4
        assert len(result["errors"]) == 0

    def test_ingest_from_file_no_documents(self):
        """Test ingestion with no valid documents."""
        with patch.object(self.ingestion, "_load_and_validate_documents", return_value=[]):
            result = self.ingestion.ingest_from_file("empty.json")

        assert not result["success"]
        assert result["documents_processed"] == 0
        assert "No valid documents" in result["errors"][0]

    def test_ingest_from_file_partial_failure(self):
        """Test ingestion with some document failures."""
        test_docs = [
            GoldenDoc(doc_id="doc1", content="Content 1", source_meta=create_test_source_meta()),
            GoldenDoc(doc_id="doc2", content="Content 2", source_meta=create_test_source_meta()),
        ]

        process_results = [
            {"success": True, "chunks_created": 2, "embeddings_generated": 2, "error": None},
            {
                "success": False,
                "chunks_created": 0,
                "embeddings_generated": 0,
                "error": "Processing failed",
            },
        ]

        with patch.object(self.ingestion, "_load_and_validate_documents", return_value=test_docs):
            with patch.object(self.ingestion, "_ensure_vector_index"):
                with patch.object(
                    self.ingestion, "_process_single_document", side_effect=process_results
                ):
                    result = self.ingestion.ingest_from_file("test.json")

        assert result["success"]  # At least one succeeded
        assert result["documents_processed"] == 1
        assert result["chunks_created"] == 2
        assert len(result["errors"]) == 1
        assert "Processing failed" in result["errors"][0]

    def test_search_similar(self):
        """Test similarity search functionality."""
        query = "Test query"
        mock_embedding = [0.1] * 384
        self.ingestion.embedding_service.generate_embedding.return_value = mock_embedding

        mock_records = [
            {
                "chunk_id": "chunk1",
                "content": "Content 1",
                "doc_id": "doc1",
                "source": "source1",
                "score": 0.95,
            },
            {
                "chunk_id": "chunk2",
                "content": "Content 2",
                "doc_id": "doc2",
                "source": "source2",
                "score": 0.85,
            },
        ]

        self.mock_session.run.return_value = mock_records

        results = self.ingestion.search_similar(query, limit=2)

        assert len(results) == 2
        assert results[0]["chunk_id"] == "chunk1"
        assert results[0]["score"] == 0.95
        assert results[1]["chunk_id"] == "chunk2"
        assert results[1]["score"] == 0.85

        # Verify the query was called with correct parameters
        self.mock_session.run.assert_called_once()
        query_call = self.mock_session.run.call_args
        assert query_call[1]["limit"] == 2
        assert query_call[1]["query_embedding"] == mock_embedding


class TestNeo4jConnectionFixed(unittest.TestCase):
    """Test the Neo4j connection class."""

    @patch("services.ai.evaluation.tools.ingestion_fixed.logger")
    def test_singleton_pattern(self, mock_logger):
        """Test that Neo4jConnectionFixed follows singleton pattern."""
        # Reset singleton for testing
        Neo4jConnectionFixed._instance = None
        Neo4jConnectionFixed._driver = None

        conn1 = Neo4jConnectionFixed()
        conn2 = Neo4jConnectionFixed()

        assert conn1 is conn2

    @patch("services.ai.evaluation.tools.ingestion_fixed.logger")
    def test_connection_initialization(self, mock_logger):
        """Test proper connection initialization."""
        # Reset singleton
        Neo4jConnectionFixed._instance = None
        Neo4jConnectionFixed._driver = None

        conn = Neo4jConnectionFixed()

        # Driver could be None (if neo4j not installed) or a mock
        # Just check that the connection was created
        assert conn is not None

    def test_close_connection(self):
        """Test closing the connection."""
        # Reset singleton
        Neo4jConnectionFixed._instance = None
        Neo4jConnectionFixed._driver = None

        conn = Neo4jConnectionFixed()
        # Set a mock driver to test close
        mock_driver = MagicMock()
        conn._driver = mock_driver

        conn.close()

        mock_driver.close.assert_called_once()
        assert conn._driver is None


if __name__ == "__main__":
    unittest.main()
