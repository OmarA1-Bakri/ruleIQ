#!/usr/bin/env python3
"""
Feature PR Reviewer - Comprehensive review for large feature PRs
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict
import logging
from github_api_client import GitHubAPIClient, PRInfo

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class FeaturePRReviewer:
    """Reviews and analyzes large feature pull requests"""

    def __init__(self, client: GitHubAPIClient = None, config: Dict = None) -> None:
        """Initialize feature PR reviewer"""
        self.client = client or GitHubAPIClient()
        self.config = config or {}
        self.thresholds = self.config.get(
            "thresholds",
            {
                "large_pr": {"additions": 1000, "files": 50},
                "extra_large_pr": {"additions": 5000, "files": 100},
                "massive_pr": {"additions": 10000, "files": 200},
            },
        )

    def review_feature_pr(self, pr_number: int) -> Dict:
        """Perform comprehensive review of a feature PR"""
        logger.info(f"Starting comprehensive review of PR #{pr_number}")

        pr = self.client.get_pr(pr_number)
        if not pr:
            return {"error": f"PR #{pr_number} not found"}

        review = {
            "pr_number": pr_number,
            "title": pr.title,
            "author": pr.author,
            "size_analysis": self._analyze_pr_size(pr),
            "component_breakdown": self._analyze_components(pr),
            "impact_assessment": self._assess_impact(pr),
            "test_coverage": self._analyze_test_coverage(pr),
            "code_quality": self._assess_code_quality(pr),
            "breaking_changes": self._identify_breaking_changes(pr),
            "merge_strategy": self._recommend_merge_strategy(pr),
            "recommendations": [],
        }

        review["recommendations"] = self._generate_recommendations(review)
        return review

    def _analyze_pr_size(self, pr: PRInfo) -> Dict:
        """Analyze PR size and complexity"""
        total_changes = pr.additions + pr.deletions

        size_category = "small"
        if total_changes >= self.thresholds["massive_pr"]["additions"]:
            size_category = "massive"
        elif total_changes >= self.thresholds["extra_large_pr"]["additions"]:
            size_category = "extra_large"
        elif total_changes >= self.thresholds["large_pr"]["additions"]:
            size_category = "large"
        elif total_changes >= 500:
            size_category = "medium"

        return {
            "category": size_category,
            "additions": pr.additions,
            "deletions": pr.deletions,
            "total_changes": total_changes,
            "files_changed": pr.changed_files,
            "complexity_score": self._calculate_complexity_score(pr),
        }

    def _calculate_complexity_score(self, pr: PRInfo) -> int:
        """Calculate complexity score for PR"""
        score = 0
        score += min(pr.additions // 100, 50)
        score += min(pr.changed_files // 5, 30)
        score += min(pr.deletions // 200, 20)
        return min(score, 100)

    def _analyze_components(self, pr: PRInfo) -> Dict:
        """Break down changes by component"""
        files = self.client.get_pr_files(pr.number)
        components = {
            "api": {"files": 0, "changes": 0},
            "frontend": {"files": 0, "changes": 0},
            "database": {"files": 0, "changes": 0},
            "tests": {"files": 0, "changes": 0},
            "docs": {"files": 0, "changes": 0},
            "config": {"files": 0, "changes": 0},
            "other": {"files": 0, "changes": 0},
        }

        for file in files:
            path = file["filename"].lower()
            changes = file.get("additions", 0) + file.get("deletions", 0)

            if "api" in path or "backend" in path:
                component = "api"
            elif "frontend" in path or "client" in path or "components" in path:
                component = "frontend"
            elif "database" in path or "migrations" in path or "models" in path:
                component = "database"
            elif "test" in path or "spec" in path:
                component = "tests"
            elif "doc" in path or "readme" in path:
                component = "docs"
            elif "config" in path or "settings" in path:
                component = "config"
            else:
                component = "other"

            components[component]["files"] += 1
            components[component]["changes"] += changes

        return components

    def _assess_impact(self, pr: PRInfo) -> Dict:
        """Assess potential impact of changes"""
        impact = {"level": "low", "areas": [], "risks": [], "benefits": []}

        components = self._analyze_components(pr)

        # Determine impact level
        if pr.changed_files > 100 or pr.additions > 5000:
            impact["level"] = "critical"
        elif pr.changed_files > 50 or pr.additions > 1000:
            impact["level"] = "high"
        elif pr.changed_files > 20 or pr.additions > 500:
            impact["level"] = "medium"

        # Identify affected areas
        for comp, data in components.items():
            if data["files"] > 0:
                impact["areas"].append(
                    {
                        "component": comp,
                        "files": data["files"],
                        "severity": "high"
                        if data["files"] > 20
                        else "medium"
                        if data["files"] > 5
                        else "low",
                    }
                )

        # Identify risks
        if components["database"]["files"] > 0:
            impact["risks"].append("Database schema changes may require migration")
        if components["api"]["files"] > 10:
            impact["risks"].append("API changes may affect external integrations")
        if pr.conflicts:
            impact["risks"].append("Merge conflicts need resolution")

        return impact

    def _analyze_test_coverage(self, pr: PRInfo) -> Dict:
        """Analyze test coverage for PR"""
        files = self.client.get_pr_files(pr.number)

        test_files = [f for f in files if "test" in f["filename"].lower()]
        code_files = [
            f
            for f in files
            if "test" not in f["filename"].lower()
            and not f["filename"].endswith((".md", ".json", ".yaml", ".yml"))
        ]

        return {
            "test_files": len(test_files),
            "code_files": len(code_files),
            "test_ratio": len(test_files) / max(len(code_files), 1),
            "has_tests": len(test_files) > 0,
            "adequate_tests": len(test_files) >= len(code_files) * 0.3,
        }

    def _assess_code_quality(self, pr: PRInfo) -> Dict:
        """Assess code quality metrics"""
        checks = self.client.get_pr_status_checks(pr.number)

        quality_checks = {
            "linting": "unknown",
            "formatting": "unknown",
            "type_checking": "unknown",
            "security": "unknown",
        }

        for check_name, status in checks.items():
            check_lower = check_name.lower()
            if "lint" in check_lower or "eslint" in check_lower or "pylint" in check_lower:
                quality_checks["linting"] = status
            elif "format" in check_lower or "prettier" in check_lower or "black" in check_lower:
                quality_checks["formatting"] = status
            elif "type" in check_lower or "mypy" in check_lower or "typescript" in check_lower:
                quality_checks["type_checking"] = status
            elif "security" in check_lower or "bandit" in check_lower:
                quality_checks["security"] = status

        passed_checks = sum(
            1 for status in quality_checks.values() if status in ["success", "passed"]
        )
        total_checks = sum(1 for status in quality_checks.values() if status != "unknown")

        return {
            "checks": quality_checks,
            "passed": passed_checks,
            "total": total_checks,
            "quality_score": (passed_checks / max(total_checks, 1)) * 100
            if total_checks > 0
            else 0,
        }

    def _identify_breaking_changes(self, pr: PRInfo) -> Dict:
        """Identify potential breaking changes"""
        breaking_changes = {"detected": False, "indicators": [], "files": []}

        # Check PR description
        if pr.body:
            breaking_keywords = ["breaking", "migration", "incompatible", "deprecated"]
            for keyword in breaking_keywords:
                if keyword in pr.body.lower():
                    breaking_changes["detected"] = True
                    breaking_changes["indicators"].append(f'Keyword "{keyword}" in description')

        # Check files
        files = self.client.get_pr_files(pr.number)
        for file in files:
            filename = file["filename"]
            if "migration" in filename.lower():
                breaking_changes["detected"] = True
                breaking_changes["files"].append(filename)
            if "api" in filename.lower() and file.get("deletions", 0) > 50:
                breaking_changes["indicators"].append(f"Large API deletions in {filename}")

        return breaking_changes

    def _recommend_merge_strategy(self, pr: PRInfo) -> Dict:
        """Recommend merge strategy for the PR"""
        size_analysis = self._analyze_pr_size(pr)

        if size_analysis["category"] in ["massive", "extra_large"]:
            return {
                "strategy": "staged",
                "reason": "PR is too large for single merge",
                "steps": [
                    "Split into smaller, logical commits",
                    "Review and merge infrastructure changes first",
                    "Deploy and test each component separately",
                    "Final integration and testing",
                ],
            }
        elif pr.conflicts:
            return {
                "strategy": "rebase_first",
                "reason": "Conflicts need resolution",
                "steps": [
                    "Resolve conflicts locally",
                    "Rebase on latest main",
                    "Ensure all tests pass",
                    "Merge using squash or merge commit",
                ],
            }
        else:
            return {
                "strategy": "standard",
                "reason": "PR can be merged normally",
                "steps": ["Final review", "Ensure CI passes", "Merge using configured strategy"],
            }

    def _generate_recommendations(self, review: Dict) -> List[Dict]:
        """Generate specific recommendations"""
        recommendations = []

        # Size recommendations
        if review["size_analysis"]["category"] in ["massive", "extra_large"]:
            recommendations.append(
                {
                    "priority": "high",
                    "type": "split_pr",
                    "message": "Consider splitting this PR into smaller, focused changes",
                }
            )

        # Test recommendations
        if not review["test_coverage"]["has_tests"]:
            recommendations.append(
                {
                    "priority": "critical",
                    "type": "add_tests",
                    "message": "No tests found - add comprehensive test coverage",
                }
            )
        elif not review["test_coverage"]["adequate_tests"]:
            recommendations.append(
                {
                    "priority": "high",
                    "type": "improve_tests",
                    "message": "Test coverage appears insufficient for the changes",
                }
            )

        # Breaking changes
        if review["breaking_changes"]["detected"]:
            recommendations.append(
                {
                    "priority": "critical",
                    "type": "document_breaking",
                    "message": "Document breaking changes and provide migration guide",
                }
            )

        # Code quality
        if review["code_quality"]["quality_score"] < 50:
            recommendations.append(
                {
                    "priority": "high",
                    "type": "fix_quality",
                    "message": "Address code quality issues before merging",
                }
            )

        return recommendations

    def generate_report(self, review: Dict) -> str:
        """Generate detailed review report"""
        report = [f"# Feature PR Review: PR #{review['pr_number']}\n"]
        report.append(f"## {review['title']}\n")
        report.append(f"Author: {review['author']}\n\n")

        # Size Analysis
        size = review["size_analysis"]
        report.append("## Size Analysis\n")
        report.append(f"- **Category**: {size['category'].upper()}\n")
        report.append(
            f"- **Total Changes**: {size['total_changes']} "
            f"(+{size['additions']}/-{size['deletions']})\n"
        )
        report.append(f"- **Files Changed**: {size['files_changed']}\n")
        report.append(f"- **Complexity Score**: {size['complexity_score']}/100\n\n")

        # Component Breakdown
        report.append("## Component Breakdown\n")
        for comp, data in review["component_breakdown"].items():
            if data["files"] > 0:
                report.append(
                    f"- **{comp.title()}**: {data['files']} files, {data['changes']} changes\n"
                )

        # Impact Assessment
        impact = review["impact_assessment"]
        report.append("\n## Impact Assessment\n")
        report.append(f"- **Impact Level**: {impact['level'].upper()}\n")
        if impact["risks"]:
            report.append("### Risks\n")
            for risk in impact["risks"]:
                report.append(f"- {risk}\n")

        # Test Coverage
        tests = review["test_coverage"]
        report.append("\n## Test Coverage\n")
        report.append(f"- **Test Files**: {tests['test_files']}\n")
        report.append(f"- **Code Files**: {tests['code_files']}\n")
        report.append(f"- **Coverage Ratio**: {tests['test_ratio']:.2%}\n")
        report.append(f"- **Adequate Tests**: {'✅' if tests['adequate_tests'] else '❌'}\n")

        # Recommendations
        if review["recommendations"]:
            report.append("\n## Recommendations\n")
            for rec in sorted(
                review["recommendations"],
                key=lambda x: ["low", "medium", "high", "critical"].index(x["priority"]),
            ):
                report.append(f"- **[{rec['priority'].upper()}]** {rec['message']}\n")

        # Merge Strategy
        strategy = review["merge_strategy"]
        report.append("\n## Recommended Merge Strategy\n")
        report.append(f"**Strategy**: {strategy['strategy'].replace('_', ' ').title()}\n")
        report.append(f"**Reason**: {strategy['reason']}\n")
        report.append("### Steps:\n")
        for i, step in enumerate(strategy["steps"], 1):
            report.append(f"{i}. {step}\n")

        return "".join(report)


def main():
    """Main execution function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Review feature PRs")
    parser.add_argument("--pr", type=int, help="PR number to review")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no actual changes)")
    parser.add_argument(
        "--report-file", type=str, default="feature_pr_review.md", help="Path to save report file"
    )
    args = parser.parse_args()

    # Load configuration
    config = None
    config_path = args.config if args.config else Path(__file__).with_name("config.yaml")
    if config_path:
        config_path = Path(config_path)
        if config_path.exists():
            try:
                import yaml

                with open(config_path, "r") as f:
                    full_config = yaml.safe_load(f)
                    config = full_config.get("feature_review", {})
                    logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.warning(f"Error loading config: {e}, using defaults")

    # Initialize reviewer
    client = GitHubAPIClient(dry_run=args.dry_run)
    reviewer = FeaturePRReviewer(client=client, config=config or {})

    # Use provided PR number or default
    pr_number = args.pr if args.pr else 122

    # Review the PR
    review = reviewer.review_feature_pr(pr_number)

    # Generate and save report
    report = reviewer.generate_report(review)

    with open(args.report_file, "w") as f:
        f.write(report)
    print(f"Feature PR review saved to {args.report_file}")

    # Save JSON results
    results_file = args.report_file.replace(".md", ".json")
    with open(results_file, "w") as f:
        json.dump(review, f, indent=2, default=str)

    # Print summary
    print(f"\n{report}")


if __name__ == "__main__":
    main()
