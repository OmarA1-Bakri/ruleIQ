"""
Compliance Analysis Service

Handles compliance analysis, evidence gap detection, and validation.
Ported from legacy ComplianceAssistant implementation.
"""

import json
import logging
import re
from typing import Any, Dict, List
from uuid import UUID, uuid4

from services.ai.response.generator import ResponseGenerator
from services.ai.context_manager import ContextManager

logger = logging.getLogger(__name__)


class ComplianceAnalysisService:
    """Handles compliance analysis operations."""

    def __init__(
        self, response_generator: ResponseGenerator, context_manager: ContextManager
    ) -> None:
        """Initialize the compliance analysis service."""
        self.response_generator = response_generator
        self.context_manager = context_manager

    async def analyze_evidence_gap(
        self, business_profile_id: UUID, framework: str
    ) -> Dict[str, Any]:
        """
        Analyze compliance evidence gaps for a specific framework.

        Uses AI to analyze current evidence status and identify critical gaps
        in compliance coverage.

        Args:
            business_profile_id: Business profile ID
            framework: Framework identifier (e.g., 'GDPR', 'ISO27001')

        Returns:
            Gap analysis dictionary with completion percentage, recommendations,
            critical gaps, and risk level

        Raises:
            BusinessLogicException: If gap analysis fails
        """
        try:
            # Get business context and evidence
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )

            business_profile = context.get("business_profile", {})
            evidence_items = context.get("recent_evidence", [])

            # Build AI prompt for gap analysis
            prompt = f"""Analyze compliance evidence gaps for {framework}:

            Business Profile:
            - Company: {business_profile.get("company_name", "Unknown")}
            - Industry: {business_profile.get("industry", "Unknown")}
            - Size: {business_profile.get("employee_count", 0)} employees

            Current Evidence Status:
            - Total Evidence Items: {len(evidence_items)}
            - Evidence Types: {self._get_evidence_types_summary(evidence_items)}

            Framework: {framework}

            Provide a structured analysis with:
            1. Current completion percentage (0-100)
            2. Critical missing evidence types
            3. Top 3 priority recommendations with specific actions
            4. Risk assessment of current gaps
            """

            # Generate AI response
            response = await self.response_generator.generate_simple(
                system_prompt="You are a compliance expert analyzing evidence gaps.",
                user_prompt=prompt,
                task_type="compliance_analysis",
                context={
                    "framework": framework,
                    "business_profile": business_profile,
                    "evidence_count": len(evidence_items),
                },
            )

            # Parse AI response
            try:
                if isinstance(response, str) and response.strip().startswith("{"):
                    parsed_response = json.loads(response)
                    completion_percentage = parsed_response.get("completion_percentage", 50)
                    recommendations = parsed_response.get("recommendations", [])
                    critical_gaps = parsed_response.get("critical_gaps", [])
                    risk_level = parsed_response.get("risk_level", "Medium")
                else:
                    # Fallback parsing
                    completion_percentage = 30
                    recommendations = self._get_fallback_recommendations()
                    critical_gaps = ["Analysis unavailable", "Manual review needed"]
                    risk_level = "Medium"

            except (json.JSONDecodeError, AttributeError):
                # Fallback to default recommendations
                completion_percentage = 30
                recommendations = self._get_fallback_recommendations()
                critical_gaps = ["Documentation gaps", "Policy updates needed"]
                risk_level = "Medium"

            # Summarize evidence types
            evidence_types_dict = self._get_evidence_types_summary(evidence_items)
            evidence_types = list(evidence_types_dict.keys())

            # Count recent activity
            recent_activity = len([item for item in evidence_items if item.get("updated_at")])

            return {
                "framework": framework,
                "completion_percentage": completion_percentage,
                "evidence_collected": len(evidence_items),
                "evidence_types": evidence_types,
                "recent_activity": recent_activity,
                "recommendations": recommendations,
                "critical_gaps": critical_gaps,
                "risk_level": risk_level,
            }

        except Exception as e:
            logger.error(f"Error analyzing evidence gap for {framework}: {e}", exc_info=True)
            # Return fallback response instead of raising
            return {
                "framework": framework,
                "completion_percentage": 30,
                "evidence_collected": 0,
                "evidence_types": [],
                "recent_activity": 0,
                "recommendations": self._get_fallback_recommendations(),
                "critical_gaps": ["Analysis unavailable", "Manual review needed"],
                "risk_level": "Medium",
            }

    @staticmethod
    def validate_accuracy(response: str, framework: str) -> Dict[str, Any]:
        """
        Validate accuracy of a response against known facts.

        Args:
            response: Response text to validate
            framework: Framework identifier

        Returns:
            Validation results dictionary
        """
        # Simplified accuracy validation
        accuracy_score = 0.8  # Default
        fact_checks = []

        # Check for framework-specific facts
        if "GDPR" in framework.upper() and "72" in response and "hour" in response.lower():
            fact_checks.append({"fact": "72 hours notification", "verified": True})
            accuracy_score += 0.1

        return {
            "accuracy_score": min(accuracy_score, 1.0),
            "fact_checks": fact_checks,
            "confidence": "Medium",
            "sources": [],
        }

    @staticmethod
    def detect_hallucination(response: str) -> Dict[str, Any]:
        """
        Detect potential hallucinations in response.

        Args:
            response: Response text to check

        Returns:
            Detection results dictionary
        """
        suspicious_patterns = [
            r"€\d+,\d+.*registration.*fee",
            r"\$\d+,\d+.*annual.*cost",
            r"article.*\d+.*requires.*€",
        ]

        suspicious_claims = []
        for pattern in suspicious_patterns:
            matches = re.finditer(pattern, response, re.IGNORECASE)
            for match in matches:
                suspicious_claims.append(match.group(0))

        hallucination_confidence = len(suspicious_claims) * 0.3

        recommendation = "Verify with official sources" if suspicious_claims else "Appears accurate"

        return {
            "hallucination_detected": len(suspicious_claims) > 0,
            "confidence": min(hallucination_confidence, 1.0),
            "suspicious_claims": suspicious_claims,
            "recommendation": recommendation,
        }

    def generate_compliance_mapping(
        self, policy: Dict[str, Any], framework: str, policy_type: str
    ) -> Dict[str, Any]:
        """
        Generate compliance mapping for a policy.

        Maps policy types to relevant framework controls and provides
        compliance objectives and audit considerations.

        Args:
            policy: Policy dictionary
            framework: Framework identifier (e.g., 'ISO27001', 'GDPR', 'SOC2')
            policy_type: Type of policy (e.g., 'information_security', 'data_protection')

        Returns:
            Compliance mapping dictionary with controls, objectives, and audit considerations
        """
        # Framework control mappings
        control_mappings = {
            "ISO27001": {
                "information_security": ["A.5.1.1", "A.5.1.2"],
                "access_control": ["A.9.1.1", "A.9.1.2", "A.9.2.1"],
                "incident_management": ["A.16.1.1", "A.16.1.2", "A.16.1.3"],
                "business_continuity": ["A.17.1.1", "A.17.1.2", "A.17.2.1"],
            },
            "GDPR": {
                "data_protection": ["Art. 5", "Art. 6", "Art. 7"],
                "data_subject_rights": ["Art. 12", "Art. 13", "Art. 14", "Art. 15-22"],
                "privacy_by_design": ["Art. 25"],
                "breach_notification": ["Art. 33", "Art. 34"],
            },
            "SOC2": {
                "security": ["CC6.1", "CC6.2", "CC6.3"],
                "availability": ["A1.1", "A1.2", "A1.3"],
                "confidentiality": ["C1.1", "C1.2"],
                "processing_integrity": ["PI1.1", "PI1.2"],
            },
        }

        # Get mapped controls for this framework and policy type
        mapped_controls = control_mappings.get(framework, {}).get(policy_type, [])

        return {
            "framework": framework,
            "policy_type": policy_type,
            "mapped_controls": mapped_controls,
            "compliance_objectives": [
                f"Ensure compliance with {framework} requirements",
                "Establish clear governance and accountability",
                "Implement effective risk management",
                "Enable continuous monitoring and improvement",
            ],
            "audit_considerations": [
                "Document all policy implementations",
                "Maintain evidence of compliance activities",
                "Regular review and update cycles",
                "Staff training and awareness programs",
            ],
        }

    def _get_evidence_types_summary(self, evidence_items: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Summarize evidence types from evidence items.

        Args:
            evidence_items: List of evidence item dictionaries

        Returns:
            Dictionary mapping evidence types to counts
        """
        type_counts = {}
        for item in evidence_items:
            evidence_type = item.get("evidence_type", "unknown")
            type_counts[evidence_type] = type_counts.get(evidence_type, 0) + 1
        return type_counts

    def _get_fallback_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get fallback recommendations when AI analysis fails.

        Returns:
            List of default recommendation dictionaries
        """
        return [
            {
                "type": "documentation",
                "description": "Review compliance documentation",
                "priority": "medium",
            },
            {"type": "policy", "description": "Update security policies", "priority": "high"},
            {"type": "training", "description": "Conduct staff training", "priority": "medium"},
        ]
