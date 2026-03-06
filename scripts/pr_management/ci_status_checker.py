#!/usr/bin/env python3
"""
CI Status Checker - Monitor and analyze CI/CD pipeline status for PRs
"""

import argparse
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
from github_api_client import GitHubAPIClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CIStatusChecker:
    """Monitors and analyzes CI/CD status for pull requests"""

    def __init__(self, client: GitHubAPIClient = None, config: Dict = None) -> None:
        """Initialize CI status checker"""
        self.client = client or GitHubAPIClient()
        self.config = config or {}
        self.required_checks = self.config.get(
            "required_checks",
            [
                "CodeQL Analysis",
                "Security Checks",
                "Comprehensive Testing",
                "Aikido Security",
                "Vercel Preview",
            ],
        )
        self.critical_checks = ["Security Checks", "Aikido Security", "CodeQL Analysis"]

    def check_all_prs(self) -> Dict:
        """Check CI status for all open PRs"""
        prs = self.client.get_all_open_prs()
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_prs": len(prs),
            "pr_statuses": [],
            "summary": {"all_passing": 0, "some_failing": 0, "pending": 0, "no_checks": 0},
            "failures": [],
        }

        for pr in prs:
            status = self.check_pr_status(pr.number)
            results["pr_statuses"].append(status)

            if status["overall_status"] == "success":
                results["summary"]["all_passing"] += 1
            elif status["overall_status"] == "failure":
                results["summary"]["some_failing"] += 1
                results["failures"].append(status)
            elif status["overall_status"] == "pending":
                results["summary"]["pending"] += 1
            else:
                results["summary"]["no_checks"] += 1

        return results

    def check_pr_status(self, pr_number: int) -> Dict:
        """Check CI status for a specific PR"""
        pr = self.client.get_pr(pr_number)
        if not pr:
            return {"error": f"PR #{pr_number} not found"}

        checks = self.client.get_pr_status_checks(pr_number)

        return {
            "pr_number": pr_number,
            "title": pr.title,
            "checks": checks,
            "overall_status": self._determine_overall_status(checks),
            "required_checks_status": self._check_required_checks(checks),
            "failed_checks": self._get_failed_checks(checks),
            "pending_checks": self._get_pending_checks(checks),
            "missing_checks": self._get_missing_checks(checks),
            "can_merge": self._can_merge(checks),
        }

    def wait_for_checks(self, pr_number: int, timeout: int = 1800) -> Tuple[bool, Dict]:
        """Wait for CI checks to complete"""
        start_time = time.time()
        last_status = None

        while time.time() - start_time < timeout:
            status = self.check_pr_status(pr_number)

            if status["overall_status"] in ["success", "failure"]:
                return status["overall_status"] == "success", status

            if last_status != status["overall_status"]:
                logger.info(f"PR #{pr_number} CI status: {status['overall_status']}")
                last_status = status["overall_status"]

            time.sleep(30)

        return False, status

    def analyze_failures(self, pr_number: int) -> Dict:
        """Analyze CI failures for a PR"""
        status = self.check_pr_status(pr_number)
        failed_checks = status["failed_checks"]

        analysis = {
            "pr_number": pr_number,
            "failed_checks": failed_checks,
            "failure_patterns": [],
            "recommendations": [],
        }

        for check in failed_checks:
            pattern = self._identify_failure_pattern(check)
            if pattern:
                analysis["failure_patterns"].append(pattern)

        analysis["recommendations"] = self._generate_fix_recommendations(
            analysis["failure_patterns"]
        )
        return analysis

    def _determine_overall_status(self, checks: Dict) -> str:
        """Determine overall CI status"""
        if not checks:
            return "no_checks"

        statuses = list(checks.values())

        if any(s in ["failure", "error", "timed_out"] for s in statuses):
            return "failure"
        elif any(s in ["pending", "queued", "in_progress", None] for s in statuses):
            return "pending"
        elif all(s in ["success", "passed", "neutral", "skipped"] for s in statuses):
            return "success"
        else:
            return "unknown"

    def _check_required_checks(self, checks: Dict) -> Dict:
        """Check status of required checks"""
        required_status = {}
        for required in self.required_checks:
            found = False
            for check_name, status in checks.items():
                if required.lower() in check_name.lower():
                    required_status[required] = status
                    found = True
                    break
            if not found:
                required_status[required] = "missing"
        return required_status

    def _get_failed_checks(self, checks: Dict) -> List[str]:
        """Get list of failed checks"""
        return [
            name for name, status in checks.items() if status in ["failure", "error", "timed_out"]
        ]

    def _get_pending_checks(self, checks: Dict) -> List[str]:
        """Get list of pending checks"""
        return [
            name
            for name, status in checks.items()
            if status in ["pending", "queued", "in_progress", None]
        ]

    def _get_missing_checks(self, checks: Dict) -> List[str]:
        """Get list of missing required checks"""
        missing = []
        for required in self.required_checks:
            if not any(required.lower() in check.lower() for check in checks):
                missing.append(required)
        return missing

    def _can_merge(self, checks: Dict) -> bool:
        """Determine if PR can be merged based on CI status"""
        required_status = self._check_required_checks(checks)

        # All required checks must pass
        for check, status in required_status.items():
            if check in self.critical_checks and status not in ["success", "passed"]:
                return False
            if status in ["failure", "error", "missing"]:
                return False

        return True

    def _identify_failure_pattern(self, check_name: str) -> Optional[Dict]:
        """Identify common failure patterns"""
        patterns = {
            "test": {"keywords": ["test", "spec"], "type": "test_failure"},
            "lint": {"keywords": ["lint", "eslint", "pylint"], "type": "linting_error"},
            "type": {"keywords": ["type", "typescript", "mypy"], "type": "type_error"},
            "security": {"keywords": ["security", "bandit", "safety"], "type": "security_issue"},
            "build": {"keywords": ["build", "compile"], "type": "build_failure"},
            "deploy": {"keywords": ["deploy", "vercel"], "type": "deployment_failure"},
        }

        check_lower = check_name.lower()
        for pattern_name, pattern_data in patterns.items():
            if any(keyword in check_lower for keyword in pattern_data["keywords"]):
                return {"check": check_name, "type": pattern_data["type"], "category": pattern_name}

        return None

    def _generate_fix_recommendations(self, patterns: List[Dict]) -> List[Dict]:
        """Generate recommendations for fixing CI failures"""
        recommendations = []

        pattern_types = set(p["type"] for p in patterns)

        if "test_failure" in pattern_types:
            recommendations.append(
                {
                    "type": "fix_tests",
                    "priority": "high",
                    "action": "Run tests locally and fix failing test cases",
                }
            )

        if "linting_error" in pattern_types:
            recommendations.append(
                {
                    "type": "fix_lint",
                    "priority": "medium",
                    "action": "Run linter locally (npm run lint or equivalent) and fix issues",
                }
            )

        if "type_error" in pattern_types:
            recommendations.append(
                {
                    "type": "fix_types",
                    "priority": "medium",
                    "action": "Fix type errors using TypeScript or type checker",
                }
            )

        if "security_issue" in pattern_types:
            recommendations.append(
                {
                    "type": "fix_security",
                    "priority": "critical",
                    "action": "Address security vulnerabilities immediately",
                }
            )

        if "build_failure" in pattern_types:
            recommendations.append(
                {
                    "type": "fix_build",
                    "priority": "high",
                    "action": "Check build configuration and dependencies",
                }
            )

        return recommendations

    def generate_report(self, results: Dict) -> str:
        """Generate CI status report"""
        report = ["# CI/CD Status Report\n"]
        report.append(f"Generated: {results['timestamp']}\n")
        report.append(f"Total PRs: {results['total_prs']}\n\n")

        # Summary
        summary = results["summary"]
        report.append("## Summary\n")
        report.append(f"- ✅ All Passing: {summary['all_passing']}\n")
        report.append(f"- ❌ Some Failing: {summary['some_failing']}\n")
        report.append(f"- ⏳ Pending: {summary['pending']}\n")
        report.append(f"- ⚠️ No Checks: {summary['no_checks']}\n\n")

        # Failures
        if results["failures"]:
            report.append("## Failed CI Checks\n")
            for failure in results["failures"]:
                report.append(f"\n### PR #{failure['pr_number']}: {failure['title']}\n")
                report.append("Failed checks:\n")
                for check in failure["failed_checks"]:
                    report.append(f"- ❌ {check}\n")

        return "".join(report)


def main():
    """Main execution function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Check CI/CD status for PRs")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no actual changes)")
    parser.add_argument(
        "--report-file", type=str, default="ci_status_report.md", help="Path to save report file"
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
                    config = full_config.get("ci_status", {})
                    logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.warning(f"Error loading config: {e}, using defaults")

    # Initialize checker
    client = GitHubAPIClient(dry_run=args.dry_run)
    checker = CIStatusChecker(client=client, config=config or {})

    # Check all PRs
    results = checker.check_all_prs()

    # Generate report
    report = checker.generate_report(results)

    with open(args.report_file, "w") as f:
        f.write(report)
    print(f"CI status report saved to {args.report_file}")

    # Save JSON results
    results_file = args.report_file.replace(".md", "_results.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{report}")


if __name__ == "__main__":
    main()
