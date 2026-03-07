"""

# Constants
CONFIDENCE_THRESHOLD = 0.8
DEFAULT_RETRIES = 5
MAX_RETRIES = 3

IQ Agent Neo4j Integration Module.
Connects enhanced compliance data in Neo4j with IQ agent's decision-making.
"""

import logging
from typing import Dict, Any, List
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)


class IQNeo4jIntegration:
    """
    Integration layer between IQ agent and enhanced Neo4j compliance graph.
    Provides intelligent query capabilities for compliance decision-making.
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> None:
        """Initialize integration with Neo4j connection."""
        self.driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.logger = logging.getLogger(self.__class__.__name__)

    async def close(self) -> None:
        """Close Neo4j connection."""
        await self.driver.close()

    async def assess_compliance_risk(self, business_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess compliance risk for a business profile using enhanced metadata.

        Args:
            business_profile: Business attributes including industry, country, etc.

        Returns:
            Risk assessment with applicable regulations and scores
        """
        query = """
        // Find applicable regulations based on business triggers
        MATCH (r:Regulation)
        WHERE
            // Industry match
            (r.business_triggers IS NOT NULL AND
             (r.business_triggers CONTAINS $industry OR
              r.business_triggers CONTAINS 'any'))
            OR
            // Direct trigger match
            EXISTS((r)-[:APPLIES_TO]->(:BusinessTrigger {industry: $industry}))
            OR
            EXISTS((r)-[:APPLIES_TO]->(:BusinessTrigger {country: $country}))

        // Get enforcement history
        OPTIONAL MATCH (r)-[:HAS_ENFORCEMENT]->(e:Enforcement)

        // Get suggested controls
        OPTIONAL MATCH (r)-[:SUGGESTS_CONTROL]->(c:Control)

        // Get related regulations
        OPTIONAL MATCH (r)-[:DEPENDS_ON|EQUIVALENT_TO|SUPERSEDES]->(related:Regulation)

        RETURN
            r.id as regulation_id,
            r.title as title,
            r.base_risk_score as base_risk,
            r.enforcement_frequency as enforcement_freq,
            r.max_penalty as max_penalty,
            r.automation_potential as automation_potential,
            r.implementation_complexity as complexity,
            r.typical_timeline as timeline,
            r.evidence_templates as evidence_templates,
            count(DISTINCT e) as enforcement_count,
            sum(e.penalty_amount) as total_penalties,
            collect(DISTINCT c.name) as suggested_controls,
            collect(DISTINCT related.id) as related_regulations
        ORDER BY base_risk DESC
        """
        applicable_regulations = []
        total_risk_score = 0
        high_risk_count = 0
        critical_regulations = []
        async with self.driver.session() as session:
            result = await session.run(
                query,
                {
                    "industry": business_profile.get("industry", "general"),
                    "country": business_profile.get("country", "Global"),
                    "revenue": business_profile.get("annual_revenue", 0),
                    "employees": business_profile.get("employee_count", 0),
                },
            )
            async for record in result:
                base_risk = record["base_risk"] or 5
                enforcement_adjustment = min(record["enforcement_count"] * 0.5, 3)
                adjusted_risk = min(base_risk + enforcement_adjustment, 10)
                regulation = {
                    "id": record["regulation_id"],
                    "title": record["title"],
                    "base_risk_score": base_risk,
                    "adjusted_risk_score": adjusted_risk,
                    "enforcement_frequency": record["enforcement_freq"],
                    "max_penalty": record["max_penalty"],
                    "automation_potential": record["automation_potential"] or 0.5,
                    "complexity": record["complexity"] or 5,
                    "timeline": record["timeline"],
                    "enforcement_count": record["enforcement_count"],
                    "total_penalties": record["total_penalties"] or 0,
                    "suggested_controls": record["suggested_controls"],
                    "related_regulations": record["related_regulations"],
                    "evidence_templates": record["evidence_templates"],
                }
                applicable_regulations.append(regulation)
                total_risk_score += adjusted_risk
                if adjusted_risk >= 8:
                    high_risk_count += 1
                if adjusted_risk >= 9:
                    critical_regulations.append(
                        {
                            "title": record["title"],
                            "risk": adjusted_risk,
                            "max_penalty": record["max_penalty"],
                        }
                    )
        avg_risk = total_risk_score / len(applicable_regulations) if applicable_regulations else 0
        risk_level = self._categorize_risk_level(avg_risk, high_risk_count)
        return {
            "applicable_regulations": applicable_regulations,
            "total_regulations": len(applicable_regulations),
            "average_risk_score": round(avg_risk, 2),
            "high_risk_count": high_risk_count,
            "critical_regulations": critical_regulations,
            "risk_level": risk_level,
            "automation_potential": self._calculate_automation_potential(applicable_regulations),
            "estimated_implementation_months": self._estimate_timeline(applicable_regulations),
            "top_controls": self._identify_top_controls(applicable_regulations),
        }

    async def get_compliance_roadmap(
        self, business_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate prioritized compliance roadmap based on risk and dependencies.

        Args:
            business_profile: Business attributes

        Returns:
            Prioritized list of compliance actions
        """
        assessment = await self.assess_compliance_risk(business_profile)
        regulations = assessment["applicable_regulations"]
        roadmap = []
        processed = set()
        for reg in sorted(regulations, key=lambda x: x["adjusted_risk_score"], reverse=True):
            if reg["id"] in processed:
                continue
            deps = await self._get_regulation_dependencies(reg["id"])
            for dep in deps:
                if dep["id"] not in processed:
                    roadmap.append(
                        {
                            "phase": "Foundation",
                            "regulation_id": dep["id"],
                            "title": dep["title"],
                            "reason": f"Dependency for {reg['title']}",
                            "risk_score": dep["risk_score"],
                            "timeline": dep["timeline"],
                            "controls": dep["controls"],
                        }
                    )
                    processed.add(dep["id"])
            phase = self._determine_phase(reg["adjusted_risk_score"])
            roadmap.append(
                {
                    "phase": phase,
                    "regulation_id": reg["id"],
                    "title": reg["title"],
                    "reason": self._get_prioritization_reason(reg),
                    "risk_score": reg["adjusted_risk_score"],
                    "timeline": reg["timeline"],
                    "controls": reg["suggested_controls"][:5],
                }
            )
            processed.add(reg["id"])
        return roadmap

    async def find_control_overlaps(self, regulation_ids: List[str]) -> Dict[str, Any]:
        """
        Find overlapping controls between regulations for efficiency.

        Args:
            regulation_ids: List of regulation IDs to analyze

        Returns:
            Control overlap analysis
        """
        query = """
        UNWIND $reg_ids as reg_id
        MATCH (r:Regulation {id: reg_id})-[:SUGGESTS_CONTROL]->(c:Control)
        WITH c, collect(DISTINCT r.id) as regulations, count(DISTINCT r) as reg_count
        WHERE reg_count > 1
        RETURN
            c.name as control_name,
            c.id as control_id,
            regulations,
            reg_count,
            // Calculate efficiency score
            toFloat(reg_count) / toFloat(size($reg_ids)) as coverage_ratio
        ORDER BY reg_count DESC, coverage_ratio DESC
        """
        async with self.driver.session() as session:
            result = await session.run(query, {"reg_ids": regulation_ids})
            overlaps = []
            async for record in result:
                overlaps.append(
                    {
                        "control": record["control_name"],
                        "control_id": record["control_id"],
                        "covers_regulations": record["regulations"],
                        "regulation_count": record["reg_count"],
                        "coverage_ratio": round(record["coverage_ratio"], 2),
                    }
                )
        total_controls = await self._count_total_controls(regulation_ids)
        overlapping_controls = len(overlaps)
        efficiency_gain = (
            (1 - overlapping_controls / total_controls) * 100 if total_controls > 0 else 0
        )
        return {
            "overlapping_controls": overlaps,
            "total_unique_controls": total_controls,
            "overlapping_control_count": overlapping_controls,
            "efficiency_gain_percentage": round(efficiency_gain, 1),
            "recommended_implementation_order": self._optimize_control_order(overlaps),
        }

    async def analyze_enforcement_patterns(
        self, industry: str, timeframe_days: int = 365
    ) -> Dict[str, Any]:
        """
        Analyze enforcement patterns for an industry.

        Args:
            industry: Industry sector
            timeframe_days: Days to look back

        Returns:
            Enforcement pattern analysis
        """
        query = """
        MATCH (r:Regulation)-[:HAS_ENFORCEMENT]->(e:Enforcement)
        WHERE r.business_triggers CONTAINS $industry
            OR EXISTS((r)-[:APPLIES_TO]->(:BusinessTrigger {industry: $industry}))
        WITH r, e
        ORDER BY e.date DESC
        RETURN
            r.id as regulation_id,
            r.title as regulation_title,
            collect({
                date: e.date,
                firm: e.firm,
                penalty: e.penalty_amount,
                violation: e.violation_type
            }) as enforcements,
            count(e) as enforcement_count,
            sum(e.penalty_amount) as total_penalties,
            avg(e.penalty_amount) as avg_penalty
        ORDER BY total_penalties DESC
        LIMIT 20
        """
        patterns = []
        total_industry_penalties = 0
        async with self.driver.session() as session:
            result = await session.run(query, {"industry": industry})
            async for record in result:
                patterns.append(
                    {
                        "regulation": record["regulation_title"],
                        "regulation_id": record["regulation_id"],
                        "enforcement_count": record["enforcement_count"],
                        "total_penalties": record["total_penalties"] or 0,
                        "average_penalty": record["avg_penalty"] or 0,
                        "recent_cases": record["enforcements"][:5],
                    }
                )
                total_industry_penalties += record["total_penalties"] or 0
        trending = self._identify_trending_violations(patterns)
        return {
            "enforcement_patterns": patterns,
            "total_industry_penalties": total_industry_penalties,
            "trending_violations": trending,
            "high_risk_areas": patterns[:5] if patterns else [],
            "recommendations": self._generate_enforcement_recommendations(patterns),
        }

    async def get_automation_opportunities(self, regulation_ids: List[str]) -> Dict[str, Any]:
        """
        Identify automation opportunities across regulations.

        Args:
            regulation_ids: List of regulation IDs

        Returns:
            Automation opportunity analysis
        """
        query = """
        UNWIND $reg_ids as reg_id
        MATCH (r:Regulation {id: reg_id})
        OPTIONAL MATCH (r)-[:SUGGESTS_CONTROL]->(c:Control)
        RETURN
            r.id as regulation_id,
            r.title as title,
            r.automation_potential as automation_score,
            r.implementation_complexity as complexity,
            collect(DISTINCT c.name) as controls
        ORDER BY automation_score DESC
        """
        opportunities = []
        high_automation = []
        total_automation_score = 0
        async with self.driver.session() as session:
            result = await session.run(query, {"reg_ids": regulation_ids})
            async for record in result:
                automation_score = record["automation_score"] or 0.5
                total_automation_score += automation_score
                opportunity = {
                    "regulation_id": record["regulation_id"],
                    "title": record["title"],
                    "automation_score": automation_score,
                    "complexity": record["complexity"] or 5,
                    "automatable_controls": self._identify_automatable_controls(record["controls"]),
                    "automation_category": self._categorize_automation(automation_score),
                }
                opportunities.append(opportunity)
                if automation_score >= 0.7:
                    high_automation.append(opportunity)
        avg_automation = total_automation_score / len(opportunities) if opportunities else 0
        return {
            "automation_opportunities": opportunities,
            "high_automation_candidates": high_automation,
            "average_automation_potential": round(avg_automation, 2),
            "estimated_efficiency_gain": self._estimate_efficiency_gain(opportunities),
            "implementation_roadmap": self._create_automation_roadmap(opportunities),
        }

    def _categorize_risk_level(self, avg_risk: float, high_risk_count: int) -> str:
        """Categorize overall risk level."""
        if avg_risk >= 8 or high_risk_count >= DEFAULT_RETRIES:
            return "CRITICAL"
        elif avg_risk >= 6 or high_risk_count >= MAX_RETRIES:
            return "HIGH"
        elif avg_risk >= 4:
            return "MEDIUM"
        else:
            return "LOW"

    def _calculate_automation_potential(self, regulations: List[Dict]) -> float:
        """Calculate average automation potential."""
        if not regulations:
            return 0
        scores = [r["automation_potential"] for r in regulations if r["automation_potential"]]
        return round(sum(scores) / len(scores), 2) if scores else 0.5

    def _estimate_timeline(self, regulations: List[Dict]) -> int:
        """Estimate total implementation timeline in months."""
        total_months = 0
        for reg in regulations:
            timeline = reg.get("timeline", "Unknown")
            if "month" in str(timeline).lower():
                parts = timeline.split("-")
                if len(parts) == 2:
                    total_months += int(parts[1].split()[0])
                elif parts[0].isdigit():
                    total_months += int(parts[0])
            else:
                total_months += 6
        return min(total_months, 36)

    def _identify_top_controls(self, regulations: List[Dict]) -> List[str]:
        """Identify most frequently suggested controls."""
        control_counts = {}
        for reg in regulations:
            for control in reg.get("suggested_controls", []):
                control_counts[control] = control_counts.get(control, 0) + 1
        sorted_controls = sorted(control_counts.items(), key=lambda x: x[1], reverse=True)
        return [control for control, _ in sorted_controls[:10]]

    async def _get_regulation_dependencies(self, regulation_id: str) -> List[Dict]:
        """Get dependencies for a regulation."""
        query = """
        MATCH (r:Regulation {id: $reg_id})-[:DEPENDS_ON]->(dep:Regulation)
        OPTIONAL MATCH (dep)-[:SUGGESTS_CONTROL]->(c:Control)
        RETURN
            dep.id as id,
            dep.title as title,
            dep.base_risk_score as risk_score,
            dep.typical_timeline as timeline,
            collect(DISTINCT c.name) as controls
        """
        deps = []
        async with self.driver.session() as session:
            result = await session.run(query, {"reg_id": regulation_id})
            async for record in result:
                deps.append(
                    {
                        "id": record["id"],
                        "title": record["title"],
                        "risk_score": record["risk_score"] or 5,
                        "timeline": record["timeline"],
                        "controls": record["controls"],
                    }
                )
        return deps

    def _determine_phase(self, risk_score: float) -> str:
        """Determine implementation phase based on risk."""
        if risk_score >= 9:
            return "Immediate"
        elif risk_score >= 7:
            return "Phase 1"
        elif risk_score >= DEFAULT_RETRIES:
            return "Phase 2"
        else:
            return "Phase 3"

    def _get_prioritization_reason(self, regulation: Dict) -> str:
        """Generate prioritization reason."""
        if regulation["adjusted_risk_score"] >= 9:
            return f"Critical risk (score: {regulation['adjusted_risk_score']}) with {regulation['enforcement_count']} enforcement cases"
        elif regulation["enforcement_count"] > DEFAULT_RETRIES:
            return f"High enforcement activity ({regulation['enforcement_count']} cases, ${regulation['total_penalties']:,.0f} in penalties)"
        elif regulation["adjusted_risk_score"] >= 7:
            return f"High risk regulation (score: {regulation['adjusted_risk_score']})"
        else:
            return "Standard compliance requirement"

    async def _count_total_controls(self, regulation_ids: List[str]) -> int:
        """Count total unique controls across regulations."""
        query = """
        UNWIND $reg_ids as reg_id
        MATCH (r:Regulation {id: reg_id})-[:SUGGESTS_CONTROL]->(c:Control)
        RETURN count(DISTINCT c) as total
        """
        async with self.driver.session() as session:
            result = await session.run(query, {"reg_ids": regulation_ids})
            record = await result.single()
            return record["total"] if record else 0

    def _optimize_control_order(self, overlaps: List[Dict]) -> List[Dict]:
        """Optimize control implementation order for maximum coverage."""
        return sorted(
            overlaps, key=lambda x: (x["coverage_ratio"], x["regulation_count"]), reverse=True
        )[:10]

    def _identify_trending_violations(self, patterns: List[Dict]) -> List[str]:
        """Identify trending violation types."""
        violation_counts = {}
        for pattern in patterns:
            for case in pattern.get("recent_cases", []):
                violation = case.get("violation")
                if violation:
                    violation_counts[violation] = violation_counts.get(violation, 0) + 1
        sorted_violations = sorted(violation_counts.items(), key=lambda x: x[1], reverse=True)
        return [v[0] for v in sorted_violations[:5]]

    def _generate_enforcement_recommendations(self, patterns: List[Dict]) -> List[str]:
        """Generate recommendations based on enforcement patterns."""
        recommendations = []
        if patterns:
            top_risk = patterns[0]
            recommendations.append(
                f"Priority focus on {top_risk['regulation']} - highest penalty exposure"
            )
        high_frequency = [p for p in patterns if p["enforcement_count"] >= DEFAULT_RETRIES]
        if high_frequency:
            recommendations.append(
                f"Implement automated monitoring for {len(high_frequency)} high-frequency violation areas"
            )
        return recommendations

    def _identify_automatable_controls(self, controls: List[str]) -> List[str]:
        """Identify which controls can be automated."""
        automatable_keywords = [
            "monitoring",
            "logging",
            "scanning",
            "detection",
            "reporting",
            "validation",
            "encryption",
            "backup",
            "audit",
        ]
        automatable = []
        for control in controls:
            if any(keyword in control.lower() for keyword in automatable_keywords):
                automatable.append(control)
        return automatable

    def _categorize_automation(self, score: float) -> str:
        """Categorize automation potential."""
        if score >= CONFIDENCE_THRESHOLD:
            return "Fully Automatable"
        elif score >= 0.6:
            return "Mostly Automatable"
        elif score >= 0.4:
            return "Partially Automatable"
        else:
            return "Manual Process"

    def _estimate_efficiency_gain(self, opportunities: List[Dict]) -> Dict[str, Any]:
        """Estimate efficiency gain from automation."""
        high_auto = len([o for o in opportunities if o["automation_score"] >= 0.7])
        medium_auto = len([o for o in opportunities if 0.4 <= o["automation_score"] < 0.7])
        time_saved_hours = high_auto * 40 + medium_auto * 20
        cost_saved = time_saved_hours * 150
        return {
            "estimated_hours_saved_annually": time_saved_hours,
            "estimated_cost_savings": f"${cost_saved:,.0f}",
            "efficiency_improvement": f"{min(high_auto * 15, 75)}%",
        }

    def _create_automation_roadmap(self, opportunities: List[Dict]) -> List[Dict]:
        """Create automation implementation roadmap."""
        roadmap = []
        phase1 = [
            o
            for o in opportunities
            if o["automation_score"] >= 0.7 and o["complexity"] <= DEFAULT_RETRIES
        ]
        if phase1:
            roadmap.append(
                {
                    "phase": "Quick Wins",
                    "timeline": "1-3 months",
                    "items": phase1[:5],
                    "expected_impact": "High",
                }
            )
        phase2 = [
            o
            for o in opportunities
            if o["automation_score"] >= 0.7 and o["complexity"] > DEFAULT_RETRIES
        ]
        if phase2:
            roadmap.append(
                {
                    "phase": "Strategic Automation",
                    "timeline": "3-6 months",
                    "items": phase2[:5],
                    "expected_impact": "High",
                }
            )
        phase3 = [o for o in opportunities if 0.4 <= o["automation_score"] < 0.7]
        if phase3:
            roadmap.append(
                {
                    "phase": "Incremental Improvements",
                    "timeline": "6-12 months",
                    "items": phase3[:5],
                    "expected_impact": "Medium",
                }
            )
        return roadmap
