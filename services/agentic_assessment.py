"""
Agentic Assessment Service

Transforms traditional static assessments into conversational, context-aware interactions
that build relationships and learn from user behavior patterns.

Features:
- Conversational assessment flow instead of static forms
- Context continuity across sessions
- Personalized questioning based on user patterns
- Trust-based automation of routine assessments
- Proactive compliance gap identification

Part of the ruleIQ Agentic Transformation Vision 2025
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from services.context_service import (
    get_context_service,
    InteractionType,
    TrustLevel,
    CommunicationStyle,
)
from services.assessment_service import AssessmentService
from services.ai import ComplianceAssistant

logger = logging.getLogger(__name__)


class ConversationState(str, Enum):
    #     STARTING = "starting"  # Unused variable
    #     GATHERING_CONTEXT = "gathering_context"  # Unused variable
    #     ASKING_QUESTIONS = "asking_questions"  # Unused variable
    #     CLARIFYING = "clarifying"  # Unused variable
    #     SUMMARIZING = "summarizing"  # Unused variable
    #     COMPLETED = "completed"  # Unused variable
    #     PAUSED = "paused"  # Unused variable

    """Conversation states"""

    INITIAL = "initial"
    GATHERING = "gathering"
    COMPLETE = "complete"


class QuestionType(str, Enum):
    BASIC_INFO = "basic_info"
    COMPLIANCE_SPECIFIC = "compliance_specific"
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    VERIFICATION = "verification"


@dataclass
class ConversationalQuestion:
    """A question in the conversational assessment flow"""

    id: str
    question_text: str
    question_type: QuestionType
    framework_area: str
    required: bool = True
    follow_up_conditions: Optional[Dict[str, Any]] = None
    personalization_context: Optional[Dict[str, Any]] = None
    trust_level_required: TrustLevel = TrustLevel.UNKNOWN


@dataclass
class AssessmentConversation:
    """State of an ongoing assessment conversation"""

    session_id: str
    user_id: str
    business_profile_id: str
    conversation_state: ConversationState
    current_question: Optional[ConversationalQuestion]
    answered_questions: List[Dict[str, Any]]
    pending_clarifications: List[str]
    context_gathered: Dict[str, Any]
    trust_signals: List[str]
    personalization_data: Dict[str, Any]
    started_at: datetime
    last_activity: datetime
    estimated_completion: float  # 0-1 progress


class AgenticAssessmentService:
    """
    Service that provides agentic, conversational assessments

    This service transforms the traditional static assessment process into
    an ongoing conversation that:
    1. Adapts to user communication style and preferences
    2. Remembers context from previous assessments
    3. Asks personalized follow-up questions
    4. Builds trust through transparent reasoning
    5. Automates routine parts for trusted users
    """

    def __init__(self) -> None:
        self.context_service = None
        self.assessment_service = AssessmentService()
        self.llm_service = ComplianceAssistant()
        self._conversation_templates = self._load_conversation_templates()

    async def initialize(self) -> None:
        """Initialize the agentic assessment service"""
        try:
            self.context_service = await get_context_service()
            logger.info("Agentic assessment service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize agentic assessment service: {e}")
            raise

    async def start_conversational_assessment(
        self,
        user_id: str,
        business_profile_id: str,
        session_id: str,
        framework_types: List[str],
        resume_previous: bool = False,
    ) -> Dict[str, Any]:
        """
        Start a new conversational assessment or resume an existing one

        Args:
            user_id: User identifier
            business_profile_id: Business profile to assess
            session_id: Session identifier
            framework_types: List of frameworks to assess (ISO27001, GDPR, etc.)
            resume_previous: Whether to resume a previous incomplete assessment

        Returns:
            Dict containing conversation state and first question
        """
        try:
            # Get user patterns for personalization
            user_patterns = await self.context_service.retrieve_user_patterns(user_id)

            # Check for resumable assessment if requested
            if resume_previous:
                existing_conversation = await self._get_resumable_conversation(user_id)
                if existing_conversation:
                    return await self._resume_conversation(
                        existing_conversation,
                        session_id,
                    )

            # Start new conversation
            conversation = AssessmentConversation(
                session_id=session_id,
                user_id=user_id,
                business_profile_id=business_profile_id,
                conversation_state=ConversationState.STARTING,
                current_question=None,
                answered_questions=[],
                pending_clarifications=[],
                context_gathered={
                    "framework_types": framework_types,
                    "user_patterns": asdict(user_patterns) if user_patterns else None,
                },
                trust_signals=[],
                personalization_data={},
                started_at=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc),
                estimated_completion=0.0,
            )

            # Store conversation state
            await self._store_conversation(conversation)

            # Record interaction
            await self.context_service.store_interaction_context(
                user_id=user_id,
                interaction_type=InteractionType.ASSESSMENT_START,
                context={
                    "framework_types": framework_types,
                    "session_id": session_id,
                    "business_profile_id": business_profile_id,
                },
                session_id=session_id,
            )

            # Generate personalized opening
            opening_message = await self._generate_personalized_opening(
                user_patterns,
                framework_types,
            )

            # Get first question
            first_question = await self._get_next_question(conversation)
            conversation.current_question = first_question
            conversation.conversation_state = ConversationState.GATHERING_CONTEXT

            await self._store_conversation(conversation)

            return {
                "conversation_id": session_id,
                "state": conversation.conversation_state,
                "opening_message": opening_message,
                "current_question": asdict(first_question) if first_question else None,
                "progress": conversation.estimated_completion,
                "personalization": {
                    "trust_level": (
                        user_patterns.trust_level if user_patterns else TrustLevel.UNKNOWN,
                    ),
                    "communication_style": (
                        user_patterns.communication_style
                        if user_patterns
                        else CommunicationStyle.FORMAL,
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Failed to start conversational assessment: {e}")
            raise

    async def process_conversation_response(
        self,
        session_id: str,
        user_response: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process user response in the conversation and determine next action

        Args:
            session_id: Session identifier
            user_response: User's response to current question
            additional_context: Optional additional context

        Returns:
            Dict containing next question or conversation completion
        """
        try:
            # Get conversation state
            conversation = await self._get_conversation(session_id)
            if not conversation:
                raise ValueError(
                    f"No active conversation found for session {session_id}",
                )

            # Process the response
            processed_response = await self._process_response(
                conversation,
                user_response,
                additional_context or {},
            )

            # Record the response
            conversation.answered_questions.append(
                {
                    "question_id": conversation.current_question.id,
                    "question_text": conversation.current_question.question_text,
                    "response": user_response,
                    "processed_response": processed_response,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "additional_context": additional_context,
                },
            )

            # Analyze response for trust signals
            trust_signals = await self._analyze_trust_signals(
                user_response,
                processed_response,
            )
            conversation.trust_signals.extend(trust_signals)

            # Update context and personalization
            await self._update_conversation_context(conversation, processed_response)

            # Determine next action
            next_action = await self._determine_next_action(conversation)

            # Update conversation state
            conversation.last_activity = datetime.now(timezone.utc)
            conversation.estimated_completion = len(
                conversation.answered_questions
            ) / self._estimate_total_questions(conversation)

            if next_action["action"] == "ask_question":
                conversation.current_question = next_action["question"]
                conversation.conversation_state = ConversationState.ASKING_QUESTIONS
            elif next_action["action"] == "clarify":
                conversation.conversation_state = ConversationState.CLARIFYING
                conversation.pending_clarifications.extend(
                    next_action.get("clarifications", []),
                )
            elif next_action["action"] == "complete":
                conversation.conversation_state = ConversationState.COMPLETED
                # Generate final assessment
                assessment_result = await self._generate_final_assessment(conversation)
                next_action["assessment_result"] = assessment_result

            await self._store_conversation(conversation)

            # Record interaction
            await self.context_service.store_interaction_context(
                user_id=conversation.user_id,
                interaction_type=InteractionType.ASSESSMENT_CONTINUE,
                context={
                    "response_processed": True,
                    "question_id": (
                        conversation.current_question.id if conversation.current_question else None,
                    ),
                    "progress": conversation.estimated_completion,
                },
                session_id=session_id,
            )

            return {
                "conversation_id": session_id,
                "state": conversation.conversation_state,
                "progress": conversation.estimated_completion,
                "next_action": next_action,
                "trust_signals": trust_signals,
                "estimated_remaining_time": self._estimate_remaining_time(conversation),
            }

        except Exception as e:
            logger.error(f"Failed to process conversation response: {e}")
            raise

    async def pause_conversation(self, session_id: str) -> Dict[str, Any]:
        """Pause an ongoing conversation for later resumption"""
        try:
            conversation = await self._get_conversation(session_id)
            if not conversation:
                raise ValueError(
                    f"No active conversation found for session {session_id}",
                )

            conversation.conversation_state = ConversationState.PAUSED
            conversation.last_activity = datetime.now(timezone.utc)

            await self._store_conversation(conversation)

            # Record interaction
            await self.context_service.store_interaction_context(
                user_id=conversation.user_id,
                interaction_type=InteractionType.ASSESSMENT_CONTINUE,
                context={
                    "action": "paused",
                    "progress": conversation.estimated_completion,
                },
                session_id=session_id,
            )

            return {
                "conversation_id": session_id,
                "state": conversation.conversation_state,
                "progress": conversation.estimated_completion,
                "message": "Conversation paused. You can resume anytime.",
                "resume_context": {
                    "current_question": (
                        asdict(conversation.current_question)
                        if conversation.current_question
                        else None,
                    ),
                    "progress": conversation.estimated_completion,
                },
            }

        except Exception as e:
            logger.error(f"Failed to pause conversation: {e}")
            raise

    async def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of the current conversation state"""
        try:
            conversation = await self._get_conversation(session_id)
            if not conversation:
                raise ValueError(f"No conversation found for session {session_id}")

            summary = {
                "conversation_id": session_id,
                "state": conversation.conversation_state,
                "progress": conversation.estimated_completion,
                "started_at": conversation.started_at.isoformat(),
                "last_activity": conversation.last_activity.isoformat(),
                "questions_answered": len(conversation.answered_questions),
                "estimated_total_questions": self._estimate_total_questions(
                    conversation,
                ),
                "framework_types": conversation.context_gathered.get(
                    "framework_types",
                    [],
                ),
                "trust_signals_count": len(conversation.trust_signals),
                "current_question": (
                    asdict(conversation.current_question)
                    if conversation.current_question
                    else None,
                ),
            }

            if conversation.conversation_state == ConversationState.COMPLETED:
                summary["completion_timestamp"] = conversation.last_activity.isoformat()

            return summary

        except Exception as e:
            logger.error(f"Failed to get conversation summary: {e}")
            raise

    async def _generate_personalized_opening(
        self, user_patterns: Optional[Any], framework_types: List[str]
    ) -> str:
        """Generate a personalized opening message based on user patterns"""
        try:
            if not user_patterns:
                return (
                    f"I'll help you complete your {', '.join(framework_types)} compliance "
                    "assessment. Let's start with some questions about your business.",
                )

            # Personalize based on communication style
            if user_patterns.communication_style == CommunicationStyle.CASUAL:
                greeting = "Hi! Ready to tackle your compliance assessment?"
            elif user_patterns.communication_style == CommunicationStyle.TECHNICAL:
                greeting = (
                    f"Let's conduct a comprehensive {', '.join(framework_types)} "
                    "compliance evaluation.",
                )
            else:
                greeting = (
                    f"Good day. I'll assist you with your {', '.join(framework_types)} "
                    "compliance assessment.",
                )

            # Add trust-based context
            if user_patterns.trust_level in [
                TrustLevel.TRUSTING,
                TrustLevel.DELEGATING,
            ]:
                trust_context = (
                    " Based on your profile, I can streamline some routine questions.",
                )
            else:
                trust_context = " I'll explain each step as we go."

            # Add previous context if available
            if "assessment" in user_patterns.common_tasks:
                experience_context = (
                    " I see you've done assessments before, so we can focus on any changes "
                    "since last time.",
                )
            else:
                experience_context = (
                    " This assessment will help identify your compliance requirements.",
                )

            return greeting + trust_context + experience_context

        except Exception as e:
            logger.error(f"Failed to generate personalized opening: {e}")
            return (f"Let's start your {', '.join(framework_types)} compliance assessment.",)

    async def _get_next_question(
        self, conversation: AssessmentConversation
    ) -> Optional[ConversationalQuestion]:
        """Get the next appropriate question based on conversation context"""
        try:
            # Determine question type needed
            if conversation.conversation_state == ConversationState.GATHERING_CONTEXT:
                question_type = QuestionType.BASIC_INFO
            else:
                question_type = QuestionType.COMPLIANCE_SPECIFIC

            # Get framework-specific questions
            framework_types = conversation.context_gathered.get("framework_types", [])
            answered_question_ids = [q["question_id"] for q in conversation.answered_questions]

            # Find appropriate question from templates
            for framework in framework_types:
                questions = self._conversation_templates.get(framework, {}).get(
                    question_type.value,
                    [],
                )
                for q_data in questions:
                    if q_data["id"] not in answered_question_ids:
                        # Check if question is appropriate for user's trust level
                        user_patterns = conversation.context_gathered.get(
                            "user_patterns",
                        )
                        user_trust = TrustLevel.UNKNOWN
                        if user_patterns:
                            user_trust = TrustLevel(
                                user_patterns.get("trust_level", TrustLevel.UNKNOWN),
                            )

                        required_trust = TrustLevel(
                            q_data.get("trust_level_required", TrustLevel.UNKNOWN),
                        )
                        if self._trust_level_sufficient(user_trust, required_trust):
                            return ConversationalQuestion(**q_data)

            return None

        except Exception as e:
            logger.error(f"Failed to get next question: {e}")
            return None

    def _load_conversation_templates(self) -> Dict[str, Any]:
        """Load conversation templates for different frameworks"""
        # This would typically load from a file or database
        # For now, return a basic template structure
        return {
            "ISO27001": {
                "basic_info": [
                    {
                        "id": "iso_company_size",
                        "question_text": "How many employees does your organization have?",
                        "question_type": "basic_info",
                        "framework_area": "scope",
                        "required": True,
                        "trust_level_required": "unknown",
                    },
                    {
                        "id": "iso_industry_type",
                        "question_text": "What industry sector does your business operate in?",
                        "question_type": "basic_info",
                        "framework_area": "context",
                        "required": True,
                        "trust_level_required": "unknown",
                    },
                ],
                "compliance_specific": [
                    {
                        "id": "iso_information_assets",
                        "question_text": "What types of sensitive information does your organization handle?",
                        "question_type": "compliance_specific",
                        "framework_area": "asset_management",
                        "required": True,
                        "trust_level_required": "unknown",
                    },
                ],
            },
            "GDPR": {
                "basic_info": [
                    {
                        "id": "gdpr_data_processing",
                        "question_text": "Do you process personal data of EU residents?",
                        "question_type": "basic_info",
                        "framework_area": "scope",
                        "required": True,
                        "trust_level_required": "unknown",
                    },
                ],
                "compliance_specific": [
                    {
                        "id": "gdpr_data_categories",
                        "question_text": "What categories of personal data do you process?",
                        "question_type": "compliance_specific",
                        "framework_area": "data_processing",
                        "required": True,
                        "trust_level_required": "unknown",
                    },
                ],
            },
        }

    async def _process_response(
        self,
        conversation: AssessmentConversation,
        user_response: str,
        additional_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process and validate user response"""
        try:
            # Use LLM to extract structured data from natural language response
            current_question = conversation.current_question
            if not current_question:
                return {"raw_response": user_response}

            # Create prompt for LLM to extract structured data
            extraction_prompt = f"""
            Extract structured information from this user response to the compliance question.

            Question: {current_question.question_text}
            Framework Area: {current_question.framework_area}
            User Response: {user_response}

            Please extract:
            1. The main answer/value
            2. Any additional details mentioned
            3. Confidence level in the response (high/medium/low)
            4. Whether clarification might be needed

            Return as JSON.
            """

            llm_result = await self.llm_service.process_text(
                extraction_prompt,
                temperature=0.1,  # Low temperature for structured extraction,
            )

            try:
                structured_data = json.loads(llm_result)
            except json.JSONDecodeError:
                # Fallback to basic processing
                structured_data = {
                    "main_answer": user_response,
                    "confidence": "medium",
                    "needs_clarification": False,
                }

            return {
                "raw_response": user_response,
                "structured_data": structured_data,
                "additional_context": additional_context,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to process response: {e}")
            return {"raw_response": user_response, "error": str(e)}

    async def _analyze_trust_signals(
        self, user_response: str, processed_response: Dict[str, Any]
    ) -> List[str]:
        """Analyze response for trust-building signals"""
        trust_signals = []

        # Analyze response completeness
        if len(user_response.strip()) > 50:
            trust_signals.append("detailed_response")

        # Check for proactive information sharing
        if any(
            keyword in user_response.lower() for keyword in ["also", "additionally", "furthermore"]
        ):
            trust_signals.append("proactive_disclosure")

        # Check for questions about process
        if "?" in user_response:
            trust_signals.append("engaged_inquiry")

        # Check structured data confidence
        structured_data = processed_response.get("structured_data", {})
        if structured_data.get("confidence") == "high":
            trust_signals.append("confident_response")

        return trust_signals

    async def _determine_next_action(self, conversation: AssessmentConversation) -> Dict[str, Any]:
        """Determine what action to take next in the conversation"""
        try:
            # Check if we need clarification on last response
            if conversation.pending_clarifications:
                return {
                    "action": "clarify",
                    "clarifications": conversation.pending_clarifications,
                }

            # Check if we have enough information to complete
            conversation.context_gathered.get("framework_types", [])
            total_questions_needed = self._estimate_total_questions(conversation)
            answered_count = len(conversation.answered_questions)

            if answered_count >= total_questions_needed:
                return {"action": "complete"}

            # Get next question
            next_question = await self._get_next_question(conversation)
            if next_question:
                return {"action": "ask_question", "question": next_question}
            else:
                # No more questions available, complete assessment
                return {"action": "complete"}

        except Exception as e:
            logger.error(f"Failed to determine next action: {e}")
            return {"action": "complete"}  # Default to completion on error

    def _estimate_total_questions(self, conversation: AssessmentConversation) -> int:
        """Estimate total questions needed based on frameworks and context"""
        framework_types = conversation.context_gathered.get("framework_types", [])

        # Base questions per framework
        base_questions = {"ISO27001": 8, "GDPR": 6, "SOC2": 7}

        total = sum(base_questions.get(framework, 5) for framework in framework_types)

        # Adjust based on user patterns
        user_patterns = conversation.context_gathered.get("user_patterns")
        if user_patterns and user_patterns.get("trust_level") in [
            "trusting",
            "delegating",
        ]:
            total = int(total * 0.8)  # Reduce questions for trusted users

        return max(3, total)  # Minimum 3 questions

    def _estimate_remaining_time(self, conversation: AssessmentConversation) -> int:
        """Estimate remaining time in minutes"""
        total_questions = self._estimate_total_questions(conversation)
        remaining_questions = total_questions - len(conversation.answered_questions)

        # Estimate 2-3 minutes per question on average
        return max(1, remaining_questions * 2.5)

    def _trust_level_sufficient(self, user_trust: TrustLevel, required_trust: TrustLevel) -> bool:
        """Check if user's trust level meets the requirement for a question"""
        trust_order = [
            TrustLevel.UNKNOWN,
            TrustLevel.SKEPTICAL,
            TrustLevel.CAUTIOUS,
            TrustLevel.TRUSTING,
            TrustLevel.DELEGATING,
        ]

        user_index = trust_order.index(user_trust) if user_trust in trust_order else 0
        required_index = (
            trust_order.index(required_trust) if required_trust in trust_order else 0,
        )

        return user_index >= required_index

    async def _store_conversation(self, conversation: AssessmentConversation) -> None:
        """Store conversation state in context service"""
        await self.context_service.update_session_context(
            conversation.session_id,
            {"agentic_assessment": asdict(conversation)},
        )

    async def _get_conversation(self, session_id: str) -> Optional[AssessmentConversation]:
        """Retrieve conversation state from context service"""
        session_context = await self.context_service.get_session_context(session_id)
        if session_context and "agentic_assessment" in session_context.conversation_state:
            data = session_context.conversation_state["agentic_assessment"]
            # Convert datetime strings back to datetime objects
            data["started_at"] = datetime.fromisoformat(data["started_at"])
            data["last_activity"] = datetime.fromisoformat(data["last_activity"])
            if data.get("current_question"):
                data["current_question"] = ConversationalQuestion(
                    **data["current_question"],
                )
            return AssessmentConversation(**data)
        return None

    async def _resume_conversation(
        self, conversation: AssessmentConversation, new_session_id: str
    ) -> Dict[str, Any]:
        """Resume a paused conversation with a new session"""
        conversation.session_id = new_session_id
        conversation.conversation_state = ConversationState.ASKING_QUESTIONS
        conversation.last_activity = datetime.now(timezone.utc)

        await self._store_conversation(conversation)

        return {
            "conversation_id": new_session_id,
            "state": conversation.conversation_state,
            "current_question": (
                asdict(conversation.current_question) if conversation.current_question else None,
            ),
            "progress": conversation.estimated_completion,
            "message": "Welcome back! Let's continue where we left off.",
        }

    async def _get_resumable_conversation(self, user_id: str) -> Optional[AssessmentConversation]:
        """Find a resumable conversation for the user"""
        # This would query for paused conversations
        # For now, return None (no resumable conversations)
        return None

    async def _generate_final_assessment(
        self, conversation: AssessmentConversation
    ) -> Dict[str, Any]:
        """Generate the final assessment result from conversation"""
        try:
            # Record completion
            await self.context_service.store_interaction_context(
                user_id=conversation.user_id,
                interaction_type=InteractionType.ASSESSMENT_COMPLETE,
                context={
                    "questions_answered": len(conversation.answered_questions),
                    "framework_types": conversation.context_gathered.get(
                        "framework_types",
                        [],
                    ),
                    "trust_signals_collected": len(conversation.trust_signals),
                },
                session_id=conversation.session_id,
            )

            # Update trust score based on completion
            await self.context_service.update_trust_score(
                conversation.user_id,
                {
                    "task_completed_successfully": True,
                    "engagement_level": (
                        "high" if len(conversation.trust_signals) > 3 else "medium",
                    ),
                },
            )

            return {
                "assessment_id": f"conv_{conversation.session_id}",
                "completion_timestamp": datetime.now(timezone.utc).isoformat(),
                "questions_answered": len(conversation.answered_questions),
                "frameworks_assessed": conversation.context_gathered.get(
                    "framework_types",
                    [],
                ),
                "trust_signals_collected": conversation.trust_signals,
                "personalization_applied": bool(conversation.personalization_data),
                "next_steps": [
                    "Review findings",
                    "Generate policies",
                    "Schedule follow-up",
                ],
            }

        except Exception as e:
            logger.error(f"Failed to generate final assessment: {e}")
            return {"error": str(e)}

    async def _update_conversation_context(
        self, conversation: AssessmentConversation, processed_response: Dict[str, Any]
    ) -> None:
        """Update conversation context with new information"""
        # Extract business context from responses
        structured_data = processed_response.get("structured_data", {})

        # Update context based on question area
        if conversation.current_question:
            area = conversation.current_question.framework_area
            if area not in conversation.context_gathered:
                conversation.context_gathered[area] = {}

            conversation.context_gathered[area][conversation.current_question.id] = structured_data


# Global service instance
_agentic_assessment_service = None


async def get_agentic_assessment_service() -> AgenticAssessmentService:
    """Get or create the agentic assessment service instance"""
    global _agentic_assessment_service
    if _agentic_assessment_service is None:
        _agentic_assessment_service = AgenticAssessmentService()
        await _agentic_assessment_service.initialize()
    return _agentic_assessment_service
