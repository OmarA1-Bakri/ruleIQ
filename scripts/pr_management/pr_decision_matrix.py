#!/usr/bin/env python3
"""
PR Decision Matrix - Systematic evaluation and decision recommendations for PRs
"""

import json
from typing import List, Dict
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PRDecisionMatrix:
    """Provides systematic decision-making for PR management"""

    def __init__(self) -> None:
        """Initialize decision matrix"""
        self.criteria = self._load_decision_criteria()
        self.weights = self._load_weights()

    def _load_decision_criteria(self) -> Dict:
        """Load decision criteria for different PR types"""
        return {
            "dependabot": {
                "auto_merge_threshold": 80,
                "factors": [
                    {"name": "ci_passing", "weight": 30, "required": True},
                    {"name": "no_major_version", "weight": 20, "required": False},
                    {"name": "security_update", "weight": 25, "required": False},
                    {"name": "no_conflicts", "weight": 15, "required": True},
                    {"name": "small_change", "weight": 10, "required": False},
                ],
            },
            "security": {
                "auto_merge_threshold": 90,
                "factors": [
                    {"name": "ci_passing", "weight": 20, "required": True},
                    {"name": "fixes_vulnerability", "weight": 35, "required": False},
                    {"name": "no_breaking_changes", "weight": 20, "required": False},
                    {"name": "security_scans_pass", "weight": 25, "required": True},
                ],
            },
            "feature": {
                "auto_merge_threshold": 95,
                "factors": [
                    {"name": "ci_passing", "weight": 20, "required": True},
                    {"name": "has_tests", "weight": 25, "required": True},
                    {"name": "has_documentation", "weight": 15, "required": False},
                    {"name": "code_reviewed", "weight": 25, "required": True},
                    {"name": "manageable_size", "weight": 15, "required": False},
                ],
            },
            "bugfix": {
                "auto_merge_threshold": 85,
                "factors": [
                    {"name": "ci_passing", "weight": 30, "required": True},
                    {"name": "has_tests", "weight": 25, "required": False},
                    {"name": "fixes_issue", "weight": 25, "required": False},
                    {"name": "no_regressions", "weight": 20, "required": True},
                ],
            },
        }

    def _load_weights(self) -> Dict:
        """Load importance weights for decision factors"""
        return {
            "priority": {"critical": 100, "high": 75, "medium": 50, "low": 25},
            "risk": {"low": 100, "medium": 50, "high": 25, "critical": 0},
            "age": {
                "fresh": 100,  # < 7 days
                "recent": 75,  # 7-14 days
                "old": 50,  # 14-30 days
                "stale": 25,  # > 30 days
            },
        }

    def evaluate_pr(self, pr_data: Dict) -> Dict:
        """Evaluate a PR and provide decision recommendation"""
        pr_type = pr_data.get("type", "other")
        criteria = self.criteria.get(pr_type, self.criteria.get("bugfix"))

        evaluation = {
            "pr_number": pr_data.get("number"),
            "type": pr_type,
            "score": 0,
            "max_score": 100,
            "factors": [],
            "decision": "manual_review",
            "confidence": 0,
            "reasons": [],
            "actions": [],
        }

        # Evaluate each factor
        for factor in criteria["factors"]:
            factor_result = self._evaluate_factor(factor, pr_data)
            evaluation["factors"].append(factor_result)

            if factor_result["met"]:
                evaluation["score"] += factor["weight"]

            if factor["required"] and not factor_result["met"]:
                evaluation["reasons"].append(f"Required factor not met: {factor['name']}")

        # Calculate confidence
        evaluation["confidence"] = (evaluation["score"] / evaluation["max_score"]) * 100

        # Determine decision
        evaluation["decision"] = self._determine_decision(
            evaluation["score"], criteria["auto_merge_threshold"], evaluation["factors"]
        )

        # Generate actions
        evaluation["actions"] = self._generate_actions(evaluation, pr_data)

        return evaluation

    def _evaluate_factor(self, factor: Dict, pr_data: Dict) -> Dict:
        """Evaluate a single decision factor"""
        factor_name = factor["name"]
        met = False
        details = ""

        if factor_name == "ci_passing":
            met = pr_data.get("ci_status") == "passing"
            details = f"CI status: {pr_data.get('ci_status', 'unknown')}"

        elif factor_name == "no_major_version":
            met = not pr_data.get("has_major_version_bump", False)
            details = "No major version bumps" if met else "Contains major version bumps"

        elif factor_name == "security_update":
            met = pr_data.get("is_security_update", False)
            details = "Security update" if met else "Not a security update"

        elif factor_name == "no_conflicts":
            met = not pr_data.get("has_conflicts", False)
            details = "No merge conflicts" if met else "Has merge conflicts"

        elif factor_name == "small_change":
            changes = pr_data.get("total_changes", 0)
            met = changes < 100
            details = f"{changes} total changes"

        elif factor_name == "fixes_vulnerability":
            met = len(pr_data.get("vulnerabilities_fixed", [])) > 0
            details = f"Fixes {len(pr_data.get('vulnerabilities_fixed', []))} vulnerabilities"

        elif factor_name == "no_breaking_changes":
            met = not pr_data.get("has_breaking_changes", False)
            details = "No breaking changes" if met else "Contains breaking changes"

        elif factor_name == "security_scans_pass":
            met = pr_data.get("security_scans_status") == "passed"
            details = f"Security scans: {pr_data.get('security_scans_status', 'unknown')}"

        elif factor_name == "has_tests":
            met = pr_data.get("has_tests", False)
            details = "Tests included" if met else "No tests found"

        elif factor_name == "has_documentation":
            met = pr_data.get("has_documentation", False)
            details = "Documentation updated" if met else "No documentation updates"

        elif factor_name == "code_reviewed":
            met = pr_data.get("review_count", 0) > 0
            details = f"{pr_data.get('review_count', 0)} reviews"

        elif factor_name == "manageable_size":
            files = pr_data.get("files_changed", 0)
            met = files < 50
            details = f"{files} files changed"

        elif factor_name == "fixes_issue":
            met = pr_data.get("linked_issues", 0) > 0
            details = f"Fixes {pr_data.get('linked_issues', 0)} issues"

        elif factor_name == "no_regressions":
            met = not pr_data.get("has_regressions", False)
            details = "No regressions detected" if met else "Potential regressions"

        return {
            "name": factor_name,
            "met": met,
            "weight": factor["weight"],
            "required": factor["required"],
            "details": details,
        }

    def _determine_decision(self, score: int, threshold: int, factors: List[Dict]) -> str:
        """Determine the decision based on score and factors"""
        # Check if all required factors are met
        required_met = all(f["met"] for f in factors if f["required"])

        if not required_met:
            return "blocked"

        if score >= threshold:
            return "auto_merge"
        elif score >= threshold * 0.8:
            return "ready_for_merge"
        elif score >= threshold * 0.6:
            return "needs_review"
        else:
            return "manual_review"

    def _generate_actions(self, evaluation: Dict, pr_data: Dict) -> List[Dict]:
        """Generate recommended actions based on evaluation"""
        actions = []
        decision = evaluation["decision"]

        if decision == "auto_merge":
            actions.append(
                {
                    "type": "merge",
                    "priority": "high",
                    "description": "Automatically merge this PR",
                    "confidence": evaluation["confidence"],
                }
            )

        elif decision == "blocked":
            for factor in evaluation["factors"]:
                if factor["required"] and not factor["met"]:
                    actions.append(
                        {
                            "type": "fix",
                            "priority": "critical",
                            "description": f"Fix required factor: {factor['name']}",
                            "details": factor["details"],
                        }
                    )

        elif decision == "ready_for_merge":
            actions.append(
                {
                    "type": "review",
                    "priority": "medium",
                    "description": "Quick review recommended before merge",
                    "confidence": evaluation["confidence"],
                }
            )

        elif decision == "needs_review":
            actions.append(
                {
                    "type": "review",
                    "priority": "high",
                    "description": "Thorough review required",
                    "confidence": evaluation["confidence"],
                }
            )

            # Add specific improvement suggestions
            for factor in evaluation["factors"]:
                if not factor["met"] and not factor["required"]:
                    actions.append(
                        {
                            "type": "improve",
                            "priority": "low",
                            "description": f"Consider improving: {factor['name']}",
                            "details": factor["details"],
                        }
                    )

        return actions

    def batch_evaluate(self, pr_list: List[Dict]) -> Dict:
        """Evaluate multiple PRs and provide batch recommendations"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_prs": len(pr_list),
            "evaluations": [],
            "summary": {
                "auto_merge": [],
                "ready_for_merge": [],
                "needs_review": [],
                "blocked": [],
                "manual_review": [],
            },
            "batch_recommendations": [],
        }

        for pr_data in pr_list:
            evaluation = self.evaluate_pr(pr_data)
            results["evaluations"].append(evaluation)
            results["summary"][evaluation["decision"]].append(pr_data.get("number"))

        # Generate batch recommendations
        results["batch_recommendations"] = self._generate_batch_recommendations(results["summary"])

        return results

    def _generate_batch_recommendations(self, summary: Dict) -> List[Dict]:
        """Generate recommendations for batch processing"""
        recommendations = []

        if summary["auto_merge"]:
            recommendations.append(
                {
                    "action": "batch_merge",
                    "priority": "high",
                    "description": f"Auto-merge {len(summary['auto_merge'])} PRs that meet all criteria",
                    "pr_numbers": summary["auto_merge"],
                }
            )

        if summary["blocked"]:
            recommendations.append(
                {
                    "action": "fix_blockers",
                    "priority": "critical",
                    "description": f"Address blockers for {len(summary['blocked'])} PRs",
                    "pr_numbers": summary["blocked"],
                }
            )

        if summary["ready_for_merge"]:
            recommendations.append(
                {
                    "action": "quick_review",
                    "priority": "medium",
                    "description": f"Quick review and merge {len(summary['ready_for_merge'])} PRs",
                    "pr_numbers": summary["ready_for_merge"],
                }
            )

        return recommendations

    def generate_decision_report(self, evaluation: Dict) -> str:
        """Generate a decision report for a single PR"""
        report = [f"# PR Decision Report - PR #{evaluation['pr_number']}\n\n"]
        report.append(f"**Type**: {evaluation['type']}\n")
        report.append(f"**Decision**: {evaluation['decision'].replace('_', ' ').upper()}\n")
        report.append(f"**Confidence**: {evaluation['confidence']:.1f}%\n")
        report.append(f"**Score**: {evaluation['score']}/{evaluation['max_score']}\n\n")

        report.append("## Factor Evaluation\n")
        for factor in evaluation["factors"]:
            status = "✅" if factor["met"] else "❌"
            required = " (REQUIRED)" if factor["required"] else ""
            report.append(f"- {status} **{factor['name']}**{required}: {factor['details']}\n")

        if evaluation["reasons"]:
            report.append("\n## Issues\n")
            for reason in evaluation["reasons"]:
                report.append(f"- {reason}\n")

        if evaluation["actions"]:
            report.append("\n## Recommended Actions\n")
            for action in evaluation["actions"]:
                report.append(f"- **[{action['priority'].upper()}]** {action['description']}\n")
                if "details" in action:
                    report.append(f"  {action['details']}\n")

        return "".join(report)


def main():
    """Main execution function"""
    matrix = PRDecisionMatrix()

    # Example PR data for evaluation
    example_prs = [
        {
            "number": 107,
            "type": "dependabot",
            "ci_status": "passing",
            "has_major_version_bump": False,
            "is_security_update": False,
            "has_conflicts": False,
            "total_changes": 50,
        },
        {
            "number": 104,
            "type": "security",
            "ci_status": "passing",
            "vulnerabilities_fixed": ["CVE-2024-1234"],
            "has_breaking_changes": False,
            "security_scans_status": "passed",
        },
        {
            "number": 122,
            "type": "feature",
            "ci_status": "failing",
            "has_tests": True,
            "has_documentation": False,
            "review_count": 0,
            "files_changed": 357,
        },
    ]

    # Evaluate all PRs
    results = matrix.batch_evaluate(example_prs)

    # Generate reports
    with open("decision_matrix_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Print individual evaluations
    for evaluation in results["evaluations"]:
        report = matrix.generate_decision_report(evaluation)
        print(report)
        print("-" * 80)


if __name__ == "__main__":
    main()
