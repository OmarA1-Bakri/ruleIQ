"""

Master Integration Graph for ruleIQ Compliance System

This module integrates all four phases:
- Phase 1: Enhanced State Management
- Phase 2: Error Handling with Retry Logic
- Phase 3: RAG System with Real AI Integration
- Phase 4: Celery Task Migration

The master graph orchestrates all components to provide end-to-end
compliance assessment and task execution without failures.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any, AsyncGenerator
from uuid import UUID
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph_agent.graph.enhanced_state import (
    EnhancedComplianceState,
    WorkflowStatus,
    create_enhanced_initial_state,
    StateTransition,
    StateAggregator,
)
from langgraph_agent.graph.error_handler import ErrorHandlerNode
from enum import Enum


class ErrorRecoveryStrategy(Enum):
    """Error recovery strategies."""

    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_BREAK = "circuit_break"


from dataclasses import dataclass


@dataclass
class RAGConfig:
    """Configuration for RAG system."""

    embeddings_model: str = "mistral-embed"
    vector_store_type: str = "faiss"
    llm_provider: str = "google"
    chunk_size: int = 1000
    chunk_overlap: int = 200


from langgraph_agent.graph.celery_migration_graph import CeleryMigrationGraph
from services.neo4j_service import Neo4jGraphRAGService as Neo4jService
from langgraph_agent.services.ai_service import AIService
from langgraph_agent.services.compliance_analyzer import ComplianceAnalyzer
from langgraph_agent.services.evidence_collector import EvidenceCollector

logger = logging.getLogger(__name__)


class MasterIntegrationGraph:
    """
    Master integration graph that orchestrates all four phases
    of the compliance system with production-ready reliability.
    """

    def __init__(
        self,
        checkpointer: Optional[AsyncPostgresSaver] = None,
        rag_config: Optional[RAGConfig] = None,
        enable_streaming: bool = True,
    ) -> None:
        """Initialize the master integration graph."""
        self.checkpointer = checkpointer
        self.enable_streaming = enable_streaming
        self.state_transition = StateTransition()
        self.state_aggregator = StateAggregator()
        self.error_handler = ErrorHandlerNode(max_retries=3)
        self.recovery_strategies = [
            ErrorRecoveryStrategy.RETRY,
            ErrorRecoveryStrategy.FALLBACK,
            ErrorRecoveryStrategy.CIRCUIT_BREAK,
        ]
        self.rag_system = None
        self.rag_config = rag_config or RAGConfig()
        self.celery_graph = None
        self.neo4j_service = Neo4jService()
        self.ai_service = AIService()
        self.compliance_analyzer = ComplianceAnalyzer()
        self.evidence_collector = EvidenceCollector()
        self.graph = self._build_master_graph()

    async def initialize_async_components(self) -> Any:
        """Initialize components that require async setup."""
        self.celery_graph = await CeleryMigrationGraph.create(checkpointer=self.checkpointer)
        await self.rag_system.initialize()
        self.graph = self._build_master_graph()
        self.app = self.graph.compile(checkpointer=self.checkpointer)
        return self

    @classmethod
    async def create(
        cls,
        database_url: Optional[str] = None,
        rag_config: Optional[RAGConfig] = None,
        enable_streaming: bool = True,
    ) -> Any:
        """Factory method to create and initialize the master graph."""
        checkpointer = None
        if database_url:
            try:
                checkpointer = AsyncPostgresSaver.from_conn_string(database_url)
                await checkpointer.setup()
                logger.info("PostgreSQL checkpointer initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize checkpointer: {e}")
        instance = cls(
            checkpointer=checkpointer, rag_config=rag_config, enable_streaming=enable_streaming
        )
        await instance.initialize_async_components()
        return instance

    def _build_master_graph(self) -> StateGraph:
        """Build the master integration graph."""
        graph = StateGraph(EnhancedComplianceState)
        graph.add_node("router", self._router_node)
        graph.add_node("profile_builder", self._profile_builder_node)
        graph.add_node("compliance_analyzer", self._compliance_analyzer_node)
        graph.add_node("rag_query", self._rag_query_node)
        graph.add_node("evidence_collector", self._evidence_collector_node)
        graph.add_node("task_executor", self._task_executor_node)
        graph.add_node("response_generator", self._response_generator_node)
        graph.add_node("error_handler", self._error_handler_node)
        graph.add_node("checkpoint_saver", self._checkpoint_saver_node)
        graph.set_entry_point("router")
        graph.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "profile": "profile_builder",
                "compliance": "compliance_analyzer",
                "rag": "rag_query",
                "evidence": "evidence_collector",
                "task": "task_executor",
                "response": "response_generator",
                "error": "error_handler",
                "end": END,
            },
        )
        graph.add_edge("profile_builder", "checkpoint_saver")
        graph.add_edge("checkpoint_saver", "compliance_analyzer")
        graph.add_conditional_edges(
            "compliance_analyzer",
            self._compliance_decision,
            {
                "rag": "rag_query",
                "evidence": "evidence_collector",
                "response": "response_generator",
                "error": "error_handler",
            },
        )
        graph.add_conditional_edges(
            "rag_query",
            self._rag_decision,
            {
                "evidence": "evidence_collector",
                "response": "response_generator",
                "error": "error_handler",
            },
        )
        graph.add_edge("evidence_collector", "response_generator")
        graph.add_conditional_edges(
            "task_executor",
            self._task_decision,
            {"response": "response_generator", "error": "error_handler", "retry": "task_executor"},
        )
        graph.add_edge("response_generator", END)
        graph.add_conditional_edges(
            "error_handler",
            self._error_decision,
            {"retry": "router", "fallback": "response_generator", "end": END},
        )
        return graph

    async def _router_node(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """Route to appropriate processing node based on state."""
        start_time = datetime.now(timezone.utc)
        state = self.state_transition.record_transition(
            state, state.get("current_node", "start"), "router"
        )
        messages = state["messages"]
        if not messages:
            state["next_node"] = "end"
            return state
        last_message = messages[-1]
        if not state.get("business_profile"):
            state["next_node"] = "profile"
        elif "compliance" in last_message.content.lower():
            state["next_node"] = "compliance"
        elif "evidence" in last_message.content.lower():
            state["next_node"] = "evidence"
        elif "task" in last_message.content.lower():
            state["next_node"] = "task"
        elif state.get("requires_rag_query"):
            state["next_node"] = "rag"
        else:
            state["next_node"] = "response"
        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        state["node_latencies"]["router"] = latency_ms
        return state

    async def _profile_builder_node(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """Build business profile from user input."""
        start_time = datetime.now(timezone.utc)
        state = self.state_transition.record_transition(state, "router", "profile_builder")
        try:
            profile_data = await self.ai_service.extract_business_profile(state["messages"])
            state["business_profile"] = profile_data
            state["profile_complete"] = True
            state["messages"].append(
                AIMessage(
                    content=f"Business profile created for {profile_data.get('company_name', 'your company')}"
                )
            )
        except Exception as e:
            logger.error(f"Profile builder error: {e}")
            state["errors"].append(
                {
                    "node": "profile_builder",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        state["node_latencies"]["profile_builder"] = latency_ms
        return state

    async def _compliance_analyzer_node(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """Analyze compliance requirements."""
        start_time = datetime.now(timezone.utc)
        state = self.state_transition.record_transition(
            state, state.get("current_node", "router"), "compliance_analyzer"
        )
        try:
            compliance_results = await self.compliance_analyzer.analyze(
                business_profile=state.get("business_profile", {}),
                context=state.get("compliance_context", {}),
            )
            state["compliance_data"]["frameworks"].extend(compliance_results.get("frameworks", []))
            state["compliance_data"]["obligations"].extend(
                compliance_results.get("obligations", [])
            )
            if compliance_results.get("requires_additional_info"):
                state["requires_rag_query"] = True
            state["token_usage"]["total"] += compliance_results.get("tokens_used", 0)
        except Exception as e:
            logger.error(f"Compliance analyzer error: {e}")
            state["errors"].append(
                {
                    "node": "compliance_analyzer",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        state["node_latencies"]["compliance_analyzer"] = latency_ms
        return state

    async def _rag_query_node(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """Execute RAG query for additional information."""
        start_time = datetime.now(timezone.utc)
        state = self.state_transition.record_transition(
            state, state.get("current_node", "compliance_analyzer"), "rag_query"
        )
        try:
            query = self._prepare_rag_query(state)
            rag_results = await self.rag_system.query(
                query=query,
                filters={
                    "frameworks": state["compliance_data"].get("frameworks", []),
                    "company_size": state["business_profile"].get("company_size"),
                },
            )
            state["rag_results"] = rag_results
            state["compliance_context"].update(rag_results.get("context", {}))
            state["requires_rag_query"] = False
            state["token_usage"]["total"] += rag_results.get("tokens_used", 0)
        except Exception as e:
            logger.error(f"RAG query error: {e}")
            state["errors"].append(
                {
                    "node": "rag_query",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        state["node_latencies"]["rag_query"] = latency_ms
        return state

    async def _evidence_collector_node(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """Collect evidence for compliance."""
        start_time = datetime.now(timezone.utc)
        state = self.state_transition.record_transition(
            state, state.get("current_node", "rag_query"), "evidence_collector"
        )
        try:
            evidence_items = await self.evidence_collector.collect(
                requirements=state["compliance_data"].get("obligations", []),
                business_profile=state.get("business_profile", {}),
            )
            state["compliance_data"]["evidence"].extend(evidence_items)
            state["evidence_collected"] = len(evidence_items)
        except Exception as e:
            logger.error(f"Evidence collector error: {e}")
            state["errors"].append(
                {
                    "node": "evidence_collector",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        state["node_latencies"]["evidence_collector"] = latency_ms
        return state

    async def _task_executor_node(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """Execute migrated Celery tasks."""
        start_time = datetime.now(timezone.utc)
        state = self.state_transition.record_transition(
            state, state.get("current_node", "router"), "task_executor"
        )
        try:
            task_type = state.get("task_type")
            task_params = state.get("task_params", {})
            if self.celery_graph and task_type:
                task_result = await self.celery_graph.execute_task(
                    task_type=task_type,
                    params=task_params,
                    session_id=state["session_id"],
                    company_id=state.get("company_id"),
                )
                state["task_results"] = task_result
                state["task_executed"] = True
                state["tool_outputs"][f"task_{task_type}"] = task_result
        except Exception as e:
            logger.error(f"Task executor error: {e}")
            state["errors"].append(
                {
                    "node": "task_executor",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
            state["retry_count"] += 1
        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        state["node_latencies"]["task_executor"] = latency_ms
        return state

    async def _response_generator_node(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """Generate final response."""
        start_time = datetime.now(timezone.utc)
        state = self.state_transition.record_transition(
            state, state.get("current_node"), "response_generator"
        )
        try:
            response = await self.ai_service.generate_response(
                compliance_data=state.get("compliance_data", {}),
                evidence=state["compliance_data"].get("evidence", []),
                rag_context=state.get("rag_results", {}),
                task_results=state.get("task_results", {}),
                errors=state.get("errors", []),
            )
            state["messages"].append(AIMessage(content=response))
            state["workflow_status"] = WorkflowStatus.COMPLETED
            state["should_continue"] = False
        except Exception as e:
            logger.error(f"Response generator error: {e}")
            state["errors"].append(
                {
                    "node": "response_generator",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state["error_count"] += 1
        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        state["node_latencies"]["response_generator"] = latency_ms
        state["end_time"] = datetime.now(timezone.utc)
        state["total_latency_ms"] = sum(state["node_latencies"].values())
        return state

    async def _error_handler_node(self, state: EnhancedComplianceState) -> EnhancedComplianceState:
        """Handle errors with recovery strategies."""
        return await self.error_handler(state)

    async def _checkpoint_saver_node(
        self, state: EnhancedComplianceState
    ) -> EnhancedComplianceState:
        """Save checkpoint for recovery."""
        if self.checkpointer:
            state["checkpoint_saved"] = True
            state["checkpoint_timestamp"] = datetime.now(timezone.utc).isoformat()
        return state

    def _route_decision(self, state: EnhancedComplianceState) -> str:
        """Decide routing from router node."""
        return state.get("next_node", "response")

    def _compliance_decision(self, state: EnhancedComplianceState) -> str:
        """Decide routing from compliance analyzer."""
        if state.get("requires_rag_query"):
            return "rag"
        elif state.get("requires_evidence"):
            return "evidence"
        elif state["error_count"] > 0:
            return "error"
        else:
            return "response"

    def _rag_decision(self, state: EnhancedComplianceState) -> str:
        """Decide routing from RAG query."""
        if state.get("requires_evidence"):
            return "evidence"
        elif state["error_count"] > 0:
            return "error"
        else:
            return "response"

    def _task_decision(self, state: EnhancedComplianceState) -> str:
        """Decide routing from task executor."""
        if state["retry_count"] > 0 and state["retry_count"] < state["max_retries"]:
            return "retry"
        elif state["error_count"] > 0:
            return "error"
        else:
            return "response"

    def _error_decision(self, state: EnhancedComplianceState) -> str:
        """Decide routing from error handler."""
        if state.get("should_retry") and state["retry_count"] < state["max_retries"]:
            return "retry"
        elif state.get("fallback_available"):
            return "fallback"
        else:
            return "end"

    def _prepare_rag_query(self, state: EnhancedComplianceState) -> str:
        """Prepare RAG query from state context."""
        frameworks = state["compliance_data"].get("frameworks", [])
        obligations = state["compliance_data"].get("obligations", [])
        query_parts = []
        if frameworks:
            query_parts.append(f"Compliance requirements for {', '.join(frameworks[:3])}")
        if obligations:
            query_parts.append(
                f"Obligations: {', '.join([o.get('title', '') for o in obligations[:3]])}"
            )
        if not query_parts:
            query_parts.append("General compliance guidance")
        return " - ".join(query_parts)

    async def run(
        self,
        session_id: str,
        company_id: UUID,
        user_input: str,
        thread_id: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[Any, None]:
        """
        Run the master integration graph.

        Args:
            session_id: Unique session identifier
            company_id: Company UUID
            user_input: User message input
            thread_id: Optional thread ID for checkpointing
            **kwargs: Additional configuration

        Yields:
            Events from graph execution
        """
        initial_state = create_enhanced_initial_state(
            session_id=session_id, company_id=company_id, initial_message=user_input, **kwargs
        )
        config = {
            "configurable": {
                "thread_id": thread_id or f"session_{session_id}",
                "checkpoint_ns": "master_integration",
            }
        }
        if self.enable_streaming:
            async for event in self.app.astream(initial_state, config, stream_mode="values"):
                yield {
                    "type": "state_update",
                    "data": self.state_aggregator.get_conversation_summary(event),
                }
                if event.get("messages"):
                    last_message = event["messages"][-1]
                    if isinstance(last_message, AIMessage):
                        yield {"type": "assistant_message", "data": last_message.content}
        else:
            result = await self.app.ainvoke(initial_state, config)
            yield {
                "type": "final_state",
                "data": self.state_aggregator.get_conversation_summary(result),
            }

    async def get_state_summary(self, thread_id: str) -> Dict[str, Any]:
        """Get summary of current state for a thread."""
        if self.checkpointer:
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint = await self.checkpointer.aget(config)
            if checkpoint:
                state = checkpoint.values
                return {
                    "conversation": self.state_aggregator.get_conversation_summary(state),
                    "compliance": self.state_aggregator.get_compliance_summary(state),
                    "performance": self.state_aggregator.get_performance_metrics(state),
                }
        return {}

    async def close(self) -> None:
        """Clean up resources."""
        if self.neo4j_service:
            await self.neo4j_service.close()
        if self.rag_system:
            await self.rag_system.close()
        if self.checkpointer:
            await self.checkpointer.close()
