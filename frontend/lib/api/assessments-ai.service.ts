import { withRetry, createAppError } from '../utils/error-handling';

import { chatService } from './chat.service';
import { apiClient } from './client';

import type {
  Gap,
  Recommendation,
  Question,
  AssessmentProgress,
} from '@/lib/assessment-engine/types';
import type { BusinessProfile } from '@/types/api';

// AI Request/Response Interfaces
export interface AIHelpRequest {
  question_id: string;
  question_text: string;
  framework_id: string;
  section_id?: string;
  user_context?: {
    business_profile?: Partial<BusinessProfile>;
    current_answers?: Record<string, any>;
    assessment_progress?: Partial<AssessmentProgress>;
  };
}

export interface AIHelpResponse {
  guidance: string;
  confidence_score: number;
  related_topics?: string[];
  follow_up_suggestions?: string[];
  source_references?: string[];
}

export interface AIRateLimitError {
  error: {
    message: string;
    code: string;
    operation: string;
    limit: number;
    window: string;
    retry_after: number;
    burst_allowance: number;
  };
  suggestion: string;
}

export interface AIFollowUpRequest {
  question_id: string;
  question_text: string;
  user_answer: any;
  assessment_context: {
    framework_id: string;
    section_id?: string;
    current_answers: Record<string, any>;
    business_profile_id?: string;
  };
}

export interface AIFollowUpResponse {
  follow_up_questions: Question[];
  reasoning: string;
  estimated_completion_time?: number;
}

export interface AIAnalysisRequest {
  assessment_id: string;
  responses: Record<string, any>;
  framework_id: string;
  business_profile: Partial<BusinessProfile>;
}

export interface AIAnalysisResponse {
  gaps: Gap[];
  recommendations: Recommendation[];
  risk_assessment: {
    overall_risk_level: 'low' | 'medium' | 'high' | 'critical';
    risk_score: number;
    key_risk_areas: string[];
  };
  compliance_insights: {
    maturity_level: string;
    score_breakdown: Record<string, number>;
    improvement_priority: string[];
  };
  evidence_requirements: {
    priority: 'high' | 'medium' | 'low';
    evidence_type: string;
    description: string;
    control_mapping: string[];
  }[];
}

export interface AIRecommendationRequest {
  gaps: Gap[];
  business_profile: Partial<BusinessProfile>;
  existing_policies?: string[];
  industry_context?: string;
  timeline_preferences?: 'urgent' | 'standard' | 'gradual';
}

export interface AIRecommendationResponse {
  recommendations: Recommendation[];
  implementation_plan: {
    phases: {
      phase_number: number;
      phase_name: string;
      duration_weeks: number;
      tasks: string[];
      dependencies: string[];
    }[];
    total_timeline_weeks: number;
    resource_requirements: string[];
  };
  success_metrics: string[];
}

// Streaming Interfaces
export interface StreamingChunk {
  chunk_id: string;
  content: string;
  chunk_type: 'content' | 'metadata' | 'complete' | 'error';
  timestamp: string;
}

export interface StreamingMetadata {
  request_id: string;
  framework_id: string;
  business_profile_id: string;
  started_at: string;
  stream_type: 'analysis' | 'recommendations' | 'help';
}

export interface StreamingOptions {
  onChunk?: (chunk: StreamingChunk) => void;
  onComplete?: () => void;
  onError?: (error: string) => void;
  onMetadata?: (metadata: StreamingMetadata) => void;
}

// Mock responses for development
const mockAIResponses = {
  help: {
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

  followUp: {
    questions: [
      {
        id: 'ai_follow_1',
        type: 'radio' as const,
        text: 'Do you have automated systems in place to delete data when retention periods expire?',
        options: [
          { value: 'yes', label: 'Yes, fully automated' },
          { value: 'partial', label: 'Partially automated' },
          { value: 'manual', label: 'Manual process only' },
          { value: 'no', label: 'No deletion process' },
        ],
        validation: { required: true },
        weight: 2,
        metadata: {
          ai_generated: true,
          reasoning: 'Follow-up to assess implementation maturity',
        },
      },
    ],
    follow_up_questions: [
      {
        id: 'ai_follow_1',
        type: 'radio' as const,
        text: 'Do you have automated systems in place to delete data when retention periods expire?',
        options: [
          { value: 'yes', label: 'Yes, fully automated' },
          { value: 'partial', label: 'Partially automated' },
          { value: 'manual', label: 'Manual process only' },
          { value: 'no', label: 'No deletion process' },
        ],
        validation: { required: true },
        weight: 2,
        metadata: {
          ai_generated: true,
          reasoning: 'Follow-up to assess implementation maturity',
        },
      },
    ],
    reasoning:
      "Based on your data retention policy response, I'm asking about implementation to understand the practical compliance level.",
    estimated_completion_time: 2,
  },

  analysis: {
    gaps: [
      {
        id: 'gap_1',
        questionId: 'q1',
        questionText: 'Do you have documented data retention policies with defined periods for different data categories?',
        section: 'Data Protection',
        category: 'Data Protection',
        severity: 'high' as const,
        description: 'Informal retention practices instead of documented policies',
        impact: 'Potential GDPR violation for excessive data retention',
        currentState: 'Informal retention practices',
        targetState: 'Documented retention policies with defined periods',
        expectedAnswer: 'Yes, with documented policies for each data category',
        actualAnswer: 'No, we handle this informally',
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
        category: 'Data Protection',
        impact: 'High - Reduces GDPR violation risk and improves data governance',
        effort: 'Medium - Requires documentation and system configuration',
        estimatedTime: '3-4 weeks with phased implementation',
        relatedGaps: ['gap_1'],
      },
    ],
    risk_assessment: {
      overall_risk_level: 'high' as const,
      risk_score: 7.2,
      key_risk_areas: ['Data Retention', 'Automated Compliance', 'Legal Documentation'],
    },
    compliance_insights: {
      maturity_level: 'Developing',
      score_breakdown: {
        'Data Processing': 75,
        'Subject Rights': 82,
        'Security Measures': 68,
      },
      improvement_priority: ['Data Retention', 'Security Controls', 'Documentation'],
    },
    evidence_requirements: [
      {
        priority: 'high' as const,
        evidence_type: 'Policy Documentation',
        description: 'Documented data retention policy with approval and review dates',
        control_mapping: ['GDPR Article 5', 'ISO 27001 A.18.1.4'],
      },
    ],
  },
};

class AssessmentAIService {
  private useProductionEndpoints =
    process.env.NODE_ENV === 'production' || process.env['NEXT_PUBLIC_USE_REAL_AI'] === 'true';

  /**
   * Get AI help for a specific assessment question
   */
  async getQuestionHelp(request: AIHelpRequest): Promise<AIHelpResponse> {
    return withRetry(
      async () => {
        try {
          if (this.useProductionEndpoints) {
            const aiRequest = apiClient.post<AIHelpResponse>(
              `/ai/assessments/${request.framework_id}/help`,
              request,
            );
            const response = await this.executeWithTimeout(
              aiRequest,
              15000,
              'Question help AI request',
            );
            return response;
          }

          // Development fallback with no artificial delay
          return mockAIResponses.help;
        } catch (error: unknown) {
          // TODO: Replace with proper logging

          // // TODO: Replace with proper logging

          // Handle rate limiting specifically - don't retry immediately
          if (error.response?.status === 429) {
            const rateLimitError = error.response.data as AIRateLimitError;
            const retryAfter = rateLimitError.error.retry_after;

            return {
              guidance: `Rate limit exceeded for AI help requests. ${rateLimitError.suggestion}`,
              confidence_score: 0.1,
              related_topics: ['Rate Limiting'],
              follow_up_suggestions: [
                `Wait ${retryAfter} seconds before trying again`,
                'Consider reviewing existing guidance while waiting',
                'Contact support if you need immediate assistance',
              ],
              source_references: [
                `Rate limit: ${rateLimitError.error.limit} requests per ${rateLimitError.error.window}`,
              ],
            };
          }

          // Enhanced error handling with fallback to mock data
          if (this.useProductionEndpoints && error instanceof Error) {
            // TODO: Replace with proper logging
            return mockAIResponses.help;
          }

          throw createAppError(error, 'AI help request');
        }
      },
      {
        maxAttempts: 2,
        initialDelay: 1000,
        retryCondition: (error) => error.type === 'network' || error.type === 'server',
      },
    );
  }

  /**
   * Get AI-generated follow-up questions based on current responses
   */
  async getFollowUpQuestions(request: AIFollowUpRequest): Promise<AIFollowUpResponse> {
    try {
      if (this.useProductionEndpoints) {
        const aiRequest = apiClient.post<AIFollowUpResponse>('/ai/assessments/followup', request);
        const response = await this.executeWithTimeout(
          aiRequest,
          20000,
          'Follow-up questions AI request',
        );
        return response;
      }

      // Development fallback with no artificial delay
      return mockAIResponses.followUp;
    } catch (error: unknown) {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging

      // Handle rate limiting specifically
      if (error.response?.status === 429) {
        const rateLimitError = error.response.data as AIRateLimitError;
        const retryAfter = rateLimitError.error.retry_after;

        return {
          follow_up_questions: [],
          reasoning: `Rate limit exceeded for AI follow-up questions. ${rateLimitError.suggestion}`,
          estimated_completion_time: retryAfter,
        };
      }

      // Enhanced error handling with fallback to mock data
      if (this.useProductionEndpoints && error instanceof Error) {
        // TODO: Replace with proper logging
        return mockAIResponses.followUp;
      }

      throw new Error('Unable to generate follow-up questions at this time.');
    }
  }

  /**
   * Get comprehensive AI analysis of assessment results
   */
  async getAssessmentAnalysis(request: AIAnalysisRequest): Promise<AIAnalysisResponse> {
    try {
      if (this.useProductionEndpoints) {
        const response = await apiClient.post<AIAnalysisResponse>(
          '/ai/assessments/analysis',
          request,
        );
        return response;
      }

      // Development fallback
      return mockAIResponses.analysis;
    } catch (error) {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging

      if (this.useProductionEndpoints && error instanceof Error) {
        // TODO: Replace with proper logging
        return mockAIResponses.analysis;
      }

      throw new Error('Unable to analyze assessment results at this time.');
    }
  }

  /**
   * Get AI-generated personalized recommendations
   */
  async getPersonalizedRecommendations(
    request: AIRecommendationRequest,
  ): Promise<AIRecommendationResponse> {
    try {
      if (this.useProductionEndpoints) {
        const response = await apiClient.post<AIRecommendationResponse>(
          '/ai/assessments/recommendations',
          request,
        );
        return response;
      }

      // Development fallback
      return {
        recommendations: mockAIResponses.analysis.recommendations,
        implementation_plan: {
          phases: [
            {
              phase_number: 1,
              phase_name: 'Foundation & Documentation',
              duration_weeks: 4,
              tasks: [
                'Document current data retention practices',
                'Create formal retention policy',
                'Get legal review and approval',
              ],
              dependencies: [],
            },
            {
              phase_number: 2,
              phase_name: 'Implementation & Automation',
              duration_weeks: 6,
              tasks: [
                'Implement automated deletion systems',
                'Train staff on new procedures',
                'Conduct compliance testing',
              ],
              dependencies: ['Phase 1 completion'],
            },
          ],
          total_timeline_weeks: 10,
          resource_requirements: ['DPO (0.5 FTE)', 'Legal Counsel', 'IT Developer (0.25 FTE)'],
        },
        success_metrics: [
          '100% of data categories have documented retention periods',
          'Automated deletion operational for 80% of data types',
          'Zero retention-related compliance incidents',
        ],
      };
    } catch (error) {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging

      if (this.useProductionEndpoints && error instanceof Error) {
        // TODO: Replace with proper logging
        return {
          recommendations: mockAIResponses.analysis.recommendations,
          implementation_plan: {
            phases: [
              {
                phase_number: 1,
                phase_name: 'Foundation & Documentation',
                duration_weeks: 4,
                tasks: [
                  'Document current data retention practices',
                  'Create formal retention policy',
                  'Get legal review and approval',
                ],
                dependencies: [],
              },
            ],
            total_timeline_weeks: 10,
            resource_requirements: ['DPO (0.5 FTE)', 'Legal Counsel'],
          },
          success_metrics: [
            '100% of data categories have documented retention periods',
            'Automated deletion operational for 80% of data types',
          ],
        };
      }

      throw new Error('Unable to generate recommendations at this time.');
    }
  }

  /**
   * Connect to chat service for conversational assessment help
   */
  async getConversationalHelp(
    conversationId: string,
    questionContext: {
      question: Question;
      framework: string;
      userResponse?: any;
    },
  ): Promise<void> {
    const helpMessage = `I need help with this assessment question:

**Framework:** ${questionContext.framework}
**Question:** ${questionContext.question.text}
${questionContext.question.description ? `**Context:** ${questionContext.question.description}` : ''}
${questionContext.userResponse ? `**My current answer:** ${questionContext.userResponse}` : ''}

Can you provide guidance on how to answer this question correctly?`;

    await chatService.sendMessage(conversationId, {
      content: helpMessage,
    });
  }

  /**
   * Submit feedback on AI assistance quality
   */
  async submitFeedback(
    interactionId: string,
    feedback: {
      helpful: boolean;
      rating?: number;
      comments?: string;
      improvement_suggestions?: string[];
    },
  ): Promise<void> {
    try {
      if (this.useProductionEndpoints) {
        await apiClient.post('/ai/assessments/feedback', {
          interaction_id: interactionId,
          ...feedback,
        });
      } else {
    // TODO: Replace with proper logging
      }
    } catch (error) {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging
      // Non-blocking - don't throw error for feedback submission
    }
  }

  /**
   * Get AI performance metrics for admin users
   */
  async getAIMetrics(): Promise<{
    response_times: { avg: number; p95: number };
    accuracy_score: number;
    user_satisfaction: number;
    total_interactions: number;
  }> {
    try {
      const response = await apiClient.get<{
        response_times: { avg: number; p95: number };
        accuracy_score: number;
        user_satisfaction: number;
        total_interactions: number;
      }>('/ai/assessments/metrics');
      return response;
    } catch (error) {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging
      throw new Error('Unable to retrieve AI performance metrics.');
    }
  }

  // ===== HELPER METHODS FOR CONTEXT EXTRACTION =====

  /**
   * Extract business profile information from assessment context
   * Combines explicit business profile data with inferred context from answers
   */
  getBusinessProfileFromContext(
    businessProfile?: Partial<BusinessProfile>,
    currentAnswers?: Record<string, any>,
  ): Partial<BusinessProfile> {
    const context: Partial<BusinessProfile> = { ...businessProfile };

    if (!currentAnswers) return context;

    // Extract company size from answers
    if (currentAnswers?.['company_size'] || currentAnswers?.['employee_count']) {
      // Note: BusinessProfile from @/types/auth doesn't have employee_count, using size instead
      (context as any).size = currentAnswers['company_size'] || currentAnswers['employee_count'];
    }

    // Extract industry information - ensure proper capitalization
    if (currentAnswers?.['industry'] || currentAnswers?.['business_sector']) {
      const industry = currentAnswers['industry'] || currentAnswers['business_sector'];
      // Capitalize the industry name properly
      if (typeof industry === 'string') {
        context.industry = industry.charAt(0).toUpperCase() + industry.slice(1).toLowerCase();
      }
    }

    // Extract compliance frameworks
    if (currentAnswers?.['compliance_frameworks']) {
      context.planned_frameworks = Array.isArray(currentAnswers['compliance_frameworks'])
        ? currentAnswers['compliance_frameworks']
        : [currentAnswers['compliance_frameworks']];
    }

    // Note: The BusinessProfile from @/types/auth has limited properties
    // Additional context can be stored in a separate object for AI processing

    return context;
  }

  /**
   * Extract existing policies and compliance measures from user answers
   * Identifies what compliance measures are already in place
   */
  getExistingPoliciesFromAnswers(currentAnswers?: Record<string, any>): {
    existing_policies: string[];
    compliance_measures: string[];
    gaps_identified: string[];
  } {
    const result = {
      existing_policies: [] as string[],
      compliance_measures: [] as string[],
      gaps_identified: [] as string[],
    };

    if (!currentAnswers) return result;

    // Check for existing policies
    const policyQuestions = [
      'privacy_policy',
      'data_protection_policy',
      'security_policy',
      'incident_response_plan',
      'staff_training_policy',
      'retention_policy',
    ];

    policyQuestions.forEach((policy) => {
      if (currentAnswers[policy] === 'Yes' || currentAnswers[policy] === true) {
        result.existing_policies.push(
          policy.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
        );
      } else if (currentAnswers[policy] === 'No' || currentAnswers[policy] === false) {
        result.gaps_identified.push(
          policy.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
        );
      }
    });

    // Check for compliance measures
    const complianceMeasures = [
      'regular_audits',
      'staff_training',
      'access_controls',
      'encryption',
      'backup_procedures',
      'incident_logging',
      'vendor_assessments',
    ];

    complianceMeasures.forEach((measure) => {
      if (currentAnswers[measure] === 'Yes' || currentAnswers[measure] === true) {
        result.compliance_measures.push(
          measure.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
        );
      } else if (currentAnswers[measure] === 'No' || currentAnswers[measure] === false) {
        result.gaps_identified.push(
          measure.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
        );
      }
    });

    // Check for specific compliance frameworks
    if (currentAnswers['gdpr_compliance'] === 'Yes') {
      result.compliance_measures.push('GDPR Compliance Program');
    }
    if (currentAnswers['iso27001'] === 'Yes') {
      result.compliance_measures.push('ISO 27001 Implementation');
    }
    if (currentAnswers['cyber_essentials'] === 'Yes') {
      result.compliance_measures.push('Cyber Essentials Certification');
    }

    return result;
  }

  /**
   * Extract industry-specific context and regulatory requirements
   * Determines applicable regulations based on industry and business activities
   */
  getIndustryContextFromAnswers(
    businessProfile?: Partial<BusinessProfile>,
    currentAnswers?: Record<string, any>,
  ): {
    industry: string;
    applicable_regulations: string[];
    risk_level: 'low' | 'medium' | 'high';
    special_requirements: string[];
  } {
    const industry = businessProfile?.industry || currentAnswers?.['industry'] || 'general';
    const result = {
      industry,
      applicable_regulations: ['GDPR', 'UK GDPR', 'Data Protection Act 2018'] as string[],
      risk_level: 'medium' as 'low' | 'medium' | 'high',
      special_requirements: [] as string[],
    };

    // Industry-specific regulations
    switch (industry.toLowerCase()) {
      case 'financial services':
      case 'banking':
      case 'fintech':
        result.applicable_regulations.push('FCA Regulations', 'PCI DSS', 'Basel III');
        result.risk_level = 'high';
        result.special_requirements.push('Financial conduct reporting', 'Anti-money laundering');
        break;

      case 'healthcare':
      case 'medical':
        result.applicable_regulations.push('MHRA Regulations', 'Clinical Trial Regulations');
        result.risk_level = 'high';
        result.special_requirements.push('Patient data protection', 'Medical device compliance');
        break;

      case 'education':
        result.applicable_regulations.push('Equality Act 2010', 'Children Act 2004');
        result.special_requirements.push('Safeguarding requirements', 'Student data protection');
        break;

      case 'retail':
      case 'e-commerce':
        if (currentAnswers?.['processes_payments']) {
          result.applicable_regulations.push('PCI DSS', 'Consumer Rights Act 2015');
        }
        result.special_requirements.push('Consumer protection', 'Product safety');
        break;

      case 'technology':
      case 'software':
        result.applicable_regulations.push('Cyber Security Regulations');
        if (currentAnswers?.['ai_processing'] || currentAnswers?.['automated_decisions']) {
          result.special_requirements.push('AI governance', 'Algorithmic transparency');
        }
        break;

      default:
        result.risk_level = 'medium';
    }

    // Additional context from answers
    if (
      currentAnswers?.['handles_personal_data'] === 'Yes' ||
      currentAnswers?.['data_sensitivity'] === 'High'
    ) {
      result.risk_level = result.risk_level === 'low' ? 'medium' : result.risk_level;
    }

    if (currentAnswers?.['international_transfers'] === 'Yes') {
      result.applicable_regulations.push('International Transfer Regulations');
      result.special_requirements.push('Adequacy decisions', 'Transfer impact assessments');
    }

    if (currentAnswers?.['employee_count'] && parseInt(currentAnswers['employee_count']) > 250) {
      result.special_requirements.push('Large organization reporting', 'DPO appointment required');
    }

    return result;
  }

  /**
   * Extract timeline preferences and urgency indicators from user responses
   * Helps prioritize recommendations based on user's implementation timeline
   */
  getTimelinePreferenceFromAnswers(currentAnswers?: Record<string, any>): {
    urgency: 'low' | 'medium' | 'high' | 'critical';
    preferred_timeline: string;
    implementation_capacity: 'limited' | 'moderate' | 'high';
    priority_areas: string[];
  } {
    const result = {
      urgency: 'medium' as 'low' | 'medium' | 'high' | 'critical',
      preferred_timeline: '3-6 months',
      implementation_capacity: 'moderate' as 'limited' | 'moderate' | 'high',
      priority_areas: [] as string[],
    };

    if (!currentAnswers) return result;

    // Extract explicit timeline preferences
    if (currentAnswers['implementation_timeline']) {
      result.preferred_timeline = currentAnswers['implementation_timeline'];

      // Map timeline to urgency
      const timeline = currentAnswers['implementation_timeline'].toLowerCase();
      if (timeline.includes('immediate') || timeline.includes('1 month')) {
        result.urgency = 'critical';
      } else if (timeline.includes('3 month') || timeline.includes('quarter')) {
        result.urgency = 'high';
      } else if (timeline.includes('6 month') || timeline.includes('year')) {
        result.urgency = 'medium';
      } else {
        result.urgency = 'low';
      }
    }

    // Extract urgency indicators
    if (
      currentAnswers['recent_incidents'] === 'Yes' ||
      currentAnswers['security_breaches'] === 'Yes'
    ) {
      result.urgency = 'critical';
      result.priority_areas.push('Incident response', 'Security measures');
    }

    if (currentAnswers['regulatory_deadline'] === 'Yes' || currentAnswers['compliance_deadline']) {
      result.urgency = result.urgency === 'low' ? 'high' : 'critical';
      result.priority_areas.push('Regulatory compliance');
    }

    if (currentAnswers['audit_upcoming'] === 'Yes') {
      result.urgency = 'high';
      result.priority_areas.push('Audit preparation', 'Documentation');
    }

    // Extract implementation capacity
    if (currentAnswers['dedicated_compliance_team'] === 'Yes') {
      result.implementation_capacity = 'high';
    } else if (currentAnswers['compliance_resources'] === 'Limited') {
      result.implementation_capacity = 'limited';
    }

    if (currentAnswers['budget_constraints'] === 'Yes') {
      result.implementation_capacity = 'limited';
      result.priority_areas.push('Cost-effective solutions');
    }

    // Extract priority areas from gaps
    if (currentAnswers['biggest_concern']) {
      const concern = currentAnswers['biggest_concern'].toLowerCase();
      if (concern.includes('data') || concern.includes('privacy')) {
        result.priority_areas.push('Data protection');
      }
      if (concern.includes('security') || concern.includes('cyber')) {
        result.priority_areas.push('Cybersecurity');
      }
      if (concern.includes('staff') || concern.includes('training')) {
        result.priority_areas.push('Staff training');
      }
    }

    return result;
  }

  /**
   * Execute AI request with timeout handling using Promise.race
   * Ensures AI requests don't hang indefinitely
   */
  private async executeWithTimeout<T>(
    aiRequest: Promise<T>,
    timeoutMs: number = 30000,
    operation: string = 'AI request',
  ): Promise<T> {
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new Error(`${operation} timed out after ${timeoutMs}ms`));
      }, timeoutMs);
    });

    try {
      const result = await Promise.race([aiRequest, timeoutPromise]);
      return result;
    } catch {
      if (error instanceof Error && error.message.includes('timed out')) {
        // TODO: Replace with proper logging
        throw new Error(`${operation} is taking longer than expected. Please try again.`);
      }
      throw error;
    }
  }

  /**
   * Enhanced AI request wrapper that combines context extraction with timeout handling
   * Uses all helper methods to provide rich context to AI requests
   */
  async getEnhancedAIResponse(
    prompt: string,
    context: {
      businessProfile?: Partial<BusinessProfile>;
      currentAnswers?: Record<string, any>;
      assessmentType?: string;
    },
    timeoutMs: number = 30000,
  ): Promise<any> {
    try {
      // Extract comprehensive context using helper methods
      const businessContext = this.getBusinessProfileFromContext(
        context.businessProfile,
        context.currentAnswers,
      );

      const existingPolicies = this.getExistingPoliciesFromAnswers(context.currentAnswers);

      const industryContext = this.getIndustryContextFromAnswers(
        context.businessProfile,
        context.currentAnswers,
      );

      const timelinePreferences = this.getTimelinePreferenceFromAnswers(context.currentAnswers);

      // Build enhanced context for AI
      const enhancedContext = {
        business_profile: businessContext,
        existing_policies: existingPolicies,
        industry_context: industryContext,
        timeline_preferences: timelinePreferences,
        assessment_type: context.assessmentType || 'general',
      };

      // Use mock response in test/development mode
      if (!this.useProductionEndpoints) {
        return {
          analysis: `${mockAIResponses.analysis.compliance_insights.maturity_level} - Based on your assessment responses, we have identified key areas for improvement.`,
          recommendations: mockAIResponses.analysis.recommendations,
          confidence_score: 0.92,
          gaps: mockAIResponses.analysis.gaps,
          risk_assessment: mockAIResponses.analysis.risk_assessment,
          compliance_insights: mockAIResponses.analysis.compliance_insights,
        };
      }

      // Make AI request with timeout
      const aiRequest = apiClient.post('/ai/assessments/enhanced-analysis', {
        prompt,
        context: enhancedContext,
        timestamp: new Date().toISOString(),
      });

      const response = await this.executeWithTimeout(aiRequest, timeoutMs, 'Enhanced AI analysis');

      return response;
    } catch (error) {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging

      // Fallback response with basic recommendations
      return {
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
    }
  }

  // Streaming Methods
  async analyzeAssessmentWithStreaming(
    request: AIAnalysisRequest,
    options: StreamingOptions,
  ): Promise<void> {
    try {
      const eventSource = new EventSource('/api/v1/ai/assessments/analysis/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${await this.getAuthToken()}`,
        },
        body: JSON.stringify(request),
      } as any);

      eventSource.onmessage = (event) => {
        try {
          const chunk: StreamingChunk = JSON.parse(event.data);

          switch (chunk.chunk_type) {
            case 'metadata':
              const metadata: StreamingMetadata = JSON.parse(chunk.content);
              options.onMetadata?.(metadata);
              break;
            case 'content':
              options.onChunk?.(chunk);
              break;
            case 'complete':
              options.onComplete?.();
              eventSource.close();
              break;
            case 'error':
              options.onError?.(chunk.content);
              eventSource.close();
              break;
          }
        } catch {
          // TODO: Replace with proper logging

          // // TODO: Replace with proper logging
          options.onError?.('Error parsing response data');
        }
      };

      eventSource.onerror = () => {
        options.onError?.('Connection error occurred');
        eventSource.close();
      };
    } catch (error) {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging
      options.onError?.('Failed to start analysis stream');
    }
  }

  async getRecommendationsWithStreaming(
    request: AIRecommendationRequest,
    options: StreamingOptions,
  ): Promise<void> {
    try {
      const eventSource = new EventSource('/api/v1/ai/assessments/recommendations/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${await this.getAuthToken()}`,
        },
        body: JSON.stringify(request),
      } as any);

      eventSource.onmessage = (event) => {
        try {
          const chunk: StreamingChunk = JSON.parse(event.data);

          switch (chunk.chunk_type) {
            case 'metadata':
              const metadata: StreamingMetadata = JSON.parse(chunk.content);
              options.onMetadata?.(metadata);
              break;
            case 'content':
              options.onChunk?.(chunk);
              break;
            case 'complete':
              options.onComplete?.();
              eventSource.close();
              break;
            case 'error':
              options.onError?.(chunk.content);
              eventSource.close();
              break;
          }
        } catch {
          // TODO: Replace with proper logging

          // // TODO: Replace with proper logging
          options.onError?.('Error parsing response data');
        }
      };

      eventSource.onerror = () => {
        options.onError?.('Connection error occurred');
        eventSource.close();
      };
    } catch (error) {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging
      options.onError?.('Failed to start recommendations stream');
    }
  }

  async getQuestionHelpWithStreaming(
    frameworkId: string,
    request: AIHelpRequest,
    options: StreamingOptions,
  ): Promise<void> {
    try {
      const eventSource = new EventSource(`/api/v1/ai/assessments/${frameworkId}/help/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${await this.getAuthToken()}`,
        },
        body: JSON.stringify(request),
      } as any);

      eventSource.onmessage = (event) => {
        try {
          const chunk: StreamingChunk = JSON.parse(event.data);

          switch (chunk.chunk_type) {
            case 'metadata':
              const metadata: StreamingMetadata = JSON.parse(chunk.content);
              options.onMetadata?.(metadata);
              break;
            case 'content':
              options.onChunk?.(chunk);
              break;
            case 'complete':
              options.onComplete?.();
              eventSource.close();
              break;
            case 'error':
              options.onError?.(chunk.content);
              eventSource.close();
              break;
          }
        } catch {
          // TODO: Replace with proper logging

          // // TODO: Replace with proper logging
          options.onError?.('Error parsing response data');
        }
      };

      eventSource.onerror = () => {
        options.onError?.('Connection error occurred');
        eventSource.close();
      };
    } catch (error) {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging
      options.onError?.('Failed to start help stream');
    }
  }

  private async getAuthToken(): Promise<string> {
    // Implementation would depend on your auth system
    // This is a placeholder for the actual token retrieval
    return localStorage.getItem('auth_token') || '';
  }
}

export const assessmentAIService = new AssessmentAIService();
