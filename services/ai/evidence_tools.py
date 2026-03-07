"""
import logging


logger = logging.getLogger(__name__)
# Constants
MINUTE_SECONDS = 60

DEFAULT_RETRIES = 5
HALF_RATIO = 0.5
MAX_RETRIES = 3


Evidence and Compliance Scoring Tools for Function Calling

Implements tools for evidence requirement mapping and compliance scoring
to support comprehensive assessment analysis.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from config.logging_config import get_logger
from .tools import BaseTool, ToolResult, ToolType, register_tool

logger = get_logger(__name__)


@dataclass
class EvidenceRequirement:
    """Represents an evidence requirement for compliance"""

    id: str
    title: str
    description: str
    framework: str
    control_reference: str
    evidence_type: str
    collection_method: str
    frequency: str
    priority: str
    responsible_party: str
    automation_potential: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "framework": self.framework,
            "control_reference": self.control_reference,
            "evidence_type": self.evidence_type,
            "collection_method": self.collection_method,
            "frequency": self.frequency,
            "priority": self.priority,
            "responsible_party": self.responsible_party,
            "automation_potential": self.automation_potential,
        }


@dataclass
class ComplianceScore:
    """Represents a compliance score calculation"""

    overall_score: float
    category_scores: Dict[str, float]
    maturity_level: str
    risk_level: str
    confidence_score: float
    calculation_date: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "category_scores": self.category_scores,
            "maturity_level": self.maturity_level,
            "risk_level": self.risk_level,
            "confidence_score": self.confidence_score,
            "calculation_date": self.calculation_date,
        }


class EvidenceMapperTool(BaseTool):
    """Tool for mapping evidence requirements to compliance controls"""

    def __init__(self) -> None:
        super().__init__(
            name="map_evidence_requirements",
            description="Map evidence requirements to compliance controls and create collection plans",
        )

    def get_function_schema(self) -> Dict[str, Any]:
        """Get the function schema for Google Generative AI function calling"""
        return {
            "name": "map_evidence_requirements",
            "description": "Map evidence requirements to compliance controls",
            "parameters": {
                "type": "object",
                "properties": {
                    "evidence_requirements": {
                        "type": "array",
                        "description": "List of evidence requirements",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "Title of the evidence requirement",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Detailed description of what evidence is needed",
                                },
                                "framework": {
                                    "type": "string",
                                    "description": "Compliance framework (e.g., 'GDPR', 'ISO27001')",
                                },
                                "control_reference": {
                                    "type": "string",
                                    "description": "Specific control or article reference",
                                },
                                "evidence_type": {
                                    "type": "string",
                                    "enum": ["document", "process", "technical", "interview"],
                                    "description": "Type of evidence required",
                                },
                                "collection_method": {
                                    "type": "string",
                                    "description": "How the evidence should be collected",
                                },
                                "frequency": {
                                    "type": "string",
                                    "enum": [
                                        "one-time",
                                        "annual",
                                        "quarterly",
                                        "monthly",
                                        "continuous",
                                    ],
                                    "description": "How often evidence needs to be collected",
                                },
                                "priority": {
                                    "type": "string",
                                    "enum": ["critical", "high", "medium", "low"],
                                    "description": "Priority level for evidence collection",
                                },
                                "responsible_party": {
                                    "type": "string",
                                    "description": "Who is responsible for collecting this evidence",
                                },
                                "automation_potential": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low", "none"],
                                    "description": "Potential for automating evidence collection",
                                },
                            },
                            "required": [
                                "title",
                                "description",
                                "framework",
                                "control_reference",
                                "evidence_type",
                                "collection_method",
                                "frequency",
                                "priority",
                            ],
                        },
                    },
                    "collection_plan": {
                        "type": "object",
                        "properties": {
                            "immediate_actions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Actions to take immediately (0-30 days)",
                            },
                            "short_term_actions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Actions for 1-3 months",
                            },
                            "ongoing_processes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Ongoing evidence collection processes",
                            },
                            "automation_opportunities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Opportunities for automating evidence collection",
                            },
                        },
                        "required": [
                            "immediate_actions",
                            "short_term_actions",
                            "ongoing_processes",
                        ],
                    },
                    "resource_requirements": {
                        "type": "object",
                        "properties": {
                            "personnel": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Personnel needed for evidence collection",
                            },
                            "tools_and_systems": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tools and systems needed",
                            },
                            "estimated_effort": {
                                "type": "string",
                                "description": "Estimated effort required",
                            },
                            "budget_considerations": {
                                "type": "string",
                                "description": "Budget considerations for evidence collection",
                            },
                        },
                        "required": ["personnel", "tools_and_systems", "estimated_effort"],
                    },
                },
                "required": ["evidence_requirements", "collection_plan", "resource_requirements"],
            },
        }

    async def execute(
        self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute evidence requirement mapping"""
        try:
            evidence_data = parameters.get("evidence_requirements", [])
            collection_plan = parameters.get("collection_plan", {})
            resource_requirements = parameters.get("resource_requirements", {})
            processed_evidence = []
            for i, evidence_data_item in enumerate(evidence_data):
                evidence = EvidenceRequirement(
                    id=f"evidence_{i + 1}",
                    title=evidence_data_item.get("title", ""),
                    description=evidence_data_item.get("description", ""),
                    framework=evidence_data_item.get("framework", ""),
                    control_reference=evidence_data_item.get("control_reference", ""),
                    evidence_type=evidence_data_item.get("evidence_type", "document"),
                    collection_method=evidence_data_item.get("collection_method", ""),
                    frequency=evidence_data_item.get("frequency", "annual"),
                    priority=evidence_data_item.get("priority", "medium"),
                    responsible_party=evidence_data_item.get("responsible_party", "TBD"),
                    automation_potential=evidence_data_item.get("automation_potential", "low"),
                )
                processed_evidence.append(evidence.to_dict())
            evidence_analysis = self._analyze_evidence_requirements(processed_evidence)
            collection_timeline = self._generate_collection_timeline(processed_evidence)
            result_data = {
                "evidence_requirements": processed_evidence,
                "evidence_count": len(processed_evidence),
                "collection_plan": collection_plan,
                "resource_requirements": resource_requirements,
                "evidence_analysis": evidence_analysis,
                "collection_timeline": collection_timeline,
                "automation_recommendations": self._generate_automation_recommendations(
                    processed_evidence
                ),
                "analysis_timestamp": datetime.now().isoformat(),
            }
            logger.info(
                "Evidence mapping completed: %s evidence requirements mapped"
                % len(processed_evidence)
            )
            return ToolResult(
                success=True,
                data=result_data,
                metadata={
                    "tool_type": "evidence_mapping",
                    "evidence_count": len(processed_evidence),
                    "frameworks": list({e["framework"] for e in processed_evidence}),
                },
            )
        except Exception as e:
            logger.error("Evidence mapping failed: %s" % e)
            return ToolResult(success=False, error=f"Evidence mapping execution failed: {e!s}")

    def _analyze_evidence_requirements(self, evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze evidence requirements for insights"""
        analysis = {
            "by_type": {},
            "by_frequency": {},
            "by_priority": {},
            "by_framework": {},
            "automation_potential": {},
        }
        for evidence in evidence_list:
            evidence_type = evidence.get("evidence_type", "unknown")
            analysis["by_type"][evidence_type] = analysis["by_type"].get(evidence_type, 0) + 1
            frequency = evidence.get("frequency", "unknown")
            analysis["by_frequency"][frequency] = analysis["by_frequency"].get(frequency, 0) + 1
            priority = evidence.get("priority", "unknown")
            analysis["by_priority"][priority] = analysis["by_priority"].get(priority, 0) + 1
            framework = evidence.get("framework", "unknown")
            analysis["by_framework"][framework] = analysis["by_framework"].get(framework, 0) + 1
            automation = evidence.get("automation_potential", "unknown")
            analysis["automation_potential"][automation] = (
                analysis["automation_potential"].get(automation, 0) + 1
            )
        return analysis

    def _generate_collection_timeline(
        self, evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, str]]]:
        """Generate timeline for evidence collection"""
        timeline = {"immediate": [], "quarterly": [], "annual": [], "continuous": []}
        for evidence in evidence_list:
            item = {
                "title": evidence["title"],
                "priority": evidence["priority"],
                "responsible_party": evidence["responsible_party"],
            }
            frequency = evidence.get("frequency", "annual")
            priority = evidence.get("priority", "medium")
            if priority == "critical" or frequency == "one-time":
                timeline["immediate"].append(item)
            elif frequency in {"quarterly", "monthly"}:
                timeline["quarterly"].append(item)
            elif frequency == "continuous":
                timeline["continuous"].append(item)
            else:
                timeline["annual"].append(item)
        return timeline

    def _generate_automation_recommendations(
        self, evidence_list: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Generate recommendations for automating evidence collection"""
        recommendations = []
        high_automation_items = [
            e for e in evidence_list if e.get("automation_potential") == "high"
        ]
        for item in high_automation_items:
            recommendations.append(
                {
                    "evidence": item["title"],
                    "recommendation": f"Consider automated collection for {item['title']} using {item['collection_method']}",
                    "benefit": "Reduced manual effort and improved consistency",
                    "implementation_effort": "Medium",
                }
            )
        if len(high_automation_items) > MAX_RETRIES:
            recommendations.append(
                {
                    "evidence": "Multiple items",
                    "recommendation": "Implement centralized evidence management platform",
                    "benefit": "Streamlined evidence collection and reporting",
                    "implementation_effort": "High",
                }
            )
        return recommendations


class ComplianceScoringTool(BaseTool):
    """Tool for calculating compliance scores and maturity levels"""

    def __init__(self) -> None:
        super().__init__(
            name="calculate_compliance_score",
            description="Calculate compliance scores and maturity levels based on assessment results",
        )

    def get_function_schema(self) -> Dict[str, Any]:
        """Get the function schema for Google Generative AI function calling"""
        return {
            "name": "calculate_compliance_score",
            "description": "Calculate compliance scores and maturity levels",
            "parameters": {
                "type": "object",
                "properties": {
                    "assessment_results": {
                        "type": "object",
                        "properties": {
                            "framework": {
                                "type": "string",
                                "description": "Compliance framework assessed",
                            },
                            "total_controls": {
                                "type": "number",
                                "description": "Total number of controls assessed",
                            },
                            "compliant_controls": {
                                "type": "number",
                                "description": "Number of fully compliant controls",
                            },
                            "partially_compliant_controls": {
                                "type": "number",
                                "description": "Number of partially compliant controls",
                            },
                            "non_compliant_controls": {
                                "type": "number",
                                "description": "Number of non-compliant controls",
                            },
                            "category_scores": {
                                "type": "object",
                                "description": "Scores by category (e.g., {'data_protection': 85, 'access_control': 75})",
                                "additionalProperties": {"type": "number"},
                            },
                        },
                        "required": [
                            "framework",
                            "total_controls",
                            "compliant_controls",
                            "partially_compliant_controls",
                            "non_compliant_controls",
                        ],
                    },
                    "weighting_factors": {
                        "type": "object",
                        "properties": {
                            "critical_controls_weight": {
                                "type": "number",
                                "description": "Weight multiplier for critical controls (default: 1.5)",
                            },
                            "business_impact_weight": {
                                "type": "number",
                                "description": "Weight based on business impact (default: 1.0)",
                            },
                            "regulatory_risk_weight": {
                                "type": "number",
                                "description": "Weight based on regulatory risk (default: 1.2)",
                            },
                        },
                    },
                    "context_factors": {
                        "type": "object",
                        "properties": {
                            "industry": {
                                "type": "string",
                                "description": "Industry sector for context",
                            },
                            "business_size": {
                                "type": "string",
                                "enum": ["micro", "small", "medium", "large"],
                                "description": "Size of the business",
                            },
                            "risk_tolerance": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                                "description": "Organization's risk tolerance",
                            },
                            "assessment_scope": {
                                "type": "string",
                                "description": "Scope of the assessment",
                            },
                        },
                    },
                },
                "required": ["assessment_results"],
            },
        }

    async def execute(
        self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute compliance scoring calculation"""
        try:
            assessment_results = parameters.get("assessment_results", {})
            weighting_factors = parameters.get("weighting_factors", {})
            context_factors = parameters.get("context_factors", {})
            base_score = self._calculate_base_score(assessment_results)
            weighted_score = self._apply_weighting(base_score, weighting_factors)
            maturity_level = self._determine_maturity_level(weighted_score, assessment_results)
            risk_level = self._calculate_risk_level(
                weighted_score, assessment_results, context_factors
            )
            confidence_score = self._calculate_confidence_score(assessment_results)
            compliance_score = ComplianceScore(
                overall_score=weighted_score,
                category_scores=assessment_results.get("category_scores", {}),
                maturity_level=maturity_level,
                risk_level=risk_level,
                confidence_score=confidence_score,
                calculation_date=datetime.now().isoformat(),
            )
            improvement_recommendations = self._generate_improvement_recommendations(
                weighted_score, assessment_results, context_factors
            )
            benchmark_comparison = self._generate_benchmark_comparison(
                weighted_score, context_factors
            )
            result_data = {
                "compliance_score": compliance_score.to_dict(),
                "score_breakdown": {
                    "base_score": base_score,
                    "weighted_score": weighted_score,
                    "weighting_applied": weighting_factors,
                    "score_calculation": self._explain_score_calculation(assessment_results),
                },
                "improvement_recommendations": improvement_recommendations,
                "benchmark_comparison": benchmark_comparison,
                "next_assessment_recommendation": self._recommend_next_assessment(
                    weighted_score, maturity_level
                ),
                "analysis_timestamp": datetime.now().isoformat(),
            }
            logger.info(
                "Compliance scoring completed: %s% overall score, %s maturity"
                % (weighted_score, maturity_level)
            )
            return ToolResult(
                success=True,
                data=result_data,
                metadata={
                    "tool_type": "compliance_scoring",
                    "overall_score": weighted_score,
                    "maturity_level": maturity_level,
                    "risk_level": risk_level,
                },
            )
        except Exception as e:
            logger.error("Compliance scoring failed: %s" % e)
            return ToolResult(success=False, error=f"Compliance scoring execution failed: {e!s}")

    def _calculate_base_score(self, assessment_results: Dict[str, Any]) -> float:
        """Calculate base compliance score"""
        total = assessment_results.get("total_controls", 0)
        if total == 0:
            return 0.0
        compliant = assessment_results.get("compliant_controls", 0)
        partially_compliant = assessment_results.get("partially_compliant_controls", 0)
        total_points = compliant + partially_compliant * 0.5
        return total_points / total * 100

    def _apply_weighting(self, base_score: float, weighting_factors: Dict[str, Any]) -> float:
        """Apply weighting factors to base score"""
        critical_weight = weighting_factors.get("critical_controls_weight", 1.0)
        business_weight = weighting_factors.get("business_impact_weight", 1.0)
        regulatory_weight = weighting_factors.get("regulatory_risk_weight", 1.0)
        composite_weight = (critical_weight + business_weight + regulatory_weight) / 3
        weighted_score = min(100.0, base_score * composite_weight)
        return round(weighted_score, 1)

    def _determine_maturity_level(self, score: float, assessment_results: Dict[str, Any]) -> str:
        """Determine maturity level based on score and assessment details"""
        if score >= 90:
            return "optimized"
        elif score >= 75:
            return "managed"
        elif score >= MINUTE_SECONDS:
            return "defined"
        elif score >= 40:
            return "developing"
        else:
            return "initial"

    def _calculate_risk_level(
        self, score: float, assessment_results: Dict[str, Any], context_factors: Dict[str, Any]
    ) -> str:
        """Calculate overall risk level"""
        non_compliant = assessment_results.get("non_compliant_controls", 0)
        total = assessment_results.get("total_controls", 1)
        risk_tolerance = context_factors.get("risk_tolerance", "medium")
        non_compliant_ratio = non_compliant / total
        if risk_tolerance == "low":
            if non_compliant_ratio > 0.2 or score < 70:
                return "critical"
            elif non_compliant_ratio > 0.1 or score < 80:
                return "high"
            elif score < 90:
                return "medium"
            else:
                return "low"
        elif risk_tolerance == "high":
            if non_compliant_ratio > HALF_RATIO or score < 40:
                return "critical"
            elif non_compliant_ratio > 0.3 or score < MINUTE_SECONDS:
                return "high"
            elif score < 75:
                return "medium"
            else:
                return "low"
        elif non_compliant_ratio > 0.3 or score < 50:
            return "critical"
        elif non_compliant_ratio > 0.2 or score < 70:
            return "high"
        elif score < 85:
            return "medium"
        else:
            return "low"

    def _calculate_confidence_score(self, assessment_results: Dict[str, Any]) -> float:
        """Calculate confidence in the score based on assessment completeness"""
        total_controls = assessment_results.get("total_controls", 0)
        if total_controls >= 50:
            base_confidence = 0.95
        elif total_controls >= 20:
            base_confidence = 0.85
        elif total_controls >= 10:
            base_confidence = 0.75
        else:
            base_confidence = 0.6
        category_scores = assessment_results.get("category_scores", {})
        if len(category_scores) >= DEFAULT_RETRIES:
            base_confidence += 0.05
        return min(1.0, base_confidence)

    def _generate_improvement_recommendations(
        self, score: float, assessment_results: Dict[str, Any], context_factors: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate recommendations for score improvement"""
        recommendations = []
        if score < MINUTE_SECONDS:
            recommendations.append(
                {
                    "priority": "critical",
                    "recommendation": "Focus on fundamental compliance controls implementation",
                    "impact": "High - Address basic compliance requirements first",
                }
            )
        if score < 80:
            recommendations.append(
                {
                    "priority": "high",
                    "recommendation": "Implement systematic compliance monitoring processes",
                    "impact": "Medium - Improve ongoing compliance management",
                }
            )
        category_scores = assessment_results.get("category_scores", {})
        for category, category_score in category_scores.items():
            if category_score < 70:
                recommendations.append(
                    {
                        "priority": "medium",
                        "recommendation": f"Strengthen {category.replace('_', ' ')} controls and processes",
                        "impact": f"Medium - Improve {category} compliance",
                    }
                )
        return recommendations

    def _generate_benchmark_comparison(
        self, score: float, context_factors: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate benchmark comparison data"""
        industry = context_factors.get("industry", "general")
        business_size = context_factors.get("business_size", "medium")
        industry_benchmarks = {
            "financial": {"average": 78, "good": 85, "excellent": 92},
            "healthcare": {"average": 75, "good": 82, "excellent": 90},
            "technology": {"average": 72, "good": 80, "excellent": 88},
            "general": {"average": 70, "good": 78, "excellent": 85},
        }
        benchmark = industry_benchmarks.get(industry, industry_benchmarks["general"])
        performance_level = "below_average"
        if score >= benchmark["excellent"]:
            performance_level = "excellent"
        elif score >= benchmark["good"]:
            performance_level = "good"
        elif score >= benchmark["average"]:
            performance_level = "average"
        return {
            "industry": industry,
            "business_size": business_size,
            "your_score": score,
            "industry_average": benchmark["average"],
            "industry_good": benchmark["good"],
            "industry_excellent": benchmark["excellent"],
            "performance_level": performance_level,
            "percentile_rank": self._calculate_percentile_rank(score, benchmark),
        }

    def _calculate_percentile_rank(self, score: float, benchmark: Dict[str, float]) -> int:
        """Calculate approximate percentile rank"""
        if score >= benchmark["excellent"]:
            return 90
        elif score >= benchmark["good"]:
            return 75
        elif score >= benchmark["average"]:
            return 50
        else:
            return 25

    def _recommend_next_assessment(self, score: float, maturity_level: str) -> str:
        """Recommend when to conduct next assessment"""
        if score < MINUTE_SECONDS or maturity_level == "initial":
            return ("3-6 months - Frequent assessments needed for rapid improvement",)
        elif score < 80 or maturity_level in ["developing", "defined"]:
            return "6-12 months - Regular assessments to track progress"
        else:
            return "12-18 months - Annual assessments for maintenance"

    def _explain_score_calculation(self, assessment_results: Dict[str, Any]) -> Dict[str, Any]:
        """Explain how the score was calculated"""
        total = assessment_results.get("total_controls", 0)
        compliant = assessment_results.get("compliant_controls", 0)
        partially_compliant = assessment_results.get("partially_compliant_controls", 0)
        non_compliant = assessment_results.get("non_compliant_controls", 0)
        return {
            "total_controls_assessed": total,
            "fully_compliant": compliant,
            "partially_compliant": partially_compliant,
            "non_compliant": non_compliant,
            "calculation_method": "Fully compliant controls = 100% weight, Partially compliant = 50% weight",
            "score_formula": "(compliant + (partially_compliant * 0.5)) / total * 100",
        }


register_tool(EvidenceMapperTool(), ToolType.EVIDENCE_MAPPING)
register_tool(ComplianceScoringTool(), ToolType.COMPLIANCE_SCORING)
