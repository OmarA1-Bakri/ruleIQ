"""
Agentic Integration Service
Combines RAG system with Pydantic AI agents for seamless Claude integration
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from services.agentic_rag import AgenticRAGSystem
from services.agents.pydantic_ai_framework import (
    AgentOrchestrator,
    AgentContext,
    ComplianceAgentResponse,
)

logger = logging.getLogger(__name__)


class AgenticIntegrationService:
    """
    Main integration service that orchestrates RAG and agents
    Provides the interface for seamless Claude integration
    """

    def __init__(self) -> None:
        # Initialize RAG system
        self.rag_system = AgenticRAGSystem()

        # Initialize agent orchestrators for different trust levels
        self.agent_orchestrators = {
            0: AgentOrchestrator(trust_level=0, rag_system=self.rag_system),
            1: AgentOrchestrator(trust_level=1, rag_system=self.rag_system),
            2: AgentOrchestrator(trust_level=2, rag_system=self.rag_system),
            3: AgentOrchestrator(trust_level=3, rag_system=self.rag_system),
        }

        # Track active sessions
        self.active_sessions = {}

        # Configuration
        self.auto_process_docs = (os.getenv("AUTO_PROCESS_DOCS", "true").lower() == "true",)

        # Initialize fact-checker and self-critic system
        self.fact_checker = None
        self.self_critic_enabled = (os.getenv("ENABLE_RAG_SELF_CRITIC", "true").lower() == "true",)

    async def initialize(self) -> None:
        """Initialize the service and process documentation if needed"""
        try:
            logger.info("Initializing Agentic Integration Service...")

            # Check if documentation is already processed
            stats = await self.rag_system.get_framework_statistics()

            if stats.get("total_chunks", 0) == 0 and self.auto_process_docs:
                logger.info(
                    "No documentation found, processing LangGraph and Pydantic AI docs...",
                )
                await self.rag_system.process_documentation_files()
                logger.info("Documentation processing completed")
            else:
                logger.info(
                    f"Found {stats.get('total_chunks', 0)} documentation chunks and {stats.get('total_code_examples', 0)} code examples",
                )

            # Initialize fact-checker if enabled
            if self.self_critic_enabled:
                from .rag_fact_checker import RAGFactChecker

                self.fact_checker = RAGFactChecker()
                logger.info("RAG self-critic and fact-checker initialized")

            logger.info("Agentic Integration Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Agentic Integration Service: {e}")
            raise

    async def process_compliance_request(
        self,
        request: str,
        user_id: str,
        session_id: Optional[str] = None,
        trust_level: int = 1,
        business_context: Optional[Dict[str, Any]] = None,
    ) -> ComplianceAgentResponse:
        """
        Process a compliance request using the appropriate agent

        Args:
            request: User's compliance question or request
            user_id: ID of the requesting user
            session_id: Optional session ID for context tracking
            trust_level: Agent trust level (0-3)
            business_context: Additional business context

        Returns:
            ComplianceAgentResponse with recommendations and reasoning
        """
        try:
            # Generate session ID if not provided
            if not session_id:
                session_id = f"{user_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

            # Get or create session context
            context = self._get_session_context(
                user_id=user_id,
                session_id=session_id,
                trust_level=trust_level,
                business_context=business_context or {},
            )

            # Validate trust level
            if trust_level not in self.agent_orchestrators:
                trust_level = 1  # Default to trust level 1
                logger.warning(
                    f"Invalid trust level provided, defaulting to {trust_level}",
                )

            # Process request through agent orchestrator
            orchestrator = self.agent_orchestrators[trust_level]
            response = await orchestrator.route_request(request, context)

            # Update session context
            self.active_sessions[session_id] = context

            # Log request for analytics
            await self._log_request(request, response, context)

            return response

        except Exception as e:
            logger.error(f"Error processing compliance request: {e}")

            # Return safe fallback response
            return ComplianceAgentResponse(
                recommendation=(
                    "I apologize, but I encountered an error processing your compliance request. "
                    "Please try rephrasing your question or contact support for assistance.",
                ),
                confidence=0.0,
                trust_level_required=1,
                reasoning=f"System error: {str(e)}",
                risk_level="medium",
                requires_human_approval=True,
                sources=["system_error"],
            )

    async def query_documentation(
        self,
        query: str,
        source_filter: Optional[str] = None,
        query_type: str = "documentation",
    ) -> Dict[str, Any]:
        """
        Query the RAG documentation system directly

        Args:
            query: Documentation question
            source_filter: Filter by 'langgraph' or 'pydantic_ai'
            query_type: 'documentation', 'code_examples', or 'hybrid'

        Returns:
            RAG response with answer and sources
        """
        try:
            result = await self.rag_system.query_documentation(
                query=query,
                source_filter=source_filter,
                query_type=query_type,
                max_results=5,
            )

            return {
                "answer": result.answer,
                "confidence": result.confidence,
                "sources": result.sources,
                "processing_time": result.processing_time,
                "query_type": result.query_type,
            }

        except Exception as e:
            logger.error(f"Error querying documentation: {e}")
            return {
                "answer": f"I encountered an error while searching the documentation: {str(e)}",
                "confidence": 0.0,
                "sources": [],
                "processing_time": 0.0,
                "query_type": query_type,
            }

    async def get_implementation_guidance(self, topic: str, framework: str = "langgraph") -> str:
        """
        Get specific implementation guidance for LangGraph or Pydantic AI

        Args:
            topic: What to implement (e.g., "state management", "agent design")
            framework: "langgraph" or "pydantic_ai"

        Returns:
            Detailed implementation guidance with code examples
        """
        try:
            guidance_query = (
                f"How do I implement {topic} in {framework}? Provide detailed code examples and best practices.",
            )

            result = await self.rag_system.query_documentation(
                query=guidance_query,
                source_filter=framework,
                query_type="hybrid",
                max_results=3,
            )

            return result.answer

        except Exception as e:
            logger.error(f"Error getting implementation guidance: {e}")
            return f"I apologize, but I couldn't retrieve guidance for {topic} in {framework}. Please check the documentation directly or try rephrasing your request."  # noqa: E501

    async def find_code_examples(
        self, task_description: str, framework: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find specific code examples for a task

        Args:
            task_description: Description of what you want to implement
            framework: Optional framework filter

        Returns:
            Code examples with explanations
        """
        try:
            example_query = f"Show me code examples for: {task_description}"

            result = await self.rag_system.query_documentation(
                query=example_query,
                source_filter=framework,
                query_type="code_examples",
                max_results=5,
            )

            return {
                "examples": result.sources,
                "explanation": result.answer,
                "confidence": result.confidence,
            }

        except Exception as e:
            logger.error(f"Error finding code examples: {e}")
            return {
                "examples": [],
                "explanation": f"I couldn't find code examples for: {task_description}",
                "confidence": 0.0,
            }

    async def validate_implementation_approach(self, approach_description: str) -> str:
        """
        Validate a technical approach against best practices

        Args:
            approach_description: Description of your proposed approach

        Returns:
            Validation feedback and suggestions
        """
        try:
            validation_query = f"""
            Is this a good approach for LangGraph/Pydantic AI implementation?

            Proposed approach: {approach_description}

            Please provide detailed feedback, suggestions for improvement, and any potential issues.
            """

            result = await self.rag_system.query_documentation(
                query=validation_query,
                source_filter=None,
                query_type="hybrid",
                max_results=5,
            )

            return result.answer

        except Exception as e:
            logger.error(f"Error validating approach: {e}")
            return f"I couldn't validate your approach due to an error: {str(e)}"

    async def fact_check_response(
        self,
        response_text: str,
        sources: List[Dict[str, Any]],
        original_query: str,
        quick_check: bool = False,
    ) -> Dict[str, Any]:
        """
        Fact-check a RAG response using the self-critic system

        Args:
            response_text: The response to fact-check
            sources: Source documents used for the response
            original_query: The original user query
            quick_check: If True, use quick fact-checking for real-time use

        Returns:
            Fact-check results with approval status and confidence scores
        """
        try:
            if not self.fact_checker:
                logger.warning(
                    "Fact-checker not initialized, returning basic validation",
                )
                return {
                    "approved": True,
                    "confidence": 0.7,
                    "fact_check_available": False,
                    "message": "Fact-checking service not available",
                }

            if quick_check:
                # Quick fact-check for real-time usage
                is_reliable = await self.fact_checker.quick_fact_check(
                    response_text=response_text,
                    sources=sources,
                )

                return {
                    "approved": is_reliable,
                    "confidence": 0.8 if is_reliable else 0.4,
                    "fact_check_type": "quick",
                    "fact_check_available": True,
                    "message": "Quick fact-check completed",
                }
            else:
                # Comprehensive fact-checking
                assessment = await self.fact_checker.comprehensive_fact_check(
                    response_text=response_text,
                    sources=sources,
                    original_query=original_query,
                )

                return {
                    "approved": assessment.approved_for_use,
                    "confidence": assessment.response_reliability,
                    "overall_score": assessment.overall_score,
                    "source_quality": assessment.source_quality_score,
                    "fact_check_type": "comprehensive",
                    "fact_check_available": True,
                    "flagged_issues": assessment.flagged_issues,
                    "recommendations": assessment.recommendations,
                    "fact_check_results": len(assessment.fact_check_results),
                    "self_critiques": len(assessment.self_critiques),
                    "message": "Comprehensive fact-check completed",
                }

        except Exception as e:
            logger.error(f"Error during fact-checking: {e}")
            return {
                "approved": True,  # Fail open for safety
                "confidence": 0.5,
                "fact_check_available": False,
                "error": str(e),
                "message": "Fact-checking failed, proceeding with caution",
            }

    async def query_documentation_with_validation(
        self,
        query: str,
        source_filter: Optional[str] = None,
        query_type: str = "documentation",
        enable_fact_check: bool = True,
        quick_validation: bool = True,
    ) -> Dict[str, Any]:
        """
        Query documentation with automatic fact-checking validation

        Args:
            query: Documentation question
            source_filter: Filter by 'langgraph' or 'pydantic_ai'
            query_type: 'documentation', 'code_examples', or 'hybrid'
            enable_fact_check: Whether to run fact-checking
            quick_validation: Use quick fact-check for better performance

        Returns:
            RAG response with validation results
        """
        try:
            # Get standard RAG response
            rag_result = await self.query_documentation(
                query=query,
                source_filter=source_filter,
                query_type=query_type,
            )

            # Add validation if enabled and fact-checker available
            if enable_fact_check and self.fact_checker and self.self_critic_enabled:
                validation_result = await self.fact_check_response(
                    response_text=rag_result["answer"],
                    sources=rag_result["sources"],
                    original_query=query,
                    quick_check=quick_validation,
                )

                # Combine results
                rag_result.update(
                    {
                        "validation": validation_result,
                        "trust_score": validation_result["confidence"],
                        "approved_for_use": validation_result["approved"],
                    },
                )
            else:
                # Add default validation info
                rag_result.update(
                    {
                        "validation": {
                            "fact_check_available": False,
                            "message": "Fact-checking disabled or unavailable",
                        },
                        "trust_score": rag_result["confidence"],
                        "approved_for_use": True,
                    },
                )

            return rag_result

        except Exception as e:
            logger.error(f"Error in validated documentation query: {e}")
            return {
                "answer": f"I encountered an error while processing your query: {str(e)}",
                "confidence": 0.0,
                "sources": [],
                "processing_time": 0.0,
                "query_type": query_type,
                "validation": {"fact_check_available": False, "error": str(e)},
                "trust_score": 0.0,
                "approved_for_use": False,
            }

    def _get_session_context(
        self,
        user_id: str,
        session_id: str,
        trust_level: int,
        business_context: Dict[str, Any],
    ) -> AgentContext:
        """Get or create session context"""

        if session_id in self.active_sessions:
            context = self.active_sessions[session_id]
            # Update trust level if changed
            context.trust_level = trust_level
            # Merge business context
            context.business_context.update(business_context)
        else:
            context = AgentContext(
                user_id=user_id,
                session_id=session_id,
                trust_level=trust_level,
                business_context=business_context,
                interaction_history=[],
                preferences={},
            )

        return context

    async def _log_request(
        self, request: str, response: ComplianceAgentResponse, context: AgentContext
    ) -> None:
        """Log request for analytics and improvement"""
        try:
            # This could be expanded to log to database for analytics
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": context.user_id,
                "session_id": context.session_id,
                "trust_level": context.trust_level,
                "request_type": "compliance",
                "confidence": response.confidence,
                "risk_level": response.risk_level,
                "required_approval": response.requires_human_approval,
            }

            logger.info(f"Request logged: {log_entry}")

        except Exception as e:
            logger.warning(f"Failed to log request: {e}")

    async def get_system_status(self) -> Dict[str, Any]:
        """Get status of the agentic system"""
        try:
            # Get RAG system statistics
            rag_stats = await self.rag_system.get_framework_statistics()

            # Get available sources
            sources = await self.rag_system.get_available_sources()

            return {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "rag_system": {
                    "total_chunks": rag_stats.get("total_chunks", 0),
                    "total_code_examples": rag_stats.get("total_code_examples", 0),
                    "available_sources": sources,
                    "capabilities": {
                        "contextual_embeddings": self.rag_system.use_contextual_embeddings,
                        "hybrid_search": self.rag_system.use_hybrid_search,
                        "agentic_rag": self.rag_system.use_agentic_rag,
                        "knowledge_graph": self.rag_system.use_knowledge_graph,
                    },
                },
                "agents": {
                    "available_trust_levels": list(self.agent_orchestrators.keys()),
                    "active_sessions": len(self.active_sessions),
                },
                "fact_checker": {
                    "enabled": self.self_critic_enabled,
                    "available": self.fact_checker is not None,
                    "capabilities": (
                        {
                            "quick_fact_check": True,
                            "comprehensive_analysis": True,
                            "self_criticism": True,
                            "quality_scoring": True,
                        }
                        if self.fact_checker
                        else {},
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "status": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }

    def cleanup_inactive_sessions(self, max_age_hours: int = 24) -> None:
        """Clean up old inactive sessions"""
        try:
            current_time = datetime.now(timezone.utc)
            sessions_to_remove = []

            for session_id, context in self.active_sessions.items():
                # Check last interaction time
                if context.interaction_history:
                    last_interaction = datetime.fromisoformat(
                        context.interaction_history[-1]["timestamp"],
                    )
                    age_hours = (current_time - last_interaction).total_seconds() / 3600

                    if age_hours > max_age_hours:
                        sessions_to_remove.append(session_id)

            for session_id in sessions_to_remove:
                del self.active_sessions[session_id]

            if sessions_to_remove:
                logger.info(f"Cleaned up {len(sessions_to_remove)} inactive sessions")

        except Exception as e:
            logger.warning(f"Error cleaning up sessions: {e}")


# Global service instance
_agentic_service = None


def get_agentic_service() -> AgenticIntegrationService:
    """Get or create the global agentic service instance"""
    global _agentic_service
    if _agentic_service is None:
        _agentic_service = AgenticIntegrationService()
    return _agentic_service


async def initialize_agentic_service():
    """Initialize the global agentic service"""
    service = get_agentic_service()
    await service.initialize()
    return service
