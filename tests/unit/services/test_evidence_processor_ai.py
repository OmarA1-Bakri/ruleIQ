"""

# Constants

Unit Tests for AI-Enhanced Evidence Processor

Tests the AI classification functionality added to the evidence processor.
"""

import json
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4
import pytest
from database.evidence_item import EvidenceItem
from services.automation.evidence_processor import EvidenceProcessor

from tests.test_constants import DEFAULT_LIMIT, MAX_RETRIES


@pytest.mark.unit
@pytest.mark.ai
class TestEvidenceProcessorAI:
    """Test AI enhancement features in evidence processor"""

    @pytest.fixture
    def mock_evidence_item(self):
        """Create a mock evidence item for testing."""
        evidence = Mock(spec=EvidenceItem)
        evidence.id = uuid4()
        evidence.evidence_type = "unknown"
        evidence.description = "Security policy document outlining access controls"
        evidence.evidence_name = "access_control_policy.pdf"
        evidence.raw_data = json.dumps(
            {"file_type": "pdf", "content": "This policy defines access control procedures..."}
        )
        evidence.metadata = {}
        return evidence

    @pytest.fixture
    def mock_processor(self, db_session):
        """Create evidence processor with mocked dependencies."""
        processor = EvidenceProcessor(db_session)
        processor.ai_model = Mock()
        return processor

    @pytest.mark.asyncio
    async def test_ai_classify_evidence_success(self, mock_processor, mock_evidence_item):
        """Test successful AI classification of evidence."""
        mock_response = Mock()
        mock_response.text = """TYPE: policy_document
CONTROLS: A.5.1.1, A.5.1.2, A.9.1.1
CONFIDENCE: 85
REASONING: Document contains policy language and access control procedures"""
        mock_processor.ai_model.generate_content.return_value = mock_response
        result = await mock_processor._ai_classify_evidence(mock_evidence_item)
        assert result["suggested_type"] == "policy_document"
        assert result["confidence"] == 85
        assert len(result["suggested_controls"]) == MAX_RETRIES
        assert "A.5.1.1" in result["suggested_controls"]
        assert "policy language" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_ai_classify_evidence_fallback(self, mock_processor, mock_evidence_item):
        """Test fallback classification when AI fails."""
        mock_processor.ai_model.generate_content.side_effect = Exception("AI service unavailable")
        result = await mock_processor._ai_classify_evidence(mock_evidence_item)
        assert result["suggested_type"] == "policy_document"
        assert result["confidence"] == 40
        assert result["reasoning"] == "Rule-based classification (AI unavailable)"

    def test_parse_classification_response_valid(self, mock_processor, mock_evidence_item):
        """Test parsing valid AI classification response."""
        response_text = """TYPE: training_record
CONTROLS: A.7.2.2, A.7.2.3
CONFIDENCE: 92
REASONING: Contains training completion certificates and attendance records"""
        result = mock_processor._parse_classification_response(response_text, mock_evidence_item)
        assert result["suggested_type"] == "training_record"
        assert result["confidence"] == 92
        assert len(result["suggested_controls"]) == 2
        assert "training completion" in result["reasoning"]

    def test_parse_classification_response_invalid(self, mock_processor, mock_evidence_item):
        """Test parsing invalid AI response falls back gracefully."""
        response_text = "Invalid response format"
        result = mock_processor._parse_classification_response(response_text, mock_evidence_item)
        assert result["suggested_type"] == "policy_document"
        assert result["confidence"] == 40
        assert "Rule-based classification" in result["reasoning"]

    def test_fallback_classification_policy(self, mock_processor):
        """Test rule-based classification for policy documents."""
        evidence = Mock(spec=EvidenceItem)
        evidence.evidence_type = "unknown"
        evidence.description = "Information security policy and procedures"
        evidence.evidence_name = "security_policy.pdf"
        result = mock_processor._fallback_classification(evidence)
        assert result["suggested_type"] == "policy_document"
        assert result["confidence"] == 40
        assert len(result["suggested_controls"]) > 0

    def test_fallback_classification_training(self, mock_processor):
        """Test rule-based classification for training records."""
        evidence = Mock(spec=EvidenceItem)
        evidence.evidence_type = "unknown"
        evidence.description = "Security awareness training certificate"
        evidence.evidence_name = "training_cert.pdf"
        result = mock_processor._fallback_classification(evidence)
        assert result["suggested_type"] == "training_record"
        assert result["confidence"] == 40
        assert "A.7.2.2" in result["suggested_controls"]

    def test_fallback_classification_unknown(self, mock_processor):
        """Test rule-based classification for unknown evidence."""
        evidence = Mock(spec=EvidenceItem)
        evidence.evidence_type = "document"
        evidence.description = "Some random document"
        evidence.evidence_name = "random.txt"
        result = mock_processor._fallback_classification(evidence)
        assert result["suggested_type"] == "document"
        assert result["confidence"] == 40

    @pytest.mark.asyncio
    async def test_enrich_evidence_with_ai_high_confidence(
        self, mock_processor, mock_evidence_item
    ):
        """Test evidence enrichment with high confidence AI classification."""
        mock_processor._ai_classify_evidence = AsyncMock(
            return_value={
                "suggested_type": "policy_document",
                "confidence": 85,
                "suggested_controls": ["A.5.1.1", "A.5.1.2"],
                "reasoning": "High confidence policy classification",
            }
        )
        result = await mock_processor.enrich_evidence_with_ai(mock_evidence_item)
        assert result.evidence_type == "policy_document"
        assert "ai_classification" in result.metadata
        assert result.metadata["ai_classification"]["confidence"] == 85

    @pytest.mark.asyncio
    async def test_enrich_evidence_with_ai_low_confidence(self, mock_processor, mock_evidence_item):
        """Test evidence enrichment with low confidence AI classification."""
        original_type = mock_evidence_item.evidence_type
        mock_processor._ai_classify_evidence = AsyncMock(
            return_value={
                "suggested_type": "policy_document",
                "confidence": 45,
                "suggested_controls": ["A.5.1.1"],
                "reasoning": "Low confidence classification",
            }
        )
        result = await mock_processor.enrich_evidence_with_ai(mock_evidence_item)
        assert result.evidence_type == original_type
        assert "ai_classification" in result.metadata
        assert result.metadata["ai_classification"]["confidence"] == 45

    @patch("services.automation.evidence_processor.flag_modified")
    def test_process_evidence_with_ai_preparation(
        self, mock_flag_modified, mock_processor, mock_evidence_item
    ):
        """Test that AI processing preparation is added to metadata."""
        mock_processor.process_evidence = Mock()
        mock_processor.process_evidence_with_ai(mock_evidence_item)
        mock_processor.process_evidence.assert_called_once_with(mock_evidence_item)
        assert mock_evidence_item.metadata["ai_classification_pending"] is True
        mock_flag_modified.assert_called_once_with(mock_evidence_item, "metadata")

    @pytest.mark.asyncio
    async def test_generate_ai_response_success(self, mock_processor):
        """Test successful AI response generation."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "AI response text"
        mock_model.generate_content.return_value = mock_response
        result = await mock_processor._generate_ai_response(mock_model, "test prompt")
        assert result == "AI response text"
        mock_model.generate_content.assert_called_once_with("test prompt")

    @pytest.mark.asyncio
    async def test_generate_ai_response_failure(self, mock_processor):
        """Test AI response generation failure."""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("AI service error")
        with pytest.raises(Exception, match="AI service error"):
            await mock_processor._generate_ai_response(mock_model, "test prompt")

    def test_confidence_score_clamping(self, mock_processor, mock_evidence_item):
        """Test that confidence scores are properly clamped to 0-100 range."""
        response_text = "TYPE: policy_document\nCONFIDENCE: 150\nREASONING: Test"
        result = mock_processor._parse_classification_response(response_text, mock_evidence_item)
        assert result["confidence"] == DEFAULT_LIMIT
        response_text = "TYPE: policy_document\nCONFIDENCE: -10\nREASONING: Test"
        result = mock_processor._parse_classification_response(response_text, mock_evidence_item)
        assert result["confidence"] == 0
