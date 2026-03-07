import { describe, it, expect } from 'vitest';
import { BusinessProfileFieldMapper, getAPIFieldName } from '@/lib/api/business-profile/field-mapper';

// ============================================================================
// BusinessProfileFieldMapper.fieldMap
// ============================================================================

describe('BusinessProfileFieldMapper.fieldMap', () => {
  it('maps handles_personal_data → handles_persona', () => {
    expect(BusinessProfileFieldMapper.fieldMap.handles_personal_data).toBe('handles_persona');
  });

  it('maps processes_payments → processes_payme', () => {
    expect(BusinessProfileFieldMapper.fieldMap.processes_payments).toBe('processes_payme');
  });

  it('maps stores_health_data → stores_health_d', () => {
    expect(BusinessProfileFieldMapper.fieldMap.stores_health_data).toBe('stores_health_d');
  });

  it('maps provides_financial_services → provides_financ', () => {
    expect(BusinessProfileFieldMapper.fieldMap.provides_financial_services).toBe('provides_financ');
  });

  it('maps operates_critical_infrastructure → operates_critic', () => {
    expect(BusinessProfileFieldMapper.fieldMap.operates_critical_infrastructure).toBe('operates_critic');
  });

  it('maps has_international_operations → has_internation', () => {
    expect(BusinessProfileFieldMapper.fieldMap.has_international_operations).toBe('has_internation');
  });

  it('maps existing_frameworks → existing_framew', () => {
    expect(BusinessProfileFieldMapper.fieldMap.existing_frameworks).toBe('existing_framew');
  });

  it('maps planned_frameworks → planned_framewo', () => {
    expect(BusinessProfileFieldMapper.fieldMap.planned_frameworks).toBe('planned_framewo');
  });

  it('maps development_tools → development_too', () => {
    expect(BusinessProfileFieldMapper.fieldMap.development_tools).toBe('development_too');
  });

  it('maps compliance_budget → compliance_budg', () => {
    expect(BusinessProfileFieldMapper.fieldMap.compliance_budget).toBe('compliance_budg');
  });

  it('maps compliance_timeline → compliance_time', () => {
    expect(BusinessProfileFieldMapper.fieldMap.compliance_timeline).toBe('compliance_time');
  });
});

// ============================================================================
// BusinessProfileFieldMapper.toAPI
// ============================================================================

describe('BusinessProfileFieldMapper.toAPI', () => {
  it('maps frontend boolean field to truncated API field', () => {
    const result = BusinessProfileFieldMapper.toAPI({ handles_personal_data: true });
    expect(result).toHaveProperty('handles_persona', true);
    expect(result).not.toHaveProperty('handles_personal_data');
  });

  it('preserves unmapped fields unchanged', () => {
    const result = BusinessProfileFieldMapper.toAPI({ company_name: 'Acme', industry: 'Tech' });
    expect(result.company_name).toBe('Acme');
    expect(result.industry).toBe('Tech');
  });

  it('maps multiple fields at once', () => {
    const result = BusinessProfileFieldMapper.toAPI({
      handles_personal_data: true,
      processes_payments: false,
      stores_health_data: true,
    });
    expect(result.handles_persona).toBe(true);
    expect(result.processes_payme).toBe(false);
    expect(result.stores_health_d).toBe(true);
  });

  it('converts compliance_budget string to number', () => {
    const result = BusinessProfileFieldMapper.toAPI({ compliance_budget: '50000' });
    expect(result.compliance_budg).toBe(50000);
    expect(typeof result.compliance_budg).toBe('number');
  });

  it('converts invalid compliance_budget to 0', () => {
    const result = BusinessProfileFieldMapper.toAPI({ compliance_budget: 'not-a-number' });
    expect(result.compliance_budg).toBe(0);
  });

  it('maps array fields (existing_frameworks)', () => {
    const result = BusinessProfileFieldMapper.toAPI({
      existing_frameworks: ['ISO 27001', 'GDPR'],
    });
    expect(result.existing_framew).toEqual(['ISO 27001', 'GDPR']);
  });

  it('returns null/undefined passthrough', () => {
    const result = BusinessProfileFieldMapper.toAPI(null as any);
    expect(result).toBeNull();
  });

  it('returns empty object for empty input', () => {
    const result = BusinessProfileFieldMapper.toAPI({});
    expect(result).toEqual({});
  });
});

// ============================================================================
// BusinessProfileFieldMapper.fromAPI
// ============================================================================

describe('BusinessProfileFieldMapper.fromAPI', () => {
  it('maps truncated API field back to frontend field name', () => {
    const result = BusinessProfileFieldMapper.fromAPI({ handles_persona: true });
    expect(result).toHaveProperty('handles_personal_data', true);
    expect(result).not.toHaveProperty('handles_persona');
  });

  it('maps multiple truncated fields', () => {
    const result = BusinessProfileFieldMapper.fromAPI({
      handles_persona: true,
      processes_payme: false,
    });
    expect(result?.handles_personal_data).toBe(true);
    expect(result?.processes_payments).toBe(false);
  });

  it('preserves unmapped fields unchanged', () => {
    const result = BusinessProfileFieldMapper.fromAPI({ company_name: 'Test Corp' });
    expect((result as any).company_name).toBe('Test Corp');
  });

  it('converts compliance_budg number to string', () => {
    const result = BusinessProfileFieldMapper.fromAPI({ compliance_budg: 50000 });
    expect((result as any).compliance_budget).toBe('50000');
    expect(typeof (result as any).compliance_budget).toBe('string');
  });

  it('returns null for null input', () => {
    expect(BusinessProfileFieldMapper.fromAPI(null)).toBeNull();
  });

  it('returns null for undefined input', () => {
    expect(BusinessProfileFieldMapper.fromAPI(undefined)).toBeNull();
  });
});

// ============================================================================
// BusinessProfileFieldMapper.getAPIField
// ============================================================================

describe('BusinessProfileFieldMapper.getAPIField', () => {
  it('returns truncated API field for mapped field', () => {
    expect(BusinessProfileFieldMapper.getAPIField('handles_personal_data' as any)).toBe('handles_persona');
  });

  it('returns the same field name for unmapped field', () => {
    expect(BusinessProfileFieldMapper.getAPIField('company_name' as any)).toBe('company_name');
  });

  it('returns correct API field for all mapped fields', () => {
    const mapped = BusinessProfileFieldMapper.fieldMap;
    Object.entries(mapped).forEach(([frontendKey, apiKey]) => {
      expect(BusinessProfileFieldMapper.getAPIField(frontendKey as any)).toBe(apiKey);
    });
  });
});

// ============================================================================
// BusinessProfileFieldMapper.getFrontendField
// ============================================================================

describe('BusinessProfileFieldMapper.getFrontendField', () => {
  it('returns descriptive frontend field for truncated API field', () => {
    expect(BusinessProfileFieldMapper.getFrontendField('handles_persona')).toBe('handles_personal_data');
  });

  it('returns the same field for unmapped API field', () => {
    expect(BusinessProfileFieldMapper.getFrontendField('company_name')).toBe('company_name');
  });

  it('returns correct frontend field for all mapped API fields', () => {
    const mapped = BusinessProfileFieldMapper.fieldMap;
    Object.entries(mapped).forEach(([frontendKey, apiKey]) => {
      expect(BusinessProfileFieldMapper.getFrontendField(apiKey)).toBe(frontendKey);
    });
  });
});

// ============================================================================
// BusinessProfileFieldMapper.validateMappings
// ============================================================================

describe('BusinessProfileFieldMapper.validateMappings', () => {
  it('returns isValid=true and empty missingMappings', () => {
    const result = BusinessProfileFieldMapper.validateMappings();
    expect(result.isValid).toBe(true);
    expect(result.missingMappings).toHaveLength(0);
  });

  it('returns an object with isValid and missingMappings keys', () => {
    const result = BusinessProfileFieldMapper.validateMappings();
    expect(result).toHaveProperty('isValid');
    expect(result).toHaveProperty('missingMappings');
    expect(Array.isArray(result.missingMappings)).toBe(true);
  });
});

// ============================================================================
// BusinessProfileFieldMapper.getAllMappings
// ============================================================================

describe('BusinessProfileFieldMapper.getAllMappings', () => {
  it('returns all 11 mappings', () => {
    const mappings = BusinessProfileFieldMapper.getAllMappings();
    expect(Object.keys(mappings).length).toBe(11);
  });

  it('returns a plain object (not the original const)', () => {
    const mappings = BusinessProfileFieldMapper.getAllMappings();
    expect(typeof mappings).toBe('object');
    expect(mappings).not.toBe(BusinessProfileFieldMapper.fieldMap);
  });

  it('contains all expected frontend field keys', () => {
    const mappings = BusinessProfileFieldMapper.getAllMappings();
    expect(mappings).toHaveProperty('handles_personal_data');
    expect(mappings).toHaveProperty('existing_frameworks');
    expect(mappings).toHaveProperty('compliance_budget');
  });
});

// ============================================================================
// BusinessProfileFieldMapper.transformFormDataForAPI
// ============================================================================

describe('BusinessProfileFieldMapper.transformFormDataForAPI', () => {
  it('maps boolean fields and ensures they are boolean', () => {
    const result = BusinessProfileFieldMapper.transformFormDataForAPI({
      handles_personal_data: true,
      processes_payments: false,
    });
    expect(result.handles_persona).toBe(true);
    expect(result.processes_payme).toBe(false);
    expect(typeof result.handles_persona).toBe('boolean');
  });

  it('ensures array fields remain arrays', () => {
    const result = BusinessProfileFieldMapper.transformFormDataForAPI({
      existing_frameworks: ['GDPR', 'ISO 27001'],
      cloud_providers: ['AWS'],
    });
    expect(Array.isArray(result.existing_framew)).toBe(true);
    expect(Array.isArray(result.cloud_providers)).toBe(true);
  });

  it('resets non-array values to empty array for known array fields', () => {
    const result = BusinessProfileFieldMapper.transformFormDataForAPI({
      cloud_providers: 'AWS', // should be coerced to []
    });
    expect(result.cloud_providers).toEqual([]);
  });
});

// ============================================================================
// BusinessProfileFieldMapper.createUpdatePayload
// ============================================================================

describe('BusinessProfileFieldMapper.createUpdatePayload', () => {
  const original: any = {
    company_name: 'Acme',
    handles_personal_data: false,
    existing_frameworks: ['GDPR'],
  };

  it('includes only changed fields', () => {
    const result = BusinessProfileFieldMapper.createUpdatePayload(original, {
      handles_personal_data: true,
    } as any);
    expect(result).toHaveProperty('handles_persona', true);
    expect(result).not.toHaveProperty('company_name');
  });

  it('returns empty object when nothing changed', () => {
    const result = BusinessProfileFieldMapper.createUpdatePayload(original, {
      company_name: 'Acme',
    } as any);
    expect(Object.keys(result).length).toBe(0);
  });

  it('handles array field changes', () => {
    const result = BusinessProfileFieldMapper.createUpdatePayload(original, {
      existing_frameworks: ['GDPR', 'ISO 27001'],
    } as any);
    expect(result.existing_framew).toEqual(['GDPR', 'ISO 27001']);
  });
});

// ============================================================================
// getAPIFieldName helper
// ============================================================================

describe('getAPIFieldName', () => {
  it('returns the API field name for handles_personal_data', () => {
    expect(getAPIFieldName('handles_personal_data' as any)).toBe('handles_persona');
  });

  it('returns the same name for unmapped fields', () => {
    expect(getAPIFieldName('company_name' as any)).toBe('company_name');
  });
});
