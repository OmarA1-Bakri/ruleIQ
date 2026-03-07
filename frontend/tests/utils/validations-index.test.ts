import { describe, it, expect } from 'vitest';
import {
  evidenceSchema,
  assessmentResponseSchema,
  assessmentSessionSchema,
  policyGenerationSchema,
  implementationPlanSchema,
  reportGenerationSchema,
  chatMessageSchema,
  searchSchema,
  integrationConfigSchema,
} from '@/lib/validations/index';

// ============================================================================
// evidenceSchema
// ============================================================================

describe('evidenceSchema', () => {
  const validEvidence = {
    title: 'Access Control Policy',
    control_id: 'c1',
    framework: 'ISO 27001',
    business_profile_id: 'bp1',
    evidence_type: 'document',
  };

  it('parses valid minimal evidence', () => {
    expect(evidenceSchema.safeParse(validEvidence).success).toBe(true);
  });

  it('rejects empty title', () => {
    expect(evidenceSchema.safeParse({ ...validEvidence, title: '' }).success).toBe(false);
  });

  it('rejects title longer than 255 chars', () => {
    expect(
      evidenceSchema.safeParse({ ...validEvidence, title: 'x'.repeat(256) }).success,
    ).toBe(false);
  });

  it('accepts title exactly 255 chars', () => {
    expect(
      evidenceSchema.safeParse({ ...validEvidence, title: 'x'.repeat(255) }).success,
    ).toBe(true);
  });

  it('rejects description longer than 2000 chars', () => {
    expect(
      evidenceSchema.safeParse({ ...validEvidence, description: 'x'.repeat(2001) }).success,
    ).toBe(false);
  });

  it('accepts optional description under 2000 chars', () => {
    expect(
      evidenceSchema.safeParse({ ...validEvidence, description: 'A short description' }).success,
    ).toBe(true);
  });

  it('defaults tags to empty array when omitted', () => {
    const result = evidenceSchema.safeParse(validEvidence);
    if (result.success) {
      expect(result.data.tags).toEqual([]);
    }
  });

  it('accepts tags as string array', () => {
    expect(
      evidenceSchema.safeParse({ ...validEvidence, tags: ['gdpr', 'policy'] }).success,
    ).toBe(true);
  });

  it('rejects missing control_id', () => {
    const { control_id: _, ...rest } = validEvidence;
    expect(evidenceSchema.safeParse(rest).success).toBe(false);
  });
});

// ============================================================================
// assessmentResponseSchema
// ============================================================================

describe('assessmentResponseSchema', () => {
  it('accepts string response_value', () => {
    const result = assessmentResponseSchema.safeParse({
      question_id: 'q1',
      response_type: 'text',
      response_value: 'yes',
    });
    expect(result.success).toBe(true);
  });

  it('accepts boolean response_value', () => {
    const result = assessmentResponseSchema.safeParse({
      question_id: 'q1',
      response_type: 'boolean',
      response_value: true,
    });
    expect(result.success).toBe(true);
  });

  it('accepts array response_value', () => {
    const result = assessmentResponseSchema.safeParse({
      question_id: 'q1',
      response_type: 'multiple_choice',
      response_value: ['option1', 'option2'],
    });
    expect(result.success).toBe(true);
  });

  it('accepts all valid response_type values', () => {
    ['multiple_choice', 'text', 'boolean'].forEach((response_type) => {
      expect(
        assessmentResponseSchema.safeParse({
          question_id: 'q1',
          response_type,
          response_value: 'val',
        }).success,
      ).toBe(true);
    });
  });

  it('rejects invalid response_type', () => {
    expect(
      assessmentResponseSchema.safeParse({
        question_id: 'q1',
        response_type: 'checkbox',
        response_value: 'val',
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// assessmentSessionSchema
// ============================================================================

describe('assessmentSessionSchema', () => {
  it('parses valid session with required fields', () => {
    const result = assessmentSessionSchema.safeParse({ business_profile_id: 'bp1' });
    expect(result.success).toBe(true);
  });

  it('defaults responses to empty array', () => {
    const result = assessmentSessionSchema.safeParse({ business_profile_id: 'bp1' });
    if (result.success) {
      expect(result.data.responses).toEqual([]);
    }
  });

  it('rejects empty business_profile_id', () => {
    expect(assessmentSessionSchema.safeParse({ business_profile_id: '' }).success).toBe(false);
  });

  it('accepts optional framework_id', () => {
    expect(
      assessmentSessionSchema.safeParse({
        business_profile_id: 'bp1',
        framework_id: 'f1',
      }).success,
    ).toBe(true);
  });

  it('accepts responses array', () => {
    expect(
      assessmentSessionSchema.safeParse({
        business_profile_id: 'bp1',
        responses: [
          { question_id: 'q1', response_type: 'text', response_value: 'yes' },
        ],
      }).success,
    ).toBe(true);
  });
});

// ============================================================================
// policyGenerationSchema
// ============================================================================

describe('policyGenerationSchema', () => {
  const validPolicy = {
    framework: 'ISO 27001',
    business_profile_id: 'bp1',
    policy_title: 'Access Control Policy',
    tone: 'formal' as const,
  };

  it('parses valid policy generation data', () => {
    expect(policyGenerationSchema.safeParse(validPolicy).success).toBe(true);
  });

  it('accepts all valid tone values', () => {
    ['formal', 'informal', 'strict'].forEach((tone) => {
      expect(policyGenerationSchema.safeParse({ ...validPolicy, tone }).success).toBe(true);
    });
  });

  it('rejects invalid tone', () => {
    expect(policyGenerationSchema.safeParse({ ...validPolicy, tone: 'casual' }).success).toBe(false);
  });

  it('rejects empty policy_title', () => {
    expect(policyGenerationSchema.safeParse({ ...validPolicy, policy_title: '' }).success).toBe(false);
  });

  it('rejects policy_title longer than 255 chars', () => {
    expect(
      policyGenerationSchema.safeParse({ ...validPolicy, policy_title: 'x'.repeat(256) }).success,
    ).toBe(false);
  });

  it('defaults specific_controls to empty array', () => {
    const result = policyGenerationSchema.safeParse(validPolicy);
    if (result.success) {
      expect(result.data.specific_controls).toEqual([]);
    }
  });

  it('accepts specific_controls as string array', () => {
    expect(
      policyGenerationSchema.safeParse({ ...validPolicy, specific_controls: ['ctrl1'] }).success,
    ).toBe(true);
  });
});

// ============================================================================
// implementationPlanSchema
// ============================================================================

describe('implementationPlanSchema', () => {
  const validPlan = {
    business_profile_id: 'bp1',
    framework_id: 'f1',
    title: 'GDPR Implementation Plan',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
  };

  it('parses valid implementation plan', () => {
    expect(implementationPlanSchema.safeParse(validPlan).success).toBe(true);
  });

  it('rejects empty title', () => {
    expect(implementationPlanSchema.safeParse({ ...validPlan, title: '' }).success).toBe(false);
  });

  it('rejects title longer than 255 chars', () => {
    expect(
      implementationPlanSchema.safeParse({ ...validPlan, title: 'x'.repeat(256) }).success,
    ).toBe(false);
  });

  it('rejects missing start_date', () => {
    const { start_date: _, ...rest } = validPlan;
    expect(implementationPlanSchema.safeParse(rest).success).toBe(false);
  });

  it('rejects empty end_date', () => {
    expect(implementationPlanSchema.safeParse({ ...validPlan, end_date: '' }).success).toBe(false);
  });
});

// ============================================================================
// reportGenerationSchema
// ============================================================================

describe('reportGenerationSchema', () => {
  const validReport = {
    business_profile_id: 'bp1',
    report_type: 'executive_summary' as const,
    format: 'pdf' as const,
  };

  it('parses valid report generation data', () => {
    expect(reportGenerationSchema.safeParse(validReport).success).toBe(true);
  });

  it('accepts all valid report types', () => {
    const types = [
      'executive_summary',
      'gap_analysis',
      'evidence_report',
      'audit_readiness',
      'compliance_status',
      'control_matrix',
      'risk_assessment',
    ];
    types.forEach((report_type) => {
      expect(reportGenerationSchema.safeParse({ ...validReport, report_type }).success).toBe(true);
    });
  });

  it('rejects invalid report type', () => {
    expect(
      reportGenerationSchema.safeParse({ ...validReport, report_type: 'custom_report' }).success,
    ).toBe(false);
  });

  it('accepts all valid formats', () => {
    ['pdf', 'excel', 'html', 'csv'].forEach((format) => {
      expect(reportGenerationSchema.safeParse({ ...validReport, format }).success).toBe(true);
    });
  });

  it('rejects invalid format', () => {
    expect(
      reportGenerationSchema.safeParse({ ...validReport, format: 'docx' }).success,
    ).toBe(false);
  });

  it('defaults include_evidence to true', () => {
    const result = reportGenerationSchema.safeParse(validReport);
    if (result.success) {
      expect(result.data.include_evidence).toBe(true);
    }
  });

  it('defaults frameworks to empty array', () => {
    const result = reportGenerationSchema.safeParse(validReport);
    if (result.success) {
      expect(result.data.frameworks).toEqual([]);
    }
  });

  it('accepts optional start_date and end_date', () => {
    expect(
      reportGenerationSchema.safeParse({
        ...validReport,
        start_date: '2024-01-01',
        end_date: '2024-12-31',
      }).success,
    ).toBe(true);
  });
});

// ============================================================================
// chatMessageSchema
// ============================================================================

describe('chatMessageSchema', () => {
  it('parses valid message', () => {
    expect(chatMessageSchema.safeParse({ message: 'Hello' }).success).toBe(true);
  });

  it('rejects empty message', () => {
    expect(chatMessageSchema.safeParse({ message: '' }).success).toBe(false);
  });

  it('rejects message longer than 2000 chars', () => {
    expect(chatMessageSchema.safeParse({ message: 'x'.repeat(2001) }).success).toBe(false);
  });

  it('accepts message exactly 2000 chars', () => {
    expect(chatMessageSchema.safeParse({ message: 'x'.repeat(2000) }).success).toBe(true);
  });

  it('rejects missing message field', () => {
    expect(chatMessageSchema.safeParse({}).success).toBe(false);
  });
});

// ============================================================================
// searchSchema
// ============================================================================

describe('searchSchema', () => {
  it('parses valid search with query only', () => {
    expect(searchSchema.safeParse({ query: 'GDPR requirements' }).success).toBe(true);
  });

  it('rejects empty query', () => {
    expect(searchSchema.safeParse({ query: '' }).success).toBe(false);
  });

  it('accepts optional filters', () => {
    expect(
      searchSchema.safeParse({
        query: 'test',
        filters: { framework: 'ISO 27001', status: 'active' },
      }).success,
    ).toBe(true);
  });

  it('accepts filters with only some fields', () => {
    expect(
      searchSchema.safeParse({ query: 'test', filters: { evidence_type: 'document' } }).success,
    ).toBe(true);
  });

  it('accepts empty filters object', () => {
    expect(searchSchema.safeParse({ query: 'test', filters: {} }).success).toBe(true);
  });
});

// ============================================================================
// integrationConfigSchema
// ============================================================================

describe('integrationConfigSchema', () => {
  const validConfig = {
    provider: 'google_workspace' as const,
    credentials: { api_key: 'abc123' },
  };

  it('parses valid integration config', () => {
    expect(integrationConfigSchema.safeParse(validConfig).success).toBe(true);
  });

  it('accepts all valid providers', () => {
    const providers = [
      'google_workspace',
      'microsoft_365',
      'slack',
      'github',
      'jira',
      'azure_ad',
    ];
    providers.forEach((provider) => {
      expect(integrationConfigSchema.safeParse({ ...validConfig, provider }).success).toBe(true);
    });
  });

  it('rejects invalid provider', () => {
    expect(
      integrationConfigSchema.safeParse({ ...validConfig, provider: 'dropbox' }).success,
    ).toBe(false);
  });

  it('rejects missing credentials', () => {
    const { credentials: _, ...rest } = validConfig;
    expect(integrationConfigSchema.safeParse(rest).success).toBe(false);
  });

  it('accepts optional settings', () => {
    expect(
      integrationConfigSchema.safeParse({ ...validConfig, settings: { sync_interval: 60 } }).success,
    ).toBe(true);
  });
});
