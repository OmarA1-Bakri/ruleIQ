#!/usr/bin/env python3
"""
Enhanced PR Orchestrator - Main entry point for automated PR management
This script provides a unified interface for:
1. Reviewing all PRs automatically
2. Merging safe PRs with high confidence
3. Adding actionable comments to uncertain PRs
4. Comprehensive safety checks and audit trail
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import logging

# Import existing components
from pr_cleanup_orchestrator import PRCleanupOrchestrator
from pr_auto_reviewer import PRAutoReviewer
from github_api_client import GitHubAPIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedPROrchestrator:
    """Enhanced orchestrator combining automatic review with existing cleanup"""

    def __init__(self, dry_run: bool = True, config: Dict = None):
        """Initialize the enhanced orchestrator"""
        self.dry_run = dry_run
        self.config = config or {}
        
        # Initialize components
        self.auto_reviewer = PRAutoReviewer(dry_run=dry_run, config=config)
        self.cleanup_orchestrator = PRCleanupOrchestrator(dry_run=dry_run, config=config)
        self.client = GitHubAPIClient(dry_run=dry_run)
        
        # Results tracking
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'mode': 'dry_run' if dry_run else 'live',
            'auto_review_results': {},
            'cleanup_results': {},
            'summary': {},
            'recommendations': []
        }

    def execute_enhanced_cleanup(self) -> Dict:
        """Execute enhanced PR management workflow"""
        logger.info("=" * 80)
        logger.info("ENHANCED PR MANAGEMENT ORCHESTRATION")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info("=" * 80)

        try:
            # Phase 1: Automatic PR Review and Actions
            logger.info("\n🤖 PHASE 1: AUTOMATIC PR REVIEW")
            logger.info("=" * 50)
            
            auto_review_results = self.auto_reviewer.review_all_prs()
            self.results['auto_review_results'] = auto_review_results
            
            self._log_auto_review_summary(auto_review_results)

            # Phase 2: Remaining Cleanup (if needed)
            logger.info("\n🧹 PHASE 2: COMPREHENSIVE CLEANUP")
            logger.info("=" * 50)
            
            # Only run cleanup if there are still PRs that need processing
            remaining_prs = self._get_remaining_prs(auto_review_results)
            
            if remaining_prs:
                logger.info(f"Running cleanup for {len(remaining_prs)} remaining PRs")
                cleanup_results = self.cleanup_orchestrator.execute_cleanup()
                self.results['cleanup_results'] = cleanup_results
            else:
                logger.info("No additional cleanup needed - all PRs processed by auto-reviewer")
                self.results['cleanup_results'] = {'skipped': True}

            # Phase 3: Generate final recommendations
            logger.info("\n📊 PHASE 3: GENERATING RECOMMENDATIONS")
            logger.info("=" * 50)
            
            self._generate_recommendations()
            self._generate_final_summary()

        except Exception as e:
            error_msg = f"Critical error in enhanced orchestration: {str(e)}"
            logger.error(error_msg)
            self.results['summary'] = {'error': error_msg}

        logger.info("\n" + "=" * 80)
        logger.info("ENHANCED PR MANAGEMENT COMPLETE")
        logger.info("=" * 80)

        return self.results

    def _log_auto_review_summary(self, auto_review_results: Dict):
        """Log summary of auto-review results"""
        summary = auto_review_results.get('summary', {})
        
        logger.info(f"Auto-Review Summary:")
        logger.info(f"  - Total Processed: {summary.get('total_processed', 0)}")
        logger.info(f"  - Auto-Merged: {summary.get('auto_merged', 0)}")
        logger.info(f"  - Commented: {summary.get('commented', 0)}")
        logger.info(f"  - Skipped: {summary.get('skipped', 0)}")
        logger.info(f"  - Success Rate: {summary.get('success_rate', 0):.1f}%")

        # Log specific actions
        if auto_review_results.get('auto_merged'):
            logger.info("  ✅ Auto-merged PRs:")
            for pr in auto_review_results['auto_merged']:
                logger.info(f"    - #{pr['pr_number']}: {pr['title']}")

        if auto_review_results.get('commented'):
            logger.info("  💬 PRs with helpful comments:")
            for pr in auto_review_results['commented']:
                logger.info(f"    - #{pr['pr_number']}: {pr['title']}")

    def _get_remaining_prs(self, auto_review_results: Dict) -> List:
        """Get PRs that still need processing after auto-review"""
        try:
            all_prs = self.client.get_all_open_prs()
            processed_pr_numbers = {pr['pr_number'] for pr in auto_review_results.get('processed_prs', [])}
            
            remaining = [pr for pr in all_prs if pr.number not in processed_pr_numbers]
            return remaining
            
        except Exception as e:
            logger.warning(f"Could not determine remaining PRs: {e}")
            return []

    def _generate_recommendations(self):
        """Generate actionable recommendations based on results"""
        recommendations = []
        
        auto_summary = self.results['auto_review_results'].get('summary', {})
        
        # Recommendations based on auto-review results
        if auto_summary.get('errors', 0) > 0:
            recommendations.append({
                'priority': 'high',
                'category': 'errors',
                'title': 'Review Auto-Review Errors',
                'description': f"There were {auto_summary['errors']} errors during auto-review. Check logs and retry failed operations.",
                'action': 'investigate_errors'
            })

        if auto_summary.get('skipped', 0) > 0:
            recommendations.append({
                'priority': 'medium',
                'category': 'manual_review',
                'title': 'Manual Review Required',
                'description': f"{auto_summary['skipped']} PRs were skipped and require manual review.",
                'action': 'manual_review_skipped_prs'
            })

        low_confidence_prs = [
            pr for pr in self.results['auto_review_results'].get('processed_prs', [])
            if pr.get('confidence_score', 0) < 60 and pr.get('action_taken') == 'manual_review_required'
        ]
        
        if low_confidence_prs:
            recommendations.append({
                'priority': 'medium',
                'category': 'code_quality',
                'title': 'Improve PR Quality',
                'description': f"{len(low_confidence_prs)} PRs have low confidence scores. Consider improving PR descriptions, adding tests, or breaking down large changes.",
                'action': 'improve_pr_quality',
                'affected_prs': [pr['pr_number'] for pr in low_confidence_prs]
            })

        # Success recommendations
        if auto_summary.get('auto_merged', 0) > 0:
            recommendations.append({
                'priority': 'info',
                'category': 'success',
                'title': 'Automated Merges Successful',
                'description': f"Successfully auto-merged {auto_summary['auto_merged']} PRs. No further action needed.",
                'action': 'none'
            })

        if auto_summary.get('commented', 0) > 0:
            recommendations.append({
                'priority': 'info',
                'category': 'success',
                'title': 'Helpful Comments Added',
                'description': f"Added helpful comments to {auto_summary['commented']} PRs. Authors should address the feedback.",
                'action': 'monitor_pr_updates'
            })

        self.results['recommendations'] = recommendations

    def _generate_final_summary(self):
        """Generate final summary of all actions"""
        auto_summary = self.results['auto_review_results'].get('summary', {})
        cleanup_summary = self.results['cleanup_results'].get('summary', {}) if not self.results['cleanup_results'].get('skipped') else {}
        
        total_processed = auto_summary.get('total_processed', 0) + cleanup_summary.get('prs_processed', 0)
        total_merged = auto_summary.get('auto_merged', 0) + cleanup_summary.get('prs_merged', 0)
        total_actions = auto_summary.get('total_processed', 0) + cleanup_summary.get('total_actions', 0)
        
        self.results['summary'] = {
            'total_prs_processed': total_processed,
            'total_prs_merged': total_merged,
            'total_actions_taken': total_actions,
            'auto_review_success_rate': auto_summary.get('success_rate', 0),
            'recommendations_count': len(self.results['recommendations']),
            'mode': self.results['mode'],
            'execution_successful': True
        }

    def generate_comprehensive_report(self) -> str:
        """Generate comprehensive report of all activities"""
        summary = self.results['summary']
        auto_results = self.results['auto_review_results']
        
        report = f"""# Enhanced PR Management Report

**Generated:** {self.results['timestamp']}
**Mode:** {self.results['mode'].upper()}
**Execution Status:** {'✅ Successful' if summary.get('execution_successful') else '❌ Failed'}

## 📊 Executive Summary
- **Total PRs Processed:** {summary.get('total_prs_processed', 0)}
- **Total PRs Merged:** {summary.get('total_prs_merged', 0)}
- **Auto-Review Success Rate:** {summary.get('auto_review_success_rate', 0):.1f}%
- **Recommendations Generated:** {summary.get('recommendations_count', 0)}

## 🤖 Automatic Review Results

### Auto-Merged PRs ✅
"""
        
        auto_merged = auto_results.get('auto_merged', [])
        if auto_merged:
            for pr in auto_merged:
                report += f"- **PR #{pr['pr_number']}:** {pr['title']}\n"
                report += f"  - Confidence: {pr['confidence']:.1f}%\n"
                report += f"  - Merge method: {pr['merge_method']}\n\n"
        else:
            report += "- None\n\n"

        report += "### PRs with Helpful Comments 💬\n"
        
        commented = auto_results.get('commented', [])
        if commented:
            for pr in commented:
                report += f"- **PR #{pr['pr_number']}:** {pr['title']}\n"
                report += f"  - Confidence: {pr['confidence']:.1f}%\n"
                report += f"  - Decision: {pr['decision']}\n\n"
        else:
            report += "- None\n\n"

        # Add recommendations
        recommendations = self.results.get('recommendations', [])
        if recommendations:
            report += "## 📋 Recommendations\n\n"
            
            for rec in recommendations:
                priority_emoji = {'high': '🚨', 'medium': '⚠️', 'info': 'ℹ️'}.get(rec['priority'], '📌')
                report += f"### {priority_emoji} {rec['title']} ({rec['priority'].upper()})\n"
                report += f"**Category:** {rec['category']}\n"
                report += f"**Description:** {rec['description']}\n"
                report += f"**Action:** {rec['action']}\n"
                
                if 'affected_prs' in rec:
                    report += f"**Affected PRs:** {', '.join(f'#{pr}' for pr in rec['affected_prs'])}\n"
                
                report += "\n"
        
        # Add errors if any
        if auto_results.get('errors'):
            report += "## ❌ Errors\n\n"
            for error in auto_results['errors']:
                report += f"- {error}\n"
            report += "\n"

        report += """## 🔄 Next Steps

1. **Review auto-merged PRs** - Verify they were merged correctly
2. **Check commented PRs** - Ensure authors are addressing feedback  
3. **Handle manual review PRs** - Review PRs that couldn't be automated
4. **Monitor CI/CD** - Ensure merged changes don't break anything
5. **Update automation** - Improve rules based on results

---
*This report was generated by the Enhanced PR Management Orchestrator*
"""

        return report


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Enhanced PR Management Orchestrator')
    parser.add_argument('--live', action='store_true', help='Run in live mode (default is dry-run)')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', help='Run in dry-run mode (default)')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--output', default='enhanced_orchestration_results.json', help='Output file for results')
    parser.add_argument('--report-file', type=str, default='enhanced_orchestration_report.md', help='Path to save report file')
    parser.add_argument('--auto-review-only', action='store_true', help='Run only auto-review phase')
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
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.warning(f"Error loading config: {e}, using defaults")

    # Initialize and run orchestrator
    if args.auto_review_only:
        # Run only auto-review
        reviewer = PRAutoReviewer(dry_run=dry_run, config=config)
        results = reviewer.review_all_prs()
        report = reviewer.generate_report()
        
        # Save results
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
            
        with open(args.report_file, 'w') as f:
            f.write(report)
    else:
        # Run full enhanced orchestration
        orchestrator = EnhancedPROrchestrator(dry_run=dry_run, config=config)
        results = orchestrator.execute_enhanced_cleanup()
        
        # Generate comprehensive report
        report = orchestrator.generate_comprehensive_report()
        
        # Save results
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
            
        with open(args.report_file, 'w') as f:
            f.write(report)

    # Display report
    print("\n" + "=" * 80)
    print(report)
    print("=" * 80)
    
    logger.info(f"Results saved to {args.output}")
    logger.info(f"Report saved to {args.report_file}")


if __name__ == "__main__":
    main()