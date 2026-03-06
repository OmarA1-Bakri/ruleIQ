"""

GraphRAG Research Engine for UK Compliance Intelligence
Implements machine-actionable research prompts and knowledge graph integration
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from langchain.prompts import PromptTemplate
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)


class ResearchType(Enum):
    """Types of compliance research"""

    REGULATORY_UPDATE = "regulatory_update"
    OBLIGATION_EXTRACTION = "obligation_extraction"
    CONTROL_MAPPING = "control_mapping"
    RISK_ASSESSMENT = "risk_assessment"
    GAP_IDENTIFICATION = "gap_identification"
    CROSS_REGULATION = "cross_regulation"
    ENFORCEMENT_TRENDS = "enforcement_trends"
    BEST_PRACTICES = "best_practices"


@dataclass
class ResearchQuery:
    """Structured research query"""

    query_id: str
    research_type: ResearchType
    query_text: str
    context: Dict[str, Any]
    filters: Dict[str, Any]
    max_results: int = 10
    include_reasoning: bool = True


@dataclass
class ResearchResult:
    """Structured research result"""

    result_id: str
    query_id: str
    findings: List[Dict[str, Any]]
    confidence_score: float
    sources: List[str]
    reasoning: Optional[str] = None
    timestamp: datetime = None


class GraphRAGResearchEngine:
    """
    GraphRAG-powered research engine for automated compliance intelligence
    Integrates with Neo4j knowledge graph and LLM for intelligent research
    """

    RESEARCH_PROMPTS = {
        "obligation_extraction": PromptTemplate(
            input_variables=["regulation_text", "jurisdiction", "industry"],
            template="""
            Extract machine-actionable compliance obligations from the following UK regulatory text.

            Regulation Text: {regulation_text}
            Jurisdiction: {jurisdiction}
            Industry Context: {industry}

            For each obligation identified, extract and structure:

            1. OBLIGATION IDENTIFICATION
            - Unique identifier (reference to regulation section)
            - Obligation title (concise description)
            - Full requirement text
            - Requirement type (mandatory/recommended/optional)

            2. APPLICABILITY
            - Entity types affected
            - Thresholds or conditions
            - Exemptions or exceptions
            - Geographic scope

            3. IMPLEMENTATION REQUIREMENTS
            - Specific actions required
            - Documentation needed
            - Systems/processes required
            - Roles/responsibilities

            4. COMPLIANCE VERIFICATION
            - Evidence required
            - Audit criteria
            - Testing procedures
            - Reporting requirements

            5. TIMELINE & DEADLINES
            - Implementation deadline
            - Reporting frequency
            - Review cycles
            - Transition periods

            6. CONSEQUENCES
            - Penalties for non-compliance
            - Enforcement mechanisms
            - Regulatory powers
            - Appeal processes

            7. AUTOMATION POTENTIAL
            - Automatable components (0-100% score)
            - Integration points
            - Data requirements
            - System dependencies

            Output as structured JSON following the ComplianceObligation schema:
            {{
                "obligations": [
                    {{
                        "id": "UK-GDPR-Art15-1",
                        "title": "Right of Access",
                        "requirement": "...",
                        "type": "mandatory",
                        "applicable_to": [...],
                        "actions": [...],
                        "verification": [...],
                        "timeline": "...",
                        "penalties": {{...}},
                        "automation_score": 0.75
                    }},
                ]
            }}
            """,
        ),
        "control_mapping": PromptTemplate(
            input_variables=["obligations", "existing_controls", "framework"],
            template="""
            Map compliance obligations to controls following UK regulatory standards.

            Obligations: {obligations}
            Existing Controls: {existing_controls}
            Framework: {framework}

            Perform comprehensive control mapping:

            1. CONTROL IDENTIFICATION
            For each obligation, identify:
            - Required controls (must-have)
            - Recommended controls (should-have)
            - Optional enhancements (nice-to-have)

            2. CONTROL EFFECTIVENESS MAPPING
            - Preventive controls
            - Detective controls
            - Corrective controls
            - Compensating controls

            3. UK FRAMEWORK ALIGNMENT
            - ISO 27001 mapping
            - NIST CSF mapping
            - ICO guidance alignment
            - FCA handbook requirements

            4. GAP ANALYSIS
            - Missing controls
            - Inadequate controls
            - Redundant controls
            - Optimization opportunities

            5. IMPLEMENTATION PRIORITY
            Priority 1: Regulatory mandated
            Priority 2: High risk mitigation
            Priority 3: Best practices
            Priority 4: Enhancements

            6. CONTROL TESTING
            - Test procedures
            - Frequency requirements
            - Evidence requirements
            - Remediation timelines

            Output structured control mapping with clear traceability.
            """,
        ),
        "risk_assessment_research": PromptTemplate(
            input_variables=["organization_profile", "regulations", "industry_context"],
            template="""
            Conduct regulatory risk research for UK compliance.

            Organization: {organization_profile}
            Regulations: {regulations}
            Industry: {industry_context}

            Research and analyze:

            1. REGULATORY ENFORCEMENT TRENDS
            - Recent UK enforcement actions
            - Penalty trends and amounts
            - Focus areas by regulators
            - Industry-specific enforcement

            2. INHERENT RISK FACTORS
            - Business model risks
            - Geographic risks
            - Customer base risks
            - Product/service risks
            - Third-party risks

            3. UK-SPECIFIC RISK INDICATORS
            - ICO enforcement priorities
            - FCA thematic reviews
            - SFO investigation trends
            - HSE focus areas
            - HMRC compliance campaigns

            4. PEER ANALYSIS
            - Industry incidents
            - Competitor penalties
            - Sector vulnerabilities
            - Best practice adoption

            5. EMERGING RISKS
            - Upcoming regulations
            - Technology risks
            - Geopolitical factors
            - Climate/ESG requirements

            6. RISK SCORING METHODOLOGY
            - Likelihood assessment (1-5)
            - Impact assessment (1-5)
            - Velocity (speed of onset)
            - Vulnerability factors
            - Control effectiveness

            Provide risk intelligence with actionable insights.
            """,
        ),
        "cross_regulation_analysis": PromptTemplate(
            input_variables=["regulations", "organization_scope", "conflicts"],
            template="""
            Analyze cross-regulation requirements and conflicts for UK compliance.

            Regulations: {regulations}
            Scope: {organization_scope}
            Known Conflicts: {conflicts}

            Perform cross-regulation analysis:

            1. OVERLAPPING REQUIREMENTS
            - Common obligations across regulations
            - Unified compliance opportunities
            - Consolidated controls
            - Shared evidence/documentation

            2. CONFLICTING REQUIREMENTS
            - Direct conflicts
            - Interpretation differences
            - Timing conflicts
            - Scope conflicts

            3. UK REGULATORY HIERARCHY
            - Primary legislation precedence
            - Secondary legislation
            - Regulatory guidance
            - Industry codes

            4. RESOLUTION STRATEGIES
            - Conflict resolution approaches
            - Regulator consultation needs
            - Legal opinion requirements
            - Risk-based decisions

            5. INTEGRATION OPPORTUNITIES
            - Unified compliance framework
            - Common control framework
            - Integrated reporting
            - Consolidated assessments

            6. EFFICIENCY GAINS
            - Deduplication opportunities
            - Process consolidation
            - Technology leverage
            - Resource optimization

            Output integration strategy with conflict resolution.
            """,
        ),
        "regulatory_change_detection": PromptTemplate(
            input_variables=["current_requirements", "regulatory_updates", "horizon_scanning"],
            template="""
            Detect and analyze UK regulatory changes impacting compliance.

            Current Requirements: {current_requirements}
            Recent Updates: {regulatory_updates}
            Horizon Scanning: {horizon_scanning}

            Analyze regulatory changes:

            1. IMMEDIATE CHANGES
            - In-force date passed
            - Immediate compliance required
            - Emergency measures
            - Enforcement commenced

            2. UPCOMING CHANGES (0-6 MONTHS)
            - Confirmed effective dates
            - Final rules published
            - Transition periods ending
            - Grace periods expiring

            3. FUTURE CHANGES (6-24 MONTHS)
            - Proposed regulations
            - Consultation outcomes
            - Draft legislation
            - Policy statements

            4. HORIZON RISKS (24+ MONTHS)
            - Green papers
            - Policy discussions
            - International developments
            - Technology-driven changes

            5. CHANGE IMPACT ASSESSMENT
            - Operational impact
            - System changes required
            - Process updates needed
            - Training requirements
            - Cost implications

            6. IMPLEMENTATION ROADMAP
            - Critical path items
            - Dependencies
            - Resource requirements
            - Milestone dates
            - Success criteria

            Provide actionable change intelligence with clear timelines.
            """,
        ),
        "enforcement_pattern_analysis": PromptTemplate(
            input_variables=["enforcement_data", "organization_profile", "time_period"],
            template="""
            Analyze UK regulatory enforcement patterns for risk insights.

            Enforcement Data: {enforcement_data}
            Organization Profile: {organization_profile}
            Period: {time_period}

            Analyze enforcement patterns:

            1. ENFORCEMENT STATISTICS
            - Total actions by regulator
            - Penalty amounts and trends
            - Most common violations
            - Industry distribution

            2. VIOLATION PATTERNS
            - Root causes identified
            - Systemic issues
            - Repeat offenses
            - Aggravating factors

            3. REGULATOR FOCUS AREAS
            - ICO priorities
            - FCA themes
            - CMA investigations
            - HSE campaigns
            - HMRC focus

            4. PENALTY CALCULATIONS
            - Base penalty amounts
            - Aggravating factors
            - Mitigating factors
            - Settlement discounts
            - Appeal outcomes

            5. ORGANIZATIONAL RELEVANCE
            - Similar organization actions
            - Industry-specific risks
            - Size/complexity factors
            - Geographic considerations

            6. PREDICTIVE INDICATORS
            - Early warning signs
            - Risk indicators
            - Inspection triggers
            - Complaint patterns

            Provide enforcement intelligence with risk mitigation strategies.
            """,
        ),
    }

    def __init__(self, neo4j_uri: str, neo4j_auth: tuple, llm_client) -> None:
        self.neo4j_driver = AsyncGraphDatabase.driver(neo4j_uri, auth=neo4j_auth)
        self.llm_client = llm_client
        self.research_cache = {}

    async def conduct_research(
        self, query: ResearchQuery, use_cache: bool = True
    ) -> ResearchResult:
        """
        Execute comprehensive research workflow
        """
        if use_cache and query.query_id in self.research_cache:
            logger.info("Using cached research for query %s" % query.query_id)
            return self.research_cache[query.query_id]
        try:
            graph_context = await self._query_knowledge_graph(query)
            research_prompts = self._generate_research_prompts(query, graph_context)
            llm_results = await self._execute_llm_research(research_prompts)
            synthesized_results = await self._synthesize_findings(llm_results, graph_context, query)
            research_result = self._structure_results(synthesized_results, query)
            if use_cache:
                self.research_cache[query.query_id] = research_result
            return research_result
        except Exception as e:
            logger.error("Research failed for query %s: %s" % (query.query_id, str(e)))
            raise

    async def _query_knowledge_graph(self, query: ResearchQuery) -> Dict[str, Any]:
        """Query Neo4j knowledge graph for relevant context"""
        async with self.neo4j_driver.session() as session:
            cypher_query = self._build_cypher_query(query)
            result = await session.run(cypher_query, query=query.query_text)
            records = await result.values()
            return {
                "nodes": [r[0] for r in records if len(r) > 0],
                "relationships": [r[1] for r in records if len(r) > 1],
                "properties": [r[2] for r in records if len(r) > 2],
            }

    def _build_cypher_query(self, query: ResearchQuery) -> str:
        """Build appropriate Cypher query for research type"""
        query_templates = {
            ResearchType.OBLIGATION_EXTRACTION: """
                MATCH (r:Regulation {jurisdiction: 'UK'})-[:CONTAINS]->(o:Obligation)
                WHERE o.text CONTAINS $query OR o.title CONTAINS $query
                OPTIONAL MATCH (o)-[:REQUIRES]->(c:Control)
                OPTIONAL MATCH (o)-[:HAS_PENALTY]->(p:Penalty)
                RETURN o, collect(DISTINCT c), collect(DISTINCT p)
                LIMIT 50
            """,
            ResearchType.CONTROL_MAPPING: """
                MATCH (o:Obligation)-[:REQUIRES]->(c:Control)
                WHERE o.id IN $obligation_ids
                OPTIONAL MATCH (c)-[:MAPS_TO]->(f:Framework)
                OPTIONAL MATCH (c)-[:TESTED_BY]->(t:Test)
                RETURN o, c, collect(DISTINCT f), collect(DISTINCT t)
            """,
            ResearchType.RISK_ASSESSMENT: """
                MATCH (r:Risk)-[:AFFECTS]->(o:Obligation)
                WHERE r.industry = $industry OR r.type = 'universal'
                OPTIONAL MATCH (r)-[:MITIGATED_BY]->(c:Control)
                OPTIONAL MATCH (r)-[:RESULTED_IN]->(e:Enforcement)
                RETURN r, o, collect(DISTINCT c), collect(DISTINCT e)
                ORDER BY r.severity DESC
                LIMIT 25
            """,
            ResearchType.CROSS_REGULATION: """
                MATCH (r1:Regulation)-[:CONTAINS]->(o1:Obligation)
                MATCH (r2:Regulation)-[:CONTAINS]->(o2:Obligation)
                WHERE r1.id <> r2.id
                AND (o1.requirement CONTAINS $query OR o2.requirement CONTAINS $query)
                AND (o1)-[:CONFLICTS_WITH|:OVERLAPS_WITH]-(o2)
                RETURN r1, r2, o1, o2, type(o1-[]-o2) as relationship
            """,
            ResearchType.ENFORCEMENT_TRENDS: """
                MATCH (e:Enforcement)-[:FOR_VIOLATION_OF]->(o:Obligation)
                WHERE e.date >= date({year: date().year - 2})
                AND e.jurisdiction = 'UK'
                OPTIONAL MATCH (e)-[:AGAINST]->(org:Organization)
                RETURN e, o, org
                ORDER BY e.penalty_amount DESC
                LIMIT 100
            """,
        }
        return query_templates.get(
            query.research_type, query_templates[ResearchType.OBLIGATION_EXTRACTION]
        )

    def _generate_research_prompts(
        self, query: ResearchQuery, graph_context: Dict[str, Any]
    ) -> List[str]:
        """Generate specific research prompts based on query and context"""
        prompt_template = self.RESEARCH_PROMPTS.get(
            query.research_type.value, self.RESEARCH_PROMPTS["obligation_extraction"]
        )
        prompt_context = {
            **query.context,
            "graph_nodes": json.dumps(graph_context.get("nodes", [])[:10]),
            "graph_relationships": json.dumps(graph_context.get("relationships", [])[:10]),
        }
        prompts = []
        main_prompt = prompt_template.format(**prompt_context)
        prompts.append(main_prompt)
        if query.research_type == ResearchType.OBLIGATION_EXTRACTION:
            for category in ["data_protection", "financial_conduct", "anti_money_laundering"]:
                specialized_context = {
                    **prompt_context,
                    "focus_area": category,
                }
                prompts.append(prompt_template.format(**specialized_context))
        return prompts

    async def _execute_llm_research(self, prompts: List[str]) -> List[Dict[str, Any]]:
        """Execute research prompts using LLM"""
        results = []
        batch_size = 5
        for i in range(0, len(prompts), batch_size):
            batch = prompts[i : i + batch_size]
            tasks = [self.llm_client.agenerate([prompt]) for prompt in batch]
            batch_results = await asyncio.gather(*tasks)
            for result in batch_results:
                try:
                    parsed = json.loads(result.generations[0][0].text)
                    results.append(parsed)
                except json.JSONDecodeError:
                    results.append({"raw_text": result.generations[0][0].text})
        return results

    async def _synthesize_findings(
        self, llm_results: List[Dict], graph_context: Dict, query: ResearchQuery
    ) -> Dict[str, Any]:
        """Synthesize findings from multiple sources"""
        synthesis_prompt = """
        Synthesize the following research findings into actionable intelligence.

        Research Query: {query}
        LLM Findings: {llm_findings}
        Graph Context: {graph_context}

        Provide:
        1. Key findings (prioritized)
        2. Confidence assessment
        3. Evidence sources
        4. Actionable recommendations
        5. Further research needed

        Output as structured JSON.
        """
        synthesis_context = {
            "query": query.query_text,
            "llm_findings": json.dumps(llm_results[:5]),
            "graph_context": json.dumps(
                {
                    "node_count": len(graph_context.get("nodes", [])),
                    "relationship_count": len(graph_context.get("relationships", [])),
                    "sample_nodes": graph_context.get("nodes", [])[:3],
                }
            ),
        }
        synthesis_result = await self.llm_client.agenerate(
            [synthesis_prompt.format(**synthesis_context)]
        )
        try:
            return json.loads(synthesis_result.generations[0][0].text)
        except json.JSONDecodeError:
            return {"synthesis": synthesis_result.generations[0][0].text}

    def _structure_results(
        self, synthesized: Dict[str, Any], query: ResearchQuery
    ) -> ResearchResult:
        """Structure final research results"""
        findings = synthesized.get("findings", synthesized)
        confidence = self._calculate_confidence(synthesized)
        sources = self._extract_sources(synthesized)
        return ResearchResult(
            result_id=f"result_{query.query_id}_{datetime.now().timestamp()}",
            query_id=query.query_id,
            findings=findings if isinstance(findings, list) else [findings],
            confidence_score=confidence,
            sources=sources,
            reasoning=synthesized.get("reasoning") if query.include_reasoning else None,
            timestamp=datetime.now(),
        )

    def _calculate_confidence(self, synthesized: Dict) -> float:
        """Calculate confidence score for research results"""
        base_confidence = 0.5
        if synthesized.get("evidence_sources"):
            base_confidence += 0.1 * min(len(synthesized["evidence_sources"]), 3)
        if synthesized.get("consistency_score"):
            base_confidence += 0.2 * synthesized["consistency_score"]
        if synthesized.get("conflicts"):
            base_confidence -= 0.1 * min(len(synthesized["conflicts"]), 2)
        return min(max(base_confidence, 0.0), 1.0)

    def _extract_sources(self, synthesized: Dict) -> List[str]:
        """Extract and format sources"""
        sources = []
        if "sources" in synthesized:
            sources.extend(synthesized["sources"])
        if "evidence_sources" in synthesized:
            sources.extend(synthesized["evidence_sources"])
        if "graph_references" in synthesized:
            sources.extend([f"KG:{ref}" for ref in synthesized["graph_references"]])
        return list(set(sources))

    async def close(self) -> None:
        """Clean up resources"""
        await self.neo4j_driver.close()
