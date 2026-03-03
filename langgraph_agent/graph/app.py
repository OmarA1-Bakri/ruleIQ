"""
from __future__ import annotations

Minimal runnable LangGraph application with PostgreSQL checkpointer.
StateGraph with basic node structure and compilation.
"""
import logging
from typing import Dict, Any, Optional, AsyncGenerator
from uuid import UUID, uuid4
from datetime import datetime, timezone
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.runnables import RunnableConfig
from .state import ComplianceAgentState, create_initial_state, update_state_metadata
from ..core.constants import GRAPH_NODES, SLO_P95_LATENCY_MS, DATABASE_CONFIG, AUTONOMY_LEVELS
from ..core.models import GraphMessage, SafeFallbackResponse
logger = logging.getLogger(__name__)

async def router_node(state: ComplianceAgentState) -> ComplianceAgentState:
    """
    Router node - determines which specialized node to route to.
    Minimal implementation for now, will be expanded in Chunk 3.
    """
    logger.info(f"Router processing for company {state['company_id']}")
    state['current_node'] = GRAPH_NODES['router']
    last_message = state['messages'][-1] if state['messages'] else None
    if not last_message:
        state['next_node'] = '__end__'
        return update_state_metadata(state)
    content_lower = last_message.content.lower()
    if any((word in content_lower for word in ['gdpr', 'privacy', 'data protection'])):
        state['next_node'] = GRAPH_NODES['compliance_analyzer']
    elif any((word in content_lower for word in ['obligation', 'requirement', 'must do'])):
        state['next_node'] = GRAPH_NODES['obligation_finder']
    elif any((word in content_lower for word in ['evidence', 'document', 'proof'])):
        state['next_node'] = GRAPH_NODES['evidence_collector']
    elif any((word in content_lower for word in ['review', 'legal', 'lawyer'])):
        state['next_node'] = GRAPH_NODES['legal_reviewer']
    else:
        state['next_node'] = GRAPH_NODES['compliance_analyzer']
    logger.info(f"Router decision: {state['next_node']}")
    return update_state_metadata(state)

async def compliance_analyzer_node(state: ComplianceAgentState) -> ComplianceAgentState:
    """
    Compliance analyzer node - analyzes business for compliance requirements.
    Minimal implementation for now.
    """
    logger.info(f"Compliance analyzer processing for company {state['company_id']}")
    state['current_node'] = GRAPH_NODES['compliance_analyzer']
    response_msg = GraphMessage(role='assistant', content="I'm analyzing your compliance requirements. Based on your inquiry, I'll help identify applicable frameworks and obligations.", timestamp=datetime.now(timezone.utc))
    state['messages'].append(response_msg)
    state['next_node'] = '__end__'
    return update_state_metadata(state)

async def obligation_finder_node(state: ComplianceAgentState) -> ComplianceAgentState:
    """
    Obligation finder node - searches for specific compliance obligations.
    Minimal implementation for now.
    """
    logger.info(f"Obligation finder processing for company {state['company_id']}")
    state['current_node'] = GRAPH_NODES['obligation_finder']
    response_msg = GraphMessage(role='assistant', content="I'm searching for specific compliance obligations relevant to your business. This will include requirements from applicable frameworks.", timestamp=datetime.now(timezone.utc))
    state['messages'].append(response_msg)
    state['next_node'] = '__end__'
    return update_state_metadata(state)

async def evidence_collector_node(state: ComplianceAgentState) -> ComplianceAgentState:
    """
    Evidence collector node - helps gather compliance evidence.
    Minimal implementation for now.
    """
    logger.info(f"Evidence collector processing for company {state['company_id']}")
    state['current_node'] = GRAPH_NODES['evidence_collector']
    response_msg = GraphMessage(role='assistant', content="I'm helping you collect and organize compliance evidence. This includes policies, procedures, and documentation.", timestamp=datetime.now(timezone.utc))
    state['messages'].append(response_msg)
    state['next_node'] = '__end__'
    return update_state_metadata(state)

async def legal_reviewer_node(state: ComplianceAgentState) -> ComplianceAgentState:
    """
    Legal reviewer node - handles legal review requests.
    Minimal implementation for now.
    """
    logger.info(f"Legal reviewer processing for company {state['company_id']}")
    state['current_node'] = GRAPH_NODES['legal_reviewer']
    response_msg = GraphMessage(role='assistant', content="I'm preparing materials for legal review. This ensures compliance decisions meet legal standards.", timestamp=datetime.now(timezone.utc))
    state['messages'].append(response_msg)
    state['next_node'] = '__end__'
    return update_state_metadata(state)

def create_graph() -> StateGraph:
    """
    Create the LangGraph StateGraph with minimal node structure.

    Returns:
        Configured StateGraph ready for compilation
    """
    graph = StateGraph(ComplianceAgentState)
    graph.add_node(GRAPH_NODES['router'], router_node)
    graph.add_node(GRAPH_NODES['compliance_analyzer'], compliance_analyzer_node)
    graph.add_node(GRAPH_NODES['obligation_finder'], obligation_finder_node)
    graph.add_node(GRAPH_NODES['evidence_collector'], evidence_collector_node)
    graph.add_node(GRAPH_NODES['legal_reviewer'], legal_reviewer_node)

    def route_after_router(state: ComplianceAgentState) -> str:
        """Route from router to appropriate specialized node."""
        return state['next_node'] or '__end__'
    graph.add_edge(START, GRAPH_NODES['router'])
    graph.add_conditional_edges(GRAPH_NODES['router'], route_after_router, {GRAPH_NODES['compliance_analyzer']: GRAPH_NODES['compliance_analyzer'], GRAPH_NODES['obligation_finder']: GRAPH_NODES['obligation_finder'], GRAPH_NODES['evidence_collector']: GRAPH_NODES['evidence_collector'], GRAPH_NODES['legal_reviewer']: GRAPH_NODES['legal_reviewer'], '__end__': END})
    graph.add_edge(GRAPH_NODES['compliance_analyzer'], END)
    graph.add_edge(GRAPH_NODES['obligation_finder'], END)
    graph.add_edge(GRAPH_NODES['evidence_collector'], END)
    graph.add_edge(GRAPH_NODES['legal_reviewer'], END)
    return graph

def create_checkpointer(database_url: str) -> PostgresSaver:
    """
    Create PostgreSQL checkpointer for state persistence.

    Args:
        database_url: PostgreSQL connection string

    Returns:
        Configured PostgresSaver
    """
    checkpointer = PostgresSaver.from_conn_string(conn_string=database_url, **DATABASE_CONFIG)
    return checkpointer

def compile_graph(database_url: str, interrupt_before: Optional[list]=None, interrupt_after: Optional[list]=None) -> Any:
    """
    Compile the LangGraph with PostgreSQL checkpointer.

    Args:
        database_url: PostgreSQL connection string
        interrupt_before: Optional list of nodes to interrupt before
        interrupt_after: Optional list of nodes to interrupt after

    Returns:
        Compiled graph ready for execution
    """
    graph = create_graph()
    checkpointer = create_checkpointer(database_url)
    compile_kwargs = {'checkpointer': checkpointer}
    if interrupt_before:
        compile_kwargs['interrupt_before'] = interrupt_before
    if interrupt_after:
        compile_kwargs['interrupt_after'] = interrupt_after
    compiled_graph = graph.compile(**compile_kwargs)
    logger.info('LangGraph compiled successfully with PostgreSQL checkpointer')
    return compiled_graph

async def invoke_graph(compiled_graph: Any, company_id: UUID, user_input: str, thread_id: Optional[str]=None, user_id: Optional[UUID]=None, autonomy_level: int=AUTONOMY_LEVELS['trusted_advisor']) -> Dict[str, Any]:
    """
    Invoke the compiled graph with a new user input.

    Args:
        compiled_graph: Compiled LangGraph
        company_id: Company UUID for tenancy
        user_input: User's input message
        thread_id: Optional thread ID for conversation continuity
        user_id: Optional user ID for audit trails
        autonomy_level: Agent autonomy level

    Returns:
        Final state after graph execution
    """
    if not thread_id:
        thread_id = f'thread_{uuid4()}'
    initial_state = create_initial_state(company_id=company_id, user_input=user_input, thread_id=thread_id, user_id=user_id, autonomy_level=autonomy_level)
    config = RunnableConfig(configurable={'thread_id': thread_id, 'company_id': str(company_id)})
    start_time = datetime.now(timezone.utc)
    try:
        logger.info(f'Invoking graph for company {company_id}, thread {thread_id}')
        final_state = await compiled_graph.ainvoke(initial_state, config=config)
        end_time = datetime.now(timezone.utc)
        latency_ms = int((end_time - start_time).total_seconds() * 1000)
        final_state['latency_ms'] = latency_ms
        if latency_ms > SLO_P95_LATENCY_MS:
            logger.warning(f'SLO violation: {latency_ms}ms > {SLO_P95_LATENCY_MS}ms')
        else:
            logger.info(f'SLO compliant: {latency_ms}ms')
        logger.info(f'Graph execution completed in {latency_ms}ms')
        return final_state
    except Exception as e:
        logger.error(f'Graph execution failed: {str(e)}')
        error_response = SafeFallbackResponse(error_message=f'Graph execution failed: {str(e)}', error_details={'exception_type': type(e).__name__}, company_id=company_id, thread_id=thread_id)
        initial_state['errors'].append(error_response)
        initial_state['error_count'] += 1
        return initial_state

async def stream_graph(compiled_graph: Any, company_id: UUID, user_input: str, thread_id: Optional[str]=None, user_id: Optional[UUID]=None, autonomy_level: int=AUTONOMY_LEVELS['trusted_advisor']) -> AsyncGenerator[Any, None]:
    """
    Stream graph execution for real-time updates.

    Args:
        compiled_graph: Compiled LangGraph
        company_id: Company UUID for tenancy
        user_input: User's input message
        thread_id: Optional thread ID for conversation continuity
        user_id: Optional user ID for audit trails
        autonomy_level: Agent autonomy level

    Yields:
        State updates during graph execution
    """
    if not thread_id:
        thread_id = f'thread_{uuid4()}'
    initial_state = create_initial_state(company_id=company_id, user_input=user_input, thread_id=thread_id, user_id=user_id, autonomy_level=autonomy_level)
    config = RunnableConfig(configurable={'thread_id': thread_id, 'company_id': str(company_id)})
    try:
        logger.info(f'Streaming graph for company {company_id}, thread {thread_id}')
        async for chunk in compiled_graph.astream(initial_state, config=config):
            yield chunk
    except Exception as e:
        logger.error(f'Graph streaming failed: {str(e)}')
        error_response = SafeFallbackResponse(error_message=f'Graph streaming failed: {str(e)}', error_details={'exception_type': type(e).__name__}, company_id=company_id, thread_id=thread_id)
        yield {'error': error_response}
_compiled_graph = None

def get_compiled_graph(database_url: str) -> Any:
    """
    Get or create the compiled graph instance.

    Args:
        database_url: PostgreSQL connection string

    Returns:
        Compiled graph instance
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = compile_graph(database_url)
    return _compiled_graph
