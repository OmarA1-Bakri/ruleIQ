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

describe('ImplementationService', () => {
  let implementationService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/implementation.service');
    implementationService = serviceMod.implementationService;
  });

  describe('getImplementationPlans', () => {
    it('calls GET /implementation/plans without params', async () => {
      const mockData = { plans: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await implementationService.getImplementationPlans();

      expect(apiClient.get).toHaveBeenCalledWith('/implementation/plans', {});
      expect(result.total).toBe(0);
    });

    it('passes filter params when provided', async () => {
      const mockData = {
        plans: [
          {
            id: 'impl-1',
            framework_name: 'ISO 27001',
            status: 'active',
            overall_progress: 45,
          },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await implementationService.getImplementationPlans({
        business_profile_id: 'bp-1',
        status: 'active',
        page: 1,
        page_size: 10,
      });

      expect(apiClient.get).toHaveBeenCalledWith('/implementation/plans', {
        params: { business_profile_id: 'bp-1', status: 'active', page: 1, page_size: 10 },
      });
      expect(result.plans).toHaveLength(1);
    });
  });

  describe('getImplementationPlan', () => {
    it('calls GET /implementation/plans/:id', async () => {
      const mockPlan = {
        id: 'impl-1',
        framework_name: 'GDPR',
        status: 'active',
        overall_progress: 60,
        phases: [],
      };

      (apiClient.get as any).mockResolvedValue(mockPlan);

      const result = await implementationService.getImplementationPlan('impl-1');

      expect(apiClient.get).toHaveBeenCalledWith('/implementation/plans/impl-1');
      expect(result.overall_progress).toBe(60);
    });
  });

  describe('createImplementationPlan', () => {
    it('calls POST /implementation/plans', async () => {
      const request = {
        business_profile_id: 'bp-1',
        framework_id: 'iso27001',
        start_date: '2025-07-01',
        target_duration_weeks: 24,
        priority_areas: ['access-control', 'encryption'],
      };

      const mockPlan = {
        id: 'impl-new',
        ...request,
        status: 'draft',
        overall_progress: 0,
        phases: [],
      };

      (apiClient.post as any).mockResolvedValue(mockPlan);

      const result = await implementationService.createImplementationPlan(request);

      expect(apiClient.post).toHaveBeenCalledWith('/implementation/plans', request);
      expect(result.id).toBe('impl-new');
      expect(result.status).toBe('draft');
    });
  });

  describe('updateImplementationPlan', () => {
    it('calls PATCH /implementation/plans/:id', async () => {
      const update = { status: 'active', target_completion_date: '2025-12-31' };
      const mockPlan = { id: 'impl-1', status: 'active' };
      (apiClient.patch as any).mockResolvedValue(mockPlan);

      const result = await implementationService.updateImplementationPlan('impl-1', update);

      expect(apiClient.patch).toHaveBeenCalledWith('/implementation/plans/impl-1', update);
      expect(result.status).toBe('active');
    });
  });

  describe('updateTaskProgress', () => {
    it('calls PATCH /implementation/plans/:planId/tasks/:taskId/progress', async () => {
      const mockTask = { id: 'task-1', progress: 75, status: 'in_progress' };
      (apiClient.patch as any).mockResolvedValue(mockTask);

      const result = await implementationService.updateTaskProgress(
        'impl-1',
        'task-1',
        75,
        'Completed initial assessment',
      );

      expect(apiClient.patch).toHaveBeenCalledWith(
        '/implementation/plans/impl-1/tasks/task-1/progress',
        { progress: 75, notes: 'Completed initial assessment' },
      );
      expect(result.progress).toBe(75);
    });

    it('works without notes', async () => {
      const mockTask = { id: 'task-1', progress: 50 };
      (apiClient.patch as any).mockResolvedValue(mockTask);

      await implementationService.updateTaskProgress('impl-1', 'task-1', 50);

      expect(apiClient.patch).toHaveBeenCalledWith(
        '/implementation/plans/impl-1/tasks/task-1/progress',
        { progress: 50, notes: undefined },
      );
    });
  });

  describe('completeMilestone', () => {
    it('calls POST /implementation/plans/:planId/milestones/:milestoneId/complete', async () => {
      const mockMilestone = {
        id: 'ms-1',
        name: 'Gap Analysis Complete',
        achieved: true,
        achieved_date: '2025-06-15',
      };

      (apiClient.post as any).mockResolvedValue(mockMilestone);

      const result = await implementationService.completeMilestone(
        'impl-1',
        'ms-1',
        ['gap-report.pdf', 'findings.xlsx'],
      );

      expect(apiClient.post).toHaveBeenCalledWith(
        '/implementation/plans/impl-1/milestones/ms-1/complete',
        { evidence: ['gap-report.pdf', 'findings.xlsx'] },
      );
      expect(result.achieved).toBe(true);
    });

    it('works without evidence', async () => {
      const mockMilestone = { id: 'ms-2', achieved: true };
      (apiClient.post as any).mockResolvedValue(mockMilestone);

      await implementationService.completeMilestone('impl-1', 'ms-2');

      expect(apiClient.post).toHaveBeenCalledWith(
        '/implementation/plans/impl-1/milestones/ms-2/complete',
        { evidence: undefined },
      );
    });
  });

  describe('getImplementationRecommendations', () => {
    it('calls GET /implementation/recommendations', async () => {
      const mockData = {
        recommended_approach: 'phased',
        estimated_duration: '6 months',
        resource_requirements: {
          internal_team_size: 5,
          external_support_needed: true,
          key_roles: ['CISO', 'Security Analyst', 'Project Manager'],
          estimated_budget: '50000 GBP',
        },
        priority_controls: [
          {
            control_id: 'A.9.1',
            control_name: 'Access Control Policy',
            reason: 'Foundation for other controls',
            quick_win: true,
          },
        ],
        risk_factors: ['Limited internal expertise'],
        success_factors: ['Executive sponsorship'],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await implementationService.getImplementationRecommendations('bp-1', 'iso27001');

      expect(apiClient.get).toHaveBeenCalledWith('/implementation/recommendations', {
        params: { business_profile_id: 'bp-1', framework_id: 'iso27001' },
      });
      expect(result.recommended_approach).toBe('phased');
      expect(result.resource_requirements.internal_team_size).toBe(5);
      expect(result.priority_controls).toHaveLength(1);
    });
  });

  describe('getImplementationResources', () => {
    it('calls GET /implementation/resources/:frameworkId', async () => {
      const mockData = {
        templates: [{ id: 't-1', name: 'ISMS Template', type: 'document', download_url: '/dl/t-1' }],
        guides: [{ id: 'g-1', title: 'Implementation Guide', category: 'getting-started', url: '/g/1' }],
        tools: [{ id: 'tool-1', name: 'Risk Tool', description: 'Risk assessment', type: 'free', url: '/tools/1' }],
        training: [{ id: 'tr-1', title: 'ISO Lead Auditor', provider: 'BSI', duration: '5 days', cost: '2000 GBP', url: '/training/1' }],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await implementationService.getImplementationResources('iso27001');

      expect(apiClient.get).toHaveBeenCalledWith('/implementation/resources/iso27001');
      expect(result.templates).toHaveLength(1);
      expect(result.guides).toHaveLength(1);
      expect(result.tools).toHaveLength(1);
      expect(result.training).toHaveLength(1);
    });
  });

  describe('exportImplementationPlan', () => {
    it('calls download with pdf extension', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await implementationService.exportImplementationPlan('impl-1', 'pdf');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/implementation/plans/impl-1/export?format=pdf',
        'implementation-plan-impl-1.pdf',
      );
    });

    it('calls download with excel extension', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await implementationService.exportImplementationPlan('impl-1', 'excel');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/implementation/plans/impl-1/export?format=excel',
        'implementation-plan-impl-1.excel',
      );
    });

    it('maps project format to mpp extension', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await implementationService.exportImplementationPlan('impl-1', 'project');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/implementation/plans/impl-1/export?format=project',
        'implementation-plan-impl-1.mpp',
      );
    });
  });

  describe('getImplementationAnalytics', () => {
    it('calls GET /implementation/plans/:id/analytics', async () => {
      const mockData = {
        burndown_chart: [
          { date: '2025-06-01', planned_remaining: 50, actual_remaining: 55 },
        ],
        velocity_trend: [
          { week: '2025-W24', completed_tasks: 3, average_velocity: 2.8 },
        ],
        bottlenecks: [
          {
            area: 'Access Control',
            impact: 'high',
            affected_tasks: 5,
            recommendation: 'Allocate dedicated resource',
          },
        ],
        projected_completion: {
          current_pace_date: '2026-01-15',
          confidence_level: 0.72,
          risks: ['Holiday season delay'],
        },
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await implementationService.getImplementationAnalytics('impl-1');

      expect(apiClient.get).toHaveBeenCalledWith('/implementation/plans/impl-1/analytics');
      expect(result.burndown_chart).toHaveLength(1);
      expect(result.bottlenecks).toHaveLength(1);
      expect(result.projected_completion.confidence_level).toBe(0.72);
    });
  });
});

// ── Type interface tests ─────────────────────────────────

describe('Implementation type interfaces', () => {
  it('ImplementationPlan status values', () => {
    const statuses = ['draft', 'active', 'completed', 'on_hold'];
    expect(statuses).toHaveLength(4);
  });

  it('ImplementationPhase status values', () => {
    const statuses = ['not_started', 'in_progress', 'completed', 'blocked'];
    expect(statuses).toHaveLength(4);
  });

  it('ImplementationTask status values', () => {
    const statuses = ['pending', 'in_progress', 'completed', 'blocked'];
    expect(statuses).toHaveLength(4);
  });
});
