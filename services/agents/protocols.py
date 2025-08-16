"""
Protocol definitions for compliance agents.

This module defines the base protocols and interfaces that all compliance agents
must implement, ensuring consistency and maintainability across the system.
"""

from typing import Protocol, Dict, List, Optional, Any, runtime_checkable
from abc import abstractmethod
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class ResponseStatus(Enum):
    """Standard response statuses for all agents."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    PENDING = "pending"
    FALLBACK = "fallback"


class AgentCapability(Enum):
    """Capabilities that agents can declare."""
    ASSESSMENT = "assessment"
    RISK_ANALYSIS = "risk_analysis"
    EVIDENCE_CHECK = "evidence_check"
    REGULATION_SEARCH = "regulation_search"
    PLAN_GENERATION = "plan_generation"
    CONVERSATIONAL = "conversational"
    REPORT_GENERATION = "report_generation"
    POLICY_CREATION = "policy_creation"


@dataclass
class AgentMetadata:
    """Metadata about an agent's capabilities and configuration."""
    name: str
    version: str
    capabilities: List[AgentCapability]
    supports_streaming: bool
    supports_context: bool
    max_context_length: int
    preferred_llm: str
    fallback_llm: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ComplianceContext:
    """Standard context structure for compliance queries."""
    business_profile_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    regulations: Optional[List[str]] = None
    industry: Optional[str] = None
    jurisdiction: Optional[str] = None
    previous_messages: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ComplianceResponse:
    """Standard response structure for all compliance agents."""
    status: ResponseStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    artifacts: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    confidence_score: Optional[float] = None
    processing_time_ms: Optional[int] = None
    agent_metadata: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    session_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary format."""
        return {
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "artifacts": self.artifacts,
            "recommendations": self.recommendations,
            "evidence": self.evidence,
            "confidence_score": self.confidence_score,
            "processing_time_ms": self.processing_time_ms,
            "agent_metadata": self.agent_metadata,
            "errors": self.errors,
            "warnings": self.warnings,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


@runtime_checkable
class ComplianceAgent(Protocol):
    """
    Base protocol for all compliance agents.
    
    This protocol ensures consistent interfaces across different agent implementations
    while allowing flexibility in internal implementation details.
    """
    
    @abstractmethod
    async def process_query(
        self,
        query: str,
        context: Optional[ComplianceContext] = None
    ) -> ComplianceResponse:
        """
        Process a compliance-related query.
        
        Args:
            query: The user's query or request
            context: Optional context for the query
            
        Returns:
            Standardized compliance response
        """
        ...
    
    @abstractmethod
    async def get_capabilities(self) -> AgentMetadata:
        """
        Get the agent's capabilities and metadata.
        
        Returns:
            Agent metadata including capabilities and configuration
        """
        ...
    
    @abstractmethod
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
        ...
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health status of the agent.
        
        Returns:
            Health status including dependencies and readiness
        """
        ...


@runtime_checkable
class ConversationalAgent(ComplianceAgent, Protocol):
    """Extended protocol for conversational agents."""
    
    @abstractmethod
    async def start_conversation(
        self,
        initial_message: str,
        context: Optional[ComplianceContext] = None
    ) -> ComplianceResponse:
        """Start a new conversation."""
        ...
    
    @abstractmethod
    async def continue_conversation(
        self,
        message: str,
        session_id: str,
        context: Optional[ComplianceContext] = None
    ) -> ComplianceResponse:
        """Continue an existing conversation."""
        ...
    
    @abstractmethod
    async def end_conversation(
        self,
        session_id: str
    ) -> ComplianceResponse:
        """End a conversation and cleanup resources."""
        ...
    
    @abstractmethod
    async def get_conversation_history(
        self,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve conversation history."""
        ...


@runtime_checkable
class AssessmentAgent(ComplianceAgent, Protocol):
    """Extended protocol for assessment agents."""
    
    @abstractmethod
    async def start_assessment(
        self,
        assessment_type: str,
        context: ComplianceContext
    ) -> ComplianceResponse:
        """Start a new compliance assessment."""
        ...
    
    @abstractmethod
    async def get_assessment_progress(
        self,
        assessment_id: str
    ) -> Dict[str, Any]:
        """Get the progress of an ongoing assessment."""
        ...
    
    @abstractmethod
    async def complete_assessment(
        self,
        assessment_id: str
    ) -> ComplianceResponse:
        """Complete and finalize an assessment."""
        ...
    
    @abstractmethod
    async def generate_assessment_report(
        self,
        assessment_id: str,
        format: str = "pdf"
    ) -> bytes:
        """Generate a report for a completed assessment."""
        ...


class AgentRegistry:
    """
    Registry for managing multiple compliance agents.
    
    This class provides a central place to register, discover, and
    route requests to appropriate agents based on capabilities.
    """
    
    def __init__(self):
        self._agents: Dict[str, ComplianceAgent] = {}
        self._capability_map: Dict[AgentCapability, List[str]] = {}
    
    def register(self, agent_id: str, agent: ComplianceAgent) -> None:
        """Register a new agent."""
        if not isinstance(agent, ComplianceAgent):
            raise TypeError(f"Agent must implement ComplianceAgent protocol")
        
        self._agents[agent_id] = agent

        # Index capabilities for routing
        try:
            metadata = agent.get_capabilities()
            for cap in metadata.capabilities:
                self._capability_map.setdefault(cap, []).append(agent_id)
        except Exception:
            # Non-fatal: capability-based routing will fall back
            pass
    def get_agent(self, agent_id: str) -> Optional[ComplianceAgent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def find_agents_by_capability(
        self,
        capability: AgentCapability
    ) -> List[str]:
        """Find agents that have a specific capability."""
        return self._capability_map.get(capability, [])
    
    def list_agents(self) -> Dict[str, str]:
        """List all registered agents."""
        return {
            agent_id: agent.__class__.__name__
            for agent_id, agent in self._agents.items()
        }
    
    async def route_query(
        self,
        query: str,
        preferred_agent: Optional[str] = None,
        required_capabilities: Optional[List[AgentCapability]] = None,
        context: Optional[ComplianceContext] = None
    ) -> ComplianceResponse:
        """
        Route a query to the most appropriate agent.
        
        Args:
            query: The query to process
            preferred_agent: Preferred agent ID if any
            required_capabilities: Required capabilities for handling the query
            context: Query context
            
        Returns:
            Response from the selected agent
        """
        # Try preferred agent first
        if preferred_agent and preferred_agent in self._agents:
            agent = self._agents[preferred_agent]
            return await agent.process_query(query, context)
        
        # Find agent by required capabilities
        if required_capabilities:
            for capability in required_capabilities:
                agent_ids = self.find_agents_by_capability(capability)
                if agent_ids:
                    agent = self._agents[agent_ids[0]]
                    return await agent.process_query(query, context)
        
        # Fallback to first available agent
        if self._agents:
            agent = next(iter(self._agents.values()))
            return await agent.process_query(query, context)
        
        # No agents available
        return ComplianceResponse(
            status=ResponseStatus.ERROR,
            message="No agents available to process this query",
            errors=["No registered agents found"]
        )


# Singleton registry instance
agent_registry = AgentRegistry()