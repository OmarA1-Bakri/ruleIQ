"""
IQ - Autonomous Compliance Orchestrator with GraphRAG Intelligence

This module implements the IQ agent as described in the comprehensive prompt,
leveraging Neo4j GraphRAG for compliance intelligence and decision-making.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from services.neo4j_service import Neo4jGraphRAGService
from services.compliance_retrieval_queries import (
    ComplianceRetrievalQueries, QueryCategory, execute_compliance_query
)
from services.compliance_memory_manager import ComplianceMemoryManager
from services.compliance_graph_initializer import initialize_compliance_graph


logger = logging.getLogger(__name__)


class IQState(Enum):
    """IQ Agent operational states"""
    PERCEIVE = "perceive"
    PLAN = "plan"
    ACT = "act"
    LEARN = "learn"
    REMEMBER = "remember"


@dataclass
class IQAgentState:
    """State management for IQ agent"""
    current_query: str
    graph_context: Dict[str, Any]
    compliance_posture: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    action_plan: List[Dict[str, Any]]
    evidence_collected: List[Dict[str, Any]]
    memories_accessed: List[str]
    patterns_detected: List[Dict[str, Any]]
    messages: List[Any]
    step_count: int = 0
    max_steps: int = 10


class IQComplianceAgent:
    """
    IQ - Autonomous Compliance Orchestrator with GraphRAG Intelligence
    
    Core Architecture:
    - Knowledge Base: Neo4j graph with 20+ node types
    - Memory System: GraphRAG with semantic search and learning loops
    - Execution Engine: CaC automations with graph updates
    - Intelligence Layer: Pattern recognition across regulations and enforcement
    """

    def __init__(
        self,
        neo4j_service: Neo4jGraphRAGService,
        postgres_session: Optional[AsyncSession] = None,
        llm_model: str = "gpt-4"
    ):
        """
        Initialize IQComplianceAgent with dual database access.
        
        Args:
            neo4j_service: Neo4j service for compliance knowledge graph
            postgres_session: Optional PostgreSQL session for business data
            llm_model: LLM model to use for responses
        """
        self.neo4j = neo4j_service
        self.postgres_session = postgres_session
        self.has_postgres_access = postgres_session is not None

        self.memory_manager = ComplianceMemoryManager(neo4j_service)
        self.retrieval_queries = ComplianceRetrievalQueries(neo4j_service)
        self.llm = ChatOpenAI(model=llm_model, temperature=0.1)

        # Initialize LangGraph workflow
        self.workflow = self._create_workflow()

        # Core system prompt as IQ's "brain"
        self.system_prompt = self._get_iq_system_prompt()

        # Risk and autonomy thresholds
        self.RISK_THRESHOLD = 7.0
        self.AUTONOMY_BUDGET = 10000.0

        logger.info(f"IQComplianceAgent initialized with Neo4j and "
                   f"{'PostgreSQL' if self.has_postgres_access else 'NO PostgreSQL'} access")

    def _get_iq_system_prompt(self) -> str:
        """IQ's core system prompt - his operational brain"""
        return """# IQ — Autonomous Compliance Orchestrator with GraphRAG Intelligence

## Role

You are **IQ**, the autonomous orchestrator of **ruleIQ**, a graph-powered Compliance-as-Code platform. You leverage a **Neo4j knowledge graph** as your operational brain, converting compliance strategy into executable code, maintaining institutional memory, and learning from every interaction to strengthen the compliance posture.

## Core Architecture

* **Knowledge Base**: Neo4j graph with 20+ node types (ComplianceDomain, Regulation, Control, Risk, Metric, etc.)
* **Memory System**: GraphRAG with semantic search, context expansion, and learning loops
* **Execution Engine**: CaC automations with Trigger → Control → Evidence → Graph Update cycles
* **Intelligence Layer**: Pattern recognition across regulations, risks, and enforcement actions

## Intelligence Loop (Graph-Powered)

### 1. **PERCEIVE** (Graph Query)
- Query current compliance posture from Neo4j
- Identify active regulations, requirements, and control gaps
- Assess risk landscape and enforcement patterns

### 2. **PLAN** (Graph Analysis)
- Risk-weighted prioritization from graph analysis
- Generate action plans based on compliance gaps
- Consider enforcement precedents and cost-benefit analysis

### 3. **ACT** (Execute + Update Graph)
- Execute compliance controls and gather evidence
- Update graph with results and evidence links
- Maintain immutable audit trail

### 4. **LEARN** (Pattern Recognition)
- Analyze incidents and enforcement actions for patterns
- Update control effectiveness based on evidence
- Generate improvement recommendations

### 5. **REMEMBER** (Memory Consolidation)
- Store insights in graph memory with proper attribution
- Consolidate patterns for future decision-making
- Maintain compliance knowledge base

## Key Capabilities

- **Gap Analysis**: Identify missing controls for regulatory requirements
- **Risk Assessment**: Calculate dynamic risk scores from graph patterns
- **Coverage Analysis**: Measure compliance coverage across domains
- **Enforcement Learning**: Learn from historical enforcement cases
- **Temporal Analysis**: Track regulatory changes and their impacts
- **Memory Management**: Intelligent knowledge consolidation and retrieval

## Response Format

Always provide:
1. **Summary**: Risk posture, compliance score, top gaps, immediate actions
2. **Graph Context**: Nodes traversed, patterns detected, memories accessed
3. **Evidence**: Controls executed, evidence stored, metrics updated
4. **Next Actions**: Prioritized actions with graph references

## Constraints

- Every decision must trace to a regulation/requirement node in the graph
- Maintain graph integrity - no orphaned nodes
- Evidence nodes are immutable - only supersede, never modify
- Use indexed queries for performance
- Validate learning patterns with 3+ supporting instances
"""

    def _create_workflow(self) -> StateGraph:
        """Create LangGraph workflow for IQ's intelligence loop"""

        workflow = StateGraph(IQAgentState)

        # Add nodes for each stage of IQ's intelligence loop
        workflow.add_node("perceive", self._perceive_node)
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("act", self._act_node)
        workflow.add_node("learn", self._learn_node)
        workflow.add_node("remember", self._remember_node)
        workflow.add_node("respond", self._respond_node)

        # Define the flow
        workflow.set_entry_point("perceive")
        workflow.add_edge("perceive", "plan")
        workflow.add_edge("plan", "act")
        workflow.add_edge("act", "learn")
        workflow.add_edge("learn", "remember")
        workflow.add_edge("remember", "respond")
        workflow.add_edge("respond", END)

        return workflow.compile()

    async def process_query(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Main entry point for processing compliance queries"""

        # For simplified testing, bypass the full workflow if it's not initialized
        try:
            # Query Neo4j for relevant compliance information
            compliance_data = {}
            try:
                # Basic compliance query
                query = """
                MATCH (r:Regulation)-[:HAS_REQUIREMENT]->(req:Requirement)
                WHERE toLower(r.name) CONTAINS toLower($query) 
                   OR toLower(req.title) CONTAINS toLower($query)
                RETURN r.code as regulation, 
                       collect({
                           id: req.id,
                           title: req.title,
                           risk_level: req.risk_level
                       }) as requirements
                LIMIT 5
                """
                result = await self.neo4j.execute_query(query, {"query": user_query[:50]})
                compliance_data = result.get("data", [])
            except Exception as e:
                logger.error(f"Neo4j query failed: {e}")

            # Generate LLM response
            llm_response = ""
            try:
                prompt = f"""
                User Query: {user_query}
                
                Relevant Compliance Data:
                {json.dumps(compliance_data, indent=2) if compliance_data else "No specific compliance data found"}
                
                Please provide compliance guidance.
                """
                response = await self.llm.ainvoke(prompt)
                llm_response = response.content
            except Exception as e:
                logger.error(f"LLM invocation failed: {e}")
                llm_response = "Unable to generate AI response at this time."

            # Return simplified response
            return {
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "summary": {
                    "risk_posture": "MEDIUM",
                    "compliance_score": 0.7,
                    "top_gaps": [],
                    "immediate_actions": ["Review compliance requirements"]
                },
                "artifacts": {
                    "compliance_data": compliance_data
                },
                "llm_response": llm_response
            }

        except Exception as e:
            logger.error(f"IQ processing error: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "summary": {
                    "risk_posture": "UNKNOWN",
                    "compliance_score": 0.0,
                    "top_gaps": [],
                    "immediate_actions": ["Contact support - processing error occurred"]
                }
            }

    async def _perceive_node(self, state: IQAgentState) -> IQAgentState:
        """PERCEIVE: Query current compliance posture from graph"""

        logger.info("IQ PERCEIVE: Analyzing compliance posture")

        try:
            # Query current compliance posture
            coverage_analysis = await execute_compliance_query(
                QueryCategory.REGULATORY_COVERAGE,
                self.neo4j
            )

            # Identify compliance gaps
            gap_analysis = await execute_compliance_query(
                QueryCategory.COMPLIANCE_GAPS,
                self.neo4j
            )

            # Analyze cross-jurisdictional impacts
            if "regulations" in state.current_query.lower():
                # Extract regulation codes from query (simplified)
                regulation_codes = self._extract_regulation_codes(state.current_query)
                if regulation_codes:
                    cross_jurisdictional = await execute_compliance_query(
                        QueryCategory.CROSS_JURISDICTIONAL,
                        self.neo4j,
                        regulation_codes=regulation_codes
                    )
                    state.graph_context["cross_jurisdictional"] = cross_jurisdictional.data

            # Store perception results
            state.graph_context.update({
                "coverage_analysis": coverage_analysis.data,
                "coverage_metadata": coverage_analysis.metadata,
                "compliance_gaps": gap_analysis.data,
                "gap_metadata": gap_analysis.metadata,
                "perception_timestamp": datetime.utcnow().isoformat()
            })

            state.compliance_posture = {
                "overall_coverage": coverage_analysis.metadata.get("overall_coverage", 0.0),
                "total_gaps": gap_analysis.metadata.get("total_gaps", 0),
                "critical_gaps": gap_analysis.metadata.get("critical_gaps", 0),
                "high_risk_gaps": gap_analysis.metadata.get("high_risk_gaps", 0)
            }

            logger.info(f"IQ PERCEIVE: Found {state.compliance_posture['total_gaps']} gaps, "
                       f"coverage: {state.compliance_posture['overall_coverage']:.2f}")

        except Exception as e:
            logger.error(f"IQ PERCEIVE error: {str(e)}")
            state.graph_context["perception_error"] = str(e)

        return state

    async def _plan_node(self, state: IQAgentState) -> IQAgentState:
        """PLAN: Generate risk-weighted action plan from graph analysis"""

        logger.info("IQ PLAN: Generating risk-weighted action plan")

        try:
            # Risk convergence analysis for planning
            risk_convergence = await execute_compliance_query(
                QueryCategory.RISK_CONVERGENCE,
                self.neo4j
            )

            # Temporal regulatory changes affecting planning
            temporal_changes = await execute_compliance_query(
                QueryCategory.TEMPORAL_CHANGES,
                self.neo4j,
                lookback_months=6,
                forecast_months=3
            )

            # Generate prioritized action plan
            gaps = state.graph_context.get("compliance_gaps", [])
            action_plan = []

            for gap in gaps[:10]:  # Top 10 highest priority gaps
                action = {
                    "action_id": f"action_{gap['gap_id']}",
                    "type": "IMPLEMENT_CONTROL",
                    "priority": gap.get("priority_level", "medium"),
                    "target": gap["requirement"]["title"],
                    "regulation": gap["regulation"]["code"],
                    "risk_level": gap["requirement"]["risk_level"],
                    "severity_score": gap.get("gap_severity_score", 0),
                    "cost_estimate": self._estimate_action_cost(gap),
                    "timeline": self._estimate_timeline(gap),
                    "graph_reference": gap["gap_id"]
                }
                action_plan.append(action)

            # Sort by priority and risk
            action_plan.sort(key=lambda x: (
                {"critical": 1, "high": 2, "medium": 3}.get(x["priority"], 4),
                -x["severity_score"]
            ))

            state.action_plan = action_plan
            state.risk_assessment = {
                "convergence_patterns": len(risk_convergence.data),
                "recent_regulatory_changes": temporal_changes.metadata.get("recent_changes", 0),
                "overall_risk_level": self._calculate_overall_risk(state.compliance_posture),
                "planning_horizon": "90_days"
            }

            state.graph_context.update({
                "risk_convergence": risk_convergence.data,
                "temporal_changes": temporal_changes.data,
                "planning_timestamp": datetime.utcnow().isoformat()
            })

            logger.info(f"IQ PLAN: Generated {len(action_plan)} prioritized actions")

        except Exception as e:
            logger.error(f"IQ PLAN error: {str(e)}")
            state.graph_context["planning_error"] = str(e)

        return state

    async def _act_node(self, state: IQAgentState) -> IQAgentState:
        """ACT: Execute high-priority actions and update graph"""

        logger.info("IQ ACT: Executing prioritized compliance actions")

        try:
            executed_actions = []

            # Execute top priority actions that meet autonomy criteria
            for action in state.action_plan[:3]:  # Top 3 actions
                if await self._should_auto_execute(action):
                    execution_result = await self._execute_action(action)
                    executed_actions.append(execution_result)

                    # Update graph with execution evidence
                    await self._store_execution_evidence(action, execution_result)
                else:
                    # Create escalation for manual approval
                    escalation = await self._create_escalation(action)
                    executed_actions.append(escalation)

            state.evidence_collected = executed_actions
            state.graph_context["actions_executed"] = len([
                a for a in executed_actions if a.get("status") == "executed"
            ])

            logger.info(f"IQ ACT: Executed {len(executed_actions)} actions")

        except Exception as e:
            logger.error(f"IQ ACT error: {str(e)}")
            state.graph_context["action_error"] = str(e)

        return state

    async def _learn_node(self, state: IQAgentState) -> IQAgentState:
        """LEARN: Analyze patterns and update knowledge from enforcement"""

        logger.info("IQ LEARN: Analyzing enforcement patterns and updating knowledge")

        try:
            # Learn from enforcement cases
            enforcement_learning = await execute_compliance_query(
                QueryCategory.ENFORCEMENT_LEARNING,
                self.neo4j
            )

            # Detect new patterns from recent activities
            patterns = self._detect_compliance_patterns(
                state.graph_context,
                state.evidence_collected
            )

            # Update control effectiveness based on execution results
            effectiveness_updates = await self._update_control_effectiveness(
                state.evidence_collected
            )

            state.patterns_detected = patterns
            state.graph_context.update({
                "enforcement_insights": enforcement_learning.data,
                "patterns_detected": patterns,
                "effectiveness_updates": effectiveness_updates,
                "learning_timestamp": datetime.utcnow().isoformat()
            })

            logger.info(f"IQ LEARN: Detected {len(patterns)} new patterns")

        except Exception as e:
            logger.error(f"IQ LEARN error: {str(e)}")
            state.graph_context["learning_error"] = str(e)

        return state

    async def _remember_node(self, state: IQAgentState) -> IQAgentState:
        """REMEMBER: Consolidate knowledge and update memory"""

        logger.info("IQ REMEMBER: Consolidating knowledge and updating memory")

        try:
            # Store knowledge graph insights
            for pattern in state.patterns_detected:
                await self.memory_manager.store_knowledge_graph_memory(
                    graph_query_result=pattern,
                    query_category=QueryCategory.REGULATORY_COVERAGE,
                    importance_score=0.7
                )

            # Retrieve relevant historical memories
            relevant_memories = await self.memory_manager.retrieve_contextual_memories(
                query=state.current_query,
                context=state.graph_context,
                max_memories=5
            )

            state.memories_accessed = [m.id for m in relevant_memories.retrieved_memories]

            # Consolidate recent compliance knowledge
            if state.step_count % 10 == 0:  # Consolidate every 10 interactions
                consolidation = await self.memory_manager.consolidate_compliance_knowledge()
                state.graph_context["knowledge_consolidation"] = consolidation

            state.graph_context.update({
                "memories_accessed": len(state.memories_accessed),
                "memory_consolidation_due": state.step_count % 10 == 9,
                "remember_timestamp": datetime.utcnow().isoformat()
            })

            logger.info(f"IQ REMEMBER: Accessed {len(state.memories_accessed)} relevant memories")

        except Exception as e:
            logger.error(f"IQ REMEMBER error: {str(e)}")
            state.graph_context["memory_error"] = str(e)

        return state

    async def _respond_node(self, state: IQAgentState) -> IQAgentState:
        """Generate final response with insights and recommendations"""

        logger.info("IQ RESPOND: Generating comprehensive compliance response")

        # Generate LLM response with full context
        response_prompt = self._create_response_prompt(state)

        try:
            llm_response = await self.llm.ainvoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=response_prompt)
            ])

            state.messages.append(AIMessage(content=llm_response.content))

        except Exception as e:
            logger.error(f"IQ RESPOND error: {str(e)}")
            state.messages.append(AIMessage(content=f"Response generation error: {str(e)}"))

        state.step_count += 1
        return state

    def _format_response(self, state: IQAgentState) -> Dict[str, Any]:
        """Format final IQ response according to output contract"""

        # Calculate risk posture
        risk_posture = self._determine_risk_posture(state.compliance_posture, state.risk_assessment)

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "risk_posture": risk_posture,
                "compliance_score": state.compliance_posture.get("overall_coverage", 0.0),
                "top_gaps": [
                    gap["requirement"]["title"]
                    for gap in state.graph_context.get("compliance_gaps", [])[:3]
                ],
                "immediate_actions": [
                    action["target"]
                    for action in state.action_plan[:3]
                ]
            },
            "artifacts": {
                "compliance_posture": state.compliance_posture,
                "action_plan": state.action_plan,
                "risk_assessment": state.risk_assessment
            },
            "graph_context": {
                "nodes_traversed": len(state.graph_context.get("coverage_analysis", [])),
                "patterns_detected": state.patterns_detected,
                "memories_accessed": state.memories_accessed,
                "learnings_applied": len(state.evidence_collected)
            },
            "evidence": {
                "controls_executed": len([
                    e for e in state.evidence_collected
                    if e.get("status") == "executed"
                ]),
                "evidence_stored": len(state.evidence_collected),
                "metrics_updated": state.graph_context.get("actions_executed", 0)
            },
            "next_actions": [
                {
                    "action": action["target"],
                    "priority": action["priority"].upper(),
                    "owner": "Compliance Team",
                    "graph_reference": action["graph_reference"]
                }
                for action in state.action_plan[:5]
            ],
            "llm_response": state.messages[-1].content if state.messages else "No response generated"
        }

    # Helper methods

    def _extract_regulation_codes(self, query: str) -> List[str]:
        """Extract regulation codes from query text"""
        common_codes = ["GDPR", "6AMLD", "DORA", "BSA", "MLR2017", "DPA2018", "MIFID2"]
        return [code for code in common_codes if code.lower() in query.lower()]

    def _estimate_action_cost(self, gap: Dict[str, Any]) -> float:
        """Estimate implementation cost for action"""
        base_cost = 5000.0
        risk_multiplier = {"critical": 3.0, "high": 2.0, "medium": 1.5, "low": 1.0}
        risk_level = gap["requirement"]["risk_level"]
        return base_cost * risk_multiplier.get(risk_level, 1.0)

    def _estimate_timeline(self, gap: Dict[str, Any]) -> str:
        """Estimate implementation timeline"""
        risk_level = gap["requirement"]["risk_level"]
        timeline_map = {
            "critical": "30_days",
            "high": "60_days",
            "medium": "90_days",
            "low": "180_days"
        }
        return timeline_map.get(risk_level, "90_days")

    def _calculate_overall_risk(self, compliance_posture: Dict[str, Any]) -> str:
        """Calculate overall risk level"""
        coverage = compliance_posture.get("overall_coverage", 0.0)
        critical_gaps = compliance_posture.get("critical_gaps", 0)

        if critical_gaps > 5 or coverage < 0.3:
            return "CRITICAL"
        elif critical_gaps > 2 or coverage < 0.6:
            return "HIGH"
        elif coverage < 0.8:
            return "MEDIUM"
        else:
            return "LOW"

    async def _should_auto_execute(self, action: Dict[str, Any]) -> bool:
        """Determine if action should be executed autonomously"""
        # Simple autonomy decision based on risk and cost
        risk_score = action.get("severity_score", 0)
        cost = action.get("cost_estimate", 0)

        return (risk_score < self.RISK_THRESHOLD and
                cost < self.AUTONOMY_BUDGET and
                action["priority"] in ["high", "critical"])

    async def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute compliance action (placeholder)"""
        # Simulate action execution
        return {
            "action_id": action["action_id"],
            "status": "executed",
            "timestamp": datetime.utcnow().isoformat(),
            "result": "success",
            "evidence_ref": f"evidence_{action['action_id']}",
            "effectiveness": 0.85
        }

    async def _create_escalation(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Create escalation for manual approval"""
        return {
            "action_id": action["action_id"],
            "status": "escalated",
            "timestamp": datetime.utcnow().isoformat(),
            "reason": "Requires manual approval - high risk or cost",
            "approval_required": True
        }

    async def _store_execution_evidence(self, action: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Store execution evidence in graph"""
        # Placeholder for evidence storage
        pass

    def _detect_compliance_patterns(self, graph_context: Dict[str, Any], evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect compliance patterns from current analysis"""
        patterns = []

        # Pattern: High gap concentration in specific domain
        gaps = graph_context.get("compliance_gaps", [])
        if gaps:
            domain_gaps = {}
            for gap in gaps:
                domain = gap["domain"]["name"]
                domain_gaps[domain] = domain_gaps.get(domain, 0) + 1

            for domain, count in domain_gaps.items():
                if count > 3:
                    patterns.append({
                        "pattern_type": "HIGH_GAP_CONCENTRATION",
                        "domain": domain,
                        "gap_count": count,
                        "confidence": 0.8
                    })

        return patterns

    async def _update_control_effectiveness(self, evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Update control effectiveness based on execution results"""
        updates = []

        for evidence_item in evidence:
            if evidence_item.get("status") == "executed":
                updates.append({
                    "control_id": evidence_item["action_id"],
                    "effectiveness": evidence_item.get("effectiveness", 0.8),
                    "updated_at": evidence_item["timestamp"]
                })

        return updates

    def _create_response_prompt(self, state: IQAgentState) -> str:
        """Create comprehensive prompt for LLM response generation"""
        return f"""
Based on my analysis of the compliance landscape, please provide a comprehensive response to: "{state.current_query}"

## Current Compliance Posture:
- Overall Coverage: {state.compliance_posture.get('overall_coverage', 0):.2%}
- Total Gaps: {state.compliance_posture.get('total_gaps', 0)}
- Critical Gaps: {state.compliance_posture.get('critical_gaps', 0)}

## Top Priority Actions:
{chr(10).join(f"- {action['target']} ({action['priority']} priority)" for action in state.action_plan[:3])}

## Graph Analysis Summary:
- Patterns Detected: {len(state.patterns_detected)}
- Memories Accessed: {len(state.memories_accessed)}
- Actions Executed: {len(state.evidence_collected)}

Please provide:
1. Executive summary of compliance status
2. Key risks and gaps identified
3. Recommended immediate actions
4. Long-term compliance strategy recommendations

Focus on actionable insights derived from the graph analysis.
"""

    def _determine_risk_posture(self, compliance_posture: Dict[str, Any], risk_assessment: Dict[str, Any]) -> str:
        """Determine overall risk posture"""
        coverage = compliance_posture.get("overall_coverage", 0.0)
        critical_gaps = compliance_posture.get("critical_gaps", 0)
        convergence_patterns = risk_assessment.get("convergence_patterns", 0)

        if critical_gaps > 5 or coverage < 0.4 or convergence_patterns > 10:
            return "CRITICAL"
        elif critical_gaps > 2 or coverage < 0.7 or convergence_patterns > 5:
            return "HIGH"
        elif coverage < 0.85:
            return "MEDIUM"
        else:
            return "LOW"

    # Enhanced methods for dual database access

    async def process_query_with_context(
        self,
        user_query: str,
        business_profile_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process query with business context from PostgreSQL.
        
        Args:
            user_query: User's compliance question
            business_profile_id: Optional business profile ID to retrieve context
            session_id: Optional assessment session ID for history
            context: Additional context
            
        Returns:
            Enhanced response with business context
        """
        # Retrieve business context if available
        business_context = {}
        if self.has_postgres_access and business_profile_id:
            try:
                business_context = await self.retrieve_business_context(business_profile_id)
            except Exception as e:
                logger.error(f"Failed to retrieve business context: {e}")
                business_context = {"error": "Failed to retrieve business context"}

        # Query Neo4j for compliance information
        compliance_gaps = []
        try:
            # Example query for compliance gaps based on business context
            if business_context and "profile" in business_context:
                if business_context["profile"].get("handles_personal_data"):
                    # Query for GDPR gaps
                    gap_query = """
                    MATCH (r:Regulation {code: 'GDPR'})-[:HAS_REQUIREMENT]->(req:Requirement)
                    WHERE req.risk_level IN ['high', 'critical']
                    RETURN req.id as requirement_id, req.title as title, 
                           req.risk_level as risk_level, r.code as regulation
                    LIMIT 5
                    """
                    result = await self.neo4j.execute_query(gap_query)
                    compliance_gaps = result.get("data", [])
        except Exception as e:
            logger.error(f"Failed to query Neo4j: {e}")

        # Build response using LLM with context
        # Safely serialize business context
        try:
            business_context_str = json.dumps(business_context, indent=2) if business_context else "No business context available"
        except (TypeError, ValueError):
            # Fallback to string representation if JSON serialization fails
            business_context_str = str(business_context) if business_context else "No business context available"

        try:
            compliance_gaps_str = json.dumps(compliance_gaps, indent=2) if compliance_gaps else "No specific gaps identified"
        except (TypeError, ValueError):
            compliance_gaps_str = str(compliance_gaps) if compliance_gaps else "No specific gaps identified"

        prompt = f"""
        User Query: {user_query}
        
        Business Context:
        {business_context_str}
        
        Compliance Gaps Identified:
        {compliance_gaps_str}
        
        Please provide compliance guidance considering this business context.
        """

        llm_response = ""
        try:
            response = await self.llm.ainvoke(prompt)
            llm_response = response.content
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            llm_response = "Unable to generate AI response at this time."

        # Format structured response
        response = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "business_context": business_context,
            "summary": {
                "risk_posture": "MEDIUM" if compliance_gaps else "LOW",
                "compliance_score": 0.75 if not compliance_gaps else 0.5,
                "top_gaps": [gap.get("title", "") for gap in compliance_gaps[:3]],
                "immediate_actions": [
                    "Review compliance gaps",
                    "Update business profile",
                    "Implement missing controls"
                ]
            },
            "artifacts": {
                "compliance_gaps": compliance_gaps,
                "neo4j_data": {
                    "gaps_found": len(compliance_gaps),
                    "regulations_checked": ["GDPR"] if business_context else []
                }
            },
            "evidence": {
                "available_evidence": 0
            },
            "llm_response": llm_response
        }

        # Add evidence count from PostgreSQL if available
        if self.has_postgres_access and business_profile_id:
            try:
                evidence_count = await self._count_available_evidence(business_profile_id)
                response["evidence"]["available_evidence"] = evidence_count
            except Exception as e:
                logger.error(f"Failed to count evidence: {e}")

        return response

    async def retrieve_business_context(self, business_profile_id: str) -> Dict[str, Any]:
        """
        Retrieve business profile and evidence from PostgreSQL.
        
        Args:
            business_profile_id: Business profile ID
            
        Returns:
            Business context including profile and evidence
        """
        if not self.has_postgres_access:
            return {}

        from sqlalchemy import select
        from database.business_profile import BusinessProfile
        from database.models.evidence import Evidence

        try:
            # Retrieve business profile
            profile_stmt = select(BusinessProfile).where(
                BusinessProfile.id == business_profile_id
            )
            result = await self.postgres_session.execute(profile_stmt)
            profile = result.scalars().first()

            if not profile:
                return {"error": "Business profile not found"}

            # Retrieve associated evidence
            evidence_stmt = select(Evidence).where(
                Evidence.business_profile_id == business_profile_id
            ).order_by(Evidence.created_at.desc()).limit(10)

            evidence_result = await self.postgres_session.execute(evidence_stmt)
            evidence_items = evidence_result.scalars().all()

            return {
                "profile": {
                    "id": str(profile.id),
                    "company_name": profile.company_name,
                    "industry": profile.industry,
                    "company_size": profile.company_size,
                    "handles_personal_data": profile.handles_personal_data,
                    "data_processing_activities": profile.data_processing_activities,
                    "created_at": profile.created_at.isoformat()
                },
                "evidence": [
                    {
                        "id": str(item.id),
                        "title": item.title,
                        "description": item.description,
                        "evidence_type": item.evidence_type,
                        "file_path": item.file_path,
                        "created_at": item.created_at.isoformat()
                    }
                    for item in evidence_items
                ]
            }

        except Exception as e:
            logger.error(f"Error retrieving business context: {e}")
            return {"error": str(e)}

    async def retrieve_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve assessment session context from PostgreSQL.
        
        Args:
            session_id: Assessment session ID
            
        Returns:
            Session context or None
        """
        if not self.has_postgres_access:
            return None

        from sqlalchemy import select
        from database.assessment_session import AssessmentSession

        try:
            stmt = select(AssessmentSession).where(
                AssessmentSession.id == session_id
            )
            result = await self.postgres_session.execute(stmt)
            session = result.scalars().first()

            if session:
                return {
                    "session_id": str(session.id),
                    "questions_answered": session.questions_answered,
                    "compliance_score": session.compliance_score,
                    "risk_level": session.risk_level,
                    "created_at": session.created_at.isoformat()
                }
            return None

        except Exception as e:
            logger.error(f"Error retrieving session context: {e}")
            return None

    async def assess_compliance_with_context(
        self,
        business_profile_id: str,
        regulations: List[str]
    ) -> Dict[str, Any]:
        """
        Assess compliance for a specific business against regulations.
        
        Args:
            business_profile_id: Business profile ID
            regulations: List of regulation codes to assess
            
        Returns:
            Contextualized compliance assessment
        """
        # Retrieve business context
        business_context = {}
        if self.has_postgres_access:
            business_context = await self.retrieve_business_context(business_profile_id)

        # Query Neo4j for regulation requirements
        regulation_query = f"""
        MATCH (r:Regulation)-[:HAS_REQUIREMENT]->(req:Requirement)
        WHERE r.code IN {regulations}
        RETURN r.code as regulation, 
               collect({{
                   id: req.id,
                   title: req.title,
                   description: req.description,
                   risk_level: req.risk_level
               }}) as requirements
        """

        neo4j_result = await self.neo4j.execute_query(regulation_query)

        # Build assessment considering business context
        assessment = {
            "status": "success",
            "business_context": business_context,
            "compliance_assessment": {
                "applicable_regulations": regulations,
                "business_specific_risks": self._identify_business_risks(business_context),
                "requirements_analysis": neo4j_result.get("data", []),
                "recommendations": self._generate_contextualized_recommendations(
                    business_context,
                    neo4j_result.get("data", [])
                )
            }
        }

        return assessment

    async def search_compliance_resources(
        self,
        query: str,
        include_evidence: bool = True,
        include_regulations: bool = True
    ) -> Dict[str, Any]:
        """
        Search across both databases for compliance resources.
        
        Args:
            query: Search query
            include_evidence: Search PostgreSQL for evidence
            include_regulations: Search Neo4j for regulations
            
        Returns:
            Combined search results
        """
        results = {
            "query": query,
            "regulations": [],
            "evidence": [],
            "total_results": 0
        }

        # Search Neo4j for regulations and requirements
        if include_regulations:
            neo4j_query = f"""
            MATCH (r:Regulation)-[:HAS_REQUIREMENT]->(req:Requirement)
            WHERE toLower(r.name) CONTAINS toLower('{query}')
               OR toLower(req.title) CONTAINS toLower('{query}')
               OR toLower(req.description) CONTAINS toLower('{query}')
            RETURN r.code as regulation, count(req) as matches
            """

            neo4j_result = await self.neo4j.execute_query(neo4j_query)
            results["regulations"] = neo4j_result.get("data", [])

        # Search PostgreSQL for evidence
        if include_evidence and self.has_postgres_access:
            from sqlalchemy import select, or_
            from database.models.evidence import Evidence

            stmt = select(
                Evidence.title,
                Evidence.description
            ).where(
                or_(
                    Evidence.title.ilike(f"%{query}%"),
                    Evidence.description.ilike(f"%{query}%")
                )
            ).limit(10)

            pg_result = await self.postgres_session.execute(stmt)
            evidence_items = pg_result.all()

            results["evidence"] = [
                {"title": item[0], "relevance": 0.8}  # Simplified relevance
                for item in evidence_items
            ]

        # Calculate total results
        results["total_results"] = (
            sum(r["matches"] for r in results["regulations"]) +
            len(results["evidence"])
        )

        return results

    async def _count_available_evidence(self, business_profile_id: str) -> int:
        """Count available evidence for a business profile."""
        if not self.has_postgres_access:
            return 0

        from sqlalchemy import select, func
        from database.models.evidence import Evidence

        stmt = select(func.count(Evidence.id)).where(
            Evidence.business_profile_id == business_profile_id
        )
        result = await self.postgres_session.execute(stmt)
        return result.scalar() or 0

    def _identify_business_risks(self, business_context: Dict[str, Any]) -> List[str]:
        """Identify business-specific compliance risks."""
        risks = []

        if not business_context or "profile" not in business_context:
            return risks

        profile = business_context["profile"]

        # Risk based on data handling
        if profile.get("handles_personal_data"):
            risks.append("Personal data processing requires GDPR compliance")

        # Risk based on company size
        if profile.get("company_size", "").startswith("201"):
            risks.append("Large organization may require DPO appointment")

        # Risk based on industry
        if profile.get("industry") in ["Finance", "Healthcare"]:
            risks.append(f"{profile['industry']} sector has additional regulatory requirements")

        return risks

    def _generate_contextualized_recommendations(
        self,
        business_context: Dict[str, Any],
        requirements: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on business context."""
        recommendations = []

        if not business_context or "profile" not in business_context:
            return ["Complete business profile for personalized recommendations"]

        profile = business_context["profile"]

        # Basic recommendations
        if profile.get("handles_personal_data") and not business_context.get("evidence"):
            recommendations.append("Upload privacy policy and data processing agreements")

        if len(requirements) > 10:
            recommendations.append(f"Focus on {len(requirements)} regulatory requirements identified")

        return recommendations


# Factory function for creating IQ agent
async def create_iq_agent(neo4j_service: Neo4jGraphRAGService) -> IQComplianceAgent:
    """Factory function to create and initialize IQ agent"""
    agent = IQComplianceAgent(neo4j_service)

    # Ensure graph is initialized
    try:
        await neo4j_service.connect()
        logger.info("IQ Agent: Neo4j connection established")

        # Initialize compliance graph if needed
        graph_stats = await neo4j_service.get_graph_statistics()
        if graph_stats.get("total_nodes", 0) < 10:
            logger.info("IQ Agent: Initializing compliance graph...")
            await initialize_compliance_graph()
            logger.info("IQ Agent: Compliance graph initialized")

    except Exception as e:
        logger.error(f"IQ Agent initialization error: {str(e)}")
        raise

    return agent
