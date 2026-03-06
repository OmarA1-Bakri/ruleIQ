"""
Response Parser

Handles parsing AI responses into structured formats.
Migrated from legacy ComplianceAssistant implementation.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResponseParser:
    """Parses AI responses into structured data."""

    @staticmethod
    def parse_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Parse a JSON string, stripping markdown code fences if present.

        Args:
            text: Text that may contain JSON, optionally inside ```json fences.

        Returns:
            Parsed dict/list, or None on failure.
        """
        if text is None:
            return None

        cleaned = text.strip()

        # Strip markdown json code fences
        if cleaned.startswith("```"):
            # Remove opening fence line
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1 :]
            # Remove closing fence
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3].rstrip()

        # Try direct JSON parse
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass

        # Try to find JSON object or array in text
        for pattern in [r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", r"\[.*\]"]:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except (json.JSONDecodeError, ValueError):
                    continue

        return None

    @staticmethod
    def parse_recommendations(response: str, framework: str) -> List[Dict[str, Any]]:
        """
        Parse recommendations from AI response.
        Migrated from _parse_ai_recommendations in legacy assistant.

        Args:
            response: AI response text
            framework: Framework identifier

        Returns:
            List of recommendation dictionaries
        """
        # Try JSON parsing first
        try:
            if response.strip().startswith("{") or response.strip().startswith("["):
                parsed = json.loads(response)
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict) and "recommendations" in parsed:
                    return parsed["recommendations"]
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        json_match = re.search(r"```json\s*(\{.*?\}|\[.*?\])\s*```", response, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict) and "recommendations" in parsed:
                    return parsed["recommendations"]
            except json.JSONDecodeError:
                pass

        # Fallback to text parsing
        return ResponseParser._parse_text_recommendations(response, framework)

    @staticmethod
    def _parse_text_recommendations(response: str, framework: str) -> List[Dict[str, Any]]:
        """Parse recommendations from plain text format."""
        recommendations = []
        lines = response.split("\n")
        current_rec = None

        for line in lines:
            line = line.strip()
            # Check for bullet points or numbered lists
            if (
                line.startswith("- ")
                or line.startswith("* ")
                or line.startswith("1.")
                or line.startswith("2.")
                or line.startswith("3.")
            ):
                if current_rec:
                    recommendations.append(current_rec)
                title = re.sub(r"^[-*\d\.]\s*", "", line)
                current_rec = {
                    "id": f"rec_{len(recommendations) + 1}",
                    "title": title,
                    "description": title,
                    "priority": "medium",
                    "effort_estimate": "2-4 weeks",
                    "impact_score": 0.7,
                    "implementation_steps": [title],
                }
            elif current_rec and line and not line.startswith("#"):
                current_rec["description"] += f" {line}"

        if current_rec:
            recommendations.append(current_rec)

        return recommendations[:5] if recommendations else []

    @staticmethod
    def parse_policy(response: str, framework: str, policy_type: str) -> Dict[str, Any]:
        """
        Parse policy from AI response.
        Migrated from _parse_policy_response in legacy assistant.

        Args:
            response: AI response text
            framework: Framework identifier
            policy_type: Type of policy

        Returns:
            Policy dictionary
        """
        # Try JSON parsing
        try:
            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Fallback to text parsing
        return ResponseParser._parse_text_policy(response, framework, policy_type)

    @staticmethod
    def _parse_text_policy(response: str, framework: str, policy_type: str) -> Dict[str, Any]:
        """Parse policy from plain text format."""
        return {
            "title": f"{policy_type.title()} Policy for {framework}",
            "framework": framework,
            "policy_type": policy_type,
            "content": response,
            "sections": ResponseParser._extract_sections(response),
            "metadata": {"framework": framework, "policy_type": policy_type, "generated": True},
        }

    @staticmethod
    def _extract_sections(text: str) -> List[Dict[str, Any]]:
        """Extract sections from text based on markdown headers."""
        sections = []
        current_section = None
        lines = text.split("\n")

        for line in lines:
            if line.startswith("## ") or line.startswith("# "):
                if current_section:
                    sections.append(current_section)
                current_section = {"title": line.lstrip("#").strip(), "content": ""}
            elif current_section:
                current_section["content"] += line + "\n"

        if current_section:
            sections.append(current_section)

        return sections if sections else [{"title": "Policy Content", "content": text}]

    @staticmethod
    def parse_assessment_help(response: str) -> Dict[str, Any]:
        """
        Parse assessment help response.
        Migrated from _parse_assessment_help_response in legacy assistant.
        """
        try:
            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Fallback structure matching legacy behavior
        return {
            "guidance": response,
            "confidence_score": 0.8,
            "related_topics": [],
            "follow_up_suggestions": [],
            "source_references": [],
        }

    @staticmethod
    def parse_assessment_followup(response: str) -> Dict[str, Any]:
        """
        Parse follow-up questions.
        Migrated from _parse_assessment_followup_response in legacy assistant.
        """
        try:
            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Fallback structure matching legacy behavior
        return {"follow_up_questions": [response], "recommendations": [], "confidence_score": 0.8}

    @staticmethod
    def parse_assessment_analysis(response: str) -> Dict[str, Any]:
        """
        Parse assessment analysis results.
        Migrated from _parse_assessment_analysis_response in legacy assistant.
        """
        try:
            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Fallback structure matching legacy behavior
        return {
            "gaps": [],
            "recommendations": [],
            "risk_assessment": {"level": "medium", "description": response},
            "compliance_insights": {"summary": response},
            "evidence_requirements": [],
        }

    @staticmethod
    def parse_assessment_recommendations(response: str) -> Dict[str, Any]:
        """
        Parse personalized recommendations.
        Migrated from _parse_assessment_recommendations_response in legacy assistant.
        """
        # Try direct JSON parsing
        try:
            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting from JSON code blocks
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                if "recommendations" in parsed:
                    logger.info(
                        f"Successfully extracted {len(parsed['recommendations'])} recommendations from JSON"
                    )
                    return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to extract JSON: {e}")

        # Try finding any JSON object in the response
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Parse as text with bullet points
        logger.info(f"Parsing text response for recommendations: {response[:200]}...")
        recommendations = []
        lines = response.split("\n")
        current_rec = None

        for line in lines:
            line = line.strip()
            if (
                line.startswith("- ")
                or line.startswith("* ")
                or line.startswith("1.")
                or line.startswith("2.")
                or line.startswith("3.")
            ):
                if current_rec:
                    recommendations.append(current_rec)
                title = re.sub(r"^[-*\d\.]\s*", "", line)
                current_rec = {
                    "id": f"rec_{len(recommendations) + 1}",
                    "title": title,
                    "description": title,
                    "priority": "medium",
                    "effort_estimate": "2-4 weeks",
                    "impact_score": 0.7,
                    "implementation_steps": [title],
                }
            elif current_rec and line and not line.startswith("#"):
                current_rec["description"] += f" {line}"

        if current_rec:
            recommendations.append(current_rec)

        # Default fallback if no recommendations found
        if not recommendations and response.strip():
            recommendations.append(
                {
                    "id": "rec_1",
                    "title": "Review Compliance Requirements",
                    "description": "Please review the compliance requirements for your organization.",
                    "priority": "medium",
                    "effort_estimate": "1-2 weeks",
                    "impact_score": 0.6,
                    "resources": ["Compliance team"],
                    "implementation_steps": ["Review the provided guidance"],
                }
            )

        return {
            "recommendations": recommendations[:5],
            "implementation_plan": {
                "phases": [
                    {
                        "phase_number": 1,
                        "phase_name": "Initial Implementation",
                        "tasks": recommendations[:3],
                    }
                ],
                "total_effort_estimate": "4-8 weeks",
                "priority_order": [rec["id"] for rec in recommendations[:5]],
            },
            "metadata": {"parsed_from": "text", "confidence_score": 0.7},
        }

    @staticmethod
    def parse_workflow(response: str, framework: str = "", control_id: str = "") -> Dict[str, Any]:
        """
        Parse workflow structure.
        Migrated from _parse_workflow_response in legacy assistant.
        """
        # Try JSON parsing
        try:
            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Fallback to text parsing
        return ResponseParser._parse_text_workflow(response, framework, control_id)

    @staticmethod
    def _parse_text_workflow(response: str, framework: str, control_id: str) -> Dict[str, Any]:
        """Parse workflow from plain text format."""
        phases = []
        lines = response.split("\n")
        current_phase = None

        for line in lines:
            line = line.strip()
            if line.startswith("## ") or (line.startswith("# ") and "Phase" in line):
                if current_phase:
                    phases.append(current_phase)
                current_phase = {"name": line.lstrip("#").strip(), "tasks": [], "description": ""}
            elif current_phase and (line.startswith("- ") or line.startswith("* ")):
                task = line.lstrip("-* ").strip()
                current_phase["tasks"].append({"task": task, "status": "pending"})
            elif current_phase and line:
                current_phase["description"] += line + " "

        if current_phase:
            phases.append(current_phase)

        return {
            "workflow_name": f"Evidence Collection Workflow for {framework}",
            "framework": framework,
            "control_id": control_id,
            "phases": phases
            if phases
            else [
                {
                    "name": "Implementation",
                    "tasks": [{"task": response, "status": "pending"}],
                    "description": "Workflow implementation",
                }
            ],
            "estimated_duration": "4-8 weeks",
            "metadata": {"framework": framework, "control_id": control_id, "generated": True},
        }

    @staticmethod
    def extract_json(text: str) -> Optional[Any]:
        """
        Extract JSON from text.

        Args:
            text: Text containing JSON

        Returns:
            Parsed JSON or None
        """
        # Try direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in text
        # Look for {...} or [...]
        json_patterns = [
            r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",  # Nested objects
            r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]",  # Nested arrays
        ]

        for pattern in json_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    continue

        return None

    @staticmethod
    def parse_text_fallback(text: str, response_type: str) -> Any:
        """
        Generic text parsing fallback.

        Args:
            text: Response text
            response_type: Type of response

        Returns:
            Best-effort structured response
        """
        if response_type == "recommendations":
            # Parse as list of recommendations
            lines = text.split("\n")
            recommendations = []

            for line in lines:
                line = line.strip()
                if line and (line.startswith("-") or line.startswith("•") or line[0].isdigit()):
                    recommendations.append(
                        {
                            "title": line.lstrip("-•0123456789. "),
                            "description": "",
                            "priority": "Medium",
                            "effort_hours": 4,
                        }
                    )

            return recommendations if recommendations else []

        elif response_type == "policy":
            return {
                "title": "Generated Policy",
                "sections": [{"title": "Content", "content": text}],
                "roles": [],
                "procedures": [],
            }

        else:
            return {"content": text}

    @staticmethod
    def validate_structure(data: Dict, required_fields: List[str]) -> bool:
        """
        Validate that data contains required fields.

        Args:
            data: Data dictionary
            required_fields: List of required field names

        Returns:
            True if valid, False otherwise
        """
        missing = [field for field in required_fields if field not in data]

        if missing:
            logger.warning(f"Missing required fields: {missing}")
            return False

        return True
