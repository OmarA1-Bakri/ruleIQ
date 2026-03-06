#!/usr/bin/env python3
"""
PR Cleanup Orchestrator - Main coordinator for systematic PR cleanup
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict
import logging

# Import all components
from github_api_client import GitHubAPIClient
from pr_analyzer import PRAnalyzer
from dependabot_handler import DependabotHandler
from security_pr_reviewer import SecurityPRReviewer
from feature_pr_reviewer import FeaturePRReviewer
from ci_status_checker import CIStatusChecker
from pr_decision_matrix import PRDecisionMatrix
from branch_cleanup import BranchCleanup

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PRCleanupOrchestrator:
    """Orchestrates the entire PR cleanup process"""

    def __init__(self, dry_run: bool = True, config: Dict = None, output_dir: str = None) -> None:
        """Initialize orchestrator with all components"""
        self.dry_run = dry_run
        self.config = config or {}
        self.output_dir = Path(output_dir) if output_dir else Path("scripts/pr_management/reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.client = GitHubAPIClient(dry_run=dry_run)
        self.analyzer = PRAnalyzer(self.client)
        self.dependabot = DependabotHandler(self.client, config=self.config.get("dependabot", {}))
        self.security_reviewer = SecurityPRReviewer(
            self.client, config=self.config.get("security", {})
        )
        self.feature_reviewer = FeaturePRReviewer(self.client)
        self.ci_checker = CIStatusChecker(self.client)
        self.decision_matrix = PRDecisionMatrix()
        self.branch_cleanup = BranchCleanup(dry_run=dry_run)

        self.results = {
            "timestamp": datetime.now().isoformat(),
            "mode": "dry_run" if dry_run else "live",
            "phases": {},
            "summary": {},
            "actions_taken": [],
            "errors": [],
        }

    def execute_cleanup(self) -> Dict:
        """Execute the complete PR cleanup workflow"""
        logger.info("=" * 80)
        logger.info("STARTING PR CLEANUP ORCHESTRATION")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info("=" * 80)

        try:
            # Phase 1: Analysis
            self._phase_analysis()

            # Phase 2: CI Status Check
            self._phase_ci_check()

            # Phase 3: Security PRs
            self._phase_security_prs()

            # Phase 4: Dependabot PRs
            self._phase_dependabot_prs()

            # Phase 5: Feature PRs
            self._phase_feature_prs()

            # Phase 6: Decision Making
            self._phase_decision_making()

            # Phase 7: Branch Cleanup
            self._phase_branch_cleanup()

            # Generate final summary
            self._generate_summary()

        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            self.results["errors"].append(str(e))

        return self.results

    def _phase_analysis(self):
        """Phase 1: Comprehensive PR Analysis"""
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 1: PR ANALYSIS")
        logger.info("=" * 40)

        analysis = self.analyzer.analyze_all_prs()
        self.results["phases"]["analysis"] = analysis

        # Print summary
        summary = analysis["summary"]
        logger.info(f"Found {summary['total_prs']} open PRs")
        logger.info(f"  - Dependabot: {summary['dependabot_prs']}")
        logger.info(f"  - Security: {summary['security_prs']}")
        logger.info(f"  - Features: {summary['feature_prs']}")
        logger.info(f"  - With conflicts: {summary['with_conflicts']}")
        logger.info(f"  - CI failing: {summary['ci_failing']}")

        # Save analysis report
        report = self.analyzer.generate_report("markdown")
        report_path = self.output_dir / "pr_analysis_report.md"
        with open(report_path, "w") as f:
            f.write(report)
        logger.info(f"Analysis report saved to {report_path}")

    def _phase_ci_check(self):
        """Phase 2: CI/CD Status Verification"""
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 2: CI/CD STATUS CHECK")
        logger.info("=" * 40)

        ci_results = self.ci_checker.check_all_prs()
        self.results["phases"]["ci_check"] = ci_results

        summary = ci_results["summary"]
        logger.info("CI Status Summary:")
        logger.info(f"  - All passing: {summary['all_passing']}")
        logger.info(f"  - Some failing: {summary['some_failing']}")
        logger.info(f"  - Pending: {summary['pending']}")

        # Analyze failures
        for failure in ci_results["failures"][:5]:  # Show first 5
            logger.warning(
                f"  PR #{failure['pr_number']}: {len(failure['failed_checks'])} checks failed"
            )

    def _phase_security_prs(self):
        """Phase 3: Security PR Processing"""
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 3: SECURITY PRS")
        logger.info("=" * 40)

        # Get security PR numbers from analysis
        analysis = self.results["phases"]["analysis"]
        security_prs = []

        for category_data in analysis["categories"].values():
            for pr in category_data.get("prs", []):
                # Check if this is a security PR
                pr_obj = self.client.get_pr(pr["number"])
                if pr_obj and (pr_obj.is_security or "security" in pr_obj.title.lower()):
                    security_prs.append(pr["number"])

        if security_prs:
            logger.info(f"Reviewing {len(security_prs)} security PRs: {security_prs}")
            security_results = self.security_reviewer.review_security_prs(security_prs)
            self.results["phases"]["security"] = security_results

            # Process urgent merges
            for pr_num in security_results["summary"].get("urgent_merges", []):
                if not self.dry_run:
                    logger.info(f"Merging urgent security PR #{pr_num}")
                    if self.client.merge_pr(pr_num, merge_method="merge"):
                        self.results["actions_taken"].append(f"Merged security PR #{pr_num}")
                else:
                    logger.info(f"[DRY RUN] Would merge urgent security PR #{pr_num}")
        else:
            logger.info("No security PRs found")

    def _phase_dependabot_prs(self):
        """Phase 4: Dependabot PR Processing"""
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 4: DEPENDABOT PRS")
        logger.info("=" * 40)

        dependabot_results = self.dependabot.process_all_dependabot_prs()
        self.results["phases"]["dependabot"] = dependabot_results

        logger.info("Dependabot Processing Summary:")
        logger.info(f"  - Total: {dependabot_results['total_prs']}")
        logger.info(f"  - Processed: {dependabot_results['processed']}")
        logger.info(f"  - Skipped: {dependabot_results['skipped']}")
        logger.info(f"  - Failed: {dependabot_results['failed']}")

        # Record actions
        for pr in dependabot_results["details"].get("processed", []):
            self.results["actions_taken"].append(f"Processed Dependabot PR #{pr['pr']}")

    def _phase_feature_prs(self):
        """Phase 5: Feature PR Review"""
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 5: FEATURE PRS")
        logger.info("=" * 40)

        # Identify large feature PRs
        analysis = self.results["phases"]["analysis"]
        feature_prs = []

        for pr_info in analysis.get("priority_order", []):
            if pr_info["category"] == "feature":
                feature_prs.append(pr_info["pr_number"])

        if feature_prs:
            logger.info(f"Found {len(feature_prs)} feature PRs")
            feature_results = []

            for pr_num in feature_prs[:3]:  # Review top 3 feature PRs
                logger.info(f"Reviewing feature PR #{pr_num}")
                review = self.feature_reviewer.review_feature_pr(pr_num)
                feature_results.append(review)

                # Generate report
                report = self.feature_reviewer.generate_report(review)
                report_path = self.output_dir / f"feature_pr_{pr_num}_review.md"
                with open(report_path, "w") as f:
                    f.write(report)

            self.results["phases"]["feature_prs"] = feature_results
        else:
            logger.info("No feature PRs to review")

    def _phase_decision_making(self):
        """Phase 6: Decision Matrix Evaluation"""
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 6: DECISION MAKING")
        logger.info("=" * 40)

        # Prepare PR data for decision matrix
        all_prs = self.client.get_all_open_prs()
        pr_data_list = []

        for pr in all_prs[:20]:  # Process up to 20 PRs
            # Prepare data for decision matrix
            pr_data = {
                "number": pr.number,
                "type": self._determine_pr_type(pr),
                "ci_status": self._get_ci_status(pr.number),
                "has_major_version_bump": self._check_major_version(pr),
                "is_security_update": pr.is_security,
                "has_conflicts": pr.conflicts,
                "total_changes": pr.additions + pr.deletions,
                "files_changed": pr.changed_files,
                "has_tests": self._check_has_tests(pr),
                "review_count": len(self.client.get_pr_reviews(pr.number)),
            }
            pr_data_list.append(pr_data)

        # Evaluate all PRs
        decision_results = self.decision_matrix.batch_evaluate(pr_data_list)
        self.results["phases"]["decisions"] = decision_results

        # Process auto-merge candidates
        for pr_num in decision_results["summary"]["auto_merge"]:
            if not self.dry_run:
                logger.info(f"Auto-merging PR #{pr_num}")
                if self.client.merge_pr(pr_num):
                    self.results["actions_taken"].append(f"Auto-merged PR #{pr_num}")
            else:
                logger.info(f"[DRY RUN] Would auto-merge PR #{pr_num}")

        logger.info("Decision Summary:")
        logger.info(f"  - Auto-merge: {len(decision_results['summary']['auto_merge'])}")
        logger.info(f"  - Ready for merge: {len(decision_results['summary']['ready_for_merge'])}")
        logger.info(f"  - Needs review: {len(decision_results['summary']['needs_review'])}")
        logger.info(f"  - Blocked: {len(decision_results['summary']['blocked'])}")

    def _phase_branch_cleanup(self):
        """Phase 7: Branch Cleanup"""
        logger.info("\n" + "=" * 40)
        logger.info("PHASE 7: BRANCH CLEANUP")
        logger.info("=" * 40)

        cleanup_results = self.branch_cleanup.cleanup_merged_branches()
        self.results["phases"]["branch_cleanup"] = cleanup_results

        logger.info("Branch Cleanup Summary:")
        logger.info(f"  - Local deleted: {len(cleanup_results['local_deleted'])}")
        logger.info(f"  - Remote deleted: {len(cleanup_results['remote_deleted'])}")
        logger.info(f"  - Skipped: {len(cleanup_results['skipped'])}")

    def _generate_summary(self):
        """Generate final summary of all actions"""
        summary = {
            "total_actions": len(self.results["actions_taken"]),
            "errors": len(self.results["errors"]),
            "prs_processed": 0,
            "prs_merged": 0,
            "branches_cleaned": 0,
        }

        # Count merged PRs
        for action in self.results["actions_taken"]:
            if "merged" in action.lower():
                summary["prs_merged"] += 1
            if "processed" in action.lower() or "merged" in action.lower():
                summary["prs_processed"] += 1

        # Count cleaned branches
        if "branch_cleanup" in self.results["phases"]:
            cleanup = self.results["phases"]["branch_cleanup"]
            summary["branches_cleaned"] = len(cleanup.get("local_deleted", [])) + len(
                cleanup.get("remote_deleted", [])
            )

        self.results["summary"] = summary

    def _determine_pr_type(self, pr) -> str:
        """Determine PR type for decision matrix"""
        if pr.is_dependabot:
            return "dependabot"
        elif pr.is_security:
            return "security"
        elif pr.changed_files > 50 or pr.additions > 1000:
            return "feature"
        elif "fix" in pr.title.lower() or "bug" in pr.title.lower():
            return "bugfix"
        else:
            return "other"

    def _get_ci_status(self, pr_number: int) -> str:
        """Get simplified CI status"""
        status = self.ci_checker.check_pr_status(pr_number)
        return status.get("overall_status", "unknown")

    def _check_major_version(self, pr) -> bool:
        """Check if PR has major version bump"""
        import re

        version_pattern = r"from (\d+)\.[\d.]+ to (\d+)\.[\d.]+"

        # Check title first (primary source)
        match = re.search(version_pattern, pr.title)
        if match:
            return int(match.group(2)) > int(match.group(1))

        # Also check body if present (fallback)
        if pr.body:
            match = re.search(version_pattern, pr.body)
            if match:
                return int(match.group(2)) > int(match.group(1))

        return False

    def _check_has_tests(self, pr) -> bool:
        """Check if PR includes test files"""
        files = self.client.get_pr_files(pr.number)
        return any("test" in f["filename"].lower() for f in files)

    def generate_pr_cleanup_summary(self) -> str:
        """Generate concise PR cleanup summary for repository root"""
        report = ["# PR Cleanup Summary\n\n"]
        report.append(f"**Generated**: {self.results['timestamp']}  \n")
        report.append(f"**Mode**: {self.results['mode'].upper()}\n\n")

        # PR Analysis Results
        if "analysis" in self.results["phases"]:
            analysis = self.results["phases"]["analysis"]
            summary = analysis.get("summary", {})
            report.append("## PR Analysis Results\n\n")
            report.append(f"- Total Open PRs: {summary.get('total_prs', 0)}\n")
            report.append(f"- Dependabot PRs: {summary.get('dependabot_prs', 0)}\n")
            report.append(f"- Security PRs: {summary.get('security_prs', 0)}\n")
            report.append(f"- Feature PRs: {summary.get('feature_prs', 0)}\n")
            report.append(f"- PRs with Conflicts: {summary.get('with_conflicts', 0)}\n")
            report.append(f"- CI Failing: {summary.get('ci_failing', 0)}\n\n")

        # Actions Taken
        report.append("## Actions Taken\n\n")
        if self.results["actions_taken"]:
            merged = [a for a in self.results["actions_taken"] if "merged" in a.lower()]
            closed = [a for a in self.results["actions_taken"] if "closed" in a.lower()]
            needs_action = [a for a in self.results["actions_taken"] if "needs" in a.lower()]

            if merged:
                report.append("### Merged\n")
                for action in merged:
                    report.append(f"- {action}\n")
                report.append("\n")

            if closed:
                report.append("### Closed\n")
                for action in closed:
                    report.append(f"- {action}\n")
                report.append("\n")

            if needs_action:
                report.append("### Needs Action\n")
                for action in needs_action:
                    report.append(f"- {action}\n")
                report.append("\n")
        else:
            report.append("_No actions taken (dry run or no actionable PRs)_\n\n")

        # Dependabot Processing
        if "dependabot" in self.results["phases"]:
            dep = self.results["phases"]["dependabot"]
            report.append("## Dependabot Processing\n\n")
            report.append(f"- Processed: {dep.get('processed', 0)}\n")
            report.append(f"- Skipped: {dep.get('skipped', 0)}\n")
            report.append(f"- Failed: {dep.get('failed', 0)}\n\n")

        # Security PR Status
        if "security" in self.results["phases"]:
            sec = self.results["phases"]["security"]
            report.append("## Security PR Status\n\n")
            if "summary" in sec:
                urgent = sec["summary"].get("urgent_merges", [])
                if urgent:
                    report.append(f"- Urgent merges: {', '.join(f'#{pr}' for pr in urgent)}\n")
                else:
                    report.append("- No urgent security PRs\n")
            report.append("\n")

        # Feature PR Notes
        if "feature_prs" in self.results["phases"]:
            report.append("## Feature PR Notes\n\n")
            feature_prs = self.results["phases"]["feature_prs"]
            if feature_prs:
                report.append(f"- Reviewed {len(feature_prs)} feature PRs\n")
                report.append(f"- Detailed reports saved in {self.output_dir}\n\n")
            else:
                report.append("- No feature PRs reviewed\n\n")

        # CI Status
        if "ci_check" in self.results["phases"]:
            ci = self.results["phases"]["ci_check"]
            summary = ci.get("summary", {})
            report.append("## CI Status\n\n")
            report.append(f"- All Passing: {summary.get('all_passing', 0)}\n")
            report.append(f"- Some Failing: {summary.get('some_failing', 0)}\n")
            report.append(f"- Pending: {summary.get('pending', 0)}\n\n")

        # Remaining Actions
        report.append("## Remaining Actions\n\n")
        if "decisions" in self.results["phases"]:
            decisions = self.results["phases"]["decisions"]
            summary = decisions.get("summary", {})
            needs_review = summary.get("needs_review", [])
            blocked = summary.get("blocked", [])

            if needs_review:
                report.append(
                    f"- PRs needing review: {', '.join(f'#{pr}' for pr in needs_review)}\n"
                )
            if blocked:
                report.append(f"- Blocked PRs: {', '.join(f'#{pr}' for pr in blocked)}\n")
            if not needs_review and not blocked:
                report.append("- No remaining actions required\n")
        else:
            report.append("- Decision phase not completed\n")

        return "".join(report)

    def generate_final_report(self) -> str:
        """Generate comprehensive final report"""
        report = ["# PR CLEANUP ORCHESTRATION REPORT\n"]
        report.append(f"Generated: {self.results['timestamp']}\n")
        report.append(f"Mode: {self.results['mode'].upper()}\n\n")

        # Summary
        summary = self.results.get("summary", {})
        report.append("## SUMMARY\n")
        report.append(f"- Total Actions: {summary.get('total_actions', 0)}\n")
        report.append(f"- PRs Processed: {summary.get('prs_processed', 0)}\n")
        report.append(f"- PRs Merged: {summary.get('prs_merged', 0)}\n")
        report.append(f"- Branches Cleaned: {summary.get('branches_cleaned', 0)}\n")
        report.append(f"- Errors: {summary.get('errors', 0)}\n\n")

        # Actions taken
        if self.results["actions_taken"]:
            report.append("## ACTIONS TAKEN\n")
            for action in self.results["actions_taken"]:
                report.append(f"- {action}\n")
            report.append("\n")

        # Errors
        if self.results["errors"]:
            report.append("## ERRORS\n")
            for error in self.results["errors"]:
                report.append(f"- {error}\n")

        return "".join(report)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="PR Cleanup Orchestrator")
    parser.add_argument("--live", action="store_true", help="Run in live mode (default is dry-run)")
    parser.add_argument(
        "--dry-run", dest="dry_run", action="store_true", help="Run in dry-run mode (default)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="scripts/pr_management/reports",
        help="Output directory for all reports",
    )
    parser.add_argument("--config", type=str, help="Path to configuration file")
    args = parser.parse_args()

    # Determine mode (--live takes precedence)
    dry_run = not args.live if args.live else True

    # Load configuration
    config = None
    config_path = args.config if args.config else Path(__file__).with_name("config.yaml")
    if config_path:
        config_path = Path(config_path)
        if config_path.exists():
            try:
                import yaml

                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                    logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.warning(f"Error loading config: {e}, using defaults")

    # Initialize and run orchestrator
    orchestrator = PRCleanupOrchestrator(
        dry_run=dry_run, config=config or {}, output_dir=args.output_dir
    )
    results = orchestrator.execute_cleanup()

    # Generate and save reports
    final_report = orchestrator.generate_final_report()
    print("\n" + "=" * 80)
    print(final_report)

    # Ensure output directory exists
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save detailed results
    results_file = output_path / "orchestration_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Results saved to {results_file}")

    # Save orchestration report
    report_file = output_path / "orchestration_report.md"
    with open(report_file, "w") as f:
        f.write(final_report)
    logger.info(f"Report saved to {report_file}")

    # Save PR Cleanup Summary at repository root
    summary_report = orchestrator.generate_pr_cleanup_summary()
    summary_file = Path("PR_CLEANUP_SUMMARY.md")
    with open(summary_file, "w") as f:
        f.write(summary_report)
    logger.info(f"PR Cleanup Summary saved to {summary_file}")

    logger.info("\n" + "=" * 80)
    logger.info("PR CLEANUP ORCHESTRATION COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
