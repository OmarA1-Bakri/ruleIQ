"""
Workflow Service

Handles evidence collection workflow generation with full AI-powered logic.
Ported from legacy ComplianceAssistant implementation.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from database.user import User
from services.ai.response.generator import ResponseGenerator
from services.ai.response.parser import ResponseParser
from services.ai.response.fallback import FallbackGenerator
from services.ai.context_manager import ContextManager

logger = logging.getLogger(__name__)


class WorkflowService:
    """Handles workflow generation operations with full AI integration."""

    def __init__(
        self,
        response_generator: ResponseGenerator,
        response_parser: ResponseParser,
        fallback_generator: FallbackGenerator,
        context_manager: ContextManager,
    ) -> None:
        """Initialize the workflow service."""
        self.response_generator = response_generator
        self.response_parser = response_parser
        self.fallback_generator = fallback_generator
        self.context_manager = context_manager

    async def generate_workflow(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        control_id: Optional[str] = None,
        workflow_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """
        Generate intelligent, step-by-step evidence collection workflows
        tailored to specific frameworks, controls, and business contexts.

        Args:
            user: User object
            business_profile_id: Business profile ID
            framework: Framework identifier (e.g., 'GDPR', 'ISO27001')
            control_id: Optional control ID for specific control workflows
            workflow_type: Type of workflow ('comprehensive', 'quick', 'detailed')

        Returns:
            Workflow dictionary with phases, steps, effort estimation
        """
        try:
            # Get business context and evidence
            context = await self.context_manager.get_conversation_context(
                uuid4(), business_profile_id
            )
            business_context = context.get("business_profile", {})
            existing_evidence = context.get("recent_evidence", [])

            # Analyze compliance maturity
            maturity_analysis = await self._analyze_compliance_maturity(
                business_context, existing_evidence, framework
            )

            # Generate AI-powered contextual workflow
            workflow = await self._generate_contextual_workflow(
                framework, control_id, business_context, maturity_analysis, workflow_type
            )

            # Enhance with automation recommendations
            workflow = self._enhance_workflow_with_automation(workflow, business_context)

            # Calculate effort estimation
            workflow["effort_estimation"] = self._calculate_workflow_effort(workflow)

            return workflow

        except Exception as e:
            logger.error(f"Error generating evidence collection workflow: {e}", exc_info=True)
            # Fallback to template-based workflow
            return self.fallback_generator.get_workflow(framework, control_id)

    async def _generate_contextual_workflow(
        self,
        framework: str,
        control_id: Optional[str],
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
        workflow_type: str,
    ) -> Dict[str, Any]:
        """Generate a contextual workflow using AI."""
        try:
            # Build comprehensive prompt
            prompt = self._build_workflow_generation_prompt(
                framework, control_id, business_context, maturity_analysis, workflow_type
            )

            # Generate AI response
            response = await self.response_generator.generate_simple(
                system_prompt=prompt["system"],
                user_prompt=prompt["user"],
                task_type="workflow_generation",
                context={
                    "framework": framework,
                    "control_id": control_id,
                    "business_context": business_context,
                },
            )

            # Parse workflow from response
            workflow = self._parse_workflow_response(response, framework, control_id)
            return workflow

        except Exception as e:
            logger.error(f"Error generating contextual workflow: {e}")
            return self._get_fallback_workflow(framework, control_id, maturity_analysis)

    def _build_workflow_generation_prompt(
        self,
        framework: str,
        control_id: Optional[str],
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
        workflow_type: str,
    ) -> Dict[str, str]:
        """Build comprehensive prompt for workflow generation."""
        system_prompt = f"""You are an expert compliance consultant specializing in {framework}.
Generate a detailed, step-by-step evidence collection workflow that is practical and
tailored to the organization's specific context and maturity level.

The workflow should include:
1. Clear, actionable steps in logical sequence
2. Specific deliverables and artifacts for each step
3. Role assignments and responsibilities
4. Time estimates and dependencies
5. Quality checkpoints and validation criteria
6. Tools and resources needed
7. Common pitfalls and how to avoid them

Return the workflow as JSON with this structure:
{{
    "workflow_id": "unique_id",
    "title": "Workflow Title",
    "description": "Brief description",
    "framework": "{framework}",
    "control_id": "{control_id or "general"}",
    "phases": [
        {{
            "phase_id": "phase_1",
            "title": "Phase Title",
            "description": "Phase description",
            "estimated_hours": 4,
            "steps": [
                {{
                    "step_id": "step_1",
                    "title": "Step Title",
                    "description": "Detailed step description",
                    "deliverables": ["Deliverable 1", "Deliverable 2"],
                    "responsible_role": "Role",
                    "estimated_hours": 2,
                    "dependencies": [],
                    "tools_needed": ["Tool 1"],
                    "validation_criteria": ["Criteria 1"]
                }}
            ]
        }}
    ]
}}"""

        control_context = f" for control {control_id}" if control_id else ""
        user_prompt = f"""
Generate a {workflow_type} evidence collection workflow for {framework}{control_context}.

Organization Context:
- Company: {business_context.get("company_name", "Unknown")}
- Industry: {business_context.get("industry", "Unknown")}
- Size: {business_context.get("employee_count", 0)} employees
- Maturity Level: {maturity_analysis.get("maturity_level", "Basic")}
- Organization Category: {maturity_analysis.get("size_category", "small")}

Requirements:
- Tailor the workflow to the organization's maturity level
- Consider industry-specific requirements
- Include both manual and automated approaches where applicable
- Provide realistic time estimates
- Include quality assurance checkpoints
- Consider resource constraints for {maturity_analysis.get("size_category", "small")} organizations

Generate a comprehensive workflow with 3-5 phases and 2-4 steps per phase.
"""

        return {"system": system_prompt, "user": user_prompt}

    def _parse_workflow_response(
        self, response: str, framework: str, control_id: Optional[str]
    ) -> Dict[str, Any]:
        """Parse AI workflow response into structured format."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                workflow = json.loads(json_match.group())
                workflow = self._validate_workflow_structure(workflow, framework, control_id)
                return workflow

            # Fallback to text parsing
            return self._parse_text_workflow(response, framework, control_id)

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Error parsing workflow response: {e}")
            return self._get_fallback_workflow(framework, control_id, {"maturity_level": "Basic"})

    def _validate_workflow_structure(
        self, workflow: Dict[str, Any], framework: str, control_id: Optional[str]
    ) -> Dict[str, Any]:
        """Validate and enhance workflow structure."""
        workflow.setdefault(
            "workflow_id", f"{framework}_{control_id or 'general'}_{uuid4().hex[:8]}"
        )
        workflow.setdefault("framework", framework)
        workflow.setdefault("control_id", control_id or "general")
        workflow.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        workflow.setdefault("phases", [])

        for i, phase in enumerate(workflow["phases"]):
            phase.setdefault("phase_id", f"phase_{i + 1}")
            phase.setdefault("estimated_hours", 4)
            phase.setdefault("steps", [])

            for j, step in enumerate(phase["steps"]):
                step.setdefault("step_id", f"step_{j + 1}")
                step.setdefault("estimated_hours", 2)
                step.setdefault("deliverables", [])
                step.setdefault("dependencies", [])
                step.setdefault("tools_needed", [])
                step.setdefault("validation_criteria", [])
                step.setdefault("responsible_role", "Compliance Team")

        return workflow

    def _parse_text_workflow(
        self, response: str, framework: str, control_id: Optional[str]
    ) -> Dict[str, Any]:
        """Parse text-based workflow as fallback."""
        workflow = {
            "workflow_id": f"{framework}_{control_id or 'general'}_{uuid4().hex[:8]}",
            "title": f"{framework} Evidence Collection Workflow",
            "description": f"Evidence collection workflow for {framework}",
            "framework": framework,
            "control_id": control_id or "general",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "phases": [],
        }

        lines = response.split("\n")
        current_phase = None

        for line in lines:
            line = line.strip()

            if line.startswith("Phase") or line.startswith("##"):
                if current_phase:
                    workflow["phases"].append(current_phase)
                current_phase = {
                    "phase_id": f"phase_{len(workflow['phases']) + 1}",
                    "title": line,
                    "description": line,
                    "estimated_hours": 8,
                    "steps": [],
                }

            elif line.startswith("Step") or line.startswith("-") or line.startswith("*"):
                if current_phase:
                    step = {
                        "step_id": f"step_{len(current_phase['steps']) + 1}",
                        "title": line,
                        "description": line,
                        "deliverables": [line],
                        "responsible_role": "Compliance Team",
                        "estimated_hours": 2,
                        "dependencies": [],
                        "tools_needed": [],
                        "validation_criteria": ["Complete deliverables"],
                    }
                    current_phase["steps"].append(step)

        if current_phase:
            workflow["phases"].append(current_phase)

        return workflow

    def _enhance_workflow_with_automation(
        self, workflow: Dict[str, Any], business_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance workflow with automation recommendations."""
        org_size = self._categorize_organization_size(business_context.get("employee_count", 0))
        industry = business_context.get("industry", "").lower()

        for phase in workflow.get("phases", []):
            for step in phase.get("steps", []):
                step["automation_opportunities"] = self._identify_step_automation(
                    step, org_size, industry
                )

                if step["automation_opportunities"].get("high_automation_potential", False):
                    step["estimated_hours_with_automation"] = max(
                        1, step.get("estimated_hours", 2) * 0.3
                    )
                else:
                    step["estimated_hours_with_automation"] = step.get("estimated_hours", 2)

        workflow["automation_summary"] = self._calculate_workflow_automation_potential(workflow)
        return workflow

    def _identify_step_automation(
        self, step: Dict[str, Any], org_size: str, industry: str
    ) -> Dict[str, Any]:
        """Identify automation opportunities for a workflow step."""
        step_title = step.get("title", "").lower()
        step_description = step.get("description", "").lower()

        automation_keywords = {
            "high": ["policy", "template", "scan", "monitor", "log", "report", "backup"],
            "medium": ["review", "assess", "document", "configure", "test"],
            "low": ["interview", "training", "meeting", "approval", "sign-off"],
        }

        automation_level = "low"
        for level, keywords in automation_keywords.items():
            if any(keyword in step_title or keyword in step_description for keyword in keywords):
                automation_level = level
                break

        # Upgrade automation level for larger organizations
        if org_size in ["enterprise", "medium"] and automation_level == "medium":
            automation_level = "high"

        automation_tools = self._suggest_automation_tools(step_title, org_size, industry)

        return {
            "automation_level": automation_level,
            "high_automation_potential": automation_level == "high",
            "suggested_tools": automation_tools,
            "effort_reduction_percentage": {"high": 70, "medium": 40, "low": 10}[automation_level],
        }

    def _suggest_automation_tools(self, step_title: str, org_size: str, industry: str) -> List[str]:
        """Suggest specific automation tools for a step."""
        tools = []
        step_lower = step_title.lower()

        if "policy" in step_lower:
            tools.extend(["Policy management platforms", "Document automation tools"])
        if "scan" in step_lower or "monitor" in step_lower:
            tools.extend(["Vulnerability scanners", "Security monitoring tools", "SIEM platforms"])
        if "log" in step_lower:
            tools.extend(["Log aggregation platforms", "Audit trail systems"])
        if "report" in step_lower:
            tools.extend(["BI tools", "Automated reporting platforms"])
        if "backup" in step_lower:
            tools.extend(["Backup automation tools", "Cloud backup services"])
        if "test" in step_lower:
            tools.extend(["Automated testing frameworks", "Security testing tools"])

        return tools[:3]  # Limit to top 3 suggestions

    def _calculate_workflow_automation_potential(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall automation potential for workflow."""
        total_steps = 0
        automatable_steps = 0
        total_hours = 0
        potential_savings_hours = 0

        for phase in workflow.get("phases", []):
            for step in phase.get("steps", []):
                total_steps += 1
                step_hours = step.get("estimated_hours", 2)
                total_hours += step_hours

                if step.get("automation_opportunities", {}).get("high_automation_potential"):
                    automatable_steps += 1
                    reduction = step["automation_opportunities"]["effort_reduction_percentage"]
                    potential_savings_hours += step_hours * (reduction / 100)

        return {
            "total_steps": total_steps,
            "automatable_steps": automatable_steps,
            "automation_percentage": (automatable_steps / total_steps * 100)
            if total_steps > 0
            else 0,
            "total_hours": total_hours,
            "potential_savings_hours": round(potential_savings_hours, 1),
            "potential_savings_percentage": round(
                (potential_savings_hours / total_hours * 100) if total_hours > 0 else 0, 1
            ),
        }

    def _calculate_workflow_effort(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate total effort estimation for workflow."""
        total_hours = 0
        by_phase = {}

        for phase in workflow.get("phases", []):
            phase_hours = 0
            for step in phase.get("steps", []):
                phase_hours += step.get("estimated_hours", 2)

            by_phase[phase.get("phase_id", "unknown")] = phase_hours
            total_hours += phase_hours

        return {
            "total_hours": total_hours,
            "total_days": round(total_hours / 8, 1),
            "by_phase": by_phase,
        }

    def _get_fallback_workflow(
        self, framework: str, control_id: Optional[str], maturity_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get fallback workflow when AI generation fails."""
        return self.fallback_generator.get_workflow(framework, control_id)

    async def _analyze_compliance_maturity(
        self, business_context: Dict[str, Any], existing_evidence: List[Dict], framework: str
    ) -> Dict[str, Any]:
        """Analyze the organization's compliance maturity level."""
        evidence_count = len(existing_evidence)
        evidence_types = len({item.get("evidence_type", "") for item in existing_evidence})
        industry = business_context.get("industry", "").lower()
        employee_count = business_context.get("employee_count", 0)

        # Determine maturity level based on evidence
        if evidence_count >= 50 and evidence_types >= 8:
            maturity_level = "Advanced"
            maturity_score = 85
        elif evidence_count >= 20 and evidence_types >= 5:
            maturity_level = "Intermediate"
            maturity_score = 65
        elif evidence_count >= 5 and evidence_types >= 3:
            maturity_level = "Basic"
            maturity_score = 40
        else:
            maturity_level = "Initial"
            maturity_score = 20

        # Adjust for industry
        if industry in ["healthcare", "finance", "government"]:
            maturity_score = min(maturity_score + 10, 100)
        elif industry in ["technology", "consulting"]:
            maturity_score = min(maturity_score + 5, 100)

        return {
            "maturity_level": maturity_level,
            "maturity_score": maturity_score,
            "evidence_count": evidence_count,
            "evidence_types_count": evidence_types,
            "size_category": self._categorize_organization_size(employee_count),
            "industry_category": industry,
        }

    def _categorize_organization_size(self, employee_count: int) -> str:
        """Categorize organization size based on employee count."""
        if employee_count >= 1000:
            return "enterprise"
        elif employee_count >= 250:
            return "medium"
        elif employee_count >= 50:
            return "small"
        else:
            return "micro"
