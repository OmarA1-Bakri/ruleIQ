/**
 * Zod validation schemas for all domain types
 * Provides runtime validation for API responses and data structures
 */

import { z } from 'zod';

// ============================================================================
// BUSINESS PROFILE SCHEMAS
// ============================================================================

export const AssessmentDataSchema = z.object({
  current_step: z.number().optional(),
  completed_steps: z.array(z.string()).optional(),
  answers: z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.array(z.string()), z.null()])).optional(),
  progress_percentage: z.number().optional(),
  last_updated: z.string().optional(),
  responses: z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.array(z.string())])).optional(),
  scores: z.array(z.object({
    category: z.string(),
    score: z.number().min(0).max(100),
    confidence: z.number().min(0).max(1),
  })).optional(),
  completion_status: z.enum(['not_started', 'in_progress', 'completed']).optional(),
});

export type AssessmentData = z.infer<typeof AssessmentDataSchema>;

export const BusinessProfileSchema = z.object({
  id: z.string().optional(),
  user_id: z.string().optional(),
  company_name: z.string(),
  industry: z.string(),
  employee_count: z.number(),
  annual_revenue: z.string().optional(),
  country: z.string(),
  data_sensitivity: z.enum(['Low', 'Moderate', 'High', 'Confidential']),
  data_types: z.array(z.string()),
  handles_personal_data: z.boolean(),
  processes_payments: z.boolean(),
  stores_health_data: z.boolean(),
  provides_financial_services: z.boolean(),
  operates_critical_infrastructure: z.boolean(),
  has_international_operations: z.boolean(),
  cloud_providers: z.array(z.string()),
  saas_tools: z.array(z.string()),
  development_tools: z.array(z.string()),
  existing_frameworks: z.array(z.string()),
  planned_frameworks: z.array(z.string()),
  compliance_budget: z.string().optional(),
  compliance_timeline: z.string().optional(),
  assessment_completed: z.boolean(),
  assessment_data: AssessmentDataSchema,
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
});

export type BusinessProfile = z.infer<typeof BusinessProfileSchema>;

export const ValidationSchemaSchema = z.object({
  required: z.boolean().optional(),
  minLength: z.number().optional(),
  maxLength: z.number().optional(),
  pattern: z.string().optional(),
  min: z.number().optional(),
  max: z.number().optional(),
  enum: z.array(z.string()).optional(),
  custom: z.function().args(z.unknown()).returns(z.union([z.string(), z.null()])).optional(),
});

export type ValidationSchema = z.infer<typeof ValidationSchemaSchema>;

export const WizardStepSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string().optional(),
  fields: z.array(z.string()),
  validation: ValidationSchemaSchema.optional(),
  completed: z.boolean().optional(),
  required: z.boolean().optional(),
});

export type WizardStep = z.infer<typeof WizardStepSchema>;

// ============================================================================
// FREEMIUM SCHEMAS
// ============================================================================

export const PersonalizationDataSchema = z.object({
  user_type: z.string().optional(),
  priority_areas: z.array(z.string()).optional(),
  current_challenges: z.array(z.string()).optional(),
  tech_stack: z.array(z.string()).optional(),
  budget_range: z.string().optional(),
  timeline: z.string().optional(),
  industry_preferences: z.array(z.string()).optional(),
  framework_focus: z.array(z.string()).optional(),
  business_size_category: z.enum(['startup', 'small', 'medium', 'large', 'enterprise']).optional(),
  custom_settings: z.record(z.string(), z.unknown()).optional(),
});

export type PersonalizationData = z.infer<typeof PersonalizationDataSchema>;

export const AssessmentAnswerSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.array(z.string()),
  z.object({
    value: z.unknown(),
    metadata: z.record(z.string(), z.unknown()).optional(),
  }),
]);

export type AssessmentAnswer = z.infer<typeof AssessmentAnswerSchema>;

export const LeadCaptureRequestSchema = z.object({
  email: z.string().email(),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  company_name: z.string().optional(),
  company_size: z.string().optional(),
  industry: z.string().optional(),
  phone: z.string().optional(),
  newsletter_subscribed: z.boolean().optional(),
  marketing_consent: z.boolean().optional(),
  utm_source: z.string().optional(),
  utm_medium: z.string().optional(),
  utm_campaign: z.string().optional(),
  utm_term: z.string().optional(),
  utm_content: z.string().optional(),
  referrer_url: z.string().optional(),
  landing_page: z.string().optional(),
  user_agent: z.string().optional(),
  ip_address: z.string().optional(),
  role: z.string().optional(),
});

export const AssessmentStartRequestSchema = z.object({
  lead_id: z.string(),
  business_type: z.string(),
  company_size: z.string().optional(),
  industry: z.string().optional(),
  compliance_frameworks: z.array(z.string()).optional(),
  personalization_data: PersonalizationDataSchema.optional(),
  assessment_type: z.string().optional(),
});

export const AssessmentAnswerRequestSchema = z.object({
  session_token: z.string(),
  question_id: z.string(),
  answer: AssessmentAnswerSchema,
  time_spent_seconds: z.number().optional(),
  confidence_level: z.number().optional(),
  session_id: z.string().optional(),
  time_spent: z.number().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export const CompleteAssessmentRequestSchema = z.object({
  completed_at: z.string(),
  answers: z.array(z.object({
    question_id: z.string(),
    value: z.any().refine((val) => {
      // Ensure no File or Blob objects are in the value
      if (val instanceof File || val instanceof Blob) return false;
      if (Array.isArray(val)) {
        return !val.some(item => item instanceof File || item instanceof Blob);
      }
      return true;
    }, "File objects must be serialized before submission"),
  })),
  section_scores: z.record(z.string(), z.number().min(0).max(100)),
  overall_score: z.number().min(0).max(100),
  compliance_score: z.number().min(0).max(100).optional(),
  risk_score: z.number().nullable().optional(),
  metadata: z.object({
    framework_id: z.string(),
    completion_time: z.number(),
    user_agent: z.string(),
  }),
});

export const ProgressSchema = z.object({
  current_question: z.number(),
  total_questions_estimate: z.number(),
  progress_percentage: z.number(),
});

export const FreemiumAssessmentStartResponseSchema = z.object({
  session_id: z.string(),
  session_token: z.string(),
  question_id: z.string(),
  question_text: z.string(),
  question_type: z.enum(['multiple_choice', 'yes_no', 'text', 'scale']),
  question_context: z.string().optional(),
  answer_options: z.array(z.string()).optional(),
  is_required: z.boolean().optional(),
  progress: ProgressSchema,
  personalization_applied: z.boolean(),
  expires_at: z.string(),
});

export const AssessmentQuestionResponseSchema = z.object({
  next_question_id: z.string().optional(),
  next_question_text: z.string().optional(),
  next_question_type: z.enum(['multiple_choice', 'yes_no', 'text', 'scale']).optional(),
  next_question_context: z.string().optional(),
  next_answer_options: z.array(z.string()).optional(),
  progress: ProgressSchema,
  is_complete: z.boolean(),
  session_token: z.string(),
  answer_recorded: z.boolean(),
  validation_errors: z.array(z.string()).optional(),
});

export const LeadResponseSchema = z.object({
  lead_id: z.string(),
  email: z.string(),
  lead_score: z.number(),
  lead_status: z.string(),
  message: z.string(),
  created_at: z.string(),
});

export const AssessmentResponseSchema = z.object({
  question_id: z.string(),
  question_text: z.string(),
  answer: AssessmentAnswerSchema,
  confidence_level: z.number().optional(),
  time_spent_seconds: z.number().optional(),
});

export const TrackingMetadataSchema = z.object({
  timestamp: z.string(),
  page_url: z.string().optional(),
  referrer: z.string().optional(),
  session_id: z.string().optional(),
  user_agent: z.string().optional(),
  custom_properties: z.record(z.string(), z.unknown()).optional(),
});

export type TrackingMetadata = z.infer<typeof TrackingMetadataSchema>;

export const FreemiumBehaviorEventSchema = z.object({
  event_type: z.string(),
  event_category: z.string().optional(),
  event_label: z.string().optional(),
  event_value: z.number().optional(),
  metadata: TrackingMetadataSchema.optional(),
});

export type FreemiumBehaviorEvent = z.infer<typeof FreemiumBehaviorEventSchema>;

// ============================================================================
// AI SCHEMAS
// ============================================================================

export const AssessmentAnswersSchema = z.record(
  z.string(),
  z.union([z.string(), z.number(), z.boolean(), z.array(z.string()), z.null()])
);

export type AssessmentAnswers = z.infer<typeof AssessmentAnswersSchema>;

export const AIErrorContextSchema = z.object({
  endpoint: z.string().optional(),
  request_id: z.string().optional(),
  timestamp: z.string().optional(),
  user_action: z.string().optional(),
  additional_info: z.record(z.string(), z.unknown()).optional(),
  user_id: z.string().optional(),
  session_id: z.string().optional(),
  error_code: z.string().optional(),
});

export type AIErrorContext = z.infer<typeof AIErrorContextSchema>;

export const QuestionMetadataSchema = z.object({
  category: z.string().optional(),
  weight: z.number().optional(),
  dependencies: z.array(z.string()).optional(),
  validation_rules: z.record(z.string(), z.unknown()).optional(),
  display_conditions: z.record(z.string(), z.unknown()).optional(),
  difficulty: z.enum(['easy', 'medium', 'hard']).optional(),
  estimated_time: z.number().optional(),
  tags: z.array(z.string()).optional(),
  scoring_weight: z.number().optional(),
});

export type QuestionMetadata = z.infer<typeof QuestionMetadataSchema>;

export const UserContextSchema = z.object({
  business_profile: BusinessProfileSchema.partial().optional(),
  current_answers: AssessmentAnswersSchema.optional(),
  assessment_progress: z.object({
    current_step: z.number().optional(),
    total_steps: z.number().optional(),
    completed_sections: z.array(z.string()).optional(),
  }).partial().optional(),
});

export const AIErrorSchema = z.object({
  type: z.enum([
    'timeout',
    'quota_exceeded',
    'service_unavailable',
    'content_filtered',
    'parsing_error',
    'validation_error',
    'unknown_error'
  ]),
  code: z.string().optional(),
  context: AIErrorContextSchema.optional(),
  retryable: z.boolean().optional(),
  message: z.string(),
  name: z.string(),
});

export const AIResponseMetadataSchema = z.object({
  confidence_score: z.number(),
  response_time_ms: z.number(),
  model_used: z.string(),
  cached: z.boolean(),
  tokens_used: z.number().optional(),
  cost_estimate: z.number().optional(),
});

export const BaseAIResponseSchema = z.object({
  metadata: AIResponseMetadataSchema,
  request_id: z.string(),
  generated_at: z.string(),
});

export const AIHelpResponseSchema = BaseAIResponseSchema.extend({
  guidance: z.string(),
  related_topics: z.array(z.string()).optional(),
  follow_up_suggestions: z.array(z.string()).optional(),
  source_references: z.array(z.string()).optional(),
  explanation: z.string().optional(),
  examples: z.array(z.string()).optional(),
  relevant_regulations: z.array(z.string()).optional(),
  suggested_answer: z.string().optional(),
  confidence: z.number().min(0).max(1).optional(),
});

export const AIFollowUpQuestionSchema = z.object({
  id: z.string(),
  text: z.string(),
  type: z.enum(['radio', 'checkbox', 'text', 'textarea', 'scale']),
  options: z.array(z.object({
    value: z.string(),
    label: z.string(),
    description: z.string().optional(),
  })).optional(),
  reasoning: z.string(),
  priority: z.enum(['high', 'medium', 'low']),
  metadata: QuestionMetadataSchema.optional(),
});

// ============================================================================
// CHAT SCHEMAS
// ============================================================================

export const ChatMessageMetadataSchema = z.object({
  source: z.string().optional(),
  confidence: z.number().optional(),
  processing_time: z.number().optional(),
  tokens_used: z.number().optional(),
  references: z.array(z.string()).optional(),
  actions: z.array(z.object({
    type: z.string(),
    label: z.string(),
    data: z.record(z.string(), z.unknown()),
  })).optional(),
});

export type ChatMessageMetadata = z.infer<typeof ChatMessageMetadataSchema>;

// Additional Freemium Response Schemas
export const FreemiumLeadResponseSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  company_name: z.string().optional(),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  role: z.string().optional(),
  company_size: z.string().optional(),
  industry: z.string().optional(),
  created_at: z.string().datetime(),
  token: z.string(),
  session_id: z.string().uuid().optional(),
});

export const AdvancedAssessmentStartResponseSchema = z.object({
  session_id: z.string().uuid(),
  lead_id: z.string().uuid(),
  assessment_type: z.string(),
  current_question: z.lazy(() => AssessmentQuestionSchema),
  current_question_index: z.number().int().nonnegative(),
  total_questions: z.number().int().positive(),
  progress_percentage: z.number().min(0).max(100),
  created_at: z.string().datetime(),
});

export const AdvancedQuestionResponseSchema = z.object({
  question: z.lazy(() => AssessmentQuestionSchema),
  next_question_index: z.number().int().nonnegative().optional(),
  is_last_question: z.boolean(),
  progress_percentage: z.number().min(0).max(100),
  session_id: z.string().uuid(),
});

export const AssessmentResultsResponseSchema = z.object({
  session_id: z.string().uuid(),
  lead_id: z.string().optional(),
  session_token: z.string(),
  compliance_score: z.number().min(0).max(100),
  risk_score: z.number().min(0).max(100),
  completion_percentage: z.number().min(0).max(100),
  results_summary: z.string(),
  compliance_gaps: z.array(z.object({
    area: z.string(),
    requirement: z.string(),
    current_state: z.string(),
    target_state: z.string(),
    action_required: z.string(),
    priority: z.enum(['low', 'medium', 'high', 'critical']),
  })),
  recommendations: z.array(z.object({
    title: z.string(),
    description: z.string(),
    priority: z.enum(['low', 'medium', 'high', 'critical']),
    estimated_effort: z.string().optional(),
  })),
  detailed_analysis: z.object({
    strengths: z.array(z.string()),
    weaknesses: z.array(z.string()),
    critical_areas: z.array(z.string()),
    next_steps: z.array(z.string()),
  }),
  conversion_cta: z.object({
    primary_message: z.string(),
    secondary_message: z.string(),
    cta_button_text: z.string(),
    urgency_indicator: z.string().optional(),
  }),
  results_generated_at: z.string().datetime(),
  results_expire_at: z.string().datetime(),
});

export const HealthStatusSchema = z.object({
  status: z.enum(['healthy', 'unhealthy', 'degraded']),
  timestamp: z.string().datetime(),
  version: z.string().optional(),
  dependencies: z.record(z.string(), z.enum(['healthy', 'unhealthy', 'degraded'])).optional(),
});

export const ChatMessageSchema = z.object({
  id: z.string(),
  content: z.string(),
  role: z.enum(['user', 'assistant', 'system']),
  timestamp: z.string(),
  metadata: ChatMessageMetadataSchema.optional(),
  conversation_id: z.string().optional(),
  created_at: z.string().optional(),
});

export const ChatWebSocketMessageSchema = z.object({
  type: z.enum(['message', 'status', 'error', 'typing', 'acknowledgment']),
  payload: z.unknown(),
  timestamp: z.string(),
  id: z.string().optional(),
});

// ============================================================================
// EVIDENCE SCHEMAS
// ============================================================================

export const EvidenceItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  type: z.enum(['document', 'policy', 'certificate', 'report', 'other', 'screenshot', 'log']),
  file_path: z.string().optional(),
  url: z.string().optional(),
  description: z.string().optional(),
  tags: z.array(z.string()).optional(),
  created_at: z.string(),
  updated_at: z.string().optional(),
  verified: z.boolean().optional(),
  verification_date: z.string().optional(),
  expiry_date: z.string().optional(),
  uploaded_at: z.string().optional(),
  uploaded_by: z.string().optional(),
  metadata: z.object({
    file_size: z.number().optional(),
    file_type: z.string().optional(),
    upload_date: z.string().optional(),
    verified_by: z.string().optional(),
    verification_date: z.string().optional(),
    tags: z.array(z.string()).optional(),
    source: z.string().optional(),
  }).optional(),
  status: z.enum(['pending', 'verified', 'rejected']).optional(),
});

export type EvidenceItem = z.infer<typeof EvidenceItemSchema>;

// ============================================================================
// API SCHEMAS
// ============================================================================

export const PolicyContentStructureSchema = z.union([
  z.object({
    type: z.literal('markdown'),
    content: z.string(),
  }),
  z.object({
    type: z.literal('sections'),
    sections: z.array(z.object({
      id: z.string(),
      title: z.string(),
      content: z.string(),
      order: z.number(),
    })),
    metadata: z.object({
      version: z.string(),
      last_updated: z.string(),
      approved_by: z.string().optional(),
    }).optional(),
  }),
  z.object({
    type: z.literal('template'),
    template_id: z.string(),
    variables: z.record(z.string(), z.unknown()),
  }),
]);

export type PolicyContentStructure = z.infer<typeof PolicyContentStructureSchema>;

export const QuestionValidationRulesSchema = z.object({
  required: z.boolean().optional(),
  min_length: z.number().optional(),
  max_length: z.number().optional(),
  pattern: z.string().optional(),
  custom_validator: z.string().optional(),
  depends_on: z.array(z.object({
    question_id: z.string(),
    condition: z.string(),
    value: z.unknown(),
  })).optional(),
  error_messages: z.record(z.string(), z.string()).optional(),
});

export type QuestionValidationRules = z.infer<typeof QuestionValidationRulesSchema>;

export const IntegrationConfigSchema = z.object({
  provider: z.string(),
  api_key: z.string().optional(),
  api_secret: z.string().optional(),
  webhook_url: z.string().optional(),
  settings: z.record(z.string(), z.unknown()),
  enabled: z.boolean(),
  last_sync: z.string().optional(),
  environment: z.enum(['development', 'staging', 'production']).optional(),
  custom_fields: z.record(z.string(), z.unknown()).optional(),
});

export type IntegrationConfig = z.infer<typeof IntegrationConfigSchema>;

export const AlertDetailsSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('compliance'),
    framework: z.string(),
    requirement: z.string(),
    deadline: z.string().optional(),
    severity: z.enum(['low', 'medium', 'high', 'critical']),
  }),
  z.object({
    type: z.literal('system'),
    component: z.string(),
    message: z.string(),
    severity: z.enum(['info', 'warning', 'error']),
  }),
  z.object({
    type: z.literal('security'),
    threat_type: z.string(),
    affected_assets: z.array(z.string()),
    severity: z.enum(['low', 'medium', 'high', 'critical']),
    remediation: z.string().optional(),
  }),
]);

export type AlertDetails = z.infer<typeof AlertDetailsSchema>;

export const APIErrorResponseSchema = z.object({
  error: z.string(),
  message: z.string(),
  code: z.string().optional(),
  details: z.record(z.string(), z.unknown()).optional(),
  request_id: z.string().optional(),
  statusCode: z.number().optional(),
  timestamp: z.string().optional(),
});

export type APIErrorResponse = z.infer<typeof APIErrorResponseSchema>;

export const ApiResponseSchema = <T extends z.ZodType>(dataSchema: T) => z.object({
  success: z.boolean(),
  data: dataSchema.optional(),
  error: z.string().optional(),
  message: z.string().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export const PaginatedResponseSchema = <T extends z.ZodType>(itemSchema: T) => z.object({
  items: z.array(itemSchema),
  total: z.number(),
  page: z.number(),
  per_page: z.number(),
  has_next: z.boolean(),
  has_previous: z.boolean(),
});

// ============================================================================
// HEALTH CHECK SCHEMA
// ============================================================================

export const DetailedHealthStatusSchema = z.object({
  status: z.enum(['healthy', 'degraded', 'unhealthy']),
  version: z.string().optional(),
  timestamp: z.string(),
  checks: z.record(z.string(), z.object({
    status: z.enum(['ok', 'warning', 'error']),
    message: z.string().optional(),
    latency_ms: z.number().optional(),
  })).optional(),
});

export type DetailedHealthStatus = z.infer<typeof DetailedHealthStatusSchema>;

// ============================================================================
// Additional Types from existing schemas
// ============================================================================

export const ComplianceRequirementSchema = z.object({
  id: z.string(),
  framework: z.string(),
  requirement_id: z.string(),
  title: z.string(),
  description: z.string(),
  category: z.string(),
  priority: z.enum(['low', 'medium', 'high', 'critical']),
  evidence_required: z.array(z.string()).optional(),
  validation_rules: QuestionValidationRulesSchema.optional(),
});

export const AssessmentQuestionSchema = z.object({
  id: z.string(),
  text: z.string(),
  type: z.enum(['multiple_choice', 'text', 'boolean', 'scale', 'matrix', 'file_upload', 'yes_no']),
  category: z.string().optional(),
  required: z.boolean(),
  options: z.array(z.object({
    value: z.string(),
    label: z.string(),
    score: z.number().optional(),
  })).optional(),
  validation_rules: QuestionValidationRulesSchema.optional(),
  help_text: z.string().optional(),
  metadata: QuestionMetadataSchema.optional(),
});

export const PolicyDocumentSchema = z.object({
  id: z.string(),
  title: z.string(),
  type: z.string(),
  version: z.string(),
  status: z.enum(['draft', 'review', 'approved', 'published', 'archived']),
  content: z.union([z.string(), PolicyContentStructureSchema]),
  created_at: z.string(),
  updated_at: z.string(),
  created_by: z.string(),
  approved_by: z.string().optional(),
  approval_date: z.string().optional(),
  next_review_date: z.string().optional(),
  tags: z.array(z.string()).optional(),
});

export const IntegrationSchema = z.object({
  id: z.string(),
  name: z.string(),
  provider: z.string(),
  status: z.enum(['active', 'inactive', 'error', 'pending']),
  config: IntegrationConfigSchema,
  last_sync: z.string().optional(),
  error_message: z.string().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const AlertSchema = z.object({
  id: z.string(),
  type: z.enum(['compliance', 'security', 'system', 'user']),
  severity: z.enum(['info', 'warning', 'error', 'critical']),
  title: z.string(),
  message: z.string(),
  details: AlertDetailsSchema,
  acknowledged: z.boolean(),
  acknowledged_by: z.string().optional(),
  acknowledged_at: z.string().optional(),
  created_at: z.string(),
  resolved_at: z.string().optional(),
});

// ============================================================================
// TYPE GUARD HELPERS
// ============================================================================

export const createTypeGuard = <T>(schema: z.ZodType<T>) => (value: unknown): value is T => {
  return schema.safeParse(value).success;
};

export const createValidatedParser = <T>(schema: z.ZodType<T>) => (value: unknown): T => {
  return schema.parse(value);
};

export const createSafeParser = <T>(schema: z.ZodType<T>) => (value: unknown): T | null => {
  const result = schema.safeParse(value);
  return result.success ? result.data : null;
};

// ============================================================================
// Type exports
// ============================================================================

export type LeadCaptureRequest = z.infer<typeof LeadCaptureRequestSchema>;
export type AssessmentStartRequest = z.infer<typeof AssessmentStartRequestSchema>;
export type AssessmentAnswerRequest = z.infer<typeof AssessmentAnswerRequestSchema>;
export type CompleteAssessmentRequest = z.infer<typeof CompleteAssessmentRequestSchema>;
export type FreemiumAssessmentResponse = z.infer<typeof FreemiumAssessmentStartResponseSchema>;
export type AssessmentQuestionResponse = z.infer<typeof AssessmentQuestionResponseSchema>;
export type LeadResponse = z.infer<typeof LeadResponseSchema>;
export type FreemiumLeadResponse = z.infer<typeof FreemiumLeadResponseSchema>;
export type UserContext = z.infer<typeof UserContextSchema>;
export type AIError = z.infer<typeof AIErrorSchema>;
export type BaseAIResponse = z.infer<typeof BaseAIResponseSchema>;
export type AIHelpResponse = z.infer<typeof AIHelpResponseSchema>;
export type AIFollowUpQuestion = z.infer<typeof AIFollowUpQuestionSchema>;
export type ChatMessage = z.infer<typeof ChatMessageSchema>;
export type ChatWebSocketMessage = z.infer<typeof ChatWebSocketMessageSchema>;
export type ComplianceRequirement = z.infer<typeof ComplianceRequirementSchema>;
export type AssessmentQuestion = z.infer<typeof AssessmentQuestionSchema>;
export type PolicyDocument = z.infer<typeof PolicyDocumentSchema>;
export type Integration = z.infer<typeof IntegrationSchema>;
export type Alert = z.infer<typeof AlertSchema>;