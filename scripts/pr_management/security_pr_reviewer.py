#!/usr/bin/env python3
"""
Security PR Reviewer - Security-focused review for Aikido and security-related PRs
"""

import argparse
import json
import re
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import logging
from github_api_client import GitHubAPIClient, PRInfo

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SecurityPRReviewer:
    """Reviews and validates security-related pull requests"""

    def __init__(self, client: GitHubAPIClient = None, config: Dict = None) -> None:
        """Initialize security PR reviewer"""
        self.client = client or GitHubAPIClient()
        self.config = config or {}
        self.security_patterns = self._load_security_patterns()
        self.severity_levels = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

    def _load_security_patterns(self) -> Dict:
        """Load security patterns and indicators"""
        return {
            "vulnerabilities": [
                "CVE-",
                "GHSA-",
                "vulnerability",
                "exploit",
                "injection",
                "XSS",
                "CSRF",
                "SQL injection",
                "buffer overflow",
                "RCE",
            ],
            "security_fixes": [
                "security fix",
                "patch",
                "sanitize",
                "escape",
                "validate",
                "authentication",
                "authorization",
                "encryption",
                "hash",
            ],
            "risky_changes": [
                "disable",
                "bypass",
                "skip",
                "ignore",
                "allow",
                "permit",
                "trust",
                "unsafe",
                "dangerous",
                "eval",
                "exec",
            ],
            "sensitive_files": [
                "auth",
                "security",
                "crypto",
                "password",
                "token",
                "key",
                "secret",
                "credential",
                "permission",
                "access",
            ],
        }

    def review_security_prs(self, pr_numbers: List[int] = None) -> Dict:
        """Review security-related PRs"""
        logger.info("Starting security PR review...")

        # Get PRs to review
        if pr_numbers:
            prs = [self.client.get_pr(num) for num in pr_numbers]
            prs = [pr for pr in prs if pr]  # Filter out None
        else:
            # Get all security-related PRs
            all_prs = self.client.get_all_open_prs()
            prs = [pr for pr in all_prs if self._is_security_pr(pr)]

        logger.info(f"Found {len(prs)} security PRs to review")

        results = {
            "timestamp": datetime.now().isoformat(),
            "total_prs": len(prs),
            "reviews": [],
            "summary": {},
            "recommendations": [],
        }

        for pr in prs:
            review = self._review_single_pr(pr)
            results["reviews"].append(review)

        # Generate summary and recommendations
        results["summary"] = self._generate_summary(results["reviews"])
        results["recommendations"] = self._generate_recommendations(results["reviews"])

        return results

    def _is_security_pr(self, pr: PRInfo) -> bool:
        """Determine if a PR is security-related"""
        # Check if explicitly marked as security
        if pr.is_security:
            return True

        # Check title and body for security keywords
        text = f"{pr.title} {pr.body or ''}".lower()
        for pattern in (
            self.security_patterns["vulnerabilities"] + self.security_patterns["security_fixes"]
        ):
            if pattern.lower() in text:
                return True

        # Check if from security tools (Aikido, Snyk, etc.)
        security_authors = ["aikido", "snyk", "dependabot[bot]", "github-actions"]
        if any(author in pr.author.lower() for author in security_authors):
            if "security" in text or "vulnerability" in text:
                return True

        return False

    def _review_single_pr(self, pr: PRInfo) -> Dict:
        """Perform detailed review of a single security PR"""
        logger.info(f"Reviewing security PR #{pr.number}: {pr.title}")

        review = {
            "pr_number": pr.number,
            "title": pr.title,
            "author": pr.author,
            "security_assessment": {},
            "risk_assessment": {},
            "validation_results": {},
            "recommendations": [],
            "approval_status": "pending",
        }

        # Perform security assessment
        review["security_assessment"] = self._assess_security_impact(pr)

        # Perform risk assessment
        review["risk_assessment"] = self._assess_risk(pr)

        # Validate the changes
        review["validation_results"] = self._validate_security_changes(pr)

        # Check CI/CD status
        ci_status = self._check_security_scans(pr)
        review["ci_status"] = ci_status

        # Generate recommendations
        review["recommendations"] = self._generate_pr_recommendations(pr, review)

        # Determine approval status
        review["approval_status"] = self._determine_approval_status(review)

        return review

    def _assess_security_impact(self, pr: PRInfo) -> Dict:
        """Assess the security impact of the PR"""
        assessment = {
            "severity": "unknown",
            "vulnerabilities_fixed": [],
            "security_improvements": [],
            "potential_issues": [],
            "affected_components": [],
        }

        # Parse PR description for CVE/GHSA references
        if pr.body:
            cve_pattern = r"CVE-\d{4}-\d+"
            ghsa_pattern = r"GHSA-[\w-]+"

            cves = re.findall(cve_pattern, pr.body)
            ghsas = re.findall(ghsa_pattern, pr.body)

            assessment["vulnerabilities_fixed"].extend(cves)
            assessment["vulnerabilities_fixed"].extend(ghsas)

        # Analyze files changed
        files = self.client.get_pr_files(pr.number)
        for file in files:
            filename = file["filename"]

            # Check if sensitive file
            if any(
                pattern in filename.lower() for pattern in self.security_patterns["sensitive_files"]
            ):
                assessment["affected_components"].append(
                    {
                        "file": filename,
                        "type": "sensitive",
                        "changes": f"+{file.get('additions', 0)}/-{file.get('deletions', 0)}",
                    }
                )

            # Analyze patch content if available
            if "patch" in file:
                patch = file["patch"]

                # Check for security improvements
                for pattern in self.security_patterns["security_fixes"]:
                    if pattern in patch:
                        assessment["security_improvements"].append(
                            {"file": filename, "pattern": pattern}
                        )

                # Check for risky changes
                for pattern in self.security_patterns["risky_changes"]:
                    if pattern in patch and f"-{pattern}" not in patch:  # Added, not removed
                        assessment["potential_issues"].append(
                            {
                                "file": filename,
                                "issue": f"Potentially risky pattern: {pattern}",
                                "severity": "medium",
                            }
                        )

        # Determine overall severity
        if assessment["vulnerabilities_fixed"]:
            if any("critical" in vuln.lower() for vuln in assessment["vulnerabilities_fixed"]):
                assessment["severity"] = "critical"
            else:
                assessment["severity"] = "high"
        elif assessment["security_improvements"]:
            assessment["severity"] = "medium"
        elif assessment["potential_issues"]:
            assessment["severity"] = "low"
        else:
            assessment["severity"] = "info"

        return assessment

    def _assess_risk(self, pr: PRInfo) -> Dict:
        """Assess the risk associated with the PR"""
        risk = {"level": "low", "factors": [], "score": 0}

        # Size risk
        if pr.additions + pr.deletions > 1000:
            risk["factors"].append("large_change_size")
            risk["score"] += 3
        elif pr.additions + pr.deletions > 500:
            risk["factors"].append("medium_change_size")
            risk["score"] += 2

        # Files changed risk
        if pr.changed_files > 20:
            risk["factors"].append("many_files_changed")
            risk["score"] += 2

        # Sensitive files risk
        files = self.client.get_pr_files(pr.number)
        sensitive_count = sum(
            1
            for f in files
            if any(p in f["filename"].lower() for p in self.security_patterns["sensitive_files"])
        )
        if sensitive_count > 5:
            risk["factors"].append("multiple_sensitive_files")
            risk["score"] += 3
        elif sensitive_count > 0:
            risk["factors"].append("sensitive_files_modified")
            risk["score"] += 1

        # Author trust
        trusted_authors = ["aikido", "dependabot[bot]", "github-actions"]
        if not any(author in pr.author.lower() for author in trusted_authors):
            risk["factors"].append("manual_pr")
            risk["score"] += 1

        # Age risk
        age_days = (datetime.now(pr.created_at.tzinfo) - pr.created_at).days
        if age_days > 30:
            risk["factors"].append("stale_pr")
            risk["score"] += 2

        # Determine risk level
        if risk["score"] >= 7:
            risk["level"] = "high"
        elif risk["score"] >= 4:
            risk["level"] = "medium"
        else:
            risk["level"] = "low"

        return risk

    def _validate_security_changes(self, pr: PRInfo) -> Dict:
        """Validate that security changes are properly implemented"""
        validation = {
            "tests_added": False,
            "documentation_updated": False,
            "breaking_changes": False,
            "security_scans_passed": False,
            "review_required": True,
            "issues": [],
        }

        files = self.client.get_pr_files(pr.number)

        # Check for test files
        test_files = [f for f in files if "test" in f["filename"].lower()]
        validation["tests_added"] = len(test_files) > 0

        # Check for documentation updates
        doc_files = [
            f
            for f in files
            if any(ext in f["filename"].lower() for ext in [".md", ".rst", ".txt", "doc"])
        ]
        validation["documentation_updated"] = len(doc_files) > 0

        # Check for breaking changes indicators
        if pr.body:
            breaking_indicators = ["breaking", "incompatible", "migration", "upgrade"]
            validation["breaking_changes"] = any(
                ind in pr.body.lower() for ind in breaking_indicators
            )

        # Check security scan status
        checks = self.client.get_pr_status_checks(pr.number)
        security_checks = {
            k: v
            for k, v in checks.items()
            if any(sec in k.lower() for sec in ["security", "aikido", "snyk", "codeql"])
        }

        validation["security_scans_passed"] = all(
            status in ["success", "passed"] for status in security_checks.values()
        )

        # Identify issues
        if not validation["tests_added"]:
            validation["issues"].append(
                {
                    "type": "missing_tests",
                    "severity": "medium",
                    "message": "No test files found for security changes",
                }
            )

        if not validation["documentation_updated"]:
            validation["issues"].append(
                {
                    "type": "missing_docs",
                    "severity": "low",
                    "message": "Documentation not updated for security changes",
                }
            )

        if validation["breaking_changes"]:
            validation["issues"].append(
                {
                    "type": "breaking_changes",
                    "severity": "high",
                    "message": "PR contains breaking changes that require careful review",
                }
            )

        if not validation["security_scans_passed"]:
            validation["issues"].append(
                {
                    "type": "failed_security_scans",
                    "severity": "critical",
                    "message": "Security scans have not passed",
                }
            )

        return validation

    def _check_security_scans(self, pr: PRInfo) -> Dict:
        """Check status of security scanning tools"""
        checks = self.client.get_pr_status_checks(pr.number)

        security_tools = {
            "aikido": False,
            "codeql": False,
            "snyk": False,
            "bandit": False,
            "safety": False,
            "trivy": False,
        }

        results = {
            "tools_run": [],
            "tools_passed": [],
            "tools_failed": [],
            "overall_status": "unknown",
        }

        for check_name, status in checks.items():
            check_lower = check_name.lower()

            for tool in security_tools:
                if tool in check_lower:
                    security_tools[tool] = True
                    results["tools_run"].append(tool)

                    if status in ["success", "passed"]:
                        results["tools_passed"].append(tool)
                    elif status in ["failure", "failed", "error"]:
                        results["tools_failed"].append(tool)

        # Determine overall status
        if results["tools_failed"]:
            results["overall_status"] = "failed"
        elif results["tools_passed"] and not results["tools_failed"]:
            results["overall_status"] = "passed"
        elif results["tools_run"]:
            results["overall_status"] = "pending"
        else:
            results["overall_status"] = "no_scans"

        return results

    def _generate_pr_recommendations(self, pr: PRInfo, review: Dict) -> List[Dict]:
        """Generate specific recommendations for a PR"""
        recommendations = []

        # Based on security assessment
        assessment = review["security_assessment"]
        if assessment["severity"] in ["critical", "high"]:
            recommendations.append(
                {
                    "priority": "high",
                    "action": "urgent_merge",
                    "reason": f"Fixes {assessment['severity']} severity vulnerabilities",
                }
            )

        # Based on validation results
        validation = review["validation_results"]
        for issue in validation["issues"]:
            if issue["severity"] == "critical":
                recommendations.append(
                    {"priority": "critical", "action": "fix_required", "reason": issue["message"]}
                )
            elif issue["severity"] == "high":
                recommendations.append(
                    {"priority": "high", "action": "review_required", "reason": issue["message"]}
                )

        # Based on risk assessment
        risk = review["risk_assessment"]
        if risk["level"] == "high":
            recommendations.append(
                {
                    "priority": "medium",
                    "action": "careful_review",
                    "reason": f"High risk due to: {', '.join(risk['factors'])}",
                }
            )

        # Based on CI status
        if review["ci_status"]["overall_status"] == "failed":
            recommendations.append(
                {
                    "priority": "high",
                    "action": "fix_ci",
                    "reason": f"Security scans failed: {', '.join(review['ci_status']['tools_failed'])}",
                }
            )

        return recommendations

    def _determine_approval_status(self, review: Dict) -> str:
        """Determine if PR should be approved"""
        # Check for critical issues
        validation = review["validation_results"]
        has_critical_issues = any(issue["severity"] == "critical" for issue in validation["issues"])

        if has_critical_issues:
            return "blocked"

        # Check CI status
        if review["ci_status"]["overall_status"] == "failed":
            return "ci_failed"

        # Check risk level
        if review["risk_assessment"]["level"] == "high":
            return "needs_review"

        # Check security severity
        if review["security_assessment"]["severity"] in ["critical", "high"]:
            if review["ci_status"]["overall_status"] == "passed":
                return "approved_urgent"
            else:
                return "pending_ci"

        # Default
        return "approved"

    def _generate_summary(self, reviews: List[Dict]) -> Dict:
        """Generate summary of all reviews"""
        summary = {
            "total_reviewed": len(reviews),
            "by_severity": {},
            "by_status": {},
            "critical_issues": [],
            "urgent_merges": [],
        }

        for review in reviews:
            # Count by severity
            severity = review["security_assessment"]["severity"]
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1

            # Count by status
            status = review["approval_status"]
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1

            # Identify critical issues
            if status == "blocked":
                summary["critical_issues"].append(review["pr_number"])

            # Identify urgent merges
            if status == "approved_urgent":
                summary["urgent_merges"].append(review["pr_number"])

        return summary

    def _generate_recommendations(self, reviews: List[Dict]) -> List[Dict]:
        """Generate overall recommendations"""
        recommendations = []

        # Urgent merges
        urgent = [r["pr_number"] for r in reviews if r["approval_status"] == "approved_urgent"]
        if urgent:
            recommendations.append(
                {
                    "priority": "critical",
                    "action": "merge_urgent_security_fixes",
                    "prs": urgent,
                    "reason": "Critical security vulnerabilities fixed",
                }
            )

        # Fix CI failures
        ci_failed = [
            r["pr_number"] for r in reviews if r["ci_status"]["overall_status"] == "failed"
        ]
        if ci_failed:
            recommendations.append(
                {
                    "priority": "high",
                    "action": "fix_security_scan_failures",
                    "prs": ci_failed,
                    "reason": "Security scans must pass before merge",
                }
            )

        # Manual review needed
        needs_review = [r["pr_number"] for r in reviews if r["approval_status"] == "needs_review"]
        if needs_review:
            recommendations.append(
                {
                    "priority": "medium",
                    "action": "manual_security_review",
                    "prs": needs_review,
                    "reason": "High-risk changes require careful review",
                }
            )

        return recommendations

    def generate_report(self, results: Dict) -> str:
        """Generate detailed security review report"""
        report = ["# Security PR Review Report\n"]
        report.append(f"Generated: {results['timestamp']}\n")
        report.append(f"Total PRs Reviewed: {results['total_prs']}\n")

        # Summary section
        summary = results["summary"]
        report.append("\n## Summary\n")
        report.append("\n### By Severity\n")
        for severity, count in summary["by_severity"].items():
            report.append(f"- {severity.upper()}: {count}\n")

        report.append("\n### By Status\n")
        for status, count in summary["by_status"].items():
            report.append(f"- {status.replace('_', ' ').title()}: {count}\n")

        # Critical issues
        if summary["critical_issues"]:
            report.append("\n## ⚠️ Critical Issues\n")
            for pr_num in summary["critical_issues"]:
                review = next(r for r in results["reviews"] if r["pr_number"] == pr_num)
                report.append(f"\n### PR #{pr_num}: {review['title']}\n")
                for issue in review["validation_results"]["issues"]:
                    if issue["severity"] == "critical":
                        report.append(f"- {issue['message']}\n")

        # Urgent merges
        if summary["urgent_merges"]:
            report.append("\n## 🚨 Urgent Merges Required\n")
            for pr_num in summary["urgent_merges"]:
                review = next(r for r in results["reviews"] if r["pr_number"] == pr_num)
                report.append(f"- PR #{pr_num}: {review['title']}\n")
                vulns = review["security_assessment"]["vulnerabilities_fixed"]
                if vulns:
                    report.append(f"  Fixes: {', '.join(vulns)}\n")

        # Detailed reviews
        report.append("\n## Detailed Reviews\n")
        for review in results["reviews"]:
            report.append(f"\n### PR #{review['pr_number']}: {review['title']}\n")
            report.append(f"- **Author**: {review['author']}\n")
            report.append(f"- **Severity**: {review['security_assessment']['severity']}\n")
            report.append(f"- **Risk Level**: {review['risk_assessment']['level']}\n")
            report.append(f"- **Approval Status**: {review['approval_status']}\n")
            report.append(f"- **CI Status**: {review['ci_status']['overall_status']}\n")

            if review["recommendations"]:
                report.append("\n**Recommendations**:\n")
                for rec in review["recommendations"]:
                    report.append(f"- [{rec['priority'].upper()}] {rec['reason']}\n")

        # Overall recommendations
        if results["recommendations"]:
            report.append("\n## Overall Recommendations\n")
            for rec in results["recommendations"]:
                report.append(f"\n### {rec['action'].replace('_', ' ').title()}\n")
                report.append(f"- **Priority**: {rec['priority'].upper()}\n")
                report.append(f"- **Reason**: {rec['reason']}\n")
                report.append(f"- **PRs**: {', '.join(f'#{pr}' for pr in rec['prs'][:10])}\n")

        return "".join(report)


def main():
    """Main execution function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Review security PRs")
    parser.add_argument("--prs", type=str, help="Comma-separated list of PR numbers to review")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no actual changes)")
    parser.add_argument(
        "--report-file",
        type=str,
        default="security_review_report.md",
        help="Path to save report file",
    )
    args = parser.parse_args()

    # Parse PR numbers if provided
    pr_numbers = None
    if args.prs:
        try:
            pr_numbers = [int(pr.strip()) for pr in args.prs.split(",")]
            logger.info(f"Reviewing specific PRs: {pr_numbers}")
        except ValueError:
            logger.error(f"Invalid PR numbers format: {args.prs}")
            return

    # Load configuration if provided
    config = None
    config_path = Path(args.config) if args.config else Path(__file__).with_name("config.yaml")

    if config_path.exists():
        try:
            import yaml

            with open(config_path, "r") as f:
                full_config = yaml.safe_load(f)
                config = full_config.get("security_review", {})
                logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.warning(f"Error loading config: {e}, using defaults")

    # Initialize reviewer
    client = GitHubAPIClient(dry_run=args.dry_run)
    reviewer = SecurityPRReviewer(client=client, config=config)

    # Review PRs (auto-detect if no specific PRs provided)
    results = reviewer.review_security_prs(pr_numbers)

    # Generate and save report
    report = reviewer.generate_report(results)

    with open(args.report_file, "w") as f:
        f.write(report)
    print(f"Security review report saved to {args.report_file}")

    # Save JSON results
    with open("security_review_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    print(f"\n{report}")


if __name__ == "__main__":
    main()
