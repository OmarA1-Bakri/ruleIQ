import { describe, it, expect, vi } from 'vitest';
import { PoliciesService } from '@/lib/api/policies-typed';

// Mock the API client to prevent actual HTTP requests
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

// Valid policy fixture
function createValidPolicy(overrides: Record<string, any> = {}) {
  return {
    id: '550e8400-e29b-41d4-a716-446655440000',
    title: 'Data Protection Policy',
    description: 'Policy for handling personal data',
    category: 'data_protection',
    status: 'draft',
    created_at: '2025-06-15T10:00:00Z',
    updated_at: '2025-06-15T10:00:00Z',
    version: 1,
    ...overrides,
  };
}

describe('PoliciesService', () => {
  let service: PoliciesService;

  beforeEach(() => {
    service = new PoliciesService();
  });

  describe('validatePolicy', () => {
    it('validates a correct policy object', () => {
      const policy = createValidPolicy();
      const result = service.validatePolicy(policy);

      expect(result.id).toBe(policy.id);
      expect(result.title).toBe(policy.title);
      expect(result.category).toBe('data_protection');
    });

    it('validates all category values', () => {
      const categories = ['data_protection', 'security', 'privacy', 'compliance', 'operational', 'financial'];

      categories.forEach((category) => {
        const policy = createValidPolicy({ category });
        expect(() => service.validatePolicy(policy)).not.toThrow();
      });
    });

    it('validates all status values', () => {
      const statuses = ['draft', 'under_review', 'approved', 'published', 'archived'];

      statuses.forEach((status) => {
        const policy = createValidPolicy({ status });
        expect(() => service.validatePolicy(policy)).not.toThrow();
      });
    });

    it('validates optional fields when present', () => {
      const policy = createValidPolicy({
        content: 'Full policy content here...',
        tags: ['gdpr', 'data-protection'],
        compliance_frameworks: ['ISO 27001', 'SOC 2'],
        risk_level: 'high',
      });

      const result = service.validatePolicy(policy);
      expect(result.content).toBe('Full policy content here...');
      expect(result.tags).toEqual(['gdpr', 'data-protection']);
      expect(result.risk_level).toBe('high');
    });

    it('validates all risk levels', () => {
      const levels = ['low', 'medium', 'high', 'critical'];

      levels.forEach((level) => {
        const policy = createValidPolicy({ risk_level: level });
        expect(() => service.validatePolicy(policy)).not.toThrow();
      });
    });

    it('rejects invalid UUID', () => {
      const policy = createValidPolicy({ id: 'not-a-uuid' });
      expect(() => service.validatePolicy(policy)).toThrow();
    });

    it('rejects empty title', () => {
      const policy = createValidPolicy({ title: '' });
      expect(() => service.validatePolicy(policy)).toThrow();
    });

    it('rejects title over 255 characters', () => {
      const policy = createValidPolicy({ title: 'A'.repeat(256) });
      expect(() => service.validatePolicy(policy)).toThrow();
    });

    it('rejects invalid category', () => {
      const policy = createValidPolicy({ category: 'invalid_category' });
      expect(() => service.validatePolicy(policy)).toThrow();
    });

    it('rejects invalid status', () => {
      const policy = createValidPolicy({ status: 'invalid_status' });
      expect(() => service.validatePolicy(policy)).toThrow();
    });

    it('rejects invalid risk_level', () => {
      const policy = createValidPolicy({ risk_level: 'extreme' });
      expect(() => service.validatePolicy(policy)).toThrow();
    });

    it('rejects non-positive version', () => {
      const policy = createValidPolicy({ version: 0 });
      expect(() => service.validatePolicy(policy)).toThrow();
    });

    it('rejects negative version', () => {
      const policy = createValidPolicy({ version: -1 });
      expect(() => service.validatePolicy(policy)).toThrow();
    });

    it('rejects non-integer version', () => {
      const policy = createValidPolicy({ version: 1.5 });
      expect(() => service.validatePolicy(policy)).toThrow();
    });

    it('rejects missing required fields', () => {
      expect(() => service.validatePolicy({})).toThrow();
      expect(() => service.validatePolicy({ id: '550e8400-e29b-41d4-a716-446655440000' })).toThrow();
    });

    it('rejects invalid datetime format', () => {
      const policy = createValidPolicy({ created_at: 'not-a-date' });
      expect(() => service.validatePolicy(policy)).toThrow();
    });
  });

  describe('hasRequiredFields', () => {
    it('returns true for valid policy with all required fields', () => {
      const policy = createValidPolicy();
      expect(service.hasRequiredFields(policy)).toBe(true);
    });

    it('returns false for missing id', () => {
      const { id, ...policy } = createValidPolicy();
      expect(service.hasRequiredFields(policy)).toBe(false);
    });

    it('returns false for missing title', () => {
      const { title, ...policy } = createValidPolicy();
      expect(service.hasRequiredFields(policy)).toBe(false);
    });

    it('returns false for missing category', () => {
      const { category, ...policy } = createValidPolicy();
      expect(service.hasRequiredFields(policy)).toBe(false);
    });

    it('returns false for missing status', () => {
      const { status, ...policy } = createValidPolicy();
      expect(service.hasRequiredFields(policy)).toBe(false);
    });

    it('returns false for empty object', () => {
      expect(service.hasRequiredFields({})).toBe(false);
    });

    it('returns false for null', () => {
      expect(service.hasRequiredFields(null)).toBe(false);
    });

    it('returns false for invalid category value', () => {
      const policy = createValidPolicy({ category: 'invalid' });
      expect(service.hasRequiredFields(policy)).toBe(false);
    });
  });
});
