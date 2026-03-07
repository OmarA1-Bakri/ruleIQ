"""
Fallback Response Generator

Provides default responses when AI generation fails.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# Framework-specific recommendation templates
GDPR_RECOMMENDATIONS = [
    {
        "control_id": "GDPR-1",
        "title": "Data Processing Policy",
        "description": "Establish a comprehensive policy for processing personal data",
        "priority": "High",
        "effort_hours": 8,
        "automation_possible": False,
        "business_justification": "Required for GDPR compliance",
        "implementation_steps": [
            "Document data processing activities",
            "Define lawful basis for processing",
            "Establish data retention policies",
        ],
    },
    {
        "control_id": "GDPR-2",
        "title": "Data Subject Rights Procedures",
        "description": "Implement procedures for handling data subject requests",
        "priority": "High",
        "effort_hours": 6,
        "automation_possible": True,
        "business_justification": "Legal requirement under GDPR",
        "implementation_steps": [
            "Create request handling process",
            "Train staff on rights procedures",
            "Implement tracking system",
        ],
    },
]

ISO27001_RECOMMENDATIONS = [
    {
        "control_id": "ISO-A.5.1",
        "title": "Information Security Policy",
        "description": "Develop and maintain an information security policy",
        "priority": "High",
        "effort_hours": 10,
        "automation_possible": False,
        "business_justification": "Foundation of ISO 27001 compliance",
        "implementation_steps": [
            "Draft security policy document",
            "Get management approval",
            "Communicate to all staff",
        ],
    },
    {
        "control_id": "ISO-A.9.1",
        "title": "Access Control Policy",
        "description": "Establish access control requirements",
        "priority": "High",
        "effort_hours": 8,
        "automation_possible": True,
        "business_justification": "Protect information assets",
        "implementation_steps": [
            "Define access requirements",
            "Implement access controls",
            "Review access regularly",
        ],
    },
]


class FallbackGenerator:
    """Generates fallback responses when AI is unavailable."""

    @staticmethod
    def get_recommendations(
        framework: str, maturity_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get fallback recommendations for a framework.

        Args:
            framework: Framework identifier
            maturity_analysis: Maturity analysis data

        Returns:
            List of recommendation dictionaries
        """
        framework_upper = framework.upper()

        if "GDPR" in framework_upper:
            return GDPR_RECOMMENDATIONS.copy()
        elif "ISO" in framework_upper or "27001" in framework_upper:
            return ISO27001_RECOMMENDATIONS.copy()
        else:
            # Generic recommendations
            return [
                {
                    "control_id": "GEN-1",
                    "title": "Compliance Assessment",
                    "description": "Conduct initial compliance assessment",
                    "priority": "High",
                    "effort_hours": 4,
                    "automation_possible": False,
                    "business_justification": "Understand current compliance status",
                    "implementation_steps": [
                        "Review framework requirements",
                        "Assess current controls",
                        "Identify gaps",
                    ],
                }
            ]

    @staticmethod
    def get_policy(
        framework: str, policy_type: str, business_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get fallback policy template.

        Args:
            framework: Framework identifier
            policy_type: Type of policy
            business_context: Business context

        Returns:
            Policy dictionary
        """
        return {
            "title": f"{framework} {policy_type} Policy",
            "version": "1.0",
            "effective_date": "TBD",
            "sections": [
                {
                    "title": "Purpose",
                    "content": f"This policy outlines {policy_type} requirements for {framework} compliance.",
                },
                {
                    "title": "Scope",
                    "content": "This policy applies to all organizational activities and personnel.",
                },
                {
                    "title": "Requirements",
                    "content": "Specific requirements will be defined based on framework standards.",
                },
            ],
            "roles": [
                {"title": "Compliance Officer", "responsibilities": ["Policy oversight"]},
                {"title": "Management", "responsibilities": ["Policy approval"]},
            ],
            "procedures": [
                {"title": "Policy Review", "steps": ["Annual review", "Update as needed"]}
            ],
        }

    @staticmethod
    def get_workflow(framework: str, control_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get fallback workflow template.

        Args:
            framework: Framework identifier
            control_id: Optional control identifier

        Returns:
            Workflow dictionary
        """
        return {
            "workflow_id": str(uuid4()),
            "framework": framework,
            "control_id": control_id,
            "phases": [
                {
                    "phase_id": "planning",
                    "name": "Planning",
                    "description": "Plan evidence collection approach",
                    "steps": [
                        {
                            "step_id": "plan-1",
                            "name": "Identify Requirements",
                            "description": "Determine what evidence is needed",
                            "effort_hours": 2,
                            "automation_possible": False,
                            "dependencies": [],
                        }
                    ],
                },
                {
                    "phase_id": "collection",
                    "name": "Collection",
                    "description": "Collect required evidence",
                    "steps": [
                        {
                            "step_id": "collect-1",
                            "name": "Gather Evidence",
                            "description": "Collect evidence items",
                            "effort_hours": 4,
                            "automation_possible": True,
                            "dependencies": ["plan-1"],
                        }
                    ],
                },
                {
                    "phase_id": "review",
                    "name": "Review",
                    "description": "Review collected evidence",
                    "steps": [
                        {
                            "step_id": "review-1",
                            "name": "Review Quality",
                            "description": "Ensure evidence meets requirements",
                            "effort_hours": 2,
                            "automation_possible": False,
                            "dependencies": ["collect-1"],
                        }
                    ],
                },
            ],
            "effort_estimation": {
                "total_hours": 8,
                "total_days": 1,
                "by_phase": {"planning": 2, "collection": 4, "review": 2},
            },
        }

    @staticmethod
    def get_assessment_help(question_text: str, framework_id: str) -> Dict[str, Any]:
        """
        Get fallback assessment help.

        Args:
            question_text: Question text
            framework_id: Framework identifier

        Returns:
            Help response dictionary
        """
        return {
            "guidance": f"For {framework_id}, please consider the specific requirements related to: {question_text}",
            "confidence_score": 0.5,
            "related_topics": [],
            "follow_up_suggestions": [
                "Review framework documentation",
                "Consult with compliance expert",
            ],
            "source_references": [],
            "is_fallback": True,
        }

    @staticmethod
    def get_fast_fallback_help(
        question_text: str, framework_id: str, question_id: str
    ) -> Dict[str, Any]:
        """
        Get ultra-fast fallback help for timeouts.

        Args:
            question_text: Question text
            framework_id: Framework identifier
            question_id: Question identifier

        Returns:
            Fast help response dictionary
        """
        return {
            "guidance": "Please refer to framework documentation for guidance on this question.",
            "confidence_score": 0.3,
            "related_topics": [],
            "follow_up_suggestions": [],
            "source_references": [],
            "is_fallback": True,
            "is_fast_fallback": True,
        }

    @staticmethod
    def get_assessment_followup(framework_id: str) -> Dict[str, Any]:
        """Get fallback follow-up questions."""
        return {
            "questions": [
                {
                    "question_text": "What is your current compliance maturity level?",
                    "rationale": "Understanding maturity helps tailor recommendations",
                    "priority": "High",
                }
            ]
        }

    @staticmethod
    def get_assessment_analysis(framework_id: str) -> Dict[str, Any]:
        """Get fallback analysis structure."""
        return {
            "strengths": [],
            "weaknesses": [],
            "gaps": [],
            "compliance_score": 0,
            "risk_level": "Unknown",
            "recommendations": [],
            "is_fallback": True,
        }

    @staticmethod
    def get_assessment_recommendations(framework_id: str) -> Dict[str, Any]:
        """Get fallback recommendations."""
        return {
            "recommendations": [
                {
                    "title": "Begin Compliance Assessment",
                    "description": "Start with a comprehensive compliance assessment",
                    "priority": "High",
                    "effort": "Medium",
                }
            ],
            "is_fallback": True,
        }
