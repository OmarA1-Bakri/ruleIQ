#!/usr/bin/env python3
"""
Dependabot PR Handler - Automated processing of Dependabot dependency update PRs
"""

import argparse
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
import logging
from github_api_client import GitHubAPIClient, PRInfo

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DependabotHandler:
    """Handles automated processing of Dependabot pull requests"""

    def __init__(self, client: GitHubAPIClient = None, config: Dict = None) -> None:
        """Initialize Dependabot handler"""
        self.client = client or GitHubAPIClient()
        self.config = config or self._load_default_config()
        self.processed_prs = []
        self.skipped_prs = []
        self.failed_prs = []

    def _load_default_config(self) -> Dict:
        """Load default configuration for Dependabot handling"""
        return {
            "auto_merge": True,
            "required_checks": ["ci", "security", "tests"],
            "max_major_version_bumps": 0,
            "allow_dev_dependencies": True,
            "batch_size": 5,
            "wait_for_checks_timeout": 1800,  # 30 minutes
            "merge_method": "squash",
            "priority_packages": ["security", "eslint", "pytest", "fastapi"],
            "blocked_packages": [],
            "require_all_checks_pass": True,
            "allow_merge_without_checks": False,  # Safety gate for auto-merge
        }

    def process_all_dependabot_prs(self) -> Dict:
        """Process all Dependabot PRs according to configuration"""
        logger.info("Starting Dependabot PR processing...")

        # Get all open PRs
        all_prs = self.client.get_all_open_prs()

        # Filter Dependabot PRs
        dependabot_prs = [pr for pr in all_prs if pr.is_dependabot]
        logger.info(f"Found {len(dependabot_prs)} Dependabot PRs")

        # Categorize by type
        categorized = self._categorize_dependabot_prs(dependabot_prs)

        # Process each category
        results = {
            "total": len(dependabot_prs),
            "processed": [],
            "skipped": [],
            "failed": [],
            "categories": categorized,
        }

        # Process security updates first
        for pr in categorized.get("security", []):
            result = self._process_single_pr(pr, priority="high")
            self._update_results(results, pr, result)

        # Process priority packages
        for pr in categorized.get("priority", []):
            result = self._process_single_pr(pr, priority="medium")
            self._update_results(results, pr, result)

        # Process regular updates
        batch_count = 0
        for pr in categorized.get("regular", []):
            if batch_count >= self.config["batch_size"]:
                logger.info(f"Reached batch size limit ({self.config['batch_size']})")
                results["skipped"].append({"pr": pr.number, "reason": "batch_limit_reached"})
                continue

            result = self._process_single_pr(pr, priority="low")
            if result["status"] == "merged":
                batch_count += 1
            self._update_results(results, pr, result)

        # Process dev dependencies last
        for pr in categorized.get("dev", []):
            if batch_count >= self.config["batch_size"]:
                results["skipped"].append({"pr": pr.number, "reason": "batch_limit_reached"})
                continue

            result = self._process_single_pr(pr, priority="low")
            if result["status"] == "merged":
                batch_count += 1
            self._update_results(results, pr, result)

        return self._generate_summary(results)

    def _categorize_dependabot_prs(self, prs: List[PRInfo]) -> Dict[str, List[PRInfo]]:
        """Categorize Dependabot PRs by update type"""
        categories = {
            "security": [],
            "priority": [],
            "regular": [],
            "dev": [],
            "major": [],
            "blocked": [],
        }

        for pr in prs:
            # Check if blocked
            if self._is_blocked_package(pr):
                categories["blocked"].append(pr)
                continue

            # Check for major version bump
            if self._is_major_version_bump(pr):
                categories["major"].append(pr)
                continue

            # Check if security update
            if self._is_security_update(pr):
                categories["security"].append(pr)
            # Check if priority package
            elif self._is_priority_package(pr):
                categories["priority"].append(pr)
            # Check if dev dependency
            elif self._is_dev_dependency(pr):
                categories["dev"].append(pr)
            else:
                categories["regular"].append(pr)

        return categories

    def _process_single_pr(self, pr: PRInfo, priority: str = "medium") -> Dict:
        """Process a single Dependabot PR"""
        logger.info(f"Processing PR #{pr.number}: {pr.title}")

        result = {"pr_number": pr.number, "status": "pending", "message": "", "checks": {}}

        # Check if PR is mergeable
        if not self._is_mergeable(pr):
            result["status"] = "skipped"
            result["message"] = "PR is not mergeable (conflicts or other issues)"
            return result

        # Wait for CI checks
        checks_passed, check_results = self._wait_for_checks(pr)
        result["checks"] = check_results

        if not checks_passed:
            if priority == "high":
                # For security updates, try to fix failing tests
                logger.warning(f"Security PR #{pr.number} has failing checks. Attempting to fix...")
                if self._attempt_fix_checks(pr):
                    checks_passed, check_results = self._wait_for_checks(pr)
                    result["checks"] = check_results

            if not checks_passed:
                result["status"] = "failed"
                result["message"] = "Required CI checks failed"
                return result

        # Validate the update
        validation = self._validate_update(pr)
        if not validation["valid"]:
            result["status"] = "skipped"
            result["message"] = validation["reason"]
            return result

        # Merge the PR
        if self.config["auto_merge"] and not self.client.dry_run:
            merge_success = self._merge_pr(pr)
            if merge_success:
                result["status"] = "merged"
                result["message"] = f"Successfully merged using {self.config['merge_method']}"
            else:
                result["status"] = "failed"
                result["message"] = "Merge operation failed"
        else:
            result["status"] = "ready"
            result["message"] = "Ready to merge (dry run or manual mode)"

        return result

    def _is_blocked_package(self, pr: PRInfo) -> bool:
        """Check if PR updates a blocked package"""
        for package in self.config["blocked_packages"]:
            if package.lower() in pr.title.lower():
                return True
        return False

    def _is_major_version_bump(self, pr: PRInfo) -> bool:
        """Check if PR contains major version bump"""
        # Parse version numbers from title
        version_pattern = r"from (\d+)\.[\d.]+ to (\d+)\.[\d.]+"
        match = re.search(version_pattern, pr.title)

        if match:
            old_major = int(match.group(1))
            new_major = int(match.group(2))
            return new_major > old_major

        return False

    def _is_security_update(self, pr: PRInfo) -> bool:
        """Check if PR is a security update"""
        security_keywords = ["security", "vulnerability", "CVE", "patch"]
        title_lower = pr.title.lower()
        body_lower = (pr.body or "").lower()

        return any(
            keyword.lower() in title_lower or keyword.lower() in body_lower
            for keyword in security_keywords
        )

    def _is_priority_package(self, pr: PRInfo) -> bool:
        """Check if PR updates a priority package"""
        for package in self.config["priority_packages"]:
            if package.lower() in pr.title.lower():
                return True
        return False

    def _is_dev_dependency(self, pr: PRInfo) -> bool:
        """Check if PR updates a dev dependency"""
        dev_keywords = ["devDependencies", "dev-dependencies", "test", "lint", "prettier", "eslint"]
        return any(keyword in pr.title or keyword in (pr.body or "") for keyword in dev_keywords)

    def _is_mergeable(self, pr: PRInfo) -> bool:
        """Check if PR is mergeable"""
        # Refresh PR data
        fresh_pr = self.client.get_pr(pr.number)
        if not fresh_pr:
            return False

        # Check mergeable state
        if fresh_pr.mergeable is False:
            return False

        if fresh_pr.conflicts:
            logger.warning(f"PR #{pr.number} has conflicts")
            return False

        return True

    def _wait_for_checks(self, pr: PRInfo, timeout: int = None) -> Tuple[bool, Dict]:
        """Wait for CI checks to complete"""
        timeout = timeout or self.config["wait_for_checks_timeout"]
        start_time = time.time()
        check_results = {}

        while time.time() - start_time < timeout:
            # Get current status checks
            checks = self.client.get_pr_status_checks(pr.number)

            if not checks:
                logger.warning(f"No status checks found for PR #{pr.number}")
                # Safety check: only allow merge without checks if explicitly configured
                if not self.config.get("allow_merge_without_checks", False):
                    logger.info(
                        f"Blocking PR #{pr.number}: No CI checks configured and allow_merge_without_checks is False"
                    )
                    return False, {"reason": "no_checks_configured"}
                else:
                    logger.warning(
                        f"Allowing PR #{pr.number} without checks (allow_merge_without_checks=True)"
                    )
                    return True, {}

            # Check if all required checks are present
            all_complete = True
            all_passed = True

            for check_name, status in checks.items():
                check_results[check_name] = status

                # Check if this is a required check
                is_required = any(
                    req in check_name.lower() for req in self.config["required_checks"]
                )

                if is_required:
                    if status in ["pending", None]:
                        all_complete = False
                    elif status not in ["success", "passed"]:
                        all_passed = False

            if all_complete:
                if self.config["require_all_checks_pass"]:
                    # Check all checks, not just required ones
                    all_passed = all(
                        status in ["success", "passed", "neutral"]
                        for status in checks.values()
                        if status not in ["pending", None]
                    )

                return all_passed, check_results

            # Wait before next check
            logger.info(f"Waiting for checks to complete for PR #{pr.number}...")
            time.sleep(30)

        logger.warning(f"Timeout waiting for checks on PR #{pr.number}")
        return False, check_results

    def _attempt_fix_checks(self, pr: PRInfo) -> bool:
        """Attempt to fix failing checks (e.g., update branch, rerun)"""
        logger.info(f"Attempting to fix checks for PR #{pr.number}")

        # Try updating the branch first
        if self.client.update_branch(pr.number):
            logger.info(f"Updated branch for PR #{pr.number}")
            time.sleep(60)  # Wait for checks to restart
            return True

        # Try rerunning failed workflows
        workflows = self.client.get_workflow_runs(pr.head_branch)
        for workflow in workflows:
            if workflow.get("conclusion") == "failure":
                if self.client.rerun_workflow(workflow["id"]):
                    logger.info(f"Reran failed workflow for PR #{pr.number}")
                    time.sleep(60)
                    return True

        return False

    def _detect_ecosystem(self, pr: PRInfo, files: List[Dict]) -> str:
        """Detect the ecosystem based on PR title and changed files"""
        # Check PR title/body for hints
        pr.title.lower()
        (pr.body or "").lower()

        # Check file names for ecosystem indicators
        filenames = [f["filename"] for f in files]

        # Node.js / npm / yarn / pnpm
        if any(
            f in filenames
            for f in ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"]
        ):
            if "pnpm-lock.yaml" in filenames:
                return "pnpm"
            elif "yarn.lock" in filenames:
                return "yarn"
            else:
                return "npm"

        # Python - Poetry
        if any(f in filenames for f in ["pyproject.toml", "poetry.lock"]):
            return "poetry"

        # Python - Pipenv
        if any(f in filenames for f in ["Pipfile", "Pipfile.lock"]):
            return "pipenv"

        # Python - pip/requirements
        if any("requirements" in f and f.endswith(".txt") for f in filenames):
            return "pip"

        # Go modules
        if any(f in filenames for f in ["go.mod", "go.sum"]):
            return "go"

        # Rust / Cargo
        if any(f in filenames for f in ["Cargo.toml", "Cargo.lock"]):
            return "rust"

        # Ruby / Bundler
        if any(f in filenames for f in ["Gemfile", "Gemfile.lock"]):
            return "ruby"

        # Java / Maven
        if "pom.xml" in filenames:
            return "maven"

        # Java / Gradle
        if any(f.endswith(".gradle") or f.endswith(".gradle.kts") for f in filenames):
            return "gradle"

        return "unknown"

    def _validate_ecosystem_files(self, ecosystem: str, files: List[Dict]) -> Tuple[bool, str]:
        """Validate that changed files match the expected pattern for the ecosystem"""
        filenames = [f["filename"] for f in files]

        # Define expected patterns for each ecosystem
        ecosystem_patterns = {
            "npm": {
                "manifest": ["package.json"],
                "lock": ["package-lock.json"],
                "optional": [".npmrc"],
            },
            "yarn": {
                "manifest": ["package.json"],
                "lock": ["yarn.lock"],
                "optional": [".yarnrc", ".yarnrc.yml"],
            },
            "pnpm": {
                "manifest": ["package.json"],
                "lock": ["pnpm-lock.yaml"],
                "optional": [".npmrc", "pnpm-workspace.yaml"],
            },
            "poetry": {"manifest": ["pyproject.toml"], "lock": ["poetry.lock"], "optional": []},
            "pipenv": {"manifest": ["Pipfile"], "lock": ["Pipfile.lock"], "optional": []},
            "pip": {
                "manifest": [],  # requirements*.txt files
                "lock": [],
                "optional": [],
            },
            "go": {"manifest": ["go.mod"], "lock": ["go.sum"], "optional": []},
            "rust": {"manifest": ["Cargo.toml"], "lock": ["Cargo.lock"], "optional": []},
            "ruby": {
                "manifest": ["Gemfile"],
                "lock": ["Gemfile.lock"],
                "optional": [".ruby-version"],
            },
            "maven": {"manifest": ["pom.xml"], "lock": [], "optional": []},
            "gradle": {
                "manifest": [],  # *.gradle or *.gradle.kts files
                "lock": ["gradle.lock", "gradle.lockfile"],
                "optional": ["gradle.properties", "settings.gradle", "settings.gradle.kts"],
            },
        }

        if ecosystem not in ecosystem_patterns:
            # Unknown ecosystem, be permissive
            return True, ""

        pattern = ecosystem_patterns[ecosystem]

        # Check for unexpected files
        allowed_files = pattern["manifest"] + pattern["lock"] + pattern["optional"]

        # For pip, allow requirements*.txt files
        if ecosystem == "pip":
            allowed_files = [f for f in filenames if "requirements" in f and f.endswith(".txt")]

        # For gradle, allow *.gradle and *.gradle.kts files
        if ecosystem == "gradle":
            allowed_files.extend(
                [f for f in filenames if f.endswith(".gradle") or f.endswith(".gradle.kts")]
            )
            allowed_files.extend(pattern["optional"])

        # Check for source code changes (usually not expected in dependency updates)
        source_extensions = [
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".rb",
            ".c",
            ".cpp",
            ".h",
        ]
        source_changes = [
            f
            for f in filenames
            if any(f.endswith(ext) for ext in source_extensions)
            and not any(test_indicator in f for test_indicator in ["test", "spec", "__tests__"])
        ]

        if source_changes:
            # Some updates may require minimal source changes, be lenient if it's just 1-2 files
            if len(source_changes) > 2:
                return (
                    False,
                    f"Unexpected source code changes for {ecosystem} update: {', '.join(source_changes)}",
                )

        # Check if only expected files are changed
        if ecosystem not in {"pip", "gradle"}:
            unexpected_files = [f for f in filenames if f not in allowed_files]
            # Allow some flexibility for monorepo structures
            unexpected_files = [
                f
                for f in unexpected_files
                if not f.startswith("packages/") and not f.startswith("apps/")
            ]

            if unexpected_files and len(unexpected_files) > 2:
                return (
                    False,
                    f"Unexpected files for {ecosystem} update: {', '.join(unexpected_files)}",
                )

        return True, ""

    def _validate_update(self, pr: PRInfo) -> Dict:
        """Validate the dependency update with ecosystem awareness"""
        validation = {"valid": True, "reason": ""}

        # Check for breaking changes in description
        if pr.body and "breaking" in pr.body.lower():
            validation["valid"] = False
            validation["reason"] = "Contains breaking changes"
            return validation

        # Check file changes
        files = self.client.get_pr_files(pr.number)

        # Detect ecosystem
        ecosystem = self._detect_ecosystem(pr, files)
        logger.info(f"Detected ecosystem for PR #{pr.number}: {ecosystem}")

        # Validate files match ecosystem expectations
        valid, reason = self._validate_ecosystem_files(ecosystem, files)
        if not valid:
            validation["valid"] = False
            validation["reason"] = reason
            return validation

        # Additional validation: check for too many changes
        if len(files) > 10 and ecosystem != "unknown":
            validation["valid"] = False
            validation["reason"] = (
                f"Too many files changed ({len(files)}) for {ecosystem} dependency update"
            )
            return validation

        return validation

    def _merge_pr(self, pr: PRInfo) -> bool:
        """Merge the PR using configured method"""
        commit_title = f"chore(deps): {pr.title}"
        commit_message = f"Auto-merged by Dependabot handler\n\nOriginal PR: #{pr.number}"

        return self.client.merge_pr(
            pr.number,
            merge_method=self.config["merge_method"],
            commit_title=commit_title,
            commit_message=commit_message,
        )

    def _update_results(self, results: Dict, pr: PRInfo, process_result: Dict) -> None:
        """Update results dictionary with processing outcome"""
        if process_result["status"] == "merged":
            pr_info = {"pr": pr.number, "title": pr.title, "message": process_result["message"]}
            results["processed"].append(pr_info)
            self.processed_prs.append(pr_info)  # Also update instance list
        elif process_result["status"] in ["skipped", "ready"]:
            pr_info = {"pr": pr.number, "title": pr.title, "reason": process_result["message"]}
            results["skipped"].append(pr_info)
            self.skipped_prs.append(pr_info)  # Also update instance list
        else:
            pr_info = {
                "pr": pr.number,
                "title": pr.title,
                "reason": process_result["message"],
                "checks": process_result["checks"],
            }
            results["failed"].append(pr_info)
            self.failed_prs.append(pr_info)  # Also update instance list

    def _generate_summary(self, results: Dict) -> Dict:
        """Generate processing summary"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_prs": results["total"],
            "processed": len(results["processed"]),
            "skipped": len(results["skipped"]),
            "failed": len(results["failed"]),
            "details": results,
            "recommendations": [],
        }

        # Add recommendations
        if results["failed"]:
            summary["recommendations"].append(
                {
                    "action": "review_failed",
                    "description": f"Review {len(results['failed'])} failed PRs manually",
                    "prs": [f["pr"] for f in results["failed"]],
                }
            )

        if results["categories"].get("major"):
            summary["recommendations"].append(
                {
                    "action": "review_major",
                    "description": f"Review {len(results['categories']['major'])} major version updates",
                    "prs": [pr.number for pr in results["categories"]["major"]],
                }
            )

        if results["categories"].get("blocked"):
            summary["recommendations"].append(
                {
                    "action": "handle_blocked",
                    "description": f"Handle {len(results['categories']['blocked'])} blocked packages",
                    "prs": [pr.number for pr in results["categories"]["blocked"]],
                }
            )

        return summary

    def generate_report(self, results: Dict = None) -> str:
        """Generate a report of processing results

        Args:
            results: Optional results dict to use. If not provided, uses instance lists.
        """
        report = ["# Dependabot PR Processing Report\n"]
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Use results dict if provided, otherwise fall back to instance lists
        processed = results.get("processed", []) if results else self.processed_prs
        skipped = results.get("skipped", []) if results else self.skipped_prs
        failed = results.get("failed", []) if results else self.failed_prs

        # Add summary
        report.append("\n## Summary\n")
        report.append(f"- Total Processed: {len(processed)}\n")
        report.append(f"- Total Skipped: {len(skipped)}\n")
        report.append(f"- Total Failed: {len(failed)}\n")

        if processed:
            report.append("\n## Successfully Processed\n")
            for pr in processed:
                report.append(f"- PR #{pr['pr']}: {pr['title']}\n")
                if "message" in pr:
                    report.append(f"  - {pr['message']}\n")

        if skipped:
            report.append("\n## Skipped\n")
            for pr in skipped:
                report.append(f"- PR #{pr['pr']}: {pr.get('title', 'N/A')}\n")
                report.append(f"  - Reason: {pr.get('reason', 'Unknown')}\n")

        if failed:
            report.append("\n## Failed\n")
            for pr in failed:
                report.append(f"- PR #{pr['pr']}: {pr.get('title', 'N/A')}\n")
                report.append(f"  - Reason: {pr.get('reason', 'Unknown')}\n")
                if "checks" in pr and pr["checks"]:
                    report.append(
                        f"  - Failed checks: {', '.join(k for k, v in pr['checks'].items() if v not in ['success', 'passed'])}\n"
                    )

        return "".join(report)


def main():
    """Main execution function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Process Dependabot PRs")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no actual changes)")
    parser.add_argument(
        "--report-file",
        type=str,
        default="dependabot_processing_report.md",
        help="Path to save report file",
    )
    args = parser.parse_args()

    # Load configuration
    config = None
    config_path = args.config if args.config else Path(__file__).with_name("config.yaml")
    try:
        with open(config_path, "r") as f:
            import yaml

            full_config = yaml.safe_load(f)
            config = full_config.get("pr_categories", {}).get("dependabot", {})
            logger.info(f"Loaded configuration from {config_path}")
    except FileNotFoundError:
        logger.info(f"Config file not found at {config_path}, using default configuration")
    except Exception as e:
        logger.warning(f"Error loading config: {e}, using default configuration")

    # Initialize handler with dry_run option
    client = GitHubAPIClient(dry_run=args.dry_run)
    handler = DependabotHandler(client=client, config=config)

    # Process all Dependabot PRs
    results = handler.process_all_dependabot_prs()

    # Print summary
    print("\nDependabot PR Processing Summary:")
    print(f"  Total PRs: {results['total_prs']}")
    print(f"  Processed: {results['processed']}")
    print(f"  Skipped: {results['skipped']}")
    print(f"  Failed: {results['failed']}")

    # Print recommendations
    if results["recommendations"]:
        print("\nRecommendations:")
        for rec in results["recommendations"]:
            print(f"  - {rec['description']}")
            print(f"    PRs: {', '.join(f'#{pr}' for pr in rec['prs'][:5])}")

    # Save detailed report - pass results to generate_report
    report = handler.generate_report(results["details"])
    with open(args.report_file, "w") as f:
        f.write(report)
    print(f"\nDetailed report saved to {args.report_file}")

    # Save JSON results
    with open("dependabot_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    main()
