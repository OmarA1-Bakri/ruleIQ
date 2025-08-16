"""
Enhanced Assessment Agent with ReAct Architecture for ruleIQ.

This module extends the assessment agent with ReAct (Reasoning and Acting) capabilities,
allowing for more intelligent, adaptive compliance assessments.
"""

from typing import Dict, List, Optional, Any, TypedDict, Annotated
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from services.neo4j_service import Neo4jGraphRAGService
from services.ai.circuit_breaker import AICircuitBreaker
from services.agents.services import RiskAnalysisService, CompliancePlanService
from services.agents.repositories import ComplianceRepository, EvidenceRepository
from config.logging_config import get_logger

logger = get_logger(__name__)


class ComplianceTools:
    """Tools for ReAct agent to interact with compliance systems."""
    
    def __init__(self, neo4j_service: Neo4jGraphRAGService, postgres_session):
        self.neo4j = neo4j_service
        self.postgres = postgres_session
        self.circuit_breaker = AICircuitBreaker()
    
    @tool
    async def search_regulations(self, query: str) -> Dict[str, Any]:
        """
        Search compliance regulations in Neo4j knowledge graph.
        
        Args:
            query: Search query for regulations
            
        Returns:
            Relevant regulations and requirements
        """
        try:
            result = await self.neo4j.execute_query(
                """
                MATCH (r:Regulation)-[:HAS_REQUIREMENT]->(req:Requirement)
                WHERE r.name CONTAINS $query OR req.title CONTAINS $query
                RETURN r.name as regulation, 
                       collect(req.title) as requirements
                LIMIT 5
                """,
                {"query": query}
            )
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"Regulation search failed: {e}")
            return {"status": "error", "message": str(e)}
    
    @tool
    async def analyze_business_risk(self, business_profile: Dict) -> Dict[str, Any]:
        """
        Analyze compliance risks for a business profile.
        
        Args:
            business_profile: Business information dictionary
            
        Returns:
            Risk assessment with scores and recommendations
        """
        try:
            # Extract key factors
            industry = business_profile.get("industry", "unknown")
            size = business_profile.get("company_size", "unknown")
            data_handling = business_profile.get("handles_personal_data", False)
            
            risk_factors = []
            
            if data_handling:
                risk_factors.append({
                    "factor": "Personal Data Handling",
                    "risk_level": "high",
                    "regulations": ["GDPR", "DPA 2018"]
                })
            
            if size in ["201-500", "500+"]:
                risk_factors.append({
                    "factor": "Large Organization",
                    "risk_level": "medium",
                    "regulations": ["ISO 27001", "SOC 2"]
                })
            
            # Calculate overall risk score
            risk_score = len(risk_factors) * 25 + (30 if data_handling else 0)
            
            return {
                "status": "success",
                "risk_score": min(risk_score, 100),
                "risk_factors": risk_factors,
                "priority_actions": self._get_priority_actions(risk_factors)
            }
        except Exception as e:
            logger.error(f"Risk analysis failed: {e}")
            return {"status": "error", "message": str(e)}
    
    @tool
    async def generate_compliance_plan(
        self, 
        business_profile: Dict,
        risk_assessment: Dict
    ) -> Dict[str, Any]:
        """
        Generate a customized compliance action plan.
        
        Args:
            business_profile: Business information
            risk_assessment: Risk analysis results
            
        Returns:
            Structured compliance plan with timelines
        """
        try:
            risk_score = risk_assessment.get("risk_score", 50)
            
            if risk_score > 70:
                priority = "immediate"
                timeline = "1-2 weeks"
            elif risk_score > 40:
                priority = "high"
                timeline = "1 month"
            else:
                priority = "moderate"
                timeline = "3 months"
            
            plan = {
                "priority": priority,
                "timeline": timeline,
                "phases": [
                    {
                        "phase": 1,
                        "title": "Foundation",
                        "tasks": [
                            "Conduct gap analysis",
                            "Document current processes",
                            "Identify key stakeholders"
                        ],
                        "duration": "1 week"
                    },
                    {
                        "phase": 2,
                        "title": "Implementation",
                        "tasks": [
                            "Develop policies",
                            "Implement controls",
                            "Train staff"
                        ],
                        "duration": timeline
                    },
                    {
                        "phase": 3,
                        "title": "Validation",
                        "tasks": [
                            "Internal audit",
                            "Remediation",
                            "Certification prep"
                        ],
                        "duration": "2 weeks"
                    }
                ]
            }
            
            return {"status": "success", "plan": plan}
        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            return {"status": "error", "message": str(e)}
    
    @tool
    async def check_evidence_availability(
        self,
        business_id: str,
        requirement: str
    ) -> Dict[str, Any]:
        """
        Check if business has evidence for a specific requirement.
        
        Args:
            business_id: Business profile ID
            requirement: Compliance requirement to check
            
        Returns:
            Evidence status and available documents
        """
        try:
            from sqlalchemy import select
            from database.models.evidence import Evidence
            
            stmt = select(Evidence).where(
                Evidence.business_profile_id == business_id,
                Evidence.title.contains(requirement)
            )
            
            result = await self.postgres.execute(stmt)
            evidence_items = result.scalars().all()
            
            return {
                "status": "success",
                "has_evidence": len(evidence_items) > 0,
                "evidence_count": len(evidence_items),
                "evidence": [
                    {
                        "title": item.title,
                        "type": item.evidence_type,
                        "uploaded": item.created_at.isoformat()
                    }
                    for item in evidence_items
                ]
            }
        except Exception as e:
            logger.error(f"Evidence check failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_priority_actions(self, risk_factors: List[Dict]) -> List[str]:
        """Generate priority actions based on risk factors."""
        actions = []
        
        for factor in risk_factors:
            if factor["risk_level"] == "high":
                if "GDPR" in factor.get("regulations", []):
                    actions.append("Appoint Data Protection Officer")
                    actions.append("Conduct Privacy Impact Assessment")
                if "ISO 27001" in factor.get("regulations", []):
                    actions.append("Implement Information Security Management System")
            elif factor["risk_level"] == "medium":
                actions.append(f"Review {factor['factor']} compliance requirements")
        
        return actions[:5]  # Return top 5 priority actions


class ReActAssessmentAgent:
    """
    Enhanced Assessment Agent using ReAct architecture.
    
    This agent can:
    1. Reason about compliance requirements
    2. Act by searching regulations and analyzing risks
    3. Observe results and adapt strategy
    """
    
    def __init__(self, neo4j_service, postgres_session, model_name="gpt-4"):
        self.tools_provider = ComplianceTools(neo4j_service, postgres_session)
        
        # Initialize tools
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
            self.model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0)
        
        # Create ReAct agent
        self.agent = create_react_agent(
            model=self.model,
            tools=self.tools,
            messages_modifier=self._create_system_prompt()
        )
        
        logger.info(f"ReAct Assessment Agent initialized with {model_name}")
    
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
    
    async def conduct_assessment(
        self,
        user_query: str,
        business_context: Optional[Dict] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Conduct an intelligent compliance assessment using ReAct.
        
        Args:
            user_query: User's question or request
            business_context: Optional business profile information
            session_id: Optional session ID for tracking
            
        Returns:
            Assessment results with reasoning and recommendations
        """
        try:
            # Prepare the initial message
            messages = [("human", user_query)]
            
            # Add business context if provided
            if business_context:
                context_msg = f"\nBusiness Context: {business_context}"
                messages[0] = ("human", user_query + context_msg)
            
            # Invoke the ReAct agent
            result = await self.agent.ainvoke(
                {"messages": messages},
                config={"configurable": {"session_id": session_id or "default"}}
            )
            
            # Extract and format the response
            response = {
                "status": "success",
                "session_id": session_id,
                "reasoning_steps": self._extract_reasoning_steps(result),
                "final_answer": result["messages"][-1].content,
                "tools_used": self._extract_tools_used(result),
                "recommendations": self._extract_recommendations(result)
            }
            
            logger.info(f"ReAct assessment completed for session {session_id}")
            return response
            
        except Exception as e:
            logger.error(f"ReAct assessment failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "session_id": session_id
            }
    
    def _extract_reasoning_steps(self, result: Dict) -> List[str]:
        """Extract reasoning steps from agent execution."""
        steps = []
        for message in result.get("messages", []):
            if hasattr(message, "content") and "Thought:" in message.content:
                # Extract reasoning from agent's thought process
                thought = message.content.split("Thought:")[1].split("\n")[0].strip()
                steps.append(thought)
        return steps
    
    def _extract_tools_used(self, result: Dict) -> List[str]:
        """Extract which tools were used during execution."""
        tools = []
        for message in result.get("messages", []):
            if hasattr(message, "tool_calls"):
                for tool_call in message.tool_calls:
                    tools.append(tool_call["name"])
        return list(set(tools))
    
    def _extract_recommendations(self, result: Dict) -> List[Dict[str, str]]:
        """Extract actionable recommendations from the response."""
        recommendations = []
        
        final_message = result["messages"][-1].content
        
        # Simple extraction based on common patterns
        if "recommend" in final_message.lower():
            lines = final_message.split("\n")
            for line in lines:
                if any(marker in line for marker in ["•", "-", "1.", "2.", "3."]):
                    recommendations.append({
                        "action": line.strip().lstrip("•-123456789. "),
                        "priority": "high" if "immediate" in line.lower() else "medium"
                    })
        
        return recommendations[:5]  # Return top 5 recommendations


# Usage example
async def demo_react_assessment():
    """Demonstrate ReAct assessment capabilities."""
    from services.neo4j_service import Neo4jGraphRAGService
    from database.session import get_db
    
    # Initialize services
    neo4j = Neo4jGraphRAGService()
    async with get_db() as db:
        # Create ReAct agent
        agent = ReActAssessmentAgent(neo4j, db)
        
        # Example assessment
        result = await agent.conduct_assessment(
            user_query="We're a fintech startup handling payment data. What are our top compliance priorities?",
            business_context={
                "industry": "Financial Services",
                "company_size": "11-50",
                "handles_personal_data": True,
                "data_types": ["payment_data", "personal_identifiable_info"]
            },
            session_id="demo_session_001"
        )
        
        print(f"Assessment Result: {result}")
        return result


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_react_assessment())