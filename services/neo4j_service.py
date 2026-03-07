"""

Neo4j GraphRAG Service for Compliance Intelligence
Implements comprehensive graph database operations for CCO compliance knowledge
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ClientError
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class Neo4jGraphRAGService:
    """
    Production-ready Neo4j service for compliance intelligence with GraphRAG capabilities

    All Neo4j credentials must be provided via environment variables (NEO4J_URI, NEO4J_USERNAME,
    NEO4J_PASSWORD). The service will fail to initialize if required credentials are not set.
    Use Doppler for production: doppler run -- python main.py
    """

    def __init__(self) -> None:
        self.driver: Optional[Driver] = None
        self.uri = os.getenv("NEO4J_URI")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        self.executor = ThreadPoolExecutor(max_workers=10)

        # Validate required environment variables
        if not self.uri:
            raise ValueError(
                "NEO4J_URI environment variable is required. "
                "Set it in your environment or use Doppler: doppler run -- python main.py"
            )
        if not self.username:
            raise ValueError(
                "NEO4J_USERNAME environment variable is required. "
                "Set it in your environment or use Doppler: doppler run -- python main.py"
            )
        if not self.password:
            raise ValueError(
                "NEO4J_PASSWORD environment variable is required. "
                "Set it in your environment or use Doppler: doppler run -- python main.py. "
                "NEVER use default passwords in production."
            )

        logger.info(f"Neo4j service initialized with URI: {self.uri}")

    async def initialize(self) -> bool:
        """Initialize Neo4j connection and verify schema"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )
            if not await self._verify_connection():
                raise Exception("Neo4j connection verification failed")
            await self._initialize_schema()
            logger.info("Neo4j GraphRAG service initialized successfully")
            return True
        except Exception as e:
            logger.error("Failed to initialize Neo4j service: %s" % e)
            return False

    async def _verify_connection(self) -> bool:
        """Verify Neo4j connection is working"""

        def _test_connection() -> bool:
            if self.driver is None:
                return False
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS test")
                record = result.single()
                return record is not None and record["test"] == 1

        try:
            result = await asyncio.get_event_loop().run_in_executor(self.executor, _test_connection)
            return result
        except Exception as e:
            logger.error("Neo4j connection test failed: %s" % e)
            return False

    async def _initialize_schema(self) -> None:
        """Initialize Neo4j schema with indexes and constraints"""
        indexes = [
            "CREATE INDEX regulation_jurisdiction IF NOT EXISTS FOR (r:Regulation) ON (r.jurisdiction)",
            "CREATE INDEX requirement_mandatory IF NOT EXISTS FOR (req:Requirement) ON (req.mandatory)",
            "CREATE INDEX control_status IF NOT EXISTS FOR (c:Control) ON (c.implementation_status)",
            "CREATE INDEX risk_score IF NOT EXISTS FOR (r:Risk) ON (r.risk_score)",
            "CREATE INDEX metric_type IF NOT EXISTS FOR (m:Metric) ON (m.type)",
            "CREATE INDEX vendor_criticality IF NOT EXISTS FOR (v:Vendor) ON (v.criticality)",
            "CREATE INDEX milestone_timeline IF NOT EXISTS FOR (m:Milestone) ON (m.timeline)",
            "CREATE INDEX domain_priority IF NOT EXISTS FOR (d:ComplianceDomain) ON (d.priority)",
        ]
        constraints = [
            "CREATE CONSTRAINT regulation_name IF NOT EXISTS FOR (r:Regulation) REQUIRE r.name IS UNIQUE",
            "CREATE CONSTRAINT requirement_id IF NOT EXISTS FOR (req:Requirement) REQUIRE req.id IS UNIQUE",
            "CREATE CONSTRAINT control_id IF NOT EXISTS FOR (c:Control) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT risk_id IF NOT EXISTS FOR (r:Risk) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (d:ComplianceDomain) REQUIRE d.name IS UNIQUE",
        ]

        def _create_schema() -> None:
            if self.driver is None:
                return
            with self.driver.session(database=self.database) as session:
                for index_query in indexes:
                    try:
                        session.run(index_query)
                    except ClientError as e:
                        if "already exists" not in str(e):
                            logger.warning("Index creation warning: %s" % e)
                for constraint_query in constraints:
                    try:
                        session.run(constraint_query)
                    except ClientError as e:
                        if "already exists" not in str(e):
                            logger.warning("Constraint creation warning: %s" % e)

        try:
            await asyncio.get_event_loop().run_in_executor(self.executor, _create_schema)
            logger.info("Neo4j schema initialized")
        except Exception as e:
            logger.error("Schema initialization failed: %s" % e)
            raise

    async def execute_query(
        self, query: str, parameters: Optional[Dict[str, Any]] = None, read_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results"""

        def _run_query() -> List[Dict[str, Any]]:
            if self.driver is None:
                return []
            access_mode = "READ" if read_only else "WRITE"
            with self.driver.session(
                database=self.database, default_access_mode=access_mode
            ) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]

        try:
            result = await asyncio.get_event_loop().run_in_executor(self.executor, _run_query)
            return result
        except Exception as e:
            logger.error("Query execution failed: %s" % e)
            logger.error("Query: %s" % query)
            logger.error("Parameters: %s" % parameters)
            raise

    async def execute_transaction(self, queries: List[Tuple[str, Dict[str, Any]]]) -> bool:
        """Execute multiple queries in a transaction"""

        def _run_transaction() -> bool:
            if self.driver is None:
                return False
            with self.driver.session(database=self.database) as session:
                with session.begin_transaction() as tx:
                    for query, params in queries:
                        tx.run(query, params)
                    tx.commit()
                    return True

        try:
            result = await asyncio.get_event_loop().run_in_executor(self.executor, _run_transaction)
            return result
        except Exception as e:
            logger.error("Transaction failed: %s" % e)
            return False

    async def get_compliance_coverage(self, domain_name: Optional[str] = None) -> Dict[str, Any]:
        """Get compliance coverage analysis for a domain"""
        if domain_name:
            query = """
            MATCH (domain:ComplianceDomain {name: $domain_name})-[:GOVERNS]->(reg:Regulation)
                  -[:REQUIRES]->(req:Requirement)
            OPTIONAL MATCH (req)<-[:IMPLEMENTS]-(ctrl:Control)
            RETURN domain.name AS domain,
                   reg.name AS regulation,
                   COUNT(req) AS total_requirements,
                   COUNT(ctrl) AS implemented_controls,
                   ROUND(100.0 * COUNT(ctrl) / COUNT(req), 2) AS coverage_percentage
            """
            params = {"domain_name": domain_name}
        else:
            query = """
            MATCH (domain:ComplianceDomain)-[:GOVERNS]->(reg:Regulation)
                  -[:REQUIRES]->(req:Requirement)
            OPTIONAL MATCH (req)<-[:IMPLEMENTS]-(ctrl:Control)
            RETURN domain.name AS domain,
                   reg.name AS regulation,
                   COUNT(req) AS total_requirements,
                   COUNT(ctrl) AS implemented_controls,
                   ROUND(100.0 * COUNT(ctrl) / COUNT(req), 2) AS coverage_percentage
            ORDER BY domain.priority, coverage_percentage DESC
            """
            params = {}
        results = await self.execute_query(query, params)
        return {"coverage_analysis": results}

    async def get_unimplemented_requirements(self) -> Dict[str, Any]:
        """Find all unimplemented mandatory requirements"""
        query = """
        MATCH (reg:Regulation)-[:REQUIRES {mandatory: true}]->(req:Requirement)
        WHERE NOT EXISTS((req)<-[:IMPLEMENTS]-(:Control))
        RETURN reg.name AS regulation,
               req.title AS requirement,
               req.deadline AS deadline,
               req.description AS description
        ORDER BY req.deadline
        """
        results = await self.execute_query(query)
        return {"unimplemented_requirements": results}

    async def calculate_residual_risks(self) -> Dict[str, Any]:
        """Calculate residual risk across all domains"""
        query = """
        MATCH (risk:Risk)
        OPTIONAL MATCH (risk)<-[m:MITIGATES]-(ctrl:Control)
        WITH risk,
             risk.risk_score AS inherent_risk,
             COALESCE(AVG(m.mitigation_percentage), 0) AS avg_mitigation
        RETURN risk.name AS risk_name,
               risk.category AS category,
               inherent_risk,
               ROUND(inherent_risk * (1 - avg_mitigation/100.0), 2) AS residual_risk,
               CASE
                 WHEN inherent_risk * (1 - avg_mitigation/100.0) >= 15 THEN 'HIGH'
                 WHEN inherent_risk * (1 - avg_mitigation/100.0) >= 10 THEN 'MEDIUM'
                 ELSE 'LOW'
               END AS risk_level
        ORDER BY residual_risk DESC
        """
        results = await self.execute_query(query)
        return {"residual_risks": results}

    async def get_unmitigated_high_risks(self) -> Dict[str, Any]:
        """Find high-risk areas needing immediate attention"""
        query = """
        MATCH (risk:Risk)
        WHERE risk.risk_score >= 15
        AND NOT EXISTS((risk)<-[:MITIGATES]-(:Control))
        RETURN risk.name AS risk_name,
               risk.category AS category,
               risk.description AS description,
               risk.risk_score AS score
        ORDER BY risk.risk_score DESC
        """
        results = await self.execute_query(query)
        return {"unmitigated_high_risks": results}

    async def find_regulatory_convergence(self) -> Dict[str, Any]:
        """Find common requirements across jurisdictions"""
        query = """
        MATCH (j1:Jurisdiction)-[:ENFORCES]->(r1:Regulation)-[:REQUIRES]->(req1:Requirement)
        MATCH (j2:Jurisdiction)-[:ENFORCES]->(r2:Regulation)-[:REQUIRES]->(req2:Requirement)
        WHERE j1.code <> j2.code
          AND req1.description = req2.description
        RETURN DISTINCT req1.title AS common_requirement,
               COLLECT(DISTINCT j1.code + ':' + r1.name) AS regulations
        ORDER BY size(COLLECT(DISTINCT j1.code)) DESC
        """
        results = await self.execute_query(query)
        return {"regulatory_convergence": results}

    async def analyze_control_effectiveness(self) -> Dict[str, Any]:
        """Analyze control effectiveness and automation levels"""
        query = """
        MATCH (ctrl:Control)
        OPTIONAL MATCH (ctrl)-[impl:IMPLEMENTS]->(req:Requirement)
        OPTIONAL MATCH (ctrl)-[mit:MITIGATES]->(risk:Risk)
        OPTIONAL MATCH (metric:Metric)-[:MEASURES]->(ctrl)
        RETURN ctrl.name AS control,
               ctrl.automation_level AS automation,
               ctrl.implementation_status AS status,
               COUNT(DISTINCT req) AS requirements_addressed,
               COUNT(DISTINCT risk) AS risks_mitigated,
               COLLECT(DISTINCT metric.name) AS metrics,
               CASE ctrl.automation_level
                 WHEN 'FULLY_AUTOMATED' THEN 3
                 WHEN 'SEMI_AUTOMATED' THEN 2
                 WHEN 'MANUAL' THEN 1
                 ELSE 0
               END AS automation_score
        ORDER BY COUNT(DISTINCT req) DESC, automation_score DESC
        """
        results = await self.execute_query(query)
        return {"control_effectiveness": results}

    async def get_manual_controls_needing_automation(self) -> Dict[str, Any]:
        """Find manual controls that need technology enablement"""
        query = """
        MATCH (ctrl:Control {automation_level: 'MANUAL'})
        WHERE ctrl.implementation_status IN ['NOT_STARTED', 'IN_PROGRESS']
        OPTIONAL MATCH (ctrl)-[:IMPLEMENTS]->(req:Requirement {mandatory: true})
        RETURN ctrl.name AS manual_control,
               ctrl.type AS control_type,
               COUNT(req) AS mandatory_requirements,
               ctrl.description AS description,
               ctrl.frequency AS frequency
        ORDER BY COUNT(req) DESC
        """
        results = await self.execute_query(query)
        return {"automation_candidates": results}

    async def learn_from_enforcement_actions(self) -> Dict[str, Any]:
        """Extract lessons from enforcement actions"""
        query = """
        MATCH (ea:EnforcementAction)-[:PRECEDENT_FOR]->(ctrl:Control)
        OPTIONAL MATCH (ctrl)-[:IMPLEMENTS]->(req:Requirement)
        RETURN ea.target_company AS company,
               ea.violation_type AS violation,
               ea.penalty_amount AS fine,
               ea.lessons_learned AS lessons,
               ea.date AS incident_date,
               COLLECT(DISTINCT ctrl.name) AS controls_to_strengthen,
               COLLECT(DISTINCT req.title) AS requirements_affected
        ORDER BY ea.penalty_amount DESC
        """
        results = await self.execute_query(query)
        return {"enforcement_lessons": results}

    async def get_compliance_metrics_dashboard(self) -> Dict[str, Any]:
        """Get KPI/KRI dashboard data"""
        query = """
        MATCH (m:Metric)
        OPTIONAL MATCH (m)-[:MEASURES]->(ctrl:Control)
        RETURN m.type AS metric_type,
               m.name AS metric,
               m.current_value AS current,
               m.target_value AS target,
               m.frequency AS frequency,
               m.owner AS owner,
               CASE
                 WHEN m.type = 'KPI' AND m.current_value < m.target_value THEN 'GREEN'
                 WHEN m.type = 'KRI' AND m.current_value > m.target_value THEN 'RED'
                 ELSE 'AMBER'
               END AS status,
               COLLECT(ctrl.name) AS related_controls
        ORDER BY m.type, status DESC
        """
        results = await self.execute_query(query)
        return {"metrics_dashboard": results}

    async def query_by_domain_and_jurisdiction(
        self, domain: str, jurisdiction: str
    ) -> Dict[str, Any]:
        """Natural language query: What are the requirements for [DOMAIN] in [JURISDICTION]?"""
        query = """
        MATCH (domain:ComplianceDomain {name: $domain})
              -[:GOVERNS]->(reg:Regulation {jurisdiction: $jurisdiction})
              -[:REQUIRES]->(req:Requirement)
        RETURN reg.name AS regulation,
               COLLECT({
                 title: req.title,
                 description: req.description,
                 mandatory: req.mandatory,
                 deadline: req.deadline,
                 article_reference: req.article_reference
               }) AS requirements
        """
        params = {"domain": domain, "jurisdiction": jurisdiction}
        results = await self.execute_query(query, params)
        return {"domain_requirements": results}

    async def query_controls_for_regulation(self, regulation: str) -> Dict[str, Any]:
        """Natural language query: What controls do we need for [REGULATION]?"""
        query = """
        MATCH (reg:Regulation {name: $regulation})-[:REQUIRES]->(req:Requirement)
        OPTIONAL MATCH (req)<-[:IMPLEMENTS]-(ctrl:Control)
        RETURN req.title AS requirement,
               req.mandatory AS is_mandatory,
               COLLECT(ctrl.name) AS existing_controls,
               CASE
                 WHEN SIZE(COLLECT(ctrl)) = 0 THEN 'MISSING'
                 ELSE 'IMPLEMENTED'
               END AS status
        ORDER BY req.mandatory DESC, status
        """
        params = {"regulation": regulation}
        results = await self.execute_query(query, params)
        return {"regulation_controls": results}

    async def find_compliance_gaps(self) -> Dict[str, Any]:
        """Use graph patterns to identify compliance gaps"""
        query = """
        MATCH (domain:ComplianceDomain)-[:GOVERNS]->(reg:Regulation)
              -[:REQUIRES]->(req:Requirement)
        WHERE NOT EXISTS((req)<-[:IMPLEMENTS]-(:Control))
          AND req.mandatory = true
        RETURN domain.name AS domain,
               domain.priority AS priority,
               reg.name AS regulation,
               COUNT(req) AS missing_controls,
               COLLECT(req.title) AS unimplemented_requirements
        ORDER BY domain.priority, missing_controls DESC
        """
        results = await self.execute_query(query)
        return {"compliance_gaps": results}

    async def trace_risk_mitigation_chain(self, risk_name: str) -> Dict[str, Any]:
        """Trace risk mitigation through controls to technology"""
        query = """
        MATCH (risk:Risk {name: $risk_name})<-[:MITIGATES]-(control:Control)
        OPTIONAL MATCH (control)<-[:MONITORS]-(tech:Technology)
        RETURN risk.name AS risk,
               risk.risk_score AS inherent_risk,
               control.name AS control,
               control.automation_level AS automation,
               tech.name AS technology,
               tech.category AS tech_category
        """
        params = {"risk_name": risk_name}
        results = await self.execute_query(query, params)
        return {"mitigation_chain": results}

    async def bulk_load_compliance_data(self, data_file: str) -> bool:
        """Load compliance data from JSON file"""
        try:
            with open(data_file, "r") as f:
                data = json.load(f)
            if "domains" in data:
                query = """
                UNWIND $domains AS d
                CREATE (domain:ComplianceDomain {
                    name: d.name,
                    description: d.description,
                    priority: d.priority,
                    regulatory_severity: d.regulatory_severity
                })
                """
                await self.execute_query(query, {"domains": data["domains"]}, read_only=False)
            if "regulations" in data:
                query = """
                UNWIND $regulations AS r
                CREATE (reg:Regulation {
                    name: r.name,
                    full_name: r.full_name,
                    jurisdiction: r.jurisdiction,
                    effective_date: date(r.effective_date),
                    enforcement_body: r.enforcement_body,
                    description: r.description,
                    penalty_range: r.penalty_range,
                    status: r.status
                })
                """
                await self.execute_query(
                    query, {"regulations": data["regulations"]}, read_only=False
                )
            logger.info("Successfully loaded compliance data from %s" % data_file)
            return True
        except Exception as e:
            logger.error("Failed to load compliance data: %s" % e)
            return False

    async def get_graph_statistics(self) -> Dict[str, Any]:
        """Get basic graph statistics for initialization check"""
        try:
            query = """
            MATCH (n)
            RETURN count(n) as total_nodes
            """
            result = await self.execute_query(query, read_only=True)
            return result[0] if result else {"total_nodes": 0}
        except Exception as e:
            logger.error("Failed to get graph statistics: %s" % e)
            return {"total_nodes": 0}

    async def close(self) -> None:
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            self.executor.shutdown(wait=True)
            logger.info("Neo4j service closed")


_neo4j_service: Optional[Neo4jGraphRAGService] = None


async def get_neo4j_service() -> Neo4jGraphRAGService:
    """Get or create the global Neo4j service instance"""
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jGraphRAGService()
        await _neo4j_service.initialize()
    return _neo4j_service


async def initialize_neo4j_service() -> Any:
    """Initialize the global Neo4j service"""
    service = await get_neo4j_service()
    return service
