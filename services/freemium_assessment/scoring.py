"""
Pure scoring and gap-identification functions for freemium assessments.

All functions are stateless — no database or AI dependencies.
"""

from typing import Any, Dict, List


def calculate_compliance_score(answers: Dict[str, Any], assessment_type: str) -> float:
    """Calculate compliance score based on answers.

    Returns a percentage (0.0–100.0) rounded to one decimal place.
    """
    if not answers:
        return 0.0

    total_score = 0.0
    answer_count = len(answers)

    for answer_data in answers.values():
        answer = str(answer_data.get("answer", "")).lower()
        confidence = answer_data.get("confidence", "medium")

        # Basic scoring
        if "yes" in answer or "implemented" in answer or "compliant" in answer:
            score = 85.0
        elif "partially" in answer or "in progress" in answer:
            score = 60.0
        elif "no" in answer or "not implemented" in answer:
            score = 25.0
        else:
            score = 50.0  # Neutral/text answers

        # Adjust for confidence
        confidence_multiplier = {"high": 1.0, "medium": 0.9, "low": 0.7}.get(
            confidence,
            0.8,
        )
        total_score += score * confidence_multiplier

    return round(total_score / answer_count, 1)


def determine_risk_level(compliance_score: float, ai_analysis: Dict[str, Any]) -> str:
    """Determine risk level based on compliance score."""
    if compliance_score >= 80:
        return "low"
    elif compliance_score >= 60:
        return "medium"
    elif compliance_score >= 40:
        return "high"
    else:
        return "critical"


def identify_compliance_gaps(
    answers: Dict[str, Any], assessment_type: str, ai_analysis: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Identify specific compliance gaps based on answers."""
    gaps = []

    for question_id, answer_data in answers.items():
        answer = str(answer_data.get("answer", "")).lower()

        if "no" in answer or "not implemented" in answer:
            gaps.append(
                {
                    "question_id": question_id,
                    "gap_type": "missing_control",
                    "severity": "medium",
                    "description": f"Gap identified in {question_id}",
                },
            )

    return gaps
