/**
 * AI Service Integration Tests
 * Tests for Phase 1.5.3: Testing & Validation
 */

// vi.mock is hoisted by Vitest's transform above all import statements, so
// this mock runs before any module that depends on src/config/env is evaluated.
// This prevents the zod env-var validation from throwing during test collection.
import { vi } from 'vitest';

vi.mock('@/src/config/env', () => ({
  env: {
    NEXT_PUBLIC_API_URL: 'http://localhost:8000',
    NEXT_PUBLIC_WEBSOCKET_URL: 'ws://localhost:8000/ws',
    NEXT_PUBLIC_AUTH_DOMAIN: 'localhost',
    NEXT_PUBLIC_JWT_EXPIRES_IN: '86400',
    NEXT_PUBLIC_ENABLE_ANALYTICS: false,
    NEXT_PUBLIC_ENABLE_SENTRY: false,
    NEXT_PUBLIC_ENABLE_MOCK_DATA: false,
    NEXT_PUBLIC_ENV: 'test',
    NODE_ENV: 'test',
  },
}));

process.env['NEXT_PUBLIC_API_URL'] = 'http://localhost:8000';
process.env['NEXT_PUBLIC_USE_REAL_AI'] = 'false';
process.env['NODE_ENV'] = 'test';

import { assessmentAIService } from '@/lib/api/assessments-ai.service';
import type { BusinessProfile } from '@/types/api';

describe('AI Service Integration Tests', () => {
  // Test data for different business scenarios
  const testBusinessProfiles: Partial<BusinessProfile>[] = [
    {
      id: 'test-1',
      company_name: 'TechCorp Ltd',
      industry: 'Technology',
      size: 'medium',
      compliance_frameworks: ['GDPR', 'ISO 27001'],
    },
    {
      id: 'test-2',
      company_name: 'HealthCare Solutions',
      industry: 'Healthcare',
      size: 'large',
      compliance_frameworks: ['GDPR', 'HIPAA'],
    },
    {
      id: 'test-3',
      company_name: 'FinanceFirst Bank',
      industry: 'Financial Services',
      size: 'large',
      compliance_frameworks: ['GDPR', 'PCI DSS', 'FCA'],
    },
  ];

  const testAnswers = {
    company_size: '50-200',
    industry: 'technology',
    handles_personal_data: 'Yes',
    processes_payments: 'No',
    data_sensitivity: 'High',
    implementation_timeline: '3 months',
    biggest_concern: 'Data protection compliance',
    recent_incidents: 'No',
    compliance_budget: '£25K-£100K',
  };

  describe('Helper Methods Testing', () => {
    test('getBusinessProfileFromContext should extract context correctly', () => {
      const context = assessmentAIService.getBusinessProfileFromContext(
        testBusinessProfiles[0],
        testAnswers,
      );

      expect(context).toBeDefined();
      expect(context.industry).toBe('Technology');
      expect((context as any).size).toBe('50-200'); // From answers
    });

    test('getExistingPoliciesFromAnswers should identify policies', () => {
      const testAnswersWithPolicies = {
        ...testAnswers,
        privacy_policy: 'Yes',
        data_protection_policy: 'No',
        security_policy: 'Yes',
        regular_audits: 'Yes',
        staff_training: 'No',
      };

      const policies = assessmentAIService.getExistingPoliciesFromAnswers(testAnswersWithPolicies);

      expect(policies.existing_policies).toContain('Privacy Policy');
      expect(policies.existing_policies).toContain('Security Policy');
      expect(policies.gaps_identified).toContain('Data Protection Policy');
      expect(policies.gaps_identified).toContain('Staff Training');
      expect(policies.compliance_measures).toContain('Regular Audits');
    });

    test('getIndustryContextFromAnswers should determine correct regulations', () => {
      // Test Technology industry
      const techContext = assessmentAIService.getIndustryContextFromAnswers(
        testBusinessProfiles[0],
        testAnswers,
      );

      expect(techContext.industry).toBe('Technology');
      expect(techContext.applicable_regulations).toContain('GDPR');
      expect(techContext.applicable_regulations).toContain('Cyber Security Regulations');
      expect(techContext.risk_level).toBe('medium');

      // Test Healthcare industry
      const healthContext = assessmentAIService.getIndustryContextFromAnswers(
        testBusinessProfiles[1],
        { ...testAnswers, industry: 'healthcare' },
      );

      expect(healthContext.industry).toBe('Healthcare');
      expect(healthContext.applicable_regulations).toContain('MHRA Regulations');
      expect(healthContext.risk_level).toBe('high');
      expect(healthContext.special_requirements).toContain('Patient data protection');

      // Test Financial Services industry
      const financeContext = assessmentAIService.getIndustryContextFromAnswers(
        testBusinessProfiles[2],
        { ...testAnswers, industry: 'financial services' },
      );

      expect(financeContext.industry).toBe('Financial Services');
      expect(financeContext.applicable_regulations).toContain('FCA Regulations');
      expect(financeContext.applicable_regulations).toContain('Basel III');
      expect(financeContext.risk_level).toBe('high');
    });

    test('getTimelinePreferenceFromAnswers should extract urgency correctly', () => {
      // Test urgent timeline
      const urgentAnswers = {
        ...testAnswers,
        implementation_timeline: 'immediate',
        recent_incidents: 'Yes',
        regulatory_deadline: 'Yes',
      };

      const urgentTimeline = assessmentAIService.getTimelinePreferenceFromAnswers(urgentAnswers);

      expect(urgentTimeline.urgency).toBe('critical');
      expect(urgentTimeline.priority_areas).toContain('Incident response');
      expect(urgentTimeline.priority_areas).toContain('Regulatory compliance');

      // Test standard timeline
      const standardTimeline = assessmentAIService.getTimelinePreferenceFromAnswers(testAnswers);

      expect(standardTimeline.urgency).toBe('high'); // 3 months = high urgency
      expect(standardTimeline.preferred_timeline).toBe('3 months');
      expect(standardTimeline.implementation_capacity).toBe('moderate');
    });
  });

  describe('AI Service Methods Testing', () => {
    test('getQuestionHelp should return valid help response', async () => {
      const helpRequest = {
        question_id: 'q1',
        question_text: 'Do you have a documented data retention policy?',
        framework_id: 'gdpr',
        user_context: {
          business_profile: testBusinessProfiles[0],
          current_answers: testAnswers,
        },
      };

      const response = await assessmentAIService.getQuestionHelp(helpRequest);

      expect(response).toBeDefined();
      expect(response.guidance).toBeDefined();
      expect(response.confidence_score).toBeGreaterThan(0);
      expect(response.confidence_score).toBeLessThanOrEqual(1);
      expect(Array.isArray(response.related_topics)).toBe(true);
    });

    test('getFollowUpQuestions should return relevant questions', async () => {
      const followUpRequest = {
        current_question_id: 'q1',
        user_response: 'No',
        framework_id: 'gdpr',
        context: {
          business_profile: testBusinessProfiles[0],
          current_answers: testAnswers,
        },
      };

      const response = await assessmentAIService.getFollowUpQuestions(followUpRequest);

      expect(response).toBeDefined();
      expect(Array.isArray(response.questions)).toBe(true);
      expect(response.questions.length).toBeGreaterThan(0);
      expect(response.reasoning).toBeDefined();
    });

    test('getAssessmentAnalysis should return comprehensive analysis', async () => {
      const analysisRequest = {
        assessment_id: 'test-assessment',
        responses: testAnswers,
        framework_id: 'gdpr',
        business_profile: testBusinessProfiles[0] || {},
      };

      const response = await assessmentAIService.getAssessmentAnalysis(analysisRequest);

      expect(response).toBeDefined();
      expect(Array.isArray(response.gaps)).toBe(true);
      expect(Array.isArray(response.recommendations)).toBe(true);
      expect(response.risk_assessment).toBeDefined();
      expect(response.compliance_insights).toBeDefined();
      expect(Array.isArray(response.evidence_requirements)).toBe(true);

      // Validate gap structure
      if (response.gaps.length > 0) {
        const gap = response.gaps[0];
        expect(gap.id).toBeDefined();
        expect(gap.questionId).toBeDefined();
        expect(gap.section).toBeDefined();
        expect(gap.severity).toMatch(/^(critical|high|medium|low)$/);
        expect(gap.description).toBeDefined();
        expect(gap.impact).toBeDefined();
        expect(gap.currentState).toBeDefined();
        expect(gap.targetState).toBeDefined();
      }

      // Validate recommendation structure
      if (response.recommendations.length > 0) {
        const recommendation = response.recommendations[0];
        expect(recommendation.id).toBeDefined();
        expect(recommendation.gapId).toBeDefined();
        expect(recommendation.priority).toMatch(/^(immediate|short_term|medium_term|long_term)$/);
        expect(recommendation.title).toBeDefined();
        expect(recommendation.description).toBeDefined();
        expect(recommendation.estimatedEffort).toBeDefined();
      }
    });

    test('getPersonalizedRecommendations should return tailored recommendations', async () => {
      const recommendationRequest = {
        gaps: [
          {
            id: 'gap_1',
            questionId: 'q1',
            section: 'Data Protection',
            severity: 'high' as const,
            description: 'Missing data retention policy',
            impact: 'High compliance risk',
            currentState: 'No policy',
            targetState: 'Documented policy',
          },
        ],
        business_profile: testBusinessProfiles[0],
        existing_policies: ['Privacy Policy'],
        industry_context: 'Technology',
        timeline_preferences: 'urgent',
      };

      const response =
        await assessmentAIService.getPersonalizedRecommendations(recommendationRequest);

      expect(response).toBeDefined();
      expect(Array.isArray(response.recommendations)).toBe(true);
      expect(response.implementation_plan).toBeDefined();
      expect(Array.isArray(response.success_metrics)).toBe(true);

      // Validate implementation plan structure
      expect(response.implementation_plan.phases).toBeDefined();
      expect(Array.isArray(response.implementation_plan.phases)).toBe(true);
      expect(response.implementation_plan.total_timeline_weeks).toBeGreaterThan(0);
      expect(Array.isArray(response.implementation_plan.resource_requirements)).toBe(true);
    });
  });

  describe('Enhanced AI Response Testing', () => {
    test('getEnhancedAIResponse should combine all context methods', async () => {
      const context = {
        businessProfile: testBusinessProfiles[0],
        currentAnswers: testAnswers,
        assessmentType: 'gdpr',
      };

      const response = await assessmentAIService.getEnhancedAIResponse(
        'Provide compliance recommendations for this business',
        context,
        5000, // 5 second timeout for testing
      );

      expect(response).toBeDefined();

      // Should have either real AI response or fallback
      if (response.fallback) {
        expect(response.analysis).toContain('Unable to generate detailed analysis');
        expect(response.confidence_score).toBe(0.3);
        expect(Array.isArray(response.recommendations)).toBe(true);
      } else {
        expect(response.analysis).toBeDefined();
        expect(response.confidence_score).toBeGreaterThan(0.3);
      }
    });
  });
});
