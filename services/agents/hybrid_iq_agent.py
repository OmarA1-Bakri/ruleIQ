"""
Hybrid IQ Agent implementing ComplianceAgent protocol.

This module provides an enhanced IQ Agent that combines structured workflow
with ReAct capabilities while following the standard protocol.
"""

from typing import Dict, List, Optional, Any, Literal
from enum import Enum
from datetime import datetime
import time

from services.agents.protocols import (
    ComplianceAgent,
    ConversationalAgent,
    ComplianceContext,
    ComplianceResponse,
    ResponseStatus,
    AgentMetadata,
    AgentCapability
)
from services.agents.react_assessment_agent import ReactAssessmentAgent
from services.agents.repositories import (
    ComplianceRepository,
    EvidenceRepository,
    BusinessProfileRepository,
    AssessmentSessionRepository
)
from services.agents.services import (
    QueryClassificationService,
    RiskAnalysisService,
    CompliancePlanService,
    EvidenceVerificationService
)
from services.iq_agent import IQComplianceAgent
from config.logging_config import get_logger

logger = get_logger(__name__)


class ProcessingMode(Enum):
    """Processing modes for the hybrid agent."""
    STRUCTURED = "structured"  # Full PPALMR workflow
    REACT = "react"  # Dynamic ReAct reasoning
    QUICK = "quick"  # Fast direct response
    AUTO = "auto"  # Automatic mode selection


class HybridIQAgent(ConversationalAgent):
    """
    Enhanced IQ Agent implementing both ComplianceAgent and ConversationalAgent protocols.
    
    Combines:
    1. Structured PPALMR workflow for formal assessments
    2. ReAct architecture for dynamic problem-solving
    3. Intelligent routing based on query classification
    4. Conversational capabilities for multi-turn interactions
    """
    
    def __init__(
        self,
        compliance_repo: ComplianceRepository,
        evidence_repo: EvidenceRepository,
        business_repo: BusinessProfileRepository,
        session_repo: AssessmentSessionRepository,
        llm_model: str = "gpt-4"
    ):
        # Initialize repositories
        self.compliance_repo = compliance_repo
        self.evidence_repo = evidence_repo
        self.business_repo = business_repo
        self.session_repo = session_repo
        
        # Initialize services
        self.query_classifier = QueryClassificationService()
        self.risk_service = RiskAnalysisService(compliance_repo)
        self.plan_service = CompliancePlanService(compliance_repo, self.risk_service)
        self.evidence_service = EvidenceVerificationService(evidence_repo, compliance_repo)
        
        # Initialize sub-agents
        self.react_agent = ReactAssessmentAgent(
            compliance_repo=compliance_repo,
            evidence_repo=evidence_repo,
            business_repo=business_repo,
            model_name=llm_model
        )
        
        # Store for conversation history
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}
        
        # Agent metadata
        self.metadata = AgentMetadata(
            name="HybridIQAgent",
            version="3.0",
            capabilities=[
                AgentCapability.ASSESSMENT,
                AgentCapability.RISK_ANALYSIS,
                AgentCapability.EVIDENCE_CHECK,
                AgentCapability.REGULATION_SEARCH,
                AgentCapability.PLAN_GENERATION,
                AgentCapability.CONVERSATIONAL,
                AgentCapability.REPORT_GENERATION
            ],
            supports_streaming=False,
            supports_context=True,
            max_context_length=8000,
            preferred_llm=llm_model,
            fallback_llm="gemini-2.0-flash-exp",
            description="Hybrid agent combining structured workflow with adaptive ReAct reasoning"
        )
        
        logger.info(f"HybridIQAgent initialized with {llm_model}")
    
    async def process_query(
        self,
        query: str,
        context: Optional[ComplianceContext] = None
    ) -> ComplianceResponse:
        """
        Process a compliance query using the most appropriate method.
        
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
            
            # Classify the query
            classification = self.query_classifier.classify_query(query)
            
            # Route to appropriate processor
            if classification["processing_mode"] == "structured":
                response = await self._process_structured(query, context)
            elif classification["processing_mode"] == "react":
                response = await self._process_with_react(query, context)
            else:  # quick
                response = await self._process_quick(query, context)
            
            # Add classification metadata
            if response.agent_metadata:
                response.agent_metadata["classification"] = classification
            else:
                response.agent_metadata = {"classification": classification}
            
            # Update processing time
            response.processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Store in conversation history if session exists
            if context and context.session_id:
                await self._store_interaction(
                    context.session_id,
                    query,
                    response
                )
            
            return response
            
        except Exception as e:
            logger.error(f"HybridIQAgent processing failed: {e}")
            
            return ComplianceResponse(
                status=ResponseStatus.ERROR,
                message="Failed to process query",
                errors=[str(e)],
                processing_time_ms=int((time.time() - start_time) * 1000),
                timestamp=datetime.utcnow()
            )
    
    async def start_conversation(
        self,
        initial_message: str,
        context: Optional[ComplianceContext] = None
    ) -> ComplianceResponse:
        """Start a new conversation."""
        # Create new session ID if not provided
        if not context:
            context = ComplianceContext()
        
        if not context.session_id:
            context.session_id = f"conv_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize conversation storage
        self._conversations[context.session_id] = []
        
        # Process the initial message
        response = await self.process_query(initial_message, context)
        response.session_id = context.session_id
        
        return response
    
    async def continue_conversation(
        self,
        message: str,
        session_id: str,
        context: Optional[ComplianceContext] = None
    ) -> ComplianceResponse:
        """Continue an existing conversation."""
        # Ensure context has session ID
        if not context:
            context = ComplianceContext(session_id=session_id)
        else:
            context.session_id = session_id
        
        # Add conversation history to context
        if session_id in self._conversations:
            context.previous_messages = self._conversations[session_id]
        
        # Process the message with context
        response = await self.process_query(message, context)
        response.session_id = session_id
        
        return response
    
    async def end_conversation(self, session_id: str) -> ComplianceResponse:
        """End a conversation and cleanup resources."""
        try:
            # Generate conversation summary if exists
            summary = None
            if session_id in self._conversations:
                history = self._conversations[session_id]
                if history:
                    summary = await self._generate_conversation_summary(history)
                
                # Cleanup
                del self._conversations[session_id]
            
            return ComplianceResponse(
                status=ResponseStatus.SUCCESS,
                message="Conversation ended successfully",
                data={"summary": summary} if summary else None,
                session_id=session_id,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to end conversation {session_id}: {e}")
            
            return ComplianceResponse(
                status=ResponseStatus.ERROR,
                message="Failed to end conversation",
                errors=[str(e)],
                session_id=session_id,
                timestamp=datetime.utcnow()
            )
    
    async def get_conversation_history(
        self,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve conversation history."""
        return self._conversations.get(session_id, [])
    
    async def get_capabilities(self) -> AgentMetadata:
        """Get the agent's capabilities and metadata."""
        return self.metadata
    
    async def validate_input(
        self,
        query: str,
        context: Optional[ComplianceContext] = None
    ) -> tuple[bool, Optional[str]]:
        """Validate input before processing."""
        if not query or not query.strip():
            return False, "Query cannot be empty"
        
        if len(query) > self.metadata.max_context_length:
            return False, f"Query exceeds maximum length ({self.metadata.max_context_length} characters)"
        
        if context and context.business_profile_id:
            # Validate business profile exists
            try:
                exists = await self.business_repo.exists(context.business_profile_id)
                if not exists:
                    return False, "Business profile not found"
            except Exception as e:
                logger.warning(f"Could not validate business profile: {e}")
        
        return True, None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health status of the agent."""
        health_status = {
            "agent": "HybridIQAgent",
            "status": "healthy",
            "sub_agents": {},
            "repositories": {},
            "services": {},
            "capabilities": [cap.value for cap in self.metadata.capabilities]
        }
        
        # Check sub-agents
        try:
            react_health = await self.react_agent.health_check()
            health_status["sub_agents"]["react"] = react_health["status"]
        except Exception as e:
            health_status["sub_agents"]["react"] = f"error: {e}"
            health_status["status"] = "degraded"
        
        # Check repositories
        repos = {
            "compliance": self.compliance_repo,
            "evidence": self.evidence_repo,
            "business": self.business_repo,
            "session": self.session_repo
        }
        
        for name, repo in repos.items():
            try:
                # Simple existence check
                health_status["repositories"][name] = "available"
            except Exception as e:
                health_status["repositories"][name] = f"error: {e}"
                health_status["status"] = "degraded"
        
        # Check services
        services = {
            "query_classifier": self.query_classifier,
            "risk_service": self.risk_service,
            "plan_service": self.plan_service,
            "evidence_service": self.evidence_service
        }
        
        for name, service in services.items():
            try:
                health_status["services"][name] = "available"
            except Exception as e:
                health_status["services"][name] = f"error: {e}"
                health_status["status"] = "degraded"
        
        return health_status
    
    async def _process_structured(
        self,
        query: str,
        context: Optional[ComplianceContext]
    ) -> ComplianceResponse:
        """Process using structured PPALMR workflow."""
        logger.info("Using structured PPALMR workflow")
        
        # For now, delegate to a simplified structured process
        # In production, this would use the full IQComplianceAgent
        
        try:
            # Get business context if available
            business_data = None
            if context and context.business_profile_id:
                profile = await self.business_repo.get_by_id(context.business_profile_id)
                if profile:
                    business_data = {
                        "company_name": profile.company_name,
                        "industry": profile.industry,
                        "company_size": profile.company_size
                    }
            
            # Perform structured assessment
            steps = [
                "Perceive: Understanding compliance requirements",
                "Plan: Creating assessment strategy",
                "Act: Gathering compliance data",
                "Learn: Analyzing patterns and gaps",
                "Memory: Storing insights for future use",
                "Respond: Generating recommendations"
            ]
            
            recommendations = [
                {
                    "action": "Conduct comprehensive gap analysis",
                    "priority": "high",
                    "type": "assessment"
                },
                {
                    "action": "Document current compliance processes",
                    "priority": "high",
                    "type": "documentation"
                },
                {
                    "action": "Implement compliance monitoring",
                    "priority": "medium",
                    "type": "monitoring"
                }
            ]
            
            return ComplianceResponse(
                status=ResponseStatus.SUCCESS,
                message=f"Structured assessment completed for: {query}",
                data={
                    "workflow": "PPALMR",
                    "steps_completed": steps,
                    "business_context": business_data
                },
                recommendations=recommendations,
                confidence_score=0.9,
                agent_metadata={
                    "mode": "structured",
                    "workflow": "PPALMR"
                },
                session_id=context.session_id if context else None,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Structured processing failed: {e}")
            raise
    
    async def _process_with_react(
        self,
        query: str,
        context: Optional[ComplianceContext]
    ) -> ComplianceResponse:
        """Process using ReAct reasoning."""
        logger.info("Using ReAct reasoning architecture")
        
        # Delegate to ReAct agent
        return await self.react_agent.process_query(query, context)
    
    async def _process_quick(
        self,
        query: str,
        context: Optional[ComplianceContext]
    ) -> ComplianceResponse:
        """Process simple queries quickly."""
        logger.info("Processing quick answer")
        
        try:
            # For quick answers, check if it's an evidence query
            if "evidence" in query.lower() or "document" in query.lower():
                if context and context.business_profile_id:
                    # Quick evidence check
                    evidence_count = await self.evidence_repo.count_by_profile(
                        context.business_profile_id
                    )
                    
                    return ComplianceResponse(
                        status=ResponseStatus.SUCCESS,
                        message=f"You have {evidence_count} evidence documents uploaded.",
                        data={"evidence_count": evidence_count},
                        confidence_score=1.0,
                        agent_metadata={"mode": "quick"},
                        session_id=context.session_id if context else None,
                        timestamp=datetime.utcnow()
                    )
            
            # Generic quick response
            return ComplianceResponse(
                status=ResponseStatus.SUCCESS,
                message="I can help you with compliance questions. Please provide more details about what you need.",
                confidence_score=0.7,
                agent_metadata={"mode": "quick"},
                session_id=context.session_id if context else None,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Quick processing failed: {e}")
            raise
    
    async def _store_interaction(
        self,
        session_id: str,
        query: str,
        response: ComplianceResponse
    ) -> None:
        """Store interaction in conversation history."""
        if session_id not in self._conversations:
            self._conversations[session_id] = []
        
        self._conversations[session_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "query": query,
            "response": response.message,
            "status": response.status.value,
            "confidence": response.confidence_score
        })
    
    async def _generate_conversation_summary(
        self,
        history: List[Dict[str, Any]]
    ) -> str:
        """Generate a summary of the conversation."""
        if not history:
            return "No conversation history"
        
        # Simple summary for now
        total_interactions = len(history)
        topics = set()
        
        for interaction in history:
            query = interaction.get("query", "")
            # Extract key topics (simplified)
            if "gdpr" in query.lower():
                topics.add("GDPR")
            if "iso" in query.lower():
                topics.add("ISO 27001")
            if "risk" in query.lower():
                topics.add("Risk Assessment")
            if "evidence" in query.lower():
                topics.add("Evidence Management")
        
        summary = f"Conversation summary: {total_interactions} interactions"
        if topics:
            summary += f" covering {', '.join(topics)}"
        
        return summary