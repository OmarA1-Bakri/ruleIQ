"""Test ingestion tool for Golden Dataset."""

from typing import Any
import pytest
from unittest.mock import Mock, patch
import json
from datetime import datetime

from services.ai.evaluation.tools.ingestion import (
    GoldenDatasetIngestion,
    DocumentProcessor,
    ChunkProcessor,
    EmbeddingGenerator,
    GraphIngestion,
)
from services.ai.evaluation.schemas.common import (
    GoldenDoc,
    GoldenChunk,
    SourceMeta,
    RegCitation,
    ExpectedOutcome,
)


class TestDocumentProcessor:
    """Test document processing functionality."""

    def test_load_golden_dataset(self) -> Any:
        """Test loading golden dataset from JSON file."""
        processor = DocumentProcessor()

        # Create test data
        test_data = {
            "documents": [
                {
                    "doc_id": "doc1",
                    "content": "Test document content.",
                    "source_meta": {
                        "origin": "regulatory",
                        "domain": "compliance",
                        "fetched_at": "2025-01-01T00:00:00Z",
                        "trust_score": 0.9,
                    },
                },
            ],
        }

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(test_data),
            )

            documents = processor.load_golden_dataset("test.json")

            assert len(documents) == 1
            assert documents[0].doc_id == "doc1"
            assert documents[0].content == "Test document content."
            assert documents[0].source_meta.trust_score == 0.9

    def test_validate_document_schema(self) -> Any:
        """Test document schema validation."""
        processor = DocumentProcessor()

        # Valid document
        valid_doc = GoldenDoc(
            doc_id="doc1",
            content="Test content",
            source_meta=SourceMeta(
                origin="test",
                domain="compliance",
                fetched_at=datetime.now(),
                trust_score=0.8,
            ),
        )

        assert processor.validate_document(valid_doc) is True

        # Invalid document (missing required fields)
        with pytest.raises(ValueError):
            invalid_doc = {"doc_id": "doc1"}  # Missing content
            processor.validate_document(invalid_doc)

    def test_preprocess_document_content(self) -> Any:
        """Test document content preprocessing."""
        processor = DocumentProcessor()

        # Test with various content formats
        content = "  This is a TEST.  \n\nWith multiple   spaces.  "
        processed = processor.preprocess_content(content)

        assert processed == "This is a TEST. With multiple spaces."
        assert "  " not in processed
        assert processed.strip() == processed


class TestChunkProcessor:
    """Test document chunking functionality."""

    def test_chunk_document_basic(self) -> Any:
        """Test basic document chunking."""
        processor = ChunkProcessor(
            chunk_size=100,
            overlap=10,  # ~25 tokens  # ~2-3 tokens,
        )

        # Create a document with enough content to chunk
        doc = GoldenDoc(
            doc_id="doc1",
            content="This is sentence one. " * 10,  # ~70 tokens
            source_meta=SourceMeta(
                origin="test",
                domain="compliance",
                fetched_at=datetime.now(),
                trust_score=0.8,
            ),
        )

        chunks = processor.chunk_document(doc)

        assert len(chunks) >= 2
        assert all(isinstance(chunk, GoldenChunk) for chunk in chunks)
        assert all(chunk.doc_id == "doc1" for chunk in chunks)
        assert all(chunk.chunk_index >= 0 for chunk in chunks)

    def test_chunk_overlap(self) -> Any:
        """Test chunk overlap functionality."""
        processor = ChunkProcessor(chunk_size=50, overlap=10)

        content = "Word " * 30  # 30 words
        doc = GoldenDoc(
            doc_id="doc1",
            content=content,
            source_meta=SourceMeta(
                origin="test",
                domain="compliance",
                fetched_at=datetime.now(),
                trust_score=0.8,
            ),
        )

        chunks = processor.chunk_document(doc)

        # Check that consecutive chunks have overlap
        if len(chunks) > 1:
            for i in range(len(chunks) - 1):
                chunk1_end = chunks[i].content.split()[-5:]
                chunk2_start = chunks[i + 1].content.split()[:5]
                # Should have some overlapping words
                overlap = set(chunk1_end) & set(chunk2_start)
                assert len(overlap) > 0

    def test_chunk_metadata_preservation(self) -> Any:
        """Test that chunk preserves document metadata."""
        processor = ChunkProcessor()

        doc = GoldenDoc(
            doc_id="doc1",
            content="Test content " * 100,
            source_meta=SourceMeta(
                origin="regulatory",
                domain="compliance",
                fetched_at=datetime.now(),
                trust_score=0.95,
            ),
            reg_citations=[
                RegCitation(
                    framework="ISO 27001",
                    article="A.12.1",
                    label="Operational procedures",
                ),
            ],
            expected_outcomes=[
                ExpectedOutcome(
                    outcome_id="out1",
                    description="Test outcome",
                    tags=["security"],
                ),
            ],
        )

        chunks = processor.chunk_document(doc)

        for chunk in chunks:
            assert chunk.doc_id == doc.doc_id
            assert chunk.source_meta == doc.source_meta
            assert chunk.reg_citations == doc.reg_citations
            assert chunk.expected_outcomes == doc.expected_outcomes


class TestEmbeddingGenerator:
    """Test embedding generation functionality."""

    @patch("sentence_transformers.SentenceTransformer")
    def test_initialize_model(self, mock_st: Any) -> Any:
        """Test model initialization."""
        generator = EmbeddingGenerator()

        mock_st.assert_called_once_with("BAAI/bge-small-en-v1.5")
        assert generator.model is not None
        assert generator.dimension == 384

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_embedding_single(self, mock_st: Any) -> Any:
        """Test single text embedding generation."""
        mock_model = Mock()
        mock_model.encode.return_value = [[0.1] * 384]
        mock_st.return_value = mock_model

        generator = EmbeddingGenerator()
        embedding = generator.generate_embedding("Test text")

        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)
        mock_model.encode.assert_called_once()

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_embeddings_batch(self, mock_st: Any) -> Any:
        """Test batch embedding generation."""
        mock_model = Mock()
        mock_model.encode.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
        mock_st.return_value = mock_model

        generator = EmbeddingGenerator()
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = generator.generate_embeddings_batch(texts)

        assert len(embeddings) == 3
        assert all(len(emb) == 384 for emb in embeddings)
        mock_model.encode.assert_called_once_with(texts, convert_to_tensor=False)

    @patch("sentence_transformers.SentenceTransformer")
    def test_embedding_normalization(self, mock_st: Any) -> Any:
        """Test that embeddings are normalized."""
        import numpy as np

        mock_model = Mock()
        # Return unnormalized embeddings
        mock_model.encode.return_value = np.array([[1.0, 2.0, 3.0]])
        mock_st.return_value = mock_model

        generator = EmbeddingGenerator()
        embedding = generator.generate_embedding("Test", normalize=True)

        # Check normalization (L2 norm should be 1)
        norm = sum(x**2 for x in embedding) ** 0.5
        assert abs(norm - 1.0) < 0.01


class TestGraphIngestion:
    """Test Neo4j graph ingestion functionality."""

    @patch("services.ai.evaluation.infrastructure.neo4j_setup.Neo4jConnection")
    def test_initialize_connection(self, mock_conn_class: Any) -> Any:
        """Test Neo4j connection initialization."""
        mock_conn = Mock()
        mock_conn_class.return_value = mock_conn

        ingestion = GraphIngestion()

        assert ingestion.connection == mock_conn
        mock_conn_class.assert_called_once()

    @patch("services.ai.evaluation.infrastructure.neo4j_setup.Neo4jConnection")
    def test_ingest_document(self, mock_conn_class: Any) -> Any:
        """Test document ingestion to Neo4j."""
        mock_conn = Mock()
        mock_conn_class.return_value = mock_conn

        ingestion = GraphIngestion()

        doc = GoldenDoc(
            doc_id="doc1",
            content="Test document",
            source_meta=SourceMeta(
                origin="test",
                domain="compliance",
                fetched_at=datetime.now(),
                trust_score=0.9,
            ),
        )

        embedding = [0.1] * 384

        result = ingestion.ingest_document(doc, embedding)

        assert result is True
        # Should execute CREATE query
        mock_conn.execute_query.assert_called()
        call_args = mock_conn.execute_query.call_args[0]
        assert "CREATE" in call_args[0]
        assert "Document" in call_args[0]

    @patch("services.ai.evaluation.infrastructure.neo4j_setup.Neo4jConnection")
    def test_ingest_chunk(self, mock_conn_class: Any) -> Any:
        """Test chunk ingestion to Neo4j."""
        mock_conn = Mock()
        mock_conn_class.return_value = mock_conn

        ingestion = GraphIngestion()

        chunk = GoldenChunk(
            chunk_id="chunk1",
            doc_id="doc1",
            chunk_index=0,
            content="Test chunk",
            source_meta=SourceMeta(
                origin="test",
                domain="compliance",
                fetched_at=datetime.now(),
                trust_score=0.9,
            ),
        )

        embedding = [0.1] * 384

        result = ingestion.ingest_chunk(chunk, embedding)

        assert result is True
        # Should execute CREATE query and relationship
        assert mock_conn.execute_query.call_count >= 1

    @patch("services.ai.evaluation.infrastructure.neo4j_setup.Neo4jConnection")
    def test_create_chunk_relationships(self, mock_conn_class: Any) -> Any:
        """Test creating relationships between chunks."""
        mock_conn = Mock()
        mock_conn_class.return_value = mock_conn

        ingestion = GraphIngestion()

        chunks = [
            GoldenChunk(
                chunk_id=f"chunk{i}",
                doc_id="doc1",
                chunk_index=i,
                content=f"Chunk {i}",
                source_meta=SourceMeta(
                    origin="test",
                    domain="compliance",
                    fetched_at=datetime.now(),
                    trust_score=0.9,
                ),
            )
            for i in range(3)
        ]

        result = ingestion.create_chunk_relationships(chunks)

        assert result is True
        # Should create NEXT relationships between consecutive chunks
        calls = mock_conn.execute_query.call_args_list
        assert any("NEXT" in str(call) for call in calls)


class TestGoldenDatasetIngestion:
    """Test complete ingestion pipeline."""

    @patch("services.ai.evaluation.tools.ingestion.GraphIngestion")
    @patch("services.ai.evaluation.tools.ingestion.EmbeddingGenerator")
    @patch("services.ai.evaluation.tools.ingestion.ChunkProcessor")
    @patch("services.ai.evaluation.tools.ingestion.DocumentProcessor")
    def test_complete_ingestion_pipeline(
        self, mock_doc_proc, mock_chunk_proc, mock_embed_gen, mock_graph
    ):
        """Test complete ingestion from file to Neo4j."""
        # Setup mocks
        mock_doc_inst = Mock()
        mock_chunk_inst = Mock()
        mock_embed_inst = Mock()
        mock_graph_inst = Mock()

        mock_doc_proc.return_value = mock_doc_inst
        mock_chunk_proc.return_value = mock_chunk_inst
        mock_embed_gen.return_value = mock_embed_inst
        mock_graph.return_value = mock_graph_inst

        # Mock document loading
        test_docs = [
            GoldenDoc(
                doc_id="doc1",
                content="Test content",
                source_meta=SourceMeta(
                    origin="test",
                    domain="compliance",
                    fetched_at=datetime.now(),
                    trust_score=0.9,
                ),
            ),
        ]
        mock_doc_inst.load_golden_dataset.return_value = test_docs

        # Mock chunking
        test_chunks = [
            GoldenChunk(
                chunk_id="chunk1",
                doc_id="doc1",
                chunk_index=0,
                content="Test chunk",
                source_meta=test_docs[0].source_meta,
            ),
        ]
        mock_chunk_inst.chunk_document.return_value = test_chunks

        # Mock embeddings
        mock_embed_inst.generate_embedding.return_value = [0.1] * 384

        # Mock graph ingestion
        mock_graph_inst.ingest_document.return_value = True
        mock_graph_inst.ingest_chunk.return_value = True

        # Run ingestion
        ingestion = GoldenDatasetIngestion()
        result = ingestion.ingest_from_file("test.json")

        assert result["success"] is True
        assert result["documents_processed"] == 1
        assert result["chunks_created"] >= 1

        # Verify all components were called
        mock_doc_inst.load_golden_dataset.assert_called_once()
        mock_chunk_inst.chunk_document.assert_called()
        mock_embed_inst.generate_embedding.assert_called()
        mock_graph_inst.ingest_document.assert_called()
        mock_graph_inst.ingest_chunk.assert_called()

    @patch("services.ai.evaluation.tools.ingestion.GraphIngestion")
    @patch("services.ai.evaluation.tools.ingestion.EmbeddingGenerator")
    def test_error_handling(self, mock_embed_gen: Any, mock_graph: Any) -> Any:
        """Test error handling in ingestion pipeline."""
        mock_embed_inst = Mock()
        mock_graph_inst = Mock()

        mock_embed_gen.return_value = mock_embed_inst
        mock_graph.return_value = mock_graph_inst

        # Simulate error
        mock_graph_inst.ingest_document.side_effect = Exception("Connection failed")

        ingestion = GoldenDatasetIngestion()

        with pytest.raises(Exception) as exc_info:
            ingestion.ingest_from_file("test.json")

        assert "Connection failed" in str(exc_info.value)
