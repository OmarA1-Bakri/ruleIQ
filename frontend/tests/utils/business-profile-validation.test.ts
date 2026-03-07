import { describe, it, expect } from 'vitest';
import { z } from 'zod';
import {
  companyInfoSchema,
  complianceProfileSchema,
  technologyStackSchema,
  complianceGoalsSchema,
  validateWizardStep,
  validateCompleteProfile,
  formatValidationErrors,
  customValidationRules,
} from '@/lib/validations/business-profile';

// ============================================================================
// companyInfoSchema
// ============================================================================

describe('companyInfoSchema', () => {
  const valid = {
    company_name: 'Acme Corp',
    industry: 'Technology',
    employee_count: 50,
    country: 'United Kingdom',
  };

  it('accepts valid company info', () => {
    expect(companyInfoSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects empty company name', () => {
    expect(companyInfoSchema.safeParse({ ...valid, company_name: '' }).success).toBe(false);
  });

  it('rejects company name shorter than 2 chars', () => {
    expect(companyInfoSchema.safeParse({ ...valid, company_name: 'A' }).success).toBe(false);
  });

  it('rejects company name longer than 100 chars', () => {
    expect(
      companyInfoSchema.safeParse({ ...valid, company_name: 'A'.repeat(101) }).success,
    ).toBe(false);
  });

  it('rejects invalid industry', () => {
    expect(
      companyInfoSchema.safeParse({ ...valid, industry: 'InvalidIndustry' as any }).success,
    ).toBe(false);
  });

  it('accepts all valid industries', () => {
    const industries = [
      'Technology', 'Healthcare', 'Financial Services', 'Education',
      'Government', 'Manufacturing', 'Retail', 'Professional Services',
      'Non-profit', 'Other',
    ];
    industries.forEach((ind) => {
      expect(
        companyInfoSchema.safeParse({ ...valid, industry: ind as any }).success,
      ).toBe(true);
    });
  });

  it('rejects employee_count of 0', () => {
    expect(companyInfoSchema.safeParse({ ...valid, employee_count: 0 }).success).toBe(false);
  });

  it('rejects negative employee_count', () => {
    expect(companyInfoSchema.safeParse({ ...valid, employee_count: -5 }).success).toBe(false);
  });

  it('rejects invalid country', () => {
    expect(
      companyInfoSchema.safeParse({ ...valid, country: 'Atlantis' as any }).success,
    ).toBe(false);
  });

  it('accepts valid countries', () => {
    const countries = ['United Kingdom', 'United States', 'Canada', 'Germany', 'Australia', 'Other'];
    countries.forEach((c) => {
      expect(
        companyInfoSchema.safeParse({ ...valid, country: c as any }).success,
      ).toBe(true);
    });
  });

  it('accepts optional annual_revenue', () => {
    expect(
      companyInfoSchema.safeParse({ ...valid, annual_revenue: 'Under £1M' as any }).success,
    ).toBe(true);
  });
});

// ============================================================================
// complianceProfileSchema
// ============================================================================

describe('complianceProfileSchema', () => {
  const valid = {
    data_sensitivity: 'Moderate',
    handles_personal_data: true,
    processes_payments: false,
    stores_health_data: false,
    provides_financial_services: false,
    operates_critical_infrastructure: false,
    has_international_operations: false,
  };

  it('accepts valid compliance profile', () => {
    expect(complianceProfileSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects invalid data_sensitivity', () => {
    expect(
      complianceProfileSchema.safeParse({ ...valid, data_sensitivity: 'VeryHigh' as any }).success,
    ).toBe(false);
  });

  it('accepts all valid data_sensitivity values', () => {
    ['Low', 'Moderate', 'High', 'Confidential'].forEach((level) => {
      expect(
        complianceProfileSchema.safeParse({ ...valid, data_sensitivity: level as any }).success,
      ).toBe(true);
    });
  });

  it('rejects non-boolean for boolean fields', () => {
    expect(
      complianceProfileSchema.safeParse({ ...valid, handles_personal_data: 'yes' as any }).success,
    ).toBe(false);
  });

  it('accepts all boolean combinations', () => {
    const allTrue = Object.fromEntries(
      Object.entries(valid).map(([k, v]) => [k, typeof v === 'boolean' ? true : v]),
    );
    expect(complianceProfileSchema.safeParse(allTrue).success).toBe(true);
  });
});

// ============================================================================
// technologyStackSchema
// ============================================================================

describe('technologyStackSchema', () => {
  it('accepts empty arrays (defaults)', () => {
    expect(technologyStackSchema.safeParse({}).success).toBe(true);
  });

  it('accepts valid cloud providers', () => {
    expect(
      technologyStackSchema.safeParse({
        cloud_providers: ['AWS', 'Microsoft Azure'],
      }).success,
    ).toBe(true);
  });

  it('accepts Other as cloud provider', () => {
    expect(
      technologyStackSchema.safeParse({
        cloud_providers: ['Other'],
      }).success,
    ).toBe(true);
  });

  it('rejects invalid cloud provider', () => {
    expect(
      technologyStackSchema.safeParse({
        cloud_providers: ['InvalidCloud' as any],
      }).success,
    ).toBe(false);
  });
});

// ============================================================================
// complianceGoalsSchema
// ============================================================================

describe('complianceGoalsSchema', () => {
  it('accepts valid compliance goals with empty arrays', () => {
    const result = complianceGoalsSchema.safeParse({
      existing_frameworks: [],
      planned_frameworks: [],
    });
    expect(result.success).toBe(true);
  });

  it('accepts valid compliance frameworks', () => {
    expect(
      complianceGoalsSchema.safeParse({
        existing_frameworks: ['ISO 27001', 'GDPR'],
        planned_frameworks: [],
      }).success,
    ).toBe(true);
  });
});

// ============================================================================
// validateWizardStep
// ============================================================================

describe('validateWizardStep', () => {
  it('returns success=true for valid company-info data', () => {
    const result = validateWizardStep('company-info', {
      company_name: 'Test Corp',
      industry: 'Technology',
      employee_count: 100,
      country: 'United Kingdom',
    });
    expect(result.success).toBe(true);
  });

  it('returns success=false for invalid company-info data', () => {
    const result = validateWizardStep('company-info', {
      company_name: '',
      industry: 'Technology',
      employee_count: 0,
      country: 'United Kingdom',
    });
    expect(result.success).toBe(false);
  });

  it('returns errors object on failure', () => {
    const result = validateWizardStep('company-info', {
      company_name: '',
      industry: 'Technology',
      employee_count: 100,
      country: 'United Kingdom',
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors).toBeDefined();
    }
  });

  it('returns success=true for valid technology-stack data', () => {
    const result = validateWizardStep('technology-stack', {
      cloud_providers: ['AWS'],
      saas_tools: [],
      development_tools: [],
    });
    expect(result.success).toBe(true);
  });

  it('returns success=true for compliance-profile step', () => {
    const result = validateWizardStep('compliance-profile', {
      data_sensitivity: 'High',
      handles_personal_data: true,
      processes_payments: false,
      stores_health_data: false,
      provides_financial_services: false,
      operates_critical_infrastructure: false,
      has_international_operations: true,
    });
    expect(result.success).toBe(true);
  });
});

// ============================================================================
// validateCompleteProfile
// ============================================================================

describe('validateCompleteProfile', () => {
  it('returns success=false for empty object', () => {
    const result = validateCompleteProfile({});
    expect(result.success).toBe(false);
  });

  it('returns errors on invalid profile', () => {
    const result = validateCompleteProfile({ company_name: '' });
    expect(result.success).toBe(false);
  });

  it('does not throw for null input', () => {
    expect(() => validateCompleteProfile(null)).not.toThrow();
  });
});

// ============================================================================
// formatValidationErrors
// ============================================================================

describe('formatValidationErrors', () => {
  it('formats a simple Zod error', () => {
    const schema = z.object({ name: z.string().min(2) });
    const result = schema.safeParse({ name: '' });
    expect(result.success).toBe(false);

    if (!result.success) {
      const formatted = formatValidationErrors(result.error);
      expect(Array.isArray(formatted)).toBe(true);
      expect(formatted.length).toBeGreaterThan(0);
      expect(formatted[0]).toHaveProperty('field');
      expect(formatted[0]).toHaveProperty('message');
    }
  });

  it('includes field path joined with dots', () => {
    const schema = z.object({ user: z.object({ name: z.string().min(1) }) });
    const result = schema.safeParse({ user: { name: '' } });

    if (!result.success) {
      const formatted = formatValidationErrors(result.error);
      expect(formatted[0]!.field).toBe('user.name');
    }
  });
});

// ============================================================================
// customValidationRules
// ============================================================================

describe('customValidationRules.validateCompanySize', () => {
  it('returns no warnings for typical company', () => {
    const warnings = customValidationRules.validateCompanySize(100, '£5M-£25M');
    expect(warnings).toHaveLength(0);
  });

  it('warns when large employee count has low revenue', () => {
    const warnings = customValidationRules.validateCompanySize(1001, 'Under £1M');
    expect(warnings.length).toBeGreaterThan(0);
    expect(warnings[0]).toContain('revenue');
  });

  it('warns when small team has very high revenue', () => {
    const warnings = customValidationRules.validateCompanySize(5, 'Over £100M');
    expect(warnings.length).toBeGreaterThan(0);
  });

  it('returns no warning for normal small team with low revenue', () => {
    const warnings = customValidationRules.validateCompanySize(5, 'Under £1M');
    expect(warnings).toHaveLength(0);
  });
});

describe('customValidationRules.validateFrameworkSelection', () => {
  it('recommends GDPR when handles_personal_data=true without GDPR selected', () => {
    const recs = customValidationRules.validateFrameworkSelection({
      handles_personal_data: true,
      existing_frameworks: [],
      planned_frameworks: [],
    } as any);
    expect(recs.some((r) => r.includes('GDPR'))).toBe(true);
  });

  it('recommends PCI DSS when processes_payments=true without PCI DSS', () => {
    const recs = customValidationRules.validateFrameworkSelection({
      processes_payments: true,
      existing_frameworks: [],
      planned_frameworks: [],
    } as any);
    expect(recs.some((r) => r.includes('PCI DSS'))).toBe(true);
  });

  it('returns empty array when frameworks already selected', () => {
    const recs = customValidationRules.validateFrameworkSelection({
      handles_personal_data: true,
      existing_frameworks: ['GDPR'],
      planned_frameworks: [],
    } as any);
    expect(recs.some((r) => r.includes('GDPR'))).toBe(false);
  });
});

describe('customValidationRules.validateTechnologyStack', () => {
  it('suggests adding technology info when stack is empty', () => {
    const suggestions = customValidationRules.validateTechnologyStack({
      cloud_providers: [],
      saas_tools: [],
    } as any);
    expect(suggestions.length).toBeGreaterThan(0);
  });

  it('returns no suggestions when stack is complete', () => {
    const suggestions = customValidationRules.validateTechnologyStack({
      cloud_providers: ['AWS'],
      saas_tools: ['Slack'],
      development_tools: ['GitHub'],
    } as any);
    expect(suggestions).toHaveLength(0);
  });
});
