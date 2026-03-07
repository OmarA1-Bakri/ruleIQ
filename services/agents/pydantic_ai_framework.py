"""

# Constants
MAX_RETRIES = 3


Pydantic AI Agent Framework for ruleIQ
Implements intelligent agents with trust levels and RAG integration
"""

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from typing import Dict, Any, List, Optional, Literal
import logging
from datetime import datetime, timezone
from services.agentic_rag import AgenticRAGSystem

logger = logging.getLogger(__name__)


class AgentContext(BaseModel):
    """Context passed to agents during execution"""

    user_id: str
    session_id: str
    trust_level: int = Field(ge=0, le=3, description="Agent trust level (0-3)")
    business_context: Dict[str, Any] = Field(default_factory=dict)
    interaction_history: List[Dict[str, Any]] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Standard response from Pydantic AI agents"""

    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    trust_level_required: int = Field(ge=0, le=3)
    reasoning: str
    sources: List[str] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)
    requires_human_approval: bool = False


class ComplianceAgentResponse(AgentResponse):
    """Response from compliance-specific agents"""

    risk_level: Literal["low", "medium", "high", "critical"]
    compliance_gaps: List[str] = Field(default_factory=list)
    recommended_policies: List[str] = Field(default_factory=list)
    implementation_steps: List[str] = Field(default_factory=list)


class BaseComplianceAgent:
    """
    Base class for ruleIQ compliance agents with RAG integration

    Trust Levels:
    - Level 0: Observe and learn only
    - Level 1: Make suggestions with explanations
    - Level 2: Collaborate on decisions
    - Level 3: Take autonomous actions
    """

    def __init__(self, trust_level: int, rag_system: Optional[AgenticRAGSystem] = None) -> None:
        self.trust_level = trust_level
        self.rag_system = rag_system
        self.agent = Agent(
            "gemini-1.5-pro",
            result_type=ComplianceAgentResponse,
            system_prompt=self._build_system_prompt(),
        )

    def _build_system_prompt(self) -> str:
        """Build system prompt based on trust level and capabilities"""
        base_prompt = f"""
        You are a UK compliance agent operating at trust level {self.trust_level}.

        Trust Level Guidelines:
        - Level 0: Observe and learn only - provide insights but no actions
        - Level 1: Make suggestions with detailed explanations
        - Level 2: Collaborate on decisions - propose specific actions
        - Level 3: Take autonomous actions within defined boundaries

        Your expertise covers UK regulations including GDPR, Companies House requirements,
        employment law, data protection, and industry-specific compliance frameworks.

        Always provide:
        1. Clear recommendations appropriate to your trust level
        2. Confidence scores based on available information
        3. Reasoning for your recommendations
        4. Risk assessment (low/medium/high/critical)
        5. Next steps the user should consider
        """
        trust_level_specifics = {
            (
                0
            ): "Focus on observation and pattern identification. Avoid making specific recommendations.",
            (
                1
            ): "Provide detailed suggestions with explanations. Always explain why you recommend each action.",
            (
                2
            ): "Propose specific actions and collaborate on implementation. You can suggest concrete steps.",
            (
                3
            ): "Take autonomous actions within your defined scope. Be proactive but always explain your reasoning.",
        }
        return (
            base_prompt
            + f"""

Trust Level {self.trust_level} Specific Guidance:
{trust_level_specifics.get(self.trust_level, "")}"""
        )

    async def process_request(self, request: str, context: AgentContext) -> ComplianceAgentResponse:
        """Process a compliance request with RAG enhancement"""
        try:
            enhanced_request = await self._enhance_with_rag(request, context)
            result = await self.agent.run(enhanced_request, deps=context.model_dump())
            adjusted_result = self._adjust_response_for_trust_level(result, context)
            await self._log_interaction(request, adjusted_result, context)
            return adjusted_result
        except Exception as e:
            logger.error("Error in agent processing: %s" % e)
            return ComplianceAgentResponse(
                recommendation="I encountered an error processing your request. Please try again or contact support.",
                confidence=0.0,
                trust_level_required=1,
                reasoning=f"Error occurred during processing: {str(e)}",
                risk_level="medium",
                requires_human_approval=True,
            )

    async def _enhance_with_rag(self, request: str, context: AgentContext) -> str:
        """Enhance request with relevant knowledge from RAG system"""
        if not self.rag_system:
            return request
        try:
            rag_query = f"UK compliance guidance for: {request}"
            rag_result = await self.rag_system.query_documentation(
                query=rag_query, source_filter=None, query_type="hybrid", max_results=3
            )
            if rag_result.confidence > 0.3:
                enhanced_request = f"""
                User Request: {request}

                Relevant Compliance Knowledge:
                {rag_result.answer}

                Sources: {", ".join([s["id"] for s in rag_result.sources])}

                Please provide guidance considering both the user's specific request and the relevant compliance knowledge above.
                """
                return enhanced_request
        except Exception as e:
            logger.warning("RAG enhancement failed: %s" % e)
        return request

    def _adjust_response_for_trust_level(
        self, response: ComplianceAgentResponse, context: AgentContext
    ) -> ComplianceAgentResponse:
        """Adjust response appropriateness based on trust level"""
        if self.trust_level == 0:
            response.recommendation = (
                f"Based on my analysis, I observe that: {response.recommendation}",
            )
            response.requires_human_approval = True
            response.next_actions = ["Review these observations with a compliance expert"]
        elif self.trust_level == 1:
            if not response.recommendation.lower().startswith(
                ("i suggest", "consider", "you might", "i recommend")
            ):
                response.recommendation = f"I suggest: {response.recommendation}"
            response.requires_human_approval = True
        elif self.trust_level == 2:
            if response.risk_level in ["high", "critical"]:
                response.requires_human_approval = True
        elif self.trust_level == MAX_RETRIES:
            if response.risk_level == "critical":
                response.requires_human_approval = True
                response.next_actions.insert(0, "CRITICAL: Immediate human review required")
        return response

    async def _log_interaction(
        self, request: str, response: ComplianceAgentResponse, context: AgentContext
    ) -> None:
        """Log interaction for learning and audit purposes"""
        try:
            interaction_log = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": context.user_id,
                "session_id": context.session_id,
                "trust_level": self.trust_level,
                "request": request[:500],
                "response_summary": response.recommendation[:200],
                "confidence": response.confidence,
                "risk_level": response.risk_level,
                "required_approval": response.requires_human_approval,
            }
            context.interaction_history.append(interaction_log)
            if len(context.interaction_history) > 10:
                context.interaction_history = context.interaction_history[-10:]
        except Exception as e:
            logger.warning("Failed to log interaction: %s" % e)


class GDPRComplianceAgent(BaseComplianceAgent):
    """Specialized agent for GDPR compliance"""

    def _build_system_prompt(self) -> str:
        base_prompt = super()._build_system_prompt()
        gdpr_specifics = """

        GDPR Specialization:
        You are specifically trained on UK GDPR and data protection requirements.

        Key Areas of Expertise:
        - Data processing lawful basis assessment
        - Privacy impact assessments (PIAs)
        - Data subject rights (access, rectification, erasure, portability)
        - Data breach notification requirements
        - Cookie consent and tracking
        - International data transfers
        - Data retention policies
        - Privacy by design principles

        Always consider:
        - Proportionality of data processing
        - Legitimate interests vs. privacy rights
        - Technical and organizational measures
        - Documentation requirements under Article 30
        """
        return base_prompt + gdpr_specifics


class CompaniesHouseAgent(BaseComplianceAgent):
    """Specialized agent for Companies House compliance"""

    def _build_system_prompt(self) -> str:
        base_prompt = super()._build_system_prompt()
        companies_house_specifics = """

        Companies House Specialization:
        You are specifically trained on UK Companies House requirements and corporate compliance.

        Key Areas of Expertise:
        - Annual filing requirements (confirmation statements, accounts)
        - Director and shareholder obligations
        - Registered office requirements
        - Company name compliance
        - Share capital and allotment procedures
        - Statutory registers maintenance
        - Dissolution and strike-off procedures
        - Corporate governance requirements

        Always consider:
        - Filing deadlines and penalties
        - Public disclosure implications
        - Director disqualification risks
        - Dormant company provisions
        """
        return base_prompt + companies_house_specifics


class EmploymentLawAgent(BaseComplianceAgent):
    """Specialized agent for employment law compliance"""

    def _build_system_prompt(self) -> str:
        base_prompt = super()._build_system_prompt()
        employment_specifics = """

        Employment Law Specialization:
        You are specifically trained on UK employment law and workplace compliance.

        Key Areas of Expertise:
        - Employment contracts and terms
        - Working time regulations
        - Minimum wage compliance
        - Health and safety obligations
        - Discrimination and equality law
        - Disciplinary and grievance procedures
        - Redundancy and TUPE
        - Holiday and sick pay entitlements

        Always consider:
        - ACAS codes of practice
        - Tribunal risks and costs
        - Insurance implications
        - Trade union considerations
        """
        return base_prompt + employment_specifics


class AgentOrchestrator:
    """
    Orchestrates multiple specialized agents based on request type
    """

    def __init__(self, trust_level: int, rag_system: Optional[AgenticRAGSystem] = None) -> None:
        self.trust_level = trust_level
        self.rag_system = rag_system
        self.agents = {
            "gdpr": GDPRComplianceAgent(trust_level, rag_system),
            "companies_house": CompaniesHouseAgent(trust_level, rag_system),
            "employment": EmploymentLawAgent(trust_level, rag_system),
            "general": BaseComplianceAgent(trust_level, rag_system),
        }

    async def route_request(self, request: str, context: AgentContext) -> ComplianceAgentResponse:
        """Route request to appropriate specialized agent"""
        try:
            agent_type = self._classify_request(request)
            logger.info(
                "Routing request to %s agent (trust level %s)" % (agent_type, self.trust_level)
            )
            response = await self.agents[agent_type].process_request(request, context)
            response.sources.append(f"Processed by {agent_type} specialist agent")
            return response
        except Exception as e:
            logger.error("Error in agent orchestration: %s" % e)
            return await self.agents["general"].process_request(request, context)

    def _classify_request(self, request: str) -> str:
        """Classify request to determine appropriate specialist agent"""
        request_lower = request.lower()
        gdpr_keywords = [
            "gdpr",
            "data protection",
            "privacy",
            "consent",
            "personal data",
            "data subject",
            "data breach",
            "data transfer",
            "cookies",
            "tracking",
        ]
        companies_keywords = [
            "companies house",
            "filing",
            "accounts",
            "confirmation statement",
            "director",
            "shareholder",
            "registered office",
            "company name",
            "incorporation",
            "dissolution",
            "statutory",
        ]
        employment_keywords = [
            "employment",
            "employee",
            "worker",
            "contract",
            "payroll",
            "holiday",
            "sick pay",
            "minimum wage",
            "working time",
            "discrimination",
            "disciplinary",
            "redundancy",
            "tribunal",
        ]
        gdpr_score = sum(1 for keyword in gdpr_keywords if keyword in request_lower)
        companies_score = sum(1 for keyword in companies_keywords if keyword in request_lower)
        employment_score = sum(1 for keyword in employment_keywords if keyword in request_lower)
        scores = {
            "gdpr": gdpr_score,
            "companies_house": companies_score,
            "employment": employment_score,
        }
        max_score = max(scores.values())
        if max_score > 0:
            return max(scores, key=scores.get)
        return "general"


def create_compliance_agent(
    trust_level: int, agent_type: str = "general", rag_system: Optional[AgenticRAGSystem] = None
) -> BaseComplianceAgent:
    """Factory function to create specialized compliance agents"""
    agent_classes = {
        "gdpr": GDPRComplianceAgent,
        "companies_house": CompaniesHouseAgent,
        "employment": EmploymentLawAgent,
        "general": BaseComplianceAgent,
    }
    agent_class = agent_classes.get(agent_type, BaseComplianceAgent)
    return agent_class(trust_level, rag_system)


def create_agent_orchestrator(
    trust_level: int, rag_system: Optional[AgenticRAGSystem] = None
) -> AgentOrchestrator:
    """Factory function to create agent orchestrator"""
    return AgentOrchestrator(trust_level, rag_system)
