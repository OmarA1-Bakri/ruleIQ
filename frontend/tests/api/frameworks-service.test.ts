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

describe('FrameworkService', () => {
  let frameworkService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/frameworks.service');
    frameworkService = serviceMod.frameworkService;
  });

  describe('getFrameworks', () => {
    it('calls GET /frameworks', async () => {
      const mockData = [
        { id: 'gdpr', name: 'GDPR', description: 'General Data Protection Regulation' },
        { id: 'iso27001', name: 'ISO 27001', description: 'Information Security' },
      ];

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await frameworkService.getFrameworks();

      expect(apiClient.get).toHaveBeenCalledWith('/frameworks');
      expect(result).toHaveLength(2);
      expect(result[0].id).toBe('gdpr');
    });
  });

  describe('getFramework', () => {
    it('calls GET /frameworks/:id', async () => {
      const mockData = { id: 'gdpr', name: 'GDPR', description: 'EU privacy regulation' };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await frameworkService.getFramework('gdpr');

      expect(apiClient.get).toHaveBeenCalledWith('/frameworks/gdpr');
      expect(result.name).toBe('GDPR');
    });
  });

  describe('getFrameworkRecommendations', () => {
    it('calls GET /frameworks/recommendations/:businessProfileId', async () => {
      const mockRecs = [
        {
          framework: { id: 'gdpr', name: 'GDPR' },
          relevance_score: 0.95,
          reasons: ['UK data processing', 'Customer PII handling'],
          estimated_effort: '3 months',
          priority: 'high',
        },
      ];

      (apiClient.get as any).mockResolvedValue(mockRecs);

      const result = await frameworkService.getFrameworkRecommendations('bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/frameworks/recommendations/bp-1');
      expect(result).toHaveLength(1);
      expect(result[0].relevance_score).toBe(0.95);
      expect(result[0].priority).toBe('high');
    });
  });

  describe('getFrameworkControls', () => {
    it('calls GET /frameworks/:id/controls', async () => {
      const mockData = {
        framework: 'GDPR',
        total_controls: 2,
        controls: [
          {
            control_id: 'gdpr-5.1',
            control_name: 'Lawful Processing',
            description: 'Processing must have a lawful basis',
            category: 'Data Processing',
            priority: 'high',
            evidence_required: ['Processing records', 'Legal basis documentation'],
          },
          {
            control_id: 'gdpr-5.2',
            control_name: 'Purpose Limitation',
            description: 'Data must be collected for specified purposes',
            category: 'Data Processing',
            priority: 'high',
            evidence_required: ['Privacy notices'],
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await frameworkService.getFrameworkControls('gdpr');

      expect(apiClient.get).toHaveBeenCalledWith('/frameworks/gdpr/controls');
      expect(result.total_controls).toBe(2);
      expect(result.controls).toHaveLength(2);
      expect(result.controls[0].control_id).toBe('gdpr-5.1');
    });
  });

  describe('getFrameworkImplementationGuide', () => {
    it('calls GET /frameworks/:id/implementation-guide', async () => {
      const mockGuide = {
        framework: 'ISO 27001',
        estimated_duration: '6 months',
        phases: [
          {
            phase: 1,
            name: 'Gap Analysis',
            duration: '4 weeks',
            tasks: ['Assess current state', 'Identify gaps'],
            deliverables: ['Gap analysis report'],
          },
        ],
        resources_required: ['Security team', 'External consultant'],
        key_milestones: ['Gap analysis complete', 'Controls implemented'],
      };

      (apiClient.get as any).mockResolvedValue(mockGuide);

      const result = await frameworkService.getFrameworkImplementationGuide('iso27001');

      expect(apiClient.get).toHaveBeenCalledWith('/frameworks/iso27001/implementation-guide');
      expect(result.estimated_duration).toBe('6 months');
      expect(result.phases).toHaveLength(1);
      expect(result.phases[0].name).toBe('Gap Analysis');
    });
  });

  describe('getFrameworkComplianceStatus', () => {
    it('calls GET /frameworks/:id/compliance-status with business_profile_id', async () => {
      const mockData = {
        framework: 'GDPR',
        overall_compliance: 78,
        by_category: { 'Data Processing': 85, 'Data Rights': 70 },
        controls_status: {
          compliant: 15,
          partial: 5,
          non_compliant: 3,
          not_assessed: 2,
        },
        last_assessment_date: '2025-06-01',
        next_review_date: '2025-12-01',
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await frameworkService.getFrameworkComplianceStatus('gdpr', 'bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/frameworks/gdpr/compliance-status', {
        params: { business_profile_id: 'bp-1' },
      });
      expect(result.overall_compliance).toBe(78);
      expect(result.controls_status.compliant).toBe(15);
    });
  });

  describe('compareFrameworks', () => {
    it('calls POST /frameworks/compare', async () => {
      const mockData = {
        frameworks: [
          {
            id: 'gdpr',
            name: 'GDPR',
            control_count: 99,
            estimated_effort: '6 months',
            industry_alignment: ['tech', 'finance'],
            key_features: ['Data protection', 'Privacy rights'],
          },
          {
            id: 'iso27001',
            name: 'ISO 27001',
            control_count: 114,
            estimated_effort: '8 months',
            industry_alignment: ['tech', 'healthcare'],
            key_features: ['Information security', 'Risk management'],
          },
        ],
        overlap_analysis: {
          common_controls: 45,
          unique_controls: { gdpr: 54, iso27001: 69 },
          compatibility_score: 0.72,
        },
        recommendation: 'Implement ISO 27001 first',
      };

      (apiClient.post as any).mockResolvedValue(mockData);

      const result = await frameworkService.compareFrameworks(['gdpr', 'iso27001']);

      expect(apiClient.post).toHaveBeenCalledWith('/frameworks/compare', {
        framework_ids: ['gdpr', 'iso27001'],
      });
      expect(result.frameworks).toHaveLength(2);
      expect(result.overlap_analysis.common_controls).toBe(45);
      expect(result.overlap_analysis.compatibility_score).toBe(0.72);
    });
  });

  describe('getFrameworkMaturityAssessment', () => {
    it('calls GET /frameworks/:id/maturity-assessment', async () => {
      const mockData = {
        framework: 'ISO 27001',
        maturity_level: 'developing',
        maturity_score: 2.5,
        strengths: ['Access control', 'Encryption'],
        weaknesses: ['Incident response', 'Business continuity'],
        improvement_areas: [
          {
            area: 'Incident Response',
            current_level: 2,
            target_level: 4,
            recommendations: ['Create IR playbooks', 'Conduct tabletop exercises'],
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await frameworkService.getFrameworkMaturityAssessment('iso27001', 'bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/frameworks/iso27001/maturity-assessment', {
        params: { business_profile_id: 'bp-1' },
      });
      expect(result.maturity_level).toBe('developing');
      expect(result.maturity_score).toBe(2.5);
      expect(result.improvement_areas).toHaveLength(1);
    });
  });

  describe('getDefaultFramework', () => {
    it('returns the freemium default framework', async () => {
      const framework = frameworkService.getDefaultFramework();

      expect(framework.id).toBe('freemium-default');
      expect(framework.name).toBe('Basic Compliance Assessment');
      expect(framework.scoringMethod).toBe('percentage');
      expect(framework.passingScore).toBe(70);
      expect(framework.estimatedDuration).toBe(15);
      expect(framework.tags).toContain('freemium');
    });

    it('has 4 sections', async () => {
      const framework = frameworkService.getDefaultFramework();

      expect(framework.sections).toHaveLength(4);
      expect(framework.sections[0].id).toBe('data-protection');
      expect(framework.sections[1].id).toBe('security-controls');
      expect(framework.sections[2].id).toBe('access-management');
      expect(framework.sections[3].id).toBe('documentation');
    });

    it('sections are ordered correctly', async () => {
      const framework = frameworkService.getDefaultFramework();

      for (let i = 0; i < framework.sections.length; i++) {
        expect(framework.sections[i].order).toBe(i + 1);
      }
    });

    it('each section has questions', async () => {
      const framework = frameworkService.getDefaultFramework();

      for (const section of framework.sections) {
        expect(section.questions.length).toBeGreaterThan(0);
        for (const q of section.questions) {
          expect(q.id).toBeTruthy();
          expect(q.text).toBeTruthy();
          expect(q.type).toBeTruthy();
          expect(q.section).toBe(section.id);
        }
      }
    });
  });
});

// ── normalizeSectionId tests ─────────────────────────────

describe('normalizeSectionId', () => {
  let normalizeSectionId: any;

  beforeEach(async () => {
    vi.resetModules();
    const mod = await import('@/lib/api/frameworks.service');
    normalizeSectionId = mod.normalizeSectionId;
  });

  it('converts to lowercase', async () => {
    expect(normalizeSectionId('Data-Protection')).toBe('data-protection');
    expect(normalizeSectionId('ACCESS')).toBe('access');
  });

  it('replaces spaces with hyphens', async () => {
    expect(normalizeSectionId('data protection')).toBe('data-protection');
    expect(normalizeSectionId('access management controls')).toBe('access-management-controls');
  });

  it('replaces underscores with hyphens', async () => {
    expect(normalizeSectionId('data_protection')).toBe('data-protection');
    expect(normalizeSectionId('security_controls')).toBe('security-controls');
  });

  it('removes non-alphanumeric characters except hyphens', async () => {
    expect(normalizeSectionId('data.protection!')).toBe('dataprotection');
    expect(normalizeSectionId('section@#$123')).toBe('section123');
  });

  it('handles mixed cases', async () => {
    expect(normalizeSectionId('Data_Protection Rules')).toBe('data-protection-rules');
  });
});
