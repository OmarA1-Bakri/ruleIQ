"""
Recommendation, conversion, and summary generation for freemium assessments.

All functions are stateless — no database or AI dependencies.
"""

from typing import Any, Dict, List, Optional


def get_fallback_recommendations(compliance_score: float) -> List[Dict[str, Any]]:
    """Get fallback recommendations when AI is unavailable."""
    if compliance_score < 40:
        return [
            {
                "priority": "high",
                "title": "Implement Basic Security Policies",
                "description": "Establish fundamental information security policies and procedures.",
                "estimated_effort": "2-4 weeks",
            },
            {
                "priority": "high",
                "title": "Data Protection Assessment",
                "description": "Conduct a comprehensive review of personal data handling practices.",
                "estimated_effort": "1-2 weeks",
            },
        ]
    elif compliance_score < 70:
        return [
            {
                "priority": "medium",
                "title": "Enhance Existing Controls",
                "description": "Strengthen current compliance measures and fill identified gaps.",
                "estimated_effort": "3-6 weeks",
            },
        ]
    else:
        return [
            {
                "priority": "low",
                "title": "Continuous Improvement",
                "description": "Implement regular reviews and updates to maintain compliance.",
                "estimated_effort": "Ongoing",
            },
        ]


def generate_next_steps(compliance_score: float, risk_level: str) -> List[str]:
    """Generate actionable next steps."""
    if compliance_score < 40:
        return [
            "Schedule a compliance consultation",
            "Prioritize high-risk areas identified",
            "Implement basic security controls",
        ]
    elif compliance_score < 70:
        return [
            "Review detailed recommendations",
            "Create implementation timeline",
            "Consider compliance platform trial",
        ]
    else:
        return [
            "Maintain current compliance practices",
            "Schedule periodic reviews",
            "Stay updated on regulatory changes",
        ]


def generate_conversion_opportunities(
    compliance_score: float,
    risk_level: str,
    gaps_identified: List[Dict[str, Any]],
    lead: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Generate conversion opportunities based on assessment results."""
    opportunities: List[Dict[str, Any]] = []

    if compliance_score < 60:
        opportunities.append(
            {
                "type": "consultation",
                "title": "Free Compliance Consultation",
                "description": "Get expert guidance on addressing your compliance gaps",
                "urgency": "high",
                "cta_text": "Book Free Consultation",
            },
        )

    if len(gaps_identified) > 3:
        opportunities.append(
            {
                "type": "trial",
                "title": "14-Day Free Trial",
                "description": "Try our compliance platform to address identified gaps",
                "urgency": "medium",
                "cta_text": "Start Free Trial",
            },
        )

    return opportunities


def generate_results_summary(
    compliance_score: float,
    risk_level: str,
    recommendations: List[Dict[str, Any]],
    gaps_identified: List[Dict[str, Any]],
) -> str:
    """Generate a human-readable results summary."""
    summary_parts = [
        f"Your compliance score is {compliance_score}% with a {risk_level} risk level.",
        f"We identified {len(gaps_identified)} areas for improvement.",
        f"Our analysis includes {len(recommendations)} personalized recommendations.",
    ]

    if compliance_score >= 80:
        summary_parts.append(
            "Your organization demonstrates strong compliance practices.",
        )
    elif compliance_score >= 60:
        summary_parts.append(
            "Your compliance foundation is solid but can be strengthened.",
        )
    else:
        summary_parts.append("Significant compliance improvements are recommended.")

    return " ".join(summary_parts)
