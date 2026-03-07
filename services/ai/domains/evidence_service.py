"""
Evidence Service

Handles evidence recommendations and analysis with full AI integration.
Ported from legacy ComplianceAssistant implementation.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from core.exceptions import (
    BusinessLogicException,
    DatabaseException,
    IntegrationException,
    NotFoundException,
)
from database.user import User
from services.ai.response.generator import ResponseGenerator
from services.ai.response.parser import ResponseParser
from services.ai.response.fallback import FallbackGenerator
from services.ai.context_manager import ContextManager
from services.ai.prompt_templates import PromptTemplates
from uuid import uuid4 as generate_uuid

logger = logging.getLogger(__name__)


class EvidenceService:
    """Handles evidence recommendation operations with full AI integration."""

    def __init__(
        self,
        response_generator: ResponseGenerator,
        response_parser: ResponseParser,
        fallback_generator: FallbackGenerator,
        context_manager: ContextManager,
        workflow_service: Optional[Any] = None,  # Optional, for maturity analysis
        compliance_service: Optional[Any] = None,  # Optional, for gap analysis
    ) -> None:
        """Initialize the evidence service."""
        self.response_generator = response_generator
        self.response_parser = response_parser
        self.fallback_generator = fallback_generator
        self.context_manager = context_manager
        self.prompt_templates = PromptTemplates()
        self.workflow_service = workflow_service
        self.compliance_service = compliance_service

    async def get_recommendations(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        control_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate evidence collection recommendations based on business context.

        This is the simple version that generates basic recommendations.
        For enhanced context-aware recommendations, this will be extended.

        Args:
            user: User object
            business_profile_id: Business profile ID
            framework: Framework identifier (e.g., 'GDPR', 'ISO27001')
            control_id: Optional control ID (currently unused, for API compatibility)

        Returns:
            List of recommendation dictionaries

        Raises:
            NotFoundException: If business profile not found
            DatabaseException: If database error occurs
            IntegrationException: If external service fails
            BusinessLogicException: For other unexpected errors
        """
        try:
            # Get business context from context manager
            context = await self.context_manager.get_conversation_context(
                uuid4(), business_profile_id
            )
            business_context = context.get("business_profile", {})

            # Build prompt using prompt templates
            prompt = self.prompt_templates.get_evidence_recommendation_prompt(
                framework, business_context
            )

            # Generate AI response
            response = await self.response_generator.generate_simple(
                system_prompt="You are a compliance expert specializing in evidence collection.",
                user_prompt=prompt,
                task_type="evidence_recommendations",
                context={"framework": framework, "business_context": business_context},
            )

            # Return recommendations in expected format
            return [
                {
                    "framework": framework,
                    "recommendations": response,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            ]

        except (NotFoundException, DatabaseException, IntegrationException) as e:
            logger.warning(
                f"Known exception while generating recommendations for business {business_profile_id}: {e}"
            )
            raise

        except Exception as e:
            logger.error(
                f"Error generating evidence recommendations for business {business_profile_id}: {e}",
                exc_info=True,
            )
            raise BusinessLogicException(
                "An unexpected error occurred while generating recommendations."
            ) from e

    def _summarize_evidence_types(self, existing_evidence: List[Dict]) -> str:
        """Summarize existing evidence types for context."""
        if not existing_evidence:
            return "No evidence collected yet"

        type_counts = {}
        for item in existing_evidence:
            evidence_type = item.get("evidence_type", "unknown")
            type_counts[evidence_type] = type_counts.get(evidence_type, 0) + 1

        summary = []
        for evidence_type, count in sorted(type_counts.items()):
            summary.append(f"- {evidence_type}: {count} items")

        return "\n".join(summary)

    def _parse_ai_recommendations(self, response: str, framework: str) -> List[Dict[str, Any]]:
        """Parse AI response into structured recommendations."""
        try:
            import json
            import re

            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                recommendations = json.loads(json_match.group())
                return recommendations

            return self._parse_text_recommendations(response, framework)

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Error parsing AI recommendations: {e}")
            return self.fallback_generator.get_recommendations(
                framework, {"maturity_level": "Basic"}
            )

    def _parse_text_recommendations(self, response: str, framework: str) -> List[Dict[str, Any]]:
        """Parse text-based recommendations as fallback."""
        recommendations = []
        lines = response.split("\n")
        current_rec = {}

        for line in lines:
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                if current_rec:
                    recommendations.append(current_rec)

                current_rec = {
                    "control_id": f"{framework}-{len(recommendations) + 1}",
                    "title": line[2:],
                    "description": line[2:],
                    "priority": "Medium",
                    "effort_hours": 4,
                    "automation_possible": False,
                    "business_justification": "Important for compliance",
                    "implementation_steps": [line[2:]],
                }

        if current_rec:
            recommendations.append(current_rec)

        return recommendations[:10]

    def _build_contextual_recommendation_prompt(
        self,
        business_context: Dict[str, Any],
        existing_evidence: List[Dict],
        maturity_analysis: Dict[str, Any],
        gaps_analysis: Dict[str, Any],
        framework: str,
    ) -> Dict[str, str]:
        """Build a comprehensive prompt for contextual recommendations."""
        system_prompt = f"""You are an expert compliance consultant specializing in {framework}.
        Generate intelligent, context-aware evidence collection recommendations based on the organization's
        specific situation, maturity level, and existing compliance posture.

        Focus on:
        1. Practical, actionable recommendations
        2. Prioritization based on risk and business impact
        3. Consideration of organizational capacity and maturity
        4. Industry-specific requirements and best practices
        5. Automation opportunities where applicable

        Return recommendations as a JSON array with this structure:
        [{{
            "control_id": "AC-1",
            "title": "Access Control Policy",
            "description": "Specific action to take",
            "priority": "High|Medium|Low",
            "effort_hours": 8,
            "automation_possible": true,
            "business_justification": "Why this is important for this organization",
            "implementation_steps": ["Step 1", "Step 2", "Step 3"]
        }}]"""

        user_prompt = f"""
        Organization Profile:
        - Company: {business_context.get("company_name", "Unknown")}
        - Industry: {business_context.get("industry", "Unknown")}
        - Size: {business_context.get("employee_count", 0)} employees
        - Maturity Level: {maturity_analysis.get("maturity_level", "Basic")}
        - Maturity Score: {maturity_analysis.get("maturity_score", 40)}/100

        Current Compliance Status:
        - Framework: {framework}
        - Completion: {gaps_analysis.get("completion_percentage", 0)}%
        - Evidence Items: {len(existing_evidence)}
        - Critical Gaps: {len(gaps_analysis.get("critical_gaps", []))}

        Existing Evidence Types:
        {self._summarize_evidence_types(existing_evidence)}

        Critical Gaps Identified:
        {gaps_analysis.get("critical_gaps", [])}

        Generate 8-12 prioritized recommendations that address the most critical gaps while
        considering the organization's maturity level and capacity for implementation.
        """

        return {"system": system_prompt, "user": user_prompt}

    async def _generate_contextual_recommendations(
        self,
        business_context: Dict[str, Any],
        existing_evidence: List[Dict],
        maturity_analysis: Dict[str, Any],
        gaps_analysis: Dict[str, Any],
        framework: str,
    ) -> List[Dict[str, Any]]:
        """Generate intelligent recommendations based on comprehensive context analysis."""
        try:
            prompt_dict = self._build_contextual_recommendation_prompt(
                business_context, existing_evidence, maturity_analysis, gaps_analysis, framework
            )

            # Generate AI response using response generator
            response = await self.response_generator.generate_simple(
                system_prompt=prompt_dict["system"],
                user_prompt=prompt_dict["user"],
                task_type="contextual_recommendations",
                context={
                    "framework": framework,
                    "business_context": business_context,
                    "maturity_analysis": maturity_analysis,
                },
            )

            recommendations = self._parse_ai_recommendations(response, framework)
            enhanced_recommendations = self._add_automation_insights(
                recommendations, business_context
            )

            return enhanced_recommendations

        except (ValueError, KeyError, IndexError) as e:
            logger.error(f"Error generating contextual recommendations: {e}")
            return self.fallback_generator.get_recommendations(framework, maturity_analysis)

    def _add_automation_insights(
        self, recommendations: List[Dict[str, Any]], business_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Add automation insights to recommendations based on business context."""
        automation_map = {
            "policy": True,
            "procedure": True,
            "log_analysis": True,
            "system_configuration": True,
            "access_review": True,
            "vulnerability_scan": True,
            "backup_verification": True,
            "training_record": False,
            "physical_security": False,
            "vendor_assessment": False,
        }

        enhanced_recommendations = []
        for rec in recommendations:
            control_type = rec.get("title", "").lower()

            automation_possible = any(
                auto_type in control_type
                for auto_type in automation_map
                if automation_map[auto_type]
            )

            rec["automation_possible"] = automation_possible

            if automation_possible:
                rec["automation_guidance"] = self._get_automation_guidance(rec, business_context)

            enhanced_recommendations.append(rec)

        return enhanced_recommendations

    def _get_automation_guidance(
        self, recommendation: Dict[str, Any], business_context: Dict[str, Any]
    ) -> str:
        """Provide specific automation guidance for a recommendation."""
        control_type = recommendation.get("title", "").lower()
        org_size = self._categorize_organization_size(business_context.get("employee_count", 0))

        if "policy" in control_type:
            return f"Use policy templates and automated policy management tools. For {org_size} organizations, consider document management systems with version control."
        elif "log" in control_type:
            return f"Implement SIEM or log management solutions. For {org_size} organizations, consider cloud-based logging services."
        elif "access" in control_type:
            return f"Use identity management systems with automated access reviews. For {org_size} organizations, consider cloud IAM solutions."
        elif "vulnerability" in control_type:
            return f"Deploy automated vulnerability scanning tools. For {org_size} organizations, consider managed security services."
        else:
            return "Consider workflow automation tools and integration platforms to streamline this process."

    def _categorize_organization_size(self, employee_count: int) -> str:
        """Categorize organization size based on employee count."""
        if employee_count < 50:
            return "small"
        elif employee_count < 250:
            return "medium"
        else:
            return "large"

    def _prioritize_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Prioritize recommendations based on business context and maturity."""

        def calculate_priority_score(rec: Dict[str, Any]) -> float:
            score = 0.0

            # Base priority
            priority_scores = {"High": 3.0, "Medium": 2.0, "Low": 1.0}
            score += priority_scores.get(rec.get("priority", "Medium"), 2.0)

            # Maturity-based weighting
            maturity_level = maturity_analysis.get("maturity_level", "Basic")
            if maturity_level == "Initial":
                if any(
                    keyword in rec.get("title", "").lower()
                    for keyword in ["policy", "procedure", "training"]
                ):
                    score += 1.0
            elif maturity_level == "Advanced":
                if any(
                    keyword in rec.get("title", "").lower()
                    for keyword in ["monitoring", "automation", "integration"]
                ):
                    score += 1.0

            # Industry-specific weighting
            industry = business_context.get("industry", "").lower()
            if industry in ["healthcare", "finance"]:
                if any(
                    keyword in rec.get("title", "").lower()
                    for keyword in ["access", "encryption", "audit"]
                ):
                    score += 0.5

            # Automation bonus
            if rec.get("automation_possible", False):
                score += 0.3

            # Effort-based adjustment
            effort_hours = rec.get("effort_hours", 4)
            if effort_hours <= 2:
                score += 0.2
            elif effort_hours >= 16:
                score -= 0.2

            return score

        for rec in recommendations:
            rec["priority_score"] = calculate_priority_score(rec)

        return sorted(recommendations, key=lambda x: x.get("priority_score", 0), reverse=True)

    def _generate_next_steps(self, top_recommendations: List[Dict[str, Any]]) -> List[str]:
        """Generate actionable next steps from top recommendations."""
        next_steps = []

        for i, rec in enumerate(top_recommendations[:3], 1):
            title = rec.get("title", "Unknown")
            effort = rec.get("effort_hours", 4)

            if rec.get("automation_possible", False):
                step = f"{i}. Start with {title} (Est. {effort}h) - Consider automation tools"
            else:
                step = f"{i}. Implement {title} (Est. {effort}h) - Manual process required"

            next_steps.append(step)

        return next_steps

    def _calculate_total_effort(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate total effort estimates for recommendations."""
        total_hours = sum(rec.get("effort_hours", 4) for rec in recommendations)
        high_priority_hours = sum(
            rec.get("effort_hours", 4) for rec in recommendations if rec.get("priority") == "High"
        )

        return {
            "total_hours": total_hours,
            "high_priority_hours": high_priority_hours,
            "estimated_weeks": round(total_hours / 40, 1),
            "quick_wins": len([r for r in recommendations if r.get("effort_hours", 4) <= 2]),
        }

    async def get_context_aware_recommendations(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        context_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """
        Enhanced context-aware evidence recommendations that consider:
        - Business profile and industry specifics
        - Existing evidence and gaps
        - User behavior patterns
        - Compliance maturity level
        - Risk assessment
        """
        try:
            # Get business context
            context = await self.context_manager.get_conversation_context(
                generate_uuid(), business_profile_id
            )
            business_context = context.get("business_profile", {})
            existing_evidence = context.get("recent_evidence", [])

            # Analyze compliance maturity (from WorkflowService)
            if self.workflow_service:
                maturity_analysis = await self.workflow_service._analyze_compliance_maturity(
                    business_context, existing_evidence, framework
                )
            else:
                # Fallback maturity analysis
                maturity_analysis = {"maturity_level": "Basic", "maturity_score": 40}

            # Analyze evidence gaps (from ComplianceService)
            if self.compliance_service:
                gaps_analysis = await self.compliance_service.analyze_evidence_gap(
                    business_profile_id, framework
                )
            else:
                # Fallback gaps analysis
                gaps_analysis = {"completion_percentage": 0, "critical_gaps": []}

            # Generate contextual recommendations
            recommendations = await self._generate_contextual_recommendations(
                business_context, existing_evidence, maturity_analysis, gaps_analysis, framework
            )

            # Prioritize recommendations
            prioritized_recommendations = self._prioritize_recommendations(
                recommendations, business_context, maturity_analysis
            )

            return {
                "framework": framework,
                "business_context": {
                    "company_name": business_context.get("company_name", "Unknown"),
                    "industry": business_context.get("industry", "Unknown"),
                    "employee_count": business_context.get("employee_count", 0),
                    "maturity_level": maturity_analysis.get("maturity_level", "Basic"),
                },
                "current_status": {
                    "completion_percentage": gaps_analysis.get("completion_percentage", 0),
                    "evidence_collected": len(existing_evidence),
                    "critical_gaps_count": len(gaps_analysis.get("critical_gaps", [])),
                },
                "recommendations": prioritized_recommendations,
                "next_steps": self._generate_next_steps(prioritized_recommendations[:3]),
                "estimated_effort": self._calculate_total_effort(prioritized_recommendations),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except (NotFoundException, DatabaseException, IntegrationException) as e:
            logger.warning(
                f"Known exception while generating context-aware recommendations for business {business_profile_id}: {e}"
            )
            raise

        except Exception as e:
            logger.error(
                f"Error generating context-aware recommendations for business {business_profile_id}: {e}",
                exc_info=True,
            )
            raise BusinessLogicException("Unable to generate context-aware recommendations") from e
