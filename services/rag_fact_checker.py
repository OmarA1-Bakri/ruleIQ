"""

# Constants
HTTP_INTERNAL_SERVER_ERROR = 500

HALF_RATIO = 0.5
MAX_ITEMS = 1000


Fact Checking and Self-Critic Module for Agentic RAG System
Provides advanced fact-checking, source verification, and response quality assessment
"""

import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import openai
from mistralai import Mistral

logger = logging.getLogger(__name__)


class FactCheckConfidence(Enum):
    """Confidence levels for fact checking"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CriticSeverity(Enum):
    """Severity levels for self-criticism"""


class FactCheckResult(BaseModel):
    """Result of fact checking analysis"""

    claim: str
    is_factual: bool
    confidence: FactCheckConfidence
    evidence: List[str]
    contradictions: List[str]
    source_reliability: float = Field(ge=0.0, le=1.0)
    reasoning: str
    timestamp: datetime = Field(default_factory=datetime.now)


class SelfCritique(BaseModel):
    """Self-critique analysis result"""

    aspect: str
    score: float = Field(ge=0.0, le=1.0)
    severity: CriticSeverity
    issues: List[str]
    suggestions: List[str]
    reasoning: str


class QualityAssessment(BaseModel):
    """Overall quality assessment of RAG response"""

    overall_score: float = Field(ge=0.0, le=1.0)
    fact_check_results: List[FactCheckResult]
    self_critiques: List[SelfCritique]
    source_quality_score: float = Field(ge=0.0, le=1.0)
    response_reliability: float = Field(ge=0.0, le=1.0)
    recommendations: List[str]
    flagged_issues: List[str]
    approved_for_use: bool
    assessment_timestamp: datetime = Field(default_factory=datetime.now)


class RAGFactChecker:
    """
    Advanced fact-checking and self-critique system for RAG responses

    Features:
    - Multi-source fact verification
    - Cross-reference validation
    - Source reliability assessment
    - Response quality scoring
    - Automated self-criticism
    - Bias detection
    """

    def __init__(self) -> None:
        self.openai_client = None
        self.mistral_client = None
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key and openai_api_key != "your-openai-api-key":
            self.openai_client = openai.OpenAI(api_key=openai_api_key)
        mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if mistral_api_key:
            self.mistral_client = Mistral(api_key=mistral_api_key)
        self.fact_check_model = "gpt-4o-mini"
        self.critic_model = "gpt-4o-mini"
        self.high_confidence_threshold = 0.85
        self.medium_confidence_threshold = 0.65
        self.approval_threshold = 0.75

    async def comprehensive_fact_check(
        self, response_text: str, sources: List[Dict[str, Any]], original_query: str
    ) -> QualityAssessment:
        """
        Perform comprehensive fact-checking and quality assessment

        Args:
            response_text: The RAG system's response
            sources: List of source documents used
            original_query: The original user query
        """
        try:
            logger.info("Starting comprehensive fact-check analysis")
            claims = await self._extract_factual_claims(response_text)
            fact_check_results = []
            for claim in claims:
                result = await self._fact_check_claim(claim, sources, response_text)
                fact_check_results.append(result)
            self_critiques = await self._perform_self_criticism(
                response_text, sources, original_query
            )
            source_quality_score = await self._assess_source_quality(sources)
            overall_score = self._calculate_overall_score(
                fact_check_results, self_critiques, source_quality_score
            )
            response_reliability = self._calculate_reliability(fact_check_results)
            recommendations = await self._generate_recommendations(
                fact_check_results, self_critiques, source_quality_score
            )
            flagged_issues = self._identify_flagged_issues(fact_check_results, self_critiques)
            approved_for_use = overall_score >= self.approval_threshold and not any(
                issue.startswith("CRITICAL") for issue in flagged_issues
            )
            return QualityAssessment(
                overall_score=overall_score,
                fact_check_results=fact_check_results,
                self_critiques=self_critiques,
                source_quality_score=source_quality_score,
                response_reliability=response_reliability,
                recommendations=recommendations,
                flagged_issues=flagged_issues,
                approved_for_use=approved_for_use,
            )
        except Exception as e:
            logger.error("Comprehensive fact-check failed: %s" % e)
            return QualityAssessment(
                overall_score=0.0,
                fact_check_results=[],
                self_critiques=[],
                source_quality_score=0.0,
                response_reliability=0.0,
                recommendations=["Fact-checking system encountered an error"],
                flagged_issues=["CRITICAL: Fact-checking system failure"],
                approved_for_use=False,
            )

    async def _extract_factual_claims(self, response_text: str) -> List[str]:
        """Extract factual claims from response text"""
        try:
            prompt = f"""
            Analyze the following text and extract specific factual claims that can be verified.
            Focus on concrete statements about how things work, specific features, capabilities, or limitations.
            Exclude opinions, general guidance, or subjective statements.

            Text to analyze:
            {response_text}

            Return a JSON list of factual claims. Each claim should be a specific, verifiable statement.
            Example: ["LangGraph supports PostgreSQL checkpointers", "State management requires TypedDict classes"]
            """
            if self.openai_client:
                response = await self.openai_client.chat.completions.create(
                    model=self.fact_check_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                    temperature=0.1,
                )
                claims_text = response.choices[0].message.content.strip()
                try:
                    claims = json.loads(claims_text)
                    return claims if isinstance(claims, list) else []
                except json.JSONDecodeError:
                    return self._manual_claim_extraction(claims_text)
            else:
                return self._manual_claim_extraction(response_text)
        except Exception as e:
            logger.warning("Failed to extract factual claims: %s" % e)
            return []

    def _manual_claim_extraction(self, text: str) -> List[str]:
        """Manual fallback for claim extraction"""
        claims = []
        sentences = text.split(".")
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and any(
                keyword in sentence.lower()
                for keyword in [
                    "supports",
                    "requires",
                    "provides",
                    "enables",
                    "uses",
                    "implements",
                    "includes",
                    "allows",
                    "prevents",
                ]
            ):
                claims.append(sentence)
        return claims[:10]

    async def _fact_check_claim(
        self, claim: str, sources: List[Dict[str, Any]], full_response: str
    ) -> FactCheckResult:
        """Fact-check a specific claim against sources"""
        try:
            source_context = "\n\n".join(
                [
                    f"""Source {i + 1} ({source.get("source", "unknown")}):
{source.get("content", "")[:1000]}"""
                    for i, source in enumerate(sources[:3])
                ]
            )
            prompt = f"""
            You are a fact-checking expert. Verify the following claim against the provided sources.

            Claim to verify: {claim}

            Available sources:
            {source_context}

            Full response context:
            {full_response[:500]}...

            Analyze and respond with a JSON object containing:
            {{
                "is_factual": boolean,
                "confidence": "high|medium|low|uncertain",
                "evidence": ["list of supporting evidence from sources"],
                "contradictions": ["list of contradictory information"],
                "source_reliability": float between 0 and 1,
                "reasoning": "detailed explanation of your analysis"
            }}

            Be thorough and conservative in your assessment.
            """
            if self.openai_client:
                response = await self.openai_client.chat.completions.create(
                    model=self.fact_check_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=600,
                    temperature=0.1,
                )
                result_text = response.choices[0].message.content.strip()
                try:
                    result_data = json.loads(result_text)
                    return FactCheckResult(
                        claim=claim,
                        is_factual=result_data.get("is_factual", False),
                        confidence=FactCheckConfidence(result_data.get("confidence", "uncertain")),
                        evidence=result_data.get("evidence", []),
                        contradictions=result_data.get("contradictions", []),
                        source_reliability=float(result_data.get("source_reliability", 0.5)),
                        reasoning=result_data.get("reasoning", "Analysis completed"),
                    )
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Failed to parse fact-check result: %s" % e)
                    return self._create_fallback_fact_check(claim)
            else:
                return self._create_fallback_fact_check(claim)
        except Exception as e:
            logger.error("Fact-checking failed for claim '%s': %s" % (claim, e))
            return self._create_fallback_fact_check(claim)

    def _create_fallback_fact_check(self, claim: str) -> FactCheckResult:
        """Create a fallback fact-check result when AI analysis fails"""
        return FactCheckResult(
            claim=claim,
            is_factual=True,
            confidence=FactCheckConfidence.UNCERTAIN,
            evidence=["Unable to verify - AI analysis unavailable"],
            contradictions=[],
            source_reliability=0.5,
            reasoning="Fact-checking service unavailable, claim not verified",
        )

    async def _perform_self_criticism(
        self, response_text: str, sources: List[Dict[str, Any]], original_query: str
    ) -> List[SelfCritique]:
        """Perform comprehensive self-criticism analysis"""
        critique_aspects = ["accuracy", "completeness", "relevance", "clarity"]
        critiques = []
        for aspect in critique_aspects:
            critique = await self._analyze_aspect(aspect, response_text, sources, original_query)
            critiques.append(critique)
        return critiques

    async def _analyze_aspect(
        self, aspect: str, response_text: str, sources: List[Dict[str, Any]], original_query: str
    ) -> SelfCritique:
        """Analyze a specific aspect of the response"""
        try:
            aspect_prompts = {
                "accuracy": "How accurate is this response? Are there any technical inaccuracies or misleading statements?",
                "completeness": "How complete is this response? What important information might be missing?",
                "relevance": "How relevant is this response to the original query? Does it address all parts of the question?",
                "clarity": "How clear and understandable is this response? Are there confusing or ambiguous parts?",
            }
            prompt = f"""
            You are a critical reviewer analyzing a RAG system response.

            Original Query: {original_query}

            Response to analyze:
            {response_text}

            Available sources count: {len(sources)}

            Focus on: {aspect_prompts.get(aspect, aspect)}

            Provide a critical analysis in JSON format:
            {{
                "score": float between 0 and 1 (1 = excellent, 0 = poor),
                "severity": "critical|high|medium|low|info",
                "issues": ["list of specific issues identified"],
                "suggestions": ["list of specific improvement suggestions"],
                "reasoning": "detailed explanation of your assessment"
            }}

            Be constructively critical and identify both strengths and weaknesses.
            """
            if self.openai_client:
                response = await self.openai_client.chat.completions.create(
                    model=self.critic_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                    temperature=0.2,
                )
                result_text = response.choices[0].message.content.strip()
                try:
                    result_data = json.loads(result_text)
                    return SelfCritique(
                        aspect=aspect,
                        score=float(result_data.get("score", 0.5)),
                        severity=CriticSeverity(result_data.get("severity", "medium")),
                        issues=result_data.get("issues", []),
                        suggestions=result_data.get("suggestions", []),
                        reasoning=result_data.get("reasoning", "Analysis completed"),
                    )
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Failed to parse criticism result for %s: %s" % (aspect, e))
                    return self._create_fallback_critique(aspect)
            else:
                return self._create_fallback_critique(aspect)
        except Exception as e:
            logger.error("Self-criticism failed for aspect '%s': %s" % (aspect, e))
            return self._create_fallback_critique(aspect)

    def _create_fallback_critique(self, aspect: str) -> SelfCritique:
        """Create a fallback critique when AI analysis fails"""
        return SelfCritique(
            aspect=aspect,
            score=0.5,
            severity=CriticSeverity.INFO,
            issues=["Unable to analyze - AI criticism unavailable"],
            suggestions=["Manual review recommended"],
            reasoning="Self-criticism service unavailable",
        )

    async def _assess_source_quality(self, sources: List[Dict[str, Any]]) -> float:
        """Assess the quality and reliability of sources used"""
        if not sources:
            return 0.0
        total_score = 0.0
        for source in sources:
            score = 0.0
            source_type = source.get("chunk_type", "unknown")
            if source_type == "documentation":
                score += 0.3
            elif source_type == "code_example":
                score += 0.4
            elif source_type == "api_reference":
                score += 0.3
            similarity = source.get("similarity", 0.0)
            score += similarity * 0.4
            content_length = len(source.get("content", ""))
            if content_length > MAX_ITEMS:
                score += 0.2
            elif content_length > HTTP_INTERNAL_SERVER_ERROR:
                score += 0.1
            framework = source.get("source", "").lower()
            if framework in ["langgraph", "pydantic_ai"]:
                score += 0.1
            total_score += min(1.0, score)
        return total_score / len(sources)

    def _calculate_overall_score(
        self,
        fact_check_results: List[FactCheckResult],
        self_critiques: List[SelfCritique],
        source_quality_score: float,
    ) -> float:
        """Calculate overall quality score"""
        weights = {"fact_accuracy": 0.4, "self_critique": 0.4, "source_quality": 0.2}
        if fact_check_results:
            fact_score = sum(
                1.0 if result.is_factual else 0.3 for result in fact_check_results
            ) / len(fact_check_results)
        else:
            fact_score = 0.8
        if self_critiques:
            critique_score = sum(critique.score for critique in self_critiques) / len(
                self_critiques
            )
        else:
            critique_score = 0.5
        overall_score = (
            weights["fact_accuracy"] * fact_score
            + weights["self_critique"] * critique_score
            + weights["source_quality"] * source_quality_score
        )
        return round(overall_score, 3)

    def _calculate_reliability(self, fact_check_results: List[FactCheckResult]) -> float:
        """Calculate response reliability based on fact-checking"""
        if not fact_check_results:
            return 0.7
        reliability_scores = []
        for result in fact_check_results:
            if result.is_factual:
                if result.confidence == FactCheckConfidence.HIGH:
                    reliability_scores.append(0.95)
                elif result.confidence == FactCheckConfidence.MEDIUM:
                    reliability_scores.append(0.8)
                elif result.confidence == FactCheckConfidence.LOW:
                    reliability_scores.append(0.6)
                else:
                    reliability_scores.append(0.4)
            else:
                reliability_scores.append(0.1)
        return round(sum(reliability_scores) / len(reliability_scores), 3)

    async def _generate_recommendations(
        self,
        fact_check_results: List[FactCheckResult],
        self_critiques: List[SelfCritique],
        source_quality_score: float,
    ) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        false_claims = [r for r in fact_check_results if not r.is_factual]
        if false_claims:
            recommendations.append(f"Review {len(false_claims)} potentially inaccurate claims")
        uncertain_claims = [
            r for r in fact_check_results if r.confidence == FactCheckConfidence.UNCERTAIN
        ]
        if uncertain_claims:
            recommendations.append(
                f"Verify {len(uncertain_claims)} uncertain claims with additional sources"
            )
        for critique in self_critiques:
            if critique.score < 0.6:
                recommendations.append(
                    f"Improve {critique.aspect}: {critique.suggestions[0] if critique.suggestions else 'needs attention'}"
                )
        if source_quality_score < HALF_RATIO:
            recommendations.append("Consider using higher-quality or more relevant sources")
        return recommendations[:5]

    def _identify_flagged_issues(
        self, fact_check_results: List[FactCheckResult], self_critiques: List[SelfCritique]
    ) -> List[str]:
        """Identify critical issues that should flag the response"""
        flagged_issues = []
        false_claims = [r for r in fact_check_results if not r.is_factual]
        if false_claims:
            flagged_issues.append(
                f"CRITICAL: {len(false_claims)} factually incorrect claims detected"
            )
        critical_critiques = [c for c in self_critiques if c.severity == CriticSeverity.CRITICAL]
        if critical_critiques:
            flagged_issues.append(f"CRITICAL: {len(critical_critiques)} critical quality issues")
        high_severity = [
            c for c in self_critiques if c.severity == CriticSeverity.HIGH and c.score < 0.3
        ]
        if high_severity:
            flagged_issues.append(f"HIGH: {len(high_severity)} high-severity quality issues")
        return flagged_issues

    async def quick_fact_check(self, response_text: str, sources: List[Dict[str, Any]]) -> bool:
        """
        Quick fact-check for real-time usage
        Returns True if response appears reliable, False if suspicious
        """
        try:
            claims = await self._extract_factual_claims(response_text)
            if not claims:
                return True
            suspicious_count = 0
            for claim in claims[:3]:
                result = await self._fact_check_claim(claim, sources, response_text)
                if not result.is_factual or result.confidence == FactCheckConfidence.UNCERTAIN:
                    suspicious_count += 1
            return suspicious_count <= len(claims[:3]) * 0.5
        except Exception as e:
            logger.error("Quick fact-check failed: %s" % e)
            return True
