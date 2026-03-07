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
  safeValidate,
} from '@/lib/stores/schemas';

// ── Helpers ──────────────────────────────────────────────

function validAssessment(overrides: Record<string, any> = {}) {
  return {
    id: 'assessment-1',
    name: 'GDPR Assessment',
    status: 'draft',
    framework_id: 'fw-1',
    business_profile_id: 'bp-1',
    ...overrides,
  };
}

function validEvidence(overrides: Record<string, any> = {}) {
  return {
    id: 'ev-1',
    title: 'Data Processing Log',
    description: 'Log file for data processing',
    control_id: 'ctrl-1',
    framework_id: 'fw-1',
    business_profile_id: 'bp-1',
    evidence_type: 'document',
    source: 'manual',
    tags: ['gdpr', 'data'],
    status: 'pending',
    created_at: '2025-06-15',
    updated_at: '2025-06-15',
    ...overrides,
  };
}

function validWidget(overrides: Record<string, any> = {}) {
  return {
    id: 'w-1',
    type: 'compliance-score',
    position: { x: 0, y: 0 },
    size: { w: 2, h: 2 },
    settings: {},
    isVisible: true,
    ...overrides,
  };
}

// ── AssessmentSchema ─────────────────────────────────────

describe('AssessmentSchema', () => {
  it('validates a correct assessment', () => {
    const result = AssessmentSchema.parse(validAssessment());
    expect(result.id).toBe('assessment-1');
    expect(result.name).toBe('GDPR Assessment');
  });

  it('accepts all valid statuses', () => {
    for (const status of ['draft', 'in_progress', 'completed', 'expired']) {
      expect(() => AssessmentSchema.parse(validAssessment({ status }))).not.toThrow();
    }
  });

  it('rejects invalid status', () => {
    expect(() => AssessmentSchema.parse(validAssessment({ status: 'invalid' }))).toThrow();
  });

  it('rejects empty id', () => {
    expect(() => AssessmentSchema.parse(validAssessment({ id: '' }))).toThrow();
  });

  it('rejects empty name', () => {
    expect(() => AssessmentSchema.parse(validAssessment({ name: '' }))).toThrow();
  });

  it('accepts optional fields', () => {
    const result = AssessmentSchema.parse(
      validAssessment({
        total_questions: 50,
        answered_questions: 30,
        score: 85,
        created_at: '2025-06-15T10:00:00Z',
        updated_at: '2025-06-15T10:00:00Z',
      }),
    );
    expect(result.total_questions).toBe(50);
    expect(result.score).toBe(85);
  });

  it('rejects score above 100', () => {
    expect(() => AssessmentSchema.parse(validAssessment({ score: 101 }))).toThrow();
  });

  it('rejects negative score', () => {
    expect(() => AssessmentSchema.parse(validAssessment({ score: -1 }))).toThrow();
  });

  it('rejects negative total_questions', () => {
    expect(() => AssessmentSchema.parse(validAssessment({ total_questions: -1 }))).toThrow();
  });
});

describe('AssessmentsArraySchema', () => {
  it('validates an array of assessments', () => {
    const result = AssessmentsArraySchema.parse([
      validAssessment(),
      validAssessment({ id: 'assessment-2', name: 'ISO Assessment' }),
    ]);
    expect(result).toHaveLength(2);
  });

  it('validates an empty array', () => {
    expect(AssessmentsArraySchema.parse([])).toEqual([]);
  });

  it('rejects if any item is invalid', () => {
    expect(() =>
      AssessmentsArraySchema.parse([validAssessment(), { id: '' }]),
    ).toThrow();
  });
});

// ── EvidenceItemSchema ───────────────────────────────────

describe('EvidenceItemSchema', () => {
  it('validates correct evidence', () => {
    const result = EvidenceItemSchema.parse(validEvidence());
    expect(result.id).toBe('ev-1');
    expect(result.tags).toEqual(['gdpr', 'data']);
  });

  it('accepts all valid statuses', () => {
    for (const status of ['pending', 'collected', 'approved', 'rejected', 'needs_review']) {
      expect(() => EvidenceItemSchema.parse(validEvidence({ status }))).not.toThrow();
    }
  });

  it('rejects invalid status', () => {
    expect(() => EvidenceItemSchema.parse(validEvidence({ status: 'unknown' }))).toThrow();
  });

  it('rejects empty title', () => {
    expect(() => EvidenceItemSchema.parse(validEvidence({ title: '' }))).toThrow();
  });

  it('accepts optional fields', () => {
    const result = EvidenceItemSchema.parse(
      validEvidence({
        quality_score: 95,
        metadata: { key: 'value' },
        file_url: 'https://example.com/file.pdf',
        file_name: 'file.pdf',
        file_size: 1024,
      }),
    );
    expect(result.quality_score).toBe(95);
    expect(result.file_name).toBe('file.pdf');
  });

  it('rejects quality_score above 100', () => {
    expect(() => EvidenceItemSchema.parse(validEvidence({ quality_score: 101 }))).toThrow();
  });

  it('rejects negative file_size', () => {
    expect(() => EvidenceItemSchema.parse(validEvidence({ file_size: -1 }))).toThrow();
  });
});

describe('EvidenceArraySchema', () => {
  it('validates array of evidence items', () => {
    const result = EvidenceArraySchema.parse([validEvidence()]);
    expect(result).toHaveLength(1);
  });
});

// ── WidgetConfigSchema ───────────────────────────────────

describe('WidgetConfigSchema', () => {
  it('validates correct widget config', () => {
    const result = WidgetConfigSchema.parse(validWidget());
    expect(result.type).toBe('compliance-score');
    expect(result.position).toEqual({ x: 0, y: 0 });
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
    for (const type of types) {
      expect(() => WidgetConfigSchema.parse(validWidget({ type }))).not.toThrow();
    }
  });

  it('rejects invalid widget type', () => {
    expect(() => WidgetConfigSchema.parse(validWidget({ type: 'custom-widget' }))).toThrow();
  });

  it('rejects negative position x', () => {
    expect(() =>
      WidgetConfigSchema.parse(validWidget({ position: { x: -1, y: 0 } })),
    ).toThrow();
  });

  it('rejects zero width', () => {
    expect(() =>
      WidgetConfigSchema.parse(validWidget({ size: { w: 0, h: 2 } })),
    ).toThrow();
  });

  it('rejects zero height', () => {
    expect(() =>
      WidgetConfigSchema.parse(validWidget({ size: { w: 2, h: 0 } })),
    ).toThrow();
  });

  it('requires isVisible to be boolean', () => {
    expect(() =>
      WidgetConfigSchema.parse(validWidget({ isVisible: 'true' })),
    ).toThrow();
  });
});

describe('WidgetsArraySchema', () => {
  it('validates array of widgets', () => {
    const result = WidgetsArraySchema.parse([
      validWidget(),
      validWidget({ id: 'w-2', type: 'pending-tasks' }),
    ]);
    expect(result).toHaveLength(2);
  });
});

// ── MetricsSchema ────────────────────────────────────────

describe('MetricsSchema', () => {
  it('validates empty metrics (all optional)', () => {
    const result = MetricsSchema.parse({});
    expect(result).toEqual({});
  });

  it('validates full metrics', () => {
    const result = MetricsSchema.parse({
      complianceScore: 85,
      completedAssessments: 10,
      pendingTasks: 5,
      overall_score: 90,
      policy_score: 80,
      implementation_score: 75,
      evidence_score: 95,
      trend: 'up',
      domain_scores: { gdpr: 85, iso: 90 },
      control_scores: { ctrl1: 80, ctrl2: 95 },
      breakdown: [
        { framework: 'GDPR', score: 85, weight: 0.5 },
        { framework: 'ISO', score: 90, weight: 0.5 },
      ],
    });
    expect(result.complianceScore).toBe(85);
    expect(result.trend).toBe('up');
  });

  it('accepts valid trend values', () => {
    for (const trend of ['up', 'down', 'stable']) {
      expect(() => MetricsSchema.parse({ trend })).not.toThrow();
    }
  });

  it('rejects invalid trend', () => {
    expect(() => MetricsSchema.parse({ trend: 'sideways' })).toThrow();
  });

  it('rejects compliance score above 100', () => {
    expect(() => MetricsSchema.parse({ complianceScore: 101 })).toThrow();
  });

  it('rejects negative pending tasks', () => {
    expect(() => MetricsSchema.parse({ pendingTasks: -1 })).toThrow();
  });

  it('rejects breakdown weight above 1', () => {
    expect(() =>
      MetricsSchema.parse({
        breakdown: [{ framework: 'GDPR', score: 85, weight: 1.5 }],
      }),
    ).toThrow();
  });
});

// ── FrameworkSchema ──────────────────────────────────────

describe('FrameworkSchema', () => {
  it('validates a correct framework', () => {
    const result = FrameworkSchema.parse({
      id: 'fw-1',
      name: 'GDPR',
    });
    expect(result.id).toBe('fw-1');
    expect(result.name).toBe('GDPR');
  });

  it('accepts optional fields', () => {
    const result = FrameworkSchema.parse({
      id: 'fw-1',
      name: 'ISO 27001',
      description: 'Information security',
      version: '2022',
      status: 'active',
    });
    expect(result.version).toBe('2022');
    expect(result.status).toBe('active');
  });

  it('accepts valid statuses', () => {
    for (const status of ['active', 'deprecated', 'draft']) {
      expect(() =>
        FrameworkSchema.parse({ id: 'fw-1', name: 'Test', status }),
      ).not.toThrow();
    }
  });

  it('rejects invalid status', () => {
    expect(() =>
      FrameworkSchema.parse({ id: 'fw-1', name: 'Test', status: 'invalid' }),
    ).toThrow();
  });

  it('rejects empty id', () => {
    expect(() => FrameworkSchema.parse({ id: '', name: 'Test' })).toThrow();
  });

  it('rejects empty name', () => {
    expect(() => FrameworkSchema.parse({ id: 'fw-1', name: '' })).toThrow();
  });
});

describe('FrameworksArraySchema', () => {
  it('validates array of frameworks', () => {
    const result = FrameworksArraySchema.parse([
      { id: 'fw-1', name: 'GDPR' },
      { id: 'fw-2', name: 'ISO' },
    ]);
    expect(result).toHaveLength(2);
  });
});

// ── safeValidate ─────────────────────────────────────────

describe('safeValidate', () => {
  it('returns parsed data on success', () => {
    const result = safeValidate(
      FrameworkSchema,
      { id: 'fw-1', name: 'GDPR' },
      'test-context',
    );
    expect(result.id).toBe('fw-1');
  });

  it('throws on invalid data in development', () => {
    expect(() =>
      safeValidate(FrameworkSchema, { id: '', name: '' }, 'test-context'),
    ).toThrow();
  });

  it('throws a ZodError on invalid data', () => {
    expect(() =>
      safeValidate(FrameworkSchema, { id: '', name: '' }, 'my-component'),
    ).toThrow();
  });
});
