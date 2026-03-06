"""
IQ - Autonomous Compliance Orchestrator with GraphRAG Intelligence

This module implements the IQ agent as described in the comprehensive prompt,
leveraging Neo4j GraphRAG for compliance intelligence and decision-making.
"""

# Constants
CONFIDENCE_THRESHOLD = 0.8
DEFAULT_RETRIES = 5
MAX_RETRIES = 3

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from services.neo4j_service import Neo4jGraphRAGService
from services.compliance_retrieval_queries import (
    ComplianceRetrievalQueries,
    QueryCategory,
    execute_compliance_query,
)
from services.compliance_memory_manager import ComplianceMemoryManager
from services.compliance_graph_initializer import initialize_compliance_graph

logger = logging.getLogger(__name__)


class IQState(Enum):
    """IQ Agent operational states"""


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
        llm_model: str = "gpt-4",
    ) -> None:
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
        self.workflow = self._create_workflow()
        self.system_prompt = self._get_iq_system_prompt()
        self.RISK_THRESHOLD = 7.0
        self.AUTONOMY_BUDGET = 10000.0
        logger.info(
            "IQComplianceAgent initialized with Neo4j and %s access"
            % ("PostgreSQL" if self.has_postgres_access else "NO PostgreSQL")
        )

    def _get_iq_system_prompt(self) -> str:
        """IQ's core system prompt - his operational brain"""
        return """# IQ — Chief Compliance Officer | Autonomous Orchestrator

## Identity & Role

You are **IQ**, the autonomous Chief Compliance Officer of **ruleIQ**. You embody decades of compliance expertise, strategic thinking, and risk management acumen. Your role is to transform compliance from a cost center into a strategic advantage through intelligent automation and predictive risk management.  # noqa: E501

## Core Architecture

### Knowledge Access
- **Personal Knowledge**: CCO Strategic Playbook (2025-2030 vision) via local manifest
- **Compliance Knowledge**: Access via GraphRAG Query Agent to unified compliance knowledge graph
- **Query Strategy**: Use the GraphRAG retriever for all regulatory lookups, evidence gathering, and compliance verification  # noqa: E501
- **Memory Systems**: Episodic (events), Semantic (regulations), Procedural (workflows), Strategic (patterns)

### Dual Graph Architecture
1. **IQ Persona Graph**: Your strategic knowledge, CCO playbook, decision frameworks
2. **Compliance Knowledge Graph**: All regulations (UK/EU/US), accessed via GraphRAG Query Agent

## Decision Framework

### Evidence Requirements
- **Minimum Sources**: ≥3 independent sources for major claims
- **Verification**: Primary sources required (legislation.gov.uk, EUR-Lex, Federal Register)
- **Query Method**: Use GraphRAG Query Agent with specific jurisdiction and regulation parameters
- **Triangulation**: Cross-reference multiple sources before making recommendations

### Risk-Weighted Prioritization
1. **Critical (8-10)**: Immediate violations, regulatory deadlines, enforcement actions
2. **High (6-8)**: Missing controls for mandatory requirements, audit findings
3. **Medium (4-6)**: Process improvements, efficiency opportunities
4. **Low (0-4)**: Nice-to-have enhancements, long-term strategic initiatives

## Operational Loop

### 1. PERCEIVE (via GraphRAG Query)
```
Query GraphRAG for:
- Current compliance posture
- Active regulations by jurisdiction
- Recent enforcement patterns
- Control effectiveness metrics
```

### 2. ANALYZE (Strategic Assessment)
```
Apply CCO expertise to:
- Risk scoring using playbook methodology
- Cross-jurisdictional impact analysis
- Cost-benefit evaluation
- Resource optimization
```

### 3. RECOMMEND (Evidence-Based)
```
Generate recommendations with:
- Specific regulatory citations (via GraphRAG)
- Implementation priorities
- Resource requirements
- Success metrics
```

### 4. ORCHESTRATE (Automation)
```
Execute through:
- Compliance-as-Code controls
- Automated evidence collection
- Continuous monitoring
- Self-healing workflows
```

### 5. LEARN (Pattern Recognition)
```
Continuously improve by:
- Analyzing enforcement trends
- Updating risk models
- Refining control effectiveness
- Consolidating strategic insights
```

## Communication Style

### As Chief Compliance Officer:
- **Strategic**: Frame compliance in business terms, ROI, and competitive advantage
- **Authoritative**: Speak with confidence backed by evidence and expertise
- **Proactive**: Anticipate risks before they materialize
- **Educational**: Explain complex regulations in clear, actionable terms
- **Risk-Aware**: Always quantify risk levels and potential impacts

### Query Patterns for GraphRAG:
```python
# Example queries to GraphRAG Query Agent:
"UK Money Laundering Regulations 2017 customer due diligence requirements"
"FCA Senior Managers Regime accountability requirements"
"GDPR Article 33 breach notification timeline"
"Cross-jurisdictional data transfer requirements UK EU US"
```

## Response Structure

### Always Include:
```json
{
  "executive_summary": {
    "risk_level": "Critical/High/Medium/Low",
    "compliance_score": "X%",
    "immediate_actions": ["action1", "action2"],
    "regulatory_references": ["via GraphRAG"],
  },
  "detailed_analysis": {
    "gaps_identified": [],
    "controls_assessed": [],
    "evidence_reviewed": [],
  },
  "recommendations": {
    "priority_1": {"action": "", "deadline": "", "regulation": ""},
    "priority_2": {"action": "", "deadline": "", "regulation": ""},
  },
  "evidence_trail": {
    "sources_consulted": ["GraphRAG queries"],
    "confidence_level": "High/Medium/Low",
    "assumptions": [],
  },
}
```

## Strategic Priorities (CCO Playbook 2025-2030)

1. **Autonomous Compliance**: 95% automation of routine tasks by 2027
2. **Predictive Intelligence**: 90% risk prediction accuracy by 2026
3. **Real-time Adaptation**: <24hr from regulation to control update
4. **Evidence-based Decisions**: 100% decision traceability
5. **Cross-jurisdictional Harmony**: 60% complexity reduction by 2028

## Constraints & Guardrails

- **Never** make claims without evidence (use GraphRAG Query Agent)
- **Always** cite specific regulations and sections
- **Escalate** critical risks immediately (risk score ≥8)
- **Document** every decision for audit trail
- **Verify** through GraphRAG before stating regulatory requirements
- **Budget**: Autonomous decision limit = £10,000
- **Legal**: Cannot provide legal advice, only compliance guidance

## Integration Protocol

When asked about specific regulations:
1. Query GraphRAG for authoritative source
2. Verify currency of regulation (check for amendments)
3. Cross-reference with enforcement cases
4. Provide practical implementation guidance
5. Include relevant deadlines and transition periods

Remember: You are the Chief Compliance Officer. Think strategically, act decisively, and always base your decisions on verifiable evidence accessed through the GraphRAG Query Agent."""

    def _create_workflow(self) -> StateGraph:
        """Create LangGraph workflow for IQ's intelligence loop"""
        workflow = StateGraph(IQAgentState)
        workflow.add_node("perceive", self._perceive_node)
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("act", self._act_node)
        workflow.add_node("learn", self._learn_node)
        workflow.add_node("remember", self._remember_node)
        workflow.add_node("respond", self._respond_node)
        workflow.set_entry_point("perceive")
        workflow.add_edge("perceive", "plan")
        workflow.add_edge("plan", "act")
        workflow.add_edge("act", "learn")
        workflow.add_edge("learn", "remember")
        workflow.add_edge("remember", "respond")
        workflow.add_edge("respond", END)
        return workflow.compile()

    async def process_query(
        self, user_query: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Main entry point for processing compliance queries"""
        try:
            compliance_data = {}
            try:
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
                logger.error("Neo4j query failed: %s" % e)
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
                logger.error("LLM invocation failed: %s" % e)
                llm_response = "Unable to generate AI response at this time."
            return {
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "risk_posture": "MEDIUM",
                    "compliance_score": 0.7,
                    "top_gaps": [],
                    "immediate_actions": ["Review compliance requirements"],
                },
                "artifacts": {"compliance_data": compliance_data},
                "llm_response": llm_response,
            }
        except Exception as e:
            logger.error("IQ processing error: %s" % str(e))
            return {
                "status": "error",
                "error": str(e),
                "summary": {
                    "risk_posture": "UNKNOWN",
                    "compliance_score": 0.0,
                    "top_gaps": [],
                    "immediate_actions": ["Contact support - processing error occurred"],
                },
            }

    async def _perceive_node(self, state: IQAgentState) -> IQAgentState:
        """PERCEIVE: Query current compliance posture from graph"""
        logger.info("IQ PERCEIVE: Analyzing compliance posture")
        try:
            coverage_analysis = await execute_compliance_query(
                QueryCategory.REGULATORY_COVERAGE, self.neo4j
            )
            gap_analysis = await execute_compliance_query(QueryCategory.COMPLIANCE_GAPS, self.neo4j)
            if "regulations" in state.current_query.lower():
                regulation_codes = self._extract_regulation_codes(state.current_query)
                if regulation_codes:
                    cross_jurisdictional = await execute_compliance_query(
                        QueryCategory.CROSS_JURISDICTIONAL,
                        self.neo4j,
                        regulation_codes=regulation_codes,
                    )
                    state.graph_context["cross_jurisdictional"] = cross_jurisdictional.data
            state.graph_context.update(
                {
                    "coverage_analysis": coverage_analysis.data,
                    "coverage_metadata": coverage_analysis.metadata,
                    "compliance_gaps": gap_analysis.data,
                    "gap_metadata": gap_analysis.metadata,
                    "perception_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            state.compliance_posture = {
                "overall_coverage": coverage_analysis.metadata.get("overall_coverage", 0.0),
                "total_gaps": gap_analysis.metadata.get("total_gaps", 0),
                "critical_gaps": gap_analysis.metadata.get("critical_gaps", 0),
                "high_risk_gaps": gap_analysis.metadata.get("high_risk_gaps", 0),
            }
            logger.info(
                "IQ PERCEIVE: Found %s gaps, coverage: %s"
                % (
                    state.compliance_posture["total_gaps"],
                    state.compliance_posture["overall_coverage"],
                )
            )
        except Exception as e:
            logger.error("IQ PERCEIVE error: %s" % str(e))
            state.graph_context["perception_error"] = str(e)
        return state

    async def _plan_node(self, state: IQAgentState) -> IQAgentState:
        """PLAN: Generate risk-weighted action plan from graph analysis"""
        logger.info("IQ PLAN: Generating risk-weighted action plan")
        try:
            risk_convergence = await execute_compliance_query(
                QueryCategory.RISK_CONVERGENCE, self.neo4j
            )
            temporal_changes = await execute_compliance_query(
                QueryCategory.TEMPORAL_CHANGES, self.neo4j, lookback_months=6, forecast_months=3
            )
            gaps = state.graph_context.get("compliance_gaps", [])
            action_plan = []
            for gap in gaps[:10]:
                action = {
                    "action_id": f"action_{gap['gap_id']}",
                    "type": "IMPLEMENT_CONTROL",
                    "priority": gap["requirement"]["risk_level"],
                    "target": gap["requirement"]["title"],
                    "regulation": gap["regulation"]["code"],
                    "risk_level": gap["requirement"]["risk_level"],
                    "severity_score": gap.get("gap_severity_score", 0),
                    "cost_estimate": self._estimate_action_cost(gap),
                    "timeline": self._estimate_timeline(gap),
                    "graph_reference": gap["gap_id"],
                }
                action_plan.append(action)
            action_plan.sort(
                key=lambda x: (
                    {"critical": 1, "high": 2, "medium": 3}.get(x["priority"], 4),
                    -x["severity_score"],
                )
            )
            state.action_plan = action_plan
            state.risk_assessment = {
                "convergence_patterns": len(risk_convergence.data),
                "recent_regulatory_changes": temporal_changes.metadata.get("recent_changes", 0),
                "overall_risk_level": self._calculate_overall_risk(state.compliance_posture),
                "planning_horizon": "90_days",
            }
            state.graph_context.update(
                {
                    "risk_convergence": risk_convergence.data,
                    "temporal_changes": temporal_changes.data,
                    "planning_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            logger.info("IQ PLAN: Generated %s prioritized actions" % len(action_plan))
        except Exception as e:
            logger.error("IQ PLAN error: %s" % str(e))
            state.graph_context["planning_error"] = str(e)
        return state

    async def _act_node(self, state: IQAgentState) -> IQAgentState:
        """ACT: Execute high-priority actions and update graph"""
        logger.info("IQ ACT: Executing prioritized compliance actions")
        try:
            executed_actions = []
            for action in state.action_plan[:3]:
                if await self._should_auto_execute(action):
                    execution_result = await self._execute_action(action)
                    executed_actions.append(execution_result)
                    await self._store_execution_evidence(action, execution_result)
                else:
                    escalation = await self._create_escalation(action)
                    executed_actions.append(escalation)
            state.evidence_collected = executed_actions
            state.graph_context["actions_executed"] = len(
                [a for a in executed_actions if a.get("status") == "executed"]
            )
            logger.info("IQ ACT: Executed %s actions" % len(executed_actions))
        except Exception as e:
            logger.error("IQ ACT error: %s" % str(e))
            state.graph_context["action_error"] = str(e)
        return state

    async def _learn_node(self, state: IQAgentState) -> IQAgentState:
        """LEARN: Analyze patterns and update knowledge from enforcement"""
        logger.info("IQ LEARN: Analyzing enforcement patterns and updating knowledge")
        try:
            enforcement_learning = await execute_compliance_query(
                QueryCategory.ENFORCEMENT_LEARNING, self.neo4j
            )
            patterns = self._detect_compliance_patterns(
                state.graph_context, state.evidence_collected
            )
            effectiveness_updates = await self._update_control_effectiveness(
                state.evidence_collected
            )
            state.patterns_detected = patterns
            state.graph_context.update(
                {
                    "enforcement_insights": enforcement_learning.data,
                    "patterns_detected": patterns,
                    "effectiveness_updates": effectiveness_updates,
                    "learning_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            logger.info("IQ LEARN: Detected %s new patterns" % len(patterns))
        except Exception as e:
            logger.error("IQ LEARN error: %s" % str(e))
            state.graph_context["learning_error"] = str(e)
        return state

    async def _remember_node(self, state: IQAgentState) -> IQAgentState:
        """REMEMBER: Consolidate knowledge and update memory"""
        logger.info("IQ REMEMBER: Consolidating knowledge and updating memory")
        try:
            for pattern in state.patterns_detected:
                await self.memory_manager.store_knowledge_graph_memory(
                    graph_query_result=pattern,
                    query_category=QueryCategory.REGULATORY_COVERAGE,
                    importance_score=0.7,
                )
            relevant_memories = await self.memory_manager.retrieve_contextual_memories(
                query=state.current_query, context=state.graph_context, max_memories=5
            )
            state.memories_accessed = [m.id for m in relevant_memories.retrieved_memories]
            if state.step_count % 10 == 0:
                consolidation = await self.memory_manager.consolidate_compliance_knowledge()
                state.graph_context["knowledge_consolidation"] = consolidation
            state.graph_context.update(
                {
                    "memories_accessed": len(state.memories_accessed),
                    "memory_consolidation_due": state.step_count % 10 == 9,
                    "remember_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            logger.info("IQ REMEMBER: Accessed %s relevant memories" % len(state.memories_accessed))
        except Exception as e:
            logger.error("IQ REMEMBER error: %s" % str(e))
            state.graph_context["memory_error"] = str(e)
        return state

    async def _respond_node(self, state: IQAgentState) -> IQAgentState:
        """Generate final response with insights and recommendations"""
        logger.info("IQ RESPOND: Generating comprehensive compliance response")
        response_prompt = self._create_response_prompt(state)
        try:
            llm_response = await self.llm.ainvoke(
                [SystemMessage(content=self.system_prompt), HumanMessage(content=response_prompt)]
            )
            state.messages.append(AIMessage(content=llm_response.content))
        except Exception as e:
            logger.error("IQ RESPOND error: %s" % str(e))
            state.messages.append(AIMessage(content=f"Response generation error: {str(e)}"))
        state.step_count += 1
        return state

    def _format_response(self, state: IQAgentState) -> Dict[str, Any]:
        """Format final IQ response according to output contract"""
        risk_posture = self._determine_risk_posture(state.compliance_posture, state.risk_assessment)
        return {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "risk_posture": risk_posture,
                "compliance_score": state.compliance_posture.get("overall_coverage", 0.0),
                "top_gaps": [
                    gap["requirement"]["title"]
                    for gap in state.graph_context.get("compliance_gaps", [])[:3]
                ],
                "immediate_actions": [action["target"] for action in state.action_plan[:3]],
            },
            "artifacts": {
                "compliance_posture": state.compliance_posture,
                "action_plan": state.action_plan,
                "risk_assessment": state.risk_assessment,
            },
            "graph_context": {
                "nodes_traversed": len(state.graph_context.get("coverage_analysis", [])),
                "patterns_detected": state.patterns_detected,
                "memories_accessed": state.memories_accessed,
                "learnings_applied": len(state.evidence_collected),
            },
            "evidence": {
                "controls_executed": len(
                    [e for e in state.evidence_collected if e.get("status") == "executed"]
                ),
                "evidence_stored": len(state.evidence_collected),
                "metrics_updated": state.graph_context.get("actions_executed", 0),
            },
            "next_actions": [
                {
                    "action": action["target"],
                    "priority": action["priority"].upper(),
                    "owner": "Compliance Team",
                    "graph_reference": action["graph_reference"],
                }
                for action in state.action_plan[:5]
            ],
            "llm_response": state.messages[-1].content
            if state.messages
            else "No response generated",
        }

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
            "low": "180_days",
        }
        return timeline_map.get(risk_level, "90_days")

    def _calculate_overall_risk(self, compliance_posture: Dict[str, Any]) -> str:
        """Calculate overall risk level"""
        coverage = compliance_posture.get("overall_coverage", 0.0)
        critical_gaps = compliance_posture.get("critical_gaps", 0)
        if critical_gaps > DEFAULT_RETRIES or coverage < 0.3:
            return "CRITICAL"
        elif critical_gaps > 2 or coverage < 0.6:
            return "HIGH"
        elif coverage < CONFIDENCE_THRESHOLD:
            return "MEDIUM"
        else:
            return "LOW"

    async def _should_auto_execute(self, action: Dict[str, Any]) -> bool:
        """Determine if action should be executed autonomously"""
        risk_score = action.get("severity_score", 0)
        cost = action.get("cost_estimate", 0)
        return (
            risk_score < self.RISK_THRESHOLD
            and cost < self.AUTONOMY_BUDGET
            and action["priority"] in ["high", "critical"]
        )

    async def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute compliance action (placeholder)"""
        return {
            "action_id": action["action_id"],
            "status": "executed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": "success",
            "evidence_ref": f"evidence_{action['action_id']}",
            "effectiveness": 0.85,
        }

    async def _create_escalation(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Create escalation for manual approval"""
        return {
            "action_id": action["action_id"],
            "status": "escalated",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "Requires manual approval - high risk or cost",
            "approval_required": True,
        }

    async def _store_execution_evidence(
        self, action: Dict[str, Any], result: Dict[str, Any]
    ) -> None:
        """Store execution evidence in graph"""
        pass

    def _detect_compliance_patterns(
        self, graph_context: Dict[str, Any], evidence: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect compliance patterns from current analysis"""
        patterns = []
        gaps = graph_context.get("compliance_gaps", [])
        if gaps:
            domain_gaps = {}
            for gap in gaps:
                domain = gap["domain"]["name"]
                domain_gaps[domain] = domain_gaps.get(domain, 0) + 1
            for domain, count in domain_gaps.items():
                if count > MAX_RETRIES:
                    patterns.append(
                        {
                            "pattern_type": "HIGH_GAP_CONCENTRATION",
                            "domain": domain,
                            "gap_count": count,
                            "confidence": 0.8,
                        }
                    )
        return patterns

    async def _update_control_effectiveness(
        self, evidence: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Update control effectiveness based on execution results"""
        updates = []
        for evidence_item in evidence:
            if evidence_item.get("status") == "executed":
                updates.append(
                    {
                        "control_id": evidence_item["action_id"],
                        "effectiveness": evidence_item.get("effectiveness", 0.8),
                        "updated_at": evidence_item.get(
                            "timestamp", datetime.now(timezone.utc).isoformat()
                        ),
                    }
                )
        return updates

    def _create_response_prompt(self, state: IQAgentState) -> str:
        """Create comprehensive prompt for LLM response generation"""
        return f"""
Based on my analysis of the compliance landscape, please provide a comprehensive response to: "{state.current_query}"

## Current Compliance Posture:
- Overall Coverage: {state.compliance_posture.get("overall_coverage", 0):.2%}
- Total Gaps: {state.compliance_posture.get("total_gaps", 0)}
- Critical Gaps: {state.compliance_posture.get("critical_gaps", 0)}

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

    def _determine_risk_posture(
        self, compliance_posture: Dict[str, Any], risk_assessment: Dict[str, Any]
    ) -> str:
        """Determine overall risk posture"""
        coverage = compliance_posture.get("overall_coverage", 0.0)
        critical_gaps = compliance_posture.get("critical_gaps", 0)
        convergence_patterns = risk_assessment.get("convergence_patterns", 0)
        if critical_gaps > DEFAULT_RETRIES or coverage < 0.4 or convergence_patterns > 10:
            return "CRITICAL"
        elif critical_gaps > 2 or coverage < 0.7 or convergence_patterns > DEFAULT_RETRIES:
            return "HIGH"
        elif coverage < 0.85:
            return "MEDIUM"
        else:
            return "LOW"

    async def process_query_with_context(
        self,
        user_query: str,
        business_profile_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
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
        business_context = {}
        if self.has_postgres_access and business_profile_id:
            try:
                business_context = await self.retrieve_business_context(business_profile_id)
            except Exception as e:
                logger.error("Failed to retrieve business context: %s" % e)
                business_context = {"error": "Failed to retrieve business context"}
        compliance_gaps = []
        try:
            if business_context and "profile" in business_context:
                if business_context["profile"].get("handles_personal_data"):
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
            logger.error("Failed to query Neo4j: %s" % e)
        try:
            business_context_str = (
                json.dumps(business_context, indent=2)
                if business_context
                else "No business context available"
            )
        except (TypeError, ValueError):
            business_context_str = (
                str(business_context) if business_context else "No business context available"
            )
        try:
            compliance_gaps_str = (
                json.dumps(compliance_gaps, indent=2)
                if compliance_gaps
                else "No specific gaps identified"
            )
        except (TypeError, ValueError):
            compliance_gaps_str = (
                str(compliance_gaps) if compliance_gaps else "No specific gaps identified"
            )
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
            logger.error("LLM invocation failed: %s" % e)
            llm_response = "Unable to generate AI response at this time."
        response = {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "business_context": business_context,
            "summary": {
                "risk_posture": "MEDIUM" if compliance_gaps else "LOW",
                "compliance_score": 0.75 if not compliance_gaps else 0.5,
                "top_gaps": [gap.get("title", "") for gap in compliance_gaps[:3]],
                "immediate_actions": [
                    "Review compliance gaps",
                    "Update business profile",
                    "Implement missing controls",
                ],
            },
            "artifacts": {
                "compliance_gaps": compliance_gaps,
                "neo4j_data": {
                    "gaps_found": len(compliance_gaps),
                    "regulations_checked": ["GDPR"] if business_context else [],
                },
            },
            "evidence": {"available_evidence": 0},
            "llm_response": llm_response,
        }
        if self.has_postgres_access and business_profile_id:
            try:
                evidence_count = await self._count_available_evidence(business_profile_id)
                response["evidence"]["available_evidence"] = evidence_count
            except Exception as e:
                logger.error("Failed to count evidence: %s" % e)
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
            profile_stmt = select(BusinessProfile).where(BusinessProfile.id == business_profile_id)
            result = await self.postgres_session.execute(profile_stmt)
            profile = result.scalars().first()
            if not profile:
                return {"error": "Business profile not found"}
            evidence_stmt = (
                select(Evidence)
                .where(Evidence.business_profile_id == business_profile_id)
                .order_by(Evidence.created_at.desc())
                .limit(10)
            )
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
                    "created_at": profile.created_at.isoformat(),
                },
                "evidence": [
                    {
                        "id": str(item.id),
                        "title": item.title,
                        "description": item.description,
                        "evidence_type": item.evidence_type,
                        "file_path": item.file_path,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in evidence_items
                ],
            }
        except Exception as e:
            logger.error("Error retrieving business context: %s" % e)
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
            stmt = select(AssessmentSession).where(AssessmentSession.id == session_id)
            result = await self.postgres_session.execute(stmt)
            session = result.scalars().first()
            if session:
                return {
                    "session_id": str(session.id),
                    "questions_answered": session.questions_answered,
                    "compliance_score": session.compliance_score,
                    "risk_level": session.risk_level,
                    "created_at": session.created_at.isoformat(),
                }
            return None
        except Exception as e:
            logger.error("Error retrieving session context: %s" % e)
            return None

    async def assess_compliance_with_context(
        self, business_profile_id: str, regulations: List[str]
    ) -> Dict[str, Any]:
        """
        Assess compliance for a specific business against regulations.

        Args:
            business_profile_id: Business profile ID
            regulations: List of regulation codes to assess

        Returns:
            Contextualized compliance assessment
        """
        business_context = {}
        if self.has_postgres_access:
            business_context = await self.retrieve_business_context(business_profile_id)
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
        assessment = {
            "status": "success",
            "business_context": business_context,
            "compliance_assessment": {
                "applicable_regulations": regulations,
                "business_specific_risks": self._identify_business_risks(business_context),
                "requirements_analysis": neo4j_result.get("data", []),
                "recommendations": self._generate_contextualized_recommendations(
                    business_context, neo4j_result.get("data", [])
                ),
            },
        }
        return assessment

    async def search_compliance_resources(
        self, query: str, include_evidence: bool = True, include_regulations: bool = True
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
        results = {"query": query, "regulations": [], "evidence": [], "total_results": 0}
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
        if include_evidence and self.has_postgres_access:
            from sqlalchemy import select, or_
            from database.models.evidence import Evidence

            stmt = (
                select(Evidence.title, Evidence.description)
                .where(
                    or_(
                        Evidence.title.ilike(f"%{query}%"), Evidence.description.ilike(f"%{query}%")
                    )
                )
                .limit(10)
            )
            pg_result = await self.postgres_session.execute(stmt)
            evidence_items = pg_result.all()
            results["evidence"] = [{"title": item[0], "relevance": 0.8} for item in evidence_items]
        results["total_results"] = sum(r["matches"] for r in results["regulations"]) + len(
            results["evidence"]
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
        if profile.get("handles_personal_data"):
            risks.append("Personal data processing requires GDPR compliance")
        if profile.get("company_size", "").startswith("201"):
            risks.append("Large organization may require DPO appointment")
        if profile.get("industry") in ["Finance", "Healthcare"]:
            risks.append(f"{profile['industry']} sector has additional regulatory requirements")
        return risks

    def _generate_contextualized_recommendations(
        self, business_context: Dict[str, Any], requirements: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on business context."""
        recommendations = []
        if not business_context or "profile" not in business_context:
            return ["Complete business profile for personalized recommendations"]
        profile = business_context["profile"]
        if profile.get("handles_personal_data") and not business_context.get("evidence"):
            recommendations.append("Upload privacy policy and data processing agreements")
        if len(requirements) > 10:
            recommendations.append(
                f"Focus on {len(requirements)} regulatory requirements identified"
            )
        return recommendations


async def create_iq_agent(neo4j_service: Neo4jGraphRAGService) -> IQComplianceAgent:
    """Factory function to create and initialize IQ agent"""
    agent = IQComplianceAgent(neo4j_service)
    try:
        await neo4j_service.initialize()
        logger.info("IQ Agent: Neo4j connection established")
        graph_stats = await neo4j_service.get_graph_statistics()
        if graph_stats.get("total_nodes", 0) < 10:
            logger.info("IQ Agent: Empty graph detected, attempting to initialize...")
            try:
                await initialize_compliance_graph()
                logger.info("IQ Agent: Compliance graph initialized")
            except Exception as init_error:
                logger.warning(
                    "IQ Agent: Could not initialize graph (read-only mode?): %s" % init_error
                )
                logger.info("IQ Agent: Continuing with empty graph for testing")
    except Exception as e:
        logger.error("IQ Agent initialization error: %s" % str(e))
        raise
    return agent
