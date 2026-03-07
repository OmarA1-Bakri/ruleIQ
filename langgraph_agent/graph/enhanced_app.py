"""
import logging


logger = logging.getLogger(__name__)
Enhanced LangGraph application with proper state management and error handling.

Phase 1 Implementation: Graph application using enhanced state with reducers.
This module provides the main graph structure with:
- Proper state transitions
- Error recovery mechanisms
- Performance tracking
- Cost monitoring
"""

import asyncio
from typing import Dict, Optional, Any, AsyncIterator
from uuid import UUID
from datetime import datetime, timezone
from langgraph.graph import StateGraph, END

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:
    AsyncPostgresSaver = None
from langgraph.checkpoint.memory import MemorySaver
from langsmith import traceable
from .enhanced_state import (
    EnhancedComplianceState,
    WorkflowStatus,
    StateTransition,
    StateAggregator,
    create_enhanced_initial_state,
)
from .error_handler import ErrorHandlerNode, get_recovery_node
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EnhancedComplianceGraph:
    """
    Enhanced compliance graph with proper state management.
    """

    def __init__(self, checkpointer: Optional[Any] = None) -> None:
        """
        Initialize the enhanced compliance graph.

        Args:
            checkpointer: Optional checkpointer for state persistence
        """
        self.checkpointer = checkpointer or self._create_checkpointer()
        self.error_handler = ErrorHandlerNode()
        self.state_transition = StateTransition()
        self.state_aggregator = StateAggregator()
        self.graph = self._build_graph()

    def _create_checkpointer(self):
        """
        Create appropriate checkpointer based on configuration.

        Returns:
            Checkpointer instance (PostgreSQL or Memory)
        """
        if settings.database_url and AsyncPostgresSaver:
            try:
                db_url = settings.database_url
                if "asyncpg" in db_url:
                    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
                checkpointer = AsyncPostgresSaver.from_conn_string(db_url)
                logger.info("PostgreSQL checkpointer created (setup pending)")
                return checkpointer
            except Exception as e:
                logger.warning(f"Failed to create PostgreSQL checkpointer: {e}")
                logger.info("Falling back to memory checkpointer")
                return MemorySaver()
        else:
            logger.info("Using memory checkpointer")
            return MemorySaver()

    async def async_setup(self) -> None:
        """
        Perform async setup operations.

        This should be called after initialization to complete async setup.
        """
        if hasattr(self.checkpointer, "setup"):
            await self.checkpointer.setup()
            logger.info("PostgreSQL checkpointer setup completed")

    @classmethod
    async def create(cls, checkpointer: Optional[Any] = None) -> Any:
        """
        Factory method to create and properly initialize the graph.

        Args:
            checkpointer: Optional checkpointer for state persistence

        Returns:
            Fully initialized EnhancedComplianceGraph instance
        """
        instance = cls(checkpointer)
        await instance.async_setup()
        return instance

    def _build_graph(self) -> StateGraph:
        """
        Build the enhanced compliance graph structure.

        Returns:
            Configured StateGraph instance
        """
        graph = StateGraph(EnhancedComplianceState)
        graph.add_node("router", self._router_node)
        graph.add_node("profile_builder", self._profile_builder_node)
        graph.add_node("compliance_analyzer", self._compliance_analyzer_node)
        graph.add_node("evidence_collector", self._evidence_collector_node)
        graph.add_node("response_generator", self._response_generator_node)
        graph.add_node("error_handler", self._error_handler_node)
        graph.set_entry_point("router")
        graph.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "profile": "profile_builder",
                "compliance": "compliance_analyzer",
                "evidence": "evidence_collector",
                "response": "response_generator",
                "error": "error_handler",
                "end": END,
            },
        )
        for node_name in [
            "profile_builder",
            "compliance_analyzer",
            "evidence_collector",
            "response_generator",
        ]:
            graph.add_conditional_edges(
                node_name,
                self._check_for_errors,
                {
                    "error_handler": "error_handler",
                    "continue": self._get_next_node_mapping(node_name),
                },
            )
        graph.add_conditional_edges(
            "error_handler",
            self._route_from_error_handler,
            {
                "router": "router",
                "profile_builder": "profile_builder",
                "compliance_analyzer": "compliance_analyzer",
                "evidence_collector": "evidence_collector",
                "response_generator": "response_generator",
                "end": END,
            },
        )
        graph.add_edge("response_generator", END)
        return graph.compile(checkpointer=self.checkpointer)

    @traceable(name="router_node")
    async def _router_node(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """
        Route to the appropriate node based on conversation context.

        Args:
            state: Current state

        Returns:
            Updated state with routing decision
        """
        start_time = datetime.now(timezone.utc)
        try:
            if state["error_count"] >= state["max_retries"]:
                state["next_node"] = "error"
                state["termination_reason"] = "Max errors reached"
                state["should_continue"] = False
                return state
            if state["turn_count"] >= state["max_turns"]:
                state["next_node"] = "end"
                state["termination_reason"] = "Max turns reached"
                state["should_continue"] = False
                return state
            if state["messages"]:
                last_message = state["messages"][-1]
                content = last_message.get("content", "").lower()
                if not state.get("business_profile"):
                    state["next_node"] = "profile"
                elif "compliance" in content or "regulation" in content:
                    state["next_node"] = "compliance"
                elif "evidence" in content or "document" in content:
                    state["next_node"] = "evidence"
                else:
                    state["next_node"] = "response"
            else:
                state["next_node"] = "response"
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            state = self.state_transition.record_transition(
                state, "router", state["next_node"], latency_ms
            )
            state["last_successful_node"] = "router"
            return state
        except Exception as e:
            logger.error(f"Router node error: {e}")
            state["errors"].append(
                {
                    "node": "router",
                    "error": str(e),
                    "type": "routing",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
            state["current_node"] = "router"
            return state

    @traceable(name="profile_builder_node")
    async def _profile_builder_node(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Build or update business profile from conversation.

        Args:
            state: Current state

        Returns:
            Updated state with business profile
        """
        start_time = datetime.now(timezone.utc)
        try:
            profile_data = {
                "industry": None,
                "size": None,
                "location": None,
                "frameworks": [],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
            for message in state["messages"]:
                content = message.get("content", "").lower()
                industries = ["healthcare", "finance", "technology", "retail", "manufacturing"]
                for industry in industries:
                    if industry in content:
                        profile_data["industry"] = industry
                        break
                if "small" in content or "startup" in content:
                    profile_data["size"] = "small"
                elif "medium" in content or "mid-size" in content:
                    profile_data["size"] = "medium"
                elif "large" in content or "enterprise" in content:
                    profile_data["size"] = "large"
            state["business_profile"].update(profile_data)
            state["messages"].append(
                {
                    "role": "system",
                    "content": f"Business profile updated: {profile_data}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            state["node_latencies"]["profile_builder"] = latency_ms
            state["last_successful_node"] = "profile_builder"
            return state
        except Exception as e:
            logger.error(f"Profile builder error: {e}")
            state["errors"].append(
                {
                    "node": "profile_builder",
                    "error": str(e),
                    "type": "processing",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
            state["current_node"] = "profile_builder"
            return state

    @traceable(name="compliance_analyzer_node")
    async def _compliance_analyzer_node(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Analyze compliance requirements based on profile.

        Args:
            state: Current state

        Returns:
            Updated state with compliance analysis
        """
        start_time = datetime.now(timezone.utc)
        try:
            frameworks = []
            industry = state["business_profile"].get("industry")
            if industry == "healthcare":
                frameworks.extend(["HIPAA", "HITECH"])
            elif industry == "finance":
                frameworks.extend(["SOX", "PCI-DSS"])
            location = state["business_profile"].get("location") or ""
            if location and ("eu" in location.lower() or "europe" in location.lower()):
                frameworks.append("GDPR")
            if location and ("california" in location.lower() or "ca" in location.lower()):
                frameworks.append("CCPA")
            state["compliance_data"]["frameworks"] = frameworks
            state["compliance_data"]["obligations"] = [
                {"id": f"ob_{i}", "framework": fw, "title": f"{fw} Compliance"}
                for i, fw in enumerate(frameworks)
            ]
            state["messages"].append(
                {
                    "role": "assistant",
                    "content": f"Based on your profile, you need to comply with: {', '.join(frameworks)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["token_usage"]["input"] += 100
            state["token_usage"]["output"] += 50
            state["token_usage"]["total"] += 150
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            state["node_latencies"]["compliance_analyzer"] = latency_ms
            state["last_successful_node"] = "compliance_analyzer"
            return state
        except Exception as e:
            logger.error(f"Compliance analyzer error: {e}")
            state["errors"].append(
                {
                    "node": "compliance_analyzer",
                    "error": str(e),
                    "type": "processing",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
            state["current_node"] = "compliance_analyzer"
            return state

    @traceable(name="evidence_collector_node")
    async def _evidence_collector_node(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Collect evidence for compliance requirements.

        Args:
            state: Current state

        Returns:
            Updated state with evidence collection
        """
        start_time = datetime.now(timezone.utc)
        try:
            evidence = []
            for obligation in state["compliance_data"].get("obligations", []):
                evidence.append(
                    {
                        "id": f"ev_{obligation['id']}",
                        "obligation_id": obligation["id"],
                        "type": "document",
                        "status": "pending",
                        "hash": f"hash_{obligation['id']}",
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            state["compliance_data"]["evidence"] = evidence
            state["tool_outputs"]["evidence_collector"] = {
                "evidence_count": len(evidence),
                "status": "completed",
            }
            state["tool_call_count"] += 1
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            state["node_latencies"]["evidence_collector"] = latency_ms
            state["last_successful_node"] = "evidence_collector"
            return state
        except Exception as e:
            logger.error(f"Evidence collector error: {e}")
            state["errors"].append(
                {
                    "node": "evidence_collector",
                    "error": str(e),
                    "type": "processing",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
            state["current_node"] = "evidence_collector"
            return state

    @traceable(name="response_generator_node")
    async def _response_generator_node(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """
        Generate final response based on analysis.

        Args:
            state: Current state

        Returns:
            Updated state with response
        """
        start_time = datetime.now(timezone.utc)
        try:
            summary = self.state_aggregator.get_compliance_summary(state)
            response = f"\nBased on our analysis:\n- Identified {summary['frameworks_identified']} compliance frameworks\n- Found {summary['obligations_found']} obligations\n- Collected {summary['evidence_collected']} evidence items\n\nYour compliance journey is {state['workflow_status'].value}.\n"
            state["messages"].append(
                {
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            tokens = state["token_usage"]["total"]
            state["estimated_cost"] = tokens * 1e-05
            state["workflow_status"] = WorkflowStatus.COMPLETED
            state["end_time"] = datetime.now(timezone.utc)
            state["should_continue"] = False
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            state["node_latencies"]["response_generator"] = latency_ms
            state["last_successful_node"] = "response_generator"
            return state
        except Exception as e:
            logger.error(f"Response generator error: {e}")
            state["errors"].append(
                {
                    "node": "response_generator",
                    "error": str(e),
                    "type": "generation",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
            state["current_node"] = "response_generator"
            return state

    @traceable(name="error_handler_node")
    async def _error_handler_node(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """
        PROPERLY handle errors with retry logic and state updates.

        This method implements:
        - Retry count increment
        - Exponential backoff calculation
        - Workflow status updates based on retry logic
        - Error details storage in state
        - Integration with centralized error handler

        Args:
            state: Current state with errors

        Returns:
            Updated state with error handling and retry decision
        """
        from datetime import datetime

        state["retry_count"] = state.get("retry_count", 0) + 1
        max_retries = state.get("max_retries", 3)
        logger.info(
            f"Error handler invoked - errors: {state.get('error_count', 0)}, retries: {state['retry_count']}/{max_retries}"
        )
        if state["retry_count"] <= max_retries:
            wait_time = min(2 ** (state["retry_count"] - 1), 30)
            logger.info(
                f"Retrying workflow - attempt {state['retry_count']}/{max_retries}, waiting {wait_time}s"
            )
            await asyncio.sleep(wait_time)
            state["workflow_status"] = WorkflowStatus.RETRYING
            state["should_continue"] = True
            state["history"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "action": "error_retry",
                    "retry_count": state["retry_count"],
                    "wait_time": wait_time,
                    "error_count": state.get("error_count", 0),
                }
            )
            if state.get("errors"):
                state["last_error_time"] = datetime.now()
                state["metadata"]["last_error"] = state["errors"][-1] if state["errors"] else None
            try:
                state = await self.error_handler.process(state)
            except Exception as e:
                logger.warning(f"Error handler processing failed: {e}, continuing with retry")
        else:
            logger.error(f"Max retries ({max_retries}) exceeded - workflow failed")
            state["workflow_status"] = WorkflowStatus.FAILED
            state["should_continue"] = False
            state["history"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "action": "workflow_failed",
                    "reason": "max_retries_exceeded",
                    "retry_count": state["retry_count"],
                    "total_errors": state.get("error_count", 0),
                }
            )
            state["metadata"]["failure_reason"] = "Maximum retry attempts exceeded"
            state["metadata"]["final_error_count"] = state.get("error_count", 0)
            try:
                state = await self.error_handler.process(state)
            except Exception as e:
                logger.error(f"Error handler final processing failed: {e}")
        state["updated_at"] = datetime.now()
        return state

    def _route_decision(self, state: EnhancedComplianceState) -> str:
        """
        Determine next node based on state.

        Args:
            state: Current state

        Returns:
            Next node name
        """
        return state.get("next_node", "end")

    def _check_for_errors(self, state: EnhancedComplianceState) -> str:
        """
        Check if errors exist and should route to error handler.

        Args:
            state: Current state

        Returns:
            "error_handler" if errors exist, "continue" otherwise
        """
        if state.get("errors") and state.get("error_count", 0) > 0:
            if state.get("retry_count", 0) < state.get("max_retries", 3):
                return "error_handler"
        return "continue"

    def _get_next_node_mapping(self, current_node: str) -> str:
        """
        Get the default next node for normal flow.

        Args:
            current_node: Name of current node

        Returns:
            Name of next node in normal flow
        """
        mapping = {
            "profile_builder": "compliance_analyzer",
            "compliance_analyzer": "evidence_collector",
            "evidence_collector": "response_generator",
            "response_generator": END,
        }
        return mapping.get(current_node, END)

    def _route_from_error_handler(self, state: EnhancedComplianceState) -> str:
        """
        Route from error handler to recovery node.

        Args:
            state: Current state

        Returns:
            Name of recovery node
        """
        if state.get("workflow_status") == WorkflowStatus.FAILED:
            return END
        return get_recovery_node(state)

    async def run(
        self,
        session_id: str,
        company_id: UUID,
        user_input: str,
        thread_id: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Run the enhanced compliance graph.

        Args:
            session_id: Session identifier
            company_id: Company UUID
            user_input: User's input message
            thread_id: Optional conversation thread ID
            **kwargs: Additional configuration

        Yields:
            State updates as the graph executes
        """
        initial_state = create_enhanced_initial_state(
            session_id=session_id,
            company_id=company_id,
            initial_message=user_input,
            thread_id=thread_id,
            **kwargs,
        )
        config = {
            "configurable": {
                "thread_id": thread_id or session_id,
                "checkpoint_ns": f"compliance_{company_id}",
            }
        }
        try:
            async for event in self.graph.astream(initial_state, config):
                for node, update in event.items():
                    yield {
                        "node": node,
                        "update": update,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    if not update.get("should_continue", True):
                        break
            final_state = await self.graph.aget_state(config)
            yield {
                "type": "summary",
                "conversation": self.state_aggregator.get_conversation_summary(final_state.values),
                "compliance": self.state_aggregator.get_compliance_summary(final_state.values),
                "performance": self.state_aggregator.get_performance_metrics(final_state.values),
            }
        except Exception as e:
            logger.error(f"Graph execution error: {e}")
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
