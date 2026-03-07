import { describe, it, expect } from 'vitest';
import {
  AssessmentSchema,
  AssessmentsArraySchema,
  EvidenceItemSchema,
  EvidenceArraySchema,
  WidgetConfigSchema,
  WidgetsArraySchema,
  MetricsSchema,
  FrameworkSchema,
  FrameworksArraySchema,
  LoadingStateSchema,
  safeValidate,
} from '@/lib/stores/schemas';

// ============================================================================
// AssessmentSchema
// ============================================================================

describe('AssessmentSchema', () => {
  const validAssessment = {
    id: 'a1',
    name: 'GDPR Assessment',
    status: 'draft' as const,
    framework_id: 'f1',
    business_profile_id: 'bp1',
  };

  it('parses a valid minimal assessment', () => {
    const result = AssessmentSchema.safeParse(validAssessment);
    expect(result.success).toBe(true);
  });

  it('accepts all valid status values', () => {
    const statuses = ['draft', 'in_progress', 'completed', 'expired'];
    statuses.forEach((status) => {
      const result = AssessmentSchema.safeParse({ ...validAssessment, status });
      expect(result.success).toBe(true);
    });
  });

  it('rejects invalid status', () => {
    const result = AssessmentSchema.safeParse({ ...validAssessment, status: 'archived' });
    expect(result.success).toBe(false);
  });

  it('rejects empty id', () => {
    const result = AssessmentSchema.safeParse({ ...validAssessment, id: '' });
    expect(result.success).toBe(false);
  });

  it('rejects empty name', () => {
    const result = AssessmentSchema.safeParse({ ...validAssessment, name: '' });
    expect(result.success).toBe(false);
  });

  it('accepts optional numeric fields', () => {
    const result = AssessmentSchema.safeParse({
      ...validAssessment,
      total_questions: 50,
      answered_questions: 20,
      score: 75.5,
    });
    expect(result.success).toBe(true);
  });

  it('rejects score > 100', () => {
    const result = AssessmentSchema.safeParse({ ...validAssessment, score: 101 });
    expect(result.success).toBe(false);
  });

  it('rejects score < 0', () => {
    const result = AssessmentSchema.safeParse({ ...validAssessment, score: -1 });
    expect(result.success).toBe(false);
  });

  it('rejects non-integer total_questions', () => {
    const result = AssessmentSchema.safeParse({ ...validAssessment, total_questions: 5.5 });
    expect(result.success).toBe(false);
  });

  it('accepts optional datetime fields', () => {
    const result = AssessmentSchema.safeParse({
      ...validAssessment,
      created_at: '2024-01-01T00:00:00.000Z',
      updated_at: '2024-06-01T12:00:00.000Z',
    });
    expect(result.success).toBe(true);
  });
});

describe('AssessmentsArraySchema', () => {
  it('parses an array of assessments', () => {
    const result = AssessmentsArraySchema.safeParse([
      { id: 'a1', name: 'Test', status: 'draft', framework_id: 'f1', business_profile_id: 'bp1' },
    ]);
    expect(result.success).toBe(true);
  });

  it('parses an empty array', () => {
    expect(AssessmentsArraySchema.safeParse([]).success).toBe(true);
  });

  it('rejects non-array input', () => {
    expect(AssessmentsArraySchema.safeParse('not-an-array').success).toBe(false);
  });
});

// ============================================================================
// EvidenceItemSchema
// ============================================================================

describe('EvidenceItemSchema', () => {
  const validEvidence = {
    id: 'e1',
    title: 'Access Control Policy',
    description: 'Policy document',
    control_id: 'c1',
    framework_id: 'f1',
    business_profile_id: 'bp1',
    evidence_type: 'document',
    source: 'internal',
    tags: [],
    status: 'pending' as const,
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
  };

  it('parses a valid evidence item', () => {
    expect(EvidenceItemSchema.safeParse(validEvidence).success).toBe(true);
  });

  it('accepts all valid status values', () => {
    const statuses = ['pending', 'collected', 'approved', 'rejected', 'needs_review'];
    statuses.forEach((status) => {
      expect(EvidenceItemSchema.safeParse({ ...validEvidence, status }).success).toBe(true);
    });
  });

  it('rejects invalid status', () => {
    expect(EvidenceItemSchema.safeParse({ ...validEvidence, status: 'archived' }).success).toBe(false);
  });

  it('accepts optional quality_score 0-100', () => {
    expect(EvidenceItemSchema.safeParse({ ...validEvidence, quality_score: 85 }).success).toBe(true);
    expect(EvidenceItemSchema.safeParse({ ...validEvidence, quality_score: 0 }).success).toBe(true);
    expect(EvidenceItemSchema.safeParse({ ...validEvidence, quality_score: 100 }).success).toBe(true);
  });

  it('rejects quality_score > 100', () => {
    expect(EvidenceItemSchema.safeParse({ ...validEvidence, quality_score: 101 }).success).toBe(false);
  });

  it('accepts optional file_url as valid URL', () => {
    expect(
      EvidenceItemSchema.safeParse({ ...validEvidence, file_url: 'https://example.com/file.pdf' }).success,
    ).toBe(true);
  });

  it('rejects invalid file_url', () => {
    expect(EvidenceItemSchema.safeParse({ ...validEvidence, file_url: 'not-a-url' }).success).toBe(false);
  });

  it('accepts optional metadata as record', () => {
    expect(
      EvidenceItemSchema.safeParse({ ...validEvidence, metadata: { key: 'value' } }).success,
    ).toBe(true);
  });
});

describe('EvidenceArraySchema', () => {
  it('parses an empty array', () => {
    expect(EvidenceArraySchema.safeParse([]).success).toBe(true);
  });
});

// ============================================================================
// WidgetConfigSchema
// ============================================================================

describe('WidgetConfigSchema', () => {
  const validWidget = {
    id: 'w1',
    type: 'compliance-score' as const,
    position: { x: 0, y: 0 },
    size: { w: 2, h: 1 },
    settings: {},
    isVisible: true,
  };

  it('parses a valid widget config', () => {
    expect(WidgetConfigSchema.safeParse(validWidget).success).toBe(true);
  });

  it('accepts all valid widget types', () => {
    const types = [
      'compliance-score',
      'framework-progress',
      'pending-tasks',
      'activity-feed',
      'upcoming-deadlines',
      'ai-insights',
    ];
    types.forEach((type) => {
      expect(WidgetConfigSchema.safeParse({ ...validWidget, type }).success).toBe(true);
    });
  });

  it('rejects invalid widget type', () => {
    expect(WidgetConfigSchema.safeParse({ ...validWidget, type: 'unknown' }).success).toBe(false);
  });

  it('rejects negative position', () => {
    expect(
      WidgetConfigSchema.safeParse({ ...validWidget, position: { x: -1, y: 0 } }).success,
    ).toBe(false);
  });

  it('rejects size w < 1', () => {
    expect(
      WidgetConfigSchema.safeParse({ ...validWidget, size: { w: 0, h: 1 } }).success,
    ).toBe(false);
  });

  it('accepts settings as record of any', () => {
    expect(
      WidgetConfigSchema.safeParse({ ...validWidget, settings: { color: 'blue', count: 5 } }).success,
    ).toBe(true);
  });
});

describe('WidgetsArraySchema', () => {
  it('parses an empty array', () => {
    expect(WidgetsArraySchema.safeParse([]).success).toBe(true);
  });
});

// ============================================================================
// MetricsSchema
// ============================================================================

describe('MetricsSchema', () => {
  it('parses empty object (all fields optional)', () => {
    expect(MetricsSchema.safeParse({}).success).toBe(true);
  });

  it('accepts complianceScore 0-100', () => {
    expect(MetricsSchema.safeParse({ complianceScore: 75 }).success).toBe(true);
    expect(MetricsSchema.safeParse({ complianceScore: 0 }).success).toBe(true);
    expect(MetricsSchema.safeParse({ complianceScore: 100 }).success).toBe(true);
  });

  it('rejects complianceScore > 100', () => {
    expect(MetricsSchema.safeParse({ complianceScore: 101 }).success).toBe(false);
  });

  it('accepts valid trend values', () => {
    ['up', 'down', 'stable'].forEach((trend) => {
      expect(MetricsSchema.safeParse({ trend }).success).toBe(true);
    });
  });

  it('rejects invalid trend', () => {
    expect(MetricsSchema.safeParse({ trend: 'sideways' }).success).toBe(false);
  });

  it('accepts breakdown array', () => {
    const result = MetricsSchema.safeParse({
      breakdown: [{ framework: 'GDPR', score: 80, weight: 0.5 }],
    });
    expect(result.success).toBe(true);
  });

  it('rejects breakdown with score > 100', () => {
    expect(
      MetricsSchema.safeParse({
        breakdown: [{ framework: 'GDPR', score: 150, weight: 0.5 }],
      }).success,
    ).toBe(false);
  });

  it('rejects breakdown with weight > 1', () => {
    expect(
      MetricsSchema.safeParse({
        breakdown: [{ framework: 'GDPR', score: 80, weight: 1.5 }],
      }).success,
    ).toBe(false);
  });

  it('accepts non-negative integer pendingTasks', () => {
    expect(MetricsSchema.safeParse({ pendingTasks: 5 }).success).toBe(true);
    expect(MetricsSchema.safeParse({ pendingTasks: 0 }).success).toBe(true);
  });

  it('rejects negative pendingTasks', () => {
    expect(MetricsSchema.safeParse({ pendingTasks: -1 }).success).toBe(false);
  });
});

// ============================================================================
// FrameworkSchema
// ============================================================================

describe('FrameworkSchema', () => {
  const validFramework = { id: 'f1', name: 'ISO 27001' };

  it('parses a valid framework', () => {
    expect(FrameworkSchema.safeParse(validFramework).success).toBe(true);
  });

  it('accepts valid status values', () => {
    ['active', 'deprecated', 'draft'].forEach((status) => {
      expect(FrameworkSchema.safeParse({ ...validFramework, status }).success).toBe(true);
    });
  });

  it('rejects invalid status', () => {
    expect(FrameworkSchema.safeParse({ ...validFramework, status: 'archived' }).success).toBe(false);
  });

  it('accepts optional description and version', () => {
    expect(
      FrameworkSchema.safeParse({ ...validFramework, description: 'desc', version: '2022' }).success,
    ).toBe(true);
  });

  it('rejects empty id', () => {
    expect(FrameworkSchema.safeParse({ ...validFramework, id: '' }).success).toBe(false);
  });
});

describe('FrameworksArraySchema', () => {
  it('parses an array of frameworks', () => {
    expect(
      FrameworksArraySchema.safeParse([{ id: 'f1', name: 'GDPR' }]).success,
    ).toBe(true);
  });

  it('parses empty array', () => {
    expect(FrameworksArraySchema.safeParse([]).success).toBe(true);
  });
});

// ============================================================================
// LoadingStateSchema
// ============================================================================

describe('LoadingStateSchema', () => {
  it('accepts true', () => {
    expect(LoadingStateSchema.safeParse(true).success).toBe(true);
  });

  it('accepts false', () => {
    expect(LoadingStateSchema.safeParse(false).success).toBe(true);
  });

  it('rejects non-boolean', () => {
    expect(LoadingStateSchema.safeParse('true').success).toBe(false);
    expect(LoadingStateSchema.safeParse(1).success).toBe(false);
  });
});

// ============================================================================
// safeValidate
// ============================================================================

describe('safeValidate', () => {
  it('returns parsed data for valid input', () => {
    const result = safeValidate(FrameworkSchema, { id: 'f1', name: 'GDPR' }, 'test');
    expect(result).toMatchObject({ id: 'f1', name: 'GDPR' });
  });

  it('throws for invalid input (development mode)', () => {
    expect(() => {
      safeValidate(FrameworkSchema, { id: '' }, 'test context');
    }).toThrow();
  });
});
