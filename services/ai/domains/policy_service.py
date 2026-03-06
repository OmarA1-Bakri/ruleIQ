"""
Policy Service

Handles AI-powered policy generation with business customization.
Ported from legacy ComplianceAssistant implementation.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from database.user import User
from services.ai.response.generator import ResponseGenerator
from services.ai.context_manager import ContextManager

logger = logging.getLogger(__name__)

# Compliance maturity thresholds
MATURITY_BASIC_THRESHOLD = 5
MATURITY_DEVELOPING_THRESHOLD = 15
MATURITY_MANAGED_THRESHOLD = 30

# Organization size thresholds (employee count)
ORG_SIZE_SMALL_THRESHOLD = 10
ORG_SIZE_MEDIUM_THRESHOLD = 50
ORG_SIZE_LARGE_THRESHOLD = 250


class PolicyService:
    """Handles policy generation operations."""

    def __init__(
        self, response_generator: ResponseGenerator, context_manager: ContextManager
    ) -> None:
        """Initialize the policy service."""
        self.response_generator = response_generator
        self.context_manager = context_manager

    async def generate_customized_policy(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        policy_type: str,
        customization_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate AI-powered, customized compliance policies.

        Generates policies based on:
        - Business profile and industry specifics
        - Framework requirements
        - Organizational size and maturity
        - Industry best practices
        - Regulatory requirements

        Args:
            user: User object
            business_profile_id: Business profile ID
            framework: Framework identifier (e.g., 'ISO27001', 'GDPR')
            policy_type: Type of policy (e.g., 'information_security')
            customization_options: Optional customization options

        Returns:
            Complete policy dictionary with sections, procedures, and guidance
        """
        try:
            # Get business context
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )

            business_context = context.get("business_profile", {})
            existing_evidence = context.get("recent_evidence", [])

            # Analyze compliance maturity
            maturity_analysis = self._analyze_compliance_maturity(
                business_context, existing_evidence, framework
            )

            # Generate contextual policy using AI
            policy = await self._generate_contextual_policy(
                framework,
                policy_type,
                business_context,
                maturity_analysis,
                customization_options or {},
            )

            # Add implementation guidance
            policy["implementation_guidance"] = self._generate_policy_implementation_guidance(
                policy, business_context, maturity_analysis
            )

            # Add compliance mapping
            policy["compliance_mapping"] = self._generate_compliance_mapping(
                policy, framework, policy_type
            )

            return policy

        except Exception as e:
            logger.error(f"Error generating customized policy: {e}", exc_info=True)
            return self._get_fallback_policy(framework, policy_type, {})

    async def _generate_contextual_policy(
        self,
        framework: str,
        policy_type: str,
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
        customization_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a contextual policy using AI."""
        try:
            # Build prompt
            prompt_data = self._build_policy_generation_prompt(
                framework, policy_type, business_context, maturity_analysis, customization_options
            )

            # Generate AI response
            response = await self.response_generator.generate_simple(
                system_prompt=prompt_data["system"],
                user_prompt=prompt_data["user"],
                task_type="policy_generation",
                context={
                    "framework": framework,
                    "policy_type": policy_type,
                    "business_context": business_context,
                },
            )

            # Parse and validate response
            policy = self._parse_policy_response(response, framework, policy_type)

            # Apply business customizations
            policy = self._apply_business_customizations(
                policy, business_context, customization_options
            )

            return policy

        except Exception as e:
            logger.error(f"Error generating contextual policy: {e}")
            return self._get_fallback_policy(framework, policy_type, business_context)

    def _build_policy_generation_prompt(
        self,
        framework: str,
        policy_type: str,
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
        customization_options: Dict[str, Any],
    ) -> Dict[str, str]:
        """Build comprehensive prompt for policy generation."""
        system_prompt = f"""You are an expert compliance consultant and policy writer \
specializing in {framework}.
Generate a comprehensive, business-specific {policy_type} policy that is:

1. Tailored to the organization's industry, size, and maturity level
2. Compliant with {framework} requirements
3. Practical and implementable
4. Written in clear, professional language
5. Includes specific procedures and controls
6. Addresses industry-specific risks and requirements

Return the policy as JSON with this structure:
{{
    "policy_id": "unique_id",
    "title": "Policy Title",
    "version": "1.0",
    "effective_date": "YYYY-MM-DD",
    "framework": "{framework}",
    "policy_type": "{policy_type}",
    "sections": [
        {{
            "section_id": "section_1",
            "title": "Section Title",
            "content": "Detailed section content",
            "subsections": [
                {{
                    "subsection_id": "subsection_1",
                    "title": "Subsection Title",
                    "content": "Detailed subsection content",
                    "controls": ["Control 1", "Control 2"]
                }}
            ]
        }}
    ],
    "roles_responsibilities": [
        {{
            "role": "Role Name",
            "responsibilities": ["Responsibility 1", "Responsibility 2"]
        }}
    ],
    "procedures": [
        {{
            "procedure_id": "proc_1",
            "title": "Procedure Title",
            "steps": ["Step 1", "Step 2", "Step 3"]
        }}
    ],
    "compliance_requirements": [
        {{
            "requirement_id": "req_1",
            "description": "Requirement description",
            "control_reference": "Control reference"
        }}
    ]
}}"""

        industry_context = business_context.get("industry", "Unknown")
        company_size = self._categorize_organization_size(business_context.get("employee_count", 0))

        user_prompt = f"""
Generate a {policy_type} policy for {framework} compliance.

Organization Profile:
- Company: {business_context.get("company_name", "Organization")}
- Industry: {industry_context}
- Size: {business_context.get("employee_count", 0)} employees ({company_size} organization)
- Maturity Level: {maturity_analysis.get("maturity_level", "Basic")}
- Geographic Scope: {customization_options.get("geographic_scope", "Single location")}

Customization Requirements:
- Tone: {customization_options.get("tone", "Professional")}
- Detail Level: {customization_options.get("detail_level", "Standard")}
- Include Templates: {customization_options.get("include_templates", True)}
- Industry Focus: {customization_options.get("industry_focus", industry_context)}

Special Considerations:
- Address {industry_context}-specific risks and requirements
- Consider {company_size} organization constraints and capabilities
- Align with {maturity_analysis.get("maturity_level", "Basic")} maturity level
- Include practical implementation guidance
- Ensure regulatory compliance for {framework}

Generate a comprehensive policy with 5-8 main sections, detailed procedures,
and clear roles and responsibilities.
"""

        return {"system": system_prompt, "user": user_prompt}

    def _parse_policy_response(
        self, response: str, framework: str, policy_type: str
    ) -> Dict[str, Any]:
        """Parse AI policy response into structured format."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                policy = json.loads(json_match.group())
                policy = self._validate_policy_structure(policy, framework, policy_type)
                return policy

            # Fallback to text parsing
            return self._parse_text_policy(response, framework, policy_type)

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Error parsing policy response: {e}")
            return self._get_fallback_policy(framework, policy_type, {})

    def _validate_policy_structure(
        self, policy: Dict[str, Any], framework: str, policy_type: str
    ) -> Dict[str, Any]:
        """Validate and enhance policy structure."""
        policy.setdefault("policy_id", f"{framework}_{policy_type}_{uuid4().hex[:8]}")
        policy.setdefault("title", f"{policy_type.replace('_', ' ').title()} Policy")
        policy.setdefault("version", "1.0")
        policy.setdefault("effective_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        policy.setdefault("framework", framework)
        policy.setdefault("policy_type", policy_type)
        policy.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        policy.setdefault("sections", [])
        policy.setdefault("roles_responsibilities", [])
        policy.setdefault("procedures", [])
        policy.setdefault("compliance_requirements", [])

        # Validate sections structure
        for i, section in enumerate(policy["sections"]):
            section.setdefault("section_id", f"section_{i + 1}")
            section.setdefault("subsections", [])
            for j, subsection in enumerate(section.get("subsections", [])):
                subsection.setdefault("subsection_id", f"subsection_{j + 1}")
                subsection.setdefault("controls", [])

        return policy

    def _parse_text_policy(self, response: str, framework: str, policy_type: str) -> Dict[str, Any]:
        """Parse text-based policy as fallback."""
        policy = {
            "policy_id": f"{framework}_{policy_type}_{uuid4().hex[:8]}",
            "title": f"{policy_type.replace('_', ' ').title()} Policy",
            "version": "1.0",
            "effective_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "framework": framework,
            "policy_type": policy_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sections": [],
            "roles_responsibilities": [],
            "procedures": [],
            "compliance_requirements": [],
        }

        # Parse text into sections
        lines = response.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if line.startswith("#") or line.startswith("Section"):
                if current_section:
                    policy["sections"].append(current_section)
                current_section = {
                    "section_id": f"section_{len(policy['sections']) + 1}",
                    "title": line.replace("#", "").strip(),
                    "content": "",
                    "subsections": [],
                }
            elif current_section and line:
                current_section["content"] += line + "\n"

        if current_section:
            policy["sections"].append(current_section)

        return policy

    def _generate_policy_implementation_guidance(
        self,
        policy: Dict[str, Any],
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate implementation guidance for the policy."""
        org_size = self._categorize_organization_size(business_context.get("employee_count", 0))

        # Determine timeline based on org size
        foundation_weeks = 2 if org_size in ["micro", "small"] else 4
        implementation_weeks = 4 if org_size in ["micro", "small"] else 8
        validation_weeks = 2 if org_size in ["micro", "small"] else 4

        return {
            "implementation_phases": [
                {
                    "phase": "Phase 1: Foundation",
                    "duration_weeks": foundation_weeks,
                    "activities": [
                        "Review and approve policy",
                        "Identify key stakeholders",
                        "Establish governance structure",
                    ],
                },
                {
                    "phase": "Phase 2: Implementation",
                    "duration_weeks": implementation_weeks,
                    "activities": [
                        "Deploy controls and procedures",
                        "Train staff on new requirements",
                        "Implement monitoring systems",
                    ],
                },
                {
                    "phase": "Phase 3: Validation",
                    "duration_weeks": validation_weeks,
                    "activities": [
                        "Test controls effectiveness",
                        "Conduct internal audit",
                        "Address any gaps identified",
                    ],
                },
            ],
            "success_metrics": [
                "Policy approval and communication completion",
                "Staff training completion rate > 95%",
                "Control implementation rate > 90%",
                "Audit findings resolution rate > 95%",
            ],
            "common_challenges": [
                "Resource constraints",
                "Staff resistance to change",
                "Technical implementation complexity",
                "Ongoing maintenance requirements",
            ],
            "mitigation_strategies": [
                "Phased implementation approach",
                "Regular communication and training",
                "Automation where possible",
                "Regular review and updates",
            ],
        }

    def _generate_compliance_mapping(
        self, policy: Dict[str, Any], framework: str, policy_type: str
    ) -> Dict[str, Any]:
        """Generate compliance mapping for the policy."""
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
            "HIPAA": {
                "privacy": ["§ 164.502", "§ 164.504", "§ 164.506"],
                "security": ["§ 164.308", "§ 164.310", "§ 164.312"],
                "breach_notification": ["§ 164.400", "§ 164.404", "§ 164.408"],
                "administrative_safeguards": [
                    "§ 164.308(a)(1)",
                    "§ 164.308(a)(3)",
                    "§ 164.308(a)(4)",
                ],
            },
        }

        # Make framework lookup case-insensitive
        framework_upper = framework.upper()
        mapped_controls = control_mappings.get(framework_upper, {}).get(policy_type, [])

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

    def _apply_business_customizations(
        self,
        policy: Dict[str, Any],
        business_context: Dict[str, Any],
        customization_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply business-specific customizations to the policy."""
        policy["business_context"] = {
            "company_name": business_context.get("company_name", "Organization"),
            "industry": business_context.get("industry", "Unknown"),
            "employee_count": business_context.get("employee_count", 0),
            "customization_applied": datetime.now(timezone.utc).isoformat(),
        }

        # Apply industry customizations
        industry = business_context.get("industry", "").lower()
        if industry in ["healthcare", "medical"]:
            policy = self._apply_healthcare_customizations(policy)
        elif industry in ["finance", "banking", "fintech"]:
            policy = self._apply_financial_customizations(policy)
        elif industry in ["technology", "software", "saas"]:
            policy = self._apply_technology_customizations(policy)

        # Apply size customizations
        org_size = self._categorize_organization_size(business_context.get("employee_count", 0))
        policy = self._apply_size_customizations(policy, org_size)

        return policy

    def _apply_healthcare_customizations(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Apply healthcare industry-specific customizations."""
        healthcare_section = {
            "section_id": "healthcare_specific",
            "title": "Healthcare Industry Requirements",
            "content": (
                "This section addresses healthcare-specific compliance "
                "requirements including HIPAA, patient data protection, "
                "and medical device security."
            ),
            "subsections": [
                {
                    "subsection_id": "hipaa_compliance",
                    "title": "HIPAA Compliance",
                    "content": (
                        "Procedures for handling protected health information (PHI) "
                        "in accordance with HIPAA requirements."
                    ),
                    "controls": ["PHI access controls", "Audit logging", "Breach notification"],
                }
            ],
        }

        policy["sections"].append(healthcare_section)
        policy["roles_responsibilities"].extend(
            [
                {
                    "role": "HIPAA Security Officer",
                    "responsibilities": [
                        "Oversee PHI security",
                        "Conduct risk assessments",
                        "Manage security incidents",
                    ],
                },
                {
                    "role": "Privacy Officer",
                    "responsibilities": [
                        "Ensure privacy compliance",
                        "Handle patient requests",
                        "Manage consent processes",
                    ],
                },
            ]
        )

        return policy

    def _apply_financial_customizations(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Apply financial industry-specific customizations."""
        financial_section = {
            "section_id": "financial_specific",
            "title": "Financial Industry Requirements",
            "content": (
                "This section addresses financial industry compliance "
                "requirements including SOX, PCI DSS, and banking regulations."
            ),
            "subsections": [
                {
                    "subsection_id": "sox_compliance",
                    "title": "Sarbanes-Oxley Compliance",
                    "content": (
                        "Controls for financial reporting and internal controls "
                        "over financial reporting."
                    ),
                    "controls": ["Financial controls", "Audit trails", "Segregation of duties"],
                }
            ],
        }

        policy["sections"].append(financial_section)
        policy["roles_responsibilities"].extend(
            [
                {
                    "role": "Chief Risk Officer",
                    "responsibilities": [
                        "Oversee risk management",
                        "Ensure regulatory compliance",
                        "Report to board",
                    ],
                },
                {
                    "role": "Compliance Officer",
                    "responsibilities": [
                        "Monitor regulatory changes",
                        "Conduct compliance training",
                        "Manage audits",
                    ],
                },
            ]
        )

        return policy

    def _apply_technology_customizations(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Apply technology industry-specific customizations."""
        tech_section = {
            "section_id": "technology_specific",
            "title": "Technology Industry Requirements",
            "content": (
                "This section addresses technology industry requirements "
                "including data protection, software security, and cloud compliance."
            ),
            "subsections": [
                {
                    "subsection_id": "software_security",
                    "title": "Software Security",
                    "content": ("Security requirements for software development and deployment."),
                    "controls": [
                        "Secure coding practices",
                        "Code reviews",
                        "Vulnerability testing",
                    ],
                }
            ],
        }

        policy["sections"].append(tech_section)
        policy["roles_responsibilities"].extend(
            [
                {
                    "role": "Chief Technology Officer",
                    "responsibilities": [
                        "Oversee technology strategy",
                        "Ensure security architecture",
                        "Manage technical risks",
                    ],
                },
                {
                    "role": "DevSecOps Lead",
                    "responsibilities": [
                        "Integrate security in development",
                        "Automate security testing",
                        "Monitor deployments",
                    ],
                },
            ]
        )

        return policy

    def _apply_size_customizations(self, policy: Dict[str, Any], org_size: str) -> Dict[str, Any]:
        """Apply organization size-specific customizations."""
        if org_size == "micro":
            policy["implementation_notes"] = [
                "Consider outsourcing complex compliance activities",
                "Focus on essential controls first",
                "Use cloud-based solutions to reduce overhead",
            ]
        elif org_size == "small":
            policy["implementation_notes"] = [
                "Implement controls in phases",
                "Consider managed services for specialized areas",
                "Focus on automation to reduce manual effort",
            ]
        elif org_size == "medium":
            policy["implementation_notes"] = [
                "Establish dedicated compliance team",
                "Implement comprehensive monitoring",
                "Consider compliance management platforms",
            ]
        else:  # large/enterprise
            policy["implementation_notes"] = [
                "Implement enterprise-grade solutions",
                "Establish compliance centers of excellence",
                "Consider advanced automation and AI tools",
            ]

        return policy

    def _get_fallback_policy(
        self, framework: str, policy_type: str, business_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Provide fallback policy when AI generation fails."""
        return {
            "policy_id": f"{framework}_{policy_type}_{uuid4().hex[:8]}",
            "title": f"{policy_type.replace('_', ' ').title()} Policy",
            "version": "1.0",
            "effective_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "framework": framework,
            "policy_type": policy_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sections": [
                {
                    "section_id": "section_1",
                    "title": "Purpose and Scope",
                    "content": (
                        f"This policy establishes the framework for {policy_type} "
                        f"in accordance with {framework} requirements."
                    ),
                    "subsections": [],
                },
                {
                    "section_id": "section_2",
                    "title": "Roles and Responsibilities",
                    "content": (
                        "This section defines the roles and responsibilities for "
                        "implementing and maintaining this policy."
                    ),
                    "subsections": [],
                },
            ],
            "roles_responsibilities": [
                {
                    "role": "Policy Owner",
                    "responsibilities": ["Maintain policy", "Ensure compliance", "Regular reviews"],
                }
            ],
            "procedures": [
                {
                    "procedure_id": "proc_1",
                    "title": "Policy Review Procedure",
                    "steps": ["Annual review", "Update as needed", "Communicate changes"],
                }
            ],
            "compliance_requirements": [
                {
                    "requirement_id": "req_1",
                    "description": f"Comply with {framework} requirements",
                    "control_reference": "General compliance",
                }
            ],
            "business_context": business_context,
        }

    def _analyze_compliance_maturity(
        self, business_context: Dict[str, Any], existing_evidence: list, framework: str
    ) -> Dict[str, Any]:
        """Analyze compliance maturity level."""
        evidence_count = len(existing_evidence)

        if evidence_count == 0:
            maturity_level = "Initial"
        elif evidence_count < MATURITY_BASIC_THRESHOLD:
            maturity_level = "Basic"
        elif evidence_count < MATURITY_DEVELOPING_THRESHOLD:
            maturity_level = "Developing"
        elif evidence_count < MATURITY_MANAGED_THRESHOLD:
            maturity_level = "Managed"
        else:
            maturity_level = "Optimized"

        return {
            "maturity_level": maturity_level,
            "evidence_count": evidence_count,
            "framework": framework,
        }

    @staticmethod
    def _categorize_organization_size(employee_count: int) -> str:
        """Categorize organization size based on employee count."""
        if employee_count < ORG_SIZE_SMALL_THRESHOLD:
            return "micro"
        elif employee_count < ORG_SIZE_MEDIUM_THRESHOLD:
            return "small"
        elif employee_count < ORG_SIZE_LARGE_THRESHOLD:
            return "medium"
        else:
            return "large"
