"""
Fallback question banks for freemium assessments.

Used when AI question generation is unavailable (circuit breaker open, quota
exhausted, etc.). Each assessment type maps to a curated list of questions.
"""

from typing import Any, Dict, List

FALLBACK_QUESTIONS: Dict[str, List[Dict[str, Any]]] = {
    "general": [
        {
            "question_id": "gen_001",
            "question_text": "Does your organization handle personal data from customers or employees?",
            "question_type": "yes_no",
            "category": "data_protection",
            "options": ["Yes", "No", "Unsure"],
        },
        {
            "question_id": "gen_002",
            "question_text": "Do you have documented information security policies?",
            "question_type": "yes_no",
            "category": "security",
            "options": ["Yes", "No", "In development"],
        },
        {
            "question_id": "gen_003",
            "question_text": "How do you currently back up your business data?",
            "question_type": "multiple_choice",
            "category": "data_management",
            "options": [
                "Cloud backup",
                "Local backup",
                "Both",
                "No formal backup",
                "Don't know",
            ],
        },
        {
            "question_id": "gen_004",
            "question_text": "Do you conduct regular security training for your employees?",
            "question_type": "yes_no",
            "category": "training",
            "options": [
                "Yes, regularly",
                "Yes, occasionally",
                "No",
                "Planning to start",
            ],
        },
        {
            "question_id": "gen_005",
            "question_text": "How do you manage access to sensitive business data?",
            "question_type": "multiple_choice",
            "category": "access_control",
            "options": [
                "Role-based access",
                "Department-based",
                "Everyone has access",
                "No formal system",
                "Unsure",
            ],
        },
        {
            "question_id": "gen_006",
            "question_text": "Do you have a data breach response plan?",
            "question_type": "yes_no",
            "category": "incident_response",
            "options": [
                "Yes, documented",
                "Yes, informal",
                "No",
                "In development",
            ],
        },
        {
            "question_id": "gen_007",
            "question_text": "How often do you review your compliance status?",
            "question_type": "multiple_choice",
            "category": "compliance_review",
            "options": [
                "Monthly",
                "Quarterly",
                "Annually",
                "Never",
                "Ad-hoc basis",
            ],
        },
        {
            "question_id": "gen_008",
            "question_text": "Do you use encryption for sensitive data?",
            "question_type": "yes_no",
            "category": "data_security",
            "options": [
                "Yes, at rest and in transit",
                "Yes, partially",
                "No",
                "Don't know",
            ],
        },
    ],
    "gdpr": [
        {
            "question_id": "gdpr_001",
            "question_text": "Do you process personal data of EU residents?",
            "question_type": "yes_no",
            "category": "scope",
            "options": ["Yes", "No", "Possibly"],
        },
        {
            "question_id": "gdpr_002",
            "question_text": "Do you have a Data Protection Officer (DPO) appointed?",
            "question_type": "yes_no",
            "category": "governance",
            "options": ["Yes", "No", "Not required"],
        },
        {
            "question_id": "gdpr_003",
            "question_text": "Do you have a privacy policy that meets GDPR requirements?",
            "question_type": "yes_no",
            "category": "documentation",
            "options": [
                "Yes, fully compliant",
                "Yes, needs updating",
                "No",
                "Unsure",
            ],
        },
        {
            "question_id": "gdpr_004",
            "question_text": "How do you handle data subject access requests?",
            "question_type": "multiple_choice",
            "category": "data_rights",
            "options": [
                "Automated process",
                "Manual process",
                "No formal process",
                "Never received any",
            ],
        },
        {
            "question_id": "gdpr_005",
            "question_text": "Do you maintain records of processing activities?",
            "question_type": "yes_no",
            "category": "documentation",
            "options": [
                "Yes, comprehensive",
                "Yes, partial",
                "No",
                "Planning to implement",
            ],
        },
        {
            "question_id": "gdpr_006",
            "question_text": "Have you conducted a Data Protection Impact Assessment (DPIA)?",
            "question_type": "yes_no",
            "category": "assessment",
            "options": [
                "Yes, recently",
                "Yes, over a year ago",
                "No",
                "Not sure if required",
            ],
        },
    ],
    "security": [
        {
            "question_id": "sec_001",
            "question_text": "Do you use multi-factor authentication for business systems?",
            "question_type": "yes_no",
            "category": "access_control",
            "options": ["Yes, everywhere", "Yes, partially", "No", "Don't know"],
        },
        {
            "question_id": "sec_002",
            "question_text": "How often do you update your software and systems?",
            "question_type": "multiple_choice",
            "category": "maintenance",
            "options": [
                "Immediately",
                "Monthly",
                "Quarterly",
                "Annually",
                "Rarely",
            ],
        },
        {
            "question_id": "sec_003",
            "question_text": "Do you perform regular security vulnerability assessments?",
            "question_type": "yes_no",
            "category": "assessment",
            "options": [
                "Yes, regularly",
                "Yes, occasionally",
                "No",
                "Planning to start",
            ],
        },
        {
            "question_id": "sec_004",
            "question_text": "How do you manage user passwords and credentials?",
            "question_type": "multiple_choice",
            "category": "credential_management",
            "options": [
                "Password manager",
                "Single sign-on",
                "Manual tracking",
                "No formal system",
            ],
        },
        {
            "question_id": "sec_005",
            "question_text": "Do you have network segmentation in place?",
            "question_type": "yes_no",
            "category": "network_security",
            "options": [
                "Yes, comprehensive",
                "Yes, partial",
                "No",
                "Don't know",
            ],
        },
        {
            "question_id": "sec_006",
            "question_text": "How do you monitor for security incidents?",
            "question_type": "multiple_choice",
            "category": "monitoring",
            "options": [
                "24/7 SOC",
                "Automated tools",
                "Manual reviews",
                "No active monitoring",
            ],
        },
        {
            "question_id": "sec_007",
            "question_text": "Do you have an incident response team?",
            "question_type": "yes_no",
            "category": "incident_response",
            "options": [
                "Yes, dedicated team",
                "Yes, assigned roles",
                "No",
                "Outsourced",
            ],
        },
        {
            "question_id": "sec_008",
            "question_text": "How often do you conduct security awareness training?",
            "question_type": "multiple_choice",
            "category": "training",
            "options": [
                "Monthly",
                "Quarterly",
                "Annually",
                "During onboarding only",
                "Never",
            ],
        },
        {
            "question_id": "sec_009",
            "question_text": "Do you maintain an inventory of all IT assets?",
            "question_type": "yes_no",
            "category": "asset_management",
            "options": ["Yes, automated", "Yes, manual", "Partial", "No"],
        },
        {
            "question_id": "sec_010",
            "question_text": "Have you implemented Zero Trust security principles?",
            "question_type": "yes_no",
            "category": "architecture",
            "options": [
                "Yes, fully",
                "Yes, partially",
                "No",
                "Planning to implement",
            ],
        },
    ],
}


def get_fallback_questions(assessment_type: str) -> List[Dict[str, Any]]:
    """Get fallback questions for the given assessment type.

    Falls back to 'general' questions if the type is not recognized.
    """
    return FALLBACK_QUESTIONS.get(assessment_type, FALLBACK_QUESTIONS["general"])
