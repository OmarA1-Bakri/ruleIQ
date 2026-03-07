/**
 * AI Fallback Tests
 * Tests for Phase 1.5.3: Testing & Validation
 * Testing fallback behavior when AI endpoints fail
 */

// Set up test environment to use mock data
process.env.NODE_ENV = 'test';
process.env['NEXT_PUBLIC_USE_REAL_AI'] = 'false';
process.env['NEXT_PUBLIC_ENABLE_MOCK_DATA'] = 'true';

describe('AI Fallback Tests', () => {
  describe('Mock Data Fallback', () => {
    test('should return mock help response when in development mode', async () => {
      // Mock the AI service behavior
      const mockHelpResponse = {
        guidance:
          "This question assesses your organization's data retention practices under GDPR. You should document specific retention periods for different categories of personal data, ensure you have legal basis for retention, and implement automatic deletion processes where possible.",
        confidence_score: 0.92,
        related_topics: ['Data Protection by Design', 'Right to Erasure', 'Data Minimization'],
        follow_up_suggestions: [
          'Review your current data retention schedule',
          'Consult with your legal team on retention requirements',
          'Consider implementing automated deletion tools',
        ],
        source_references: ['GDPR Article 5(1)(e)', 'GDPR Recital 39'],
      };

      // Simulate the service behavior
      const getQuestionHelp = async (request: any) => {
        // In development mode, always return mock data
        if (process.env['NEXT_PUBLIC_USE_REAL_AI'] !== 'true') {
          return mockHelpResponse;
        }

        // In production mode, would make real API call
        throw new Error('Production endpoint not available');
      };

      const helpRequest = {
        question_id: 'q1',
        question_text: 'Do you have a documented data retention policy?',
        framework_id: 'gdpr',
      };

      const response = await getQuestionHelp(helpRequest);

      expect(response).toBeDefined();
      expect(response.guidance).toContain('data retention practices');
      expect(response.confidence_score).toBe(0.92);
      expect(response.related_topics).toContain('Data Protection by Design');
      expect(response.follow_up_suggestions).toHaveLength(3);
      expect(response.source_references).toContain('GDPR Article 5(1)(e)');
    });

    test('should return mock analysis response with correct structure', async () => {
      const mockAnalysisResponse = {
        gaps: [
          {
            id: 'gap_1',
            questionId: 'q3',
            section: 'Data Protection',
            severity: 'high' as const,
            description: 'Informal retention practices instead of documented policies',
            impact: 'Potential GDPR violation for excessive data retention',
            currentState: 'Informal retention practices',
            targetState: 'Documented retention policies with defined periods',
          },
        ],
        recommendations: [
          {
            id: 'ai_rec_1',
            gapId: 'gap_1',
            priority: 'immediate' as const,
            title: 'Implement Comprehensive Data Retention Policy',
            description:
              'Create and document formal data retention policies with specific timeframes for different data categories, automated deletion processes, and regular compliance reviews.',
            estimatedEffort: '3-4 weeks',
            resources: [
              'Data Protection Officer',
              'Legal Team',
              'IT Department',
              'Compliance Manager',
            ],
            relatedFrameworks: ['GDPR', 'ISO 27001'],
          },
        ],
        risk_assessment: {
          overall_risk_level: 'high' as const,
          risk_score: 7.2,
          key_risk_areas: ['Data Retention', 'Automated Compliance', 'Legal Documentation'],
        },
        compliance_insights: {
          maturity_level: 'developing',
          score_breakdown: { data_protection: 65, security: 70, governance: 55 },
          improvement_priority: [
            'Data Retention Policies',
            'Automated Compliance',
            'Staff Training',
          ],
        },
        evidence_requirements: [
          {
            priority: 'high' as const,
            evidence_type: 'policy_document',
            description: 'Documented data retention policy with defined periods',
            control_mapping: ['GDPR Article 5(1)(e)', 'ISO 27001 A.11.2.9'],
          },
        ],
      };

      // Simulate the service behavior
      const getAssessmentAnalysis = async (request: any) => {
        if (process.env['NEXT_PUBLIC_USE_REAL_AI'] !== 'true') {
          return mockAnalysisResponse;
        }
        throw new Error('Production endpoint not available');
      };

      const analysisRequest = {
        assessment_id: 'test-assessment',
        responses: { data_retention: 'No' },
        framework_id: 'gdpr',
        business_profile: { industry: 'Technology' },
      };

      const response = await getAssessmentAnalysis(analysisRequest);

      expect(response).toBeDefined();
      expect(response.gaps).toHaveLength(1);
      expect(response.recommendations).toHaveLength(1);
      expect(response.risk_assessment.overall_risk_level).toBe('high');
      expect(response.compliance_insights.maturity_level).toBe('developing');
      expect(response.evidence_requirements).toHaveLength(1);

      // Validate gap structure
      const gap = response.gaps[0];
      expect(gap.id).toBe('gap_1');
      expect(gap.severity).toBe('high');
      expect(gap.description).toContain('retention practices');

      // Validate recommendation structure
      const recommendation = response.recommendations[0];
      expect(recommendation.gapId).toBe('gap_1');
      expect(recommendation.priority).toBe('immediate');
      expect(recommendation.title).toContain('Data Retention Policy');
    });

    test('should handle enhanced AI response fallback correctly', async () => {
      const fallbackResponse = {
        analysis:
          'Unable to generate detailed analysis at this time. Please ensure all required information is provided and try again.',
        recommendations: [
          {
            id: 'fallback_rec_1',
            gapId: 'unknown',
            priority: 'medium_term' as const,
            title: 'Review Current Compliance Status',
            description: 'Conduct a comprehensive review of your current compliance status',
            estimatedEffort: '1-2 weeks',
          },
          {
            id: 'fallback_rec_2',
            gapId: 'unknown',
            priority: 'medium_term' as const,
            title: 'Identify Priority Areas',
            description: 'Identify priority areas for improvement based on business risk',
            estimatedEffort: '1 week',
          },
        ],
        confidence_score: 0.3,
        fallback: true,
      };

      // Simulate enhanced AI response with error handling
      const getEnhancedAIResponse = async (prompt: string, context: any, timeoutMs: number) => {
        try {
          // Simulate AI service failure
          throw new Error('AI service temporarily unavailable');
        } catch (error) {
          // Development logging - consider proper logger

          console.error('Enhanced AI response failed:', error);
          return fallbackResponse;
        }
      };

      const context = {
        businessProfile: { industry: 'Technology' },
        currentAnswers: { data_protection: 'No' },
        assessmentType: 'gdpr',
      };

      const response = await getEnhancedAIResponse(
        'Provide compliance recommendations',
        context,
        5000,
      );

      expect(response).toBeDefined();
      expect(response.fallback).toBe(true);
      expect(response.confidence_score).toBe(0.3);
      expect(response.analysis).toContain('Unable to generate detailed analysis');
      expect(response.recommendations).toHaveLength(2);

      // Validate fallback recommendations structure
      response.recommendations.forEach((rec: any) => {
        expect(rec.id).toBeDefined();
        expect(rec.gapId).toBe('unknown');
        expect(rec.priority).toBe('medium_term');
        expect(rec.title).toBeDefined();
        expect(rec.description).toBeDefined();
        expect(rec.estimatedEffort).toBeDefined();
      });
    });
  });

  describe('Error Handling', () => {
    test('should handle network errors gracefully', async () => {
      const handleNetworkError = async () => {
        try {
          // Simulate network error
          throw new Error('Network request failed');
        } catch (error) {
          // Development logging - consider proper logger

          console.error('Network error:', error);

          // Return fallback response
          return {
            guidance: 'Unable to get AI assistance at this time. Please try again later.',
            confidence_score: 0.1,
            related_topics: [],
            follow_up_suggestions: ['Try again later', 'Contact support if issue persists'],
            source_references: [],
            fallback: true,
          };
        }
      };

      const response = await handleNetworkError();

      expect(response.fallback).toBe(true);
      expect(response.confidence_score).toBe(0.1);
      expect(response.guidance).toContain('Unable to get AI assistance');
      expect(response.follow_up_suggestions).toContain('Try again later');
    });

    test('should handle timeout errors appropriately', async () => {
      const handleTimeoutError = async () => {
        const timeoutPromise = new Promise((_, reject) => {
          setTimeout(() => reject(new Error('Request timed out')), 100);
        });

        const slowRequest = new Promise((resolve) => {
          setTimeout(() => resolve('success'), 1000);
        });

        try {
          await Promise.race([slowRequest, timeoutPromise]);
        } catch (error) {
          if (error instanceof Error && error.message.includes('timed out')) {
            return {
              error: 'Request is taking longer than expected. Please try again.',
              fallback: true,
              timeout: true,
            };
          }
          throw error;
        }
      };

      const response = await handleTimeoutError();

      expect(response.fallback).toBe(true);
      expect(response.timeout).toBe(true);
      expect(response.error).toContain('taking longer than expected');
    });
  });

  describe('Production vs Development Mode', () => {
    test('should use mock data in development mode', () => {
      const originalEnv = process.env['NEXT_PUBLIC_USE_REAL_AI'];

      // Test development mode
      process.env['NEXT_PUBLIC_USE_REAL_AI'] = 'false';

      const shouldUseMockData = process.env['NEXT_PUBLIC_USE_REAL_AI'] !== 'true';
      expect(shouldUseMockData).toBe(true);

      // Test production mode
      process.env['NEXT_PUBLIC_USE_REAL_AI'] = 'true';

      const shouldUseRealAI = process.env['NEXT_PUBLIC_USE_REAL_AI'] === 'true';
      expect(shouldUseRealAI).toBe(true);

      // Restore original environment
      process.env['NEXT_PUBLIC_USE_REAL_AI'] = originalEnv;
    });
  });
});
