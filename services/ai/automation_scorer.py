#!/usr/bin/env python3
"""
Production-grade Automation Scorer for Compliance-as-Code Implementation
Analyzes regulations for automation potential and generates strategic recommendations
"""

import asyncio
import logging
import os
from typing import Dict, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from neo4j import AsyncGraphDatabase
from pydantic import BaseModel, Field
import numpy as np

logger = logging.getLogger(__name__)


class AutomationComplexity(str, Enum):
    """Automation implementation complexity levels"""

    TRIVIAL = "trivial"  # < 1 week
    SIMPLE = "simple"  # 1-2 weeks
    MODERATE = "moderate"  # 2-4 weeks
    COMPLEX = "complex"  # 1-2 months
    STRATEGIC = "strategic"  # 2-6 months


class AutomationCategory(str, Enum):
    """Categories of compliance automation"""

    MONITORING = "monitoring"  # Real-time compliance monitoring
    REPORTING = "reporting"  # Automated report generation
    VALIDATION = "validation"  # Data/process validation
    ENFORCEMENT = "enforcement"  # Policy enforcement
    DOCUMENTATION = "documentation"  # Evidence collection
    WORKFLOW = "workflow"  # Process automation
    INTEGRATION = "integration"  # System integration
    ANALYSIS = "analysis"  # Risk/impact analysis


@dataclass
class AutomationOpportunity:
    """Represents an automation opportunity for a regulation or control"""

    regulation_id: str
    title: str
    category: AutomationCategory
    complexity: AutomationComplexity
    automation_score: float  # 0-1 scale
    readiness_score: float  # 0-1 scale of org readiness
    effort_hours: int
    roi_months: float  # Months to ROI
    prerequisites: List[str] = field(default_factory=list)
    quick_wins: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    estimated_savings_annual: float = 0.0
    confidence_level: float = 0.8  # Confidence in estimates


@dataclass
class AutomationRoadmap:
    """Strategic roadmap for automation implementation"""

    total_opportunities: int
    quick_wins: List[AutomationOpportunity]
    strategic_initiatives: List[AutomationOpportunity]
    phases: List[Dict[str, Any]]
    total_investment_hours: int
    expected_roi_months: float
    automation_coverage: float  # Percentage of regulations automated
    risk_reduction: float  # Expected risk reduction percentage


class AutomationMetrics(BaseModel):
    """Metrics for automation scoring and analysis"""

    total_regulations: int = 0
    automatable_regulations: int = 0
    quick_win_count: int = 0
    strategic_count: int = 0
    average_automation_potential: float = 0.0
    estimated_annual_savings: float = 0.0
    implementation_hours: int = 0
    roi_timeline_months: float = 0.0
    technology_stack: List[str] = Field(default_factory=list)
    coverage_by_category: Dict[str, float] = Field(default_factory=dict)


class AutomationScorer:
    """
    Production-grade automation scorer for compliance regulations.
    Analyzes automation potential and generates implementation roadmaps.
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> None:
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None

        # Automation patterns and templates
        self.automation_patterns = self._load_automation_patterns()

        # Cost models (per hour in USD)
        self.cost_models = {
            "manual_compliance_hour": 150,  # Compliance officer hourly rate
            "developer_hour": 125,  # Developer hourly rate
            "automation_maintenance_hour": 25,  # Ongoing maintenance cost,
        }

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def connect(self):
        """Establish connection to Neo4j"""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password),
            )
            # Verify connectivity
            async with self.driver.session() as session:
                await session.run("RETURN 1")
            logger.info("✅ Connected to Neo4j for automation scoring")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()

    def _load_automation_patterns(self) -> Dict[str, Any]:
        """Load automation patterns and templates"""
        return {
            "monitoring": {
                "technologies": ["CloudWatch", "Datadog", "Prometheus", "Grafana"],
                "complexity_factors": {
                    "data_sources": 0.3,
                    "alert_rules": 0.2,
                    "dashboards": 0.1,
                    "integrations": 0.4,
                },
            },
            "reporting": {
                "technologies": ["Python", "Pandas", "Jupyter", "PowerBI", "Tableau"],
                "complexity_factors": {
                    "data_collection": 0.3,
                    "transformation": 0.3,
                    "visualization": 0.2,
                    "scheduling": 0.2,
                },
            },
            "validation": {
                "technologies": ["Pydantic", "JSON Schema", "OpenAPI", "Zod"],
                "complexity_factors": {
                    "rule_complexity": 0.4,
                    "data_variety": 0.3,
                    "error_handling": 0.3,
                },
            },
            "enforcement": {
                "technologies": ["OPA", "Sentinel", "AWS Config", "Azure Policy"],
                "complexity_factors": {
                    "policy_rules": 0.3,
                    "enforcement_points": 0.3,
                    "exceptions": 0.2,
                    "remediation": 0.2,
                },
            },
            "workflow": {
                "technologies": [
                    "Airflow",
                    "Temporal",
                    "Step Functions",
                    "GitHub Actions",
                ],
                "complexity_factors": {
                    "steps": 0.2,
                    "conditions": 0.3,
                    "approvals": 0.3,
                    "integrations": 0.2,
                },
            },
        }

    async def score_regulation_automation(self, regulation_id: str) -> AutomationOpportunity:
        """
        Score a single regulation for automation potential.

        Args:
            regulation_id: Regulation identifier

        Returns:
            AutomationOpportunity with detailed scoring
        """
        async with self.driver.session() as session:
            # Get regulation details with controls
            query = """
            MATCH (r:Regulation {id: $regulation_id})
            OPTIONAL MATCH (r)-[:SUGGESTS_CONTROL]->(c:Control)
            RETURN r, collect(c) as controls
            """

            result = await session.run(query, regulation_id=regulation_id)
            record = await result.single()

            if not record:
                raise ValueError(f"Regulation {regulation_id} not found")

            regulation = dict(record["r"])
            controls = [dict(c) for c in record["controls"] if c]

            # Analyze automation potential
            opportunity = self._analyze_automation_potential(regulation, controls)

            # Calculate readiness score based on prerequisites
            opportunity.readiness_score = await self._calculate_readiness_score(
                regulation_id,
                session,
            )

            # Estimate ROI
            opportunity.roi_months = self._estimate_roi_timeline(opportunity)

            return opportunity

    def _analyze_automation_potential(
        self, regulation: Dict[str, Any], controls: List[Dict[str, Any]]
    ) -> AutomationOpportunity:
        """Analyze regulation and controls for automation potential"""

        # Determine automation category
        category = self._determine_automation_category(regulation, controls)

        # Calculate complexity based on multiple factors
        complexity = self._calculate_complexity(regulation, controls)

        # Base automation score from regulation metadata
        base_score = regulation.get("automation_potential", 0.5)

        # Adjust based on control characteristics
        control_factor = self._analyze_control_automation(controls)

        # Final automation score
        automation_score = min(1.0, base_score * (1 + control_factor))

        # Estimate effort
        effort_hours = self._estimate_effort_hours(complexity, len(controls))

        # Identify quick wins
        quick_wins = self._identify_quick_wins(regulation, controls)

        # Identify blockers
        blockers = self._identify_blockers(regulation, controls)

        # Determine required technologies
        technologies = self.automation_patterns[category.value]["technologies"]

        # Estimate annual savings
        annual_savings = self._estimate_annual_savings(
            automation_score,
            regulation.get("enforcement_frequency", "medium"),
        )

        return AutomationOpportunity(
            regulation_id=regulation["id"],
            title=regulation["title"],
            category=category,
            complexity=complexity,
            automation_score=automation_score,
            readiness_score=0.0,  # Will be calculated separately
            effort_hours=effort_hours,
            roi_months=0.0,  # Will be calculated separately
            prerequisites=self._identify_prerequisites(regulation, controls),
            quick_wins=quick_wins,
            blockers=blockers,
            technologies=technologies,
            estimated_savings_annual=annual_savings,
        )

    def _determine_automation_category(
        self, regulation: Dict[str, Any], controls: List[Dict[str, Any]]
    ) -> AutomationCategory:
        """Determine the primary automation category"""

        # Analyze regulation tags and controls
        tags = regulation.get("tags", [])
        control_types = [c.get("type", "") for c in controls]

        # Priority-based categorization
        if "reporting" in tags or "report" in regulation["title"].lower():
            return AutomationCategory.REPORTING
        elif "monitoring" in control_types or "continuous" in str(controls):
            return AutomationCategory.MONITORING
        elif "validation" in control_types or "verify" in str(controls):
            return AutomationCategory.VALIDATION
        elif "policy" in tags or "enforcement" in control_types:
            return AutomationCategory.ENFORCEMENT
        elif "workflow" in control_types or "process" in str(controls):
            return AutomationCategory.WORKFLOW
        elif "documentation" in control_types:
            return AutomationCategory.DOCUMENTATION
        elif "integration" in str(controls):
            return AutomationCategory.INTEGRATION
        else:
            return AutomationCategory.ANALYSIS

    def _calculate_complexity(
        self, regulation: Dict[str, Any], controls: List[Dict[str, Any]]
    ) -> AutomationComplexity:
        """Calculate implementation complexity"""

        # Factor in multiple dimensions
        num_controls = len(controls)
        implementation_complexity = regulation.get("implementation_complexity", 5)
        has_dependencies = "dependencies" in regulation

        # Complexity scoring
        complexity_score = (
            num_controls * 0.3
            + implementation_complexity * 0.4
            + (5 if has_dependencies else 0) * 0.3,
        )

        if complexity_score <= 3:
            return AutomationComplexity.TRIVIAL
        elif complexity_score <= 5:
            return AutomationComplexity.SIMPLE
        elif complexity_score <= 7:
            return AutomationComplexity.MODERATE
        elif complexity_score <= 9:
            return AutomationComplexity.COMPLEX
        else:
            return AutomationComplexity.STRATEGIC

    def _analyze_control_automation(self, controls: List[Dict[str, Any]]) -> float:
        """Analyze controls for automation characteristics"""
        if not controls:
            return 0.0

        automation_factors = []
        for control in controls:
            factors = 0.0

            # Check for automatable characteristics
            if "api" in str(control).lower():
                factors += 0.3
            if "automated" in str(control).lower():
                factors += 0.3
            if "real-time" in str(control).lower():
                factors += 0.2
            if "manual" not in str(control).lower():
                factors += 0.2

            automation_factors.append(min(1.0, factors))

        return np.mean(automation_factors) if automation_factors else 0.0

    def _estimate_effort_hours(self, complexity: AutomationComplexity, num_controls: int) -> int:
        """Estimate implementation effort in hours"""

        base_hours = {
            AutomationComplexity.TRIVIAL: 40,
            AutomationComplexity.SIMPLE: 80,
            AutomationComplexity.MODERATE: 160,
            AutomationComplexity.COMPLEX: 320,
            AutomationComplexity.STRATEGIC: 960,
        }

        # Add hours per control
        control_hours = num_controls * 20

        return base_hours[complexity] + control_hours

    def _identify_quick_wins(
        self, regulation: Dict[str, Any], controls: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify quick win automation opportunities"""
        quick_wins = []

        # Check for easy automation targets
        if regulation.get("automation_potential", 0) > 0.7:
            quick_wins.append(
                "High automation potential - prioritize for implementation",
            )

        if any("reporting" in str(c).lower() for c in controls):
            quick_wins.append("Automated report generation using existing data")

        if any("monitoring" in str(c).lower() for c in controls):
            quick_wins.append("Real-time monitoring dashboard implementation")

        if len(controls) <= 3:
            quick_wins.append("Limited control set - faster implementation")

        return quick_wins

    def _identify_blockers(
        self, regulation: Dict[str, Any], controls: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify potential automation blockers"""
        blockers = []

        # Check for blocking factors
        if "manual-review" in regulation.get("tags", []):
            blockers.append("Requires human review - partial automation only")

        if regulation.get("implementation_complexity", 0) > 8:
            blockers.append("High complexity requires phased approach")

        if any("third-party" in str(c).lower() for c in controls):
            blockers.append("Third-party dependencies may limit automation")

        if "legal" in regulation.get("tags", []):
            blockers.append("Legal requirements may restrict full automation")

        return blockers

    def _identify_prerequisites(
        self, regulation: Dict[str, Any], controls: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify prerequisites for automation"""
        prerequisites = []

        # Data prerequisites
        if any("data" in str(c).lower() for c in controls):
            prerequisites.append("Data pipeline and quality assurance")

        # Integration prerequisites
        if any("integration" in str(c).lower() for c in controls):
            prerequisites.append("API access and authentication setup")

        # Infrastructure prerequisites
        if regulation.get("automation_potential", 0) > 0.5:
            prerequisites.append("Automation infrastructure (CI/CD, monitoring)")

        return prerequisites

    def _estimate_annual_savings(
        self, automation_score: float, enforcement_frequency: str
    ) -> float:
        """Estimate annual cost savings from automation"""

        # Frequency multipliers (times per year)
        frequency_map = {
            "very_high": 52,  # Weekly
            "high": 12,  # Monthly
            "medium": 4,  # Quarterly
            "low": 2,  # Semi-annual
            "very_low": 1,  # Annual,
        }

        frequency = frequency_map.get(enforcement_frequency, 4)

        # Hours saved per compliance cycle
        hours_per_cycle = 40 * automation_score  # Base 40 hours

        # Annual savings
        annual_hours_saved = hours_per_cycle * frequency
        annual_cost_savings = (annual_hours_saved * self.cost_models["manual_compliance_hour"],)

        # Subtract automation maintenance cost
        maintenance_hours = annual_hours_saved * 0.1  # 10% maintenance
        maintenance_cost = (maintenance_hours * self.cost_models["automation_maintenance_hour"],)

        return max(0, annual_cost_savings - maintenance_cost)

    async def _calculate_readiness_score(self, regulation_id: str, session: Any) -> float:
        """Calculate organizational readiness for automation"""

        # Check for existing automation infrastructure
        query = """
        MATCH (r:Regulation {id: $regulation_id})
        OPTIONAL MATCH (r)-[:COMPLEMENTS]->(dep:Regulation)
        WHERE dep.automation_potential > 0.5
        RETURN count(dep) as automated_dependencies
        """

        result = await session.run(query, regulation_id=regulation_id)
        record = await result.single()

        automated_deps = record["automated_dependencies"] if record else 0

        # Readiness factors
        readiness = 0.5  # Base readiness

        if automated_deps > 0:
            readiness += 0.2  # Has automated dependencies

        # Add more readiness factors as needed

        return min(1.0, readiness)

    def _estimate_roi_timeline(self, opportunity: AutomationOpportunity) -> float:
        """Estimate ROI timeline in months"""

        # Implementation cost
        implementation_cost = (opportunity.effort_hours * self.cost_models["developer_hour"],)

        # Monthly savings
        monthly_savings = opportunity.estimated_savings_annual / 12

        if monthly_savings > 0:
            return implementation_cost / monthly_savings
        else:
            return float("inf")  # No ROI if no savings

    async def generate_automation_roadmap(
        self, business_profile: Dict[str, Any], max_phases: int = 5
    ) -> AutomationRoadmap:
        """
        Generate comprehensive automation roadmap for a business profile.

        Args:
            business_profile: Business context and requirements
            max_phases: Maximum number of implementation phases

        Returns:
            Complete automation roadmap with phased approach
        """
        async with self.driver.session() as session:
            # Get applicable regulations
            regulations = await self._get_applicable_regulations(
                business_profile,
                session,
            )

            # Score each regulation for automation
            opportunities = []
            for reg in regulations:
                try:
                    opportunity = await self.score_regulation_automation(reg["id"])
                    opportunities.append(opportunity)
                except Exception as e:
                    logger.warning(f"Failed to score {reg['id']}: {e}")
                    continue

            # Separate quick wins and strategic initiatives
            quick_wins = [
                opp
                for opp in opportunities
                if opp.complexity in [AutomationComplexity.TRIVIAL, AutomationComplexity.SIMPLE]
                and opp.automation_score > 0.6
            ]

            strategic = [
                opp
                for opp in opportunities
                if opp.complexity in [AutomationComplexity.COMPLEX, AutomationComplexity.STRATEGIC]
                or opp.automation_score > 0.8
            ]

            # Sort by ROI
            quick_wins.sort(key=lambda x: x.roi_months)
            strategic.sort(key=lambda x: x.roi_months)

            # Generate implementation phases
            phases = self._generate_implementation_phases(
                quick_wins,
                strategic,
                max_phases,
            )

            # Calculate metrics
            total_hours = sum(opp.effort_hours for opp in opportunities)
            sum(opp.estimated_savings_annual for opp in opportunities)
            avg_roi = np.mean(
                [opp.roi_months for opp in opportunities if opp.roi_months < float("inf")],
            )

            automation_coverage = (len(opportunities) / len(regulations) if regulations else 0,)

            # Estimate risk reduction
            high_risk_automated = sum(1 for opp in opportunities if opp.automation_score > 0.7)
            risk_reduction = ((high_risk_automated / len(regulations)) * 0.5 if regulations else 0,)

            return AutomationRoadmap(
                total_opportunities=len(opportunities),
                quick_wins=quick_wins[:10],  # Top 10 quick wins
                strategic_initiatives=strategic[:5],  # Top 5 strategic
                phases=phases,
                total_investment_hours=total_hours,
                expected_roi_months=avg_roi,
                automation_coverage=automation_coverage,
                risk_reduction=risk_reduction,
            )

    async def _get_applicable_regulations(
        self, business_profile: Dict[str, Any], session: Any
    ) -> List[Dict[str, Any]]:
        """Get regulations applicable to business profile"""

        # Build WHERE clause - for now get all regulations since business_triggers not fully populated
        # In production, would filter by business_triggers matching the profile
        where_conditions = []
        params = {"profile": business_profile}

        # For now, get all regulations with automation potential
        where_conditions.append("r.automation_potential IS NOT NULL")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f"""
        MATCH (r:Regulation)
        WHERE {where_clause}
        RETURN r
        ORDER BY r.base_risk_score DESC
        LIMIT 50
        """

        result = await session.run(query, **params)
        regulations = []
        async for record in result:
            regulations.append(dict(record["r"]))

        return regulations

    def _generate_implementation_phases(
        self,
        quick_wins: List[AutomationOpportunity],
        strategic: List[AutomationOpportunity],
        max_phases: int,
    ) -> List[Dict[str, Any]]:
        """Generate phased implementation plan"""

        phases = []

        # Phase 1: Foundation and Quick Wins
        if quick_wins:
            phase1_items = quick_wins[:5]
            phases.append(
                {
                    "phase": 1,
                    "name": "Foundation & Quick Wins",
                    "duration": "1-2 months",
                    "items": [opp.regulation_id for opp in phase1_items],
                    "effort_hours": sum(opp.effort_hours for opp in phase1_items),
                    "expected_savings": sum(opp.estimated_savings_annual for opp in phase1_items),
                    "focus": "Establish automation infrastructure and deliver immediate value",
                },
            )

        # Phase 2: Expand Coverage
        if len(quick_wins) > 5:
            phase2_items = quick_wins[5:10]
            phases.append(
                {
                    "phase": 2,
                    "name": "Expand Coverage",
                    "duration": "2-3 months",
                    "items": [opp.regulation_id for opp in phase2_items],
                    "effort_hours": sum(opp.effort_hours for opp in phase2_items),
                    "expected_savings": sum(opp.estimated_savings_annual for opp in phase2_items),
                    "focus": "Broaden automation coverage across compliance areas",
                },
            )

        # Phase 3: Strategic Initiatives
        if strategic:
            phase3_items = strategic[:3]
            phases.append(
                {
                    "phase": 3,
                    "name": "Strategic Automation",
                    "duration": "3-6 months",
                    "items": [opp.regulation_id for opp in phase3_items],
                    "effort_hours": sum(opp.effort_hours for opp in phase3_items),
                    "expected_savings": sum(opp.estimated_savings_annual for opp in phase3_items),
                    "focus": "Implement complex automation for high-value regulations",
                },
            )

        # Phase 4: Integration & Optimization
        if len(strategic) > 3:
            phase4_items = strategic[3:5]
            phases.append(
                {
                    "phase": 4,
                    "name": "Integration & Optimization",
                    "duration": "2-4 months",
                    "items": [opp.regulation_id for opp in phase4_items],
                    "effort_hours": sum(opp.effort_hours for opp in phase4_items),
                    "expected_savings": sum(opp.estimated_savings_annual for opp in phase4_items),
                    "focus": "Integrate automation systems and optimize performance",
                },
            )

        # Phase 5: Continuous Improvement
        phases.append(
            {
                "phase": 5,
                "name": "Continuous Improvement",
                "duration": "Ongoing",
                "items": [],
                "effort_hours": 160,  # Maintenance estimate
                "expected_savings": 0,
                "focus": "Monitor, maintain, and enhance automation capabilities",
            },
        )

        return phases[:max_phases]

    async def analyze_automation_gaps(self, business_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze gaps in current automation coverage.

        Args:
            business_profile: Business context

        Returns:
            Gap analysis with recommendations
        """
        async with self.driver.session() as session:
            # Get automation coverage by category
            query = """
            MATCH (r:Regulation)
            WHERE r.business_triggers IS NOT NULL
            RETURN
                r.tags as tags,
                avg(r.automation_potential) as avg_automation,
                count(r) as count
            """

            result = await session.run(query)

            gaps = {
                "high_manual_risk": [],
                "low_automation_coverage": [],
                "missing_integrations": [],
                "recommendations": [],
            }

            async for record in result:
                tags = record["tags"]
                avg_automation = record["avg_automation"]
                count = record["count"]

                if avg_automation < 0.3 and count > 5:
                    gaps["low_automation_coverage"].append(
                        {
                            "area": str(tags),
                            "current_automation": avg_automation,
                            "regulation_count": count,
                            "improvement_potential": (0.7 - avg_automation) * count * 1000,
                        },
                    )

            # Generate recommendations
            if gaps["low_automation_coverage"]:
                gaps["recommendations"].append(
                    "Focus on automating low-coverage areas for maximum impact",
                )

            gaps["recommendations"].append(
                "Implement monitoring automation for real-time compliance",
            )
            gaps["recommendations"].append(
                "Create automated reporting pipelines for regular audits",
            )

            return gaps

    async def estimate_automation_investment(
        self, opportunities: List[AutomationOpportunity]
    ) -> Dict[str, Any]:
        """
        Estimate total investment required for automation.

        Args:
            opportunities: List of automation opportunities

        Returns:
            Investment analysis with costs and timeline
        """

        # Calculate totals
        total_dev_hours = sum(opp.effort_hours for opp in opportunities)
        total_dev_cost = total_dev_hours * self.cost_models["developer_hour"]

        # Infrastructure costs (estimated)
        infrastructure_cost = len(opportunities) * 1000  # Per regulation

        # Training costs
        training_hours = len(set(opp.category for opp in opportunities)) * 40
        training_cost = training_hours * self.cost_models["manual_compliance_hour"]

        # Total investment
        total_investment = total_dev_cost + infrastructure_cost + training_cost

        # Annual savings
        total_annual_savings = sum(opp.estimated_savings_annual for opp in opportunities)

        # ROI calculation
        roi_months = (
            total_investment / (total_annual_savings / 12)
            if total_annual_savings > 0
            else float("inf"),
        )

        # Break-even analysis
        break_even_date = datetime.now() + timedelta(days=roi_months * 30)

        return {
            "development_cost": total_dev_cost,
            "infrastructure_cost": infrastructure_cost,
            "training_cost": training_cost,
            "total_investment": total_investment,
            "annual_savings": total_annual_savings,
            "roi_months": roi_months,
            "break_even_date": (
                break_even_date.isoformat() if roi_months < float("inf") else None,
            ),
            "net_present_value_3y": (total_annual_savings * 3) - total_investment,
            "implementation_months": total_dev_hours / 160,  # Assuming 160 hours/month
            "resources_required": {
                "developers": max(1, total_dev_hours // 960),  # 960 hours = 6 months
                "compliance_officers": 2,
                "project_manager": 1,
            },
        }


async def main():
    """Test the automation scorer"""

    # Neo4j connection details
    neo4j_uri = "bolt://localhost:7688"
    # Security: Credentials now loaded from environment via Doppler
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not neo4j_password:
        raise ValueError("NEO4J_PASSWORD environment variable not set. Configure via Doppler.")

    async with AutomationScorer(neo4j_uri, neo4j_user, neo4j_password) as scorer:
        # Test business profile
        business_profile = {
            "industry": "finance",
            "sub_industry": "fintech",
            "country": "UK",
            "processes_payments": True,
            "stores_customer_data": True,
            "has_eu_customers": True,
            "annual_revenue": 25000000,
            "employee_count": 100,
        }

        logger.info("🤖 Generating Automation Roadmap...")

        # Generate automation roadmap
        roadmap = await scorer.generate_automation_roadmap(business_profile)

        logger.info("\n📊 Automation Analysis Complete:")
        logger.info(f"  Total Opportunities: {roadmap.total_opportunities}")
        logger.info(f"  Quick Wins: {len(roadmap.quick_wins)}")
        logger.info(f"  Strategic Initiatives: {len(roadmap.strategic_initiatives)}")
        logger.info(f"  Investment Hours: {roadmap.total_investment_hours:,}")
        logger.info(f"  Expected ROI: {roadmap.expected_roi_months:.1f} months")
        logger.info(f"  Automation Coverage: {roadmap.automation_coverage:.1%}")
        logger.info(f"  Risk Reduction: {roadmap.risk_reduction:.1%}")

        if roadmap.quick_wins:
            logger.info("\n🎯 Top Quick Wins:")
            for opp in roadmap.quick_wins[:5]:
                logger.info(f"  • {opp.title}")
                logger.info(
                    f"    Score: {opp.automation_score:.2f}, Hours: {opp.effort_hours}, ROI: {opp.roi_months:.1f} months"  # noqa: E501,
                )

        if roadmap.phases:
            logger.info("\n📅 Implementation Phases:")
            for phase in roadmap.phases:
                logger.info(
                    f"  Phase {phase['phase']}: {phase['name']} ({phase['duration']})",
                )
                logger.info(
                    f"    Items: {len(phase['items'])}, Hours: {phase['effort_hours']}, Savings: ${phase['expected_savings']:,.0f}"  # noqa: E501,
                )

        # Analyze gaps
        gaps = await scorer.analyze_automation_gaps(business_profile)

        if gaps["recommendations"]:
            logger.info("\n💡 Recommendations:")
            for rec in gaps["recommendations"]:
                logger.info(f"  • {rec}")

        # Estimate investment
        if roadmap.quick_wins or roadmap.strategic_initiatives:
            all_opportunities = roadmap.quick_wins + roadmap.strategic_initiatives
            investment = await scorer.estimate_automation_investment(all_opportunities)

            logger.info("\n💰 Investment Analysis:")
            logger.info(f"  Total Investment: ${investment['total_investment']:,.0f}")
            logger.info(f"  Annual Savings: ${investment['annual_savings']:,.0f}")
            logger.info(
                f"  Break-even: {investment['break_even_date'][:10] if investment['break_even_date'] else 'N/A'}",
            )
            logger.info(f"  3-Year NPV: ${investment['net_present_value_3y']:,.0f}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
