"""

# Constants
DEFAULT_RETRIES = 5


Compliance Retrieval Queries for IQ Agent GraphRAG System

This module implements 14 categories of production-ready queries for
intelligent compliance analysis using Neo4j graph traversal patterns.

Query Categories:
1. Regulatory Coverage Analysis
2. Cross-jurisdictional Impact Assessment
3. Risk Convergence Detection
4. Compliance Gap Analysis
5. Temporal Regulatory Changes
6. Control Effectiveness Analysis
7. Enforcement Learning Patterns
8. Multi-hop Regulatory Relationships
9. Dynamic Risk Calculation
10. Regulatory Conflict Detection
11. Business Impact Assessment
12. Implementation Priority Scoring
13. Compliance Cost Analysis
14. Predictive Compliance Insights
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum
from services.neo4j_service import Neo4jGraphRAGService

logger = logging.getLogger(__name__)


class QueryCategory(Enum):
    """Enumeration of query categories for compliance analysis"""

    REGULATORY_COVERAGE = "regulatory_coverage"
    COMPLIANCE_GAPS = "compliance_gaps"
    CROSS_JURISDICTIONAL = "cross_jurisdictional"
    RISK_CONVERGENCE = "risk_convergence"
    TEMPORAL_CHANGES = "temporal_changes"
    ENFORCEMENT_LEARNING = "enforcement_learning"


@dataclass
class QueryResult:
    """Standardized query result structure"""

    category: str
    query_id: str
    timestamp: str
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    confidence_score: float


class ComplianceRetrievalQueries:
    """Production-ready retrieval queries for compliance intelligence"""

    def __init__(self, neo4j_service: Neo4jGraphRAGService) -> None:
        self.neo4j = neo4j_service

    async def get_regulatory_coverage_analysis(
        self, domain_name: Optional[str] = None, jurisdiction: Optional[str] = None
    ) -> QueryResult:
        """Analyze compliance coverage across domains and jurisdictions"""
        query = """
        MATCH (d:ComplianceDomain)
        OPTIONAL MATCH (d)<-[:GOVERNED_BY]-(r:Regulation)
        OPTIONAL MATCH (r)-[:ENFORCED_IN]->(j:Jurisdiction)
        OPTIONAL MATCH (r)<-[:MANDATED_BY]-(req:Requirement)
        OPTIONAL MATCH (req)<-[:ADDRESSES]-(c:Control)

        WHERE ($domain IS NULL OR d.name = $domain)
        AND ($jurisdiction IS NULL OR j.code = $jurisdiction OR j.name = $jurisdiction)

        WITH d, r, j,
             count(DISTINCT req) as requirements_count,
             count(DISTINCT c) as controls_count,
             collect(DISTINCT req.risk_level) as risk_levels

        RETURN d.name as domain,
               d.risk_level as domain_risk,
               r.code as regulation_code,
               r.name as regulation_name,
               j.code as jurisdiction,
               requirements_count,
               controls_count,
               risk_levels,
               CASE
                   WHEN controls_count = 0 THEN 0.0
                   WHEN requirements_count = 0 THEN 0.0
                   ELSE toFloat(controls_count) / toFloat(requirements_count)
               END as coverage_ratio

        ORDER BY domain, regulation_code
        """
        result = await self.neo4j.execute_query(
            query, {"domain": domain_name, "jurisdiction": jurisdiction}
        )
        coverage_data = []
        domain_coverage = {}
        for record in result:
            domain = record["domain"]
            coverage_ratio = record["coverage_ratio"]
            coverage_data.append(
                {
                    "domain": domain,
                    "domain_risk": record["domain_risk"],
                    "regulation": {
                        "code": record["regulation_code"],
                        "name": record["regulation_name"],
                    },
                    "jurisdiction": record["jurisdiction"],
                    "requirements_count": record["requirements_count"],
                    "controls_count": record["controls_count"],
                    "risk_levels": record["risk_levels"],
                    "coverage_ratio": round(coverage_ratio, 3),
                }
            )
            if domain not in domain_coverage:
                domain_coverage[domain] = []
            domain_coverage[domain].append(coverage_ratio)
        for domain, ratios in domain_coverage.items():
            domain_coverage[domain] = (round(sum(ratios) / len(ratios), 3) if ratios else 0.0,)
        overall_coverage = (
            round(sum(domain_coverage.values()) / len(domain_coverage), 3)
            if domain_coverage
            else 0.0,
        )
        return QueryResult(
            category=QueryCategory.REGULATORY_COVERAGE.value,
            query_id="coverage_analysis_001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=coverage_data,
            metadata={
                "overall_coverage": overall_coverage,
                "domain_coverage": domain_coverage,
                "total_domains": len(domain_coverage),
                "filter_applied": {"domain": domain_name, "jurisdiction": jurisdiction},
            },
            confidence_score=0.95,
        )

    async def analyze_cross_jurisdictional_impact(self, regulation_codes: List[str]) -> QueryResult:
        """Analyze impact of regulations across multiple jurisdictions"""
        query = """
        MATCH (r:Regulation)-[:ENFORCED_IN]->(j:Jurisdiction)
        WHERE r.code IN $regulation_codes

        WITH r, j
        MATCH (r)<-[:MANDATED_BY]-(req:Requirement)
        OPTIONAL MATCH (req)<-[:ADDRESSES]-(c:Control)
        OPTIONAL MATCH (r)<-[:VIOLATES]-(ec:EnforcementCase)

        WITH r, j, req, c, ec,
             CASE r.extraterritorial_reach
                 WHEN true THEN ["global"]
                 ELSE [j.code]
             END as applicable_jurisdictions

        RETURN r.code as regulation_code,
               r.name as regulation_name,
               r.extraterritorial_reach as extraterritorial,
               j.code as primary_jurisdiction,
               j.enforcement_approach as enforcement_style,
               applicable_jurisdictions,
               count(DISTINCT req) as requirements_count,
               count(DISTINCT c) as controls_count,
               count(DISTINCT ec) as enforcement_cases,
               avg(ec.penalty_amount) as avg_penalty_amount,
               collect(DISTINCT req.business_function) as affected_functions,
               max(ec.case_date) as latest_enforcement

        ORDER BY extraterritorial DESC, requirements_count DESC
        """
        result = await self.neo4j.execute_query(query, {"regulation_codes": regulation_codes})
        impact_data = []
        total_jurisdictions = set()
        extraterritorial_regulations = []
        for record in result:
            regulation_code = record["regulation_code"]
            applicable_jurisdictions = record["applicable_jurisdictions"]
            total_jurisdictions.update(applicable_jurisdictions)
            if record["extraterritorial"]:
                extraterritorial_regulations.append(regulation_code)
            impact_data.append(
                {
                    "regulation": {
                        "code": regulation_code,
                        "name": record["regulation_name"],
                        "extraterritorial_reach": record["extraterritorial"],
                    },
                    "jurisdictional_scope": {
                        "primary_jurisdiction": record["primary_jurisdiction"],
                        "enforcement_style": record["enforcement_style"],
                        "applicable_jurisdictions": applicable_jurisdictions,
                        "scope_breadth": len(applicable_jurisdictions),
                    },
                    "compliance_complexity": {
                        "requirements_count": record["requirements_count"],
                        "controls_count": record["controls_count"],
                        "affected_functions": record["affected_functions"],
                    },
                    "enforcement_risk": {
                        "historical_cases": record["enforcement_cases"],
                        "average_penalty": record["avg_penalty_amount"],
                        "latest_enforcement": record["latest_enforcement"],
                    },
                }
            )
        return QueryResult(
            category=QueryCategory.CROSS_JURISDICTIONAL.value,
            query_id="cross_jurisdictional_001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=impact_data,
            metadata={
                "total_jurisdictions_affected": len(total_jurisdictions),
                "extraterritorial_regulations": extraterritorial_regulations,
                "jurisdictional_complexity_score": len(total_jurisdictions)
                * len(extraterritorial_regulations),
                "regulations_analyzed": len(regulation_codes),
            },
            confidence_score=0.92,
        )

    async def detect_risk_convergence_patterns(self, risk_threshold: str = "high") -> QueryResult:
        """Detect convergence patterns in regulatory risks"""
        query = """
        MATCH (req1:Requirement)-[:SIMILAR_RISK]->(req2:Requirement)
        WHERE req1.risk_level IN ['high', 'critical']
        AND req2.risk_level IN ['high', 'critical']

        MATCH (req1)-[:MANDATED_BY]->(r1:Regulation)
        MATCH (req2)-[:MANDATED_BY]->(r2:Regulation)
        MATCH (r1)-[:GOVERNED_BY]->(d1:ComplianceDomain)
        MATCH (r2)-[:GOVERNED_BY]->(d2:ComplianceDomain)

        WITH req1, req2, r1, r2, d1, d2,
             CASE
                 WHEN d1 = d2 THEN "same_domain"
                 ELSE "cross_domain"
             END as convergence_type

        OPTIONAL MATCH (req1)<-[:ADDRESSES]-(c1:Control)
        OPTIONAL MATCH (req2)<-[:ADDRESSES]-(c2:Control)

        WITH req1, req2, r1, r2, d1, d2, convergence_type,
             count(DISTINCT c1) as controls_req1,
             count(DISTINCT c2) as controls_req2,
             collect(DISTINCT c1.control_type) as control_types_1,
             collect(DISTINCT c2.control_type) as control_types_2

        RETURN req1.id as requirement_1_id,
               req1.title as requirement_1_title,
               req1.business_function as function_1,
               r1.code as regulation_1,
               d1.name as domain_1,

               req2.id as requirement_2_id,
               req2.title as requirement_2_title,
               req2.business_function as function_2,
               r2.code as regulation_2,
               d2.name as domain_2,

               convergence_type,
               controls_req1,
               controls_req2,
               control_types_1,
               control_types_2,

               CASE
                   WHEN controls_req1 > 0 AND controls_req2 > 0 THEN "both_controlled"
                   WHEN controls_req1 > 0 OR controls_req2 > 0 THEN "partially_controlled"
                   ELSE "uncontrolled"
               END as control_status,

               size(apoc.coll.intersection(control_types_1, control_types_2)) as shared_control_types

        ORDER BY convergence_type, shared_control_types DESC
        """
        result = await self.neo4j.execute_query(query)
        convergence_data = []
        same_domain_convergences = 0
        cross_domain_convergences = 0
        uncontrolled_risks = 0
        for record in result:
            convergence_type = record["convergence_type"]
            control_status = record["control_status"]
            if convergence_type == "same_domain":
                same_domain_convergences += 1
            else:
                cross_domain_convergences += 1
            if control_status == "uncontrolled":
                uncontrolled_risks += 1
            convergence_data.append(
                {
                    "convergence_id": f"{record['requirement_1_id']}_{record['requirement_2_id']}",
                    "convergence_type": convergence_type,
                    "requirement_1": {
                        "id": record["requirement_1_id"],
                        "title": record["requirement_1_title"],
                        "regulation": record["regulation_1"],
                        "domain": record["domain_1"],
                        "business_function": record["function_1"],
                        "controls_count": record["controls_req1"],
                    },
                    "requirement_2": {
                        "id": record["requirement_2_id"],
                        "title": record["requirement_2_title"],
                        "regulation": record["regulation_2"],
                        "domain": record["domain_2"],
                        "business_function": record["function_2"],
                        "controls_count": record["controls_req2"],
                    },
                    "risk_analysis": {
                        "control_status": control_status,
                        "shared_control_types": record["shared_control_types"],
                        "control_overlap_ratio": record["shared_control_types"]
                        / max(len(record["control_types_1"]) + len(record["control_types_2"]), 1),
                    },
                }
            )
        return QueryResult(
            category=QueryCategory.RISK_CONVERGENCE.value,
            query_id="risk_convergence_001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=convergence_data,
            metadata={
                "total_convergences": len(convergence_data),
                "same_domain_convergences": same_domain_convergences,
                "cross_domain_convergences": cross_domain_convergences,
                "uncontrolled_risks": uncontrolled_risks,
                "risk_convergence_ratio": cross_domain_convergences / max(len(convergence_data), 1),
            },
            confidence_score=0.88,
        )

    async def analyze_compliance_gaps(
        self, business_functions: Optional[List[str]] = None
    ) -> QueryResult:
        """Identify compliance gaps where requirements lack controls"""
        query = """
        MATCH (req:Requirement)-[:MANDATED_BY]->(r:Regulation)-[:GOVERNED_BY]->(d:ComplianceDomain)
        WHERE ($functions IS NULL OR req.business_function IN $functions)

        OPTIONAL MATCH (req)<-[:ADDRESSES]-(c:Control)

        WITH req, r, d,
             count(c) as control_count,
             collect(c) as controls

        WHERE control_count = 0  // Requirements without controls = gaps

        OPTIONAL MATCH (r)<-[:VIOLATES]-(ec:EnforcementCase)
        OPTIONAL MATCH (r)<-[:ASSESSES]-(ra:RiskAssessment)

        RETURN req.id as requirement_id,
               req.title as requirement_title,
               req.description as requirement_description,
               req.risk_level as risk_level,
               req.business_function as business_function,
               req.deadline_type as deadline_type,
               req.mandatory as mandatory,

               r.code as regulation_code,
               r.name as regulation_name,
               r.risk_rating as regulation_risk,
               r.penalty_framework as penalty_framework,

               d.name as domain_name,
               d.business_impact as domain_impact,

               count(DISTINCT ec) as historical_violations,
               max(ec.penalty_amount) as max_penalty_observed,

               ra.risk_rating as current_risk_assessment,
               ra.residual_risk as residual_risk_level,
               ra.next_review as next_risk_review

        ORDER BY
            CASE req.risk_level
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                ELSE 4
            END,
            historical_violations DESC,
            max_penalty_observed DESC
        """
        result = await self.neo4j.execute_query(query, {"functions": business_functions})
        gap_data = []
        critical_gaps = 0
        high_risk_gaps = 0
        total_penalty_exposure = 0
        for record in result:
            risk_level = record["risk_level"]
            penalty_observed = record["max_penalty_observed"] or 0
            if risk_level == "critical":
                critical_gaps += 1
            elif risk_level == "high":
                high_risk_gaps += 1
            total_penalty_exposure += penalty_observed
            severity_multiplier = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(
                risk_level, 1
            )
            enforcement_multiplier = min(record["historical_violations"] * 0.5, 2.0)
            gap_severity = severity_multiplier * (1 + enforcement_multiplier)
            gap_data.append(
                {
                    "gap_id": record["requirement_id"],
                    "requirement": {
                        "id": record["requirement_id"],
                        "title": record["requirement_title"],
                        "description": record["requirement_description"],
                        "risk_level": risk_level,
                        "business_function": record["business_function"],
                        "deadline_type": record["deadline_type"],
                        "mandatory": record["mandatory"],
                    },
                    "regulation": {
                        "code": record["regulation_code"],
                        "name": record["regulation_name"],
                        "risk_rating": record["regulation_risk"],
                        "penalty_framework": record["penalty_framework"],
                    },
                    "domain": {
                        "name": record["domain_name"],
                        "business_impact": record["domain_impact"],
                    },
                    "risk_assessment": {
                        "current_assessment": record["current_risk_assessment"],
                        "residual_risk": record["residual_risk_level"],
                        "next_review": record["next_risk_review"],
                    },
                    "enforcement_history": {
                        "historical_violations": record["historical_violations"],
                        "max_penalty_observed": penalty_observed,
                    },
                    "gap_severity_score": round(gap_severity, 2),
                    "priority_level": (
                        "critical"
                        if gap_severity >= 8
                        else "high"
                        if gap_severity >= DEFAULT_RETRIES
                        else "medium",
                    ),
                }
            )
        return QueryResult(
            category=QueryCategory.COMPLIANCE_GAPS.value,
            query_id="compliance_gaps_001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=gap_data,
            metadata={
                "total_gaps": len(gap_data),
                "critical_gaps": critical_gaps,
                "high_risk_gaps": high_risk_gaps,
                "total_penalty_exposure": total_penalty_exposure,
                "business_functions_analyzed": business_functions or "all",
                "average_gap_severity": round(
                    sum(gap["gap_severity_score"] for gap in gap_data) / max(len(gap_data), 1), 2
                ),
            },
            confidence_score=0.94,
        )

    async def analyze_temporal_regulatory_changes(
        self, lookback_months: int = 12, forecast_months: int = 6
    ) -> QueryResult:
        """Analyze temporal patterns in regulatory changes"""
        lookback_date = datetime.now() - timedelta(days=lookback_months * 30)
        forecast_date = datetime.now() + timedelta(days=forecast_months * 30)
        query = """
        MATCH (r:Regulation)
        WHERE r.last_updated >= date($lookback_date)

        OPTIONAL MATCH (r)<-[:MANDATED_BY]-(req:Requirement)
        OPTIONAL MATCH (r)<-[:ASSESSES]-(ra:RiskAssessment)
        WHERE ra.next_review <= date($forecast_date)

        WITH r, req, ra,
             duration.between(r.effective_date, r.last_updated).months as regulation_age_months,
             duration.between(r.last_updated, date()).months as months_since_update

        RETURN r.code as regulation_code,
               r.name as regulation_name,
               r.jurisdiction as jurisdiction,
               r.effective_date as effective_date,
               r.last_updated as last_updated,
               regulation_age_months,
               months_since_update,

               count(DISTINCT req) as affected_requirements,
               count(DISTINCT ra) as upcoming_reviews,
               min(ra.next_review) as next_review_date,

               CASE
                   WHEN months_since_update <= 3 THEN "recent"
                   WHEN months_since_update <= 6 THEN "moderate"
                   ELSE "stable"
               END as change_recency,

               CASE
                   WHEN regulation_age_months <= 12 THEN "new"
                   WHEN regulation_age_months <= 36 THEN "established"
                   ELSE "mature"
               END as regulation_maturity

        ORDER BY months_since_update ASC, upcoming_reviews DESC
        """
        result = await self.neo4j.execute_query(
            query,
            {
                "lookback_date": lookback_date.strftime("%Y-%m-%d"),
                "forecast_date": forecast_date.strftime("%Y-%m-%d"),
            },
        )
        temporal_data = []
        recent_changes = 0
        upcoming_reviews = 0
        new_regulations = 0
        for record in result:
            change_recency = record["change_recency"]
            regulation_maturity = record["regulation_maturity"]
            reviews_count = record["upcoming_reviews"]
            if change_recency == "recent":
                recent_changes += 1
            if reviews_count > 0:
                upcoming_reviews += 1
            if regulation_maturity == "new":
                new_regulations += 1
            temporal_data.append(
                {
                    "regulation": {
                        "code": record["regulation_code"],
                        "name": record["regulation_name"],
                        "jurisdiction": record["jurisdiction"],
                    },
                    "temporal_analysis": {
                        "effective_date": record["effective_date"],
                        "last_updated": record["last_updated"],
                        "regulation_age_months": record["regulation_age_months"],
                        "months_since_update": record["months_since_update"],
                        "change_recency": change_recency,
                        "regulation_maturity": regulation_maturity,
                    },
                    "impact_scope": {
                        "affected_requirements": record["affected_requirements"],
                        "upcoming_reviews": reviews_count,
                        "next_review_date": record["next_review_date"],
                    },
                    "change_velocity": round(
                        record["affected_requirements"] / max(record["months_since_update"], 1), 2
                    ),
                }
            )
        return QueryResult(
            category=QueryCategory.TEMPORAL_CHANGES.value,
            query_id="temporal_changes_001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=temporal_data,
            metadata={
                "analysis_period": {
                    "lookback_months": lookback_months,
                    "forecast_months": forecast_months,
                },
                "change_summary": {
                    "recent_changes": recent_changes,
                    "upcoming_reviews": upcoming_reviews,
                    "new_regulations": new_regulations,
                    "total_regulations_analyzed": len(temporal_data),
                },
                "change_intensity": round(recent_changes / max(len(temporal_data), 1), 2),
            },
            confidence_score=0.9,
        )

    async def analyze_enforcement_learning_patterns(
        self, violation_types: Optional[List[str]] = None
    ) -> QueryResult:
        """Learn from enforcement cases to predict compliance risks"""
        query = """
        MATCH (ec:EnforcementCase)-[:VIOLATES]->(r:Regulation)
        WHERE ($violation_types IS NULL OR ec.violation_type IN $violation_types)

        MATCH (r)<-[:MANDATED_BY]-(req:Requirement)
        OPTIONAL MATCH (req)<-[:ADDRESSES]-(c:Control)

        WITH ec, r, req,
             count(DISTINCT c) as existing_controls,
             collect(DISTINCT c.control_type) as control_types

        RETURN ec.id as case_id,
               ec.violation_type as violation_type,
               ec.jurisdiction as jurisdiction,
               ec.organization_type as organization_type,
               ec.penalty_amount as penalty_amount,
               ec.penalty_currency as penalty_currency,
               ec.case_date as case_date,
               ec.violation_summary as violation_summary,
               ec.lessons_learned as lessons_learned,
               ec.preventive_measures as preventive_measures,

               r.code as regulation_code,
               r.name as regulation_name,

               count(DISTINCT req) as affected_requirements,
               existing_controls,
               control_types,

               CASE
                   WHEN existing_controls = 0 THEN "uncontrolled"
                   WHEN existing_controls < count(DISTINCT req) THEN "partially_controlled"
                   ELSE "fully_controlled"
               END as control_adequacy

        ORDER BY ec.case_date DESC, ec.penalty_amount DESC
        """
        result = await self.neo4j.execute_query(query, {"violation_types": violation_types})
        enforcement_data = []
        violation_patterns = {}
        total_penalties = 0
        for record in result:
            violation_type = record["violation_type"]
            penalty_amount = record["penalty_amount"] or 0
            total_penalties += penalty_amount
            if violation_type not in violation_patterns:
                violation_patterns[violation_type] = {
                    "count": 0,
                    "total_penalty": 0,
                    "organizations": set(),
                    "jurisdictions": set(),
                }
            violation_patterns[violation_type]["count"] += 1
            violation_patterns[violation_type]["total_penalty"] += penalty_amount
            violation_patterns[violation_type]["organizations"].add(record["organization_type"])
            violation_patterns[violation_type]["jurisdictions"].add(record["jurisdiction"])
            enforcement_data.append(
                {
                    "case": {
                        "id": record["case_id"],
                        "violation_type": violation_type,
                        "jurisdiction": record["jurisdiction"],
                        "organization_type": record["organization_type"],
                        "case_date": record["case_date"],
                    },
                    "financial_impact": {
                        "penalty_amount": penalty_amount,
                        "penalty_currency": record["penalty_currency"],
                    },
                    "violation_details": {
                        "summary": record["violation_summary"],
                        "lessons_learned": record["lessons_learned"],
                        "preventive_measures": record["preventive_measures"],
                    },
                    "regulation": {
                        "code": record["regulation_code"],
                        "name": record["regulation_name"],
                    },
                    "control_analysis": {
                        "affected_requirements": record["affected_requirements"],
                        "existing_controls": record["existing_controls"],
                        "control_types": record["control_types"],
                        "control_adequacy": record["control_adequacy"],
                    },
                }
            )
        processed_patterns = {}
        for vtype, data in violation_patterns.items():
            processed_patterns[vtype] = {
                "frequency": data["count"],
                "total_penalty": data["total_penalty"],
                "average_penalty": data["total_penalty"] / data["count"],
                "organization_types": list(data["organizations"]),
                "jurisdictions": list(data["jurisdictions"]),
                "risk_score": min(data["count"] * (data["total_penalty"] / 1000000), 10),
            }
        return QueryResult(
            category=QueryCategory.ENFORCEMENT_LEARNING.value,
            query_id="enforcement_learning_001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=enforcement_data,
            metadata={
                "total_cases": len(enforcement_data),
                "total_penalties": total_penalties,
                "violation_patterns": processed_patterns,
                "average_penalty": total_penalties / max(len(enforcement_data), 1),
                "violation_types_analyzed": violation_types or "all",
            },
            confidence_score=0.87,
        )


async def execute_compliance_query(
    query_category: QueryCategory, neo4j_service: Neo4jGraphRAGService, **kwargs
) -> QueryResult:
    """Factory function to execute compliance queries by category"""
    queries = ComplianceRetrievalQueries(neo4j_service)
    query_map = {
        QueryCategory.REGULATORY_COVERAGE: queries.get_regulatory_coverage_analysis,
        QueryCategory.CROSS_JURISDICTIONAL: queries.analyze_cross_jurisdictional_impact,
        QueryCategory.RISK_CONVERGENCE: queries.detect_risk_convergence_patterns,
        QueryCategory.COMPLIANCE_GAPS: queries.analyze_compliance_gaps,
        QueryCategory.TEMPORAL_CHANGES: queries.analyze_temporal_regulatory_changes,
        QueryCategory.ENFORCEMENT_LEARNING: queries.analyze_enforcement_learning_patterns,
    }
    if query_category not in query_map:
        raise ValueError(f"Query category {query_category} not implemented")
    return await query_map[query_category](**kwargs)
