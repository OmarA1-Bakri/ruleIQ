#!/usr/bin/env python3
"""
PR Auto-Reviewer - Enhanced automatic PR review and merge system
This module extends the existing PR management system to automatically:
1. Review all open PRs using the decision matrix
2. Automatically merge safe PRs with high confidence scores
3. Add actionable comments to uncertain PRs with next steps
4. Maintain comprehensive audit trail and safety measures
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

# Import existing components
from github_api_client import GitHubAPIClient
from pr_analyzer import PRAnalyzer
from pr_decision_matrix import PRDecisionMatrix
from security_pr_reviewer import SecurityPRReviewer
from dependabot_handler import DependabotHandler
from ci_status_checker import CIStatusChecker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PRAutoReviewer:
    """Enhanced automatic PR reviewer with merge automation and intelligent commenting"""

    def __init__(self, dry_run: bool = True, config: Dict = None):
        """Initialize the auto-reviewer"""
        self.dry_run = dry_run
        self.config = config or {}
        
        # Initialize components
        self.client = GitHubAPIClient(dry_run=dry_run)
        self.analyzer = PRAnalyzer(client=self.client)
        self.decision_matrix = PRDecisionMatrix()
        self.security_reviewer = SecurityPRReviewer(client=self.client)
        self.dependabot_handler = DependabotHandler(client=self.client)
        self.ci_checker = CIStatusChecker(client=self.client)
        
        # Results tracking
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'mode': 'dry_run' if dry_run else 'live',
            'processed_prs': [],
            'auto_merged': [],
            'commented': [],
            'skipped': [],
            'errors': [],
            'summary': {}
        }
        
        # Safety thresholds from config
        self.auto_merge_confidence_threshold = self.config.get(
            'auto_merge_confidence_threshold', 85.0
        )
        self.comment_confidence_threshold = self.config.get(
            'comment_confidence_threshold', 60.0
        )
        self.max_auto_merges_per_run = self.config.get(
            'max_auto_merges_per_run', 5
        )

    def review_all_prs(self) -> Dict:
        """Review all open PRs and take appropriate actions"""
        logger.info("=" * 80)
        logger.info("STARTING AUTOMATED PR REVIEW")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"Auto-merge threshold: {self.auto_merge_confidence_threshold}%")
        logger.info(f"Comment threshold: {self.comment_confidence_threshold}%")
        logger.info("=" * 80)

        try:
            # Get all open PRs
            all_prs = self.client.get_all_open_prs()
            logger.info(f"Found {len(all_prs)} open PRs to review")

            if not all_prs:
                logger.info("No open PRs found")
                return self.results

            # Process each PR
            auto_merge_count = 0
            for pr in all_prs:
                if auto_merge_count >= self.max_auto_merges_per_run:
                    logger.warning(f"Reached maximum auto-merges per run ({self.max_auto_merges_per_run})")
                    break

                try:
                    pr_result = self._process_single_pr(pr)
                    self.results['processed_prs'].append(pr_result)
                    
                    if pr_result['action_taken'] == 'auto_merged':
                        auto_merge_count += 1
                        
                except Exception as e:
                    error_msg = f"Error processing PR #{pr.number}: {str(e)}"
                    logger.error(error_msg)
                    self.results['errors'].append(error_msg)

            # Generate summary
            self._generate_summary()
            
            logger.info("=" * 80)
            logger.info("AUTOMATED PR REVIEW COMPLETE")
            logger.info("=" * 80)

        except Exception as e:
            error_msg = f"Critical error in PR review process: {str(e)}"
            logger.error(error_msg)
            self.results['errors'].append(error_msg)

        return self.results

    def _process_single_pr(self, pr) -> Dict:
        """Process a single PR with safety checks"""
        logger.info(f"\n--- Processing PR #{pr.number}: {pr.title} ---")
        
        pr_result = {
            'pr_number': pr.number,
            'title': pr.title,
            'author': pr.author,
            'type': self._determine_pr_type(pr),
            'confidence_score': 0,
            'decision': 'unknown',
            'action_taken': 'none',
            'safety_checks': {},
            'comment_added': False,
            'reasons': [],
            'timestamp': datetime.now().isoformat()
        }

        # Run safety checks first
        safety_result = self._run_safety_checks(pr)
        pr_result['safety_checks'] = safety_result
        
        if not safety_result['safe_to_proceed']:
            pr_result['action_taken'] = 'skipped'
            pr_result['reasons'] = safety_result['blocking_reasons']
            logger.warning(f"PR #{pr.number} skipped due to safety concerns: {safety_result['blocking_reasons']}")
            self.results['skipped'].append(pr_result)
            return pr_result

        # Evaluate PR using decision matrix
        pr_data = self._prepare_pr_data(pr)
        evaluation = self.decision_matrix.evaluate_pr(pr_data)
        
        pr_result['confidence_score'] = evaluation['confidence']
        pr_result['decision'] = evaluation['decision']
        pr_result['reasons'] = evaluation['reasons']

        # Take action based on evaluation
        action_taken = self._take_action(pr, evaluation, pr_result)
        pr_result['action_taken'] = action_taken

        return pr_result

    def _run_safety_checks(self, pr) -> Dict:
        """Run comprehensive safety checks before any action"""
        safety_result = {
            'safe_to_proceed': True,
            'blocking_reasons': [],
            'warnings': [],
            'checks': {}
        }

        # Check 1: CI status
        ci_status = self.ci_checker.check_pr_status(pr.number)
        safety_result['checks']['ci_status'] = ci_status['overall_status']
        
        if ci_status['overall_status'] == 'failed':
            safety_result['safe_to_proceed'] = False
            safety_result['blocking_reasons'].append("CI checks are failing")

        # Check 2: Merge conflicts
        has_conflicts = pr.conflicts
        safety_result['checks']['has_conflicts'] = has_conflicts
        
        if has_conflicts:
            safety_result['safe_to_proceed'] = False
            safety_result['blocking_reasons'].append("PR has merge conflicts")

        # Check 3: Security vulnerabilities (for security PRs)
        if pr.is_security:
            security_review = self.security_reviewer._review_single_pr(pr)
            safety_result['checks']['security_review'] = security_review['approval_status']
            
            if security_review['approval_status'] == 'blocked':
                safety_result['safe_to_proceed'] = False
                safety_result['blocking_reasons'].extend(security_review.get('blocking_reasons', []))

        # Check 4: Size limits for large PRs
        if pr.changed_files > 100 or pr.additions > 5000:
            safety_result['warnings'].append("Large PR - requires careful review")
            
        # Check 5: Protected files
        protected_patterns = ['.github/', 'config/', 'security/', 'Dockerfile']
        try:
            files = self.client.get_pr_files(pr.number)
            protected_files = [f for f in files if any(p in f['filename'] for p in protected_patterns)]
            
            if protected_files:
                safety_result['warnings'].append(f"Changes to protected files: {len(protected_files)} files")
                
        except Exception as e:
            logger.warning(f"Could not check files for PR #{pr.number}: {e}")

        return safety_result

    def _prepare_pr_data(self, pr) -> Dict:
        """Prepare PR data for decision matrix evaluation"""
        # Get additional data needed for evaluation
        ci_status = self.ci_checker.check_pr_status(pr.number)
        
        pr_data = {
            'number': pr.number,
            'title': pr.title,
            'type': self._determine_pr_type(pr),
            'author': pr.author,
            'size': pr.changed_files,
            'additions': pr.additions,
            'deletions': pr.deletions,
            'is_dependabot': pr.is_dependabot,
            'is_security': pr.is_security,
            'ci_status': ci_status['overall_status'],
            'has_conflicts': pr.conflicts,
            'review_count': len(pr.reviewers),
            'created_at': pr.created_at,
            'updated_at': pr.updated_at,
            'labels': pr.labels
        }
        
        return pr_data

    def _determine_pr_type(self, pr) -> str:
        """Determine PR type for processing"""
        if pr.is_dependabot:
            return 'dependabot'
        elif pr.is_security:
            return 'security'
        elif pr.changed_files > 50 or pr.additions > 1000:
            return 'feature'
        elif any(word in pr.title.lower() for word in ['fix', 'bug', 'patch']):
            return 'bugfix'
        elif any(word in pr.title.lower() for word in ['doc', 'readme', 'comment']):
            return 'documentation'
        else:
            return 'other'

    def _take_action(self, pr, evaluation: Dict, pr_result: Dict) -> str:
        """Take appropriate action based on evaluation"""
        confidence = evaluation['confidence']
        decision = evaluation['decision']
        
        logger.info(f"PR #{pr.number} evaluation: {decision} (confidence: {confidence:.1f}%)")

        # High confidence - auto-merge
        if (decision == 'auto_merge' and 
            confidence >= self.auto_merge_confidence_threshold and
            len(self.results['auto_merged']) < self.max_auto_merges_per_run):
            
            return self._auto_merge_pr(pr, evaluation)

        # Medium confidence - add helpful comment
        elif confidence >= self.comment_confidence_threshold:
            return self._add_helpful_comment(pr, evaluation, pr_result)

        # Low confidence - skip with reasoning
        else:
            logger.info(f"PR #{pr.number} requires manual review (low confidence: {confidence:.1f}%)")
            return 'manual_review_required'

    def _auto_merge_pr(self, pr, evaluation: Dict) -> str:
        """Automatically merge a PR with high confidence"""
        pr_type = self._determine_pr_type(pr)
        merge_method = self.config.get('merge_strategies', {}).get(pr_type, 'squash')
        
        # Add approval comment first
        approval_comment = self._generate_approval_comment(pr, evaluation)
        comment_success = self.client.add_pr_comment(pr.number, approval_comment)
        
        # Approve the PR
        approve_success = self.client.approve_pr(pr.number, "Automated approval - all checks passed")
        
        # Merge the PR
        merge_success = self.client.merge_pr(
            pr.number, 
            merge_method=merge_method,
            commit_title=f"Auto-merge: {pr.title}",
            commit_message=f"Automatically merged by PR Auto-Reviewer\nConfidence: {evaluation['confidence']:.1f}%\nDecision: {evaluation['decision']}"
        )
        
        if merge_success:
            self.results['auto_merged'].append({
                'pr_number': pr.number,
                'title': pr.title,
                'confidence': evaluation['confidence'],
                'merge_method': merge_method
            })
            logger.info(f"✅ Successfully auto-merged PR #{pr.number}")
            return 'auto_merged'
        else:
            logger.error(f"❌ Failed to merge PR #{pr.number}")
            return 'merge_failed'

    def _add_helpful_comment(self, pr, evaluation: Dict, pr_result: Dict) -> str:
        """Add an actionable comment to help with PR review"""
        comment = self._generate_helpful_comment(pr, evaluation, pr_result)
        
        comment_success = self.client.add_pr_comment(pr.number, comment)
        
        if comment_success:
            self.results['commented'].append({
                'pr_number': pr.number,
                'title': pr.title,
                'confidence': evaluation['confidence'],
                'decision': evaluation['decision']
            })
            logger.info(f"💬 Added helpful comment to PR #{pr.number}")
            return 'commented'
        else:
            logger.error(f"❌ Failed to add comment to PR #{pr.number}")
            return 'comment_failed'

    def _generate_approval_comment(self, pr, evaluation: Dict) -> str:
        """Generate approval comment for auto-merged PRs"""
        pr_type = self._determine_pr_type(pr)
        
        comment = f"""## 🤖 Automated Review - APPROVED ✅

This PR has been automatically reviewed and approved for merge.

**Review Summary:**
- **Type:** {pr_type.title()}
- **Confidence Score:** {evaluation['confidence']:.1f}%
- **Decision:** {evaluation['decision']}
- **Files Changed:** {pr.changed_files}
- **Lines Added/Removed:** +{pr.additions}/-{pr.deletions}

**Checks Passed:**
- ✅ CI/CD pipeline successful
- ✅ No merge conflicts
- ✅ Security scans passed
- ✅ Automated testing complete
- ✅ Code quality standards met

**Auto-merge initiated.** This PR will be merged automatically.

---
*This review was performed by the PR Auto-Reviewer system. For questions, contact the development team.*
"""
        return comment

    def _generate_helpful_comment(self, pr, evaluation: Dict, pr_result: Dict) -> str:
        """Generate helpful comment with next steps"""
        pr_type = self._determine_pr_type(pr)
        safety_checks = pr_result['safety_checks']
        
        # Base comment structure
        comment = f"""## 🤖 Automated Review - Action Required

This PR has been automatically reviewed. While it shows promise, it needs some attention before it can be merged.

**Review Summary:**
- **Type:** {pr_type.title()}
- **Confidence Score:** {evaluation['confidence']:.1f}%
- **Decision:** {evaluation['decision']}
- **Files Changed:** {pr.changed_files}
- **Lines Added/Removed:** +{pr.additions}/-{pr.deletions}

"""

        # Add specific issues and next steps
        if evaluation['decision'] == 'blocked':
            comment += "**❌ Blocking Issues:**\n"
            for reason in evaluation['reasons']:
                comment += f"- {reason}\n"
            comment += "\n"

            comment += "**🔧 Required Actions:**\n"
            for action in evaluation.get('actions', []):
                if action['type'] == 'fix':
                    comment += f"- **{action['priority'].upper()}:** {action['description']}\n"
                    if 'details' in action:
                        comment += f"  - Details: {action['details']}\n"

        elif evaluation['decision'] == 'needs_review':
            comment += "**⚠️  Manual Review Required:**\n"
            for reason in evaluation['reasons']:
                comment += f"- {reason}\n"
            comment += "\n"

            comment += "**📋 Recommended Actions:**\n"
            comment += "- Have a team member review the changes\n"
            comment += "- Verify all tests are comprehensive\n"
            if pr_type == 'feature':
                comment += "- Ensure documentation is updated\n"
                comment += "- Consider breaking down large changes\n"
            elif pr_type == 'security':
                comment += "- Have security team review the changes\n"
                comment += "- Verify vulnerability remediation\n"

        # Add safety warnings if any
        if safety_checks.get('warnings'):
            comment += "\n**⚠️  Warnings:**\n"
            for warning in safety_checks['warnings']:
                comment += f"- {warning}\n"

        # Add CI status
        ci_status = safety_checks['checks'].get('ci_status', 'unknown')
        if ci_status == 'failed':
            comment += "\n**🚨 CI Status:** Failed - Please fix failing tests before merge\n"
        elif ci_status == 'pending':
            comment += "\n**⏳ CI Status:** Pending - Waiting for checks to complete\n"
        elif ci_status == 'success':
            comment += "\n**✅ CI Status:** All checks passed\n"

        # Add merge readiness assessment
        if evaluation['confidence'] >= 80:
            comment += "\n**🎯 Merge Readiness:** High - Ready for merge after addressing items above\n"
        elif evaluation['confidence'] >= 60:
            comment += "\n**🎯 Merge Readiness:** Medium - Needs review but on the right track\n"
        else:
            comment += "\n**🎯 Merge Readiness:** Low - Significant changes needed\n"

        comment += "\n---\n*This review was performed by the PR Auto-Reviewer system. Once issues are addressed, re-run the review or request manual review.*"

        return comment

    def _generate_summary(self):
        """Generate summary of actions taken"""
        processed = len(self.results['processed_prs'])
        auto_merged = len(self.results['auto_merged'])
        commented = len(self.results['commented'])
        skipped = len(self.results['skipped'])
        errors = len(self.results['errors'])

        self.results['summary'] = {
            'total_processed': processed,
            'auto_merged': auto_merged,
            'commented': commented,
            'skipped': skipped,
            'errors': errors,
            'success_rate': ((auto_merged + commented) / max(processed, 1)) * 100
        }

    def generate_report(self) -> str:
        """Generate comprehensive report"""
        summary = self.results['summary']
        
        report = f"""# PR Auto-Reviewer Report

**Generated:** {self.results['timestamp']}
**Mode:** {self.results['mode'].upper()}

## Summary
- **Total PRs Processed:** {summary.get('total_processed', 0)}
- **Auto-Merged:** {summary.get('auto_merged', 0)}
- **Commented:** {summary.get('commented', 0)}
- **Skipped:** {summary.get('skipped', 0)}
- **Errors:** {summary.get('errors', 0)}
- **Success Rate:** {summary.get('success_rate', 0):.1f}%

## Auto-Merged PRs
"""
        
        for pr in self.results['auto_merged']:
            report += f"- **#{pr['pr_number']}:** {pr['title']} (Confidence: {pr['confidence']:.1f}%)\n"
        
        if not self.results['auto_merged']:
            report += "- None\n"

        report += "\n## PRs with Comments Added\n"
        
        for pr in self.results['commented']:
            report += f"- **#{pr['pr_number']}:** {pr['title']} (Confidence: {pr['confidence']:.1f}%)\n"
        
        if not self.results['commented']:
            report += "- None\n"

        if self.results['errors']:
            report += "\n## Errors\n"
            for error in self.results['errors']:
                report += f"- {error}\n"

        return report


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='PR Auto-Reviewer')
    parser.add_argument('--live', action='store_true', help='Run in live mode (default is dry-run)')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', help='Run in dry-run mode (default)')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--output', default='auto_review_results.json', help='Output file for results')
    parser.add_argument('--report-file', type=str, default='auto_review_report.md', help='Path to save report file')
    args = parser.parse_args()

    # Determine mode
    dry_run = not args.live if args.live else True

    # Load configuration
    config = {}
    config_path = args.config if args.config else Path(__file__).with_name('config.yaml')
    
    if Path(config_path).exists():
        try:
            import yaml
            with open(config_path, 'r') as f:
                full_config = yaml.safe_load(f)
                config = full_config.get('auto_reviewer', {})
                # Also include relevant sections from main config
                config.update({
                    'merge_strategies': full_config.get('merge_strategies', {}),
                    'auto_merge_confidence_threshold': 85.0,
                    'comment_confidence_threshold': 60.0,
                    'max_auto_merges_per_run': 5
                })
                logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.warning(f"Error loading config: {e}, using defaults")

    # Initialize and run auto-reviewer
    reviewer = PRAutoReviewer(dry_run=dry_run, config=config)
    results = reviewer.review_all_prs()

    # Generate and save reports
    report = reviewer.generate_report()
    print("\n" + "=" * 80)
    print(report)

    # Save detailed results
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Results saved to {args.output}")

    # Save report
    with open(args.report_file, 'w') as f:
        f.write(report)
    logger.info(f"Report saved to {args.report_file}")


if __name__ == "__main__":
    main()