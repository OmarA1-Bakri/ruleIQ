"""

# Constants
DEFAULT_RETRIES = 5
MAX_RETRIES = 3


Manifest Enhancer - Enriches compliance manifests with business context and risk metadata
for the ruleIQ IQ Agent's GraphRAG system.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ManifestEnhancer:
    """Enhances compliance manifests with intelligent metadata for IQ Agent."""

    def __init__(self, input_manifest_path: str, output_manifest_path: str) -> None:
        """
        Initialize the enhancer with input and output paths.

        Args:
            input_manifest_path: Path to the original manifest
            output_manifest_path: Path to save the enhanced manifest
        """
        self.input_path = Path(input_manifest_path)
        self.output_path = Path(output_manifest_path)
        self.manifest_data = None
        self.enhanced_manifest = None
        self.business_trigger_rules = {
            "gdpr": {"handles_personal_data": True, "has_eu_customers": True},
            "uk-gdpr": {"handles_personal_data": True, "country": "UK"},
            "pci": {"processes_payments": True, "stores_card_data": True},
            "soc2": {"b2b_saas": True, "processes_customer_data": True},
            "iso27001": {"requires_security_certification": True, "enterprise_customers": True},
            "aml": {"processes_payments": True, "provides_financial_services": True},
            "ai": {"uses_ai_systems": True, "automated_decision_making": True},
            "finance": {"industry": "finance", "provides_financial_services": True},
            "cyber": {"requires_cyber_certification": True},
        }
        self.risk_scoring_rules = {
            "law": 8,
            "standard": 6,
            "guidance": 4,
            "finance": 9,
            "privacy": 9,
            "aml": 10,
            "payments": 9,
            "security": 8,
        }
        self.complexity_rules = {
            "gdpr": 8,
            "iso": 7,
            "soc2": 7,
            "pci": 9,
            "aml": 9,
            "finance": 9,
            "cyber": 4,
            "ai": 6,
        }

    def load_manifest(self) -> Dict[str, Any]:
        """Load the original manifest file."""
        logger.info("Loading manifest from %s" % self.input_path)
        with open(self.input_path, "r") as f:
            self.manifest_data = json.load(f)
        items = self.manifest_data.get("items", [])
        logger.info("Loaded %s items from manifest" % len(items))
        return self.manifest_data

    def determine_business_triggers(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine business triggers based on regulation ID and tags.

        Args:
            item: Manifest item to analyze

        Returns:
            Dictionary of business trigger conditions
        """
        triggers = {}
        item_id = item.get("id", "").lower()
        tags = item.get("tags", [])
        for rule_key, rule_triggers in self.business_trigger_rules.items():
            if rule_key in item_id or any(rule_key in tag.lower() for tag in tags):
                triggers.update(rule_triggers)
        if "privacy" in tags or "data-protection" in tags:
            triggers["handles_personal_data"] = True
        if "UK" in tags:
            triggers["country"] = "UK"
        elif "EU" in tags:
            triggers["has_eu_customers"] = True
        if "platforms" in tags:
            triggers["online_platform"] = True
        if "e-money" in tags:
            triggers["issues_emoney"] = True
        return triggers

    def calculate_risk_score(self, item: Dict[str, Any]) -> int:
        """
        Calculate base risk score based on regulation type and tags.

        Args:
            item: Manifest item to analyze

        Returns:
            Risk score from 1-10
        """
        base_score = 5
        tags = item.get("tags", [])
        item_id = item.get("id", "").lower()
        for tag in tags:
            if tag.lower() in self.risk_scoring_rules:
                score = self.risk_scoring_rules[tag.lower()]
                base_score = max(base_score, score)
        critical_keywords = ["gdpr", "aml", "money-laundering", "pci", "fsma"]
        if any(keyword in item_id for keyword in critical_keywords):
            base_score = min(10, base_score + 1)
        return base_score

    def determine_complexity(self, item: Dict[str, Any]) -> int:
        """
        Determine implementation complexity based on regulation type.

        Args:
            item: Manifest item to analyze

        Returns:
            Complexity score from 1-10
        """
        item_id = item.get("id", "").lower()
        for rule_key, complexity in self.complexity_rules.items():
            if rule_key in item_id:
                return complexity
        priority = item.get("priority", 3)
        return min(10, priority * 2)

    def determine_enforcement_frequency(self, risk_score: int) -> str:
        """
        Determine enforcement frequency based on risk score.

        Args:
            risk_score: The calculated risk score

        Returns:
            Enforcement frequency category
        """
        if risk_score >= 9:
            return "very_high"
        elif risk_score >= 7:
            return "high"
        elif risk_score >= DEFAULT_RETRIES:
            return "medium"
        elif risk_score >= MAX_RETRIES:
            return "low"
        else:
            return "emerging"

    def determine_automation_potential(self, item: Dict[str, Any]) -> float:
        """
        Determine automation potential based on regulation type.

        Args:
            item: Manifest item to analyze

        Returns:
            Automation potential score from 0-1
        """
        tags = item.get("tags", [])
        if any(tag in ["security", "cyber", "monitoring"] for tag in tags):
            return 0.8
        if any(tag in ["privacy", "data-protection", "payments"] for tag in tags):
            return 0.7
        if any(tag in ["standard", "audit"] for tag in tags):
            return 0.6
        if any(tag in ["law", "guidance"] for tag in tags):
            return 0.4
        return 0.5

    def suggest_controls(self, item: Dict[str, Any]) -> List[str]:
        """
        Suggest appropriate controls based on regulation type.

        Args:
            item: Manifest item to analyze

        Returns:
            List of suggested control names
        """
        controls = []
        item_id = item.get("id", "").lower()
        tags = item.get("tags", [])
        if "privacy" in tags or "gdpr" in item_id:
            controls.extend(
                [
                    "privacy_policy_implementation",
                    "consent_management_system",
                    "data_subject_request_portal",
                    "breach_notification_procedure",
                    "data_processing_agreements",
                ]
            )
        if "aml" in tags or "money-laundering" in item_id:
            controls.extend(
                [
                    "customer_due_diligence_procedure",
                    "transaction_monitoring_system",
                    "suspicious_activity_reporting",
                    "pep_screening_system",
                    "sanctions_screening",
                ]
            )
        if "security" in tags or "iso" in item_id:
            controls.extend(
                [
                    "security_policy_framework",
                    "access_control_matrix",
                    "incident_response_plan",
                    "vulnerability_management",
                    "security_awareness_training",
                ]
            )
        if "payments" in tags or "pci" in item_id:
            controls.extend(
                [
                    "network_segmentation",
                    "cardholder_data_encryption",
                    "payment_security_monitoring",
                    "pci_compliance_scanning",
                ]
            )
        if "ai" in tags or "artificial" in item_id:
            controls.extend(
                [
                    "ai_impact_assessment",
                    "algorithmic_transparency_log",
                    "bias_testing_framework",
                    "human_oversight_procedures",
                    "ai_governance_framework",
                ]
            )
        if "finance" in tags or "fsma" in item_id:
            controls.extend(
                [
                    "regulatory_reporting_system",
                    "capital_adequacy_monitoring",
                    "risk_management_framework",
                    "compliance_monitoring_system",
                ]
            )
        return list(set(controls))[:5]

    def generate_evidence_templates(self, controls: List[str]) -> List[str]:
        """
        Generate evidence templates based on suggested controls.

        Args:
            controls: List of control names

        Returns:
            List of evidence template names
        """
        evidence_map = {
            "privacy_policy_implementation": "Privacy Policy Document",
            "consent_management_system": "Consent Records",
            "data_subject_request_portal": "DSAR Log",
            "breach_notification_procedure": "Data Breach Log",
            "data_processing_agreements": "DPA Register",
            "customer_due_diligence_procedure": "CDD Records",
            "transaction_monitoring_system": "Transaction Monitoring Reports",
            "suspicious_activity_reporting": "SAR Filing Records",
            "security_policy_framework": "Security Policy Documentation",
            "access_control_matrix": "Access Control Reviews",
            "incident_response_plan": "Incident Response Records",
            "ai_impact_assessment": "AI Impact Assessment Report",
            "algorithmic_transparency_log": "Algorithm Decision Log",
            "regulatory_reporting_system": "Regulatory Filing Records",
        }
        templates = []
        for control in controls:
            if control in evidence_map:
                templates.append(evidence_map[control])
        if not templates:
            templates = ["Compliance Documentation", "Risk Assessment Report", "Audit Trail"]
        return templates[:5]

    def enhance_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance a single manifest item with metadata.

        Args:
            item: Original manifest item

        Returns:
            Enhanced manifest item
        """
        enhanced = item.copy()
        enhanced["business_triggers"] = self.determine_business_triggers(item)
        risk_score = self.calculate_risk_score(item)
        complexity = self.determine_complexity(item)
        enhanced["risk_metadata"] = {
            "base_risk_score": risk_score,
            "enforcement_frequency": self.determine_enforcement_frequency(risk_score),
            "implementation_complexity": complexity,
            "typical_implementation_timeline": self.estimate_timeline(complexity),
        }
        controls = self.suggest_controls(item)
        if controls:
            enhanced["suggested_controls"] = controls
        enhanced["automation_potential"] = self.determine_automation_potential(item)
        if controls:
            enhanced["evidence_templates"] = self.generate_evidence_templates(controls)
        return enhanced

    def estimate_timeline(self, complexity: int) -> str:
        """
        Estimate implementation timeline based on complexity.

        Args:
            complexity: Complexity score 1-10

        Returns:
            Timeline estimate string
        """
        if complexity >= 9:
            return "18-24 months"
        elif complexity >= 7:
            return "12-18 months"
        elif complexity >= DEFAULT_RETRIES:
            return "6-12 months"
        elif complexity >= MAX_RETRIES:
            return "3-6 months"
        else:
            return "1-3 months"

    def enhance_manifest(self) -> Dict[str, Any]:
        """
        Enhance the entire manifest with intelligent metadata.

        Returns:
            Enhanced manifest dictionary
        """
        if not self.manifest_data:
            self.load_manifest()
        self.enhanced_manifest = {
            "schema_version": "2.0",
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "original_version": self.manifest_data.get("schema_version", "1.0"),
            "owner": self.manifest_data.get("owner", "Unknown"),
            "description": "Enhanced compliance manifest with business context mappings and risk intelligence",
            "priority_scale": self.manifest_data.get("priority_scale", ""),
            "metadata": {
                "total_items": len(self.manifest_data.get("items", [])),
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "enhancement_version": "1.0",
                "risk_scoring_methodology": "Based on enforcement frequency, penalty severity, and implementation complexity",
                "automation_scoring_methodology": "0-1 scale based on availability of APIs, clear rules, and measurability",
            },
            "items": [],
        }
        items = self.manifest_data.get("items", [])
        for i, item in enumerate(items):
            logger.info("Enhancing item %s/%s: %s" % (i + 1, len(items), item.get("id", "unknown")))
            enhanced_item = self.enhance_item(item)
            self.enhanced_manifest["items"].append(enhanced_item)
        logger.info("Enhanced %s items" % len(self.enhanced_manifest["items"]))
        return self.enhanced_manifest

    def save_enhanced_manifest(self) -> None:
        """Save the enhanced manifest to the output path."""
        if not self.enhanced_manifest:
            self.enhance_manifest()
        logger.info("Saving enhanced manifest to %s" % self.output_path)
        with open(self.output_path, "w") as f:
            json.dump(self.enhanced_manifest, f, indent=2)
        logger.info("Enhanced manifest saved successfully")

    def generate_enhancement_report(self) -> Dict[str, Any]:
        """
        Generate a report on the enhancement process.

        Returns:
            Report dictionary with statistics
        """
        if not self.enhanced_manifest:
            self.enhance_manifest()
        report = {
            "original_items": len(self.manifest_data.get("items", [])),
            "enhanced_items": len(self.enhanced_manifest.get("items", [])),
            "risk_distribution": {},
            "complexity_distribution": {},
            "automation_potential_avg": 0,
            "controls_suggested": 0,
            "evidence_templates_created": 0,
        }
        risk_scores = []
        complexity_scores = []
        automation_scores = []
        for item in self.enhanced_manifest.get("items", []):
            risk_meta = item.get("risk_metadata", {})
            risk_score = risk_meta.get("base_risk_score", 0)
            risk_scores.append(risk_score)
            risk_category = f"risk_{risk_score}"
            report["risk_distribution"][risk_category] = (
                report["risk_distribution"].get(risk_category, 0) + 1
            )
            complexity = risk_meta.get("implementation_complexity", 0)
            complexity_scores.append(complexity)
            automation = item.get("automation_potential", 0)
            automation_scores.append(automation)
            if "suggested_controls" in item:
                report["controls_suggested"] += len(item["suggested_controls"])
            if "evidence_templates" in item:
                report["evidence_templates_created"] += len(item["evidence_templates"])
        if automation_scores:
            report["automation_potential_avg"] = round(
                sum(automation_scores) / len(automation_scores), 2
            )
        if risk_scores:
            report["avg_risk_score"] = round(sum(risk_scores) / len(risk_scores), 1)
        if complexity_scores:
            report["avg_complexity"] = round(sum(complexity_scores) / len(complexity_scores), 1)
        return report


def main() -> None:
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Enhance compliance manifest with intelligent metadata"
    )
    parser.add_argument("--input", "-i", required=True, help="Path to input manifest JSON")
    parser.add_argument(
        "--output", "-o", required=True, help="Path to output enhanced manifest JSON"
    )
    parser.add_argument("--report", "-r", action="store_true", help="Generate enhancement report")
    args = parser.parse_args()
    enhancer = ManifestEnhancer(args.input, args.output)
    enhancer.enhance_manifest()
    enhancer.save_enhanced_manifest()
    if args.report:
        report = enhancer.generate_enhancement_report()
        logger.info("\n=== Enhancement Report ===")
        logger.info(json.dumps(report, indent=2))
        report_path = Path(args.output).parent / f"{Path(args.output).stem}_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info("\nReport saved to: %s" % report_path)
    logger.info("\n✅ Successfully enhanced manifest: %s" % args.output)


if __name__ == "__main__":
    main()
