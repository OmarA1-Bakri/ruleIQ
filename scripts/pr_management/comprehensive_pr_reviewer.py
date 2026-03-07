#!/usr/bin/env python3
"""
Comprehensive PR Review Script - Analyzes all open PRs and provides actionable steps
"""

import json
import sys
import os
from typing import List, Dict, Any
from datetime import datetime
import logging

# Add the scripts directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from github_api_client import GitHubAPIClient, PRInfo
    from pr_analyzer import PRAnalyzer
    from pr_decision_matrix import PRDecisionMatrix
    from dependabot_handler import DependabotHandler
    from security_pr_reviewer import SecurityPRReviewer
    from feature_pr_reviewer import FeaturePRReviewer
    from ci_status_checker import CIStatusChecker
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure all required modules are available")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ComprehensivePRReviewer:
    """Comprehensive PR review system that provides actionable steps for all open PRs"""
    
    def __init__(self, dry_run: bool = True):
        """Initialize the comprehensive PR reviewer"""
        self.dry_run = dry_run
        self.client = GitHubAPIClient(dry_run=dry_run)
        self.analyzer = PRAnalyzer(self.client)
        self.decision_matrix = PRDecisionMatrix()
        self.dependabot_handler = DependabotHandler(self.client)
        self.security_reviewer = SecurityPRReviewer(self.client)
        self.feature_reviewer = FeaturePRReviewer(self.client)
        self.ci_checker = CIStatusChecker(self.client)
        
        self.review_results = {
            'timestamp': datetime.now().isoformat(),
            'total_prs': 0,
            'pr_analyses': [],
            'recommendations': [],
            'auto_merge_candidates': [],
            'manual_review_required': [],
            'blocked_prs': [],
            'summary': {}
        }
    
    def review_all_prs(self) -> Dict[str, Any]:
        """Review all open PRs and provide actionable steps"""
        logger.info("Starting comprehensive PR review...")
        
        try:
            # Get all open PRs
            prs = self.client.get_all_open_prs()
            self.review_results['total_prs'] = len(prs)
            logger.info(f"Found {len(prs)} open pull requests")
            
            if not prs:
                logger.info("No open PRs found")
                return self.review_results
            
            # Analyze each PR individually
            for pr in prs:
                pr_analysis = self._analyze_individual_pr(pr)
                self.review_results['pr_analyses'].append(pr_analysis)
            
            # Generate overall recommendations
            self._generate_overall_recommendations()
            
            # Create summary
            self._create_summary()
            
            return self.review_results
            
        except Exception as e:
            logger.error(f"Error during PR review: {e}")
            self.review_results['error'] = str(e)
            return self.review_results
    
    def _analyze_individual_pr(self, pr: PRInfo) -> Dict[str, Any]:
        """Analyze an individual PR and provide specific recommendations"""
        logger.info(f"Analyzing PR #{pr.number}: {pr.title}")
        
        analysis = {
            'pr_number': pr.number,
            'title': pr.title,
            'author': pr.author,
            'created_at': pr.created_at.isoformat(),
            'is_draft': pr.draft,
            'size': {
                'additions': pr.additions,
                'deletions': pr.deletions,
                'changed_files': pr.changed_files
            },
            'category': self._categorize_pr(pr),
            'ci_status': self._check_ci_status(pr),
            'conflicts': pr.conflicts,
            'reviews': self._get_review_status(pr),
            'safety_assessment': self._assess_safety(pr),
            'additivity_assessment': self._assess_additivity(pr),
            'merge_readiness': self._assess_merge_readiness(pr),
            'recommendations': [],
            'next_steps': [],
            'risk_level': 'unknown'
        }
        
        # Category-specific analysis
        if analysis['category'] == 'dependabot':
            analysis.update(self._analyze_dependabot_pr(pr))
        elif analysis['category'] == 'security':
            analysis.update(self._analyze_security_pr(pr))
        elif analysis['category'] == 'feature':
            analysis.update(self._analyze_feature_pr(pr))
        
        # Generate final decision and recommendations
        analysis['final_decision'] = self._make_final_decision(analysis)
        analysis['recommendations'] = self._generate_pr_recommendations(analysis)
        analysis['next_steps'] = self._generate_next_steps(analysis)
        
        return analysis
    
    def _categorize_pr(self, pr: PRInfo) -> str:
        """Categorize the PR based on its characteristics"""
        if pr.is_dependabot:
            return 'dependabot'
        elif pr.is_security or 'security' in pr.title.lower():
            return 'security'
        elif pr.changed_files > 50 or pr.additions > 1000:
            return 'feature'
        elif 'fix' in pr.title.lower() or 'bug' in pr.title.lower():
            return 'bugfix'
        elif 'doc' in pr.title.lower() or 'readme' in pr.title.lower():
            return 'documentation'
        elif 'chore' in pr.title.lower() or 'deps' in pr.title.lower():
            return 'maintenance'
        else:
            return 'other'
    
    def _check_ci_status(self, pr: PRInfo) -> Dict[str, Any]:
        """Check CI status for the PR"""
        try:
            return self.ci_checker.check_pr_status(pr.number)
        except Exception as e:
            logger.warning(f"Could not check CI status for PR #{pr.number}: {e}")
            return {'overall_status': 'unknown', 'error': str(e)}
    
    def _get_review_status(self, pr: PRInfo) -> Dict[str, Any]:
        """Get review status for the PR"""
        try:
            reviews = self.client.get_pr_reviews(pr.number)
            approved_reviews = [r for r in reviews if r.get('state') == 'APPROVED']
            requested_changes = [r for r in reviews if r.get('state') == 'CHANGES_REQUESTED']
            
            return {
                'total_reviews': len(reviews),
                'approved_reviews': len(approved_reviews),
                'changes_requested': len(requested_changes),
                'has_approval': len(approved_reviews) > 0,
                'has_requested_changes': len(requested_changes) > 0
            }
        except Exception as e:
            logger.warning(f"Could not get review status for PR #{pr.number}: {e}")
            return {'error': str(e)}
    
    def _assess_safety(self, pr: PRInfo) -> Dict[str, Any]:
        """Assess the safety of the PR"""
        safety_score = 100  # Start with perfect score
        issues = []
        
        # Check size - large PRs are riskier
        if pr.additions + pr.deletions > 5000:
            safety_score -= 30
            issues.append("Extremely large PR with high risk")
        elif pr.additions + pr.deletions > 1000:
            safety_score -= 15
            issues.append("Large PR requiring careful review")
        
        # Check file count
        if pr.changed_files > 100:
            safety_score -= 20
            issues.append("High number of changed files")
        elif pr.changed_files > 50:
            safety_score -= 10
            issues.append("Moderate number of changed files")
        
        # Check for conflicts
        if pr.conflicts:
            safety_score -= 25
            issues.append("Has merge conflicts")
        
        # Age check
        age_days = (datetime.now(pr.created_at.tzinfo) - pr.created_at).days
        if age_days > 30:
            safety_score -= 10
            issues.append(f"PR is {age_days} days old")
        
        # Determine safety level
        if safety_score >= 90:
            level = 'very_safe'
        elif safety_score >= 70:
            level = 'safe'
        elif safety_score >= 50:
            level = 'moderate_risk'
        else:
            level = 'high_risk'
        
        return {
            'score': max(0, safety_score),
            'level': level,
            'issues': issues
        }
    
    def _assess_additivity(self, pr: PRInfo) -> Dict[str, Any]:
        """Assess whether the PR is positively additive to the codebase"""
        positives = []
        negatives = []
        score = 50  # Neutral starting point
        
        # Check title for positive indicators
        title_lower = pr.title.lower()
        if any(word in title_lower for word in ['feat', 'feature', 'add', 'improve', 'enhance', 'optimize']):
            score += 20
            positives.append("Appears to add new functionality or improvements")
        
        if any(word in title_lower for word in ['fix', 'bug', 'patch', 'resolve']):
            score += 15
            positives.append("Fixes bugs or issues")
        
        if any(word in title_lower for word in ['security', 'vulnerability', 'cve']):
            score += 25
            positives.append("Addresses security concerns")
        
        if any(word in title_lower for word in ['test', 'coverage', 'spec']):
            score += 10
            positives.append("Improves test coverage")
        
        if any(word in title_lower for word in ['doc', 'readme', 'documentation']):
            score += 10
            positives.append("Improves documentation")
        
        # Dependabot PRs are generally additive for security
        if pr.is_dependabot:
            score += 15
            positives.append("Automated dependency update")
        
        # Check for potential negatives
        if 'remove' in title_lower or 'delete' in title_lower:
            score -= 10
            negatives.append("Removes functionality")
        
        if 'break' in title_lower or 'breaking' in title_lower:
            score -= 20
            negatives.append("May contain breaking changes")
        
        # Large deletions might indicate removal of functionality
        if pr.deletions > pr.additions * 2:
            score -= 10
            negatives.append("Deletes more code than it adds")
        
        # Determine additivity level
        if score >= 80:
            level = 'highly_additive'
        elif score >= 60:
            level = 'additive'
        elif score >= 40:
            level = 'neutral'
        else:
            level = 'potentially_subtractive'
        
        return {
            'score': max(0, min(100, score)),
            'level': level,
            'positives': positives,
            'negatives': negatives
        }
    
    def _assess_merge_readiness(self, pr: PRInfo) -> Dict[str, Any]:
        """Assess whether the PR is ready to merge"""
        blockers = []
        warnings = []
        ready = True
        
        if pr.draft:
            blockers.append("PR is marked as draft")
            ready = False
        
        if pr.conflicts:
            blockers.append("Has merge conflicts")
            ready = False
        
        # Check CI status if available
        ci_status = self._check_ci_status(pr)
        if ci_status.get('overall_status') == 'failure':
            blockers.append("CI checks are failing")
            ready = False
        elif ci_status.get('overall_status') == 'pending':
            warnings.append("CI checks are still running")
        
        # Check reviews
        review_status = self._get_review_status(pr)
        if review_status.get('has_requested_changes'):
            blockers.append("Has requested changes from reviewers")
            ready = False
        elif not review_status.get('has_approval') and not pr.is_dependabot:
            warnings.append("No approving reviews")
        
        return {
            'ready': ready,
            'blockers': blockers,
            'warnings': warnings
        }
    
    def _analyze_dependabot_pr(self, pr: PRInfo) -> Dict[str, Any]:
        """Specific analysis for Dependabot PRs"""
        try:
            # Use existing dependabot handler to analyze
            results = self.dependabot_handler.process_single_pr(pr)
            return {
                'dependabot_analysis': results,
                'auto_merge_eligible': results.get('can_auto_merge', False)
            }
        except Exception as e:
            logger.warning(f"Could not analyze Dependabot PR #{pr.number}: {e}")
            return {'dependabot_analysis': {'error': str(e)}, 'auto_merge_eligible': False}
    
    def _analyze_security_pr(self, pr: PRInfo) -> Dict[str, Any]:
        """Specific analysis for security PRs"""
        try:
            # Use existing security reviewer
            results = self.security_reviewer._review_single_pr(pr)
            return {
                'security_analysis': results,
                'urgent': results.get('risk_assessment', {}).get('level') == 'high'
            }
        except Exception as e:
            logger.warning(f"Could not analyze security PR #{pr.number}: {e}")
            return {'security_analysis': {'error': str(e)}, 'urgent': False}
    
    def _analyze_feature_pr(self, pr: PRInfo) -> Dict[str, Any]:
        """Specific analysis for feature PRs"""
        try:
            # Use existing feature reviewer
            results = self.feature_reviewer.review_feature_pr(pr.number)
            return {
                'feature_analysis': results,
                'requires_careful_review': True
            }
        except Exception as e:
            logger.warning(f"Could not analyze feature PR #{pr.number}: {e}")
            return {'feature_analysis': {'error': str(e)}, 'requires_careful_review': True}
    
    def _make_final_decision(self, analysis: Dict[str, Any]) -> str:
        """Make final decision about the PR"""
        safety = analysis['safety_assessment']
        additivity = analysis['additivity_assessment']
        merge_readiness = analysis['merge_readiness']
        
        # Blocked if not ready to merge
        if not merge_readiness['ready']:
            return 'blocked'
        
        # Auto-merge conditions for dependabot PRs
        if (analysis['category'] == 'dependabot' and 
            safety['level'] in ['very_safe', 'safe'] and
            additivity['level'] in ['highly_additive', 'additive'] and
            analysis.get('auto_merge_eligible', False)):
            return 'auto_merge'
        
        # Manual review required for high-risk or unclear benefit
        if (safety['level'] in ['high_risk', 'moderate_risk'] or 
            additivity['level'] in ['neutral', 'potentially_subtractive']):
            return 'manual_review_required'
        
        # Ready for merge with quick review
        if (safety['level'] in ['very_safe', 'safe'] and 
            additivity['level'] in ['highly_additive', 'additive']):
            return 'ready_for_merge'
        
        return 'manual_review_required'
    
    def _generate_pr_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate specific recommendations for the PR"""
        recommendations = []
        
        # Based on final decision
        decision = analysis['final_decision']
        if decision == 'auto_merge':
            recommendations.append("✅ Safe to auto-merge - all checks passed")
        elif decision == 'blocked':
            recommendations.append("🚫 Blocked - resolve issues before merging")
            for blocker in analysis['merge_readiness']['blockers']:
                recommendations.append(f"   • Fix: {blocker}")
        elif decision == 'manual_review_required':
            recommendations.append("👥 Manual review required")
        elif decision == 'ready_for_merge':
            recommendations.append("✅ Ready for merge after quick review")
        
        # Specific safety recommendations
        safety_issues = analysis['safety_assessment']['issues']
        if safety_issues:
            recommendations.append("🔍 Safety concerns to address:")
            for issue in safety_issues:
                recommendations.append(f"   • {issue}")
        
        # Additivity recommendations
        if analysis['additivity_assessment']['level'] in ['neutral', 'potentially_subtractive']:
            recommendations.append("⚠️ Unclear benefit - verify this change adds value")
        
        return recommendations
    
    def _generate_next_steps(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate specific next steps for the PR"""
        next_steps = []
        decision = analysis['final_decision']
        
        if decision == 'auto_merge':
            if not self.dry_run:
                next_steps.append("Automatically merging PR")
            else:
                next_steps.append("Would auto-merge in live mode")
        
        elif decision == 'blocked':
            next_steps.append("Do not merge until blockers are resolved:")
            for blocker in analysis['merge_readiness']['blockers']:
                next_steps.append(f"1. Resolve: {blocker}")
        
        elif decision == 'manual_review_required':
            next_steps.append("Schedule manual review by team member")
            next_steps.append("Review code changes for quality and correctness")
            next_steps.append("Verify tests are adequate")
            next_steps.append("Check for potential side effects")
        
        elif decision == 'ready_for_merge':
            next_steps.append("Perform quick review and merge")
            next_steps.append("Verify CI passes")
            next_steps.append("Merge when ready")
        
        # Category-specific steps
        if analysis['category'] == 'security':
            next_steps.append("Priority: Review security implications")
        
        if analysis['category'] == 'feature':
            next_steps.append("Ensure feature documentation is updated")
            next_steps.append("Verify backward compatibility")
        
        return next_steps
    
    def _generate_overall_recommendations(self):
        """Generate overall recommendations based on all PR analyses"""
        auto_merge = []
        manual_review = []
        blocked = []
        ready_for_merge = []
        
        for analysis in self.review_results['pr_analyses']:
            pr_num = analysis['pr_number']
            decision = analysis['final_decision']
            
            if decision == 'auto_merge':
                auto_merge.append(pr_num)
            elif decision == 'manual_review_required':
                manual_review.append(pr_num)
            elif decision == 'blocked':
                blocked.append(pr_num)
            elif decision == 'ready_for_merge':
                ready_for_merge.append(pr_num)
        
        self.review_results['auto_merge_candidates'] = auto_merge
        self.review_results['manual_review_required'] = manual_review
        self.review_results['blocked_prs'] = blocked
        self.review_results['ready_for_merge'] = ready_for_merge
        
        # Generate recommendations
        recommendations = []
        
        if auto_merge:
            recommendations.append({
                'type': 'auto_merge',
                'priority': 'high',
                'action': f"Auto-merge {len(auto_merge)} safe Dependabot PRs",
                'pr_numbers': auto_merge
            })
        
        if ready_for_merge:
            recommendations.append({
                'type': 'quick_review',
                'priority': 'medium',
                'action': f"Quick review and merge {len(ready_for_merge)} ready PRs",
                'pr_numbers': ready_for_merge
            })
        
        if manual_review:
            recommendations.append({
                'type': 'manual_review',
                'priority': 'medium',
                'action': f"Schedule thorough review for {len(manual_review)} PRs",
                'pr_numbers': manual_review
            })
        
        if blocked:
            recommendations.append({
                'type': 'resolve_blockers',
                'priority': 'high',
                'action': f"Resolve blockers for {len(blocked)} PRs",
                'pr_numbers': blocked
            })
        
        self.review_results['recommendations'] = recommendations
    
    def _create_summary(self):
        """Create a summary of the review results"""
        total = self.review_results['total_prs']
        auto_merge_count = len(self.review_results.get('auto_merge_candidates', []))
        manual_review_count = len(self.review_results.get('manual_review_required', []))
        blocked_count = len(self.review_results.get('blocked_prs', []))
        ready_count = len(self.review_results.get('ready_for_merge', []))
        
        self.review_results['summary'] = {
            'total_prs': total,
            'auto_merge_ready': auto_merge_count,
            'manual_review_needed': manual_review_count,
            'blocked': blocked_count,
            'ready_for_merge': ready_count,
            'completion_rate': f"{((auto_merge_count + ready_count) / total * 100):.1f}%" if total > 0 else "0%"
        }
    
    def generate_report(self) -> str:
        """Generate a detailed markdown report"""
        results = self.review_results
        report = []
        
        report.append("# Comprehensive PR Review Report")
        report.append(f"Generated: {results['timestamp']}")
        report.append(f"Total PRs: {results['total_prs']}")
        report.append("")
        
        # Summary
        summary = results['summary']
        report.append("## Summary")
        report.append(f"- 🤖 Auto-merge ready: {summary['auto_merge_ready']}")
        report.append(f"- ✅ Ready for merge: {summary['ready_for_merge']}")
        report.append(f"- 👥 Manual review needed: {summary['manual_review_needed']}")
        report.append(f"- 🚫 Blocked: {summary['blocked']}")
        report.append(f"- 📊 Completion rate: {summary['completion_rate']}")
        report.append("")
        
        # Recommendations
        report.append("## Priority Actions")
        for rec in results['recommendations']:
            priority_emoji = "🔴" if rec['priority'] == 'high' else "🟡"
            report.append(f"{priority_emoji} **{rec['action']}**")
            report.append(f"   PRs: {', '.join(f'#{pr}' for pr in rec['pr_numbers'])}")
            report.append("")
        
        # Detailed PR Analysis
        report.append("## Detailed PR Analysis")
        for analysis in results['pr_analyses']:
            report.append(f"### PR #{analysis['pr_number']}: {analysis['title']}")
            report.append(f"**Author:** {analysis['author']}")
            report.append(f"**Category:** {analysis['category']}")
            report.append(f"**Decision:** {analysis['final_decision']}")
            
            # Safety and additivity
            safety = analysis['safety_assessment']
            additivity = analysis['additivity_assessment']
            report.append(f"**Safety:** {safety['level']} (score: {safety['score']})")
            report.append(f"**Additivity:** {additivity['level']} (score: {additivity['score']})")
            
            # Recommendations
            if analysis['recommendations']:
                report.append("**Recommendations:**")
                for rec in analysis['recommendations']:
                    report.append(f"- {rec}")
            
            # Next steps
            if analysis['next_steps']:
                report.append("**Next Steps:**")
                for step in analysis['next_steps']:
                    report.append(f"- {step}")
            
            report.append("")
        
        return "\n".join(report)


def main():
    """Main function to run the comprehensive PR review"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Comprehensive PR Review System')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Run in dry-run mode (default: True)')
    parser.add_argument('--live', action='store_true',
                       help='Run in live mode (will actually merge PRs)')
    parser.add_argument('--output', type=str, default='pr_review_report.md',
                       help='Output file for the report')
    
    args = parser.parse_args()
    
    # Determine run mode
    dry_run = not args.live
    
    print(f"Starting comprehensive PR review ({'DRY RUN' if dry_run else 'LIVE MODE'})...")
    
    # Initialize reviewer
    reviewer = ComprehensivePRReviewer(dry_run=dry_run)
    
    # Run the review
    results = reviewer.review_all_prs()
    
    # Generate report
    report = reviewer.generate_report()
    
    # Save report
    with open(args.output, 'w') as f:
        f.write(report)
    
    # Save JSON results
    json_output = args.output.replace('.md', '.json')
    with open(json_output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"Report saved to: {args.output}")
    print(f"JSON results saved to: {json_output}")
    
    # Print summary
    summary = results['summary']
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(f"Total PRs: {summary['total_prs']}")
    print(f"Auto-merge ready: {summary['auto_merge_ready']}")
    print(f"Ready for merge: {summary['ready_for_merge']}")
    print(f"Manual review needed: {summary['manual_review_needed']}")
    print(f"Blocked: {summary['blocked']}")
    print(f"Completion rate: {summary['completion_rate']}")
    
    if results.get('auto_merge_candidates'):
        print(f"\n🤖 Auto-merge candidates: {', '.join(f'#{pr}' for pr in results['auto_merge_candidates'])}")
    
    if results.get('blocked_prs'):
        print(f"\n🚫 Blocked PRs: {', '.join(f'#{pr}' for pr in results['blocked_prs'])}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())