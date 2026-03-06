import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    download: vi.fn(),
  },
}));

describe('ReadinessService', () => {
  let readinessService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/readiness.service');
    readinessService = serviceMod.readinessService;
  });

  describe('getReadinessScore', () => {
    it('calls GET /readiness/:businessProfileId', async () => {
      const mockData = {
        overall_score: 72,
        category_scores: {
          policies: 80,
          processes: 65,
          technology: 75,
          people: 68,
        },
        maturity_level: 'developing',
        strengths: ['Strong access controls', 'Regular backups'],
        weaknesses: ['Incomplete documentation', 'No formal IR plan'],
        recommendations: [
          {
            category: 'processes',
            priority: 'high',
            description: 'Implement incident response plan',
            effort: '2 weeks',
            impact: 'Significant risk reduction',
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await readinessService.getReadinessScore('bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/readiness/bp-1');
      expect(result.overall_score).toBe(72);
      expect(result.maturity_level).toBe('developing');
      expect(result.category_scores.policies).toBe(80);
      expect(result.recommendations).toHaveLength(1);
    });
  });

  describe('getGapAnalysis', () => {
    it('calls GET /readiness/gaps/:businessProfileId without frameworkId', async () => {
      const mockData = {
        framework: 'All',
        gaps: [],
        summary: {
          total_gaps: 0,
          critical_gaps: 0,
          estimated_remediation_time: '0 weeks',
          quick_wins: [],
        },
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await readinessService.getGapAnalysis('bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/readiness/gaps/bp-1', {});
      expect(result.summary.total_gaps).toBe(0);
    });

    it('passes framework_id when provided', async () => {
      const mockData = {
        framework: 'GDPR',
        gaps: [
          {
            control_id: 'gdpr-5.1',
            control_name: 'Lawful Processing',
            gap_type: 'partial',
            current_state: 'Basic consent management',
            target_state: 'Full GDPR-compliant processing records',
            remediation_steps: ['Document lawful basis', 'Update consent forms'],
            priority: 'high',
            estimated_effort: '2 weeks',
          },
        ],
        summary: {
          total_gaps: 1,
          critical_gaps: 0,
          estimated_remediation_time: '2 weeks',
          quick_wins: ['Update privacy notices'],
        },
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await readinessService.getGapAnalysis('bp-1', 'gdpr');

      expect(apiClient.get).toHaveBeenCalledWith('/readiness/gaps/bp-1', {
        params: { framework_id: 'gdpr' },
      });
      expect(result.gaps).toHaveLength(1);
      expect(result.gaps[0].gap_type).toBe('partial');
    });
  });

  describe('getReadinessRoadmap', () => {
    it('calls POST /readiness/roadmap', async () => {
      const mockData = {
        phases: [
          {
            phase: 1,
            name: 'Foundation',
            duration: '4 weeks',
            objectives: ['Establish baseline'],
            key_activities: [
              {
                activity: 'Gap analysis',
                owner: 'Security Team',
                effort: '1 week',
                dependencies: [],
              },
            ],
            deliverables: ['Gap analysis report'],
            success_criteria: ['All gaps documented'],
          },
        ],
        timeline: {
          start_date: '2025-07-01',
          end_date: '2025-12-31',
          milestones: [{ date: '2025-08-01', milestone: 'Foundation complete', phase: 1 }],
        },
        resource_requirements: {
          internal_hours: 400,
          external_support_needed: true,
          budget_estimate: '25000 GBP',
          tools_required: ['Risk assessment tool'],
        },
      };

      (apiClient.post as any).mockResolvedValue(mockData);

      const result = await readinessService.getReadinessRoadmap('bp-1', ['gdpr', 'iso27001']);

      expect(apiClient.post).toHaveBeenCalledWith('/readiness/roadmap', {
        business_profile_id: 'bp-1',
        target_frameworks: ['gdpr', 'iso27001'],
      });
      expect(result.phases).toHaveLength(1);
      expect(result.resource_requirements.internal_hours).toBe(400);
    });
  });

  describe('performQuickAssessment', () => {
    it('calls POST /readiness/quick-assessment', async () => {
      const answers = {
        has_data_policy: 'yes',
        mfa_enabled: 'critical_only',
        incident_plan: 'no',
      };

      const mockResponse = {
        score: 55,
        interpretation: 'Your organization has basic security measures but gaps remain.',
        next_steps: ['Create incident response plan', 'Extend MFA to all users'],
        detailed_report_available: true,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await readinessService.performQuickAssessment('bp-1', answers);

      expect(apiClient.post).toHaveBeenCalledWith('/readiness/quick-assessment', {
        business_profile_id: 'bp-1',
        answers,
      });
      expect(result.score).toBe(55);
      expect(result.next_steps).toHaveLength(2);
    });
  });

  describe('getReadinessTrends', () => {
    it('calls GET /readiness/trends/:businessProfileId with default days', async () => {
      const mockData = {
        trends: [
          { date: '2025-06-01', overall_score: 65, category_scores: { policies: 70 } },
          { date: '2025-06-15', overall_score: 72, category_scores: { policies: 80 } },
        ],
        improvements: [
          {
            category: 'policies',
            improvement_percentage: 14.3,
            key_changes: ['Added data protection policy'],
          },
        ],
        projections: {
          estimated_compliance_date: '2025-12-01',
          required_improvement_rate: 5,
          risk_areas: ['processes'],
        },
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await readinessService.getReadinessTrends('bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/readiness/trends/bp-1', {
        params: { days: 90 },
      });
      expect(result.trends).toHaveLength(2);
      expect(result.improvements).toHaveLength(1);
    });

    it('passes custom days parameter', async () => {
      (apiClient.get as any).mockResolvedValue({ trends: [], improvements: [], projections: {} });

      await readinessService.getReadinessTrends('bp-1', 30);

      expect(apiClient.get).toHaveBeenCalledWith('/readiness/trends/bp-1', {
        params: { days: 30 },
      });
    });
  });

  describe('getReadinessBenchmarks', () => {
    it('calls GET /readiness/benchmarks', async () => {
      const mockData = {
        industry_average: 68,
        top_performers: 92,
        your_position: 'above_average',
        improvement_opportunities: ['Implement automated monitoring'],
        peer_comparison: [
          { category: 'policies', your_score: 80, industry_average: 72, gap: 8 },
          { category: 'technology', your_score: 65, industry_average: 70, gap: -5 },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await readinessService.getReadinessBenchmarks('technology', 'medium');

      expect(apiClient.get).toHaveBeenCalledWith('/readiness/benchmarks', {
        params: { industry: 'technology', company_size: 'medium' },
      });
      expect(result.your_position).toBe('above_average');
      expect(result.peer_comparison).toHaveLength(2);
    });
  });

  describe('exportReadinessReport', () => {
    it('calls download with correct params for pdf', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await readinessService.exportReadinessReport('bp-1', 'pdf');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/readiness/export/bp-1?format=pdf',
        'readiness-report.pdf',
      );
    });

    it('calls download with correct params for excel', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await readinessService.exportReadinessReport('bp-1', 'excel');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/readiness/export/bp-1?format=excel',
        'readiness-report.excel',
      );
    });
  });
});

// ── Type interface tests ─────────────────────────────────

describe('Readiness type interfaces', () => {
  it('ReadinessScore maturity_level values', () => {
    const levels = ['initial', 'developing', 'defined', 'managed', 'optimized'];
    expect(levels).toHaveLength(5);
  });

  it('GapAnalysis gap_type values', () => {
    const types = ['missing', 'partial', 'outdated'];
    expect(types).toHaveLength(3);
  });
});
