"""
FreemiumAssessmentService - Core AI-powered assessment orchestration.

Handles the complete freemium assessment lifecycle:
1. AI-driven question generation based on business context
2. Dynamic session management with progress tracking
3. Answer processing with intelligent follow-up logic
4. Comprehensive results generation with personalized insights
5. Conversion opportunity identification

Integrates with:
- ComplianceAssistant for AI-generated content
- AIQuestionBank for dynamic question selection
- Circuit breaker for AI resilience
- Lead scoring for behavioral analytics
"""

import uuid
from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import (
    AssessmentLead,
    FreemiumAssessmentSession,
    AIQuestionBank,
)
from services.ai.assistant import ComplianceAssistant
from services.ai.circuit_breaker import AICircuitBreaker
from services.assessment_agent import AssessmentAgent
from config.logging_config import get_logger

from .fallback_questions import get_fallback_questions
from .scoring import (
    calculate_compliance_score,
    determine_risk_level,
    identify_compliance_gaps,
)
from .recommendations import (
    generate_conversion_opportunities,
    generate_next_steps,
    generate_results_summary,
    get_fallback_recommendations,
)

logger = get_logger(__name__)


class FreemiumAssessmentService:
    """
    Core service for managing freemium AI assessments.

    Orchestrates the complete assessment flow from session creation
    to results generation with AI-powered personalization.
    """

    def __init__(self, db_session: AsyncSession, assessment_agent=None) -> None:
        self.db = db_session
        self.assistant = ComplianceAssistant(db_session)
        self.circuit_breaker = AICircuitBreaker()
        self.assessment_agent = assessment_agent

        # Configuration constants
        self.SESSION_DURATION_HOURS = 24
        self.MIN_QUESTIONS_FOR_RESULTS = 5
        self.MAX_QUESTIONS_PER_SESSION = 12
        self.DEFAULT_QUESTION_TIME_LIMIT = 300  # 5 minutes per question
        self.USE_LANGGRAPH_AGENT = True  # Feature flag for new conversational agent

    @classmethod
    async def create(cls, db_session: AsyncSession):
        """
        Async factory method to create a FreemiumAssessmentService instance.
        This properly initializes the async AssessmentAgent.
        """
        assessment_agent = await AssessmentAgent.create(db_session)
        instance = cls(db_session, assessment_agent)
        return instance

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    async def create_session(
        self,
        lead_id: uuid.UUID,
        business_type: str,
        company_size: Optional[str] = None,
        assessment_type: str = "general",
        personalization_data: Optional[Dict[str, Any]] = None,
    ) -> FreemiumAssessmentSession:
        """
        Create a new AI assessment session for a lead.

        Args:
            lead_id: UUID of the assessment lead
            business_type: Type of business (technology, healthcare, finance, etc.)
            company_size: Company size category (1-10, 11-50, etc.)
            assessment_type: Type of assessment (general, gdpr, security, compliance)
            personalization_data: Additional data for AI personalization

        Returns:
            FreemiumAssessmentSession: Created session with initial AI questions
        """
        try:
            logger.info(f"Creating assessment session for lead: {lead_id}")

            session_token = self._generate_session_token()

            expires_at = datetime.now(timezone.utc) + timedelta(
                hours=self.SESSION_DURATION_HOURS,
            )

            full_personalization_data = personalization_data or {}
            full_personalization_data.update(
                {
                    "business_type": business_type,
                    "company_size": company_size,
                },
            )

            session = FreemiumAssessmentSession(
                session_token=session_token,
                lead_id=lead_id,
                assessment_type=assessment_type,
                status="started",
                expires_at=expires_at,
                personalization_data=full_personalization_data,
                questions_answered=0,
                progress_percentage=0.0,
            )

            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)

            use_langgraph = self.USE_LANGGRAPH_AGENT

            if use_langgraph:
                initial_context = {
                    "business_type": business_type,
                    "company_size": company_size,
                    "assessment_type": assessment_type,
                    **full_personalization_data,
                }

                try:
                    agent_state = await self.assessment_agent.start_assessment(
                        session_id=str(session.id),
                        lead_id=str(lead_id),
                        initial_context=initial_context,
                    )
                except Exception as langgraph_error:
                    import traceback

                    logger.error(
                        f"LangGraph agent failed with error: {str(langgraph_error)}",
                    )
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    logger.warning("Falling back to traditional approach")
                    use_langgraph = False
                    agent_state = None

                if agent_state:
                    current_phase = agent_state.get("current_phase", "introduction")
                    if hasattr(current_phase, "value"):
                        current_phase_str = current_phase.value
                    else:
                        current_phase_str = str(current_phase)

                    session.ai_responses = {
                        "agent_state": "active",
                        "current_phase": current_phase_str,
                        "questions_generated": (
                            len(agent_state.get("questions_asked", []))
                            if "questions_asked" in agent_state
                            else 0
                        ),
                        "total_questions_planned": agent_state.get(
                            "total_questions_planned",
                            self.MAX_QUESTIONS_PER_SESSION,
                        ),
                        "using_langgraph": True,
                        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    messages = agent_state.get("messages", [])
                    if messages and len(messages) > 0:
                        session.current_question_id = "agent_intro"
                        session.total_questions = agent_state.get(
                            "total_questions_planned",
                            self.MIN_QUESTIONS_FOR_RESULTS,
                        )
                else:
                    use_langgraph = False

            if not use_langgraph:
                initial_questions = await self._generate_initial_questions(
                    session_id=session.id,
                    business_type=business_type,
                    company_size=company_size,
                    assessment_type=assessment_type,
                    personalization_data=personalization_data,
                )

                session.ai_responses = {
                    "questions": initial_questions,
                    "questions_generated": len(initial_questions),
                    "total_questions_planned": self.MAX_QUESTIONS_PER_SESSION,
                    "personalization_applied": bool(personalization_data),
                    "using_langgraph": False,
                    "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                }

                session.user_answers = {}
                session.current_question_id = (
                    initial_questions[0]["question_id"] if initial_questions else None
                )
                session.total_questions = len(initial_questions)

            session.user_answers = {}

            await self.db.commit()

            logger.info(
                f"Session created successfully: {session.id} with LangGraph "
                f"{'enabled' if self.USE_LANGGRAPH_AGENT else 'disabled'}"
            )
            return session

        except Exception as e:
            logger.error(f"Error creating assessment session: {str(e)}")
            await self.db.rollback()
            raise

    async def process_answer(
        self,
        session_id: uuid.UUID,
        question_id: str,
        answer: str,
        answer_confidence: Optional[str] = None,
        time_spent_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Process a submitted answer and determine next question.

        Args:
            session_id: UUID of the assessment session
            question_id: ID of the answered question
            answer: User's answer
            answer_confidence: User's confidence level (low, medium, high)
            time_spent_seconds: Time spent on the question

        Returns:
            Dict containing next question, progress update, and any insights
        """
        try:
            result = await self.db.execute(
                select(FreemiumAssessmentSession).where(
                    FreemiumAssessmentSession.id == session_id,
                ),
            )
            session = result.scalar_one_or_none()
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            if session.is_expired():
                raise ValueError("Session has expired")

            logger.info(
                f"Processing answer for session: {session_id}, question: {question_id}",
            )

            if session.ai_responses and session.ai_responses.get("using_langgraph", False):
                agent_state = await self.assessment_agent.process_user_response(
                    session_id=str(session.id),
                    user_response=answer,
                    confidence=answer_confidence,
                )

                if not session.user_answers:
                    session.user_answers = {}

                session.user_answers[question_id] = {
                    "answer": answer,
                    "confidence": answer_confidence,
                    "time_spent_seconds": time_spent_seconds,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                session.questions_answered = session.questions_answered + 1
                session.progress_percentage = (
                    session.questions_answered
                    / max(session.total_questions, self.MIN_QUESTIONS_FOR_RESULTS)
                ) * 100

                current_phase = agent_state.get("current_phase")
                if hasattr(current_phase, "value"):
                    phase_value = current_phase.value
                else:
                    phase_value = str(current_phase)

                questions_answered = session.questions_answered
                is_completion_phase = phase_value.lower() in ["completion", "completed"]
                # BUG FIX: was trailing comma creating a tuple instead of bool
                has_enough_answers = questions_answered >= self.MIN_QUESTIONS_FOR_RESULTS

                completion_status = (
                    "completed" if (is_completion_phase and has_enough_answers) else "in_progress"
                )

                logger.info(
                    f"Assessment status check: phase={phase_value}, "
                    f"answered={questions_answered}, "
                    f"min_required={self.MIN_QUESTIONS_FOR_RESULTS}, "
                    f"status={completion_status}"
                )
                next_question = None

                if completion_status == "in_progress":
                    messages = agent_state.get("messages", [])
                    if messages:
                        for msg in reversed(messages):
                            if hasattr(msg, "role") and msg.role == "assistant":
                                next_question = {
                                    "question_id": f"agent_{session.questions_answered + 1}",
                                    "question_text": msg.content,
                                    "question_type": "conversational",
                                    "category": agent_state.get(
                                        "current_phase",
                                        "general",
                                    ),
                                }
                                break

                session.ai_responses.update(
                    {
                        "current_phase": str(
                            agent_state.get("current_phase", "unknown"),
                        ),
                        "questions_answered": session.questions_answered,
                        "compliance_score": agent_state.get("compliance_score", 0),
                        "risk_level": agent_state.get("risk_level", "unknown"),
                    },
                )

                if completion_status == "completed":
                    session.completed_at = datetime.now(timezone.utc)

            else:
                # Traditional processing (non-LangGraph)
                if not session.user_answers:
                    session.user_answers = {}

                session.user_answers[question_id] = {
                    "answer": answer,
                    "confidence": answer_confidence,
                    "time_spent_seconds": time_spent_seconds,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                session.questions_answered += 1
                if session.total_questions > 0:
                    session.progress_percentage = (
                        session.questions_answered / session.total_questions
                    ) * 100
                else:
                    session.progress_percentage = min(
                        session.questions_answered * 20, 100
                    )

                next_question = None
                completion_status = "in_progress"

                if session.questions_answered >= self.MIN_QUESTIONS_FOR_RESULTS:
                    follow_up_needed = await self._determine_follow_up_questions(
                        session_id=session_id,
                        latest_answer={
                            "question_id": question_id,
                            "answer": answer,
                            "confidence": answer_confidence,
                        },
                    )

                    if (
                        follow_up_needed
                        and session.questions_answered < self.MAX_QUESTIONS_PER_SESSION
                    ):
                        next_question = await self._generate_follow_up_question(
                            session_id=session_id,
                            previous_answers=session.user_answers,
                        )
                    else:
                        completion_status = "completed"
                        session.completed_at = datetime.now(timezone.utc)
                else:
                    next_question = await self._get_next_question(
                        session_id=session_id,
                        answered_questions=list(session.user_answers.keys()),
                    )

            session.completion_status = completion_status
            if next_question:
                session.current_question_id = next_question["question_id"]
            else:
                session.current_question_id = None

            await self.db.commit()

            response = {
                "session_id": str(session_id),
                "progress_percentage": session.progress_percentage,
                "questions_answered": session.questions_answered,
                "total_questions": session.total_questions,
                "completion_status": completion_status,
                "next_question": next_question,
                "answer_processed": True,
            }

            if answer_confidence == "high" and len(answer) > 50:
                response["insights"] = await self._generate_answer_insights(
                    question_id,
                    answer,
                )

            logger.info(f"Answer processed successfully for session: {session_id}")
            return response

        except Exception as e:
            logger.error(f"Error processing answer: {str(e)}")
            await self.db.rollback()
            raise

    async def generate_results(self, session_id: uuid.UUID) -> Dict[str, Any]:
        """
        Generate comprehensive assessment results with AI insights.

        Args:
            session_id: UUID of the completed assessment session

        Returns:
            Dict containing complete assessment results and recommendations
        """
        try:
            result = await self.db.execute(
                select(FreemiumAssessmentSession).where(
                    FreemiumAssessmentSession.id == session_id,
                ),
            )
            session = result.scalar_one_or_none()
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            if session.questions_answered < self.MIN_QUESTIONS_FOR_RESULTS:
                raise ValueError("Insufficient answers to generate results")

            logger.info(f"Generating results for session: {session_id}")

            result = await self.db.execute(
                select(AssessmentLead).where(AssessmentLead.id == session.lead_id),
            )
            lead = result.scalar_one_or_none()

            personalization = session.personalization_data or {}

            assessment_context = {
                "business_type": personalization.get("business_type"),
                "company_size": personalization.get("company_size"),
                "assessment_type": session.assessment_type,
                "industry": lead.industry if lead else None,
                "company_name": lead.company_name if lead else None,
                "answers": session.user_answers,
                "personalization_data": session.personalization_data,
            }

            ai_analysis = await self._generate_ai_analysis(assessment_context)

            compliance_score = calculate_compliance_score(
                session.user_answers,
                session.assessment_type,
            )

            risk_level = determine_risk_level(compliance_score, ai_analysis)

            recommendations = await self._generate_recommendations(
                assessment_context,
                ai_analysis,
                compliance_score,
            )

            gaps_identified = identify_compliance_gaps(
                session.user_answers,
                session.assessment_type,
                ai_analysis,
            )

            conversion_opportunities = generate_conversion_opportunities(
                compliance_score,
                risk_level,
                gaps_identified,
                lead,
            )

            results_summary = generate_results_summary(
                compliance_score,
                risk_level,
                recommendations,
                gaps_identified,
            )

            session.compliance_score = compliance_score
            session.risk_assessment = ai_analysis
            session.recommendations = recommendations
            session.gaps_identified = gaps_identified
            session.results_summary = results_summary

            await self.db.commit()

            results = {
                "session_id": str(session_id),
                "compliance_score": compliance_score,
                "risk_level": risk_level,
                "completed_at": (
                    session.completed_at.isoformat() if session.completed_at else None
                ),
                "risk_assessment": ai_analysis,
                "recommendations": recommendations,
                "gaps_identified": gaps_identified,
                "results_summary": results_summary,
                "conversion_opportunities": conversion_opportunities,
                "next_steps": generate_next_steps(compliance_score, risk_level),
                "assessment_metadata": {
                    "questions_answered": session.questions_answered,
                    "assessment_type": session.assessment_type,
                    "business_type": personalization.get("business_type"),
                    "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

            logger.info(f"Results generated successfully for session: {session_id}")
            return results

        except Exception as e:
            logger.error(f"Error generating results: {str(e)}")
            raise

    async def calculate_answer_score_impact(
        self, question_id: str, answer: str, confidence: Optional[str] = None
    ) -> int:
        """
        Calculate the scoring impact of a specific answer.

        Args:
            question_id: ID of the answered question
            answer: User's answer
            confidence: User's confidence level

        Returns:
            int: Score impact points (can be negative)
        """
        try:
            base_score = 5

            if len(str(answer)) > 100:
                base_score += 5
            elif len(str(answer)) < 20:
                base_score -= 2

            confidence_multiplier = {"high": 1.5, "medium": 1.0, "low": 0.8}.get(
                confidence,
                1.0,
            )

            try:
                uuid.UUID(question_id)
                result = await self.db.execute(
                    select(AIQuestionBank).where(AIQuestionBank.id == question_id),
                )
                question = result.scalar_one_or_none()
                if question:
                    difficulty_multiplier = question.difficulty_level / 5.0
                    base_score = int(base_score * difficulty_multiplier)
            except (ValueError, TypeError):
                logger.debug(
                    f"Skipping question bank lookup for non-UUID question_id: {question_id}",
                )

            final_score = int(base_score * confidence_multiplier)

            logger.debug(
                f"Score impact calculated: {final_score} for question {question_id}",
            )
            return final_score

        except Exception as e:
            logger.error(f"Error calculating score impact: {str(e)}")
            return 5  # Default safe score

    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================

    def _generate_session_token(self) -> str:
        """Generate a secure session token."""
        return uuid.uuid4().hex + uuid.uuid4().hex  # 64 characters

    async def _generate_initial_questions(
        self,
        session_id: uuid.UUID,
        business_type: str,
        company_size: Optional[str],
        assessment_type: str,
        personalization_data: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Generate initial AI questions based on business context."""
        try:
            if not self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                logger.warning("AI unavailable, using fallback questions")
                return get_fallback_questions(assessment_type)

            context = {
                "business_type": business_type,
                "company_size": company_size,
                "assessment_type": assessment_type,
                "personalization": personalization_data or {},
            }

            questions_data = await self.assistant.generate_assessment_questions(
                business_context=context,
                max_questions=3,
                difficulty_level="mixed",
            )

            return questions_data.get(
                "questions",
                get_fallback_questions(assessment_type),
            )

        except Exception as e:
            logger.error(f"Error generating initial questions: {str(e)}")
            return get_fallback_questions(assessment_type)

    async def _determine_follow_up_questions(
        self, session_id: uuid.UUID, latest_answer: Dict[str, Any]
    ) -> bool:
        """Determine if follow-up questions are needed based on latest answer."""
        try:
            answer = latest_answer.get("answer", "")
            confidence = latest_answer.get("confidence", "medium")

            if len(str(answer)) < 30 or confidence == "low":
                return True

            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                follow_up_analysis = await self.assistant.analyze_answer_completeness(
                    question_id=latest_answer.get("question_id"),
                    answer=answer,
                    confidence=confidence,
                )
                return follow_up_analysis.get("needs_follow_up", False)

            return False

        except Exception as e:
            logger.error(f"Error determining follow-up questions: {str(e)}")
            return False

    async def _generate_follow_up_question(
        self, session_id: uuid.UUID, previous_answers: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate a follow-up question based on previous answers."""
        try:
            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                follow_up = await self.assistant.generate_followup_questions(
                    previous_answers=previous_answers,
                    max_questions=1,
                )
                questions = follow_up.get("questions", [])
                return questions[0] if questions else None

            return None

        except Exception as e:
            logger.error(f"Error generating follow-up question: {str(e)}")
            return None

    async def _get_next_question(
        self, session_id: uuid.UUID, answered_questions: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get the next question dynamically based on previous answers."""
        try:
            result = await self.db.execute(
                select(FreemiumAssessmentSession).where(
                    FreemiumAssessmentSession.id == session_id,
                ),
            )
            session = result.scalar_one_or_none()
            if not session:
                return None

            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                follow_up = await self.assistant.generate_followup_questions(
                    previous_answers=session.user_answers,
                    max_questions=1,
                )
                questions = follow_up.get("questions", [])
                if questions:
                    return questions[0]

            # Fallback: select from question bank if not already asked
            fallback = get_fallback_questions(session.assessment_type)
            for question in fallback:
                if question["question_id"] not in answered_questions:
                    return question

            return None

        except Exception as e:
            logger.error(f"Error getting next question: {str(e)}")
            return None

    async def _generate_ai_analysis(self, assessment_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI-powered analysis of assessment responses."""
        try:
            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                analysis = await self.assistant.analyze_assessment_results(
                    assessment_results=assessment_context.get("responses", {}),
                    framework_id=assessment_context.get("framework_id", "general"),
                    business_profile_id=(
                        UUID(assessment_context.get("business_profile_id"))
                        if assessment_context.get("business_profile_id")
                        else UUID("00000000-0000-0000-0000-000000000000")
                    ),
                )
                return analysis
            else:
                return {"analysis": "AI analysis unavailable", "confidence": 0.5}

        except Exception as e:
            logger.error(f"Error generating AI analysis: {str(e)}")
            return {"analysis": "Analysis failed", "error": str(e)}

    async def _generate_recommendations(
        self,
        assessment_context: Dict[str, Any],
        ai_analysis: Dict[str, Any],
        compliance_score: float,
    ) -> List[Dict[str, Any]]:
        """Generate personalized recommendations."""
        try:
            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                recommendations = await self.assistant.get_personalized_recommendations(
                    assessment_context=assessment_context,
                    analysis_results=ai_analysis,
                    compliance_score=compliance_score,
                )
                return recommendations.get("recommendations", [])
            else:
                return get_fallback_recommendations(compliance_score)

        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return get_fallback_recommendations(compliance_score)

    async def _generate_answer_insights(self, question_id: str, answer: str) -> Dict[str, Any]:
        """Generate insights for a specific answer."""
        try:
            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                insights = await self.assistant.analyze_specific_answer(
                    question_id=question_id,
                    answer=answer,
                )
                return insights
            else:
                return {
                    "insight": "Detailed insights are available with our full platform",
                }

        except Exception as e:
            logger.error(f"Error generating answer insights: {str(e)}")
            return {"insight": "Unable to generate insights at this time"}
