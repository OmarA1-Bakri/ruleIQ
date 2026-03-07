import { apiClient } from './client';

import type { AIHelpResponse } from './assessments-ai.service';

// Self-Review Request/Response Interfaces
export interface SelfReviewRequest {
  original_response: AIHelpResponse;
  question_context: {
    question_id: string;
    question_text: string;
    framework_id: string;
    section_id?: string;
  };
  user_context?: {
    business_profile?: any;
    current_answers?: Record<string, any>;
    assessment_progress?: any;
  };
  review_focus?: 'accuracy' | 'completeness' | 'clarity' | 'relevance' | 'comprehensive';
}

export interface SelfReviewResponse {
  review_id: string;
  timestamp: string;

  // Initial Response
  original_response: AIHelpResponse;

  // Self-Review Analysis
  self_critique: {
    identified_issues: SelfReviewIssue[];
    confidence_assessment: ConfidenceAssessment;
    accuracy_check: AccuracyCheck;
    completeness_review: CompletenessReview;
    clarity_evaluation: ClarityEvaluation;
  };

  // Revised Response
  revised_response: AIHelpResponse;

  // Meta-Review Information
  review_quality: {
    overall_confidence: number; // 1-10 scale
    reliability_score: number; // 1-10 scale
    revision_significance: 'none' | 'minor' | 'moderate' | 'major';
    areas_needing_verification: string[];
  };

  // User Guidance
  user_guidance: {
    how_to_use: string;
    confidence_interpretation: string;
    when_to_seek_additional_help: string;
  };
}

export interface SelfReviewIssue {
  issue_id: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  category:
    | 'factual_accuracy'
    | 'logical_consistency'
    | 'completeness'
    | 'clarity'
    | 'relevance'
    | 'bias'
    | 'assumption';
  description: string;
  location: string; // Where in the response the issue was found
  suggested_fix: string;
  confidence_in_identification: number; // 1-10 scale
}

export interface ConfidenceAssessment {
  original_confidence: number;
  reviewed_confidence: number;
  confidence_factors: {
    factor: string;
    impact: 'increases' | 'decreases' | 'neutral';
    explanation: string;
  }[];
  uncertainty_areas: string[];
}

export interface AccuracyCheck {
  factual_claims: {
    claim: string;
    verification_status: 'verified' | 'uncertain' | 'requires_check' | 'potentially_incorrect';
    confidence_level: number;
  }[];
  regulatory_references: {
    reference: string;
    accuracy_status: 'correct' | 'outdated' | 'uncertain' | 'incorrect';
    notes?: string;
  }[];
  overall_accuracy_score: number;
}

export interface CompletenessReview {
  missing_aspects: string[];
  incomplete_explanations: string[];
  areas_needing_expansion: string[];
  completeness_score: number;
}

export interface ClarityEvaluation {
  unclear_explanations: string[];
  jargon_without_explanation: string[];
  logical_flow_issues: string[];
  clarity_score: number;
  readability_assessment: {
    complexity_level: 'basic' | 'intermediate' | 'advanced' | 'expert';
    target_audience_match: boolean;
    improvement_suggestions: string[];
  };
}

export interface SelfReviewMetrics {
  total_reviews: number;
  average_confidence_change: number;
  common_issue_categories: { category: string; frequency: number }[];
  revision_frequency: { level: string; count: number }[];
  user_satisfaction_with_reviews: number;
}

// Mock data for development
const mockSelfReviewResponse: SelfReviewResponse = {
  review_id: 'review_001',
  timestamp: new Date().toISOString(),
  original_response: {
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
  },
  self_critique: {
    identified_issues: [
      {
        issue_id: 'issue_001',
        severity: 'medium',
        category: 'completeness',
        description: 'Missing mention of specific retention periods for different data categories',
        location: 'Main guidance section',
        suggested_fix:
          'Add examples of common retention periods (e.g., employee data: 6 years, customer data: varies by purpose)',
        confidence_in_identification: 8,
      },
      {
        issue_id: 'issue_002',
        severity: 'low',
        category: 'clarity',
        description: 'Term "legal basis" could be clearer for non-legal audiences',
        location: 'First sentence, legal basis reference',
        suggested_fix:
          'Explain what constitutes legal basis (e.g., contract, legal obligation, legitimate interest)',
        confidence_in_identification: 9,
      },
    ],
    confidence_assessment: {
      original_confidence: 0.92,
      reviewed_confidence: 0.87,
      confidence_factors: [
        {
          factor: 'Missing specific examples',
          impact: 'decreases',
          explanation: 'Lack of concrete examples may reduce practical applicability',
        },
        {
          factor: 'Accurate regulatory references',
          impact: 'increases',
          explanation: 'Correct citation of GDPR articles increases reliability',
        },
      ],
      uncertainty_areas: [
        'Specific retention periods for different industries',
        'Technical implementation details',
      ],
    },
    accuracy_check: {
      factual_claims: [
        {
          claim: 'GDPR requires documented retention periods',
          verification_status: 'verified',
          confidence_level: 10,
        },
        {
          claim: 'Automatic deletion processes are required',
          verification_status: 'uncertain',
          confidence_level: 6,
        },
      ],
      regulatory_references: [
        {
          reference: 'GDPR Article 5(1)(e)',
          accuracy_status: 'correct',
          notes: 'Correctly cites data minimization principle',
        },
        {
          reference: 'GDPR Recital 39',
          accuracy_status: 'correct',
          notes: 'Relevant to data retention principles',
        },
      ],
      overall_accuracy_score: 8.5,
    },
    completeness_review: {
      missing_aspects: [
        'Specific retention periods by data category',
        'Legal basis types explanation',
        'Industry-specific considerations',
      ],
      incomplete_explanations: [
        'What constitutes adequate documentation',
        'How to implement automated deletion',
      ],
      areas_needing_expansion: [
        'Practical implementation steps',
        'Common challenges and solutions',
      ],
      completeness_score: 7.2,
    },
    clarity_evaluation: {
      unclear_explanations: ['Legal basis for retention (needs definition)'],
      jargon_without_explanation: ['Legal basis', 'Data Protection by Design'],
      logical_flow_issues: [],
      clarity_score: 8.1,
      readability_assessment: {
        complexity_level: 'intermediate',
        target_audience_match: true,
        improvement_suggestions: [
          'Define technical terms',
          'Add more concrete examples',
          'Include step-by-step guidance',
        ],
      },
    },
  },
  revised_response: {
    guidance:
      "This question assesses your organization's data retention practices under GDPR. You must document specific retention periods for different categories of personal data based on your legal basis for processing (such as contractual obligations, legal requirements, or legitimate interests).\n\nKey requirements:\n• Document retention periods for each data category (e.g., employee records: 6 years after termination, customer data: varies by purpose)\n• Ensure you have a valid legal basis for retention\n• Implement processes for timely deletion when retention periods expire\n• Consider automated deletion tools to ensure compliance\n\nThe goal is to retain data only as long as necessary for the original purpose, balancing business needs with privacy rights.",
    confidence_score: 0.87,
    related_topics: [
      'Data Protection by Design',
      'Right to Erasure',
      'Data Minimization',
      'Legal Basis for Processing',
    ],
    follow_up_suggestions: [
      'Create a data retention schedule mapping data categories to retention periods',
      'Identify your legal basis for retention (contract, legal obligation, legitimate interest)',
      'Consult with your legal team on industry-specific retention requirements',
      'Research automated deletion tools suitable for your data systems',
      'Establish a process for regular review and updates of retention policies',
    ],
    source_references: [
      'GDPR Article 5(1)(e) - Data minimization',
      'GDPR Article 6 - Legal basis for processing',
      'GDPR Recital 39 - Retention periods',
    ],
  },
  review_quality: {
    overall_confidence: 8.7,
    reliability_score: 8.3,
    revision_significance: 'moderate',
    areas_needing_verification: [
      'Industry-specific retention requirements',
      'Technical implementation details for automated deletion',
      'Specific legal basis requirements by jurisdiction',
    ],
  },
  user_guidance: {
    how_to_use:
      'This response has been self-reviewed and revised. The revised version includes more specific guidance and examples. Use this as a starting point, but consider consulting with legal experts for your specific situation.',
    confidence_interpretation:
      'Confidence score of 8.7/10 means this guidance is well-founded but may need customization for your specific industry or circumstances. Areas marked for verification should be checked with relevant experts.',
    when_to_seek_additional_help:
      'Seek additional legal advice if: you operate in a regulated industry, handle special category data, have complex international data transfers, or need specific technical implementation guidance.',
  },
};

class AISelfReviewService {
  private useProductionEndpoints =
    process.env.NODE_ENV === 'production' || process.env['NEXT_PUBLIC_USE_REAL_AI'] === 'true';

  /**
   * Perform self-review of an AI response
   */
  async performSelfReview(request: SelfReviewRequest): Promise<SelfReviewResponse> {
    try {
      if (this.useProductionEndpoints) {
        const response = await apiClient.post<SelfReviewResponse>('/ai/self-review', request);
        return response;
      }

      // Development fallback - simulate review processing time
      await new Promise((resolve) => setTimeout(resolve, 1500));

      return {
        ...mockSelfReviewResponse,
        review_id: `review_${Date.now()}`,
        timestamp: new Date().toISOString(),
        original_response: request.original_response,
      };
    } catch (_error) {
      // intentionally empty - fall through to throw
      throw new Error('Unable to perform self-review at this time. Please try again later.');
    }
  }

  /**
   * Get self-review for a specific AI response type
   */
  async getSpecializedReview(
    type: 'guidance' | 'analysis' | 'recommendations',
    request: SelfReviewRequest,
  ): Promise<SelfReviewResponse> {
    const specializedRequest = {
      ...request,
      review_focus: this.getReviewFocusForType(type),
    };

    return this.performSelfReview(specializedRequest);
  }

  /**
   * Quick confidence check without full review
   */
  async quickConfidenceCheck(
    response: AIHelpResponse,
    context: { question_text: string; framework_id: string },
  ): Promise<{
    confidence_score: number;
    confidence_factors: string[];
    quick_issues: string[];
    recommendation: 'use_as_is' | 'review_recommended' | 'seek_expert_help';
  }> {
    try {
      if (this.useProductionEndpoints) {
        const apiResponse = await apiClient.post<{
          confidence_score: number;
          confidence_factors: string[];
          quick_issues: string[];
          recommendation: 'use_as_is' | 'review_recommended' | 'seek_expert_help';
        }>('/ai/quick-confidence-check', {
          response,
          context,
        });
        return apiResponse;
      }

      // Development fallback
      return {
        confidence_score: 8.5,
        confidence_factors: [
          'Accurate regulatory references',
          'Clear explanation structure',
          'Practical actionable advice',
        ],
        quick_issues: [
          'Could benefit from more specific examples',
          'Technical implementation details are limited',
        ],
        recommendation: 'use_as_is',
      };
    } catch (_error) {

      return {
        confidence_score: 7.0,
        confidence_factors: ['Unable to verify at this time'],
        quick_issues: ['Review service temporarily unavailable'],
        recommendation: 'review_recommended',
      };
    }
  }

  /**
   * Get self-review metrics and analytics
   */
  async getSelfReviewMetrics(
    timeframe: 'day' | 'week' | 'month' = 'week',
  ): Promise<SelfReviewMetrics> {
    try {
      if (this.useProductionEndpoints) {
        const response = await apiClient.get<SelfReviewMetrics>(
          `/ai/self-review/metrics?timeframe=${timeframe}`,
        );
        return response;
      }

      // Development fallback
      return {
        total_reviews: 127,
        average_confidence_change: -0.15,
        common_issue_categories: [
          { category: 'completeness', frequency: 34 },
          { category: 'clarity', frequency: 28 },
          { category: 'factual_accuracy', frequency: 19 },
        ],
        revision_frequency: [
          { level: 'none', count: 23 },
          { level: 'minor', count: 58 },
          { level: 'moderate', count: 34 },
          { level: 'major', count: 12 },
        ],
        user_satisfaction_with_reviews: 8.4,
      };
    } catch (_error) {

      throw new Error('Unable to retrieve self-review metrics at this time.');
    }
  }

  /**
   * Submit feedback on self-review quality
   */
  async submitReviewFeedback(
    reviewId: string,
    feedback: {
      helpful: boolean;
      accuracy_rating: number; // 1-10
      completeness_rating: number; // 1-10
      clarity_rating: number; // 1-10
      comments?: string;
      improvement_suggestions?: string[];
    },
  ): Promise<void> {
    try {
      if (this.useProductionEndpoints) {
        await apiClient.post('/ai/self-review/feedback', {
          review_id: reviewId,
          ...feedback,
        });
      } else {
        // intentionally empty - dev mode feedback is a no-op
      }
    } catch (_error) {
      // Non-blocking - don't throw error for feedback submission
    }
  }

  /**
   * Get recommended review focus based on response type
   */
  private getReviewFocusForType(
    type: 'guidance' | 'analysis' | 'recommendations',
  ): 'comprehensive' | 'accuracy' | 'completeness' | 'clarity' | 'relevance' {
    switch (type) {
      case 'guidance':
        return 'clarity';
      case 'analysis':
        return 'accuracy';
      case 'recommendations':
        return 'completeness';
      default:
        return 'comprehensive';
    }
  }

  /**
   * Check if self-review is recommended based on response characteristics
   */
  shouldRecommendSelfReview(response: AIHelpResponse): {
    recommend: boolean;
    reason: string;
    priority: 'low' | 'medium' | 'high';
  } {
    const factors = {
      lowConfidence: response.confidence_score < 0.7,
      complexTopic: response.guidance.length > 500,
      manyReferences: (response.source_references?.length || 0) > 3,
      noFollowUp: !response.follow_up_suggestions?.length,
      highStakes:
        response.guidance.toLowerCase().includes('legal') ||
        response.guidance.toLowerCase().includes('compliance') ||
        response.guidance.toLowerCase().includes('regulatory'),
    };

    if (factors.lowConfidence) {
      return {
        recommend: true,
        reason: 'Low confidence score suggests self-review would be beneficial',
        priority: 'high',
      };
    }

    if (factors.highStakes && factors.complexTopic) {
      return {
        recommend: true,
        reason: 'High-stakes compliance topic with complex guidance',
        priority: 'high',
      };
    }

    if (factors.complexTopic || factors.manyReferences) {
      return {
        recommend: true,
        reason: 'Complex response could benefit from self-review',
        priority: 'medium',
      };
    }

    return {
      recommend: false,
      reason: 'Response appears straightforward and confident',
      priority: 'low',
    };
  }

  /**
   * Format self-review for display
   */
  formatSelfReviewForDisplay(review: SelfReviewResponse): {
    summary: string;
    key_changes: string[];
    confidence_explanation: string;
    user_action_needed: boolean;
  } {
    const significantIssues = review.self_critique.identified_issues.filter(
      (issue) => issue.severity === 'high' || issue.severity === 'critical',
    );

    const confidenceChange =
      review.self_critique.confidence_assessment.reviewed_confidence -
      review.self_critique.confidence_assessment.original_confidence;

    const summary =
      `Self-review ${review.review_quality.revision_significance === 'none' ? 'confirmed' : 'improved'} this response. ` +
      `${significantIssues.length > 0 ? `Found ${significantIssues.length} significant issues. ` : ''}` +
      `Confidence ${confidenceChange >= 0 ? 'maintained' : 'adjusted'} based on review.`;

    const keyChanges = review.self_critique.identified_issues
      .map((issue) => `${issue.category}: ${issue.suggested_fix}`)
      .slice(0, 3); // Show top 3 changes

    const confidenceExplanation =
      confidenceChange > 0
        ? `Confidence increased by ${(confidenceChange * 100).toFixed(1)}% after review`
        : confidenceChange < 0
          ? `Confidence decreased by ${Math.abs(confidenceChange * 100).toFixed(1)}% after identifying areas for improvement`
          : 'Confidence remained stable after review';

    const userActionNeeded =
      review.review_quality.areas_needing_verification.length > 0 || significantIssues.length > 0;

    return {
      summary,
      key_changes: keyChanges,
      confidence_explanation: confidenceExplanation,
      user_action_needed: userActionNeeded,
    };
  }
}

export const aiSelfReviewService = new AISelfReviewService();
