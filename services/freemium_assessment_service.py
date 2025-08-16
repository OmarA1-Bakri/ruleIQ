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
from datetime import datetime, timedelta
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
from services.assessment_agent import AssessmentAgent  # LangGraph conversational agent
from config.logging_config import get_logger

logger = get_logger(__name__)


class FreemiumAssessmentService:
    """
    Core service for managing freemium AI assessments.

    Orchestrates the complete assessment flow from session creation
    to results generation with AI-powered personalization.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session
        self.assistant = ComplianceAssistant(db_session)
        self.circuit_breaker = AICircuitBreaker()
        self.assessment_agent = AssessmentAgent(db_session)  # LangGraph conversational agent

        # Configuration constants
        self.SESSION_DURATION_HOURS = 24
        self.MIN_QUESTIONS_FOR_RESULTS = 5
        self.MAX_QUESTIONS_PER_SESSION = 12
        self.DEFAULT_QUESTION_TIME_LIMIT = 300  # 5 minutes per question
        self.USE_LANGGRAPH_AGENT = True  # Feature flag for new conversational agent

    async def create_session(
        self,
        lead_id: uuid.UUID,
        business_type: str,
        company_size: Optional[str] = None,
        assessment_type: str = "general",
        personalization_data: Optional[Dict[str, Any]] = None
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

            # Generate secure session token
            session_token = self._generate_session_token()

            # Set session expiration
            expires_at = datetime.utcnow() + timedelta(hours=self.SESSION_DURATION_HOURS)

            # Prepare personalization data with business context
            full_personalization_data = personalization_data or {}
            full_personalization_data.update({
                "business_type": business_type,
                "company_size": company_size,
            })

            # Create session record
            session = FreemiumAssessmentSession(
                session_token=session_token,
                lead_id=lead_id,
                assessment_type=assessment_type,
                status="started",  # Using status instead of completion_status
                expires_at=expires_at,
                personalization_data=full_personalization_data,
                questions_answered=0,
                progress_percentage=0.0
            )

            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)

            # Use LangGraph agent if enabled, otherwise use traditional approach
            if self.USE_LANGGRAPH_AGENT:
                # Initialize LangGraph assessment agent state
                initial_context = {
                    "business_type": business_type,
                    "company_size": company_size,
                    "assessment_type": assessment_type,
                    **full_personalization_data
                }
                
                # Start assessment with LangGraph agent
                agent_state = await self.assessment_agent.start_assessment(
                    session_id=str(session.id),
                    lead_id=str(lead_id),
                    initial_context=initial_context
                )
                
                # Store agent state in session
                session.ai_responses = {
                    "agent_state": "active",
                    "current_phase": agent_state.get("current_phase", "introduction").value if hasattr(agent_state.get("current_phase", "introduction"), 'value') else str(agent_state.get("current_phase", "introduction")),
                    "questions_generated": len(agent_state.get("questions_asked", [])),
                    "total_questions_planned": agent_state.get("total_questions_planned", self.MAX_QUESTIONS_PER_SESSION),
                    "using_langgraph": True,
                    "generation_timestamp": datetime.utcnow().isoformat()
                }
                
                # Extract first question from agent messages
                messages = agent_state.get("messages", [])
                if messages and len(messages) > 0:
                    # Last message should be the introduction/first question
                    session.current_question_id = "agent_intro"
                    session.total_questions = agent_state.get("total_questions_planned", self.MIN_QUESTIONS_FOR_RESULTS)
                
            else:
                # Generate initial AI questions based on business context (traditional approach)
                initial_questions = await self._generate_initial_questions(
                    session_id=session.id,
                    business_type=business_type,
                    company_size=company_size,
                    assessment_type=assessment_type,
                    personalization_data=personalization_data
                )

                # Store questions in session
                session.ai_responses = {
                    "questions_generated": len(initial_questions),
                    "total_questions_planned": self.MAX_QUESTIONS_PER_SESSION,
                    "personalization_applied": bool(personalization_data),
                    "using_langgraph": False,
                    "generation_timestamp": datetime.utcnow().isoformat()
                }

                session.user_answers = {}
                session.current_question_id = initial_questions[0]["question_id"] if initial_questions else None
                session.total_questions = len(initial_questions)

            session.user_answers = {}

            await self.db.commit()

            questions_count = session.ai_responses.get("questions_generated", 0) if self.USE_LANGGRAPH_AGENT else len(initial_questions if 'initial_questions' in locals() else [])
            logger.info(f"Session created successfully: {session.id} with LangGraph={'enabled' if self.USE_LANGGRAPH_AGENT else 'disabled'}")
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
        time_spent_seconds: Optional[int] = None
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
            result = await self.db.execute(select(FreemiumAssessmentSession).where(FreemiumAssessmentSession.id == session_id))
            session = result.scalar_one_or_none()
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            if session.is_expired():
                raise ValueError("Session has expired")

            logger.info(f"Processing answer for session: {session_id}, question: {question_id}")

            # Check if using LangGraph agent
            if session.ai_responses and session.ai_responses.get("using_langgraph", False):
                # Process answer with LangGraph agent
                agent_state = await self.assessment_agent.process_user_response(
                    session_id=str(session.id),
                    user_response=answer,
                    confidence=answer_confidence
                )
                
                # Store the answer
                if not session.user_answers:
                    session.user_answers = {}

                session.user_answers[question_id] = {
                    "answer": answer,
                    "confidence": answer_confidence,
                    "time_spent_seconds": time_spent_seconds,
                    "timestamp": datetime.utcnow().isoformat()
                }

                # Update progress from agent state
                session.questions_answered = agent_state.get("questions_answered", session.questions_answered + 1)
                session.progress_percentage = (session.questions_answered / max(session.total_questions, self.MIN_QUESTIONS_FOR_RESULTS)) * 100
                
                # Check if assessment is complete
                completion_status = "completed" if agent_state.get("current_phase") == "completion" else "in_progress"
                next_question = None
                
                # Extract next question from agent messages if not complete
                if completion_status == "in_progress":
                    messages = agent_state.get("messages", [])
                    if messages:
                        # Get the last AI message as the next question
                        for msg in reversed(messages):
                            if hasattr(msg, 'role') and msg.role == 'assistant':
                                next_question = {
                                    "question_id": f"agent_{session.questions_answered + 1}",
                                    "question_text": msg.content,
                                    "question_type": "conversational",
                                    "category": agent_state.get("current_phase", "general")
                                }
                                break
                
                # Update session with agent state
                session.ai_responses.update({
                    "current_phase": str(agent_state.get("current_phase", "unknown")),
                    "questions_answered": session.questions_answered,
                    "compliance_score": agent_state.get("compliance_score", 0),
                    "risk_level": agent_state.get("risk_level", "unknown")
                })
                
                if completion_status == "completed":
                    session.completed_at = datetime.utcnow()
                    
            else:
                # Traditional processing (non-LangGraph)
                # Store the answer
                if not session.user_answers:
                    session.user_answers = {}

                session.user_answers[question_id] = {
                    "answer": answer,
                    "confidence": answer_confidence,
                    "time_spent_seconds": time_spent_seconds,
                    "timestamp": datetime.utcnow().isoformat()
                }

                # Update progress
                session.questions_answered += 1
                # Calculate progress safely, avoiding division by zero
                if session.total_questions > 0:
                    session.progress_percentage = (session.questions_answered / session.total_questions) * 100
                else:
                    # If no questions were generated (e.g., due to AI quota), use a default progression
                    session.progress_percentage = min(session.questions_answered * 20, 100)  # 20% per question

                # Determine if we need more questions or can complete
                next_question = None
                completion_status = "in_progress"

                if session.questions_answered >= self.MIN_QUESTIONS_FOR_RESULTS:
                    # Use AI to determine if we have enough information or need follow-up questions
                    follow_up_needed = await self._determine_follow_up_questions(
                        session_id=session_id,
                        latest_answer={
                            "question_id": question_id,
                            "answer": answer,
                            "confidence": answer_confidence
                        }
                    )

                    if follow_up_needed and session.questions_answered < self.MAX_QUESTIONS_PER_SESSION:
                        next_question = await self._generate_follow_up_question(
                            session_id=session_id,
                            previous_answers=session.user_answers
                        )
                    else:
                        completion_status = "completed"
                        session.completed_at = datetime.utcnow()
                else:
                    # Generate next standard question
                    next_question = await self._get_next_question(
                        session_id=session_id,
                    answered_questions=list(session.user_answers.keys())
                )

            # Update session status
            session.completion_status = completion_status
            if next_question:
                session.current_question_id = next_question["question_id"]
            else:
                session.current_question_id = None

            await self.db.commit()

            # Prepare response
            response = {
                "session_id": str(session_id),
                "progress_percentage": session.progress_percentage,
                "questions_answered": session.questions_answered,
                "total_questions": session.total_questions,
                "completion_status": completion_status,
                "next_question": next_question,
                "answer_processed": True
            }

            # Add AI insights if available
            if answer_confidence == "high" and len(answer) > 50:
                response["insights"] = await self._generate_answer_insights(question_id, answer)

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
            result = await self.db.execute(select(FreemiumAssessmentSession).where(FreemiumAssessmentSession.id == session_id))
            session = result.scalar_one_or_none()
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            if session.questions_answered < self.MIN_QUESTIONS_FOR_RESULTS:
                raise ValueError("Insufficient answers to generate results")

            logger.info(f"Generating results for session: {session_id}")

            # Get lead information for personalization
            result = await self.db.execute(select(AssessmentLead).where(AssessmentLead.id == session.lead_id))
            lead = result.scalar_one_or_none()

            # Get business context from personalization data
            personalization = session.personalization_data or {}

            # Prepare context for AI analysis
            assessment_context = {
                "business_type": personalization.get("business_type"),
                "company_size": personalization.get("company_size"),
                "assessment_type": session.assessment_type,
                "industry": lead.industry if lead else None,
                "company_name": lead.company_name if lead else None,
                "answers": session.user_answers,
                "personalization_data": session.personalization_data
            }

            # Generate AI-powered compliance analysis
            ai_analysis = await self._generate_ai_analysis(assessment_context)

            # Calculate compliance score
            compliance_score = self._calculate_compliance_score(
                session.user_answers,
                session.assessment_type
            )

            # Determine risk level
            risk_level = self._determine_risk_level(compliance_score, ai_analysis)

            # Generate personalized recommendations
            recommendations = await self._generate_recommendations(
                assessment_context,
                ai_analysis,
                compliance_score
            )

            # Identify compliance gaps
            gaps_identified = self._identify_compliance_gaps(
                session.user_answers,
                session.assessment_type,
                ai_analysis
            )

            # Generate conversion opportunities
            conversion_opportunities = self._generate_conversion_opportunities(
                compliance_score,
                risk_level,
                gaps_identified,
                lead
            )

            # Create results summary
            results_summary = await self._generate_results_summary(
                compliance_score,
                risk_level,
                recommendations,
                gaps_identified
            )

            # Store results in session
            session.compliance_score = compliance_score
            session.risk_assessment = ai_analysis
            session.recommendations = recommendations
            session.gaps_identified = gaps_identified
            session.results_summary = results_summary

            await self.db.commit()

            # Prepare comprehensive response
            results = {
                "session_id": str(session_id),
                "compliance_score": compliance_score,
                "risk_level": risk_level,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "risk_assessment": ai_analysis,
                "recommendations": recommendations,
                "gaps_identified": gaps_identified,
                "results_summary": results_summary,
                "conversion_opportunities": conversion_opportunities,
                "next_steps": self._generate_next_steps(compliance_score, risk_level),
                "assessment_metadata": {
                    "questions_answered": session.questions_answered,
                    "assessment_type": session.assessment_type,
                    "business_type": personalization.get("business_type"),
                    "generation_timestamp": datetime.utcnow().isoformat()
                }
            }

            logger.info(f"Results generated successfully for session: {session_id}")
            return results

        except Exception as e:
            logger.error(f"Error generating results: {str(e)}")
            raise

    async def calculate_answer_score_impact(
        self,
        question_id: str,
        answer: str,
        confidence: Optional[str] = None
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
            # Base score impact
            base_score = 5

            # Adjust for answer completeness
            if len(str(answer)) > 100:
                base_score += 5
            elif len(str(answer)) < 20:
                base_score -= 2

            # Adjust for confidence level
            confidence_multiplier = {
                "high": 1.5,
                "medium": 1.0,
                "low": 0.8
            }.get(confidence, 1.0)

            # Adjust for question complexity (look up in question bank if available)
            result = await self.db.execute(select(AIQuestionBank).where(AIQuestionBank.question_id == question_id))
            question = result.scalar_one_or_none()
            if question:
                difficulty_multiplier = question.difficulty_level / 5.0  # Scale 1-10 to 0.2-2.0
                base_score = int(base_score * difficulty_multiplier)

            final_score = int(base_score * confidence_multiplier)

            logger.debug(f"Score impact calculated: {final_score} for question {question_id}")
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
        personalization_data: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate initial AI questions based on business context."""
        try:
            # Check if AI is available
            if not self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                logger.warning("AI unavailable, using fallback questions")
                return self._get_fallback_questions(assessment_type)

            # Build context for AI question generation
            context = {
                "business_type": business_type,
                "company_size": company_size,
                "assessment_type": assessment_type,
                "personalization": personalization_data or {}
            }

            # Generate INITIAL questions using AI assistant (start with just 2-3 to be conversational)
            questions_data = await self.assistant.generate_assessment_questions(
                business_context=context,
                max_questions=3,  # Start with fewer questions, generate more based on answers
                difficulty_level="mixed"
            )

            return questions_data.get("questions", self._get_fallback_questions(assessment_type))

        except Exception as e:
            logger.error(f"Error generating initial questions: {str(e)}")
            return self._get_fallback_questions(assessment_type)

    def _get_fallback_questions(self, assessment_type: str) -> List[Dict[str, Any]]:
        """Get hardcoded fallback questions when AI is unavailable."""
        fallback_questions = {
            "general": [
                {
                    "question_id": "gen_001",
                    "question_text": "Does your organization handle personal data from customers or employees?",
                    "question_type": "yes_no",
                    "category": "data_protection",
                    "options": ["Yes", "No", "Unsure"]
                },
                {
                    "question_id": "gen_002",
                    "question_text": "Do you have documented information security policies?",
                    "question_type": "yes_no",
                    "category": "security",
                    "options": ["Yes", "No", "In development"]
                },
                {
                    "question_id": "gen_003",
                    "question_text": "How do you currently back up your business data?",
                    "question_type": "multiple_choice",
                    "category": "data_management",
                    "options": ["Cloud backup", "Local backup", "Both", "No formal backup", "Don't know"]
                },
                {
                    "question_id": "gen_004",
                    "question_text": "Do you conduct regular security training for your employees?",
                    "question_type": "yes_no",
                    "category": "training",
                    "options": ["Yes, regularly", "Yes, occasionally", "No", "Planning to start"]
                },
                {
                    "question_id": "gen_005",
                    "question_text": "How do you manage access to sensitive business data?",
                    "question_type": "multiple_choice",
                    "category": "access_control",
                    "options": ["Role-based access", "Department-based", "Everyone has access", "No formal system", "Unsure"]
                },
                {
                    "question_id": "gen_006",
                    "question_text": "Do you have a data breach response plan?",
                    "question_type": "yes_no",
                    "category": "incident_response",
                    "options": ["Yes, documented", "Yes, informal", "No", "In development"]
                },
                {
                    "question_id": "gen_007",
                    "question_text": "How often do you review your compliance status?",
                    "question_type": "multiple_choice",
                    "category": "compliance_review",
                    "options": ["Monthly", "Quarterly", "Annually", "Never", "Ad-hoc basis"]
                },
                {
                    "question_id": "gen_008",
                    "question_text": "Do you use encryption for sensitive data?",
                    "question_type": "yes_no",
                    "category": "data_security",
                    "options": ["Yes, at rest and in transit", "Yes, partially", "No", "Don't know"]
                }
            ],
            "gdpr": [
                {
                    "question_id": "gdpr_001",
                    "question_text": "Do you process personal data of EU residents?",
                    "question_type": "yes_no",
                    "category": "scope",
                    "options": ["Yes", "No", "Possibly"]
                },
                {
                    "question_id": "gdpr_002",
                    "question_text": "Do you have a Data Protection Officer (DPO) appointed?",
                    "question_type": "yes_no",
                    "category": "governance",
                    "options": ["Yes", "No", "Not required"]
                },
                {
                    "question_id": "gdpr_003",
                    "question_text": "Do you have a privacy policy that meets GDPR requirements?",
                    "question_type": "yes_no",
                    "category": "documentation",
                    "options": ["Yes, fully compliant", "Yes, needs updating", "No", "Unsure"]
                },
                {
                    "question_id": "gdpr_004",
                    "question_text": "How do you handle data subject access requests?",
                    "question_type": "multiple_choice",
                    "category": "data_rights",
                    "options": ["Automated process", "Manual process", "No formal process", "Never received any"]
                },
                {
                    "question_id": "gdpr_005",
                    "question_text": "Do you maintain records of processing activities?",
                    "question_type": "yes_no",
                    "category": "documentation",
                    "options": ["Yes, comprehensive", "Yes, partial", "No", "Planning to implement"]
                },
                {
                    "question_id": "gdpr_006",
                    "question_text": "Have you conducted a Data Protection Impact Assessment (DPIA)?",
                    "question_type": "yes_no",
                    "category": "assessment",
                    "options": ["Yes, recently", "Yes, over a year ago", "No", "Not sure if required"]
                }
            ],
            "security": [
                {
                    "question_id": "sec_001",
                    "question_text": "Do you use multi-factor authentication for business systems?",
                    "question_type": "yes_no",
                    "category": "access_control",
                    "options": ["Yes, everywhere", "Yes, partially", "No", "Don't know"]
                },
                {
                    "question_id": "sec_002",
                    "question_text": "How often do you update your software and systems?",
                    "question_type": "multiple_choice",
                    "category": "maintenance",
                    "options": ["Immediately", "Monthly", "Quarterly", "Annually", "Rarely"]
                },
                {
                    "question_id": "sec_003",
                    "question_text": "Do you perform regular security vulnerability assessments?",
                    "question_type": "yes_no",
                    "category": "assessment",
                    "options": ["Yes, regularly", "Yes, occasionally", "No", "Planning to start"]
                },
                {
                    "question_id": "sec_004",
                    "question_text": "How do you manage user passwords and credentials?",
                    "question_type": "multiple_choice",
                    "category": "credential_management",
                    "options": ["Password manager", "Single sign-on", "Manual tracking", "No formal system"]
                },
                {
                    "question_id": "sec_005",
                    "question_text": "Do you have network segmentation in place?",
                    "question_type": "yes_no",
                    "category": "network_security",
                    "options": ["Yes, comprehensive", "Yes, partial", "No", "Don't know"]
                },
                {
                    "question_id": "sec_006",
                    "question_text": "How do you monitor for security incidents?",
                    "question_type": "multiple_choice",
                    "category": "monitoring",
                    "options": ["24/7 SOC", "Automated tools", "Manual reviews", "No active monitoring"]
                },
                {
                    "question_id": "sec_007",
                    "question_text": "Do you have an incident response team?",
                    "question_type": "yes_no",
                    "category": "incident_response",
                    "options": ["Yes, dedicated team", "Yes, assigned roles", "No", "Outsourced"]
                },
                {
                    "question_id": "sec_008",
                    "question_text": "How often do you conduct security awareness training?",
                    "question_type": "multiple_choice",
                    "category": "training",
                    "options": ["Monthly", "Quarterly", "Annually", "During onboarding only", "Never"]
                },
                {
                    "question_id": "sec_009",
                    "question_text": "Do you maintain an inventory of all IT assets?",
                    "question_type": "yes_no",
                    "category": "asset_management",
                    "options": ["Yes, automated", "Yes, manual", "Partial", "No"]
                },
                {
                    "question_id": "sec_010",
                    "question_text": "Have you implemented Zero Trust security principles?",
                    "question_type": "yes_no",
                    "category": "architecture",
                    "options": ["Yes, fully", "Yes, partially", "No", "Planning to implement"]
                }
            ]
        }

        return fallback_questions.get(assessment_type, fallback_questions["general"])

    async def _determine_follow_up_questions(
        self,
        session_id: uuid.UUID,
        latest_answer: Dict[str, Any]
    ) -> bool:
        """Determine if follow-up questions are needed based on latest answer."""
        try:
            # Simple heuristic: if answer is short or low confidence, ask follow-up
            answer = latest_answer.get("answer", "")
            confidence = latest_answer.get("confidence", "medium")

            if len(str(answer)) < 30 or confidence == "low":
                return True

            # Use AI to determine if follow-up is needed (if available)
            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                follow_up_analysis = await self.assistant.analyze_answer_completeness(
                    question_id=latest_answer.get("question_id"),
                    answer=answer,
                    confidence=confidence
                )
                return follow_up_analysis.get("needs_follow_up", False)

            return False

        except Exception as e:
            logger.error(f"Error determining follow-up questions: {str(e)}")
            return False

    async def _generate_follow_up_question(
        self,
        session_id: uuid.UUID,
        previous_answers: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate a follow-up question based on previous answers."""
        try:
            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                follow_up = await self.assistant.generate_followup_questions(
                    previous_answers=previous_answers,
                    max_questions=1
                )
                questions = follow_up.get("questions", [])
                return questions[0] if questions else None

            return None

        except Exception as e:
            logger.error(f"Error generating follow-up question: {str(e)}")
            return None

    async def _get_next_question(
        self,
        session_id: uuid.UUID,
        answered_questions: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get the next question dynamically based on previous answers."""
        try:
            # Get the session to access previous answers
            result = await self.db.execute(select(FreemiumAssessmentSession).where(FreemiumAssessmentSession.id == session_id))
            session = result.scalar_one_or_none()
            if not session:
                return None
            
            # If AI is available, generate a contextual follow-up question
            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                # Build context from previous answers
                context = {
                    "previous_answers": session.user_answers,
                    "business_type": session.personalization_data.get("business_type"),
                    "assessment_type": session.assessment_type,
                    "questions_answered": len(answered_questions)
                }
                
                # Generate a smart follow-up question based on what we've learned
                follow_up = await self.assistant.generate_followup_questions(
                    previous_answers=session.user_answers,
                    max_questions=1
                )
                questions = follow_up.get("questions", [])
                if questions:
                    return questions[0]
            
            # Fallback: Select from our question bank if not already asked
            fallback_questions = self._get_fallback_questions(session.assessment_type)
            for question in fallback_questions:
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
                    business_profile_id=UUID(assessment_context.get("business_profile_id")) if assessment_context.get("business_profile_id") else UUID("00000000-0000-0000-0000-000000000000")
                )
                return analysis
            else:
                return {"analysis": "AI analysis unavailable", "confidence": 0.5}

        except Exception as e:
            logger.error(f"Error generating AI analysis: {str(e)}")
            return {"analysis": "Analysis failed", "error": str(e)}

    def _calculate_compliance_score(
        self,
        answers: Dict[str, Any],
        assessment_type: str
    ) -> float:
        """Calculate compliance score based on answers."""
        if not answers:
            return 0.0

        # Simple scoring algorithm - can be made more sophisticated
        total_score = 0.0
        answer_count = len(answers)

        for answer_data in answers.values():
            answer = str(answer_data.get("answer", "")).lower()
            confidence = answer_data.get("confidence", "medium")

            # Basic scoring
            if "yes" in answer or "implemented" in answer or "compliant" in answer:
                score = 85.0
            elif "partially" in answer or "in progress" in answer:
                score = 60.0
            elif "no" in answer or "not implemented" in answer:
                score = 25.0
            else:
                score = 50.0  # Neutral/text answers

            # Adjust for confidence
            confidence_multiplier = {"high": 1.0, "medium": 0.9, "low": 0.7}.get(confidence, 0.8)
            total_score += score * confidence_multiplier

        return round(total_score / answer_count, 1)

    def _determine_risk_level(self, compliance_score: float, ai_analysis: Dict[str, Any]) -> str:
        """Determine risk level based on compliance score and AI analysis."""
        if compliance_score >= 80:
            return "low"
        elif compliance_score >= 60:
            return "medium"
        elif compliance_score >= 40:
            return "high"
        else:
            return "critical"

    async def _generate_recommendations(
        self,
        assessment_context: Dict[str, Any],
        ai_analysis: Dict[str, Any],
        compliance_score: float
    ) -> List[Dict[str, Any]]:
        """Generate personalized recommendations."""
        try:
            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                recommendations = await self.assistant.get_personalized_recommendations(
                    assessment_context=assessment_context,
                    analysis_results=ai_analysis,
                    compliance_score=compliance_score
                )
                return recommendations.get("recommendations", [])
            else:
                return self._get_fallback_recommendations(compliance_score)

        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return self._get_fallback_recommendations(compliance_score)

    def _get_fallback_recommendations(self, compliance_score: float) -> List[Dict[str, Any]]:
        """Get fallback recommendations when AI is unavailable."""
        if compliance_score < 40:
            return [
                {
                    "priority": "high",
                    "title": "Implement Basic Security Policies",
                    "description": "Establish fundamental information security policies and procedures.",
                    "estimated_effort": "2-4 weeks"
                },
                {
                    "priority": "high",
                    "title": "Data Protection Assessment",
                    "description": "Conduct a comprehensive review of personal data handling practices.",
                    "estimated_effort": "1-2 weeks"
                }
            ]
        elif compliance_score < 70:
            return [
                {
                    "priority": "medium",
                    "title": "Enhance Existing Controls",
                    "description": "Strengthen current compliance measures and fill identified gaps.",
                    "estimated_effort": "3-6 weeks"
                }
            ]
        else:
            return [
                {
                    "priority": "low",
                    "title": "Continuous Improvement",
                    "description": "Implement regular reviews and updates to maintain compliance.",
                    "estimated_effort": "Ongoing"
                }
            ]

    def _identify_compliance_gaps(
        self,
        answers: Dict[str, Any],
        assessment_type: str,
        ai_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify specific compliance gaps based on answers."""
        gaps = []

        for question_id, answer_data in answers.items():
            answer = str(answer_data.get("answer", "")).lower()

            if "no" in answer or "not implemented" in answer:
                gaps.append({
                    "question_id": question_id,
                    "gap_type": "missing_control",
                    "severity": "medium",
                    "description": f"Gap identified in {question_id}"
                })

        return gaps

    def _generate_conversion_opportunities(
        self,
        compliance_score: float,
        risk_level: str,
        gaps_identified: List[Dict[str, Any]],
        lead: Optional[AssessmentLead]
    ) -> List[Dict[str, Any]]:
        """Generate conversion opportunities based on assessment results."""
        opportunities = []

        if compliance_score < 60:
            opportunities.append({
                "type": "consultation",
                "title": "Free Compliance Consultation",
                "description": "Get expert guidance on addressing your compliance gaps",
                "urgency": "high",
                "cta_text": "Book Free Consultation"
            })

        if len(gaps_identified) > 3:
            opportunities.append({
                "type": "trial",
                "title": "14-Day Free Trial",
                "description": "Try our compliance platform to address identified gaps",
                "urgency": "medium",
                "cta_text": "Start Free Trial"
            })

        return opportunities

    async def _generate_results_summary(
        self,
        compliance_score: float,
        risk_level: str,
        recommendations: List[Dict[str, Any]],
        gaps_identified: List[Dict[str, Any]]
    ) -> str:
        """Generate a human-readable results summary."""
        summary_parts = [
            f"Your compliance score is {compliance_score}% with a {risk_level} risk level.",
            f"We identified {len(gaps_identified)} areas for improvement.",
            f"Our analysis includes {len(recommendations)} personalized recommendations."
        ]

        if compliance_score >= 80:
            summary_parts.append("Your organization demonstrates strong compliance practices.")
        elif compliance_score >= 60:
            summary_parts.append("Your compliance foundation is solid but can be strengthened.")
        else:
            summary_parts.append("Significant compliance improvements are recommended.")

        return " ".join(summary_parts)

    def _generate_next_steps(self, compliance_score: float, risk_level: str) -> List[str]:
        """Generate actionable next steps."""
        steps = []

        if compliance_score < 40:
            steps.extend([
                "Schedule a compliance consultation",
                "Prioritize high-risk areas identified",
                "Implement basic security controls"
            ])
        elif compliance_score < 70:
            steps.extend([
                "Review detailed recommendations",
                "Create implementation timeline",
                "Consider compliance platform trial"
            ])
        else:
            steps.extend([
                "Maintain current compliance practices",
                "Schedule periodic reviews",
                "Stay updated on regulatory changes"
            ])

        return steps

    async def _generate_answer_insights(self, question_id: str, answer: str) -> Dict[str, Any]:
        """Generate insights for a specific answer."""
        try:
            if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                insights = await self.assistant.analyze_specific_answer(
                    question_id=question_id,
                    answer=answer
                )
                return insights
            else:
                return {"insight": "Detailed insights are available with our full platform"}

        except Exception as e:
            logger.error(f"Error generating answer insights: {str(e)}")
            return {"insight": "Unable to generate insights at this time"}
