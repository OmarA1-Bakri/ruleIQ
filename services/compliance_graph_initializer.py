"""
Compliance Graph Initializer for IQ Agent GraphRAG System

This module loads CCO (Chief Compliance Officer) playbook data into Neo4j
to enable intelligent compliance analysis through graph-based retrieval.

Schema includes 20+ node types covering:
- Compliance Domains (AML, Data Protection, Operational Risk, etc.)
- Jurisdictions (UK, EU, US, etc.)
- Regulations (6AMLD, GDPR, DORA, BSA, etc.)
- Requirements, Controls, Metrics, and Risk Assessments
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from services.neo4j_service import Neo4jGraphRAGService

logger = logging.getLogger(__name__)


@dataclass
class ComplianceDomain:
    """Core compliance domain structure"""

    name: str
    description: str
    risk_level: str
    regulatory_scope: List[str]
    business_impact: str
    oversight_body: Optional[str] = None


@dataclass
class Jurisdiction:
    """Legal jurisdiction structure"""

    name: str
    code: str
    regulatory_authority: str
    enforcement_approach: str
    penalties_framework: str
    data_localization: bool = False


@dataclass
class Regulation:
    """Regulatory framework structure"""

    name: str
    code: str
    jurisdiction: str
    compliance_domain: str
    effective_date: str
    last_updated: str
    risk_rating: str
    penalty_framework: str
    extraterritorial_reach: bool


@dataclass
class Requirement:
    """Specific regulatory requirement"""

    regulation_code: str
    section: str
    title: str
    description: str
    mandatory: bool
    deadline_type: str
    risk_level: str
    business_function: str


@dataclass
class Control:
    """Control measure for compliance"""

    name: str
    control_type: str
    requirements: List[str]
    implementation_guidance: str
    testing_frequency: str
    automation_level: str
    cost_impact: str


@dataclass
class ComplianceMetric:
    """Compliance measurement and KPI"""

    name: str
    metric_type: str
    calculation_method: str
    target_value: str
    reporting_frequency: str
    data_source: str
    controls: List[str]


class ComplianceGraphInitializer:
    """Initializes Neo4j graph with CCO compliance playbook data"""

    def __init__(self, neo4j_service: Neo4jGraphRAGService) -> None:
        self.neo4j = neo4j_service

    async def initialize_full_compliance_graph(self) -> Dict[str, Any]:
        """Initialize complete compliance graph with all CCO data"""
        try:
            logger.info("Starting full compliance graph initialization")
            await self._clear_existing_data()
            await self._create_schema_constraints()
            domains_created = await self._load_compliance_domains()
            jurisdictions_created = await self._load_jurisdictions()
            regulations_created = await self._load_regulations()
            requirements_created = await self._load_requirements()
            controls_created = await self._load_controls()
            metrics_created = await self._load_metrics()
            relationships_created = await self._create_relationships()
            risks_created = await self._load_risk_assessments()
            enforcement_created = await self._load_enforcement_cases()
            temporal_created = await self._create_temporal_relationships()
            result = {
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "nodes_created": {
                    "compliance_domains": domains_created,
                    "jurisdictions": jurisdictions_created,
                    "regulations": regulations_created,
                    "requirements": requirements_created,
                    "controls": controls_created,
                    "metrics": metrics_created,
                    "risk_assessments": risks_created,
                    "enforcement_cases": enforcement_created,
                },
                "relationships_created": relationships_created + temporal_created,
                "message": "Compliance graph initialization completed successfully",
            }
            logger.info("Compliance graph initialization completed: %s" % result)
            return result
        except Exception as e:
            logger.error("Failed to initialize compliance graph: %s" % str(e))
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def _clear_existing_data(self) -> None:
        """Clear existing compliance data (optional)"""
        query = """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN [
            'ComplianceDomain', 'Jurisdiction', 'Regulation', 'Requirement',
            'Control', 'Metric', 'RiskAssessment', 'EnforcementCase'
        ])
        DETACH DELETE n
        """
        await self.neo4j.execute_query(query, read_only=False)
        logger.info("Cleared existing compliance data")

    async def _create_schema_constraints(self) -> None:
        """Create Neo4j schema constraints and indexes"""
        constraints = [
            "CREATE CONSTRAINT compliance_domain_name IF NOT EXISTS FOR (d:ComplianceDomain) REQUIRE d.name IS UNIQUE",
            "CREATE CONSTRAINT jurisdiction_code IF NOT EXISTS FOR (j:Jurisdiction) REQUIRE j.code IS UNIQUE",
            "CREATE CONSTRAINT regulation_code IF NOT EXISTS FOR (r:Regulation) REQUIRE r.code IS UNIQUE",
            "CREATE CONSTRAINT requirement_id IF NOT EXISTS FOR (req:Requirement) REQUIRE req.id IS UNIQUE",
            "CREATE CONSTRAINT control_name IF NOT EXISTS FOR (c:Control) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT metric_name IF NOT EXISTS FOR (m:Metric) REQUIRE m.name IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX regulation_jurisdiction IF NOT EXISTS FOR (r:Regulation) ON (r.jurisdiction)",
            "CREATE INDEX requirement_risk IF NOT EXISTS FOR (req:Requirement) ON (req.risk_level)",
            "CREATE INDEX control_type IF NOT EXISTS FOR (c:Control) ON (c.control_type)",
            "CREATE INDEX metric_type IF NOT EXISTS FOR (m:Metric) ON (m.metric_type)",
        ]
        for constraint in constraints:
            try:
                await self.neo4j.execute_query(constraint, read_only=False)
            except Exception as e:
                logger.warning("Constraint creation warning: %s" % e)
        for index in indexes:
            try:
                await self.neo4j.execute_query(index, read_only=False)
            except Exception as e:
                logger.warning("Index creation warning: %s" % e)
        logger.info("Schema constraints and indexes created")

    async def _load_compliance_domains(self) -> int:
        """
        Load compliance domains from CCO playbook.

        Returns:
            int: Number of compliance domains created.
        """
        # The CCO playbook data is currently hardcoded in this method for demonstration purposes,
        # but in a production environment, this data could be loaded from an external file, database, or API.
        domains = [
            ComplianceDomain(
                name="Anti-Money Laundering",
                description="Prevention of money laundering and terrorist financing",
                risk_level="high",
                regulatory_scope=["6AMLD", "MLR2017", "FATF"],
                business_impact="critical",
                oversight_body="FCA",
            ),
            ComplianceDomain(
                name="Data Protection",
                description="Personal data protection and privacy compliance",
                risk_level="high",
                regulatory_scope=["GDPR", "DPA2018", "PECR"],
                business_impact="critical",
                oversight_body="ICO",
            ),
            ComplianceDomain(
                name="Operational Risk",
                description="Operational resilience and risk management",
                risk_level="high",
                regulatory_scope=["DORA", "PRA", "FCA"],
                business_impact="significant",
                oversight_body="PRA",
            ),
            ComplianceDomain(
                name="Consumer Protection",
                description="Fair treatment of customers and consumer rights",
                risk_level="medium",
                regulatory_scope=["FCA_PRIN", "CONC", "MCOB"],
                business_impact="significant",
                oversight_body="FCA",
            ),
            ComplianceDomain(
                name="Market Conduct",
                description="Market integrity and conduct of business",
                risk_level="medium",
                regulatory_scope=["MiFID2", "MAR", "COBS"],
                business_impact="moderate",
                oversight_body="FCA",
            ),
            ComplianceDomain(
                name="Financial Crime",
                description="Prevention of financial crimes including fraud",
                risk_level="high",
                regulatory_scope=["PCA2002", "FSMA", "SFO"],
                business_impact="critical",
                oversight_body="SFO",
            ),
        ]
        query = """
        UNWIND $domains AS domain
        CREATE (d:ComplianceDomain {
            name: domain.name,
            description: domain.description,
            risk_level: domain.risk_level,
            regulatory_scope: domain.regulatory_scope,
            business_impact: domain.business_impact,
            oversight_body: domain.oversight_body,
            created_at: datetime()
        })
        """
        domain_dicts = [asdict(domain) for domain in domains]
        await self.neo4j.execute_query(query, {"domains": domain_dicts}, read_only=False)
        logger.info("Created %s compliance domains" % len(domains))
        return len(domains)

    async def _load_jurisdictions(self) -> int:
        """Load legal jurisdictions"""
        jurisdictions = [
            Jurisdiction(
                name="United Kingdom",
                code="GB",
                regulatory_authority="FCA, PRA, ICO",
                enforcement_approach="principles-based",
                penalties_framework="proportionate",
                data_localization=False,
            ),
            Jurisdiction(
                name="European Union",
                code="EU",
                regulatory_authority="EBA, ESMA, EIOPA",
                enforcement_approach="rules-based",
                penalties_framework="standardized",
                data_localization=True,
            ),
            Jurisdiction(
                name="United States",
                code="US",
                regulatory_authority="FinCEN, CFTC, SEC",
                enforcement_approach="enforcement-led",
                penalties_framework="punitive",
                data_localization=False,
            ),
        ]
        query = """
        UNWIND $jurisdictions AS jurisdiction
        CREATE (j:Jurisdiction {
            name: jurisdiction.name,
            code: jurisdiction.code,
            regulatory_authority: jurisdiction.regulatory_authority,
            enforcement_approach: jurisdiction.enforcement_approach,
            penalties_framework: jurisdiction.penalties_framework,
            data_localization: jurisdiction.data_localization,
            created_at: datetime()
        })
        """
        jurisdiction_dicts = [asdict(jurisdiction) for jurisdiction in jurisdictions]
        await self.neo4j.execute_query(
            query, {"jurisdictions": jurisdiction_dicts}, read_only=False
        )
        logger.info("Created %s jurisdictions" % len(jurisdictions))
        return len(jurisdictions)

    async def _load_regulations(self) -> int:
        """Load regulatory frameworks from CCO playbook"""
        regulations = [
            Regulation(
                name="6th Anti-Money Laundering Directive",
                code="6AMLD",
                jurisdiction="EU",
                compliance_domain="Anti-Money Laundering",
                effective_date="2021-06-03",
                last_updated="2024-01-15",
                risk_rating="critical",
                penalty_framework="up to 4 years imprisonment",
                extraterritorial_reach=True,
            ),
            Regulation(
                name="General Data Protection Regulation",
                code="GDPR",
                jurisdiction="EU",
                compliance_domain="Data Protection",
                effective_date="2018-05-25",
                last_updated="2024-03-01",
                risk_rating="critical",
                penalty_framework="up to 4% of annual turnover",
                extraterritorial_reach=True,
            ),
            Regulation(
                name="Digital Operational Resilience Act",
                code="DORA",
                jurisdiction="EU",
                compliance_domain="Operational Risk",
                effective_date="2025-01-17",
                last_updated="2024-12-15",
                risk_rating="high",
                penalty_framework="up to 1% of annual turnover",
                extraterritorial_reach=False,
            ),
            Regulation(
                name="Bank Secrecy Act",
                code="BSA",
                jurisdiction="US",
                compliance_domain="Anti-Money Laundering",
                effective_date="1970-10-26",
                last_updated="2024-06-01",
                risk_rating="critical",
                penalty_framework="criminal and civil penalties",
                extraterritorial_reach=True,
            ),
            Regulation(
                name="Money Laundering Regulations 2017",
                code="MLR2017",
                jurisdiction="GB",
                compliance_domain="Anti-Money Laundering",
                effective_date="2017-06-26",
                last_updated="2024-02-20",
                risk_rating="critical",
                penalty_framework="unlimited fines and imprisonment",
                extraterritorial_reach=False,
            ),
            Regulation(
                name="Data Protection Act 2018",
                code="DPA2018",
                jurisdiction="GB",
                compliance_domain="Data Protection",
                effective_date="2018-05-25",
                last_updated="2024-01-10",
                risk_rating="high",
                penalty_framework="up to £17.5m or 4% of turnover",
                extraterritorial_reach=False,
            ),
        ]
        query = """
        UNWIND $regulations AS regulation
        CREATE (r:Regulation {
            name: regulation.name,
            code: regulation.code,
            jurisdiction: regulation.jurisdiction,
            compliance_domain: regulation.compliance_domain,
            effective_date: date(regulation.effective_date),
            last_updated: date(regulation.last_updated),
            risk_rating: regulation.risk_rating,
            penalty_framework: regulation.penalty_framework,
            extraterritorial_reach: regulation.extraterritorial_reach,
            created_at: datetime()
        })
        """
        regulation_dicts = [asdict(regulation) for regulation in regulations]
        await self.neo4j.execute_query(query, {"regulations": regulation_dicts}, read_only=False)
        logger.info("Created %s regulations" % len(regulations))
        return len(regulations)

    async def _load_requirements(self) -> int:
        """Load specific regulatory requirements"""
        requirements = [
            Requirement(
                regulation_code="6AMLD",
                section="Art. 3",
                title="Customer Due Diligence",
                description="Enhanced due diligence for high-risk customers and PEPs",
                mandatory=True,
                deadline_type="ongoing",
                risk_level="critical",
                business_function="onboarding",
            ),
            Requirement(
                regulation_code="6AMLD",
                section="Art. 7",
                title="Transaction Monitoring",
                description="Real-time monitoring of suspicious transactions",
                mandatory=True,
                deadline_type="ongoing",
                risk_level="high",
                business_function="operations",
            ),
            Requirement(
                regulation_code="GDPR",
                section="Art. 7",
                title="Consent Management",
                description="Valid consent for data processing with withdrawal rights",
                mandatory=True,
                deadline_type="ongoing",
                risk_level="high",
                business_function="data_processing",
            ),
            Requirement(
                regulation_code="GDPR",
                section="Art. 33",
                title="Breach Notification",
                description="72-hour breach notification to supervisory authority",
                mandatory=True,
                deadline_type="event-driven",
                risk_level="critical",
                business_function="incident_response",
            ),
            Requirement(
                regulation_code="DORA",
                section="Art. 11",
                title="ICT Risk Management",
                description="Comprehensive ICT risk management framework",
                mandatory=True,
                deadline_type="ongoing",
                risk_level="high",
                business_function="technology",
            ),
            Requirement(
                regulation_code="DORA",
                section="Art. 13",
                title="Incident Reporting",
                description="Major ICT incident reporting within 4 hours",
                mandatory=True,
                deadline_type="event-driven",
                risk_level="high",
                business_function="incident_response",
            ),
        ]
        query = """
        UNWIND $requirements AS req
        CREATE (r:Requirement {
            id: req.regulation_code + "_" + replace(req.section, " ", "_"),
            regulation_code: req.regulation_code,
            section: req.section,
            title: req.title,
            description: req.description,
            mandatory: req.mandatory,
            deadline_type: req.deadline_type,
            risk_level: req.risk_level,
            business_function: req.business_function,
            created_at: datetime()
        })
        """
        requirement_dicts = [asdict(requirement) for requirement in requirements]
        await self.neo4j.execute_query(query, {"requirements": requirement_dicts}, read_only=False)
        logger.info("Created %s requirements" % len(requirements))
        return len(requirements)

    async def _load_controls(self) -> int:
        """Load control measures for compliance"""
        controls = [
            Control(
                name="Enhanced Customer Due Diligence",
                control_type="preventive",
                requirements=["6AMLD_Art._3"],
                implementation_guidance="Risk-based approach with enhanced verification for high-risk customers",
                testing_frequency="quarterly",
                automation_level="semi-automated",
                cost_impact="medium",
            ),
            Control(
                name="Real-time Transaction Monitoring",
                control_type="detective",
                requirements=["6AMLD_Art._7"],
                implementation_guidance="AI-powered transaction monitoring with configurable rules",
                testing_frequency="continuous",
                automation_level="fully-automated",
                cost_impact="high",
            ),
            Control(
                name="Consent Management System",
                control_type="preventive",
                requirements=["GDPR_Art._7"],
                implementation_guidance="Granular consent with audit trail and withdrawal mechanisms",
                testing_frequency="monthly",
                automation_level="fully-automated",
                cost_impact="medium",
            ),
            Control(
                name="Data Breach Response Plan",
                control_type="corrective",
                requirements=["GDPR_Art._33"],
                implementation_guidance="Automated breach detection with escalation procedures",
                testing_frequency="semi-annually",
                automation_level="semi-automated",
                cost_impact="low",
            ),
            Control(
                name="ICT Risk Assessment Framework",
                control_type="preventive",
                requirements=["DORA_Art._11"],
                implementation_guidance="Comprehensive risk assessment covering all ICT assets",
                testing_frequency="annually",
                automation_level="manual",
                cost_impact="medium",
            ),
        ]
        query = """
        UNWIND $controls AS control
        CREATE (c:Control {
            name: control.name,
            control_type: control.control_type,
            requirements: control.requirements,
            implementation_guidance: control.implementation_guidance,
            testing_frequency: control.testing_frequency,
            automation_level: control.automation_level,
            cost_impact: control.cost_impact,
            created_at: datetime()
        })
        """
        control_dicts = [asdict(control) for control in controls]
        await self.neo4j.execute_query(query, {"controls": control_dicts}, read_only=False)
        logger.info("Created %s controls" % len(controls))
        return len(controls)

    async def _load_metrics(self) -> int:
        """Load compliance metrics and KPIs"""
        metrics = [
            ComplianceMetric(
                name="Customer Onboarding Risk Score",
                metric_type="effectiveness",
                calculation_method="Weighted risk factors aggregation",
                target_value="< 30% high-risk customers",
                reporting_frequency="monthly",
                data_source="CRM system",
                controls=["Enhanced Customer Due Diligence"],
            ),
            ComplianceMetric(
                name="Suspicious Transaction Detection Rate",
                metric_type="efficiency",
                calculation_method="Detected / Total transactions * 100",
                target_value="> 95% accuracy",
                reporting_frequency="daily",
                data_source="Transaction monitoring system",
                controls=["Real-time Transaction Monitoring"],
            ),
            ComplianceMetric(
                name="Consent Withdrawal Response Time",
                metric_type="efficiency",
                calculation_method="Average time from request to completion",
                target_value="< 24 hours",
                reporting_frequency="weekly",
                data_source="Consent management system",
                controls=["Consent Management System"],
            ),
            ComplianceMetric(
                name="Data Breach Notification Compliance",
                metric_type="coverage",
                calculation_method="Notified within 72h / Total breaches * 100",
                target_value="100% compliance",
                reporting_frequency="incident-based",
                data_source="Incident management system",
                controls=["Data Breach Response Plan"],
            ),
        ]
        query = """
        UNWIND $metrics AS metric
        CREATE (m:Metric {
            name: metric.name,
            metric_type: metric.metric_type,
            calculation_method: metric.calculation_method,
            target_value: metric.target_value,
            reporting_frequency: metric.reporting_frequency,
            data_source: metric.data_source,
            controls: metric.controls,
            created_at: datetime()
        })
        """
        metric_dicts = [asdict(metric) for metric in metrics]
        await self.neo4j.execute_query(query, {"metrics": metric_dicts}, read_only=False)
        logger.info("Created %s metrics" % len(metrics))
        return len(metrics)

    async def _create_relationships(self) -> int:
        """Create relationships between compliance entities"""
        total_relationships = 0
        relationship_queries = [
            """
            MATCH (d:ComplianceDomain), (r:Regulation)
            WHERE r.compliance_domain = d.name
            CREATE (r)-[:GOVERNED_BY]->(d)
            """,
            """
            MATCH (j:Jurisdiction), (r:Regulation)
            WHERE r.jurisdiction = j.code OR r.jurisdiction = j.name
            CREATE (r)-[:ENFORCED_IN]->(j)
            """,
            """
            MATCH (reg:Regulation), (req:Requirement)
            WHERE req.regulation_code = reg.code
            CREATE (req)-[:MANDATED_BY]->(reg)
            """,
            """
            MATCH (req:Requirement), (c:Control)
            WHERE req.id IN c.requirements
            CREATE (c)-[:ADDRESSES]->(req)
            """,
            """
            MATCH (c:Control), (m:Metric)
            WHERE c.name IN m.controls
            CREATE (m)-[:MEASURES]->(c)
            """,
            """
            MATCH (req1:Requirement), (req2:Requirement)
            WHERE req1.risk_level = req2.risk_level AND req1 <> req2
            CREATE (req1)-[:SIMILAR_RISK]->(req2)
            """,
            """
            MATCH (req1:Requirement), (req2:Requirement)
            WHERE req1.business_function = req2.business_function AND req1 <> req2
            CREATE (req1)-[:SAME_FUNCTION]->(req2)
            """,
        ]
        for query in relationship_queries:
            await self.neo4j.execute_query(query, read_only=False)
            total_relationships += 1
        logger.info("Created relationship patterns: %s" % len(relationship_queries))
        return len(relationship_queries)

    async def _load_risk_assessments(self) -> int:
        """Load risk assessment data"""
        query = """
        CREATE (ra1:RiskAssessment {
            id: "RA_6AMLD_2024",
            regulation_code: "6AMLD",
            assessment_date: date("2024-01-15"),
            risk_rating: "high",
            likelihood: "medium",
            impact: "critical",
            mitigation_status: "in_progress",
            residual_risk: "medium",
            next_review: date("2024-07-15"),
            assessor: "Chief Compliance Officer",
            created_at: datetime()
        }),
        (ra2:RiskAssessment {
            id: "RA_GDPR_2024",
            regulation_code: "GDPR",
            assessment_date: date("2024-03-01"),
            risk_rating: "high",
            likelihood: "high",
            impact: "critical",
            mitigation_status: "ongoing",
            residual_risk: "medium",
            next_review: date("2024-09-01"),
            assessor: "Data Protection Officer",
            created_at: datetime()
        }),
        (ra3:RiskAssessment {
            id: "RA_DORA_2024",
            regulation_code: "DORA",
            assessment_date: date("2024-12-01"),
            risk_rating: "medium",
            likelihood: "medium",
            impact: "high",
            mitigation_status: "planned",
            residual_risk: "high",
            next_review: date("2025-03-01"),
            assessor: "Chief Risk Officer",
            created_at: datetime()
        })
        """
        await self.neo4j.execute_query(query, read_only=False)
        logger.info("Created 3 risk assessments")
        return 3

    async def _load_enforcement_cases(self) -> int:
        """Load enforcement case data for learning"""
        query = """
        CREATE (ec1:EnforcementCase {
            id: "EC_GDPR_001",
            regulation_code: "GDPR",
            jurisdiction: "EU",
            violation_type: "insufficient_consent",
            penalty_amount: 50000000,
            penalty_currency: "EUR",
            case_date: date("2023-05-15"),
            organization_type: "fintech",
            violation_summary: "Inadequate consent mechanisms for data processing",
            lessons_learned: "Granular consent with clear withdrawal mechanisms required",
            preventive_measures: "Enhanced consent management system implementation",
            created_at: datetime()
        }),
        (ec2:EnforcementCase {
            id: "EC_6AMLD_001",
            regulation_code: "6AMLD",
            jurisdiction: "EU",
            violation_type: "inadequate_due_diligence",
            penalty_amount: 2000000,
            penalty_currency: "EUR",
            case_date: date("2023-09-22"),
            organization_type: "bank",
            violation_summary: "Failed to conduct enhanced due diligence on high-risk customers",
            lessons_learned: "Risk-based approach with documented procedures essential",
            preventive_measures: "Enhanced KYC procedures and staff training",
            created_at: datetime()
        }),
        (ec3:EnforcementCase {
            id: "EC_BSA_001",
            regulation_code: "BSA",
            jurisdiction: "US",
            violation_type: "inadequate_monitoring",
            penalty_amount: 15000000,
            penalty_currency: "USD",
            case_date: date("2023-11-08"),
            organization_type: "crypto_exchange",
            violation_summary: "Insufficient transaction monitoring and suspicious activity reporting",
            lessons_learned: "Automated monitoring systems with manual oversight required",
            preventive_measures: "AI-powered transaction monitoring implementation",
            created_at: datetime()
        })
        """
        await self.neo4j.execute_query(query, read_only=False)
        logger.info("Created 3 enforcement cases")
        return 3

    async def _create_temporal_relationships(self) -> int:
        """Create temporal relationships for regulatory changes"""
        queries = [
            """
            // Link risk assessments to regulations
            MATCH (ra:RiskAssessment), (r:Regulation)
            WHERE ra.regulation_code = r.code
            CREATE (ra)-[:ASSESSES]->(r)
            """,
            """
            // Link enforcement cases to regulations
            MATCH (ec:EnforcementCase), (r:Regulation)
            WHERE ec.regulation_code = r.code
            CREATE (ec)-[:VIOLATES]->(r)
            """,
            """
            // Create temporal sequence for enforcement cases
            MATCH (ec1:EnforcementCase), (ec2:EnforcementCase)
            WHERE ec1.case_date < ec2.case_date AND ec1.regulation_code = ec2.regulation_code
            CREATE (ec1)-[:PRECEDES]->(ec2)
            """,
            """
            // Link similar violations across jurisdictions
            MATCH (ec1:EnforcementCase), (ec2:EnforcementCase)
            WHERE ec1.violation_type = ec2.violation_type AND ec1 <> ec2
            CREATE (ec1)-[:SIMILAR_VIOLATION]->(ec2)
            """,
        ]

        for query in queries:
            await self.neo4j.execute_query(query, read_only=False)
        logger.info("Created temporal relationships")
        return len(queries)


async def initialize_compliance_graph() -> Dict[str, Any]:
    """Standalone function to initialize compliance graph"""
    neo4j_service = Neo4jGraphRAGService()
    initializer = ComplianceGraphInitializer(neo4j_service)
    try:
        await neo4j_service.initialize()
        result = await initializer.initialize_full_compliance_graph()
        return result
    finally:
        await neo4j_service.close()


if __name__ == "__main__":

    async def main() -> None:
        result = await initialize_compliance_graph()
        logger.info("Initialization result: %s" % result)

    asyncio.run(main())
