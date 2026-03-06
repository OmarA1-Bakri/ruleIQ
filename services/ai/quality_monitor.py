"""
import logging


logger = logging.getLogger(__name__)
# Constants
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_OK = 200

DEFAULT_TIMEOUT = 30

DEFAULT_LIMIT = 100
HALF_RATIO = 0.5


AI Response Quality Monitoring System

Implements AI response quality tracking, feedback loops, and continuous
improvement mechanisms for the intelligent compliance platform.
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from config.logging_config import get_logger

logger = get_logger(__name__)


class QualityDimension(Enum):
    """Quality dimensions for AI response evaluation."""


class FeedbackType(Enum):
    """Types of feedback for AI responses."""


class QualityLevel(Enum):
    """Quality levels for responses."""

    EXCELLENT = "excellent"
    GOOD = "good"
    SATISFACTORY = "satisfactory"
    NEEDS_IMPROVEMENT = "needs_improvement"
    POOR = "poor"


@dataclass
class QualityScore:
    """Individual quality score for a dimension."""

    dimension: QualityDimension
    score: float
    confidence: float
    explanation: str = ""
    automated: bool = True


@dataclass
class ResponseFeedback:
    """User feedback for an AI response."""

    feedback_id: str
    response_id: str
    user_id: str
    feedback_type: FeedbackType
    rating: Optional[float] = None
    text_feedback: Optional[str] = None
    quality_scores: List[QualityScore] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityAssessment:
    """Comprehensive quality assessment for an AI response."""

    assessment_id: str
    response_id: str
    overall_score: float
    quality_level: QualityLevel
    dimension_scores: Dict[QualityDimension, QualityScore]
    feedback_count: int
    improvement_suggestions: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AIQualityMonitor:
    """
    AI Response Quality Monitoring System

    Features:
    - Automated quality assessment
    - User feedback collection and analysis
    - Quality trend tracking
    - Continuous improvement recommendations
    - Performance benchmarking
    - Feedback loop optimization
    """

    def __init__(self) -> None:
        self.quality_assessments: Dict[str, QualityAssessment] = {}
        self.feedback_history: List[ResponseFeedback] = []
        self.quality_trends: Dict[str, List[float]] = {}
        self.quality_thresholds = {
            QualityLevel.EXCELLENT: 8.5,
            QualityLevel.GOOD: 7.0,
            QualityLevel.SATISFACTORY: 5.5,
            QualityLevel.NEEDS_IMPROVEMENT: 3.5,
            QualityLevel.POOR: 0.0,
        }
        self.metrics = {
            "total_assessments": 0,
            "average_quality_score": 0.0,
            "user_satisfaction_rate": 0.0,
            "improvement_rate": 0.0,
        }

    async def assess_response_quality(
        self,
        response_id: str,
        response_text: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        user_feedback: ResponseFeedback = None,
    ) -> QualityAssessment:
        """
        Perform comprehensive quality assessment of an AI response.

        Args:
            response_id: Unique identifier for the response
            response_text: The AI response text
            prompt: Original prompt that generated the response
            context: Additional context information
            user_feedback: Optional user feedback

        Returns:
            Comprehensive quality assessment
        """
        try:
            dimension_scores = await self._perform_automated_scoring(response_text, prompt, context)
            if user_feedback:
                dimension_scores = self._incorporate_user_feedback(dimension_scores, user_feedback)
            overall_score = self._calculate_overall_score(dimension_scores)
            quality_level = self._determine_quality_level(overall_score)
            improvement_suggestions = self._generate_improvement_suggestions(
                dimension_scores, response_text, context
            )
            assessment = QualityAssessment(
                assessment_id=f"qa_{response_id}_{int(datetime.now(timezone.utc).timestamp())}",
                response_id=response_id,
                overall_score=overall_score,
                quality_level=quality_level,
                dimension_scores=dimension_scores,
                feedback_count=1 if user_feedback else 0,
                improvement_suggestions=improvement_suggestions,
                metadata={
                    "prompt_length": len(prompt),
                    "response_length": len(response_text),
                    "content_type": context.get("content_type") if context else "unknown",
                    "framework": context.get("framework") if context else "unknown",
                },
            )
            self.quality_assessments[response_id] = assessment
            self._update_quality_metrics(assessment)
            logger.debug(
                "Quality assessment completed for response %s: %s" % (response_id, overall_score)
            )
            return assessment
        except Exception as e:
            logger.error("Error assessing response quality: %s" % e)
            raise

    async def _perform_automated_scoring(
        self, response_text: str, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[QualityDimension, QualityScore]:
        """Perform automated quality scoring across all dimensions."""
        scores = {}
        accuracy_score = self._score_accuracy(response_text, prompt, context)
        scores[QualityDimension.ACCURACY] = QualityScore(
            dimension=QualityDimension.ACCURACY,
            score=accuracy_score,
            confidence=0.8,
            explanation="Based on content analysis and framework alignment",
        )
        relevance_score = self._score_relevance(response_text, prompt, context)
        scores[QualityDimension.RELEVANCE] = QualityScore(
            dimension=QualityDimension.RELEVANCE,
            score=relevance_score,
            confidence=0.85,
            explanation="Based on prompt-response alignment analysis",
        )
        completeness_score = self._score_completeness(response_text, prompt, context)
        scores[QualityDimension.COMPLETENESS] = QualityScore(
            dimension=QualityDimension.COMPLETENESS,
            score=completeness_score,
            confidence=0.75,
            explanation="Based on content coverage and detail analysis",
        )
        clarity_score = self._score_clarity(response_text)
        scores[QualityDimension.CLARITY] = QualityScore(
            dimension=QualityDimension.CLARITY,
            score=clarity_score,
            confidence=0.9,
            explanation="Based on readability and structure analysis",
        )
        actionability_score = self._score_actionability(response_text, context)
        scores[QualityDimension.ACTIONABILITY] = QualityScore(
            dimension=QualityDimension.ACTIONABILITY,
            score=actionability_score,
            confidence=0.8,
            explanation="Based on practical implementation guidance",
        )
        compliance_score = self._score_compliance_alignment(response_text, context)
        scores[QualityDimension.COMPLIANCE_ALIGNMENT] = QualityScore(
            dimension=QualityDimension.COMPLIANCE_ALIGNMENT,
            score=compliance_score,
            confidence=0.85,
            explanation="Based on framework requirements alignment",
        )
        return scores

    def _score_accuracy(
        self, response_text: str, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Score response accuracy."""
        score = 7.0
        framework = context.get("framework") if context else None
        if framework:
            framework_keywords = {
                "ISO27001": ["information security", "isms", "risk assessment", "controls"],
                "GDPR": ["data protection", "privacy", "consent", "data subject"],
                "SOC2": ["service organization", "trust services", "availability", "security"],
            }
            keywords = framework_keywords.get(framework, [])
            keyword_matches = sum(
                1 for keyword in keywords if keyword.lower() in response_text.lower()
            )
            if keyword_matches >= len(keywords) * 0.7:
                score += 1.5
            elif keyword_matches >= len(keywords) * 0.5:
                score += 1.0
        if "policy" in prompt.lower() and "policy" in response_text.lower():
            score += 0.5
        if "procedure" in prompt.lower() and "procedure" in response_text.lower():
            score += 0.5
        return min(10.0, score)

    def _score_relevance(
        self, response_text: str, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Score response relevance to the prompt."""
        score = 7.0
        prompt_words = set(prompt.lower().split())
        response_words = set(response_text.lower().split())
        overlap = len(prompt_words & response_words)
        overlap_ratio = overlap / len(prompt_words) if prompt_words else 0
        if overlap_ratio >= 0.7:
            score += 2.0
        elif overlap_ratio >= HALF_RATIO:
            score += 1.5
        elif overlap_ratio >= 0.3:
            score += 1.0
        if "?" in prompt and any(
            word in response_text.lower() for word in ["yes", "no", "should", "recommend"]
        ):
            score += 0.5
        return min(10.0, score)

    def _score_completeness(
        self, response_text: str, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Score response completeness."""
        score = 6.0
        response_length = len(response_text)
        if response_length >= HTTP_INTERNAL_SERVER_ERROR:
            score += 2.0
        elif response_length >= HTTP_OK:
            score += 1.5
        elif response_length >= DEFAULT_LIMIT:
            score += 1.0
        if any(indicator in response_text for indicator in ["1.", "2.", "•", "-"]):
            score += 1.0
        coverage_indicators = [
            "steps",
            "requirements",
            "considerations",
            "examples",
            "implementation",
        ]
        coverage_count = sum(
            1 for indicator in coverage_indicators if indicator in response_text.lower()
        )
        score += coverage_count * 0.3
        return min(10.0, score)

    def _score_clarity(self, response_text: str) -> float:
        """Score response clarity and readability."""
        score = 7.0
        sentences = response_text.split(".")
        avg_sentence_length = (
            sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
        )
        if 15 <= avg_sentence_length <= 20:
            score += 1.5
        elif 10 <= avg_sentence_length <= 25:
            score += 1.0
        elif avg_sentence_length > DEFAULT_TIMEOUT:
            score -= 1.0
        if any(indicator in response_text for indicator in ["\n", ":", ";"]):
            score += 0.5
        professional_terms = ["implement", "establish", "ensure", "maintain", "monitor"]
        professional_count = sum(1 for term in professional_terms if term in response_text.lower())
        score += professional_count * 0.2
        return min(10.0, score)

    def _score_actionability(
        self, response_text: str, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Score response actionability."""
        score = 6.0
        action_words = [
            "implement",
            "create",
            "establish",
            "develop",
            "conduct",
            "review",
            "update",
        ]
        action_count = sum(1 for word in action_words if word in response_text.lower())
        score += action_count * 0.5
        if any(
            indicator in response_text.lower() for indicator in ["step", "procedure", "process"]
        ):
            score += 1.5
        if any(
            indicator in response_text.lower()
            for indicator in ["daily", "weekly", "monthly", "annually"]
        ):
            score += 1.0
        if any(
            role in response_text.lower() for role in ["manager", "officer", "team", "responsible"]
        ):
            score += 1.0
        return min(10.0, score)

    def _score_compliance_alignment(
        self, response_text: str, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Score compliance framework alignment."""
        score = 7.0
        framework = context.get("framework") if context else None
        if not framework:
            return score
        compliance_terms = {
            "ISO27001": ["control", "annex", "isms", "risk management", "continual improvement"],
            "GDPR": ["lawful basis", "data subject rights", "privacy by design", "accountability"],
            "SOC2": ["trust services criteria", "control environment", "monitoring"],
        }
        terms = compliance_terms.get(framework, [])
        term_matches = sum(1 for term in terms if term.lower() in response_text.lower())
        if term_matches >= len(terms) * 0.8:
            score += 2.0
        elif term_matches >= len(terms) * 0.6:
            score += 1.5
        elif term_matches >= len(terms) * 0.4:
            score += 1.0
        return min(10.0, score)

    def _incorporate_user_feedback(
        self, dimension_scores: Dict[QualityDimension, QualityScore], feedback: ResponseFeedback
    ) -> Dict[QualityDimension, QualityScore]:
        """Incorporate user feedback into quality scores."""
        if feedback.feedback_type == FeedbackType.DETAILED_RATING and feedback.rating:
            user_score = (feedback.rating - 1) * 2.5
            user_score / 10.0
            for _dimension, score in dimension_scores.items():
                adjusted_score = score.score * 0.7 + user_score * 0.3
                score.score = min(10.0, max(0.0, adjusted_score))
                score.confidence = min(1.0, score.confidence + 0.1)
                score.automated = False
        elif feedback.feedback_type == FeedbackType.THUMBS_UP:
            for score in dimension_scores.values():
                score.score = min(10.0, score.score + 0.5)
        elif feedback.feedback_type == FeedbackType.THUMBS_DOWN:
            for score in dimension_scores.values():
                score.score = max(0.0, score.score - 1.0)
        return dimension_scores

    def _calculate_overall_score(
        self, dimension_scores: Dict[QualityDimension, QualityScore]
    ) -> float:
        """Calculate overall quality score from dimension scores."""
        weights = {
            QualityDimension.ACCURACY: 0.25,
            QualityDimension.RELEVANCE: 0.2,
            QualityDimension.COMPLETENESS: 0.15,
            QualityDimension.CLARITY: 0.15,
            QualityDimension.ACTIONABILITY: 0.15,
            QualityDimension.COMPLIANCE_ALIGNMENT: 0.1,
        }
        weighted_sum = sum(
            score.score * weights.get(dimension, 0.1)
            for dimension, score in dimension_scores.items()
        )
        return round(weighted_sum, 2)

    def _determine_quality_level(self, overall_score: float) -> QualityLevel:
        """Determine quality level based on overall score."""
        for level, threshold in sorted(
            self.quality_thresholds.items(), key=lambda x: x[1], reverse=True
        ):
            if overall_score >= threshold:
                return level
        return QualityLevel.POOR

    def _generate_improvement_suggestions(
        self,
        dimension_scores: Dict[QualityDimension, QualityScore],
        response_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Generate specific improvement suggestions based on quality scores."""
        suggestions = []
        for dimension, score in dimension_scores.items():
            if score.score < 6.0:
                if dimension == QualityDimension.ACCURACY:
                    suggestions.append("Include more framework-specific terminology and concepts")
                elif dimension == QualityDimension.RELEVANCE:
                    suggestions.append(
                        "Better address the specific question or request in the prompt"
                    )
                elif dimension == QualityDimension.COMPLETENESS:
                    suggestions.append(
                        "Provide more comprehensive coverage with additional details and examples"
                    )
                elif dimension == QualityDimension.CLARITY:
                    suggestions.append(
                        "Use clearer language and better structure with bullet points or numbered lists"
                    )
                elif dimension == QualityDimension.ACTIONABILITY:
                    suggestions.append(
                        "Include more specific implementation steps and practical guidance"
                    )
                elif dimension == QualityDimension.COMPLIANCE_ALIGNMENT:
                    suggestions.append(
                        "Better align with specific compliance framework requirements and controls"
                    )
        return suggestions

    def _update_quality_metrics(self, assessment: QualityAssessment) -> None:
        """Update overall quality metrics."""
        self.metrics["total_assessments"] += 1
        total_score = (
            self.metrics["average_quality_score"] * (self.metrics["total_assessments"] - 1)
            + assessment.overall_score
        )
        self.metrics["average_quality_score"] = total_score / self.metrics["total_assessments"]

    async def record_user_feedback(self, feedback: ResponseFeedback) -> None:
        """Record user feedback for quality improvement."""
        self.feedback_history.append(feedback)
        if feedback.response_id in self.quality_assessments:
            assessment = self.quality_assessments[feedback.response_id]
            assessment.feedback_count += 1

    async def get_quality_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get quality trends over time."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        recent_assessments = [
            assessment
            for assessment in self.quality_assessments.values()
            if start_date <= assessment.timestamp <= end_date
        ]
        if not recent_assessments:
            return {"message": "No assessments available for the specified period"}
        daily_scores = {}
        for assessment in recent_assessments:
            day_key = assessment.timestamp.strftime("%Y-%m-%d")
            if day_key not in daily_scores:
                daily_scores[day_key] = []
            daily_scores[day_key].append(assessment.overall_score)
        daily_averages = {day: statistics.mean(scores) for day, scores in daily_scores.items()}
        return {
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_assessments": len(recent_assessments),
            "average_quality_score": statistics.mean([a.overall_score for a in recent_assessments]),
            "quality_distribution": self._calculate_quality_distribution(recent_assessments),
            "daily_trends": daily_averages,
            "improvement_areas": self._identify_improvement_areas(recent_assessments),
        }

    def _calculate_quality_distribution(
        self, assessments: List[QualityAssessment]
    ) -> Dict[str, int]:
        """Calculate distribution of quality levels."""
        distribution = {level.value: (0) for level in QualityLevel}
        for assessment in assessments:
            distribution[assessment.quality_level.value] += 1
        return distribution

    def _identify_improvement_areas(self, assessments: List[QualityAssessment]) -> List[str]:
        """Identify areas needing improvement based on assessment data."""
        dimension_averages = {}
        for dimension in QualityDimension:
            scores = []
            for assessment in assessments:
                if dimension in assessment.dimension_scores:
                    scores.append(assessment.dimension_scores[dimension].score)
            if scores:
                dimension_averages[dimension] = statistics.mean(scores)
        improvement_areas = []
        for dimension, avg_score in dimension_averages.items():
            if avg_score < 7.0:
                improvement_areas.append(
                    f"{dimension.value.replace('_', ' ').title()}: {avg_score:.1f}/10"
                )
        return improvement_areas


quality_monitor = AIQualityMonitor()


async def get_quality_monitor() -> AIQualityMonitor:
    """Get the global quality monitor instance."""
    return quality_monitor
