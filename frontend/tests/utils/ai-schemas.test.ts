import { describe, it, expect } from 'vitest';
import {
  SeverityLevelSchema,
  PriorityLevelSchema,
  ImplementationEffortSchema,
  RiskLevelSchema,
  MaturityLevelSchema,
  TrendDirectionSchema,
  InsightTypeSchema,
  IntentTypeSchema,
  ExpectedAnswerTypeSchema,
  ValidationStatusSchema,
  ScoreSchema,
  PercentageSchema,
  GapSchema,
  GapAnalysisResponseSchema,
  RecommendationSchema,
  ValidationErrorSchema,
  SchemaValidationResultSchema,
  QuickConfidenceCheckSchema,
  AI_RESPONSE_SCHEMAS,
  validateAIResponse,
  validateStructuredResponse,
  getValidationErrors,
  isValidResponseType,
} from '@/lib/validations/ai-schemas';
import { z } from 'zod';

// ============================================================================
// Enum schemas
// ============================================================================

describe('SeverityLevelSchema', () => {
  it('accepts all valid values', () => {
    ['low', 'medium', 'high', 'critical'].forEach((v) => {
      expect(SeverityLevelSchema.safeParse(v).success).toBe(true);
    });
  });

  it('rejects invalid value', () => {
    expect(SeverityLevelSchema.safeParse('extreme').success).toBe(false);
  });
});

describe('PriorityLevelSchema', () => {
  it('accepts all valid values', () => {
    ['low', 'medium', 'high', 'urgent'].forEach((v) => {
      expect(PriorityLevelSchema.safeParse(v).success).toBe(true);
    });
  });

  it('rejects invalid value', () => {
    expect(PriorityLevelSchema.safeParse('critical').success).toBe(false);
  });
});

describe('ImplementationEffortSchema', () => {
  it('accepts all valid values', () => {
    ['minimal', 'low', 'medium', 'high', 'extensive'].forEach((v) => {
      expect(ImplementationEffortSchema.safeParse(v).success).toBe(true);
    });
  });

  it('rejects invalid value', () => {
    expect(ImplementationEffortSchema.safeParse('none').success).toBe(false);
  });
});

describe('RiskLevelSchema', () => {
  it('accepts all valid values', () => {
    ['low', 'medium', 'high', 'critical'].forEach((v) => {
      expect(RiskLevelSchema.safeParse(v).success).toBe(true);
    });
  });
});

describe('MaturityLevelSchema', () => {
  it('accepts all valid values', () => {
    ['initial', 'developing', 'defined', 'managed', 'optimized'].forEach((v) => {
      expect(MaturityLevelSchema.safeParse(v).success).toBe(true);
    });
  });

  it('rejects invalid value', () => {
    expect(MaturityLevelSchema.safeParse('advanced').success).toBe(false);
  });
});

describe('TrendDirectionSchema', () => {
  it('accepts all valid values', () => {
    ['improving', 'stable', 'declining'].forEach((v) => {
      expect(TrendDirectionSchema.safeParse(v).success).toBe(true);
    });
  });
});

describe('InsightTypeSchema', () => {
  it('accepts all valid values', () => {
    ['strength', 'weakness', 'opportunity', 'threat'].forEach((v) => {
      expect(InsightTypeSchema.safeParse(v).success).toBe(true);
    });
  });
});

describe('IntentTypeSchema', () => {
  it('accepts all valid values', () => {
    [
      'evidence_query',
      'compliance_check',
      'guidance_request',
      'general_query',
      'assessment_help',
    ].forEach((v) => {
      expect(IntentTypeSchema.safeParse(v).success).toBe(true);
    });
  });
});

describe('ExpectedAnswerTypeSchema', () => {
  it('accepts all valid values', () => {
    ['text', 'boolean', 'multiple_choice', 'numeric'].forEach((v) => {
      expect(ExpectedAnswerTypeSchema.safeParse(v).success).toBe(true);
    });
  });
});

describe('ValidationStatusSchema', () => {
  it('accepts all valid values', () => {
    ['valid', 'invalid', 'partially_valid'].forEach((v) => {
      expect(ValidationStatusSchema.safeParse(v).success).toBe(true);
    });
  });
});

// ============================================================================
// ScoreSchema and PercentageSchema
// ============================================================================

describe('ScoreSchema', () => {
  it('accepts 0', () => {
    expect(ScoreSchema.safeParse(0).success).toBe(true);
  });

  it('accepts 1', () => {
    expect(ScoreSchema.safeParse(1).success).toBe(true);
  });

  it('accepts 0.5', () => {
    expect(ScoreSchema.safeParse(0.5).success).toBe(true);
  });

  it('rejects below 0', () => {
    expect(ScoreSchema.safeParse(-0.1).success).toBe(false);
  });

  it('rejects above 1', () => {
    expect(ScoreSchema.safeParse(1.1).success).toBe(false);
  });

  it('rejects string', () => {
    expect(ScoreSchema.safeParse('0.5').success).toBe(false);
  });
});

describe('PercentageSchema', () => {
  it('accepts 0', () => {
    expect(PercentageSchema.safeParse(0).success).toBe(true);
  });

  it('accepts 100', () => {
    expect(PercentageSchema.safeParse(100).success).toBe(true);
  });

  it('accepts 55.5', () => {
    expect(PercentageSchema.safeParse(55.5).success).toBe(true);
  });

  it('rejects below 0', () => {
    expect(PercentageSchema.safeParse(-1).success).toBe(false);
  });

  it('rejects above 100', () => {
    expect(PercentageSchema.safeParse(101).success).toBe(false);
  });
});

// ============================================================================
// GapSchema
// ============================================================================

const validGap = {
  id: 'gap-001',
  title: 'Missing access control policy',
  description: 'The organisation lacks a formal access control policy document.',
  severity: 'high',
  category: 'Access Control',
  framework_reference: 'ISO 27001 A.9',
  current_state: 'No formal policy',
  target_state: 'Documented and enforced policy',
  impact_description: 'Unauthorized access risk',
  business_impact_score: 0.8,
  technical_complexity: 0.4,
  regulatory_requirement: true,
  estimated_effort: 'medium',
  dependencies: [],
  affected_systems: [],
  stakeholders: [],
};

describe('GapSchema', () => {
  it('accepts a valid gap object', () => {
    expect(GapSchema.safeParse(validGap).success).toBe(true);
  });

  it('rejects missing id', () => {
    const { id: _, ...noId } = validGap;
    expect(GapSchema.safeParse(noId).success).toBe(false);
  });

  it('rejects empty id', () => {
    expect(GapSchema.safeParse({ ...validGap, id: '' }).success).toBe(false);
  });

  it('rejects title longer than 200 chars', () => {
    expect(GapSchema.safeParse({ ...validGap, title: 'A'.repeat(201) }).success).toBe(false);
  });

  it('rejects description shorter than 10 chars', () => {
    expect(GapSchema.safeParse({ ...validGap, description: 'Short' }).success).toBe(false);
  });

  it('rejects invalid severity', () => {
    expect(GapSchema.safeParse({ ...validGap, severity: 'extreme' }).success).toBe(false);
  });

  it('rejects invalid estimated_effort', () => {
    expect(GapSchema.safeParse({ ...validGap, estimated_effort: 'none' }).success).toBe(false);
  });

  it('rejects business_impact_score > 1', () => {
    expect(GapSchema.safeParse({ ...validGap, business_impact_score: 1.5 }).success).toBe(false);
  });

  it('rejects non-boolean regulatory_requirement', () => {
    expect(GapSchema.safeParse({ ...validGap, regulatory_requirement: 'yes' }).success).toBe(false);
  });

  it('defaults dependencies to empty array when omitted', () => {
    const { dependencies: _, ...noDeps } = validGap;
    const result = GapSchema.safeParse(noDeps);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.dependencies).toEqual([]);
    }
  });
});

// ============================================================================
// GapAnalysisResponseSchema
// ============================================================================

const validGapAnalysis = {
  gaps: [validGap],
  overall_risk_level: 'high',
  priority_order: ['gap-001'],
  estimated_total_effort: '3 months',
  critical_gap_count: 0,
  medium_high_gap_count: 1,
  compliance_percentage: 45,
  framework_coverage: { 'ISO 27001': 45 },
  summary: 'The organisation has significant gaps in access control.',
  next_steps: ['Draft access control policy'],
};

describe('GapAnalysisResponseSchema', () => {
  it('accepts a valid gap analysis response', () => {
    expect(GapAnalysisResponseSchema.safeParse(validGapAnalysis).success).toBe(true);
  });

  it('rejects invalid overall_risk_level', () => {
    expect(
      GapAnalysisResponseSchema.safeParse({ ...validGapAnalysis, overall_risk_level: 'extreme' })
        .success,
    ).toBe(false);
  });

  it('rejects compliance_percentage > 100', () => {
    expect(
      GapAnalysisResponseSchema.safeParse({ ...validGapAnalysis, compliance_percentage: 150 })
        .success,
    ).toBe(false);
  });

  it('rejects critical_gap_count that is not an int >= 0', () => {
    expect(
      GapAnalysisResponseSchema.safeParse({ ...validGapAnalysis, critical_gap_count: -1 }).success,
    ).toBe(false);
  });

  it('rejects empty next_steps array', () => {
    expect(
      GapAnalysisResponseSchema.safeParse({ ...validGapAnalysis, next_steps: [] }).success,
    ).toBe(false);
  });

  it('rejects summary shorter than 10 chars', () => {
    expect(
      GapAnalysisResponseSchema.safeParse({ ...validGapAnalysis, summary: 'Too short' }).success,
    ).toBe(false);
  });

  it('defaults framework_coverage to empty object when omitted', () => {
    const { framework_coverage: _, ...noFc } = validGapAnalysis;
    const result = GapAnalysisResponseSchema.safeParse(noFc);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.framework_coverage).toEqual({});
    }
  });
});

// ============================================================================
// RecommendationSchema
// ============================================================================

const validRecommendation = {
  id: 'rec-001',
  title: 'Implement access control policy',
  description: 'Draft, approve, and enforce a formal access control policy.',
  priority: 'high',
  category: 'Policy',
  framework_references: ['ISO 27001 A.9'],
  effort_estimate: 'medium',
  implementation_timeline: '3 months',
  impact_score: 0.85,
  success_criteria: ['Policy approved by board'],
};

describe('RecommendationSchema', () => {
  it('accepts a valid recommendation', () => {
    expect(RecommendationSchema.safeParse(validRecommendation).success).toBe(true);
  });

  it('rejects empty framework_references', () => {
    expect(
      RecommendationSchema.safeParse({ ...validRecommendation, framework_references: [] }).success,
    ).toBe(false);
  });

  it('rejects empty success_criteria', () => {
    expect(
      RecommendationSchema.safeParse({ ...validRecommendation, success_criteria: [] }).success,
    ).toBe(false);
  });

  it('rejects invalid priority', () => {
    expect(
      RecommendationSchema.safeParse({ ...validRecommendation, priority: 'critical' }).success,
    ).toBe(false);
  });

  it('accepts optional cost_estimate', () => {
    expect(
      RecommendationSchema.safeParse({ ...validRecommendation, cost_estimate: '£5,000' }).success,
    ).toBe(true);
  });

  it('defaults automation_potential to 0 when omitted', () => {
    const result = RecommendationSchema.safeParse(validRecommendation);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.automation_potential).toBe(0);
    }
  });
});

// ============================================================================
// ValidationErrorSchema
// ============================================================================

describe('ValidationErrorSchema', () => {
  it('accepts a valid validation error', () => {
    expect(
      ValidationErrorSchema.safeParse({
        field_path: 'gaps[0].id',
        error_type: 'min_length',
        error_message: 'String must contain at least 1 character(s)',
        expected_type: 'string',
        actual_value: '',
      }).success,
    ).toBe(true);
  });

  it('accepts optional suggestion', () => {
    expect(
      ValidationErrorSchema.safeParse({
        field_path: 'gaps[0].id',
        error_type: 'min_length',
        error_message: 'String must contain at least 1 character(s)',
        expected_type: 'string',
        actual_value: '',
        suggestion: 'Provide a non-empty id',
      }).success,
    ).toBe(true);
  });

  it('rejects missing field_path', () => {
    expect(
      ValidationErrorSchema.safeParse({
        error_type: 'min_length',
        error_message: 'error',
        expected_type: 'string',
        actual_value: '',
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// SchemaValidationResultSchema
// ============================================================================

describe('SchemaValidationResultSchema', () => {
  it('accepts a valid schema validation result', () => {
    expect(
      SchemaValidationResultSchema.safeParse({
        is_valid: true,
        schema_name: 'GapAnalysisResponseSchema',
        validation_errors: [],
        validation_timestamp: '2024-01-01T00:00:00Z',
      }).success,
    ).toBe(true);
  });

  it('rejects non-boolean is_valid', () => {
    expect(
      SchemaValidationResultSchema.safeParse({
        is_valid: 'true',
        schema_name: 'GapSchema',
        validation_errors: [],
        validation_timestamp: '2024-01-01T00:00:00Z',
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// QuickConfidenceCheckSchema
// ============================================================================

describe('QuickConfidenceCheckSchema', () => {
  it('accepts all valid recommendations', () => {
    ['use_as_is', 'review_recommended', 'seek_expert_help'].forEach((rec) => {
      expect(
        QuickConfidenceCheckSchema.safeParse({
          confidence_score: 7,
          confidence_factors: ['Good source'],
          quick_issues: [],
          recommendation: rec,
        }).success,
      ).toBe(true);
    });
  });

  it('rejects confidence_score above 10', () => {
    expect(
      QuickConfidenceCheckSchema.safeParse({
        confidence_score: 11,
        confidence_factors: [],
        quick_issues: [],
        recommendation: 'use_as_is',
      }).success,
    ).toBe(false);
  });

  it('rejects invalid recommendation', () => {
    expect(
      QuickConfidenceCheckSchema.safeParse({
        confidence_score: 5,
        confidence_factors: [],
        quick_issues: [],
        recommendation: 'ignore',
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// AI_RESPONSE_SCHEMAS registry
// ============================================================================

describe('AI_RESPONSE_SCHEMAS', () => {
  it('has all expected schema keys', () => {
    const expectedKeys = [
      'gap_analysis',
      'recommendations',
      'assessment_analysis',
      'guidance',
      'followup',
      'intent_classification',
      'chat',
      'policy',
      'workflow',
      'self_review',
      'quick_confidence_check',
      'self_review_metrics',
    ];
    expectedKeys.forEach((key) => {
      expect(AI_RESPONSE_SCHEMAS).toHaveProperty(key);
    });
  });

  it('each schema has a safeParse method', () => {
    Object.values(AI_RESPONSE_SCHEMAS).forEach((schema) => {
      expect(typeof schema.safeParse).toBe('function');
    });
  });
});

// ============================================================================
// validateAIResponse
// ============================================================================

describe('validateAIResponse', () => {
  it('returns success=true for valid gap_analysis data', () => {
    const result = validateAIResponse(validGapAnalysis, 'gap_analysis');
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
  });

  it('returns success=false for invalid gap_analysis data', () => {
    const result = validateAIResponse({ gaps: 'not-an-array' }, 'gap_analysis');
    expect(result.success).toBe(false);
    expect(result.errors).toBeDefined();
    expect(result.errors!.length).toBeGreaterThan(0);
  });

  it('returns success=false for unknown response type', () => {
    const result = validateAIResponse({}, 'unknown_type' as any);
    expect(result.success).toBe(false);
  });

  it('returns validated data on success', () => {
    const result = validateAIResponse(validGapAnalysis, 'gap_analysis');
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data!.gaps).toHaveLength(1);
      expect(result.data!.overall_risk_level).toBe('high');
    }
  });
});

// ============================================================================
// validateStructuredResponse
// ============================================================================

const validStructuredResponse = {
  metadata: {
    response_id: 'resp-001',
    timestamp: '2024-01-01T00:00:00Z',
    model_used: 'gemini-pro',
    processing_time_ms: 1200,
    confidence_score: 0.9,
    schema_version: '1.0',
    validation_status: 'valid',
    validation_errors: [],
  },
  response_type: 'gap_analysis',
  payload: validGapAnalysis,
  validation_passed: true,
  fallback_used: false,
};

describe('validateStructuredResponse', () => {
  it('returns success=true for valid structured response', () => {
    const result = validateStructuredResponse(validStructuredResponse);
    expect(result.success).toBe(true);
  });

  it('returns success=false for missing metadata', () => {
    const { metadata: _, ...noMeta } = validStructuredResponse;
    const result = validateStructuredResponse(noMeta);
    expect(result.success).toBe(false);
  });

  it('returns success=false for invalid validation_status in metadata', () => {
    const result = validateStructuredResponse({
      ...validStructuredResponse,
      metadata: { ...validStructuredResponse.metadata, validation_status: 'unknown' },
    });
    expect(result.success).toBe(false);
  });

  it('defaults fallback_used to false when omitted', () => {
    const { fallback_used: _, ...noFallback } = validStructuredResponse;
    const result = validateStructuredResponse(noFallback);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data!.fallback_used).toBe(false);
    }
  });
});

// ============================================================================
// getValidationErrors
// ============================================================================

describe('getValidationErrors', () => {
  it('returns an array of error strings', () => {
    const schema = z.object({ name: z.string().min(2) });
    const result = schema.safeParse({ name: '' });
    expect(result.success).toBe(false);
    if (!result.success) {
      const errors = getValidationErrors(result.error);
      expect(Array.isArray(errors)).toBe(true);
      expect(errors.length).toBeGreaterThan(0);
      expect(typeof errors[0]).toBe('string');
    }
  });

  it('includes field path in error string', () => {
    const schema = z.object({ user: z.object({ email: z.string().email() }) });
    const result = schema.safeParse({ user: { email: 'not-an-email' } });
    if (!result.success) {
      const errors = getValidationErrors(result.error);
      expect(errors[0]).toContain('user.email');
    }
  });

  it('includes error message in error string', () => {
    const schema = z.object({ score: z.number().min(0) });
    const result = schema.safeParse({ score: -1 });
    if (!result.success) {
      const errors = getValidationErrors(result.error);
      expect(errors[0]).toContain('score');
    }
  });
});

// ============================================================================
// isValidResponseType
// ============================================================================

describe('isValidResponseType', () => {
  it('returns true for valid response types', () => {
    expect(isValidResponseType('gap_analysis')).toBe(true);
    expect(isValidResponseType('guidance')).toBe(true);
    expect(isValidResponseType('chat')).toBe(true);
    expect(isValidResponseType('quick_confidence_check')).toBe(true);
  });

  it('returns false for unknown types', () => {
    expect(isValidResponseType('unknown')).toBe(false);
    expect(isValidResponseType('')).toBe(false);
    expect(isValidResponseType('GAP_ANALYSIS')).toBe(false);
  });

  it('returns true for all registered schema keys', () => {
    Object.keys(AI_RESPONSE_SCHEMAS).forEach((key) => {
      expect(isValidResponseType(key)).toBe(true);
    });
  });
});
