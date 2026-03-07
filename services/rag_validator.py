"""RAG Self-Critic Validator for AI Response Validation."""

import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
import hashlib

# ChromaDB imports would be here in production
# from chromadb import Client
# from chromadb.config import Settings


class ValidationFailureReason(str, Enum):
    """Reasons for validation failure."""

    NO_MATCHING_REGULATION = "NO_MATCHING_REGULATION"
    CONFLICTING_INFORMATION = "CONFLICTING_INFORMATION"
    OUTDATED_REFERENCE = "OUTDATED_REFERENCE"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INVALID_CITATION = "INVALID_CITATION"


class ValidationResult(BaseModel):
    """Result of AI response validation."""

    response_id: str
    confidence_score: float = Field(ge=0.0, le=100.0)
    is_valid: bool
    requires_human_review: bool
    failure_reasons: List[ValidationFailureReason] = Field(default_factory=list)
    semantic_similarity_score: float = Field(ge=0.0, le=1.0)
    citation_coverage_score: float = Field(ge=0.0, le=1.0)
    fact_consistency_score: float = Field(ge=0.0, le=1.0)
    processing_time_ms: float
    matched_regulations: List[Dict[str, Any]] = Field(default_factory=list)
    validation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationMetrics(BaseModel):
    """Metrics for validation performance tracking."""

    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    human_review_required: int = 0
    average_confidence: float = 0.0
    average_processing_time_ms: float = 0.0
    cache_hit_rate: float = 0.0


class RAGValidator:
    """
    RAG-based validator for AI responses against compliance knowledge base.

    Validates AI responses using semantic similarity, citation coverage,
    and fact consistency checking against a regulatory knowledge base.
    """

    # Confidence thresholds
    HUMAN_REVIEW_THRESHOLD = 80.0  # Below this requires human review
    INVALID_THRESHOLD = 50.0  # Below this is considered invalid

    # Weight distribution for confidence calculation
    WEIGHTS = {"semantic_similarity": 0.40, "citation_coverage": 0.30, "fact_consistency": 0.30}

    def __init__(
        self,
        knowledge_base_path: Optional[str] = None,
        cache_enabled: bool = True,
        max_cache_size: int = 1000,
    ) -> None:
        """Initialize RAG Validator."""
        self.knowledge_base_path = knowledge_base_path
        self.cache_enabled = cache_enabled
        self.max_cache_size = max_cache_size

        # Initialize cache
        self._cache: Dict[str, ValidationResult] = {}

        # Initialize metrics
        self.metrics = ValidationMetrics()

        # In production, initialize ChromaDB client here
        # self.chroma_client = Client(Settings(...))
        # self.collection = self.chroma_client.get_or_create_collection("compliance_kb")

        # Simulated knowledge base for PoC
        self._init_mock_knowledge_base()

    def _init_mock_knowledge_base(self):
        """Initialize mock knowledge base for PoC."""
        self.mock_regulations = [
            {
                "id": "GDPR_Art5",
                "title": "GDPR Article 5 - Principles",
                "content": "Personal data shall be processed lawfully, fairly and transparently",
                "jurisdiction": "EU",
                "date": "2018-05-25",
                "category": "data_protection",
            },
            {
                "id": "ISO27001_A8",
                "title": "ISO 27001 Annex A.8 - Asset Management",
                "content": "Information and associated assets should be identified and protected",
                "jurisdiction": "International",
                "date": "2022-10-25",
                "category": "information_security",
            },
            {
                "id": "PCI_DSS_3.2",
                "title": "PCI DSS Requirement 3.2",
                "content": "Do not store sensitive authentication data after authorization",
                "jurisdiction": "International",
                "date": "2024-03-31",
                "category": "payment_security",
            },
        ]

    async def validate_response(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None,
        response_id: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate an AI response against the knowledge base.

        Args:
            response: The AI response to validate
            context: Additional context for validation
            response_id: Unique identifier for the response

        Returns:
            ValidationResult with confidence scores and validation status
        """
        start_time = time.time()

        # Generate response ID if not provided
        if not response_id:
            response_id = self._generate_response_id(response)

        # Check cache first
        if self.cache_enabled and response_id in self._cache:
            self.metrics.cache_hit_rate = (
                self.metrics.cache_hit_rate * self.metrics.total_validations + 1
            ) / (self.metrics.total_validations + 1)
            cached_result = self._cache[response_id]
            cached_result.metadata["cache_hit"] = True
            return cached_result

        # Perform validation
        try:
            # Calculate individual scores
            semantic_score = await self._calculate_semantic_similarity(response, context)
            citation_score = await self._calculate_citation_coverage(response, context)
            consistency_score = await self._calculate_fact_consistency(response, context)

            # Calculate weighted confidence score
            confidence_score = (
                semantic_score * self.WEIGHTS["semantic_similarity"]
                + citation_score * self.WEIGHTS["citation_coverage"]
                + consistency_score * self.WEIGHTS["fact_consistency"]
            ) * 100

            # Determine validation status
            is_valid = confidence_score >= self.INVALID_THRESHOLD
            requires_human_review = confidence_score < self.HUMAN_REVIEW_THRESHOLD

            # Identify failure reasons
            failure_reasons = self._identify_failure_reasons(
                semantic_score, citation_score, consistency_score, confidence_score
            )

            # Find matched regulations
            matched_regulations = await self._find_matched_regulations(response)

            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000

            # Create validation result
            result = ValidationResult(
                response_id=response_id,
                confidence_score=confidence_score,
                is_valid=is_valid,
                requires_human_review=requires_human_review,
                failure_reasons=failure_reasons,
                semantic_similarity_score=semantic_score,
                citation_coverage_score=citation_score,
                fact_consistency_score=consistency_score,
                processing_time_ms=processing_time_ms,
                matched_regulations=matched_regulations,
                metadata=context or {},
            )

            # Update cache
            if self.cache_enabled:
                self._update_cache(response_id, result)

            # Update metrics
            self._update_metrics(result)

            return result

        except Exception as e:
            # Return low confidence result on error
            return ValidationResult(
                response_id=response_id,
                confidence_score=0.0,
                is_valid=False,
                requires_human_review=True,
                failure_reasons=[ValidationFailureReason.INSUFFICIENT_CONTEXT],
                semantic_similarity_score=0.0,
                citation_coverage_score=0.0,
                fact_consistency_score=0.0,
                processing_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": str(e)},
            )

    async def validate_batch(
        self,
        responses: List[str],
        contexts: Optional[List[Dict[str, Any]]] = None,
        max_parallel: int = 10,
    ) -> List[ValidationResult]:
        """
        Validate multiple responses in batch.

        Args:
            responses: List of AI responses to validate
            contexts: Optional list of contexts for each response
            max_parallel: Maximum number of parallel validations

        Returns:
            List of ValidationResult objects
        """
        if contexts is None:
            contexts = [None] * len(responses)

        # Create validation tasks
        tasks = []
        for i, response in enumerate(responses[:max_parallel]):  # Limit batch size
            context = contexts[i] if i < len(contexts) else None
            tasks.append(self.validate_response(response, context))

        # Execute in parallel
        results = await asyncio.gather(*tasks)

        return results

    async def _calculate_semantic_similarity(
        self, response: str, context: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate semantic similarity between response and knowledge base."""
        # In production, this would:
        # 1. Generate embeddings for response
        # 2. Query ChromaDB for similar documents
        # 3. Calculate cosine similarity

        # Mock implementation for PoC
        if "GDPR" in response or "data protection" in response.lower():
            return 0.85
        elif "ISO" in response or "security" in response.lower():
            return 0.75
        elif "PCI" in response or "payment" in response.lower():
            return 0.70
        else:
            return 0.40

    async def _calculate_citation_coverage(
        self, response: str, context: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate how well citations cover the claims in response."""
        # In production, this would:
        # 1. Extract citations from response
        # 2. Verify citations exist in knowledge base
        # 3. Check if citations support claims

        # Mock implementation
        has_citations = any(
            marker in response for marker in ["Article", "Section", "Requirement", "§"]
        )
        if has_citations:
            # Check if citations are valid
            if any(reg["id"] in response for reg in self.mock_regulations):
                return 0.90
            return 0.60
        return 0.30

    async def _calculate_fact_consistency(
        self, response: str, context: Optional[Dict[str, Any]]
    ) -> float:
        """Check consistency of facts in response against knowledge base."""
        # In production, this would:
        # 1. Extract factual claims from response
        # 2. Verify each claim against knowledge base
        # 3. Check for contradictions

        # Mock implementation
        # Check for known contradictions or issues
        if "store sensitive data" in response.lower() and "after authorization" in response.lower():
            return 0.30  # Contradicts PCI DSS

        if "lawfully" in response.lower() or "transparently" in response.lower():
            return 0.95  # Aligns with GDPR

        return 0.70  # Default moderate consistency

    def _identify_failure_reasons(
        self,
        semantic_score: float,
        citation_score: float,
        consistency_score: float,
        confidence_score: float,
    ) -> List[ValidationFailureReason]:
        """Identify specific reasons for validation failure."""
        reasons = []

        if confidence_score < self.INVALID_THRESHOLD:
            reasons.append(ValidationFailureReason.LOW_CONFIDENCE)

        if semantic_score < 0.5:
            reasons.append(ValidationFailureReason.NO_MATCHING_REGULATION)

        if citation_score < 0.5:
            reasons.append(ValidationFailureReason.INVALID_CITATION)

        if consistency_score < 0.5:
            reasons.append(ValidationFailureReason.CONFLICTING_INFORMATION)

        if not reasons and confidence_score < self.HUMAN_REVIEW_THRESHOLD:
            reasons.append(ValidationFailureReason.INSUFFICIENT_CONTEXT)

        return reasons

    async def _find_matched_regulations(self, response: str) -> List[Dict[str, Any]]:
        """Find regulations that match the response content."""
        matched = []

        for reg in self.mock_regulations:
            # Simple keyword matching for PoC
            if any(
                keyword in response.lower()
                for keyword in [
                    reg["id"].lower(),
                    reg["category"].replace("_", " "),
                    reg["title"].lower().split()[0],
                ]
            ):
                matched.append(
                    {
                        "id": reg["id"],
                        "title": reg["title"],
                        "relevance_score": 0.8,  # Mock relevance
                        "jurisdiction": reg["jurisdiction"],
                    }
                )

        return matched

    def _generate_response_id(self, response: str) -> str:
        """Generate unique ID for response."""
        return hashlib.sha256(response.encode()).hexdigest()[:16]

    def _update_cache(self, response_id: str, result: ValidationResult):
        """Update result cache with LRU eviction."""
        if len(self._cache) >= self.max_cache_size:
            # Remove oldest entry (simple FIFO for PoC)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[response_id] = result

    def _update_metrics(self, result: ValidationResult):
        """Update validation metrics."""
        self.metrics.total_validations += 1

        if result.is_valid:
            self.metrics.successful_validations += 1
        else:
            self.metrics.failed_validations += 1

        if result.requires_human_review:
            self.metrics.human_review_required += 1

        # Update rolling averages
        self.metrics.average_confidence = (
            self.metrics.average_confidence * (self.metrics.total_validations - 1)
            + result.confidence_score
        ) / self.metrics.total_validations

        self.metrics.average_processing_time_ms = (
            self.metrics.average_processing_time_ms * (self.metrics.total_validations - 1)
            + result.processing_time_ms
        ) / self.metrics.total_validations

    def get_metrics(self) -> ValidationMetrics:
        """Get current validation metrics."""
        return self.metrics

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on validation service."""
        try:
            # Test validation with known good response
            test_response = "Personal data must be processed lawfully according to GDPR Article 5"
            result = await self.validate_response(test_response)

            return {
                "status": "healthy" if result.confidence_score > 70 else "degraded",
                "latency_ms": result.processing_time_ms,
                "cache_size": len(self._cache),
                "total_validations": self.metrics.total_validations,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
