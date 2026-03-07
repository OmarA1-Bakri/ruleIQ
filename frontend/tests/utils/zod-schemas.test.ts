import { describe, it, expect } from 'vitest';
import {
  BusinessProfileSchema,
  LeadCaptureRequestSchema,
  EvidenceItemSchema,
  ChatMessageSchema,
  ChatWebSocketMessageSchema,
  AIErrorSchema,
  HealthStatusSchema,
  ProgressSchema,
  APIErrorResponseSchema,
  AssessmentQuestionSchema,
  PersonalizationDataSchema,
  AssessmentAnswerSchema,
  AssessmentDataSchema,
  WizardStepSchema,
  IntegrationConfigSchema,
  FreemiumLeadResponseSchema,
  createTypeGuard,
  createValidatedParser,
  createSafeParser,
} from '@/lib/validation/zod-schemas';
import { z } from 'zod';

// ============================================================================
// BusinessProfileSchema
// ============================================================================

const validBusinessProfile = {
  company_name: 'Acme Corp',
  industry: 'Technology',
  employee_count: 50,
  country: 'United Kingdom',
  data_sensitivity: 'Moderate',
  data_types: ['personal_data'],
  handles_personal_data: true,
  processes_payments: false,
  stores_health_data: false,
  provides_financial_services: false,
  operates_critical_infrastructure: false,
  has_international_operations: false,
  cloud_providers: ['AWS'],
  saas_tools: [],
  development_tools: [],
  existing_frameworks: [],
  planned_frameworks: [],
  assessment_completed: false,
  assessment_data: {},
};

describe('BusinessProfileSchema', () => {
  it('accepts a valid business profile', () => {
    expect(BusinessProfileSchema.safeParse(validBusinessProfile).success).toBe(true);
  });

  it('rejects missing required company_name', () => {
    const { company_name: _, ...invalid } = validBusinessProfile;
    expect(BusinessProfileSchema.safeParse(invalid).success).toBe(false);
  });

  it('rejects invalid data_sensitivity', () => {
    expect(
      BusinessProfileSchema.safeParse({
        ...validBusinessProfile,
        data_sensitivity: 'VeryHigh',
      }).success,
    ).toBe(false);
  });

  it('accepts all valid data_sensitivity values', () => {
    ['Low', 'Moderate', 'High', 'Confidential'].forEach((v) => {
      expect(
        BusinessProfileSchema.safeParse({ ...validBusinessProfile, data_sensitivity: v }).success,
      ).toBe(true);
    });
  });

  it('accepts optional id and user_id', () => {
    expect(
      BusinessProfileSchema.safeParse({
        ...validBusinessProfile,
        id: 'profile-001',
        user_id: 'user-001',
      }).success,
    ).toBe(true);
  });

  it('rejects non-boolean handles_personal_data', () => {
    expect(
      BusinessProfileSchema.safeParse({
        ...validBusinessProfile,
        handles_personal_data: 'yes',
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// AssessmentDataSchema
// ============================================================================

describe('AssessmentDataSchema', () => {
  it('accepts empty object (all optional)', () => {
    expect(AssessmentDataSchema.safeParse({}).success).toBe(true);
  });

  it('accepts valid completion_status', () => {
    ['not_started', 'in_progress', 'completed'].forEach((status) => {
      expect(
        AssessmentDataSchema.safeParse({ completion_status: status }).success,
      ).toBe(true);
    });
  });

  it('rejects invalid completion_status', () => {
    expect(
      AssessmentDataSchema.safeParse({ completion_status: 'unknown' }).success,
    ).toBe(false);
  });

  it('accepts valid scores array', () => {
    expect(
      AssessmentDataSchema.safeParse({
        scores: [{ category: 'GDPR', score: 75, confidence: 0.9 }],
      }).success,
    ).toBe(true);
  });

  it('rejects score out of range', () => {
    expect(
      AssessmentDataSchema.safeParse({
        scores: [{ category: 'GDPR', score: 150, confidence: 0.9 }],
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// WizardStepSchema
// ============================================================================

describe('WizardStepSchema', () => {
  it('accepts valid wizard step', () => {
    expect(
      WizardStepSchema.safeParse({ id: 'step-1', title: 'Company Info', fields: ['name'] }).success,
    ).toBe(true);
  });

  it('rejects missing id', () => {
    expect(
      WizardStepSchema.safeParse({ title: 'Step', fields: [] }).success,
    ).toBe(false);
  });
});

// ============================================================================
// LeadCaptureRequestSchema
// ============================================================================

describe('LeadCaptureRequestSchema', () => {
  it('accepts minimal valid lead (email only)', () => {
    expect(LeadCaptureRequestSchema.safeParse({ email: 'user@example.com' }).success).toBe(true);
  });

  it('rejects invalid email', () => {
    expect(LeadCaptureRequestSchema.safeParse({ email: 'not-an-email' }).success).toBe(false);
  });

  it('accepts full lead with all optional fields', () => {
    expect(
      LeadCaptureRequestSchema.safeParse({
        email: 'user@example.com',
        first_name: 'Jane',
        last_name: 'Smith',
        company_name: 'Acme',
        company_size: '51-200',
        industry: 'Technology',
        newsletter_subscribed: true,
        marketing_consent: false,
      }).success,
    ).toBe(true);
  });
});

// ============================================================================
// AssessmentAnswerSchema
// ============================================================================

describe('AssessmentAnswerSchema', () => {
  it('accepts string answer', () => {
    expect(AssessmentAnswerSchema.safeParse('yes').success).toBe(true);
  });

  it('accepts number answer', () => {
    expect(AssessmentAnswerSchema.safeParse(42).success).toBe(true);
  });

  it('accepts boolean answer', () => {
    expect(AssessmentAnswerSchema.safeParse(true).success).toBe(true);
  });

  it('accepts array of strings', () => {
    expect(AssessmentAnswerSchema.safeParse(['option1', 'option2']).success).toBe(true);
  });

  it('accepts object with value and metadata', () => {
    expect(
      AssessmentAnswerSchema.safeParse({ value: 'something', metadata: { key: 'val' } }).success,
    ).toBe(true);
  });
});

// ============================================================================
// PersonalizationDataSchema
// ============================================================================

describe('PersonalizationDataSchema', () => {
  it('accepts empty object (all optional)', () => {
    expect(PersonalizationDataSchema.safeParse({}).success).toBe(true);
  });

  it('accepts valid business_size_category', () => {
    ['startup', 'small', 'medium', 'large', 'enterprise'].forEach((size) => {
      expect(
        PersonalizationDataSchema.safeParse({ business_size_category: size }).success,
      ).toBe(true);
    });
  });

  it('rejects invalid business_size_category', () => {
    expect(
      PersonalizationDataSchema.safeParse({ business_size_category: 'tiny' }).success,
    ).toBe(false);
  });
});

// ============================================================================
// EvidenceItemSchema
// ============================================================================

describe('EvidenceItemSchema', () => {
  const validEvidence = {
    id: 'ev-001',
    title: 'GDPR Policy Document',
    type: 'document',
    created_at: '2024-01-01T00:00:00Z',
  };

  it('accepts a valid evidence item', () => {
    expect(EvidenceItemSchema.safeParse(validEvidence).success).toBe(true);
  });

  it('accepts all valid evidence types', () => {
    ['document', 'policy', 'certificate', 'report', 'other', 'screenshot', 'log'].forEach(
      (type) => {
        expect(EvidenceItemSchema.safeParse({ ...validEvidence, type }).success).toBe(true);
      },
    );
  });

  it('rejects invalid evidence type', () => {
    expect(EvidenceItemSchema.safeParse({ ...validEvidence, type: 'video' }).success).toBe(false);
  });

  it('accepts optional status values', () => {
    ['pending', 'verified', 'rejected'].forEach((status) => {
      expect(EvidenceItemSchema.safeParse({ ...validEvidence, status }).success).toBe(true);
    });
  });

  it('rejects invalid status', () => {
    expect(EvidenceItemSchema.safeParse({ ...validEvidence, status: 'approved' }).success).toBe(false);
  });
});

// ============================================================================
// ChatMessageSchema
// ============================================================================

describe('ChatMessageSchema', () => {
  const validMessage = {
    id: 'msg-001',
    content: 'Hello world',
    role: 'user',
    timestamp: '2024-01-01T00:00:00Z',
  };

  it('accepts a valid chat message', () => {
    expect(ChatMessageSchema.safeParse(validMessage).success).toBe(true);
  });

  it('accepts all valid roles', () => {
    ['user', 'assistant', 'system'].forEach((role) => {
      expect(ChatMessageSchema.safeParse({ ...validMessage, role }).success).toBe(true);
    });
  });

  it('rejects invalid role', () => {
    expect(ChatMessageSchema.safeParse({ ...validMessage, role: 'admin' }).success).toBe(false);
  });

  it('accepts optional conversation_id', () => {
    expect(
      ChatMessageSchema.safeParse({ ...validMessage, conversation_id: 'conv-001' }).success,
    ).toBe(true);
  });
});

// ============================================================================
// ChatWebSocketMessageSchema
// ============================================================================

describe('ChatWebSocketMessageSchema', () => {
  it('accepts all valid types', () => {
    ['message', 'status', 'error', 'typing', 'acknowledgment'].forEach((type) => {
      expect(
        ChatWebSocketMessageSchema.safeParse({
          type,
          payload: 'anything',
          timestamp: '2024-01-01T00:00:00Z',
        }).success,
      ).toBe(true);
    });
  });

  it('rejects invalid type', () => {
    expect(
      ChatWebSocketMessageSchema.safeParse({
        type: 'unknown',
        payload: null,
        timestamp: '2024-01-01T00:00:00Z',
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// AIErrorSchema
// ============================================================================

describe('AIErrorSchema', () => {
  it('accepts all valid error types', () => {
    [
      'timeout',
      'quota_exceeded',
      'service_unavailable',
      'content_filtered',
      'parsing_error',
      'validation_error',
      'unknown_error',
    ].forEach((type) => {
      expect(
        AIErrorSchema.safeParse({ type, message: 'Error occurred', name: 'AIError' }).success,
      ).toBe(true);
    });
  });

  it('rejects invalid error type', () => {
    expect(
      AIErrorSchema.safeParse({ type: 'network_error', message: 'err', name: 'AIError' }).success,
    ).toBe(false);
  });

  it('accepts optional retryable field', () => {
    expect(
      AIErrorSchema.safeParse({
        type: 'timeout',
        message: 'Timed out',
        name: 'AIError',
        retryable: true,
      }).success,
    ).toBe(true);
  });
});

// ============================================================================
// HealthStatusSchema
// ============================================================================

describe('HealthStatusSchema', () => {
  it('accepts all valid statuses', () => {
    ['healthy', 'unhealthy', 'degraded'].forEach((status) => {
      expect(
        HealthStatusSchema.safeParse({
          status,
          timestamp: '2024-01-01T00:00:00Z',
        }).success,
      ).toBe(true);
    });
  });

  it('rejects invalid status', () => {
    expect(
      HealthStatusSchema.safeParse({ status: 'unknown', timestamp: '2024-01-01T00:00:00Z' }).success,
    ).toBe(false);
  });

  it('requires datetime timestamp', () => {
    expect(
      HealthStatusSchema.safeParse({ status: 'healthy', timestamp: '2024-01-01T00:00:00Z' }).success,
    ).toBe(true);
  });
});

// ============================================================================
// ProgressSchema
// ============================================================================

describe('ProgressSchema', () => {
  it('accepts valid progress', () => {
    expect(
      ProgressSchema.safeParse({
        current_question: 3,
        total_questions_estimate: 10,
        progress_percentage: 30,
      }).success,
    ).toBe(true);
  });

  it('rejects missing fields', () => {
    expect(ProgressSchema.safeParse({ current_question: 3 }).success).toBe(false);
  });
});

// ============================================================================
// APIErrorResponseSchema
// ============================================================================

describe('APIErrorResponseSchema', () => {
  it('accepts minimal error response', () => {
    expect(
      APIErrorResponseSchema.safeParse({ error: 'NOT_FOUND', message: 'Resource not found' }).success,
    ).toBe(true);
  });

  it('accepts full error response', () => {
    expect(
      APIErrorResponseSchema.safeParse({
        error: 'VALIDATION_ERROR',
        message: 'Invalid input',
        code: '400',
        request_id: 'req-001',
        statusCode: 400,
        timestamp: '2024-01-01T00:00:00Z',
      }).success,
    ).toBe(true);
  });

  it('rejects missing error field', () => {
    expect(APIErrorResponseSchema.safeParse({ message: 'Error' }).success).toBe(false);
  });
});

// ============================================================================
// AssessmentQuestionSchema
// ============================================================================

describe('AssessmentQuestionSchema', () => {
  it('accepts a valid question', () => {
    expect(
      AssessmentQuestionSchema.safeParse({
        id: 'q-001',
        text: 'Do you process personal data?',
        type: 'boolean',
        required: true,
      }).success,
    ).toBe(true);
  });

  it('accepts all valid question types', () => {
    ['multiple_choice', 'text', 'boolean', 'scale', 'matrix', 'file_upload', 'yes_no'].forEach(
      (type) => {
        expect(
          AssessmentQuestionSchema.safeParse({
            id: 'q-1',
            text: 'Question?',
            type,
            required: false,
          }).success,
        ).toBe(true);
      },
    );
  });

  it('rejects invalid question type', () => {
    expect(
      AssessmentQuestionSchema.safeParse({
        id: 'q-1',
        text: 'Question?',
        type: 'slider',
        required: true,
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// IntegrationConfigSchema
// ============================================================================

describe('IntegrationConfigSchema', () => {
  it('accepts valid config', () => {
    expect(
      IntegrationConfigSchema.safeParse({
        provider: 'github',
        settings: { scope: 'read' },
        enabled: true,
      }).success,
    ).toBe(true);
  });

  it('accepts all valid environments', () => {
    ['development', 'staging', 'production'].forEach((environment) => {
      expect(
        IntegrationConfigSchema.safeParse({
          provider: 'github',
          settings: {},
          enabled: true,
          environment,
        }).success,
      ).toBe(true);
    });
  });

  it('rejects missing provider', () => {
    expect(
      IntegrationConfigSchema.safeParse({ settings: {}, enabled: true }).success,
    ).toBe(false);
  });
});

// ============================================================================
// FreemiumLeadResponseSchema
// ============================================================================

describe('FreemiumLeadResponseSchema', () => {
  it('accepts valid lead response', () => {
    expect(
      FreemiumLeadResponseSchema.safeParse({
        id: '550e8400-e29b-41d4-a716-446655440000',
        email: 'user@example.com',
        created_at: '2024-01-01T00:00:00Z',
        token: 'tok_abc123',
      }).success,
    ).toBe(true);
  });

  it('rejects invalid UUID for id', () => {
    expect(
      FreemiumLeadResponseSchema.safeParse({
        id: 'not-a-uuid',
        email: 'user@example.com',
        created_at: '2024-01-01T00:00:00Z',
        token: 'tok_abc123',
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// createTypeGuard
// ============================================================================

describe('createTypeGuard', () => {
  it('returns true for valid data', () => {
    const isMessage = createTypeGuard(ChatMessageSchema);
    const valid = {
      id: 'msg-001',
      content: 'Hello',
      role: 'user',
      timestamp: '2024-01-01T00:00:00Z',
    };
    expect(isMessage(valid)).toBe(true);
  });

  it('returns false for invalid data', () => {
    const isMessage = createTypeGuard(ChatMessageSchema);
    expect(isMessage({ id: 'msg-001', role: 'admin' })).toBe(false);
  });

  it('works with simple schemas', () => {
    const isNumber = createTypeGuard(z.number().min(0));
    expect(isNumber(5)).toBe(true);
    expect(isNumber(-1)).toBe(false);
    expect(isNumber('5')).toBe(false);
  });
});

// ============================================================================
// createValidatedParser
// ============================================================================

describe('createValidatedParser', () => {
  it('returns parsed data for valid input', () => {
    const parseProgress = createValidatedParser(ProgressSchema);
    const result = parseProgress({
      current_question: 1,
      total_questions_estimate: 10,
      progress_percentage: 10,
    });
    expect(result.current_question).toBe(1);
  });

  it('throws for invalid input', () => {
    const parseProgress = createValidatedParser(ProgressSchema);
    expect(() => parseProgress({ current_question: 1 })).toThrow();
  });
});

// ============================================================================
// createSafeParser
// ============================================================================

describe('createSafeParser', () => {
  it('returns parsed data for valid input', () => {
    const safeParseProgress = createSafeParser(ProgressSchema);
    const result = safeParseProgress({
      current_question: 2,
      total_questions_estimate: 5,
      progress_percentage: 40,
    });
    expect(result).not.toBeNull();
    expect(result!.current_question).toBe(2);
  });

  it('returns null for invalid input', () => {
    const safeParseProgress = createSafeParser(ProgressSchema);
    const result = safeParseProgress({ invalid: true });
    expect(result).toBeNull();
  });

  it('does not throw for invalid input', () => {
    const safeParseProgress = createSafeParser(ProgressSchema);
    expect(() => safeParseProgress(null)).not.toThrow();
  });
});
