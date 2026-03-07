import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

// Mock the assessments-ai service to avoid complex dependency
vi.mock('@/lib/api/assessments-ai.service', () => ({
  assessmentAIService: {},
}));

describe('AISelfReviewService', () => {
  let aiSelfReviewService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/ai-self-review.service');
    aiSelfReviewService = serviceMod.aiSelfReviewService;
  });

  // -- Sync utility methods --

  describe('shouldRecommendSelfReview', () => {
    it('recommends high priority for low confidence', () => {
      const response = {
        guidance: 'Short guidance',
        confidence_score: 0.5,
        related_topics: [],
        follow_up_suggestions: ['Do X'],
        source_references: [],
      };

      const result = aiSelfReviewService.shouldRecommendSelfReview(response);

      expect(result.recommend).toBe(true);
      expect(result.priority).toBe('high');
      expect(result.reason).toContain('Low confidence');
    });

    it('recommends high priority for complex high-stakes topics', () => {
      const response = {
        guidance: 'This is a long guidance text about compliance requirements and legal obligations. '.repeat(10),
        confidence_score: 0.85,
        related_topics: [],
        follow_up_suggestions: ['Review'],
        source_references: [],
      };

      const result = aiSelfReviewService.shouldRecommendSelfReview(response);

      expect(result.recommend).toBe(true);
      expect(result.priority).toBe('high');
      expect(result.reason).toContain('High-stakes');
    });

    it('recommends medium priority for complex non-stakes topics', () => {
      const response = {
        guidance: 'This is a long guidance text about general topics and best practices. '.repeat(10),
        confidence_score: 0.85,
        related_topics: [],
        follow_up_suggestions: ['Review'],
        source_references: [],
      };

      const result = aiSelfReviewService.shouldRecommendSelfReview(response);

      expect(result.recommend).toBe(true);
      expect(result.priority).toBe('medium');
    });

    it('recommends medium priority for many references', () => {
      const response = {
        guidance: 'Short guidance',
        confidence_score: 0.9,
        related_topics: [],
        follow_up_suggestions: ['Review'],
        source_references: ['Ref 1', 'Ref 2', 'Ref 3', 'Ref 4'],
      };

      const result = aiSelfReviewService.shouldRecommendSelfReview(response);

      expect(result.recommend).toBe(true);
      expect(result.priority).toBe('medium');
    });

    it('does not recommend for simple confident responses', () => {
      const response = {
        guidance: 'Short and clear guidance',
        confidence_score: 0.95,
        related_topics: [],
        follow_up_suggestions: ['Check docs'],
        source_references: ['GDPR Article 5'],
      };

      const result = aiSelfReviewService.shouldRecommendSelfReview(response);

      expect(result.recommend).toBe(false);
      expect(result.priority).toBe('low');
    });
  });

  describe('formatSelfReviewForDisplay', () => {
    const baseReview = {
      review_id: 'review_001',
      timestamp: '2025-06-15T10:00:00Z',
      original_response: { guidance: 'Original', confidence_score: 0.9 },
      self_critique: {
        identified_issues: [
          {
            issue_id: 'i1',
            severity: 'high',
            category: 'completeness',
            description: 'Missing examples',
            location: 'Main section',
            suggested_fix: 'Add concrete examples',
            confidence_in_identification: 8,
          },
          {
            issue_id: 'i2',
            severity: 'low',
            category: 'clarity',
            description: 'Jargon used',
            location: 'Introduction',
            suggested_fix: 'Define technical terms',
            confidence_in_identification: 9,
          },
        ],
        confidence_assessment: {
          original_confidence: 0.92,
          reviewed_confidence: 0.87,
          confidence_factors: [],
          uncertainty_areas: [],
        },
        accuracy_check: { factual_claims: [], regulatory_references: [], overall_accuracy_score: 8 },
        completeness_review: { missing_aspects: [], incomplete_explanations: [], areas_needing_expansion: [], completeness_score: 7 },
        clarity_evaluation: { unclear_explanations: [], jargon_without_explanation: [], logical_flow_issues: [], clarity_score: 8, readability_assessment: { complexity_level: 'intermediate', target_audience_match: true, improvement_suggestions: [] } },
      },
      revised_response: { guidance: 'Revised', confidence_score: 0.87 },
      review_quality: {
        overall_confidence: 8.7,
        reliability_score: 8.3,
        revision_significance: 'moderate',
        areas_needing_verification: ['Industry-specific requirements'],
      },
      user_guidance: {
        how_to_use: 'Use as starting point',
        confidence_interpretation: 'Score of 8.7/10',
        when_to_seek_additional_help: 'Seek help if regulated',
      },
    };

    it('generates summary with significant issues', () => {
      const result = aiSelfReviewService.formatSelfReviewForDisplay(baseReview);

      expect(result.summary).toContain('improved');
      expect(result.summary).toContain('1 significant issues');
      expect(result.key_changes).toHaveLength(2);
      expect(result.confidence_explanation).toContain('decreased');
      expect(result.user_action_needed).toBe(true);
    });

    it('shows confirmed when no revision', () => {
      const noRevisionReview = {
        ...baseReview,
        review_quality: { ...baseReview.review_quality, revision_significance: 'none', areas_needing_verification: [] },
        self_critique: {
          ...baseReview.self_critique,
          identified_issues: [],
          confidence_assessment: {
            ...baseReview.self_critique.confidence_assessment,
            original_confidence: 0.9,
            reviewed_confidence: 0.9,
          },
        },
      };

      const result = aiSelfReviewService.formatSelfReviewForDisplay(noRevisionReview);

      expect(result.summary).toContain('confirmed');
      expect(result.confidence_explanation).toContain('remained stable');
      expect(result.user_action_needed).toBe(false);
    });

    it('shows increased confidence when reviewed is higher', () => {
      const increasedReview = {
        ...baseReview,
        self_critique: {
          ...baseReview.self_critique,
          confidence_assessment: {
            ...baseReview.self_critique.confidence_assessment,
            original_confidence: 0.8,
            reviewed_confidence: 0.9,
          },
        },
      };

      const result = aiSelfReviewService.formatSelfReviewForDisplay(increasedReview);

      expect(result.confidence_explanation).toContain('increased');
    });
  });
});
