/**
 * Type definitions for the AI Assessment Freemium Strategy
 * Matches backend API schemas from api/routers/freemium.py
 */

// ============================================================================
// CORE TYPES
// ============================================================================

export interface PersonalizationData {
  user_type?: string;
  priority_areas?: string[];
  current_challenges?: string[];
  tech_stack?: string[];
  budget_range?: string;
  timeline?: string;
  industry_preferences?: string[];
  framework_focus?: string[];
  business_size_category?: 'startup' | 'small' | 'medium' | 'large' | 'enterprise';
  custom_settings?: Record<string, unknown>;
}

export type AssessmentAnswer =
  | string
  | number
  | boolean
  | string[]
  | {
      value: string | number | boolean;
      metadata?: Record<string, unknown>;
    };

export interface UTMParameters {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_term?: string;
  utm_content?: string;
}

export interface TrackingMetadata {
  timestamp: string;
  page_url?: string;
  referrer?: string;
  session_id?: string;
  user_agent?: string;
  device_type?: string;
  session_duration?: number;
  utm_params?: UTMParameters;
  custom_properties?: Record<string, unknown>;
}

export interface FreemiumBehaviorEvent {
  event_type: string;
  event_category?: string;
  event_label?: string;
  event_value?: number;
  metadata?: TrackingMetadata;
}

// ============================================================================
// REQUEST TYPES
// ============================================================================

export interface LeadCaptureRequest {
  email: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  company_size?: string;
  industry?: string;
  phone?: string;
  newsletter_subscribed?: boolean;
  marketing_consent?: boolean;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_term?: string;
  utm_content?: string;
  referrer_url?: string;
  landing_page?: string;
  user_agent?: string;
  ip_address?: string;
}

export interface AssessmentStartRequest {
  lead_id: string;
  business_type: string;
  company_size?: string;
  industry?: string;
  compliance_frameworks?: string[];
  personalization_data?: PersonalizationData;
}

export interface AssessmentAnswerRequest {
  session_token: string;
  question_id: string;
  answer: AssessmentAnswer;
  time_spent_seconds?: number;
  confidence_level?: number;
}

export interface ResultsGenerationRequest {
  session_token: string;
  include_recommendations?: boolean;
  include_detailed_analysis?: boolean;
}

// ============================================================================
// RESPONSE TYPES
// ============================================================================

export interface LeadResponse {
  lead_id: string;
  email: string;
  lead_score: number;
  lead_status: string;
  message: string;
  created_at: string;
}

export interface FreemiumAssessmentStartResponse {
  session_id: string;
  session_token: string;
  question_id: string;
  question_text: string;
  question_type: 'multiple_choice' | 'yes_no' | 'text' | 'scale';
  question_context?: string;
  answer_options?: string[];
  is_required?: boolean;
  progress: {
    current_question: number;
    total_questions_estimate: number;
    progress_percentage: number;
  };
  personalization_applied: boolean;
  expires_at: string;
}

export interface AssessmentQuestionResponse {
  next_question_id?: string;
  next_question_text?: string;
  next_question_type?: 'multiple_choice' | 'yes_no' | 'text' | 'scale';
  next_question_context?: string;
  next_answer_options?: string[];
  progress: {
    current_question: number;
    total_questions_estimate: number;
    progress_percentage: number;
  };
  is_complete: boolean;
  session_token: string;
  answer_recorded: boolean;
  validation_errors?: string[];
}

export interface ComplianceGap {
  category: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  recommendation: string;
  estimated_effort: string;
  regulatory_impact: string;
}

export interface ComplianceRecommendation {
  priority: 'low' | 'medium' | 'high' | 'critical';
  category: string;
  title: string;
  description: string;
  implementation_guidance: string;
  estimated_cost: string;
  timeline: string;
  business_impact: string;
}

export interface AssessmentResultsResponse {
  session_id: string;
  lead_id?: string;
  framework_id?: string;
  session_token: string;
  compliance_score: number;
  risk_score: number;
  completion_percentage: number;
  results_summary: string;
  compliance_gaps: ComplianceGap[];
  recommendations: ComplianceRecommendation[];
  detailed_analysis: {
    strengths: string[];
    weaknesses: string[];
    critical_areas: string[];
    next_steps: string[];
  };
  conversion_cta: {
    primary_message: string;
    secondary_message: string;
    cta_button_text: string;
    urgency_indicator?: string;
  };
  results_generated_at: string;
  results_expire_at: string;
}

export interface LeadScoringResponse {
  event_id: string;
  score_applied: number;
  total_score: number;
  engagement_level: 'low' | 'medium' | 'high';
  conversion_probability: number;
  next_recommended_action: string;
  recorded_at: string;
}

// ============================================================================
// INTERNAL STATE TYPES
// ============================================================================

export interface AssessmentQuestion {
  question_id: string;
  question_text: string;
  question_type: 'multiple_choice' | 'yes_no' | 'text' | 'scale';
  question_context?: string;
  answer_options?: string[];
  is_required: boolean;
}

export interface AssessmentResponse {
  question_id: string;
  answer: AssessmentAnswer;
  answered_at: string;
  time_spent_seconds?: number;
  confidence_level?: number;
}

export interface AssessmentProgress {
  current_question: number;
  total_questions_estimate: number;
  progress_percentage: number;
  questions_answered: number;
  time_elapsed_seconds: number;
}

export interface FreemiumSession {
  session_id: string;
  session_token: string;
  lead_id: string;
  status: 'started' | 'in_progress' | 'completed' | 'abandoned';
  created_at: string;
  expires_at: string;
  last_activity_at?: string;
}

// ============================================================================
// STORE STATE TYPES
// ============================================================================

export interface FreemiumState {
  // Lead information
  leadId: string | null;
  email: string | null;
  leadScore: number;
  leadStatus: string;

  // Session management
  session: FreemiumSession | null;
  sessionToken: string | null;
  sessionExpiry: string | null;
  token: string | null; // Add for test compatibility

  // Assessment state
  currentQuestion: AssessmentQuestion | null;
  currentQuestionId: string | null; // Add for test compatibility
  responses: AssessmentResponse[];
  progress: AssessmentProgress;
  isAssessmentStarted: boolean;
  isAssessmentComplete: boolean;
  assessmentStarted: boolean; // Add for test compatibility
  assessmentCompleted: boolean; // Add for test compatibility

  // Results
  results: AssessmentResultsResponse | null;
  hasViewedResults: boolean;

  // UI state
  isLoading: boolean;
  error: string | null;

  // Consent and compliance
  hasMarketingConsent: boolean;
  hasNewsletterConsent: boolean;
  consentDate: string | null;
  consentMarketing: boolean; // Add for test compatibility
  consentTerms: boolean; // Add for test compatibility

  // Analytics and tracking
  timeStarted: string | null;
  totalTimeSpent: number;
  analyticsEvents: Array<{
    event_type: string;
    timestamp: string;
    metadata?: TrackingMetadata;
  }>;
  lastActivity: number | null; // Add for test compatibility

  // UTM parameters for test compatibility
  utmSource: string | null;
  utmCampaign: string | null;
  utmMedium: string | null;
  utmTerm: string | null;
  utmContent: string | null;

  // Computed properties for test compatibility
  isSessionExpired: boolean;
  canStartAssessment: boolean;
  hasValidSession: boolean;
  responseCount: number;
}

// ============================================================================
// STORE ACTIONS TYPES
// ============================================================================

export interface FreemiumActions {
  // Lead management
  captureLead: (leadData: LeadCaptureRequest) => Promise<void>;
  setLeadInfo: (leadId: string, email: string) => void;
  updateLeadScore: (score: number) => void;

  // Session management
  startAssessment: (startData: AssessmentStartRequest) => Promise<void>;
  loadSession: (sessionToken: string) => Promise<void>;
  clearSession: () => void;

  // Question flow
  submitAnswer: (answerData: AssessmentAnswerRequest) => Promise<void>;
  skipQuestion: () => void;
  goToPreviousQuestion: () => void;

  // Results
  generateResults: (includeDetails?: boolean) => Promise<void>;
  markResultsViewed: () => void;

  // Progress tracking
  updateProgress: (progress: Partial<AssessmentProgress>) => void;
  trackTimeSpent: (seconds: number) => void;

  // Consent management
  setMarketingConsent: (consent: boolean) => void;
  setNewsletterConsent: (consent: boolean) => void;
  updateConsent: (marketing: boolean, newsletter: boolean) => void;

  // Analytics
  trackEvent: (eventType: string, metadata?: TrackingMetadata) => void;
  recordBehavioralEvent: (eventData: FreemiumBehaviorEvent) => Promise<void>;

  // Utility methods
  isSessionExpired: () => boolean;
  canStartAssessment: () => boolean;
  hasValidSession: () => boolean;
  getCompletionPercentage: () => number;
  getResponseCount: () => number;

  // State management
  reset: (options?: { keepEmail?: boolean; keepUtm?: boolean }) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // Test compatibility methods
  setEmail: (email: string) => void;
  setToken: (token: string | null) => void;
  addResponse: (questionId: string, answer: string) => void;
  setConsent: (type: 'marketing' | 'terms', value: boolean) => void;
  setProgress: (progress: number) => void;
  markAssessmentStarted: () => void;
  markAssessmentCompleted: () => void;
  setUtmParams: (params: Record<string, string>) => void;
  setCurrentQuestion: (questionId: string | null) => void;
  updateLastActivity: () => void;
}

// ============================================================================
// API CLIENT TYPES
// ============================================================================

export interface FreemiumApiClient {
  captureLead: (data: LeadCaptureRequest) => Promise<LeadResponse>;
  startAssessment: (data: AssessmentStartRequest) => Promise<FreemiumAssessmentStartResponse>;
  submitAnswer: (data: AssessmentAnswerRequest) => Promise<AssessmentQuestionResponse>;
  generateResults: (data: ResultsGenerationRequest) => Promise<AssessmentResultsResponse>;
  recordEvent: (data: unknown) => Promise<LeadScoringResponse>;
}

// ============================================================================
// COMPONENT PROP TYPES
// ============================================================================

export interface FreemiumAssessmentFlowProps {
  initialQuestion?: AssessmentQuestion;
  onComplete?: (results: AssessmentResultsResponse) => void;
  onError?: (error: string) => void;
  className?: string;
}

export interface FreemiumResultsProps {
  results: AssessmentResultsResponse;
  onConversionClick?: () => void;
  showConversionCTA?: boolean;
  className?: string;
}

export interface LeadCaptureFormProps {
  onSubmit: (data: LeadCaptureRequest) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}

// ============================================================================
// UTILITY TYPES
// ============================================================================

export type AssessmentStatus = 'not_started' | 'in_progress' | 'completed' | 'expired' | 'error';

export type ConversionEvent =
  | 'email_captured'
  | 'assessment_started'
  | 'assessment_completed'
  | 'results_viewed'
  | 'cta_clicked'
  | 'converted_to_paid';

// ============================================================================
// ERROR TYPES
// ============================================================================

export interface FreemiumError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  timestamp: string;
}

export interface ValidationError {
  field: string;
  message: string;
  code: string;
}

// ============================================================================
// HEALTH STATUS TYPE
// ============================================================================

export interface HealthStatus {
  status: 'healthy' | 'unhealthy' | 'degraded';
  timestamp: string;
  version?: string;
  dependencies?: Record<string, 'healthy' | 'unhealthy' | 'degraded'>;
}

// ============================================================================
// EXPORT ALL TYPES
// ============================================================================

export type FreemiumStore = FreemiumState & FreemiumActions;
