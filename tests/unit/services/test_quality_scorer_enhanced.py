"""

# Constants
DEFAULT_TIMEOUT = 30


Unit Tests for Enhanced Quality Scorer

Tests the AI-enhanced quality analysis and semantic duplicate detection functionality.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4
import pytest
from database.evidence_item import EvidenceItem
from services.automation.quality_scorer import QualityScorer

from tests.test_constants import DEFAULT_LIMIT, MAX_RETRIES


@pytest.mark.unit
@pytest.mark.ai
class TestEnhancedQualityScorer:
    """Test AI enhancement features in quality scorer"""

    @pytest.fixture
    def mock_evidence_item(self):
        """Create a mock evidence item for testing."""
        evidence = Mock(spec=EvidenceItem)
        evidence.id = uuid4()
        evidence.evidence_name = "Security Policy Document"
        evidence.description = "Comprehensive information security policy covering access controls and data protection procedures"
        evidence.evidence_type = "policy_document"
        evidence.collected_at = datetime.now(timezone.utc) - timedelta(days=10)
        evidence.raw_data = json.dumps(
            {"file_type": "pdf", "content": "This policy establishes security controls..."}
        )
        evidence.control_reference = "ISO27001-A.5.1.1"
        evidence.file_path = "/path/to/policy.pdf"
        return evidence

    @pytest.fixture
    def mock_scorer(self):
        """Create quality scorer with mocked AI model."""
        scorer = QualityScorer()
        scorer.ai_model = Mock()
        return scorer

    @pytest.mark.asyncio
    async def test_calculate_enhanced_score_success(self, mock_scorer, mock_evidence_item):
        """Test successful enhanced quality scoring with AI."""
        mock_response = Mock()
        mock_response.text = """COMPLETENESS: 85
CLARITY: 90
CURRENCY: 80
VERIFIABILITY: 75
RELEVANCE: 95
SUFFICIENCY: 80
OVERALL: 84
STRENGTHS: Clear documentation, comprehensive coverage
WEAKNESSES: Could include more examples
RECOMMENDATIONS: Add implementation examples"""
        mock_scorer.ai_model.generate_content.return_value = mock_response
        result = await mock_scorer.calculate_enhanced_score(mock_evidence_item)
        assert result["overall_score"] > 0
        assert result["scoring_method"] == "enhanced_ai"
        assert "traditional_scores" in result
        assert "ai_analysis" in result
        assert result["ai_analysis"]["overall_score"] == 84
        assert len(result["ai_analysis"]["strengths"]) > 0
        assert len(result["ai_analysis"]["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_calculate_enhanced_score_fallback(self, mock_scorer, mock_evidence_item):
        """Test enhanced scoring with AI failure fallback."""
        mock_scorer.ai_model.generate_content.side_effect = Exception("AI service unavailable")
        result = await mock_scorer.calculate_enhanced_score(mock_evidence_item)
        assert result["scoring_method"] == "traditional_fallback"
        assert result["confidence"] == DEFAULT_TIMEOUT
        assert "error" in result["ai_analysis"]

    def test_prepare_content_for_analysis(self, mock_scorer, mock_evidence_item):
        """Test content preparation for AI analysis."""
        content = mock_scorer._prepare_content_for_analysis(mock_evidence_item)
        assert mock_evidence_item.evidence_name in content
        assert mock_evidence_item.description in content
        assert mock_evidence_item.evidence_type in content
        assert "file_type" in content

    def test_parse_quality_response_valid(self, mock_scorer):
        """Test parsing valid AI quality response."""
        response_text = """COMPLETENESS: 85
CLARITY: 90
CURRENCY: 80
VERIFIABILITY: 75
RELEVANCE: 95
SUFFICIENCY: 80
OVERALL: 84
STRENGTHS: Clear documentation
WEAKNESSES: Missing examples
RECOMMENDATIONS: Add more details"""
        result = mock_scorer._parse_quality_response(response_text)
        assert result["overall_score"] == 84
        assert result["scores"]["completeness"] == 85
        assert result["scores"]["clarity"] == 90
        assert "Clear documentation" in result["strengths"]
        assert "Missing examples" in result["weaknesses"]
        assert result["ai_confidence"] == 85

    def test_parse_quality_response_invalid(self, mock_scorer):
        """Test parsing invalid AI response falls back gracefully."""
        response_text = "Invalid response format"
        result = mock_scorer._parse_quality_response(response_text)
        assert result["overall_score"] == DEFAULT_TIMEOUT
        assert result["ai_confidence"] == 0

    def test_fallback_quality_analysis(self, mock_scorer, mock_evidence_item):
        """Test rule-based fallback quality analysis."""
        result = mock_scorer._fallback_quality_analysis(mock_evidence_item)
        assert "scores" in result
        assert "overall_score" in result
        assert "strengths" in result
        assert "weaknesses" in result
        assert "recommendations" in result
        assert result["ai_confidence"] == 20

    def test_calculate_traditional_scores(self, mock_scorer, mock_evidence_item):
        """Test traditional algorithmic scoring."""
        scores = mock_scorer._calculate_traditional_scores(mock_evidence_item)
        assert "completeness" in scores
        assert "freshness" in scores
        assert "content_quality" in scores
        assert "relevance" in scores
        assert all(0 <= score <= DEFAULT_LIMIT for score in scores.values())

    def test_combine_traditional_and_ai_scores(self, mock_scorer):
        """Test score combination logic."""
        traditional_scores = {
            "completeness": 80,
            "freshness": 90,
            "content_quality": 70,
            "relevance": 85,
        }
        ai_analysis = {
            "overall_score": 85,
            "ai_confidence": 80,
            "scores": {"completeness": 85, "clarity": 90},
        }
        combined_score = mock_scorer._combine_traditional_and_ai_scores(
            traditional_scores, ai_analysis
        )
        assert 0 <= combined_score <= DEFAULT_LIMIT
        assert abs(combined_score - 85) < abs(combined_score - 81.25)

    @pytest.mark.asyncio
    async def test_detect_semantic_duplicates_success(self, mock_scorer, mock_evidence_item):
        """Test successful semantic duplicate detection."""
        candidate = Mock(spec=EvidenceItem)
        candidate.id = uuid4()
        candidate.evidence_name = "Similar Security Policy"
        candidate.description = "Information security policy with access controls"
        candidate.evidence_type = "policy_document"
        candidate.collected_at = datetime.now(timezone.utc)
        candidate.raw_data = "{}"
        mock_response = Mock()
        mock_response.text = """CONTENT_SIMILARITY: 85
PURPOSE_SIMILARITY: 90
SCOPE_OVERLAP: 80
OVERALL_SIMILARITY: 85
SIMILARITY_TYPE: substantial_overlap
REASONING: Both are security policies with similar content
RECOMMENDATION: review_manually"""
        mock_scorer.ai_model.generate_content.return_value = mock_response
        duplicates = await mock_scorer.detect_semantic_duplicates(
            mock_evidence_item, [candidate], 0.8
        )
        assert len(duplicates) == 1
        assert duplicates[0]["candidate_id"] == candidate.id
        assert duplicates[0]["similarity_score"] == 85
        assert duplicates[0]["similarity_type"] == "substantial_overlap"

    @pytest.mark.asyncio
    async def test_detect_semantic_duplicates_no_matches(self, mock_scorer, mock_evidence_item):
        """Test duplicate detection with no matches."""
        candidate = Mock(spec=EvidenceItem)
        candidate.id = uuid4()
        candidate.evidence_name = "Training Certificate"
        candidate.description = "Security awareness training completion certificate"
        candidate.evidence_type = "training_record"
        candidate.collected_at = datetime.now(timezone.utc)
        candidate.raw_data = "{}"
        mock_response = Mock()
        mock_response.text = """CONTENT_SIMILARITY: 20
PURPOSE_SIMILARITY: 30
SCOPE_OVERLAP: 15
OVERALL_SIMILARITY: 22
SIMILARITY_TYPE: different
REASONING: Different types of evidence with different purposes
RECOMMENDATION: keep_both"""
        mock_scorer.ai_model.generate_content.return_value = mock_response
        duplicates = await mock_scorer.detect_semantic_duplicates(
            mock_evidence_item, [candidate], 0.8
        )
        assert len(duplicates) == 0

    def test_parse_similarity_response_valid(self, mock_scorer):
        """Test parsing valid similarity analysis response."""
        response_text = """CONTENT_SIMILARITY: 85
PURPOSE_SIMILARITY: 90
SCOPE_OVERLAP: 80
OVERALL_SIMILARITY: 85
SIMILARITY_TYPE: substantial_overlap
REASONING: Similar content and purpose
RECOMMENDATION: review_manually"""
        result = mock_scorer._parse_similarity_response(response_text)
        assert result["similarity_score"] == 85
        assert result["similarity_type"] == "substantial_overlap"
        assert result["reasoning"] == "Similar content and purpose"
        assert result["recommendation"] == "review_manually"

    def test_parse_similarity_response_invalid(self, mock_scorer):
        """Test parsing invalid similarity response."""
        response_text = "Invalid format"
        result = mock_scorer._parse_similarity_response(response_text)
        assert result["similarity_score"] == 0
        assert result["similarity_type"] == "different"
        assert result["recommendation"] == "review_manually"

    @pytest.mark.asyncio
    async def test_batch_duplicate_detection(self, mock_scorer):
        """Test batch duplicate detection across multiple evidence items."""
        evidence1 = Mock(spec=EvidenceItem)
        evidence1.id = uuid4()
        evidence1.evidence_name = "Policy A"
        evidence1.evidence_type = "policy_document"
        evidence1.description = "Security policy document"
        evidence1.collected_at = datetime.now(timezone.utc)
        evidence1.raw_data = "{}"
        evidence2 = Mock(spec=EvidenceItem)
        evidence2.id = uuid4()
        evidence2.evidence_name = "Policy B"
        evidence2.evidence_type = "policy_document"
        evidence2.description = "Similar security policy"
        evidence2.collected_at = datetime.now(timezone.utc)
        evidence2.raw_data = "{}"
        evidence3 = Mock(spec=EvidenceItem)
        evidence3.id = uuid4()
        evidence3.evidence_name = "Training Record"
        evidence3.evidence_type = "training_record"
        evidence3.description = "Training completion record"
        evidence3.collected_at = datetime.now(timezone.utc)
        evidence3.raw_data = "{}"

        def mock_generate_content(prompt):
            if "Policy A" in prompt and "Policy B" in prompt:
                response = Mock()
                response.text = """OVERALL_SIMILARITY: 85
SIMILARITY_TYPE: substantial_overlap
REASONING: Similar policies
RECOMMENDATION: review_manually"""
                return response
            else:
                response = Mock()
                response.text = """OVERALL_SIMILARITY: 20
SIMILARITY_TYPE: different
REASONING: Different types
RECOMMENDATION: keep_both"""
                return response

        mock_scorer.ai_model.generate_content.side_effect = mock_generate_content
        result = await mock_scorer.batch_duplicate_detection([evidence1, evidence2, evidence3], 0.8)
        assert result["total_items"] == MAX_RETRIES
        assert result["potential_duplicates"] == 1
        assert result["unique_items"] == 2
        assert len(result["duplicate_groups"]) == 1
