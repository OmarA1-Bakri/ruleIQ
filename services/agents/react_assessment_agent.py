"""
Enhanced Assessment Agent with ReAct Architecture implementing ComplianceAgent protocol.

This module provides a ReAct-based assessment agent that follows the standard
ComplianceAgent protocol for consistency across the system.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import time

from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from services.agents.protocols import (
    ComplianceAgent,
    ComplianceContext,
    ComplianceResponse,
    ResponseStatus,
    AgentMetadata,
    AgentCapability
)
from services.agents.repositories import (
    ComplianceRepository,
    EvidenceRepository,
    BusinessProfileRepository
)
from services.agents.services import (
    RiskAnalysisService,
    CompliancePlanService,
    EvidenceVerificationService
)
from config.logging_config import get_logger

logger = get_logger(__name__)


class ReactComplianceTools:
    """Tools for ReAct agent to interact with compliance systems."""
    
    def __init__(
        self,
        compliance_repo: ComplianceRepository,
        evidence_repo: EvidenceRepository,
        business_repo: BusinessProfileRepository,
        risk_service: RiskAnalysisService,
        plan_service: CompliancePlanService,
        evidence_service: EvidenceVerificationService
    ):
        self.compliance_repo = compliance_repo
        self.evidence_repo = evidence_repo
        self.business_repo = business_repo
        self.risk_service = risk_service
        self.plan_service = plan_service
        self.evidence_service = evidence_service
    
    @tool
    async def search_regulations(self, query: str) -> Dict[str, Any]:
        """
        Search compliance regulations in knowledge graph.
        
        Args:
            query: Search query for regulations
            
        Returns:
            Relevant regulations and requirements
        """
        try:
            resources = await self.compliance_repo.search_compliance_resources(
                search_term=query,
                resource_type="Regulation"
            )
            return {
                "status": "success",
                "regulations": resources,
                "count": len(resources)
            }
        except Exception as e:
            logger.error(f"Regulation search failed: {e}")
            return {"status": "error", "message": str(e)}
    
    @tool
    async def analyze_business_risk(self, business_profile_id: str) -> Dict[str, Any]:
        """
        Analyze compliance risks for a business.
        
        Args:
            business_profile_id: Business profile ID
            
        Returns:
            Risk assessment with scores and recommendations
        """
        try:
            # Get business profile
            profile = await self.business_repo.get_by_id(business_profile_id)
            if not profile:
                return {"status": "error", "message": "Business profile not found"}
            
            # Convert to dict for service
            profile_dict = {
                "id": str(profile.id),
                "company_name": profile.company_name,
                "industry": profile.industry,
                "company_size": profile.company_size,
                "handles_personal_data": profile.handles_personal_data,
                "data_types": profile.data_types,
                "jurisdiction": profile.jurisdiction
            }
            
            # Analyze risks
            risk_assessment = await self.risk_service.analyze_business_risk(
                profile_dict
            )
            
            return {
                "status": "success",
                **risk_assessment
            }
        except Exception as e:
            logger.error(f"Risk analysis failed: {e}")
            return {"status": "error", "message": str(e)}
    
    @tool
    async def generate_compliance_plan(
        self,
        business_profile_id: str,
        regulations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a customized compliance action plan.
        
        Args:
            business_profile_id: Business profile ID
            regulations: Target regulations
            
        Returns:
            Structured compliance plan with timelines
        """
        try:
            # Get business profile and risk assessment
            profile = await self.business_repo.get_by_id(business_profile_id)
            if not profile:
                return {"status": "error", "message": "Business profile not found"}
            
            profile_dict = {
                "id": str(profile.id),
                "company_name": profile.company_name,
                "industry": profile.industry,
                "company_size": profile.company_size,
                "handles_personal_data": profile.handles_personal_data
            }
            
            # Get risk assessment
            risk_assessment = await self.risk_service.analyze_business_risk(
                profile_dict
            )
            
            # Generate plan
            plan = await self.plan_service.generate_compliance_plan(
                business_profile=profile_dict,
                risk_assessment=risk_assessment,
                regulations=regulations
            )
            
            return {
                "status": "success",
                **plan
            }
        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            return {"status": "error", "message": str(e)}
    
    @tool
    async def check_evidence_availability(
        self,
        business_profile_id: str,
        regulation_code: str
    ) -> Dict[str, Any]:
        """
        Check if business has evidence for a regulation.
        
        Args:
            business_profile_id: Business profile ID
            regulation_code: Regulation code to check
            
        Returns:
            Evidence status and available documents
        """
        try:
            verification = await self.evidence_service.verify_evidence_completeness(
                business_profile_id=business_profile_id,
                regulation_code=regulation_code
            )
            
            return {
                "status": "success",
                **verification
            }
        except Exception as e:
            logger.error(f"Evidence check failed: {e}")
            return {"status": "error", "message": str(e)}


class ReactAssessmentAgent(ComplianceAgent):
    """
    Enhanced Assessment Agent using ReAct architecture.
    
    Implements the ComplianceAgent protocol while providing ReAct
    reasoning capabilities for adaptive compliance assessments.
    """
    
    def __init__(
        self,
        compliance_repo: ComplianceRepository,
        evidence_repo: EvidenceRepository,
        business_repo: BusinessProfileRepository,
        model_name: str = "gpt-4"
    ):
        # Initialize services
        self.risk_service = RiskAnalysisService(compliance_repo)
        self.plan_service = CompliancePlanService(compliance_repo, self.risk_service)
        self.evidence_service = EvidenceVerificationService(evidence_repo, compliance_repo)
        
        # Initialize tools
        self.tools_provider = ReactComplianceTools(
            compliance_repo=compliance_repo,
            evidence_repo=evidence_repo,
            business_repo=business_repo,
            risk_service=self.risk_service,
            plan_service=self.plan_service,
            evidence_service=self.evidence_service
        )
        
        self.tools = [
            self.tools_provider.search_regulations,
            self.tools_provider.analyze_business_risk,
            self.tools_provider.generate_compliance_plan,
            self.tools_provider.check_evidence_availability
        ]
        
        # Initialize language model
        if model_name.startswith("gpt"):
            self.model = ChatOpenAI(model=model_name, temperature=0)
        else:
            self.model = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-exp",
                temperature=0
            )
        
        # Create ReAct agent
        self.agent = create_react_agent(
            model=self.model,
            tools=self.tools,
            prompt=self._create_system_prompt()
        )
        
        # Agent metadata
        self.metadata = AgentMetadata(
            name="ReactAssessmentAgent",
            version="2.0",
            capabilities=[
                AgentCapability.ASSESSMENT,
                AgentCapability.RISK_ANALYSIS,
                AgentCapability.PLAN_GENERATION,
                AgentCapability.EVIDENCE_CHECK
            ],
            supports_streaming=False,
            supports_context=True,
            max_context_length=4000,
            preferred_llm=model_name,
            description="ReAct-based assessment agent for dynamic compliance reasoning"
        )
        
        logger.info(f"ReactAssessmentAgent initialized with {model_name}")
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for the ReAct agent."""
        return """You are IQ, an expert AI compliance assistant for ruleIQ.
        
Your goal is to help businesses understand and improve their compliance posture through intelligent assessment.

When conducting assessments:
1. REASON about what information you need
2. ACT by using available tools to gather data
3. OBSERVE the results and adapt your approach

Key principles:
- Be conversational and friendly
- Ask clarifying questions when needed
- Provide actionable recommendations
- Focus on UK compliance frameworks (GDPR, DPA 2018, ISO 27001, Cyber Essentials)
- Prioritize based on risk level

Available tools help you:
- Search compliance regulations
- Analyze business risks
- Generate compliance plans
- Check evidence availability

Always explain your reasoning and make recommendations clear and actionable."""
    
    async def process_query(
        self,
        query: str,
        context: Optional[ComplianceContext] = None
    ) -> ComplianceResponse:
        """
        Process a compliance query using ReAct reasoning.
        
        Args:
            query: The user's query or request
            context: Optional compliance context
            
        Returns:
            Standardized compliance response
        """
        start_time = time.time()
        
        try:
            # Validate input
            is_valid, error_msg = await self.validate_input(query, context)
            if not is_valid:
                return ComplianceResponse(
                    status=ResponseStatus.ERROR,
                    message=error_msg or "Invalid input",
                    timestamp=datetime.utcnow()
                )
            
            # Prepare messages with context
            messages = [("human", query)]
            
            if context:
                context_info = []
                if context.business_profile_id:
                    context_info.append(f"Business Profile ID: {context.business_profile_id}")
                if context.industry:
                    context_info.append(f"Industry: {context.industry}")
                if context.regulations:
                    context_info.append(f"Regulations: {', '.join(context.regulations)}")
                
                if context_info:
                    context_msg = "\nContext: " + ", ".join(context_info)
                    messages[0] = ("human", query + context_msg)
            
            # Invoke ReAct agent
            result = await self.agent.ainvoke(
                {"messages": messages},
                config={
                    "configurable": {
                        "session_id": context.session_id if context else "default"
                    }
                }
            )
            
            # Extract response data
            final_message = result["messages"][-1].content
            reasoning_steps = self._extract_reasoning_steps(result)
            tools_used = self._extract_tools_used(result)
            recommendations = self._extract_recommendations(result)
            
            # Calculate processing time
            processing_time = int((time.time() - start_time) * 1000)
            
            return ComplianceResponse(
                status=ResponseStatus.SUCCESS,
                message=final_message,
                data={
                    "reasoning_steps": reasoning_steps,
                    "tools_used": tools_used
                },
                recommendations=recommendations,
                confidence_score=0.85,  # Can be calculated based on tools used
                processing_time_ms=processing_time,
                agent_metadata={
                    "agent": "ReactAssessmentAgent",
                    "version": self.metadata.version,
                    "model": self.metadata.preferred_llm
                },
                session_id=context.session_id if context else None,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"ReactAssessmentAgent processing failed: {e}")
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return ComplianceResponse(
                status=ResponseStatus.ERROR,
                message="Failed to process query",
                errors=[str(e)],
                processing_time_ms=processing_time,
                timestamp=datetime.utcnow()
            )
    
    async def get_capabilities(self) -> AgentMetadata:
        """Get the agent's capabilities and metadata."""
        return self.metadata
    
    async def validate_input(
        self,
        query: str,
        context: Optional[ComplianceContext] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Validate input before processing.
        
        Args:
            query: The query to validate
            context: Optional context to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not query or not query.strip():
            return False, "Query cannot be empty"
        
        if len(query) > 4000:
            return False, "Query exceeds maximum length (4000 characters)"
        
        if context:
            if context.business_profile_id:
                # Validate business profile exists
                try:
                    exists = await self.tools_provider.business_repo.exists(
                        context.business_profile_id
                    )
                    if not exists:
                        return False, "Business profile not found"
                except Exception as e:
                    logger.warning(f"Could not validate business profile: {e}")
        
        return True, None
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health status of the agent.
        
        Returns:
            Health status including dependencies and readiness
        """
        health_status = {
            "agent": "ReactAssessmentAgent",
            "status": "healthy",
            "dependencies": {},
            "capabilities": [cap.value for cap in self.metadata.capabilities],
            "model": self.metadata.preferred_llm
        }
        
        # Check tool availability
        try:
            for tool in self.tools:
                health_status["dependencies"][tool.name] = "available"
        except Exception as e:
            health_status["status"] = "degraded"
            health_status["errors"] = [str(e)]
        
        return health_status
    
    def _extract_reasoning_steps(self, result: Dict) -> List[str]:
        """Extract reasoning steps from agent execution."""
        steps = []
        for message in result.get("messages", []):
            if hasattr(message, "content"):
                content = message.content
                # Look for reasoning patterns
                if "Thought:" in content or "Reasoning:" in content:
                    lines = content.split("\n")
                    for line in lines:
                        if "Thought:" in line or "Reasoning:" in line:
                            step = line.split(":")[-1].strip()
                            if step:
                                steps.append(step)
        return steps
    
    def _extract_tools_used(self, result: Dict) -> List[str]:
        """Extract which tools were used during execution."""
        tools = []
        for message in result.get("messages", []):
            if hasattr(message, "tool_calls"):
                for tool_call in message.tool_calls:
                    tools.append(tool_call.get("name", "unknown"))
        return list(set(tools))
    
    def _extract_recommendations(self, result: Dict) -> List[Dict[str, Any]]:
        """Extract actionable recommendations from the response."""
        recommendations = []
        
        final_message = result["messages"][-1].content
        
        # Look for recommendation patterns
        lines = final_message.split("\n")
        in_recommendations = False
        
        for line in lines:
            line_lower = line.lower()
            
            # Check if we're in a recommendations section
            if "recommend" in line_lower or "action" in line_lower or "next step" in line_lower:
                in_recommendations = True
                continue
            
            # Extract bullet points or numbered items
            if in_recommendations:
                if any(marker in line for marker in ["•", "-", "1.", "2.", "3.", "4.", "5."]):
                    action = line.strip().lstrip("•-123456789. ")
                    if action:
                        priority = "high"
                        if any(word in action.lower() for word in ["immediate", "urgent", "critical"]):
                            priority = "critical"
                        elif any(word in action.lower() for word in ["soon", "priority"]):
                            priority = "high"
                        elif any(word in action.lower() for word in ["consider", "optional"]):
                            priority = "medium"
                        
                        recommendations.append({
                            "action": action,
                            "priority": priority,
                            "type": "compliance"
                        })
        
        return recommendations[:10]  # Return top 10 recommendations