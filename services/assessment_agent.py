"""
Assessment Agent using LangGraph for conversational compliance assessments.

This module implements a stateful, conversational assessment agent that:
1. Maintains context throughout the assessment
2. Generates questions dynamically based on previous answers
3. Adapts difficulty and depth based on user expertise
4. Builds a compliance profile progressively

LangSmith tracing is integrated for observability:
- Set LANGCHAIN_TRACING_V2=true
- Set LANGCHAIN_API_KEY=your_api_key
- Set LANGCHAIN_PROJECT=ruleiq-assessment
"""

import os
import uuid
from typing import Dict, List, Optional, Any, TypedDict, Annotated
from enum import Enum

from langgraph.graph import StateGraph, add_messages
from langgraph.checkpoint import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tracers.context import tracing_v2_enabled
from langsmith import traceable

from services.ai.assistant import ComplianceAssistant
from services.ai.circuit_breaker import AICircuitBreaker
from config.logging_config import get_logger

logger = get_logger(__name__)


class AssessmentPhase(Enum):
    """Phases of the assessment conversation."""
    INTRODUCTION = "introduction"
    BUSINESS_CONTEXT = "business_context"
    COMPLIANCE_DISCOVERY = "compliance_discovery"
    DEEP_DIVE = "deep_dive"
    RISK_ASSESSMENT = "risk_assessment"
    RECOMMENDATIONS = "recommendations"
    COMPLETION = "completion"


class AssessmentState(TypedDict):
    """
    State for the assessment agent graph.
    Maintains all context throughout the assessment conversation.
    """
    # Conversation history
    messages: Annotated[List[Any], add_messages]

    # Session tracking
    session_id: str
    lead_id: str
    thread_id: str

    # Assessment progress
    current_phase: AssessmentPhase
    questions_asked: List[str]
    questions_answered: int
    total_questions_planned: int

    # Business context accumulation
    business_profile: Dict[str, Any]
    compliance_needs: List[str]
    identified_risks: List[Dict[str, Any]]

    # Dynamic question generation context
    next_question_context: Dict[str, Any]
    follow_up_needed: bool
    expertise_level: str  # beginner, intermediate, expert

    # Scoring and results
    compliance_score: float
    risk_level: str
    recommendations: List[Dict[str, Any]]
    gaps_identified: List[Dict[str, Any]]

    # Control flow
    should_continue: bool
    error_count: int
    fallback_mode: bool


class AssessmentAgent:
    """
    LangGraph-based conversational assessment agent.
    """

    def __init__(self, db_session):
        self.db = db_session
        self.assistant = ComplianceAssistant(db_session)
        self.circuit_breaker = AICircuitBreaker()
        self.checkpointer = MemorySaver()

        # Configuration
        self.MIN_QUESTIONS = 5
        self.MAX_QUESTIONS = 12
        self.CONFIDENCE_THRESHOLD = 0.7

        # Configure LangSmith tracing if enabled
        self._configure_tracing()

        # Build the graph
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=self.checkpointer)

    def _configure_tracing(self):
        """Configure LangSmith tracing for observability."""
        # Check if tracing is enabled via environment variables
        tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

        if tracing_enabled:
            # Ensure required environment variables are set
            api_key = os.getenv("LANGCHAIN_API_KEY")
            project = os.getenv("LANGCHAIN_PROJECT", "ruleiq-assessment")

            if not api_key:
                logger.warning("LANGCHAIN_TRACING_V2 is enabled but LANGCHAIN_API_KEY is not set")
                return

            # Set project name if not already set
            os.environ["LANGCHAIN_PROJECT"] = project

            logger.info(f"LangSmith tracing enabled for project: {project}")
            logger.info("Traces will be available at: https://smith.langchain.com")
        else:
            logger.debug("LangSmith tracing is disabled. Set LANGCHAIN_TRACING_V2=true to enable.")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph for assessment flow."""
        graph = StateGraph(AssessmentState)

        # Add nodes for each phase
        graph.add_node("introduction", self._introduction_node)
        graph.add_node("analyze_context", self._analyze_context_node)
        graph.add_node("generate_question", self._generate_question_node)
        graph.add_node("process_answer", self._process_answer_node)
        graph.add_node("determine_next", self._determine_next_node)
        graph.add_node("generate_results", self._generate_results_node)
        graph.add_node("completion", self._completion_node)

        # Define edges
        graph.set_entry_point("introduction")

        graph.add_edge("introduction", "generate_question")
        graph.add_edge("generate_question", "process_answer")
        graph.add_edge("process_answer", "analyze_context")
        graph.add_edge("analyze_context", "determine_next")

        # Conditional routing from determine_next
        graph.add_conditional_edges(
            "determine_next",
            self._route_next_step,
            {
                "continue": "generate_question",
                "complete": "generate_results",
                "error": "completion"
            }
        )

        graph.add_edge("generate_results", "completion")

        return graph

    async def _introduction_node(self, state: AssessmentState) -> AssessmentState:
        """Initialize the assessment with a friendly introduction."""
        intro_message = AIMessage(content="""
Hello! I'm IQ, your AI compliance assistant. I'm here to help you understand your compliance needs 
and identify areas where we can strengthen your compliance posture.

This assessment will be conversational - I'll ask you questions about your business and compliance 
practices, and based on your answers, I'll tailor my follow-up questions to get a complete picture 
of your needs.

Let's start with understanding your business context. What type of business do you operate, and 
what's your primary industry?
        """)

        state["messages"].append(intro_message)
        state["current_phase"] = AssessmentPhase.BUSINESS_CONTEXT
        state["questions_asked"].append("business_type_and_industry")

        return state

    async def _analyze_context_node(self, state: AssessmentState) -> AssessmentState:
        """Analyze accumulated context to understand the business better."""
        # Extract insights from conversation so far
        messages = state["messages"]

        # Use AI to analyze if available
        if self.circuit_breaker.is_model_available("gemini-2.5-flash") and not state["fallback_mode"]:
            try:
                analysis = await self.assistant.analyze_conversation_context(
                    messages=messages[-10:],  # Last 10 messages for context
                    business_profile=state["business_profile"]
                )

                # Update business profile with new insights
                state["business_profile"].update(analysis.get("insights", {}))

                # Identify compliance needs
                new_needs = analysis.get("compliance_needs", [])
                for need in new_needs:
                    if need not in state["compliance_needs"]:
                        state["compliance_needs"].append(need)

                # Determine expertise level from responses
                state["expertise_level"] = analysis.get("expertise_level", "intermediate")

                # Check if we need follow-up questions
                state["follow_up_needed"] = analysis.get("follow_up_needed", False)

            except Exception as e:
                logger.warning(f"Failed to analyze context with AI: {e}")
                state["fallback_mode"] = True

        # Fallback context analysis
        if state["fallback_mode"]:
            # Simple heuristic-based analysis
            recent_answer = messages[-1].content if messages else ""

            # Check answer length and detail for expertise
            if len(recent_answer) > 200:
                state["expertise_level"] = "expert"
            elif len(recent_answer) > 50:
                state["expertise_level"] = "intermediate"
            else:
                state["expertise_level"] = "beginner"

            # Simple keyword detection for compliance needs
            keywords = {
                "gdpr": ["personal data", "eu", "privacy", "gdpr"],
                "security": ["security", "breach", "cyber", "hack"],
                "iso": ["iso", "certification", "audit"],
                "data": ["data protection", "backup", "storage"]
            }

            answer_lower = recent_answer.lower()
            for need, terms in keywords.items():
                if any(term in answer_lower for term in terms):
                    if need not in state["compliance_needs"]:
                        state["compliance_needs"].append(need)

        return state

    @traceable(
        name="generate_question",
        tags=["node", "question_generation"],
        metadata={"node_type": "question_generator"}
    )
    async def _generate_question_node(self, state: AssessmentState) -> AssessmentState:
        """Generate the next question based on accumulated context."""
        # Determine question strategy based on phase and context
        phase = state["current_phase"]
        questions_answered = state["questions_answered"]

        # Try AI-powered question generation
        if self.circuit_breaker.is_model_available("gemini-2.5-flash") and not state["fallback_mode"]:
            try:
                # Build context for question generation
                context = {
                    "phase": phase.value,
                    "questions_asked": state["questions_asked"],
                    "business_profile": state["business_profile"],
                    "compliance_needs": state["compliance_needs"],
                    "expertise_level": state["expertise_level"],
                    "questions_answered": questions_answered,
                    "min_questions": self.MIN_QUESTIONS,
                    "max_questions": self.MAX_QUESTIONS
                }

                # Generate contextual question
                question_data = await self.assistant.generate_contextual_question(
                    context=context,
                    previous_messages=state["messages"][-6:]  # Last 3 Q&A pairs
                )

                if question_data:
                    question_text = question_data.get("question_text")
                    question_id = question_data.get("question_id", f"dyn_{uuid.uuid4().hex[:8]}")

                    # Add question to conversation
                    ai_message = AIMessage(
                        content=question_text,
                        additional_kwargs={
                            "question_id": question_id,
                            "question_type": question_data.get("question_type", "open"),
                            "phase": phase.value
                        }
                    )

                    state["messages"].append(ai_message)
                    state["questions_asked"].append(question_id)

                    # Update phase if suggested
                    if question_data.get("suggested_phase"):
                        new_phase = question_data["suggested_phase"]
                        if hasattr(AssessmentPhase, new_phase.upper()):
                            state["current_phase"] = AssessmentPhase[new_phase.upper()]

                    return state

            except Exception as e:
                logger.warning(f"Failed to generate AI question: {e}")
                state["fallback_mode"] = True

        # Fallback to predefined questions
        if state["fallback_mode"] or questions_answered >= self.MAX_QUESTIONS:
            question = self._get_fallback_question(state)
            if question:
                ai_message = AIMessage(
                    content=question["text"],
                    additional_kwargs={
                        "question_id": question["id"],
                        "question_type": "fallback",
                        "phase": phase.value
                    }
                )

                state["messages"].append(ai_message)
                state["questions_asked"].append(question["id"])

        return state

    async def _process_answer_node(self, state: AssessmentState) -> AssessmentState:
        """Process the user's answer and extract insights."""
        # This node would be triggered after receiving user input
        # For now, we'll simulate processing

        state["questions_answered"] += 1

        # Update progress
        progress = min(
            (state["questions_answered"] / self.MIN_QUESTIONS) * 100,
            100
        )

        # Extract key information from answer
        if state["messages"]:
            last_answer = state["messages"][-1]
            if isinstance(last_answer, HumanMessage):
                # Update business profile based on answer
                # This would use NLP/AI to extract structured data
                pass

        return state

    async def _determine_next_node(self, state: AssessmentState) -> AssessmentState:
        """Determine whether to continue with more questions or complete."""
        questions_answered = state["questions_answered"]

        # Check completion criteria
        if questions_answered >= self.MIN_QUESTIONS:
            # Check if we have enough information
            if self._has_sufficient_information(state):
                state["should_continue"] = False
            elif questions_answered >= self.MAX_QUESTIONS:
                state["should_continue"] = False
            else:
                # Continue if we need more information
                state["should_continue"] = True
        else:
            state["should_continue"] = True

        return state

    def _route_next_step(self, state: AssessmentState) -> str:
        """Route to the next appropriate node."""
        if state.get("error_count", 0) > 3:
            return "error"
        elif state["should_continue"]:
            return "continue"
        else:
            return "complete"

    async def _generate_results_node(self, state: AssessmentState) -> AssessmentState:
        """Generate comprehensive assessment results."""
        # Calculate compliance score
        state["compliance_score"] = self._calculate_compliance_score(state)

        # Determine risk level
        state["risk_level"] = self._determine_risk_level(state["compliance_score"])

        # Generate recommendations
        if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
            try:
                recommendations = await self.assistant.generate_recommendations(
                    business_profile=state["business_profile"],
                    compliance_needs=state["compliance_needs"],
                    identified_risks=state["identified_risks"],
                    compliance_score=state["compliance_score"]
                )
                state["recommendations"] = recommendations
            except Exception as e:
                logger.error(f"Failed to generate AI recommendations: {e}")
                state["recommendations"] = self._get_fallback_recommendations(state)
        else:
            state["recommendations"] = self._get_fallback_recommendations(state)

        return state

    async def _completion_node(self, state: AssessmentState) -> AssessmentState:
        """Complete the assessment with a summary."""
        summary_message = AIMessage(content=f"""
Thank you for completing the assessment! Here's what I've learned about your compliance needs:

**Compliance Score:** {state['compliance_score']:.1f}%
**Risk Level:** {state['risk_level']}

**Key Compliance Areas Identified:**
{self._format_list(state['compliance_needs'])}

**Top Recommendations:**
{self._format_recommendations(state['recommendations'][:3])}

Based on our conversation, I can see that your organization would benefit from a more structured 
approach to compliance management. Our platform can help automate many of these processes and 
ensure you stay compliant with minimal effort.

Would you like to schedule a demo to see how we can help address your specific needs?
        """)

        state["messages"].append(summary_message)
        state["current_phase"] = AssessmentPhase.COMPLETION

        return state

    def _has_sufficient_information(self, state: AssessmentState) -> bool:
        """Check if we have enough information to generate meaningful results."""
        # Check key information points
        has_business_type = bool(state["business_profile"].get("business_type"))
        has_company_size = bool(state["business_profile"].get("company_size"))
        has_compliance_needs = len(state["compliance_needs"]) > 0
        has_enough_answers = state["questions_answered"] >= self.MIN_QUESTIONS

        return all([has_business_type, has_company_size, has_compliance_needs, has_enough_answers])

    def _calculate_compliance_score(self, state: AssessmentState) -> float:
        """Calculate compliance score based on answers."""
        base_score = 50.0

        # Adjust based on identified risks
        risk_penalty = len(state["identified_risks"]) * 5
        base_score -= risk_penalty

        # Adjust based on compliance needs addressed
        needs_bonus = len(state["compliance_needs"]) * 3
        base_score += needs_bonus

        # Adjust based on expertise level
        expertise_bonus = {
            "beginner": -10,
            "intermediate": 0,
            "expert": 10
        }.get(state["expertise_level"], 0)

        base_score += expertise_bonus

        # Ensure score is within bounds
        return max(0, min(100, base_score))

    def _determine_risk_level(self, score: float) -> str:
        """Determine risk level based on compliance score."""
        if score >= 80:
            return "low"
        elif score >= 60:
            return "medium"
        elif score >= 40:
            return "high"
        else:
            return "critical"

    def _get_fallback_question(self, state: AssessmentState) -> Optional[Dict[str, Any]]:
        """Get a fallback question when AI is unavailable."""
        fallback_questions = {
            AssessmentPhase.BUSINESS_CONTEXT: [
                {"id": "fb_biz_1", "text": "How many employees does your organization have?"},
                {"id": "fb_biz_2", "text": "Do you operate in multiple countries or just domestically?"},
                {"id": "fb_biz_3", "text": "What are your main products or services?"}
            ],
            AssessmentPhase.COMPLIANCE_DISCOVERY: [
                {"id": "fb_comp_1", "text": "Do you currently follow any compliance frameworks (like ISO, SOC 2, GDPR)?"},
                {"id": "fb_comp_2", "text": "Have you had any compliance audits in the past year?"},
                {"id": "fb_comp_3", "text": "Do you handle sensitive customer data like payment information or health records?"}
            ],
            AssessmentPhase.RISK_ASSESSMENT: [
                {"id": "fb_risk_1", "text": "Have you experienced any security incidents or data breaches?"},
                {"id": "fb_risk_2", "text": "How do you currently manage access to sensitive systems?"},
                {"id": "fb_risk_3", "text": "Do you have a documented incident response plan?"}
            ]
        }

        phase_questions = fallback_questions.get(state["current_phase"], [])

        # Find a question that hasn't been asked yet
        for question in phase_questions:
            if question["id"] not in state["questions_asked"]:
                return question

        # If all questions in current phase are asked, move to next phase
        phase_order = [
            AssessmentPhase.BUSINESS_CONTEXT,
            AssessmentPhase.COMPLIANCE_DISCOVERY,
            AssessmentPhase.RISK_ASSESSMENT
        ]

        current_index = phase_order.index(state["current_phase"]) if state["current_phase"] in phase_order else 0

        if current_index < len(phase_order) - 1:
            state["current_phase"] = phase_order[current_index + 1]
            return self._get_fallback_question(state)

        return None

    def _get_fallback_recommendations(self, state: AssessmentState) -> List[Dict[str, Any]]:
        """Get fallback recommendations when AI is unavailable."""
        score = state["compliance_score"]

        if score < 40:
            return [
                {
                    "priority": "high",
                    "title": "Implement Basic Compliance Framework",
                    "description": "Start with ISO 27001 basics to establish foundational security controls"
                },
                {
                    "priority": "high",
                    "title": "Conduct Risk Assessment",
                    "description": "Identify and document your key compliance risks and vulnerabilities"
                },
                {
                    "priority": "medium",
                    "title": "Develop Security Policies",
                    "description": "Create and document essential security and data protection policies"
                }
            ]
        elif score < 70:
            return [
                {
                    "priority": "medium",
                    "title": "Enhance Current Controls",
                    "description": "Strengthen existing compliance measures and fill identified gaps"
                },
                {
                    "priority": "medium",
                    "title": "Implement Monitoring",
                    "description": "Set up continuous compliance monitoring and alerting"
                },
                {
                    "priority": "low",
                    "title": "Prepare for Certification",
                    "description": "Work towards formal compliance certification"
                }
            ]
        else:
            return [
                {
                    "priority": "low",
                    "title": "Maintain Excellence",
                    "description": "Continue regular reviews and updates to maintain high compliance standards"
                },
                {
                    "priority": "low",
                    "title": "Automate Processes",
                    "description": "Look for opportunities to automate compliance workflows"
                }
            ]

    def _format_list(self, items: List[str]) -> str:
        """Format a list for display."""
        if not items:
            return "- No specific areas identified yet"
        return "\n".join(f"- {item}" for item in items)

    def _format_recommendations(self, recommendations: List[Dict[str, Any]]) -> str:
        """Format recommendations for display."""
        if not recommendations:
            return "- No recommendations available"

        formatted = []
        for rec in recommendations:
            priority = rec.get("priority", "medium")
            title = rec.get("title", "Recommendation")
            desc = rec.get("description", "")
            formatted.append(f"- **[{priority.upper()}]** {title}: {desc}")

        return "\n".join(formatted)

    @traceable(
        name="start_assessment",
        tags=["langgraph", "assessment", "freemium"],
        metadata={"agent": "AssessmentAgent", "action": "start"}
    )
    async def start_assessment(
        self,
        session_id: str,
        lead_id: str,
        initial_context: Dict[str, Any]
    ) -> AssessmentState:
        """
        Start a new assessment session using LangGraph.
        
        Args:
            session_id: Unique session identifier
            lead_id: Lead identifier
            initial_context: Initial business context
            
        Returns:
            Initial assessment state
        """
        # Create initial state
        initial_state = AssessmentState(
            messages=[],
            session_id=session_id,
            lead_id=lead_id,
            thread_id=f"thread_{session_id}",
            current_phase=AssessmentPhase.INTRODUCTION,
            questions_asked=[],
            questions_answered=0,
            total_questions_planned=self.MIN_QUESTIONS,
            business_profile=initial_context,
            compliance_needs=[],
            identified_risks=[],
            next_question_context={},
            follow_up_needed=False,
            expertise_level="intermediate",
            compliance_score=0.0,
            risk_level="unknown",
            recommendations=[],
            gaps_identified=[],
            should_continue=True,
            error_count=0,
            fallback_mode=not self.circuit_breaker.is_model_available("gemini-2.5-flash")
        )

        # Run the introduction node with tracing context
        config = {"configurable": {"thread_id": initial_state["thread_id"]}}

        with tracing_v2_enabled(
            project_name=os.getenv("LANGCHAIN_PROJECT", "ruleiq-assessment"),
            tags=["assessment_start", f"session:{session_id}"],
            metadata={"lead_id": lead_id, "initial_context": initial_context}
        ):
            result = await self.app.ainvoke(initial_state, config)

        return result

    @traceable(
        name="process_user_response",
        tags=["langgraph", "assessment", "freemium"],
        metadata={"agent": "AssessmentAgent", "action": "process_response"}
    )
    async def process_user_response(
        self,
        session_id: str,
        user_response: str,
        confidence: Optional[str] = None
    ) -> AssessmentState:
        """
        Process a user response and continue the assessment.
        
        Args:
            session_id: Session identifier
            user_response: User's answer to the question
            confidence: User's confidence level
            
        Returns:
            Updated assessment state
        """
        # Get current state from checkpointer
        config = {"configurable": {"thread_id": f"thread_{session_id}"}}

        # Add user message to state
        user_message = HumanMessage(
            content=user_response,
            additional_kwargs={"confidence": confidence}
        )

        # Continue graph execution with tracing context
        with tracing_v2_enabled(
            project_name=os.getenv("LANGCHAIN_PROJECT", "ruleiq-assessment"),
            tags=["assessment_response", f"session:{session_id}"],
            metadata={
                "response_length": len(user_response),
                "confidence": confidence,
                "session_id": session_id
            }
        ):
            result = await self.app.ainvoke(
                {"messages": [user_message]},
                config
            )

        return result
