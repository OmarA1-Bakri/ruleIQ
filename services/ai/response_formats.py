"""

Structured Output Format Definitions for Google Gemini API

This module defines JSON schemas that will be used with Google Gemini's
response_schema parameter to ensure structured AI responses.

Part of Phase 6: Response Schema Validation implementation.
"""

from typing import Any, Dict

# =====================================================================
# Gap Analysis Response Format
# =====================================================================

GAP_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "category": {"type": "string"},
                    "framework_reference": {"type": "string"},
                    "current_state": {"type": "string"},
                    "target_state": {"type": "string"},
                    "impact_description": {"type": "string"},
                    "business_impact_score": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "technical_complexity": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "regulatory_requirement": {"type": "boolean"},
                    "estimated_effort": {
                        "type": "string",
                        "enum": ["minimal", "low", "medium", "high", "extensive"],
                    },
                    "dependencies": {"type": "array", "items": {"type": "string"}},
                    "affected_systems": {"type": "array", "items": {"type": "string"}},
                    "stakeholders": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "id",
                    "title",
                    "description",
                    "severity",
                    "category",
                    "framework_reference",
                    "current_state",
                    "target_state",
                    "impact_description",
                    "business_impact_score",
                    "technical_complexity",
                    "regulatory_requirement",
                    "estimated_effort",
                ],
            },
        },
        "overall_risk_level": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
        "priority_order": {"type": "array", "items": {"type": "string"}},
        "estimated_total_effort": {"type": "string"},
        "critical_gap_count": {"type": "integer"},
        "medium_high_gap_count": {"type": "integer"},
        "compliance_percentage": {"type": "number", "minimum": 0.0, "maximum": 100.0},
        "framework_coverage": {
            "type": "object",
            "additionalProperties": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 100.0,
            },
        },
        "summary": {"type": "string"},
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "gaps",
        "overall_risk_level",
        "priority_order",
        "estimated_total_effort",
        "critical_gap_count",
        "medium_high_gap_count",
        "compliance_percentage",
        "summary",
        "next_steps",
    ],
}


# =====================================================================
# Recommendation Response Format
# =====================================================================

RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                    },
                    "category": {"type": "string"},
                    "framework_references": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "addresses_gaps": {"type": "array", "items": {"type": "string"}},
                    "effort_estimate": {
                        "type": "string",
                        "enum": ["minimal", "low", "medium", "high", "extensive"],
                    },
                    "implementation_timeline": {"type": "string"},
                    "impact_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "cost_estimate": {"type": "string"},
                    "resource_requirements": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "success_criteria": {"type": "array", "items": {"type": "string"}},
                    "potential_challenges": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "mitigation_strategies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "automation_potential": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "roi_estimate": {"type": "string"},
                },
                "required": [
                    "id",
                    "title",
                    "description",
                    "priority",
                    "category",
                    "framework_references",
                    "addresses_gaps",
                    "effort_estimate",
                    "implementation_timeline",
                    "impact_score",
                ],
            },
        },
        "implementation_plan": {
            "type": "object",
            "properties": {
                "total_duration_weeks": {"type": "integer"},
                "phases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "phase_number": {"type": "integer"},
                            "phase_name": {"type": "string"},
                            "duration_weeks": {"type": "integer"},
                            "deliverables": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "resources_required": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "success_criteria": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "phase_number",
                            "phase_name",
                            "duration_weeks",
                            "deliverables",
                            "success_criteria",
                        ],
                    },
                },
                "resource_allocation": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "budget_estimate": {"type": "string"},
                "risk_factors": {"type": "array", "items": {"type": "string"}},
                "success_metrics": {"type": "array", "items": {"type": "string"}},
                "milestone_checkpoints": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["total_duration_weeks", "phases", "success_metrics"],
        },
        "prioritization_rationale": {"type": "string"},
        "quick_wins": {"type": "array", "items": {"type": "string"}},
        "long_term_initiatives": {"type": "array", "items": {"type": "string"}},
        "resource_summary": {"type": "object", "additionalProperties": True},
        "timeline_overview": {"type": "string"},
        "success_metrics": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "recommendations",
        "implementation_plan",
        "prioritization_rationale",
        "timeline_overview",
        "success_metrics",
    ],
}


# =====================================================================
# Assessment Analysis Response Format
# =====================================================================

ASSESSMENT_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "gaps": {"type": "array", "items": {"$ref": "#/$defs/gap"}},
        "recommendations": {
            "type": "array",
            "items": {"$ref": "#/$defs/recommendation"},
        },
        "risk_assessment": {
            "type": "object",
            "properties": {
                "overall_risk_level": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                },
                "risk_score": {"type": "number", "minimum": 0.0, "maximum": 100.0},
                "top_risk_factors": {"type": "array", "items": {"type": "string"}},
                "risk_mitigation_priorities": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "regulatory_compliance_risk": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 100.0,
                },
                "operational_risk": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 100.0,
                },
                "reputational_risk": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 100.0,
                },
                "financial_risk": {"type": "number", "minimum": 0.0, "maximum": 100.0},
            },
            "required": [
                "overall_risk_level",
                "risk_score",
                "top_risk_factors",
                "risk_mitigation_priorities",
            ],
        },
        "compliance_insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "insight_type": {
                        "type": "string",
                        "enum": ["strength", "weakness", "opportunity", "threat"],
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "impact_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "framework_area": {"type": "string"},
                    "actionable_steps": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "insight_type",
                    "title",
                    "description",
                    "impact_level",
                    "framework_area",
                    "actionable_steps",
                ],
            },
        },
        "evidence_requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "evidence_type": {"type": "string"},
                    "description": {"type": "string"},
                    "framework_reference": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                    },
                    "collection_method": {"type": "string"},
                    "automation_potential": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "estimated_effort": {
                        "type": "string",
                        "enum": ["minimal", "low", "medium", "high", "extensive"],
                    },
                    "validation_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "retention_period": {"type": "string"},
                },
                "required": [
                    "evidence_type",
                    "description",
                    "framework_reference",
                    "priority",
                    "collection_method",
                    "estimated_effort",
                ],
            },
        },
        "compliance_metrics": {
            "type": "object",
            "properties": {
                "overall_compliance_score": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 100.0,
                },
                "framework_scores": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 100.0,
                    },
                },
                "maturity_level": {
                    "type": "string",
                    "enum": [
                        "initial",
                        "developing",
                        "defined",
                        "managed",
                        "optimized",
                    ],
                },
                "coverage_percentage": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 100.0,
                },
                "gap_count_by_severity": {
                    "type": "object",
                    "properties": {
                        "low": {"type": "integer"},
                        "medium": {"type": "integer"},
                        "high": {"type": "integer"},
                        "critical": {"type": "integer"},
                    },
                },
                "improvement_trend": {
                    "type": "string",
                    "enum": ["improving", "stable", "declining"],
                },
            },
            "required": [
                "overall_compliance_score",
                "maturity_level",
                "coverage_percentage",
                "improvement_trend",
            ],
        },
        "executive_summary": {"type": "string"},
        "detailed_findings": {"type": "string"},
        "next_steps": {"type": "array", "items": {"type": "string"}},
        "confidence_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": [
        "gaps",
        "recommendations",
        "risk_assessment",
        "compliance_insights",
        "evidence_requirements",
        "compliance_metrics",
        "executive_summary",
        "detailed_findings",
        "next_steps",
        "confidence_score",
    ],
}


# =====================================================================
# Guidance Response Format
# =====================================================================

GUIDANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "guidance": {"type": "string"},
        "confidence_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "related_topics": {"type": "array", "items": {"type": "string"}},
        "follow_up_suggestions": {"type": "array", "items": {"type": "string"}},
        "source_references": {"type": "array", "items": {"type": "string"}},
        "examples": {"type": "array", "items": {"type": "string"}},
        "best_practices": {"type": "array", "items": {"type": "string"}},
        "common_pitfalls": {"type": "array", "items": {"type": "string"}},
        "implementation_tips": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "guidance",
        "confidence_score",
        "related_topics",
        "follow_up_suggestions",
        "source_references",
    ],
}


# =====================================================================
# Follow-up Response Format
# =====================================================================

FOLLOWUP_SCHEMA = {
    "type": "object",
    "properties": {
        "follow_up_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "question_text": {"type": "string"},
                    "category": {"type": "string"},
                    "importance_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                    },
                    "expected_answer_type": {
                        "type": "string",
                        "enum": ["text", "boolean", "multiple_choice", "numeric"],
                    },
                    "context": {"type": "string"},
                    "validation_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "question_id",
                    "question_text",
                    "category",
                    "importance_level",
                    "expected_answer_type",
                ],
            },
        },
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "confidence_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "assessment_completeness": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "priority_areas": {"type": "array", "items": {"type": "string"}},
        "suggested_next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "follow_up_questions",
        "recommendations",
        "confidence_score",
        "assessment_completeness",
        "suggested_next_steps",
    ],
}


# =====================================================================
# Intent Classification Format
# =====================================================================

INTENT_CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "intent_type": {
            "type": "string",
            "enum": [
                "evidence_query",
                "compliance_check",
                "guidance_request",
                "general_query",
                "assessment_help",
            ],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "entities": {
            "type": "object",
            "properties": {
                "frameworks": {"type": "array", "items": {"type": "string"}},
                "evidence_types": {"type": "array", "items": {"type": "string"}},
                "topics": {"type": "array", "items": {"type": "string"}},
            },
        },
        "context_requirements": {"type": "array", "items": {"type": "string"}},
        "suggested_actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["intent_type", "confidence", "entities"],
}


# =====================================================================
# Schema Registry
# =====================================================================

RESPONSE_SCHEMAS = {
    "gap_analysis": GAP_ANALYSIS_SCHEMA,
    "recommendations": RECOMMENDATION_SCHEMA,
    "assessment_analysis": ASSESSMENT_ANALYSIS_SCHEMA,
    "guidance": GUIDANCE_SCHEMA,
    "followup": FOLLOWUP_SCHEMA,
    "intent_classification": INTENT_CLASSIFICATION_SCHEMA,
}


def get_schema_for_response_type(response_type: str) -> Dict[str, Any]:
    """Get the JSON schema for a specific response type."""
    return RESPONSE_SCHEMAS.get(response_type, {})


def get_all_schemas() -> Dict[str, Dict[str, Any]]:
    """Get all available response schemas."""
    return RESPONSE_SCHEMAS.copy()


def validate_schema_exists(response_type: str) -> bool:
    """Check if a schema exists for the given response type."""
    return response_type in RESPONSE_SCHEMAS
