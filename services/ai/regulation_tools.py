"""
import logging


logger = logging.getLogger(__name__)
Industry Regulation Lookup Tools for Function Calling

Implements tools for looking up industry regulations, compliance requirements,
framework specifics, and risk calculations based on business context.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from config.logging_config import get_logger
from .tools import BaseTool, ToolResult, ToolType, register_tool

logger = get_logger(__name__)


@dataclass
class RegulationInfo:
    """Information about a specific regulation"""

    name: str
    description: str
    applicability: str
    key_requirements: List[str]
    penalties: str
    enforcement_body: str
    last_updated: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "applicability": self.applicability,
            "key_requirements": self.key_requirements,
            "penalties": self.penalties,
            "enforcement_body": self.enforcement_body,
            "last_updated": self.last_updated,
        }


@dataclass
class ComplianceRequirement:
    """Specific compliance requirement details"""

    requirement_id: str
    title: str
    description: str
    mandatory: bool
    framework: str
    section: str
    implementation_guidance: str
    evidence_required: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "title": self.title,
            "description": self.description,
            "mandatory": self.mandatory,
            "framework": self.framework,
            "section": self.section,
            "implementation_guidance": self.implementation_guidance,
            "evidence_required": self.evidence_required,
        }


class IndustryRegulationLookupTool(BaseTool):
    """Tool for looking up industry-specific regulations"""

    def __init__(self) -> None:
        super().__init__(
            name="lookup_industry_regulations",
            description="Look up regulations applicable to specific industries and business contexts",
        )
        self.regulation_database = {
            "technology": {
                "GDPR": RegulationInfo(
                    name="General Data Protection Regulation (UK GDPR)",
                    description="Data protection regulation for processing personal data",
                    applicability="All organizations processing personal data of UK residents",
                    key_requirements=[
                        "Lawful basis for processing",
                        "Data subject rights implementation",
                        "Privacy by design and default",
                        "Data protection impact assessments",
                        "Breach notification within 72 hours",
                    ],
                    penalties="Up to £17.5 million or 4% of global turnover",
                    enforcement_body="Information Commissioner's Office (ICO)",
                    last_updated="2021-01-01",
                ),
                "DPA2018": RegulationInfo(
                    name="Data Protection Act 2018",
                    description="UK implementation of GDPR with additional provisions",
                    applicability="All UK organizations processing personal data",
                    key_requirements=[
                        "GDPR compliance",
                        "Law enforcement processing provisions",
                        "Intelligence services exemptions",
                        "Direct marketing rules",
                    ],
                    penalties="Criminal offences and administrative fines",
                    enforcement_body="Information Commissioner's Office (ICO)",
                    last_updated="2018-05-25",
                ),
            },
            "financial": {
                "FCA": RegulationInfo(
                    name="Financial Conduct Authority Rules",
                    description="Regulatory framework for financial services",
                    applicability="Authorized financial services firms",
                    key_requirements=[
                        "Client money protection",
                        "Fair treatment of customers",
                        "Risk management frameworks",
                        "Operational resilience",
                        "Financial crime prevention",
                    ],
                    penalties="Unlimited fines and regulatory action",
                    enforcement_body="Financial Conduct Authority",
                    last_updated="2023-12-31",
                ),
                "PCI_DSS": RegulationInfo(
                    name="Payment Card Industry Data Security Standard",
                    description="Security standards for payment card data",
                    applicability="Organizations handling cardholder data",
                    key_requirements=[
                        "Secure network maintenance",
                        "Cardholder data protection",
                        "Vulnerability management",
                        "Access control implementation",
                        "Regular security testing",
                    ],
                    penalties="Fines from card brands and potential liability",
                    enforcement_body="Payment Card Industry Security Standards Council",
                    last_updated="2024-03-31",
                ),
            },
            "healthcare": {
                "MHRA": RegulationInfo(
                    name="Medicines and Healthcare products Regulatory Agency",
                    description="Regulation of medicines and medical devices",
                    applicability="Healthcare providers and medical device manufacturers",
                    key_requirements=[
                        "Good Clinical Practice (GCP)",
                        "Good Manufacturing Practice (GMP)",
                        "Pharmacovigilance",
                        "Medical device regulations",
                        "Clinical trial authorizations",
                    ],
                    penalties="Criminal prosecution and product recalls",
                    enforcement_body="Medicines and Healthcare products Regulatory Agency",
                    last_updated="2023-06-30",
                )
            },
            "general": {
                "HEALTH_SAFETY": RegulationInfo(
                    name="Health and Safety at Work Act 1974",
                    description="Workplace health and safety requirements",
                    applicability="All UK employers",
                    key_requirements=[
                        "Risk assessments",
                        "Safe working procedures",
                        "Employee training",
                        "Incident reporting",
                        "Emergency procedures",
                    ],
                    penalties="Unlimited fines and imprisonment",
                    enforcement_body="Health and Safety Executive (HSE)",
                    last_updated="1974-07-31",
                ),
                "EQUALITY_ACT": RegulationInfo(
                    name="Equality Act 2010",
                    description="Protection against discrimination in the workplace",
                    applicability="All UK employers and service providers",
                    key_requirements=[
                        "Protected characteristics awareness",
                        "Reasonable adjustments",
                        "Equal pay provisions",
                        "Harassment prevention",
                        "Positive action measures",
                    ],
                    penalties="Unlimited compensation awards",
                    enforcement_body="Equality and Human Rights Commission",
                    last_updated="2010-10-01",
                ),
            },
        }

    def get_function_schema(self) -> Dict[str, Any]:
        """Get the function schema for Google Generative AI function calling"""
        return {
            "name": "lookup_industry_regulations",
            "description": "Look up regulations applicable to specific industries",
            "parameters": {
                "type": "object",
                "properties": {
                    "industry": {
                        "type": "string",
                        "description": "Industry sector (e.g., 'technology', 'financial', 'healthcare')",
                    },
                    "business_size": {
                        "type": "string",
                        "enum": ["micro", "small", "medium", "large"],
                        "description": "Size of the business for applicable regulations",
                    },
                    "data_processing": {
                        "type": "boolean",
                        "description": "Whether the business processes personal data",
                    },
                    "geographic_scope": {
                        "type": "string",
                        "enum": ["uk_only", "eu", "international"],
                        "description": "Geographic scope of business operations",
                    },
                    "specific_activities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific business activities that may trigger additional regulations",
                    },
                },
                "required": ["industry", "business_size", "data_processing"],
            },
        }

    async def execute(
        self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute industry regulation lookup"""
        try:
            industry = parameters.get("industry", "general").lower()
            business_size = parameters.get("business_size", "small")
            processes_data = parameters.get("data_processing", True)
            geographic_scope = parameters.get("geographic_scope", "uk_only")
            activities = parameters.get("specific_activities", [])
            applicable_regulations = []
            if industry in self.regulation_database:
                for reg_name, reg_info in self.regulation_database[industry].items():
                    applicable_regulations.append(
                        {
                            "regulation": reg_name,
                            "priority": "high",
                            "reason": f"Industry-specific regulation for {industry}",
                            **reg_info.to_dict(),
                        }
                    )
            for reg_name, reg_info in self.regulation_database["general"].items():
                applicable_regulations.append(
                    {
                        "regulation": reg_name,
                        "priority": "medium",
                        "reason": "General UK business regulation",
                        **reg_info.to_dict(),
                    }
                )
            if processes_data and industry != "technology":
                gdpr_info = self.regulation_database["technology"]["GDPR"]
                applicable_regulations.append(
                    {
                        "regulation": "GDPR",
                        "priority": "critical",
                        "reason": "Processing personal data",
                        **gdpr_info.to_dict(),
                    }
                )
            filtered_regulations = self._filter_by_business_size(
                applicable_regulations, business_size
            )
            activity_regulations = self._get_activity_specific_regulations(activities)
            filtered_regulations.extend(activity_regulations)
            priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            filtered_regulations.sort(
                key=lambda x: priority_order.get(x["priority"], 2), reverse=True
            )
            result_data = {
                "applicable_regulations": filtered_regulations,
                "regulation_count": len(filtered_regulations),
                "priority_breakdown": self._analyze_priority_breakdown(filtered_regulations),
                "compliance_timeline": self._generate_compliance_timeline(filtered_regulations),
                "industry_context": {
                    "industry": industry,
                    "business_size": business_size,
                    "data_processing": processes_data,
                    "geographic_scope": geographic_scope,
                },
                "next_steps": self._generate_next_steps(filtered_regulations),
                "analysis_timestamp": datetime.now().isoformat(),
            }
            logger.info(
                "Regulation lookup completed: %s regulations found for %s industry"
                % (len(filtered_regulations), industry)
            )
            return ToolResult(
                success=True,
                data=result_data,
                metadata={
                    "tool_type": "regulation_lookup",
                    "industry": industry,
                    "regulation_count": len(filtered_regulations),
                },
            )
        except Exception as e:
            logger.error("Regulation lookup failed: %s" % e)
            return ToolResult(success=False, error=f"Regulation lookup execution failed: {e!s}")

    def _filter_by_business_size(
        self, regulations: List[Dict[str, Any]], business_size: str
    ) -> List[Dict[str, Any]]:
        """Filter regulations based on business size"""
        for regulation in regulations:
            if business_size == "micro":
                regulation["size_guidance"] = "Simplified compliance approach may be available"
            elif business_size == "small":
                regulation["size_guidance"] = "SME-focused guidance and support available"
            elif business_size == "medium":
                regulation["size_guidance"] = "Full compliance required with some flexibility"
            else:
                regulation["size_guidance"] = "Full regulatory scrutiny and compliance required"
        return regulations

    def _get_activity_specific_regulations(self, activities: List[str]) -> List[Dict[str, Any]]:
        """Get regulations specific to business activities"""
        activity_regs = []
        for activity in activities:
            activity_lower = activity.lower()
            if "payment" in activity_lower or "card" in activity_lower:
                pci_info = self.regulation_database["financial"]["PCI_DSS"]
                activity_regs.append(
                    {
                        "regulation": "PCI_DSS",
                        "priority": "high",
                        "reason": f"Activity: {activity}",
                        **pci_info.to_dict(),
                    }
                )
            if "marketing" in activity_lower or "advertising" in activity_lower:
                activity_regs.append(
                    {
                        "regulation": "PECR",
                        "priority": "medium",
                        "reason": f"Activity: {activity}",
                        "name": "Privacy and Electronic Communications Regulations",
                        "description": "Regulations for electronic marketing and communications",
                        "applicability": "Organizations conducting electronic marketing",
                        "key_requirements": [
                            "Consent for email marketing",
                            "Opt-out mechanisms",
                            "Cookie consent",
                            "Silent calls prevention",
                        ],
                        "penalties": "Up to £500,000",
                        "enforcement_body": "Information Commissioner's Office (ICO)",
                        "last_updated": "2003-12-11",
                    }
                )
        return activity_regs

    def _analyze_priority_breakdown(self, regulations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze breakdown of regulation priorities"""
        breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for reg in regulations:
            priority = reg.get("priority", "medium")
            if priority in breakdown:
                breakdown[priority] += 1
        return breakdown

    def _generate_compliance_timeline(
        self, regulations: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Generate recommended compliance timeline"""
        timeline = {"immediate": [], "short_term": [], "medium_term": [], "long_term": []}
        for reg in regulations:
            reg_name = reg.get("regulation", "Unknown")
            priority = reg.get("priority", "medium")
            if priority == "critical":
                timeline["immediate"].append(f"Begin {reg_name} compliance assessment")
            elif priority == "high":
                timeline["short_term"].append(f"Implement {reg_name} requirements")
            elif priority == "medium":
                timeline["medium_term"].append(
                    f"Address {reg_name} compliance",
                )
            else:
                timeline["long_term"].append(
                    f"Review {reg_name} applicability",
                )
        return timeline

    def _generate_next_steps(self, regulations: List[Dict[str, Any]]) -> List[str]:
        """Generate recommended next steps"""
        next_steps = []
        if any(reg.get("priority") == "critical" for reg in regulations):
            next_steps.append("Prioritize critical regulatory compliance immediately")
        next_steps.extend(
            [
                "Conduct detailed compliance gap analysis",
                "Assign compliance responsibilities to team members",
                "Establish compliance monitoring procedures",
                "Consider professional compliance consultation",
            ]
        )
        return next_steps


class ComplianceRequirementsTool(BaseTool):
    """Tool for checking specific compliance requirements"""

    def __init__(self) -> None:
        super().__init__(
            name="check_compliance_requirements",
            description="Check specific compliance requirements for given frameworks and business context",
        )

    def get_function_schema(self) -> Dict[str, Any]:
        """Get the function schema for Google Generative AI function calling"""
        return {
            "name": "check_compliance_requirements",
            "description": "Check specific compliance requirements for frameworks",
            "parameters": {
                "type": "object",
                "properties": {
                    "framework": {
                        "type": "string",
                        "description": "Compliance framework (e.g., 'GDPR', 'ISO27001', 'SOC2')",
                    },
                    "business_context": {
                        "type": "object",
                        "properties": {
                            "industry": {"type": "string"},
                            "employee_count": {"type": "number"},
                            "data_types": {"type": "array", "items": {"type": "string"}},
                            "geographic_regions": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["industry", "employee_count"],
                    },
                    "specific_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific areas of compliance to focus on",
                    },
                },
                "required": ["framework", "business_context"],
            },
        }

    async def execute(
        self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute compliance requirements check"""
        try:
            framework = parameters.get("framework", "").upper()
            business_context = parameters.get("business_context", {})
            specific_areas = parameters.get("specific_areas", [])
            requirements = self._get_framework_requirements(
                framework, business_context, specific_areas
            )
            result_data = {
                "framework": framework,
                "applicable_requirements": requirements,
                "requirement_count": len(requirements),
                "business_context": business_context,
                "compliance_checklist": self._generate_compliance_checklist(requirements),
                "implementation_priorities": self._prioritize_requirements(requirements),
                "analysis_timestamp": datetime.now().isoformat(),
            }
            logger.info(
                "Compliance requirements check completed: %s requirements found for %s"
                % (len(requirements), framework)
            )
            return ToolResult(
                success=True,
                data=result_data,
                metadata={
                    "tool_type": "compliance_requirements",
                    "framework": framework,
                    "requirement_count": len(requirements),
                },
            )
        except Exception as e:
            logger.error("Compliance requirements check failed: %s" % e)
            return ToolResult(
                success=False, error=f"Compliance requirements check execution failed: {e!s}"
            )

    def _get_framework_requirements(
        self, framework: str, business_context: Dict[str, Any], specific_areas: List[str]
    ) -> List[Dict[str, Any]]:
        """Get requirements for specific framework"""
        requirements = []
        if framework == "GDPR":
            gdpr_requirements = [
                ComplianceRequirement(
                    requirement_id="GDPR-6",
                    title="Lawful Basis for Processing",
                    description="Establish and document lawful basis for all personal data processing",
                    mandatory=True,
                    framework="GDPR",
                    section="Article 6",
                    implementation_guidance="Document lawful basis, conduct legitimate interests assessments",
                    evidence_required=[
                        "Privacy notices",
                        "Legitimate interests assessments",
                        "Consent records",
                    ],
                ),
                ComplianceRequirement(
                    requirement_id="GDPR-25",
                    title="Data Protection by Design and by Default",
                    description="Implement appropriate technical and organizational measures",
                    mandatory=True,
                    framework="GDPR",
                    section="Article 25",
                    implementation_guidance="Build privacy into systems, implement privacy-enhancing technologies",
                    evidence_required=[
                        "System design documents",
                        "Privacy impact assessments",
                        "Technical measures documentation",
                    ],
                ),
                ComplianceRequirement(
                    requirement_id="GDPR-33",
                    title="Notification of Personal Data Breach",
                    description="Report data breaches to supervisory authority within 72 hours",
                    mandatory=True,
                    framework="GDPR",
                    section="Article 33",
                    implementation_guidance="Implement breach detection and response procedures",
                    evidence_required=[
                        "Breach response plan",
                        "Incident logs",
                        "Notification procedures",
                    ],
                ),
            ]
            requirements.extend([req.to_dict() for req in gdpr_requirements])
        elif framework == "ISO27001":
            iso_requirements = [
                ComplianceRequirement(
                    requirement_id="ISO-A.5.1",
                    title="Policies for Information Security",
                    description="Information security policy and topic-specific policies",
                    mandatory=True,
                    framework="ISO27001",
                    section="A.5.1",
                    implementation_guidance="Develop comprehensive information security policies",
                    evidence_required=[
                        "Information security policy",
                        "Topic-specific policies",
                        "Policy approval records",
                    ],
                ),
                ComplianceRequirement(
                    requirement_id="ISO-A.8.1",
                    title="Responsibility for Assets",
                    description="Assets shall be identified and ownership established",
                    mandatory=True,
                    framework="ISO27001",
                    section="A.8.1",
                    implementation_guidance="Create asset inventory and assign ownership",
                    evidence_required=[
                        "Asset register",
                        "Asset ownership assignments",
                        "Asset handling procedures",
                    ],
                ),
            ]
            requirements.extend([req.to_dict() for req in iso_requirements])
        if specific_areas:
            requirements = [
                req
                for req in requirements
                if any(
                    area.lower() in req["title"].lower()
                    or area.lower() in req["description"].lower()
                    for area in specific_areas
                )
            ]
        return requirements

    def _generate_compliance_checklist(
        self, requirements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate actionable compliance checklist"""
        checklist = []
        for req in requirements:
            checklist_item = {
                "requirement": req["title"],
                "status": "pending",
                "actions": [
                    f"Review {req['section']} requirements",
                    "Assess current implementation status",
                    "Document implementation approach",
                    "Collect required evidence",
                ],
                "evidence_needed": req["evidence_required"],
                "priority": "high" if req["mandatory"] else "medium",
            }
            checklist.append(checklist_item)
        return checklist

    def _prioritize_requirements(self, requirements: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Prioritize requirements for implementation"""
        priorities = []
        mandatory_reqs = [req for req in requirements if req["mandatory"]]
        for req in mandatory_reqs:
            priorities.append(
                {
                    "requirement": req["title"],
                    "priority": "critical",
                    "reason": "Mandatory compliance requirement",
                }
            )
        optional_reqs = [req for req in requirements if not req["mandatory"]]
        for req in optional_reqs:
            priorities.append(
                {
                    "requirement": req["title"],
                    "priority": "medium",
                    "reason": "Best practice recommendation",
                }
            )
        return priorities


register_tool(IndustryRegulationLookupTool(), ToolType.REGULATION_LOOKUP)
register_tool(ComplianceRequirementsTool(), ToolType.FRAMEWORK_SPECIFICS)
