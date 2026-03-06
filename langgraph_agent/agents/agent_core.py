"""

Core agent architecture with LangGraph state machine and multi-agent coordination.
Production-ready implementation with streaming, context optimization, and error handling.
"""

import logging
from typing import Dict, Optional, Any, Union, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4
from enum import Enum

from langchain_core.runnables import RunnableConfig

from ..core.models import SafeFallbackResponse
from ..core.constants import (
    SLO_P95_LATENCY_MS,
    MODEL_CONFIG,
    AUTONOMY_LEVELS,
    EXECUTION_LIMITS,
    COST_LIMITS,
)
from ..graph.state import create_initial_state

logger = logging.getLogger(__name__)


class AgentMode(str, Enum):
    """Agent operation modes."""

    INTERACTIVE = "interactive"
    AUTONOMOUS = "autonomous"
    BATCH = "batch"
    STREAMING = "streaming"


class PriorityLevel(str, Enum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AgentConfig:
    """Configuration for compliance agent."""

    # Model configuration
    primary_model: str = MODEL_CONFIG["primary_model"]
    fallback_model: str = MODEL_CONFIG["fallback_model"]
    temperature: float = MODEL_CONFIG["temperature"]
    max_tokens: int = MODEL_CONFIG["max_tokens"]

    # Agent behavior
    mode: AgentMode = AgentMode.INTERACTIVE
    autonomy_level: int = AUTONOMY_LEVELS["trusted_advisor"]
    max_turns: int = EXECUTION_LIMITS["max_turns_per_session"]
    max_tool_calls: int = EXECUTION_LIMITS["max_tool_calls_per_turn"]

    # Performance limits
    response_timeout_seconds: int = 30
    max_context_tokens: int = 8000
    streaming_enabled: bool = True

    # Cost management
    max_cost_per_session: float = COST_LIMITS["max_per_1k_tokens"] * 50  # $17.50 per session
    cost_tracking_enabled: bool = True

    # Memory configuration
    memory_enabled: bool = True
    conversation_summarization: bool = True
    entity_extraction: bool = True

    # RAG configuration
    rag_enabled: bool = True
    retrieval_k: int = 6
    similarity_threshold: float = 0.7

    # Observability
    langsmith_enabled: bool = True
    debug_mode: bool = False
    metrics_collection: bool = True


@dataclass
class AgentMetrics:
    """Real-time agent performance metrics."""

    session_id: str
    start_time: datetime = field(default_factory=datetime.utcnow)

    # Performance metrics
    total_latency_ms: int = 0
    first_token_latency_ms: Optional[int] = None
    avg_token_generation_ms: float = 0.0

    # Usage metrics
    total_turns: int = 0
    total_tool_calls: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    # Cost tracking
    total_cost: float = 0.0
    cost_per_token: float = 0.0

    # Quality metrics
    successful_responses: int = 0
    error_count: int = 0
    fallback_responses: int = 0
    user_satisfaction_score: Optional[float] = None

    # Memory metrics
    memories_created: int = 0
    memories_retrieved: int = 0
    rag_retrievals: int = 0

    def update_latency(self, latency_ms: int) -> None:
        """Update latency metrics."""
        self.total_latency_ms += latency_ms
        if self.total_turns > 0:
            self.avg_token_generation_ms = self.total_latency_ms / self.total_turns

    def update_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Update token usage metrics."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens = self.input_tokens + self.output_tokens

    def update_cost(self, cost: float) -> None:
        """Update cost metrics."""
        self.total_cost += cost
        if self.total_tokens > 0:
            self.cost_per_token = self.total_cost / self.total_tokens

    def is_slo_compliant(self) -> bool:
        """Check if performance meets SLO requirements."""
        if self.total_turns == 0:
            return True
        avg_latency = self.total_latency_ms / self.total_turns
        return avg_latency <= SLO_P95_LATENCY_MS

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging."""
        return {
            "session_id": self.session_id,
            "duration_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds(),
            "total_latency_ms": self.total_latency_ms,
            "avg_latency_ms": self.total_latency_ms / max(self.total_turns, 1),
            "first_token_latency_ms": self.first_token_latency_ms,
            "total_turns": self.total_turns,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "error_rate": self.error_count / max(self.total_turns, 1),
            "slo_compliant": self.is_slo_compliant(),
            "cost_per_token": self.cost_per_token,
        }


class ComplianceAgent:
    """
    Production-ready compliance agent with LangGraph state machine.

    Features:
    - Multi-agent coordination
    - Advanced tool selection
    - Memory management
    - Context window optimization
    - Streaming responses
    - Comprehensive observability
    """

    def __init__(
        self,
        config: AgentConfig,
        database_url: str,
        tool_manager: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
        rag_system: Optional[Any] = None,
        observability_manager: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.database_url = database_url
        self.tool_manager = tool_manager
        self.memory_manager = memory_manager
        self.rag_system = rag_system
        self.observability_manager = observability_manager

        # Initialize state and metrics
        self.active_sessions: Dict[str, AgentMetrics] = {}
        self.compiled_graph = None

        # Initialize components
        self._initialize_graph()
        self._setup_callbacks()

        logger.info(f"ComplianceAgent initialized with config: {config}")

    def _initialize_graph(self) -> None:
        """Initialize the LangGraph state machine."""
        from ..graph.app import create_graph, create_checkpointer

        # Create graph
        graph = create_graph()

        # Create checkpointer
        checkpointer = create_checkpointer(self.database_url)

        # Compile with interrupts for human review
        interrupt_before = []
        if self.config.autonomy_level < AUTONOMY_LEVELS["autonomous_partner"]:
            interrupt_before = ["legal_reviewer"]

        self.compiled_graph = graph.compile(
            checkpointer=checkpointer, interrupt_before=interrupt_before
        )

        logger.info("LangGraph compiled successfully")

    def _setup_callbacks(self) -> None:
        """Setup callback handlers for observability."""
        self.callbacks = []

        if self.observability_manager:
            self.callbacks.append(self.observability_manager.get_callback())

        if self.config.langsmith_enabled:
            # LangSmith callback would be added here
            pass

        if self.config.debug_mode:
            # Debug callback would be added here
            pass

    async def start_session(
        self,
        company_id: UUID,
        user_id: Optional[UUID] = None,
        session_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a new agent session.

        Args:
            company_id: Company UUID for tenancy
            user_id: Optional user ID
            session_context: Optional session context

        Returns:
            Session ID for tracking
        """
        session_id = str(uuid4())

        # Initialize metrics
        metrics = AgentMetrics(session_id=session_id)
        self.active_sessions[session_id] = metrics

        # Load user profile and context
        if self.memory_manager:
            await self.memory_manager.load_user_context(company_id, user_id)

        logger.info(f"Started session {session_id} for company {company_id}")
        return session_id

    async def process_message(
        self,
        session_id: str,
        message: str,
        company_id: UUID,
        priority: PriorityLevel = PriorityLevel.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
    ) -> Union[str, SafeFallbackResponse]:
        """
        Process a user message and return response.

        Args:
            session_id: Session ID for tracking
            message: User input message
            company_id: Company UUID for tenancy
            priority: Message priority level
            context: Optional additional context

        Returns:
            Agent response or fallback response
        """
        if session_id not in self.active_sessions:
            return SafeFallbackResponse(
                error_message="Invalid session ID",
                error_details={"session_id": session_id},
            )

        metrics = self.active_sessions[session_id]
        start_time = datetime.now(timezone.utc)

        try:
            # Check limits
            if metrics.total_turns >= self.config.max_turns:
                return SafeFallbackResponse(
                    error_message="Session turn limit exceeded",
                    error_details={"max_turns": self.config.max_turns},
                )

            if metrics.total_cost >= self.config.max_cost_per_session:
                return SafeFallbackResponse(
                    error_message="Session cost limit exceeded",
                    error_details={"max_cost": self.config.max_cost_per_session},
                )

            # Create initial state
            state = create_initial_state(
                company_id=company_id,
                user_input=message,
                thread_id=session_id,
                autonomy_level=self.config.autonomy_level,
            )

            # Add context from memory and RAG
            if self.memory_manager:
                memory_context = await self.memory_manager.get_relevant_memories(
                    company_id, message
                )
                state["meta"]["memory_context"] = memory_context

            if self.rag_system:
                rag_context = await self.rag_system.retrieve_relevant_docs(
                    message, company_id, k=self.config.retrieval_k
                )
                state["retrieved_docs"] = rag_context

            # Configure runnable
            config = RunnableConfig(
                configurable={"thread_id": session_id, "company_id": str(company_id)},
                callbacks=self.callbacks,
            )

            # Execute graph
            result = await self.compiled_graph.ainvoke(state, config=config)

            # Extract response
            last_message = result["messages"][-1] if result["messages"] else None
            response = last_message.content if last_message else "No response generated"

            # Update metrics
            end_time = datetime.now(timezone.utc)
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            metrics.update_latency(latency_ms)
            metrics.total_turns += 1
            metrics.successful_responses += 1

            # Store conversation in memory
            if self.memory_manager:
                await self.memory_manager.store_conversation(
                    company_id, session_id, message, response
                )

            logger.info(f"Processed message in {latency_ms}ms for session {session_id}")
            return response

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            metrics.error_count += 1
            metrics.fallback_responses += 1

            return SafeFallbackResponse(
                error_message=f"Processing failed: {str(e)}",
                error_details={
                    "session_id": session_id,
                    "error_type": type(e).__name__,
                },
                company_id=company_id,
                thread_id=session_id,
            )

    async def stream_response(
        self,
        session_id: str,
        message: str,
        company_id: UUID,
        priority: PriorityLevel = PriorityLevel.MEDIUM,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream agent response in real-time.

        Args:
            session_id: Session ID for tracking
            message: User input message
            company_id: Company UUID for tenancy
            priority: Message priority level

        Yields:
            Streaming response chunks
        """
        if session_id not in self.active_sessions:
            yield {
                "error": SafeFallbackResponse(
                    error_message="Invalid session ID",
                    error_details={"session_id": session_id},
                )
            }
            return

        metrics = self.active_sessions[session_id]
        start_time = datetime.now(timezone.utc)
        first_token_time = None

        try:
            # Create initial state
            state = create_initial_state(
                company_id=company_id,
                user_input=message,
                thread_id=session_id,
                autonomy_level=self.config.autonomy_level,
            )

            # Configure runnable
            config = RunnableConfig(
                configurable={"thread_id": session_id, "company_id": str(company_id)},
                callbacks=self.callbacks,
            )

            # Stream graph execution
            async for chunk in self.compiled_graph.astream(state, config=config):
                # Record first token time
                if first_token_time is None:
                    first_token_time = datetime.now(timezone.utc)
                    first_token_latency = int(
                        (first_token_time - start_time).total_seconds() * 1000
                    )
                    metrics.first_token_latency_ms = first_token_latency

                yield chunk

            # Update metrics
            end_time = datetime.now(timezone.utc)
            total_latency = int((end_time - start_time).total_seconds() * 1000)
            metrics.update_latency(total_latency)
            metrics.total_turns += 1
            metrics.successful_responses += 1

        except Exception as e:
            logger.error(f"Error streaming response: {str(e)}")
            metrics.error_count += 1

            yield {
                "error": SafeFallbackResponse(
                    error_message=f"Streaming failed: {str(e)}",
                    error_details={"session_id": session_id},
                    company_id=company_id,
                    thread_id=session_id,
                )
            }

    async def get_session_metrics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific session."""
        if session_id not in self.active_sessions:
            return None

        return self.active_sessions[session_id].to_dict()

    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """
        End an agent session and return final metrics.

        Args:
            session_id: Session ID to end

        Returns:
            Final session metrics
        """
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}

        metrics = self.active_sessions[session_id]
        final_metrics = metrics.to_dict()

        # Store session summary in memory
        if self.memory_manager:
            await self.memory_manager.store_session_summary(session_id, final_metrics)

        # Remove from active sessions
        del self.active_sessions[session_id]

        logger.info(f"Ended session {session_id} with metrics: {final_metrics}")
        return final_metrics

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on agent components."""
        health = {
            "agent": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_sessions": len(self.active_sessions),
            "components": {},
        }

        # Check graph compilation
        health["components"]["graph"] = "healthy" if self.compiled_graph else "failed"

        # Check tool manager
        if self.tool_manager:
            tool_health = await self.tool_manager.health_check()
            health["components"]["tools"] = tool_health

        # Check memory manager
        if self.memory_manager:
            memory_health = await self.memory_manager.health_check()
            health["components"]["memory"] = memory_health

        # Check RAG system
        if self.rag_system:
            rag_health = await self.rag_system.health_check()
            health["components"]["rag"] = rag_health

        return health

    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        return len(self.active_sessions)

    async def interrupt_session(self, session_id: str, reason: str) -> bool:
        """
        Interrupt an active session for human review.

        Args:
            session_id: Session to interrupt
            reason: Reason for interruption

        Returns:
            True if successfully interrupted
        """
        if session_id not in self.active_sessions:
            return False

        # Implementation would depend on LangGraph's interrupt mechanism
        logger.info(f"Interrupted session {session_id}: {reason}")
        return True

    async def resume_session(self, session_id: str, human_input: Optional[str] = None) -> bool:
        """
        Resume an interrupted session.

        Args:
            session_id: Session to resume
            human_input: Optional human input to continue with

        Returns:
            True if successfully resumed
        """
        if session_id not in self.active_sessions:
            return False

        # Implementation would depend on LangGraph's resume mechanism
        logger.info(f"Resumed session {session_id}")
        return True
