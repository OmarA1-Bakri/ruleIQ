#!/usr/bin/env python3
"""
PR Analyzer - Comprehensive analysis and categorization of all open pull requests
"""

import json
from typing import List, Dict
from datetime import datetime
from collections import defaultdict
import logging
from github_api_client import GitHubAPIClient, PRInfo

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PRAnalyzer:
    """Analyzes and categorizes pull requests with detailed insights"""

    def __init__(self, client: GitHubAPIClient = None) -> None:
        """Initialize PR Analyzer"""
        self.client = client or GitHubAPIClient()
        self.analysis_results = {
            "summary": {},
            "categories": {},
            "recommendations": [],
            "risks": [],
            "dependencies": [],
            "conflicts": [],
            "priority_order": [],
        }

    def analyze_all_prs(self) -> Dict:
        """Perform comprehensive analysis of all open PRs"""
        logger.info("Starting comprehensive PR analysis...")

        # Fetch all open PRs
        prs = self.client.get_all_open_prs()
        logger.info(f"Found {len(prs)} open pull requests")

        # Categorize PRs
        categorized = self._categorize_prs(prs)

        # Analyze each category
        for category, pr_list in categorized.items():
            self.analysis_results["categories"][category] = self._analyze_category(
                category, pr_list
            )

        # Generate summary
        self.analysis_results["summary"] = self._generate_summary(prs, categorized)

        # Identify dependencies and conflicts
        self._identify_dependencies(prs)
        self._identify_conflicts(prs)

        # Generate recommendations
        self._generate_recommendations(categorized)

        # Calculate priority order
        self.analysis_results["priority_order"] = self._calculate_priority_order(prs)

        # Identify risks
        self._identify_risks(prs)

        return self.analysis_results

    def _categorize_prs(self, prs: List[PRInfo]) -> Dict[str, List[PRInfo]]:
        """Categorize PRs by type"""
        categories = defaultdict(list)

        for pr in prs:
            if pr.is_dependabot:
                categories["dependabot"].append(pr)
            elif pr.is_security or "security" in pr.title.lower():
                categories["security"].append(pr)
            elif pr.changed_files > 50 or pr.additions > 1000:
                categories["feature"].append(pr)
            elif "fix" in pr.title.lower() or "bug" in pr.title.lower():
                categories["bugfix"].append(pr)
            elif "doc" in pr.title.lower() or "readme" in pr.title.lower():
                categories["documentation"].append(pr)
            else:
                categories["other"].append(pr)

        return dict(categories)

    def _analyze_category(self, category: str, prs: List[PRInfo]) -> Dict:
        """Analyze a specific category of PRs"""
        analysis = {
            "count": len(prs),
            "prs": [],
            "total_additions": sum(pr.additions for pr in prs),
            "total_deletions": sum(pr.deletions for pr in prs),
            "total_files": sum(pr.changed_files for pr in prs),
            "avg_age_days": 0,
            "ci_status": {"passing": 0, "failing": 0, "pending": 0},
        }

        ages = []
        for pr in prs:
            age = (datetime.now(pr.created_at.tzinfo) - pr.created_at).days
            ages.append(age)

            # Check CI status
            ci_status = self._get_ci_status(pr)
            analysis["ci_status"][ci_status] += 1

            pr_summary = {
                "number": pr.number,
                "title": pr.title,
                "author": pr.author,
                "age_days": age,
                "ci_status": ci_status,
                "mergeable": pr.mergeable,
                "conflicts": pr.conflicts,
                "size": self._calculate_pr_size(pr),
                "risk_level": self._calculate_risk_level(pr),
            }
            analysis["prs"].append(pr_summary)

        if ages:
            analysis["avg_age_days"] = sum(ages) / len(ages)

        return analysis

    def _get_ci_status(self, pr: PRInfo) -> str:
        """Determine overall CI status for a PR"""
        if not pr.status_checks:
            return "pending"

        failed = any(status in ["failure", "error"] for status in pr.status_checks.values())
        pending = any(status in ["pending", None] for status in pr.status_checks.values())

        if failed:
            return "failing"
        elif pending:
            return "pending"
        else:
            return "passing"

    def _calculate_pr_size(self, pr: PRInfo) -> str:
        """Calculate PR size category"""
        total_changes = pr.additions + pr.deletions

        if total_changes < 10:
            return "tiny"
        elif total_changes < 100:
            return "small"
        elif total_changes < 500:
            return "medium"
        elif total_changes < 1000:
            return "large"
        else:
            return "extra-large"

    def _calculate_risk_level(self, pr: PRInfo) -> str:
        """Calculate risk level for a PR"""
        risk_score = 0

        # Size risk
        if pr.additions + pr.deletions > 1000:
            risk_score += 3
        elif pr.additions + pr.deletions > 500:
            risk_score += 2
        elif pr.additions + pr.deletions > 100:
            risk_score += 1

        # File count risk
        if pr.changed_files > 50:
            risk_score += 3
        elif pr.changed_files > 20:
            risk_score += 2
        elif pr.changed_files > 10:
            risk_score += 1

        # Age risk (older PRs are riskier)
        age_days = (datetime.now(pr.created_at.tzinfo) - pr.created_at).days
        if age_days > 30:
            risk_score += 2
        elif age_days > 14:
            risk_score += 1

        # Conflict risk
        if pr.conflicts:
            risk_score += 3

        # Security risk
        if pr.is_security:
            risk_score -= 1  # Security PRs should be prioritized

        if risk_score <= 2:
            return "low"
        elif risk_score <= 5:
            return "medium"
        else:
            return "high"

    def _generate_summary(self, prs: List[PRInfo], categorized: Dict) -> Dict:
        """Generate overall summary statistics"""
        total_additions = sum(pr.additions for pr in prs)
        total_deletions = sum(pr.deletions for pr in prs)
        total_files = sum(pr.changed_files for pr in prs)

        ages = [(datetime.now(pr.created_at.tzinfo) - pr.created_at).days for pr in prs]
        avg_age = sum(ages) / len(ages) if ages else 0

        return {
            "total_prs": len(prs),
            "categories": {cat: len(prs) for cat, prs in categorized.items()},
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "total_files_changed": total_files,
            "average_pr_age_days": avg_age,
            "oldest_pr_days": max(ages) if ages else 0,
            "newest_pr_days": min(ages) if ages else 0,
            "dependabot_prs": len(categorized.get("dependabot", [])),
            "security_prs": len(categorized.get("security", [])),
            "feature_prs": len(categorized.get("feature", [])),
            "with_conflicts": sum(1 for pr in prs if pr.conflicts),
            "ci_failing": sum(1 for pr in prs if self._get_ci_status(pr) == "failing"),
        }

    def _identify_dependencies(self, prs: List[PRInfo]) -> None:
        """Identify dependencies between PRs"""
        dependencies = []

        for pr in prs:
            # Check if PR mentions other PRs
            if pr.body:
                import re

                pr_refs = re.findall(r"#(\d+)", pr.body)
                for ref in pr_refs:
                    ref_num = int(ref)
                    if any(p.number == ref_num for p in prs):
                        dependencies.append(
                            {"pr": pr.number, "depends_on": ref_num, "type": "referenced"}
                        )

            # Check for branch dependencies
            for other_pr in prs:
                if pr.number != other_pr.number:
                    if pr.base_branch == other_pr.head_branch:
                        dependencies.append(
                            {"pr": pr.number, "depends_on": other_pr.number, "type": "branch"}
                        )

        self.analysis_results["dependencies"] = dependencies

    def _identify_conflicts(self, prs: List[PRInfo]) -> None:
        """Identify potential conflicts between PRs"""
        conflicts = []

        # Get files changed for each PR
        pr_files = {}
        for pr in prs:
            files = self.client.get_pr_files(pr.number)
            pr_files[pr.number] = [f["filename"] for f in files]

        # Check for file overlap
        for i, pr1 in enumerate(prs):
            for pr2 in prs[i + 1 :]:
                overlapping_files = set(pr_files.get(pr1.number, [])) & set(
                    pr_files.get(pr2.number, [])
                )
                if overlapping_files:
                    conflicts.append(
                        {
                            "pr1": pr1.number,
                            "pr2": pr2.number,
                            "conflicting_files": list(overlapping_files),
                            "severity": "high" if len(overlapping_files) > 5 else "medium",
                        }
                    )

        self.analysis_results["conflicts"] = conflicts

    def _generate_recommendations(self, categorized: Dict) -> None:
        """Generate actionable recommendations"""
        recommendations = []

        # Dependabot recommendations
        if "dependabot" in categorized:
            passing_dependabot = [
                pr for pr in categorized["dependabot"] if self._get_ci_status(pr) == "passing"
            ]
            if passing_dependabot:
                recommendations.append(
                    {
                        "type": "auto-merge",
                        "priority": "medium",
                        "action": f"Auto-merge {len(passing_dependabot)} Dependabot PRs with passing CI",
                        "prs": [pr.number for pr in passing_dependabot],
                    }
                )

        # Security recommendations
        if "security" in categorized:
            recommendations.append(
                {
                    "type": "manual-review",
                    "priority": "high",
                    "action": f"Urgently review {len(categorized['security'])} security PRs",
                    "prs": [pr.number for pr in categorized["security"]],
                }
            )

        # Conflict resolution
        conflicting_prs = [pr for pr in sum(categorized.values(), []) if pr.conflicts]
        if conflicting_prs:
            recommendations.append(
                {
                    "type": "conflict-resolution",
                    "priority": "high",
                    "action": f"Resolve conflicts in {len(conflicting_prs)} PRs",
                    "prs": [pr.number for pr in conflicting_prs],
                }
            )

        # Old PRs
        all_prs = sum(categorized.values(), [])
        old_prs = [
            pr for pr in all_prs if (datetime.now(pr.created_at.tzinfo) - pr.created_at).days > 30
        ]
        if old_prs:
            recommendations.append(
                {
                    "type": "cleanup",
                    "priority": "low",
                    "action": f"Review or close {len(old_prs)} stale PRs (>30 days old)",
                    "prs": [pr.number for pr in old_prs],
                }
            )

        self.analysis_results["recommendations"] = recommendations

    def _calculate_priority_order(self, prs: List[PRInfo]) -> List[Dict]:
        """Calculate optimal merge order for PRs"""
        priority_list = []

        for pr in prs:
            priority_score = 0

            # Security gets highest priority
            if pr.is_security:
                priority_score += 100

            # CI passing is important
            if self._get_ci_status(pr) == "passing":
                priority_score += 50
            elif self._get_ci_status(pr) == "failing":
                priority_score -= 50

            # Smaller PRs are easier to review
            size_score = {"tiny": 40, "small": 30, "medium": 20, "large": 10, "extra-large": 0}
            priority_score += size_score.get(self._calculate_pr_size(pr), 0)

            # No conflicts is good
            if not pr.conflicts:
                priority_score += 30

            # Dependabot PRs are usually safe
            if pr.is_dependabot:
                priority_score += 20

            # Older PRs should be handled
            age_days = (datetime.now(pr.created_at.tzinfo) - pr.created_at).days
            if age_days > 30:
                priority_score += 15
            elif age_days > 14:
                priority_score += 10
            elif age_days > 7:
                priority_score += 5

            priority_list.append(
                {
                    "pr_number": pr.number,
                    "title": pr.title,
                    "priority_score": priority_score,
                    "category": self._get_pr_category(pr),
                    "ci_status": self._get_ci_status(pr),
                    "risk_level": self._calculate_risk_level(pr),
                }
            )

        # Sort by priority score (higher is better)
        priority_list.sort(key=lambda x: x["priority_score"], reverse=True)

        return priority_list

    def _get_pr_category(self, pr: PRInfo) -> str:
        """Get category for a single PR"""
        if pr.is_dependabot:
            return "dependabot"
        elif pr.is_security or "security" in pr.title.lower():
            return "security"
        elif pr.changed_files > 50 or pr.additions > 1000:
            return "feature"
        elif "fix" in pr.title.lower() or "bug" in pr.title.lower():
            return "bugfix"
        elif "doc" in pr.title.lower() or "readme" in pr.title.lower():
            return "documentation"
        else:
            return "other"

    def _identify_risks(self, prs: List[PRInfo]) -> None:
        """Identify potential risks across all PRs"""
        risks = []

        for pr in prs:
            pr_risks = []

            # Large PR risk
            if pr.additions + pr.deletions > 5000:
                pr_risks.append(
                    {
                        "type": "size",
                        "severity": "high",
                        "description": f"Extremely large PR with {pr.additions + pr.deletions} changes",
                    }
                )

            # Old PR risk
            age_days = (datetime.now(pr.created_at.tzinfo) - pr.created_at).days
            if age_days > 60:
                pr_risks.append(
                    {
                        "type": "staleness",
                        "severity": "medium",
                        "description": f"PR is {age_days} days old and may be outdated",
                    }
                )

            # Conflict risk
            if pr.conflicts:
                pr_risks.append(
                    {
                        "type": "conflict",
                        "severity": "high",
                        "description": "PR has merge conflicts that need resolution",
                    }
                )

            # No reviews risk
            reviews = self.client.get_pr_reviews(pr.number)
            if not reviews and not pr.is_dependabot:
                pr_risks.append(
                    {"type": "review", "severity": "medium", "description": "PR has no reviews"}
                )

            if pr_risks:
                risks.append({"pr_number": pr.number, "title": pr.title, "risks": pr_risks})

        self.analysis_results["risks"] = risks

    def generate_report(self, format: str = "markdown") -> str:
        """Generate analysis report in specified format"""
        if format == "markdown":
            return self._generate_markdown_report()
        elif format == "json":
            return json.dumps(self.analysis_results, indent=2, default=str)
        else:
            return self._generate_text_report()

    def _generate_markdown_report(self) -> str:
        """Generate markdown formatted report"""
        report = ["# Pull Request Analysis Report\n"]
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Summary
        summary = self.analysis_results["summary"]
        report.append("## Summary\n")
        report.append(f"- **Total Open PRs**: {summary['total_prs']}\n")
        report.append(f"- **Average Age**: {summary['average_pr_age_days']:.1f} days\n")
        report.append(
            f"- **Total Changes**: +{summary['total_additions']}/-{summary['total_deletions']}\n"
        )
        report.append(f"- **Files Changed**: {summary['total_files_changed']}\n")
        report.append(f"- **PRs with Conflicts**: {summary['with_conflicts']}\n")
        report.append(f"- **CI Failing**: {summary['ci_failing']}\n")

        # Categories
        report.append("\n## PR Categories\n")
        for category, data in self.analysis_results["categories"].items():
            report.append(f"\n### {category.title()} ({data['count']} PRs)\n")
            report.append(f"- Changes: +{data['total_additions']}/-{data['total_deletions']}\n")
            report.append(f"- Average Age: {data['avg_age_days']:.1f} days\n")
            report.append(f"- CI Status: {data['ci_status']}\n")

            if data["prs"]:
                report.append("\n| PR | Title | Age | CI | Risk |\n")
                report.append("|-----|-------|-----|-----|------|\n")
                for pr in data["prs"][:5]:  # Show top 5
                    report.append(
                        f"| #{pr['number']} | {pr['title'][:40]}... | "
                        f"{pr['age_days']}d | {pr['ci_status']} | {pr['risk_level']} |\n"
                    )

        # Priority Order
        report.append("\n## Recommended Merge Order\n")
        priority_order = self.analysis_results["priority_order"][:10]
        report.append("\n| Priority | PR | Category | CI Status | Risk |\n")
        report.append("|----------|-----|----------|-----------|------|\n")
        for i, pr in enumerate(priority_order, 1):
            report.append(
                f"| {i} | #{pr['pr_number']} | {pr['category']} | "
                f"{pr['ci_status']} | {pr['risk_level']} |\n"
            )

        # Recommendations
        report.append("\n## Recommendations\n")
        for rec in self.analysis_results["recommendations"]:
            report.append(
                f"\n### {rec['priority'].upper()} Priority: {rec['type'].replace('-', ' ').title()}\n"
            )
            report.append(f"- **Action**: {rec['action']}\n")
            report.append(f"- **PRs**: {', '.join(f'#{pr}' for pr in rec['prs'][:10])}\n")

        # Risks
        if self.analysis_results["risks"]:
            report.append("\n## Identified Risks\n")
            for risk_pr in self.analysis_results["risks"][:5]:
                report.append(f"\n### PR #{risk_pr['pr_number']}: {risk_pr['title'][:50]}...\n")
                for risk in risk_pr["risks"]:
                    report.append(f"- **{risk['severity'].upper()}**: {risk['description']}\n")

        return "".join(report)

    def _generate_text_report(self) -> str:
        """Generate plain text report"""
        report = []
        report.append("=" * 80)
        report.append("PULL REQUEST ANALYSIS REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        summary = self.analysis_results["summary"]
        report.append(f"Total Open PRs: {summary['total_prs']}")
        report.append(f"Average Age: {summary['average_pr_age_days']:.1f} days")
        report.append(f"Total Changes: +{summary['total_additions']}/-{summary['total_deletions']}")
        report.append("")

        return "\n".join(report)

    def save_report(self, filename: str = None) -> str:
        """Save analysis report to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pr_analysis_{timestamp}.md"

        report = self.generate_report("markdown")
        with open(filename, "w") as f:
            f.write(report)

        logger.info(f"Report saved to {filename}")
        return filename


def main():
    """Main execution function"""
    analyzer = PRAnalyzer()

    # Perform analysis
    results = analyzer.analyze_all_prs()

    # Generate and save report
    report_file = analyzer.save_report()

    # Print summary to console
    print(analyzer.generate_report("markdown"))

    # Save JSON results
    json_file = report_file.replace(".md", ".json")
    with open(json_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Analysis complete. Reports saved to {report_file} and {json_file}")


if __name__ == "__main__":
    main()
