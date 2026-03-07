/**
 * FreemiumService - API client for public assessment endpoints
 * Handles email capture, session management, and assessment flow
 */

import { validateRequest, validateApiResponse } from '@/lib/api/validation';
import {
  LeadCaptureRequestSchema,
  LeadResponseSchema,
  AssessmentStartRequestSchema,
  FreemiumAssessmentStartResponseSchema,
  AssessmentAnswerRequestSchema,
  AssessmentQuestionResponseSchema,
  AssessmentResultsResponseSchema,
  HealthStatusSchema,
} from '@/lib/validation/zod-schemas';
import type {
  LeadCaptureRequest,
  LeadResponse,
  AssessmentStartRequest,
  FreemiumAssessmentStartResponse,
  AssessmentAnswerRequest,
  AssessmentQuestionResponse,
  AssessmentResultsResponse,
  HealthStatus,
} from '@/types/freemium';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Validate email format
 */
export const isValidEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

/**
 * Get severity color for UI display
 */
export const getSeverityColor = (severity: 'low' | 'medium' | 'high' | 'critical'): string => {
  const colors = {
    low: 'text-blue-600 bg-blue-50',
    medium: 'text-yellow-600 bg-yellow-50',
    high: 'text-orange-600 bg-orange-50',
    critical: 'text-red-600 bg-red-50',
  };
  return colors[severity] || colors.medium;
};

/**
 * Get risk score color for UI display
 */
export const getRiskScoreColor = (score: number): string => {
  if (score >= 80) return 'text-red-600';
  if (score >= 60) return 'text-orange-600';
  if (score >= 40) return 'text-yellow-600';
  return 'text-green-600';
};

/**
 * Format risk score for display
 */
export const formatRiskScore = (score: number): string => {
  return `${score.toFixed(0)}%`;
};

/**
 * Extract UTM parameters from URL
 */
export const extractUtmParams = () => {
  if (typeof window === 'undefined') return {};

  const urlParams = new URLSearchParams(window.location.search);
  return {
    utm_source: urlParams.get('utm_source'),
    utm_medium: urlParams.get('utm_medium'),
    utm_campaign: urlParams.get('utm_campaign'),
    utm_term: urlParams.get('utm_term'),
    utm_content: urlParams.get('utm_content'),
  };
};

// ============================================================================
// TYPE EXPORTS
// ============================================================================

export type {
  ComplianceGap,
  AssessmentResultsResponse as FreemiumResultsResponse,
  LeadCaptureRequest,
  LeadResponse,
  AssessmentStartRequest,
  FreemiumAssessmentStartResponse,
  AssessmentAnswerRequest,
  AssessmentQuestionResponse,
  AssessmentResultsResponse,
  HealthStatus,
} from '@/types/freemium';

// Additional type aliases for backward compatibility
export type FreemiumEmailCaptureRequest = LeadCaptureRequest;
export interface FreemiumEmailCaptureResponse extends LeadResponse {
  token?: string;
}
export type FreemiumAnswerRequest = AssessmentAnswerRequest;
export type FreemiumAnswerResponse = AssessmentQuestionResponse;

// Legacy interfaces (for backward compatibility)
export interface SessionStartRequest extends AssessmentStartRequest {}
export interface SessionResponse extends FreemiumAssessmentStartResponse {}
export interface AnswerSubmissionRequest extends AssessmentAnswerRequest {}

export interface ConversionTrackingRequest {
  event_type: string;
  metadata?: Record<string, unknown>;
}

export interface ConversionTrackingResponse {
  event_id: string;
  score_applied: number;
  total_score: number;
  engagement_level: 'low' | 'medium' | 'high';
  conversion_probability: number;
  next_recommended_action: string;
  recorded_at: string;
}

export interface TrialOffer {
  title: string;
  description: string;
  cta_text: string;
  discount_percentage?: number;
  valid_until?: string;
}

class FreemiumService {
  private baseUrl = `${API_BASE}/api/v1/freemium`;

  /**
   * Capture email and lead information
   */
  async captureEmail(data: LeadCaptureRequest): Promise<LeadResponse> {
    // Validate request data
    const validatedData = validateRequest({
      ...data,
      user_agent: typeof window !== 'undefined' ? navigator.userAgent : undefined,
      referrer_url: typeof document !== 'undefined' ? document.referrer : undefined,
      landing_page: typeof window !== 'undefined' ? window.location.href : undefined,
    }, LeadCaptureRequestSchema);

    const response = await fetch(`${this.baseUrl}/leads`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(validatedData),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Network error' }));
      throw new Error(error.detail || 'Failed to capture email');
    }

    const responseData = await response.json();
    return validateApiResponse(responseData, LeadResponseSchema) as LeadResponse;
  }

  /**
   * Start a new assessment session
   */
  async startAssessment(data: AssessmentStartRequest): Promise<FreemiumAssessmentStartResponse> {
    // Validate request data
    const validatedData = validateRequest(data, AssessmentStartRequestSchema);

    const response = await fetch(`${this.baseUrl}/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(validatedData),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Network error' }));
      throw new Error(error.detail || 'Failed to start assessment');
    }

    const responseData = await response.json();
    return validateApiResponse(responseData, FreemiumAssessmentStartResponseSchema) as FreemiumAssessmentStartResponse;
  }

  /**
   * Get session progress
   */
  async getSessionProgress(sessionToken: string): Promise<FreemiumAssessmentStartResponse> {
    const response = await fetch(`${this.baseUrl}/sessions/${sessionToken}`, {
      method: 'GET',
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Network error' }));
      throw new Error(error.detail || 'Failed to get session progress');
    }

    const responseData = await response.json();
    return validateApiResponse(responseData, FreemiumAssessmentStartResponseSchema) as FreemiumAssessmentStartResponse;
  }

  /**
   * Submit an answer
   */
  async submitAnswer(sessionToken: string, data: AssessmentAnswerRequest): Promise<AssessmentQuestionResponse> {
    // Validate request data
    const validatedData = validateRequest(data, AssessmentAnswerRequestSchema);

    const response = await fetch(`${this.baseUrl}/sessions/${sessionToken}/answers`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(validatedData),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Network error' }));
      throw new Error(error.detail || 'Failed to submit answer');
    }

    const responseData = await response.json();
    return validateApiResponse(responseData, AssessmentQuestionResponseSchema) as AssessmentQuestionResponse;
  }

  /**
   * Get assessment results
   */
  async getResults(sessionToken: string): Promise<AssessmentResultsResponse> {
    const response = await fetch(`${this.baseUrl}/sessions/${sessionToken}/results`, {
      method: 'GET',
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Network error' }));
      throw new Error(error.detail || 'Failed to get results');
    }

    const json = await response.json();
    return validateApiResponse(json, AssessmentResultsResponseSchema) as unknown as AssessmentResultsResponse;
  }

  /**
   * Health check
   */
  async healthCheck(): Promise<HealthStatus> {
    const response = await fetch(`${this.baseUrl}/health`, {
      method: 'GET',
    });

    if (!response.ok) {
      throw new Error('Freemium API is not available');
    }

    const responseData = await response.json();
    return validateApiResponse(responseData, HealthStatusSchema) as HealthStatus;
  }

  /**
   * Complete assessment and persist results
   */
  async completeAssessment(sessionToken: string, result: any): Promise<AssessmentResultsResponse> {
    // Convert answers Map to array if needed
    let answers = result.answers || [];
    if (result.answers instanceof Map) {
      answers = Array.from(result.answers.values());
    }

    // Serialize file upload answers to prevent JSON serialization errors
    const serializedAnswers = answers.map((answer: any) => {
      if (answer.value instanceof File || answer.value instanceof Blob) {
        // For file uploads, store metadata instead of the actual file
        return {
          ...answer,
          value: {
            type: 'file_upload',
            name: (answer.value as File).name || 'uploaded_file',
            size: answer.value.size,
            mimeType: answer.value.type,
            // Note: Actual file upload would need a separate endpoint
          }
        };
      }
      // Handle arrays that might contain files
      if (Array.isArray(answer.value)) {
        return {
          ...answer,
          value: answer.value.map((item: any) => {
            if (item instanceof File || item instanceof Blob) {
              return {
                type: 'file_upload',
                name: (item as File).name || 'uploaded_file',
                size: item.size,
                mimeType: item.type,
              };
            }
            return item;
          })
        };
      }
      return answer;
    });

    // Check if backend expects 'compliance_score' instead of 'overall_score'
    // Using both for compatibility
    const response = await fetch(`${this.baseUrl}/sessions/${sessionToken}/complete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        completed_at: new Date().toISOString(),
        answers: serializedAnswers,
        section_scores: result.sectionScores || {},
        overall_score: result.overallScore || 0,
        compliance_score: result.overallScore || 0, // Duplicate for API compatibility
        risk_score: result.riskScore || null,  // Allow null if not computed client-side
        metadata: {
          framework_id: result.frameworkId || 'default',
          completion_time: result.completionTime || 0,
          user_agent: typeof window !== 'undefined' ? window.navigator.userAgent : 'unknown',
        }
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to complete assessment: ${response.statusText}`);
    }

    const responseData = await response.json();
    return validateApiResponse(responseData, AssessmentResultsResponseSchema) as unknown as AssessmentResultsResponse;
  }

  /**
   * Save assessment progress
   * Note: This is a stub implementation as server persistence may be out of scope
   */
  async saveProgress(sessionToken: string, progress: any): Promise<void> {
    try {
      // Store progress in sessionStorage as a fallback
      sessionStorage.setItem(`assessment_progress_${sessionToken}`, JSON.stringify({
        progress,
        savedAt: new Date().toISOString(),
        sessionToken
      }));

      // TODO: Implement server-side persistence when API endpoint is available
      // const response = await fetch(`${this.baseUrl}/sessions/${sessionToken}/progress`, {
      //   method: 'PUT',
      //   headers: {
      //     'Content-Type': 'application/json',
      //   },
      //   body: JSON.stringify({ progress }),
      // });

      // For now, just resolve successfully
      return Promise.resolve();
    } catch (error) {
      console.error('Failed to save assessment progress:', error);
      throw new Error('Failed to save progress. Please try again.');
    }
  }

  /**
   * Get assessment history for a business profile
   */
  async getAssessmentHistory(businessProfileId: string, params?: {
    limit?: number;
    offset?: number;
    framework_id?: string;
  }): Promise<AssessmentResultsResponse[]> {
    const queryParams = new URLSearchParams();

    if (params?.limit) {
      queryParams.append('limit', params.limit.toString());
    }
    if (params?.offset) {
      queryParams.append('offset', params.offset.toString());
    }
    if (params?.framework_id) {
      queryParams.append('framework_id', params.framework_id);
    }

    const queryString = queryParams.toString();
    const url = `${this.baseUrl}/history/${businessProfileId}${queryString ? `?${queryString}` : ''}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Network error' }));
      console.error('[FreemiumService] Failed to fetch assessment history:', response.status, error);
      throw new Error(error.detail || 'Failed to fetch assessment history');
    }

    const responseData = await response.json();

    // Validate each item in the response array
    if (Array.isArray(responseData)) {
      return responseData.map(item => validateApiResponse(item, AssessmentResultsResponseSchema) as unknown as AssessmentResultsResponse);
    }

    // If single item returned, wrap in array
    return [validateApiResponse(responseData, AssessmentResultsResponseSchema) as unknown as AssessmentResultsResponse];
  }
}

export const freemiumService = new FreemiumService();

// ============================================================================
// BACKWARD COMPATIBILITY API FUNCTIONS
// ============================================================================

export const captureEmail = (
  data: FreemiumEmailCaptureRequest,
): Promise<FreemiumEmailCaptureResponse> => freemiumService.captureEmail(data);

export const startAssessment = (token: string): Promise<FreemiumAssessmentStartResponse> =>
  freemiumService.startAssessment({ lead_id: token, business_type: 'default' });

export const answerQuestion = (
  token: string,
  answerData: FreemiumAnswerRequest,
): Promise<FreemiumAnswerResponse> => freemiumService.submitAnswer(token, answerData);

export const getResults = (token: string): Promise<AssessmentResultsResponse> =>
  freemiumService.getResults(token);

export const trackConversion = (
  _token: string,
  _data: ConversionTrackingRequest,
): Promise<ConversionTrackingResponse> =>
  Promise.resolve({
    event_id: 'mock',
    score_applied: 0,
    total_score: 0,
    engagement_level: 'low' as const,
    conversion_probability: 0,
    next_recommended_action: 'continue',
    recorded_at: new Date().toISOString(),
  });
