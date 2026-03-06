"""
import logging


logger = logging.getLogger(__name__)
# Constants
DEFAULT_RETRIES = 5


Assessment-Specific AI Tools for Function Calling

Implements specialized tools for compliance assessment analysis including
gap analysis, recommendation generation, evidence mapping, and compliance scoring.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from config.logging_config import get_logger
from .tools import BaseTool, ToolResult, ToolType, register_tool

logger = get_logger(__name__)


@dataclass
class ComplianceGap:
    """Represents a compliance gap identified during analysis"""

    id: str
    section: str
    severity: str
    description: str
    impact: str
    current_state: str
    target_state: str
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "section": self.section,
            "severity": self.severity,
            "description": self.description,
            "impact": self.impact,
            "current_state": self.current_state,
            "target_state": self.target_state,
            "priority": self.priority,
        }


@dataclass
class ComplianceRecommendation:
    """Represents a compliance recommendation"""

    id: str
    title: str
    description: str
    priority: str
    implementation_effort: str
    cost_impact: str
    timeline: str
    dependencies: List[str]
    resources_required: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "implementation_effort": self.implementation_effort,
            "cost_impact": self.cost_impact,
            "timeline": self.timeline,
            "dependencies": self.dependencies,
            "resources_required": self.resources_required,
        }


class GapAnalysisTool(BaseTool):
    """Tool for extracting and analyzing compliance gaps from assessment responses"""

    def __init__(self) -> None:
        super().__init__(
            name="extract_compliance_gaps",
            description="Extract compliance gaps from assessment responses and analyze their severity and impact",
        )

    def get_function_schema(self) -> Dict[str, Any]:
        """Get the function schema for Google Generative AI function calling"""
        return {
            "name": "extract_compliance_gaps",
            "description": "Extract compliance gaps from assessment responses",
            "parameters": {
                "type": "object",
                "properties": {
                    "gaps": {
                        "type": "array",
                        "description": "List of identified compliance gaps",
                        "items": {
                            "type": "object",
                            "properties": {
                                "section": {
                                    "type": "string",
                                    "description": "Compliance framework section (e.g., 'GDPR Article 25', 'ISO 27001 A.5.1')",
                                },
                                "severity": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high", "critical"],
                                    "description": "Severity level of the gap",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Detailed description of the compliance gap",
                                },
                                "impact": {
                                    "type": "string",
                                    "description": "Business impact of not addressing this gap",
                                },
                                "current_state": {
                                    "type": "string",
                                    "description": "Current state of compliance for this requirement",
                                },
                                "target_state": {
                                    "type": "string",
                                    "description": "Required state to achieve compliance",
                                },
                            },
                            "required": [
                                "section",
                                "severity",
                                "description",
                                "impact",
                                "current_state",
                                "target_state",
                            ],
                        },
                    },
                    "overall_risk_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Overall risk level based on identified gaps",
                    },
                    "priority_order": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recommended order for addressing gaps (section identifiers)",
                    },
                    "estimated_effort": {
                        "type": "string",
                        "description": "Estimated total effort to address all gaps",
                    },
                },
                "required": ["gaps", "overall_risk_level", "priority_order", "estimated_effort"],
            },
        }

    async def execute(
        self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute gap analysis on provided data"""
        try:
            gaps_data = parameters.get("gaps", [])
            overall_risk = parameters.get("overall_risk_level", "medium")
            priority_order = parameters.get("priority_order", [])
            estimated_effort = parameters.get("estimated_effort", "Unknown")
            processed_gaps = []
            for i, gap_data in enumerate(gaps_data):
                gap = ComplianceGap(
                    id=f"gap_{i + 1}",
                    section=gap_data.get("section", ""),
                    severity=gap_data.get("severity", "medium"),
                    description=gap_data.get("description", ""),
                    impact=gap_data.get("impact", ""),
                    current_state=gap_data.get("current_state", ""),
                    target_state=gap_data.get("target_state", ""),
                    priority=self._calculate_priority(gap_data.get("severity", "medium"), i),
                )
                processed_gaps.append(gap.to_dict())
            processed_gaps.sort(key=lambda x: x["priority"], reverse=True)
            result_data = {
                "gaps": processed_gaps,
                "gap_count": len(processed_gaps),
                "severity_breakdown": self._analyze_severity_breakdown(processed_gaps),
                "overall_risk_level": overall_risk,
                "priority_order": priority_order,
                "estimated_effort": estimated_effort,
                "analysis_timestamp": datetime.now().isoformat(),
                "recommendations": self._generate_gap_recommendations(processed_gaps),
            }
            logger.info(
                "Gap analysis completed: %s gaps identified with %s overall risk"
                % (len(processed_gaps), overall_risk)
            )
            return ToolResult(
                success=True,
                data=result_data,
                metadata={
                    "tool_type": "gap_analysis",
                    "gaps_processed": len(processed_gaps),
                    "risk_level": overall_risk,
                },
            )
        except Exception as e:
            logger.error("Gap analysis failed: %s" % e)
            return ToolResult(success=False, error=f"Gap analysis execution failed: {e!s}")

    def _calculate_priority(self, severity: str, index: int) -> int:
        """Calculate priority score for gap ordering"""
        severity_scores = {"critical": 100, "high": 75, "medium": 50, "low": 25}
        base_score = severity_scores.get(severity, 50)
        return base_score - index * 2

    def _analyze_severity_breakdown(self, gaps: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze breakdown of gap severities"""
        breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for gap in gaps:
            severity = gap.get("severity", "medium")
            if severity in breakdown:
                breakdown[severity] += 1
        return breakdown

    def _generate_gap_recommendations(self, gaps: List[Dict[str, Any]]) -> List[str]:
        """Generate high-level recommendations based on gaps"""
        recommendations = []
        high_severity_count = sum(1 for gap in gaps if gap.get("severity") in ["critical", "high"])
        if high_severity_count > 0:
            recommendations.append(f"Address {high_severity_count} high-priority gaps immediately")
        if len(gaps) > DEFAULT_RETRIES:
            recommendations.append(
                "Consider phased implementation approach due to high number of gaps"
            )
        sections = [gap.get("section", "") for gap in gaps]
        if any("GDPR" in section for section in sections):
            recommendations.append("Focus on GDPR compliance as regulatory priority")
        if any("ISO 27001" in section for section in sections):
            recommendations.append("Implement ISO 27001 security controls systematically")
        return recommendations


class RecommendationGenerationTool(BaseTool):
    """Tool for generating prioritized compliance recommendations"""

    def __init__(self) -> None:
        super().__init__(
            name="generate_compliance_recommendations",
            description="Generate prioritized compliance recommendations based on assessment analysis",
        )

    def get_function_schema(self) -> Dict[str, Any]:
        """Get the function schema for Google Generative AI function calling"""
        return {
            "name": "generate_compliance_recommendations",
            "description": "Generate prioritized compliance recommendations",
            "parameters": {
                "type": "object",
                "properties": {
                    "recommendations": {
                        "type": "array",
                        "description": "List of compliance recommendations",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "Title of the recommendation",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Detailed description of what needs to be implemented",
                                },
                                "priority": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high", "critical"],
                                    "description": "Priority level for implementation",
                                },
                                "implementation_effort": {
                                    "type": "string",
                                    "description": "Estimated effort (e.g., '2-4 weeks', '1-2 days')",
                                },
                                "cost_impact": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"],
                                    "description": "Expected cost impact",
                                },
                                "timeline": {
                                    "type": "string",
                                    "description": "Recommended implementation timeline",
                                },
                                "dependencies": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Dependencies that must be addressed first",
                                },
                                "resources_required": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Resources needed for implementation",
                                },
                            },
                            "required": [
                                "title",
                                "description",
                                "priority",
                                "implementation_effort",
                                "cost_impact",
                                "timeline",
                            ],
                        },
                    },
                    "implementation_roadmap": {
                        "type": "object",
                        "properties": {
                            "phase_1": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Immediate actions (0-3 months)",
                            },
                            "phase_2": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Short-term actions (3-6 months)",
                            },
                            "phase_3": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Long-term actions (6+ months)",
                            },
                        },
                        "required": ["phase_1", "phase_2", "phase_3"],
                    },
                    "budget_estimate": {
                        "type": "object",
                        "properties": {
                            "low_estimate": {"type": "string"},
                            "high_estimate": {"type": "string"},
                            "key_cost_drivers": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["low_estimate", "high_estimate", "key_cost_drivers"],
                    },
                },
                "required": ["recommendations", "implementation_roadmap", "budget_estimate"],
            },
        }

    async def execute(
        self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute recommendation generation"""
        try:
            recommendations_data = parameters.get("recommendations", [])
            roadmap = parameters.get("implementation_roadmap", {})
            budget = parameters.get("budget_estimate", {})
            processed_recommendations = []
            for i, rec_data in enumerate(recommendations_data):
                recommendation = ComplianceRecommendation(
                    id=f"rec_{i + 1}",
                    title=rec_data.get("title", ""),
                    description=rec_data.get("description", ""),
                    priority=rec_data.get("priority", "medium"),
                    implementation_effort=rec_data.get("implementation_effort", "Unknown"),
                    cost_impact=rec_data.get("cost_impact", "medium"),
                    timeline=rec_data.get("timeline", "TBD"),
                    dependencies=rec_data.get("dependencies", []),
                    resources_required=rec_data.get("resources_required", []),
                )
                processed_recommendations.append(recommendation.to_dict())
            priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            processed_recommendations.sort(
                key=lambda x: priority_order.get(x["priority"], 2), reverse=True
            )
            result_data = {
                "recommendations": processed_recommendations,
                "recommendation_count": len(processed_recommendations),
                "priority_breakdown": self._analyze_priority_breakdown(processed_recommendations),
                "implementation_roadmap": roadmap,
                "budget_estimate": budget,
                "analysis_timestamp": datetime.now().isoformat(),
                "quick_wins": self._identify_quick_wins(processed_recommendations),
                "major_initiatives": self._identify_major_initiatives(processed_recommendations),
            }
            logger.info(
                "Recommendation generation completed: %s recommendations generated"
                % len(processed_recommendations)
            )
            return ToolResult(
                success=True,
                data=result_data,
                metadata={
                    "tool_type": "recommendation_generation",
                    "recommendations_count": len(processed_recommendations),
                    "high_priority_count": sum(
                        1
                        for r in processed_recommendations
                        if r["priority"] in ["critical", "high"]
                    ),
                },
            )
        except Exception as e:
            logger.error("Recommendation generation failed: %s" % e)
            return ToolResult(
                success=False, error=f"Recommendation generation execution failed: {e!s}"
            )

    def _analyze_priority_breakdown(self, recommendations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze breakdown of recommendation priorities"""
        breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for rec in recommendations:
            priority = rec.get("priority", "medium")
            if priority in breakdown:
                breakdown[priority] += 1
        return breakdown

    def _identify_quick_wins(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Identify quick win recommendations"""
        quick_wins = []
        for rec in recommendations:
            effort = rec.get("implementation_effort", "").lower()
            cost = rec.get("cost_impact", "").lower()
            if any(term in effort for term in ["day", "week", "quick", "easy"]) and cost == "low":
                quick_wins.append(
                    {
                        "title": rec["title"],
                        "effort": rec["implementation_effort"],
                        "timeline": rec["timeline"],
                    }
                )
        return quick_wins

    def _identify_major_initiatives(
        self, recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Identify major initiative recommendations"""
        major_initiatives = []
        for rec in recommendations:
            effort = rec.get("implementation_effort", "").lower()
            priority = rec.get("priority", "").lower()
            if (
                any(term in effort for term in ["month", "quarter", "major", "significant"])
                or priority == "critical"
            ):
                major_initiatives.append(
                    {
                        "title": rec["title"],
                        "priority": rec["priority"],
                        "effort": rec["implementation_effort"],
                        "dependencies": len(rec.get("dependencies", [])),
                    }
                )
        return major_initiatives


register_tool(GapAnalysisTool(), ToolType.GAP_ANALYSIS)
register_tool(RecommendationGenerationTool(), ToolType.RECOMMENDATION)
