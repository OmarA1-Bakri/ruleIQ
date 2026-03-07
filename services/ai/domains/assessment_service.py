"""
Assessment Service

Handles all assessment-related AI operations including help, analysis, and recommendations.
Ported from legacy ComplianceAssistant implementation.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional
from uuid import UUID, uuid4

from services.ai.response.generator import ResponseGenerator
from services.ai.context_manager import ContextManager

logger = logging.getLogger(__name__)


class AssessmentService:
    """Handles assessment-related AI operations."""

    def __init__(
        self, response_generator: ResponseGenerator, context_manager: ContextManager
    ) -> None:
        """Initialize the assessment service."""
        self.response_generator = response_generator
        self.context_manager = context_manager

    async def get_assessment_help(
        self,
        question_id: str,
        question_text: str,
        framework_id: str,
        business_profile_id: UUID,
        section_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Provide AI-powered contextual guidance for specific assessment questions.

        Args:
            question_id: Unique identifier for the question
            question_text: The actual question text
            framework_id: The compliance framework (e.g., 'gdpr', 'iso27001')
            business_profile_id: User's business profile for context
            section_id: Optional section identifier within the framework
            user_context: Additional context from the user

        Returns:
            Dict containing guidance, confidence score, related topics, etc.
        """
        try:
            system_prompt = (
                f"You are a {framework_id} compliance expert. Provide concise, actionable guidance."
            )
            user_prompt = f"""Question: {question_text}

Provide brief, practical guidance in JSON format with 'guidance' and 'confidence_score' fields."""

            start_time = datetime.now(timezone.utc)

            response = await asyncio.wait_for(
                self.response_generator.generate_simple(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    task_type="help",
                    context={"framework": framework_id},
                ),
                timeout=2.5,
            )

            response_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            structured_response = self._parse_assessment_help_response(response)
            structured_response.update(
                {
                    "request_id": f"help_{framework_id}_{question_id}_{uuid4().hex[:8]}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "framework_id": framework_id,
                    "question_id": question_id,
                    "response_time": response_time,
                }
            )

            return structured_response

        except asyncio.TimeoutError:
            logger.warning(f"AI help request timed out for {question_id}, using fast fallback")
            return self._get_fast_fallback_help(question_text, framework_id, question_id)

        except Exception as e:
            logger.error(f"Error generating assessment help: {e}")
            return self._get_fallback_assessment_help(question_text, framework_id)

    async def generate_assessment_followup(
        self,
        current_answers: Dict[str, Any],
        framework_id: str,
        business_profile_id: UUID,
        assessment_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate intelligent follow-up questions based on current assessment progress.

        Args:
            current_answers: User's current assessment responses
            framework_id: The compliance framework being assessed
            business_profile_id: User's business profile for context
            assessment_context: Additional assessment context

        Returns:
            Dict containing follow-up questions and recommendations
        """
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )

            business_profile = context.get("business_profile", {})

            # Build prompt for followup generation
            system_prompt = (
                f"You are a {framework_id} compliance expert generating follow-up questions."
            )
            company = business_profile.get("company_name", "Unknown")
            industry = business_profile.get("industry", "Unknown")

            user_prompt = f"""Based on current answers: {json.dumps(current_answers, indent=2)}

Business Context:
- Company: {company}
- Industry: {industry}

Generate 2-3 relevant follow-up questions in JSON format with
'follow_up_questions' and 'recommendations' fields."""

            response = await self.response_generator.generate_simple(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                task_type="followup",
                context={"framework": framework_id},
            )

            structured_response = self._parse_assessment_followup_response(response)
            structured_response.update(
                {
                    "request_id": f"followup_{framework_id}_{uuid4().hex[:8]}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "framework_id": framework_id,
                }
            )

            return structured_response

        except Exception as e:
            logger.error(f"Error generating assessment followup: {e}")
            return self._get_fallback_assessment_followup(framework_id)

    async def analyze_assessment_results(
        self, assessment_results: Dict[str, Any], framework_id: str, business_profile_id: UUID
    ) -> Dict[str, Any]:
        """
        Perform comprehensive AI analysis of assessment results.

        Args:
            assessment_results: The completed assessment responses
            framework_id: The compliance framework being assessed
            business_profile_id: User's business profile for context

        Returns:
            Dict containing gaps, recommendations, risk assessment, etc.
        """
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )

            business_profile = context.get("business_profile", {})

            # Build comprehensive analysis prompt
            system_prompt = (
                f"You are a {framework_id} compliance expert analyzing assessment results."
            )
            user_prompt = f"""Assessment Results:
{json.dumps(assessment_results, indent=2)}

Business Context:
- Company: {business_profile.get("company_name", "Unknown")}
- Industry: {business_profile.get("industry", "Unknown")}
- Size: {business_profile.get("employee_count", 0)} employees

Provide comprehensive analysis in JSON format with:
- gaps: List of compliance gaps identified
- recommendations: Prioritized recommendations
- risk_assessment: Risk level and description
- compliance_insights: Summary of findings
- evidence_requirements: Required evidence items"""

            response = await self.response_generator.generate_simple(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                task_type="analysis",
                context={"framework": framework_id},
            )

            structured_response = self._parse_assessment_analysis_response(response)
            structured_response.update(
                {
                    "request_id": f"analysis_{framework_id}_{uuid4().hex[:8]}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "framework_id": framework_id,
                }
            )

            return structured_response

        except Exception as e:
            logger.error(f"Error analyzing assessment results: {e}")
            return self._get_fallback_assessment_analysis(framework_id)

    async def analyze_assessment_results_stream(
        self,
        assessment_responses: Dict[str, Any],
        framework_id: str,
        business_profile_id: UUID,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream comprehensive analysis of assessment results.

        Args:
            assessment_responses: Assessment response data
            framework_id: The compliance framework
            business_profile_id: User's business profile for context
            user_context: Additional context from the user

        Yields:
            String chunks of the analysis as they're generated
        """
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )

            business_profile = context.get("business_profile", {})

            prompt = f"""Analyze assessment results for {framework_id}:

Assessment Data: {json.dumps(assessment_responses, indent=2)}

Business Context:
- Company: {business_profile.get("company_name", "Unknown")}
- Industry: {business_profile.get("industry", "Unknown")}

Provide detailed analysis of compliance gaps, strengths, and recommendations."""

            # Note: Streaming would use response_generator's streaming capability
            # For now, yield complete response
            response = await self.response_generator.generate_simple(
                system_prompt="You are ComplianceGPT, providing comprehensive assessment analysis.",
                user_prompt=prompt,
                task_type="analysis",
                context={"framework": framework_id},
            )

            yield response

        except Exception as e:
            logger.error(f"Error streaming assessment analysis: {e}")
            yield f"Unable to analyze assessment results for {framework_id} at this time."

    async def get_assessment_help_stream(
        self,
        question_id: str,
        question_text: str,
        framework_id: str,
        business_profile_id: UUID,
        section_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream contextual guidance for specific assessment questions.

        Args:
            question_id: Unique identifier for the question
            question_text: The actual question text
            framework_id: The compliance framework
            business_profile_id: User's business profile for context
            section_id: Optional section identifier
            user_context: Additional context from the user

        Yields:
            String chunks of guidance as they're generated
        """
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )

            business_profile = context.get("business_profile", {})

            company = business_profile.get("company_name", "Unknown")
            industry = business_profile.get("industry", "Unknown")

            prompt = f"""Question: {question_text}

Framework: {framework_id}
Business: {company} ({industry})

Provide practical guidance for answering this compliance question."""

            # Yield complete response (streaming would be implemented via response_generator)
            response = await self.response_generator.generate_simple(
                system_prompt="You are ComplianceGPT, providing contextual assessment guidance.",
                user_prompt=prompt,
                task_type="help",
                context={"framework": framework_id},
            )

            yield response

        except Exception as e:
            logger.error(f"Error streaming assessment help: {e}")
            yield f"Unable to provide guidance for question {question_id} at this time."

    # ============= PARSING METHODS =============

    def _parse_assessment_help_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for assessment help into structured format."""
        try:
            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass

        return {
            "guidance": response,
            "confidence_score": 0.8,
            "related_topics": [],
            "follow_up_suggestions": [],
            "source_references": [],
        }

    def _parse_assessment_followup_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for assessment followup into structured format."""
        try:
            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass

        return {"follow_up_questions": [response], "recommendations": [], "confidence_score": 0.8}

    def _parse_assessment_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for assessment analysis into structured format."""
        try:
            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass

        return {
            "gaps": [],
            "recommendations": [],
            "risk_assessment": {"level": "medium", "description": response},
            "compliance_insights": {"summary": response},
            "evidence_requirements": [],
        }

    # ============= FALLBACK METHODS =============

    def _get_fallback_assessment_help(
        self, question_text: str, framework_id: str
    ) -> Dict[str, Any]:
        """Provide fallback response when AI assessment help fails."""
        guidance_text = (
            f"For questions about {framework_id}, please refer to the "
            "official documentation or consult with a compliance expert. "
            f"The specific question '{question_text}' requires careful "
            "consideration of your business context."
        )
        return {
            "guidance": guidance_text,
            "confidence_score": 0.5,
            "related_topics": [framework_id, "compliance guidance"],
            "follow_up_suggestions": [
                "Review framework documentation",
                "Consult compliance expert",
            ],
            "source_references": [f"{framework_id} official documentation"],
            "request_id": f"fallback_help_{framework_id}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _get_fast_fallback_help(
        self, question_text: str, framework_id: str, question_id: str
    ) -> Dict[str, Any]:
        """Provide fast fallback response when AI times out."""
        framework_guidance = {
            "gdpr": (
                "GDPR requires lawful basis for processing personal data. "
                "Consider data minimization, consent, and individual rights."
            ),
            "iso27001": (
                "ISO 27001 focuses on information security management. "
                "Implement risk assessment and security controls."
            ),
            "sox": (
                "SOX requires internal controls over financial reporting. "
                "Ensure accurate financial disclosures."
            ),
            "hipaa": (
                "HIPAA protects health information. "
                "Implement safeguards for PHI and business associate agreements."
            ),
        }

        default_guidance = (
            f"This {framework_id} question requires careful analysis of "
            "your specific business context and compliance requirements."
        )

        guidance = framework_guidance.get(framework_id.lower(), default_guidance)

        return {
            "guidance": guidance,
            "confidence_score": 0.7,
            "related_topics": [framework_id, "compliance requirements"],
            "follow_up_suggestions": ["Review specific requirements", "Consult documentation"],
            "source_references": [f"{framework_id} standards"],
            "request_id": f"fast_fallback_{framework_id}_{question_id}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "response_time": 0.1,
        }

    def _get_fallback_assessment_followup(self, framework_id: str) -> Dict[str, Any]:
        """Provide fallback response when AI assessment followup fails."""
        return {
            "follow_up_questions": [
                f"What specific aspects of {framework_id} are you most concerned about?",
                "Do you have existing policies that might be relevant?",
                "What is your target timeline for compliance?",
            ],
            "recommendations": [
                "Review current compliance posture",
                "Identify key stakeholders",
                "Establish implementation timeline",
            ],
            "confidence_score": 0.5,
            "request_id": f"fallback_followup_{framework_id}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _get_fallback_assessment_analysis(self, framework_id: str) -> Dict[str, Any]:
        """Provide fallback response when AI assessment analysis fails."""
        return {
            "gaps": [
                {
                    "id": "general_gap",
                    "title": "General Compliance Gap",
                    "description": (
                        f"Unable to perform detailed analysis for {framework_id} at this time"
                    ),
                    "severity": "medium",
                    "category": "general",
                }
            ],
            "recommendations": [
                {
                    "id": "general_rec",
                    "title": "Conduct Manual Review",
                    "description": "Perform manual compliance assessment with expert guidance",
                    "priority": "high",
                    "effort_estimate": "2-4 weeks",
                    "impact_score": 0.7,
                }
            ],
            "risk_assessment": {
                "level": "medium",
                "description": "Unable to assess specific risks at this time",
            },
            "compliance_insights": {
                "summary": f"Manual review recommended for {framework_id} compliance"
            },
            "evidence_requirements": [],
            "request_id": f"fallback_analysis_{framework_id}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
