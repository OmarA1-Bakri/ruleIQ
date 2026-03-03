"""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

Enforcement Database Analyzer for IQ Agent
Provides real-world enforcement patterns and risk calibration data
"""
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
from dataclasses import dataclass, field


@dataclass
class EnforcementPattern:
    """Represents a pattern extracted from enforcement actions"""
    pattern_id: str
    pattern_type: str
    frequency: int
    avg_penalty: float
    max_penalty: float
    affected_sectors: List[str]
    common_violations: List[str]
    key_lessons: List[str]
    risk_multiplier: float
    evidence_references: List[str] = field(default_factory=list)


@dataclass
class RegulatoryTrend:
    """Tracks regulatory enforcement trends over time"""
    regulator: str
    trend_direction: str
    focus_areas: List[str]
    recent_penalty_avg: float
    year_over_year_change: float
    predicted_focus: List[str]


class EnforcementAnalyzer:
    """
    Analyzes enforcement database to provide IQ with:
    1. Real-world risk calibration data
    2. Pattern recognition for compliance gaps
    3. Evidence for claims (≥3 sources requirement)
    4. Predictive insights on regulatory focus
    """

    def __init__(self, enforcement_db_path: str=
        'data/enforcement/uk_enforcement_database.json'):
        """Initialize with enforcement database"""
        self.db_path = Path(enforcement_db_path)
        self.enforcement_data = self._load_database()
        self.patterns_cache = {}
        self.sector_risks = {}
        self._analyze_patterns()

    def _load_database(self) ->Dict[str, Any]:
        """Load enforcement database"""
        if not self.db_path.exists():
            logger.info('Warning: Enforcement database not found at %s' %
                self.db_path)
            return {'enforcement_actions': [], 'pattern_analysis': {}}
        with open(self.db_path, 'r') as f:
            return json.load(f)

    def _analyze_patterns(self) ->None:
        """Pre-analyze patterns for quick retrieval"""
        actions = self.enforcement_data.get('enforcement_actions', [])
        pattern_groups = defaultdict(list)
        for action in actions:
            for tag in action.get('pattern_tags', []):
                pattern_groups[tag].append(action)
        for pattern_tag, actions in pattern_groups.items():
            penalties = [a.get('penalty_amount', 0) for a in actions]
            sectors = list(set(a.get('sector', '') for a in actions))
            violations = []
            lessons = []
            for action in actions:
                violations.extend(action.get('violation_details', {}).get(
                    'secondary_violations', []))
                lessons.extend(action.get('lessons_learned', []))
            self.patterns_cache[pattern_tag] = EnforcementPattern(pattern_id
                =pattern_tag, pattern_type=self._categorize_pattern(
                pattern_tag), frequency=len(actions), avg_penalty=
                statistics.mean(penalties) if penalties else 0, max_penalty
                =max(penalties) if penalties else 0, affected_sectors=
                sectors, common_violations=list(set(violations))[:5],
                key_lessons=list(set(lessons))[:3], risk_multiplier=self.
                _calculate_risk_multiplier(penalties, len(actions)),
                evidence_references=[a['id'] for a in actions[:3]])

    def _categorize_pattern(self, pattern_tag: str) ->str:
        """Categorize pattern type"""
        categories = {'technical': ['technical_measures', 'access_control',
            'security', 'encryption'], 'governance': ['governance',
            'oversight', 'management', 'accountability'], 'consumer': [
            'consumer', 'customer', 'fairness', 'vulnerable'], 'data': [
            'data', 'privacy', 'gdpr', 'consent', 'retention'], 'financial':
            ['aml', 'kyc', 'transaction', 'market', 'trading'],
            'operational': ['quality', 'safety', 'staffing', 'training']}
        for category, keywords in categories.items():
            if any(keyword in pattern_tag.lower() for keyword in keywords):
                return category
        return 'general'

    def _calculate_risk_multiplier(self, penalties: List[float], frequency: int
        ) ->float:
        """Calculate risk multiplier based on enforcement patterns"""
        if not penalties:
            return 1.0
        avg_penalty = statistics.mean(penalties)
        penalty_factor = min(avg_penalty / 10000000, 2.0)
        frequency_factor = min(frequency / 5, 1.5)
        return 1.0 + penalty_factor * 0.5 + frequency_factor * 0.3

    def get_enforcement_evidence(self, regulation: str, violation_type:
        Optional[str]=None, sector: Optional[str]=None) ->List[Dict[str, Any]]:
        """
        Get enforcement evidence for IQ's ≥3 sources requirement

        Args:
            regulation: Regulation ID (e.g., 'gdpr', 'consumer-duty')
            violation_type: Specific violation category
            sector: Business sector

        Returns:
            List of relevant enforcement actions as evidence
        """
        actions = self.enforcement_data.get('enforcement_actions', [])
        relevant_actions = []
        for action in actions:
            score = 0
            if regulation.lower() in action.get('regulation', '').lower():
                score += 3
            if violation_type and violation_type in action.get(
                'violation_category', ''):
                score += 2
            if sector and sector == action.get('sector', ''):
                score += 1
            if score > 0:
                relevant_actions.append({'case_id': action['id'], 'date':
                    action['date'], 'penalty': action.get('penalty_amount',
                    0), 'violation': action['violation_details'][
                    'primary_violation'], 'lessons': action.get(
                    'lessons_learned', []), 'relevance_score': score,
                    'reference': f"{action['regulator']}-{action['id']}"})
        relevant_actions.sort(key=lambda x: (x['relevance_score'], x['date'
            ]), reverse=True)
        return relevant_actions[:5]

    def calculate_risk_adjustment(self, base_risk: float, regulation: str,
        business_context: Dict[str, Any]) ->Tuple[float, str]:
        """
        Adjust risk score based on enforcement patterns

        Args:
            base_risk: Initial risk score (0-10)
            regulation: Regulation identifier
            business_context: Business profile data

        Returns:
            Tuple of (adjusted_risk, explanation)
        """
        adjustments = []
        sector = business_context.get('industry', '').lower()
        size = business_context.get('company_size', '').lower()
        evidence = self.get_enforcement_evidence(regulation, sector=sector)
        if evidence:
            avg_penalty = statistics.mean([e['penalty'] for e in evidence if
                e['penalty'] > 0])
            if avg_penalty > 20000000:
                adjustments.append((1.5, 'High penalty precedents (£20M+)'))
            elif avg_penalty > 5000000:
                adjustments.append((1.2, 'Moderate penalty precedents (£5M+)'))
            sector_violations = [e for e in evidence if e.get('sector') ==
                sector]
            if len(sector_violations) >= 3:
                adjustments.append((1.3,
                    f'Frequent enforcement in {sector} sector'))
        if business_context.get('serves_vulnerable_customers'):
            vulnerable_cases = [e for e in evidence if 'vulnerable' in str(
                e.get('violation', '')).lower()]
            if vulnerable_cases:
                adjustments.append((1.4, 'Vulnerable population risk factor'))
        if size == 'enterprise' and evidence:
            adjustments.append((1.1, 'Enterprise-scale enforcement risk'))
        total_multiplier = 1.0
        explanations = []
        for multiplier, explanation in adjustments:
            total_multiplier *= multiplier
            explanations.append(explanation)
        adjusted_risk = min(base_risk * total_multiplier, 10.0)
        explanation = (
            f'Risk adjusted from {base_risk:.1f} to {adjusted_risk:.1f}. ')
        if explanations:
            explanation += 'Factors: ' + '; '.join(explanations)
        else:
            explanation += 'No significant enforcement patterns found.'
        return adjusted_risk, explanation

    def identify_compliance_gaps(self, business_profile: Dict[str, Any],
        current_controls: List[str]) ->List[Dict[str, Any]]:
        """
        Identify potential compliance gaps based on enforcement patterns

        Args:
            business_profile: Business context data
            current_controls: List of currently implemented controls

        Returns:
            List of identified gaps with priority scores
        """
        gaps = []
        sector = business_profile.get('industry', '').lower()
        sector_actions = [a for a in self.enforcement_data.get(
            'enforcement_actions', []) if a.get('sector', '').lower() == sector
            ]
        gap_frequency = defaultdict(int)
        for action in sector_actions:
            for gap in action.get('compliance_gaps_identified', []):
                if gap not in current_controls:
                    gap_frequency[gap] += 1
        for gap, frequency in gap_frequency.items():
            examples = [a['id'] for a in sector_actions if gap in a.get(
                'compliance_gaps_identified', [])][:3]
            gaps.append({'gap_id': gap, 'priority_score': frequency * 2,
                'enforcement_examples': examples, 'recommended_action':
                self._get_gap_remediation(gap), 'estimated_risk_reduction':
                min(frequency * 0.5, 2.0)})
        gaps.sort(key=lambda x: x['priority_score'], reverse=True)
        return gaps[:10]

    def _get_gap_remediation(self, gap: str) ->str:
        """Get remediation recommendation for a gap"""
        remediations = {'access_control_policy':
            'Implement role-based access control with MFA',
            'incident_response_plan':
            'Develop and test incident response procedures',
            'vulnerable_customer_policy':
            'Create vulnerable customer identification and support framework',
            'transaction_monitoring_system':
            'Deploy automated transaction monitoring with ML',
            'consent_management_system':
            'Implement granular consent tracking and preference center',
            'data_retention_policy':
            'Establish automated data retention and deletion procedures',
            'affordability_assessment_framework':
            'Build risk-based affordability checking system',
            'environmental_monitoring_program':
            'Implement continuous environmental monitoring',
            'age_verification_system':
            'Deploy robust age verification with multiple checks',
            'quality_assurance_program':
            'Establish independent QA with regular audits'}
        return remediations.get(gap,
            f"Implement controls to address {gap.replace('_', ' ')}")

    def get_regulatory_trends(self, regulator: Optional[str]=None,
        timeframe_days: int=365) ->List[RegulatoryTrend]:
        """
        Analyze regulatory trends for predictive insights

        Args:
            regulator: Specific regulator to analyze (None for all)
            timeframe_days: Days to look back for trend analysis

        Returns:
            List of regulatory trends
        """
        trends = []
        cutoff_date = datetime.now() - timedelta(days=timeframe_days)
        regulator_actions = defaultdict(list)
        for action in self.enforcement_data.get('enforcement_actions', []):
            action_date = datetime.strptime(action['date'], '%Y-%m-%d')
            if action_date >= cutoff_date:
                reg = action['regulator']
                if not regulator or reg == regulator:
                    regulator_actions[reg].append(action)
        for reg, actions in regulator_actions.items():
            if len(actions) < 2:
                continue
            penalties = [a.get('penalty_amount', 0) for a in actions]
            recent_penalties = penalties[-5:] if len(penalties
                ) >= 5 else penalties
            older_penalties = penalties[:-5] if len(penalties) > 5 else [0]
            avg_recent = statistics.mean(recent_penalties
                ) if recent_penalties else 0
            avg_older = statistics.mean(older_penalties
                ) if older_penalties else avg_recent
            if avg_recent > avg_older * 1.2:
                direction = 'increasing'
            elif avg_recent < avg_older * 0.8:
                direction = 'decreasing'
            else:
                direction = 'stable'
            focus_areas = []
            for action in actions[-5:]:
                focus_areas.extend(action.get('pattern_tags', []))
            focus_areas = list(set(focus_areas))[:5]
            predicted = self._predict_regulatory_focus(reg, actions)
            trends.append(RegulatoryTrend(regulator=reg, trend_direction=
                direction, focus_areas=focus_areas, recent_penalty_avg=
                avg_recent, year_over_year_change=(avg_recent - avg_older) /
                avg_older if avg_older > 0 else 0, predicted_focus=predicted))
        return trends

    def _predict_regulatory_focus(self, regulator: str, recent_actions:
        List[Dict]) ->List[str]:
        """Predict future regulatory focus areas"""
        predictions = []
        pattern_trajectory = defaultdict(int)
        for i, action in enumerate(recent_actions):
            weight = (i + 1) / len(recent_actions)
            for tag in action.get('pattern_tags', []):
                pattern_trajectory[tag] += weight
        sorted_patterns = sorted(pattern_trajectory.items(), key=lambda x:
            x[1], reverse=True)
        predictions = [pattern for pattern, _ in sorted_patterns[:3]]
        regulator_focus = {'ICO': ['ai_governance', 'children_privacy',
            'international_transfers'], 'FCA': ['consumer_duty',
            'operational_resilience', 'crypto_assets'], 'CMA': [
            'digital_markets', 'green_claims', 'subscription_traps']}
        if regulator in regulator_focus:
            predictions.extend(regulator_focus[regulator])
        return list(set(predictions))[:5]

    def generate_enforcement_summary(self, regulation: str,
        business_context: Dict[str, Any]) ->Dict[str, Any]:
        """
        Generate comprehensive enforcement summary for IQ agent

        Args:
            regulation: Regulation to analyze
            business_context: Business profile data

        Returns:
            Comprehensive enforcement intelligence summary
        """
        evidence = self.get_enforcement_evidence(regulation=regulation,
            sector=business_context.get('industry'))
        base_risk = business_context.get('risk_score', 5.0)
        adjusted_risk, risk_explanation = self.calculate_risk_adjustment(
            base_risk, regulation, business_context)
        current_controls = business_context.get('implemented_controls', [])
        gaps = self.identify_compliance_gaps(business_context, current_controls,
            )
        trends = self.get_regulatory_trends(timeframe_days=365)
        all_lessons = []
        for e in evidence[:3]:
            all_lessons.extend(e.get('lessons', []))
        unique_lessons = list(set(all_lessons))[:5]
        return {'regulation': regulation, 'enforcement_evidence': evidence[
            :3], 'risk_assessment': {'base_risk': base_risk,
            'adjusted_risk': adjusted_risk, 'explanation': risk_explanation
            }, 'compliance_gaps': gaps[:5], 'lessons_learned':
            unique_lessons, 'regulatory_trends': [{'regulator': t.regulator,
            'direction': t.trend_direction, 'focus': t.focus_areas} for t in
            trends[:3]], 'recommended_actions': self.
            _generate_recommendations(evidence, gaps), 'confidence_level':
            self._calculate_confidence(len(evidence))}

    def _generate_recommendations(self, evidence: List[Dict], gaps: List[Dict]
        ) ->List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        if gaps:
            top_gap = gaps[0]
            recommendations.append(
                f"Priority 1: {top_gap['recommended_action']} (Risk reduction: {top_gap['estimated_risk_reduction']:.1f} points)",
                )
        if evidence:
            common_violations = set()
            for e in evidence[:3]:
                if 'lessons' in e:
                    common_violations.update(e['lessons'][:1])
            for violation in list(common_violations)[:2]:
                recommendations.append(f'Implement: {violation}')
        if len(recommendations) < 3:
            recommendations.extend([
                'Conduct comprehensive compliance gap assessment',
                'Implement continuous monitoring and alerting',
                'Establish board-level compliance oversight'])
        return recommendations[:5]

    def _calculate_confidence(self, evidence_count: int) ->str:
        """Calculate confidence level based on available evidence"""
        if evidence_count >= 5:
            return 'HIGH'
        elif evidence_count >= 3:
            return 'MEDIUM'
        elif evidence_count >= 1:
            return 'LOW'
        else:
            return 'INSUFFICIENT'


class IQEnforcementIntegration:
    """
    Integrates enforcement intelligence into IQ's decision-making
    Implements the learn() and remember() capabilities with real-world data
    """

    def __init__(self, enforcement_analyzer: EnforcementAnalyzer):
        self.analyzer = enforcement_analyzer
        self.learning_cache = {}

    def enhance_risk_assessment(self, regulation_id: str, business_profile:
        Dict[str, Any], current_risk: float) ->Dict[str, Any]:
        """
        Enhance IQ's risk assessment with enforcement data
        Supports IQ's _assess_node() function
        """
        summary = self.analyzer.generate_enforcement_summary(regulation=
            regulation_id, business_context=business_profile)
        return {'original_risk': current_risk, 'adjusted_risk': summary[
            'risk_assessment']['adjusted_risk'], 'adjustment_reason':
            summary['risk_assessment']['explanation'],
            'evidence_references': [e['case_id'] for e in summary[
            'enforcement_evidence']], 'confidence': summary[
            'confidence_level'], 'recommended_controls': summary[
            'recommended_actions'], 'compliance_gaps': summary[
            'compliance_gaps'], 'learning_points': summary['lessons_learned']}

    def learn_from_enforcement(self, regulation_id: str, sector: str) ->Dict[
        str, Any]:
        """
        Extract learning patterns for IQ's _learn_node()
        """
        cache_key = f'{regulation_id}:{sector}'
        if cache_key in self.learning_cache:
            return self.learning_cache[cache_key]
        patterns = []
        for pattern_id, pattern in self.analyzer.patterns_cache.items():
            if sector in pattern.affected_sectors:
                patterns.append({'pattern': pattern_id, 'frequency':
                    pattern.frequency, 'risk_impact': pattern.
                    risk_multiplier, 'lessons': pattern.key_lessons,
                    'evidence': pattern.evidence_references})
        patterns.sort(key=lambda x: x['frequency'] * x['risk_impact'],
            reverse=True)
        learning = {'regulation': regulation_id, 'sector': sector,
            'patterns': patterns[:5], 'key_insights': self.
            _extract_insights(patterns), 'timestamp': datetime.now().
            isoformat()}
        self.learning_cache[cache_key] = learning
        return learning

    def _extract_insights(self, patterns: List[Dict]) ->List[str]:
        """Extract key insights from patterns"""
        insights = []
        if patterns:
            top_pattern = patterns[0]
            insights.append(
                f"Most common issue: {top_pattern['pattern']} (seen {top_pattern['frequency']} times)",
                )
            highest_risk = max(patterns, key=lambda x: x['risk_impact'])
            if highest_risk != top_pattern:
                insights.append(
                    f"Highest risk: {highest_risk['pattern']} (risk multiplier: {highest_risk['risk_impact']:.1f}x)",
                    )
            all_lessons = []
            for p in patterns[:3]:
                all_lessons.extend(p.get('lessons', []))
            if all_lessons:
                insights.append(f'Key lesson: {all_lessons[0]}')
        return insights

    def get_evidence_for_claim(self, claim_type: str, regulation: str,
        context: Dict[str, Any]) ->List[Dict[str, Any]]:
        """
        Provide evidence for IQ's claims (≥3 sources requirement)
        """
        enforcement_evidence = self.analyzer.get_enforcement_evidence(
            regulation=regulation, sector=context.get('industry'))
        formatted_evidence = []
        for e in enforcement_evidence[:3]:
            formatted_evidence.append({'source_type': 'enforcement_action',
                'source_id': e['case_id'], 'relevance': e['relevance_score'
                ], 'date': e['date'], 'summary': e['violation'], 'penalty':
                e['penalty'], 'url':
                f"https://regulator.gov.uk/enforcement/{e['case_id']}"})
        if len(formatted_evidence) < 3:
            pattern_evidence = {'source_type': 'pattern_analysis',
                'source_id': 'enforcement_patterns_2024', 'relevance': 5,
                'date': datetime.now().isoformat(), 'summary':
                'Statistical analysis of enforcement patterns', 'url':
                'internal://enforcement/patterns'}
            formatted_evidence.append(pattern_evidence)
        return formatted_evidence


if __name__ == '__main__':
    analyzer = EnforcementAnalyzer()
    business_context = {'industry': 'finance', 'company_size': 'enterprise',
        'serves_vulnerable_customers': True, 'risk_score': 6.0}
    adjusted_risk, explanation = analyzer.calculate_risk_adjustment(base_risk
        =6.0, regulation='gdpr', business_context=business_context)
    logger.info('Risk Adjustment: %s' % adjusted_risk)
    logger.info('Explanation: %s' % explanation)
    evidence = analyzer.get_enforcement_evidence(regulation='gdpr', sector=
        'finance')
    logger.info('\nEnforcement Evidence Found: %s cases' % len(evidence))
    for e in evidence[:3]:
        logger.info('  - %s: £%s penalty' % (e['case_id'], e['penalty']))
    gaps = analyzer.identify_compliance_gaps(business_profile=
        business_context, current_controls=['access_control_policy',
        'incident_response_plan'])
    logger.info('\nCompliance Gaps Identified: %s' % len(gaps))
    for gap in gaps[:3]:
        logger.info('  - %s: Priority %s' % (gap['gap_id'], gap[
            'priority_score']))
    trends = analyzer.get_regulatory_trends()
    logger.info('\nRegulatory Trends:')
    for trend in trends[:3]:
        print(
            f'  - {trend.regulator}: {trend.trend_direction} (YoY: {trend.year_over_year_change:+.1%})',
            )
