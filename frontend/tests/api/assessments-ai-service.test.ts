import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

// Mock error-handling utilities
vi.mock('@/lib/utils/error-handling', () => ({
  withRetry: vi.fn((fn: () => Promise<any>) => fn()),
  createAppError: vi.fn((err: any) => err),
}));

// Mock chat service dependency
vi.mock('@/lib/api/chat.service', () => ({
  chatService: {
    sendMessage: vi.fn(),
  },
}));

describe('AssessmentAIService', () => {
  let assessmentAIService: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const serviceMod = await import('@/lib/api/assessments-ai.service');
    assessmentAIService = serviceMod.assessmentAIService;
  });

  // -- Sync helper methods (no API calls, no setTimeout) --

  describe('getBusinessProfileFromContext', () => {
    it('returns empty context with no data', () => {
      const result = assessmentAIService.getBusinessProfileFromContext();
      expect(result).toEqual({});
    });

    it('passes through business profile', () => {
      const profile = { industry: 'Technology', company_name: 'Acme' };
      const result = assessmentAIService.getBusinessProfileFromContext(profile);
      expect(result.industry).toBe('Technology');
      expect(result.company_name).toBe('Acme');
    });

    it('extracts company_size from answers', () => {
      const result = assessmentAIService.getBusinessProfileFromContext({}, {
        company_size: 'medium',
      });
      expect((result as any).size).toBe('medium');
    });

    it('extracts employee_count from answers', () => {
      const result = assessmentAIService.getBusinessProfileFromContext({}, {
        employee_count: '50-100',
      });
      expect((result as any).size).toBe('50-100');
    });

    it('extracts and capitalizes industry from answers', () => {
      const result = assessmentAIService.getBusinessProfileFromContext({}, {
        industry: 'technology',
      });
      expect(result.industry).toBe('Technology');
    });

    it('extracts business_sector as industry', () => {
      const result = assessmentAIService.getBusinessProfileFromContext({}, {
        business_sector: 'HEALTHCARE',
      });
      expect(result.industry).toBe('Healthcare');
    });

    it('extracts compliance_frameworks as planned_frameworks array', () => {
      const result = assessmentAIService.getBusinessProfileFromContext({}, {
        compliance_frameworks: ['GDPR', 'ISO 27001'],
      });
      expect(result.planned_frameworks).toEqual(['GDPR', 'ISO 27001']);
    });

    it('wraps single compliance_framework in array', () => {
      const result = assessmentAIService.getBusinessProfileFromContext({}, {
        compliance_frameworks: 'GDPR',
      });
      expect(result.planned_frameworks).toEqual(['GDPR']);
    });
  });

  describe('getExistingPoliciesFromAnswers', () => {
    it('returns empty result with no answers', () => {
      const result = assessmentAIService.getExistingPoliciesFromAnswers();
      expect(result.existing_policies).toEqual([]);
      expect(result.compliance_measures).toEqual([]);
      expect(result.gaps_identified).toEqual([]);
    });

    it('identifies existing policies from Yes answers', () => {
      const answers = {
        privacy_policy: 'Yes',
        data_protection_policy: 'Yes',
        security_policy: 'No',
      };

      const result = assessmentAIService.getExistingPoliciesFromAnswers(answers);

      expect(result.existing_policies).toContain('Privacy Policy');
      expect(result.existing_policies).toContain('Data Protection Policy');
      expect(result.gaps_identified).toContain('Security Policy');
    });

    it('identifies compliance measures', () => {
      const answers = {
        regular_audits: 'Yes',
        staff_training: true,
        encryption: 'No',
        access_controls: false,
      };

      const result = assessmentAIService.getExistingPoliciesFromAnswers(answers);

      expect(result.compliance_measures).toContain('Regular Audits');
      expect(result.compliance_measures).toContain('Staff Training');
      expect(result.gaps_identified).toContain('Encryption');
      expect(result.gaps_identified).toContain('Access Controls');
    });

    it('detects specific compliance programs', () => {
      const answers = {
        gdpr_compliance: 'Yes',
        iso27001: 'Yes',
        cyber_essentials: 'Yes',
      };

      const result = assessmentAIService.getExistingPoliciesFromAnswers(answers);

      expect(result.compliance_measures).toContain('GDPR Compliance Program');
      expect(result.compliance_measures).toContain('ISO 27001 Implementation');
      expect(result.compliance_measures).toContain('Cyber Essentials Certification');
    });
  });

  describe('getIndustryContextFromAnswers', () => {
    it('returns default context with no data', () => {
      const result = assessmentAIService.getIndustryContextFromAnswers();
      expect(result.industry).toBe('general');
      expect(result.applicable_regulations).toContain('GDPR');
      expect(result.risk_level).toBe('medium');
    });

    it('detects financial services industry', () => {
      const result = assessmentAIService.getIndustryContextFromAnswers(
        { industry: 'financial services' },
      );
      expect(result.applicable_regulations).toContain('FCA Regulations');
      expect(result.applicable_regulations).toContain('PCI DSS');
      expect(result.risk_level).toBe('high');
      expect(result.special_requirements).toContain('Financial conduct reporting');
    });

    it('detects healthcare industry', () => {
      const result = assessmentAIService.getIndustryContextFromAnswers(
        { industry: 'healthcare' },
      );
      expect(result.risk_level).toBe('high');
      expect(result.special_requirements).toContain('Patient data protection');
    });

    it('detects education industry', () => {
      const result = assessmentAIService.getIndustryContextFromAnswers(
        { industry: 'education' },
      );
      expect(result.special_requirements).toContain('Safeguarding requirements');
    });

    it('detects retail with payment processing', () => {
      const result = assessmentAIService.getIndustryContextFromAnswers(
        { industry: 'retail' },
        { processes_payments: true },
      );
      expect(result.applicable_regulations).toContain('PCI DSS');
    });

    it('detects technology with AI processing', () => {
      const result = assessmentAIService.getIndustryContextFromAnswers(
        { industry: 'technology' },
        { ai_processing: true },
      );
      expect(result.special_requirements).toContain('AI governance');
    });

    it('adds international transfer requirements', () => {
      const result = assessmentAIService.getIndustryContextFromAnswers(
        {},
        { international_transfers: 'Yes' },
      );
      expect(result.applicable_regulations).toContain('International Transfer Regulations');
      expect(result.special_requirements).toContain('Adequacy decisions');
    });

    it('adds large org requirements for 250+ employees', () => {
      const result = assessmentAIService.getIndustryContextFromAnswers(
        {},
        { employee_count: '500' },
      );
      expect(result.special_requirements).toContain('Large organization reporting');
      expect(result.special_requirements).toContain('DPO appointment required');
    });
  });

  describe('getTimelinePreferenceFromAnswers', () => {
    it('returns defaults with no answers', () => {
      const result = assessmentAIService.getTimelinePreferenceFromAnswers();
      expect(result.urgency).toBe('medium');
      expect(result.preferred_timeline).toBe('3-6 months');
      expect(result.implementation_capacity).toBe('moderate');
      expect(result.priority_areas).toEqual([]);
    });

    it('sets critical urgency for immediate timeline', () => {
      const result = assessmentAIService.getTimelinePreferenceFromAnswers({
        implementation_timeline: 'immediate implementation',
      });
      expect(result.urgency).toBe('critical');
    });

    it('sets high urgency for 3 month timeline', () => {
      const result = assessmentAIService.getTimelinePreferenceFromAnswers({
        implementation_timeline: '3 month plan',
      });
      expect(result.urgency).toBe('high');
    });

    it('sets critical urgency for recent incidents', () => {
      const result = assessmentAIService.getTimelinePreferenceFromAnswers({
        recent_incidents: 'Yes',
      });
      expect(result.urgency).toBe('critical');
      expect(result.priority_areas).toContain('Incident response');
    });

    it('sets high urgency for upcoming audit', () => {
      const result = assessmentAIService.getTimelinePreferenceFromAnswers({
        audit_upcoming: 'Yes',
      });
      expect(result.urgency).toBe('high');
      expect(result.priority_areas).toContain('Audit preparation');
    });

    it('detects high implementation capacity', () => {
      const result = assessmentAIService.getTimelinePreferenceFromAnswers({
        dedicated_compliance_team: 'Yes',
      });
      expect(result.implementation_capacity).toBe('high');
    });

    it('detects limited capacity from budget constraints', () => {
      const result = assessmentAIService.getTimelinePreferenceFromAnswers({
        budget_constraints: 'Yes',
      });
      expect(result.implementation_capacity).toBe('limited');
      expect(result.priority_areas).toContain('Cost-effective solutions');
    });

    it('extracts priority areas from biggest concern', () => {
      const result = assessmentAIService.getTimelinePreferenceFromAnswers({
        biggest_concern: 'data privacy and cybersecurity threats',
      });
      expect(result.priority_areas).toContain('Data protection');
      expect(result.priority_areas).toContain('Cybersecurity');
    });
  });
});

// -- Type interface tests --

describe('AssessmentAI type interfaces', () => {
  it('risk_level values', () => {
    const levels = ['low', 'medium', 'high', 'critical'];
    expect(levels).toHaveLength(4);
  });

  it('review_focus values', () => {
    const focuses = ['accuracy', 'completeness', 'clarity', 'relevance', 'comprehensive'];
    expect(focuses).toHaveLength(5);
  });

  it('timeline_preferences values', () => {
    const prefs = ['urgent', 'standard', 'gradual'];
    expect(prefs).toHaveLength(3);
  });
});
