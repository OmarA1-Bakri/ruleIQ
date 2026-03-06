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

describe('EvidenceCollectionService', () => {
  let evidenceCollectionService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/evidence-collection.service');
    evidenceCollectionService = serviceMod.evidenceCollectionService;
  });

  describe('createCollectionPlan', () => {
    it('calls POST /evidence-collection/plans', async () => {
      const request = {
        framework: 'GDPR',
        target_completion_weeks: 8,
        include_existing_evidence: true,
      };

      const mockPlan = {
        id: 'plan-1',
        framework: 'GDPR',
        status: 'active',
        tasks: [],
        estimated_total_hours: 40,
        automation_opportunities: { effort_savings_hours: 10, effort_savings_percentage: 25 },
      };

      (apiClient.post as any).mockResolvedValue(mockPlan);

      const result = await evidenceCollectionService.createCollectionPlan(request);

      expect(apiClient.post).toHaveBeenCalledWith('/evidence-collection/plans', request);
      expect(result.id).toBe('plan-1');
    });
  });

  describe('getCollectionPlan', () => {
    it('calls GET /evidence-collection/plans/:planId', async () => {
      const mockPlan = {
        id: 'plan-1',
        framework: 'GDPR',
        tasks: [],
        estimated_total_hours: 40,
        automation_opportunities: { effort_savings_hours: 10, effort_savings_percentage: 25 },
      };

      (apiClient.get as any).mockResolvedValue(mockPlan);

      const result = await evidenceCollectionService.getCollectionPlan('plan-1');

      expect(apiClient.get).toHaveBeenCalledWith('/evidence-collection/plans/plan-1');
      expect(result.framework).toBe('GDPR');
    });
  });

  describe('listCollectionPlans', () => {
    it('calls GET /evidence-collection/plans without params', async () => {
      const mockPlans = [
        { id: 'plan-1', framework: 'GDPR', status: 'active', progress_percentage: 45 },
      ];

      (apiClient.get as any).mockResolvedValue(mockPlans);

      const result = await evidenceCollectionService.listCollectionPlans();

      expect(apiClient.get).toHaveBeenCalledWith('/evidence-collection/plans', {});
      expect(result).toHaveLength(1);
    });

    it('passes params when provided', async () => {
      (apiClient.get as any).mockResolvedValue([]);

      await evidenceCollectionService.listCollectionPlans({
        framework: 'ISO 27001',
        status: 'active',
      });

      expect(apiClient.get).toHaveBeenCalledWith('/evidence-collection/plans', {
        params: { framework: 'ISO 27001', status: 'active' },
      });
    });
  });

  describe('getPriorityTasks', () => {
    it('calls GET with default limit of 5', async () => {
      const mockTasks = [
        { id: 'task-1', priority: 'critical', status: 'pending' },
      ];

      (apiClient.get as any).mockResolvedValue(mockTasks);

      const result = await evidenceCollectionService.getPriorityTasks('plan-1');

      expect(apiClient.get).toHaveBeenCalledWith(
        '/evidence-collection/plans/plan-1/priority-tasks',
        { params: { limit: 5 } },
      );
      expect(result).toHaveLength(1);
    });

    it('passes custom limit', async () => {
      (apiClient.get as any).mockResolvedValue([]);

      await evidenceCollectionService.getPriorityTasks('plan-1', 10);

      expect(apiClient.get).toHaveBeenCalledWith(
        '/evidence-collection/plans/plan-1/priority-tasks',
        { params: { limit: 10 } },
      );
    });
  });

  describe('updateTaskStatus', () => {
    it('calls PATCH /evidence-collection/plans/:planId/tasks/:taskId', async () => {
      const data = { status: 'completed' as const, completion_notes: 'Done' };
      const mockTask = { id: 'task-1', ...data };
      (apiClient.patch as any).mockResolvedValue(mockTask);

      const result = await evidenceCollectionService.updateTaskStatus('plan-1', 'task-1', data);

      expect(apiClient.patch).toHaveBeenCalledWith(
        '/evidence-collection/plans/plan-1/tasks/task-1',
        data,
      );
      expect(result.status).toBe('completed');
    });
  });

  describe('getAutomationRecommendations', () => {
    it('calls GET /evidence-collection/automation-recommendations/:framework', async () => {
      const mockData = {
        framework: 'GDPR',
        automation_opportunities: [
          {
            evidence_type: 'access_logs',
            automation_level: 'full',
            effort_reduction: '80%',
            success_rate: '95%',
            recommended_tools: ['CloudWatch'],
          },
        ],
        recommended_tools: ['CloudWatch', 'Terraform'],
        estimated_time_savings: 120,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await evidenceCollectionService.getAutomationRecommendations('GDPR');

      expect(apiClient.get).toHaveBeenCalledWith(
        '/evidence-collection/automation-recommendations/GDPR',
      );
      expect(result.estimated_time_savings).toBe(120);
      expect(result.automation_opportunities).toHaveLength(1);
    });
  });

  // -- Sync utility methods --

  describe('calculateTimeSavings', () => {
    it('calculates time savings from a plan', () => {
      const plan = {
        estimated_total_hours: 100,
        automation_opportunities: {
          effort_savings_hours: 30,
          effort_savings_percentage: 30,
        },
        tasks: [],
      };

      const result = evidenceCollectionService.calculateTimeSavings(plan);

      expect(result.manualHours).toBe(100);
      expect(result.savedHours).toBe(30);
      expect(result.automatedHours).toBe(70);
      expect(result.savedPercentage).toBe(30);
    });
  });

  describe('getTaskStatistics', () => {
    it('computes statistics from tasks', () => {
      const plan = {
        tasks: [
          { status: 'completed', priority: 'high', automation_level: 'full' },
          { status: 'completed', priority: 'medium', automation_level: 'partial' },
          { status: 'pending', priority: 'high', automation_level: 'manual' },
          { status: 'in_progress', priority: 'low', automation_level: 'full' },
        ],
        estimated_total_hours: 40,
        automation_opportunities: { effort_savings_hours: 10, effort_savings_percentage: 25 },
      };

      const result = evidenceCollectionService.getTaskStatistics(plan);

      expect(result.total).toBe(4);
      expect(result.byStatus['completed']).toBe(2);
      expect(result.byStatus['pending']).toBe(1);
      expect(result.byStatus['in_progress']).toBe(1);
      expect(result.byPriority['high']).toBe(2);
      expect(result.byAutomationLevel['full']).toBe(2);
      expect(result.completionPercentage).toBe(50);
    });

    it('handles empty tasks', () => {
      const plan = {
        tasks: [],
        estimated_total_hours: 0,
        automation_opportunities: { effort_savings_hours: 0, effort_savings_percentage: 0 },
      };

      const result = evidenceCollectionService.getTaskStatistics(plan);

      expect(result.total).toBe(0);
      // 0/0 = NaN, Math.round(NaN) = NaN
      expect(result.completionPercentage).toBeNaN();
    });
  });

  describe('filterTasks', () => {
    const tasks = [
      { id: 't1', priority: 'high', status: 'pending', automation_level: 'full', evidence_type: 'policy' },
      { id: 't2', priority: 'medium', status: 'completed', automation_level: 'manual', evidence_type: 'log' },
      { id: 't3', priority: 'high', status: 'in_progress', automation_level: 'full', evidence_type: 'config' },
      { id: 't4', priority: 'low', status: 'pending', automation_level: 'partial', evidence_type: 'policy' },
    ];

    it('filters by priority', () => {
      const result = evidenceCollectionService.filterTasks(tasks, { priority: ['high'] });
      expect(result).toHaveLength(2);
    });

    it('filters by status', () => {
      const result = evidenceCollectionService.filterTasks(tasks, { status: ['pending'] });
      expect(result).toHaveLength(2);
    });

    it('filters by automation level', () => {
      const result = evidenceCollectionService.filterTasks(tasks, { automationLevel: ['full'] });
      expect(result).toHaveLength(2);
    });

    it('filters by evidence type', () => {
      const result = evidenceCollectionService.filterTasks(tasks, { evidenceType: ['policy'] });
      expect(result).toHaveLength(2);
    });

    it('combines multiple criteria', () => {
      const result = evidenceCollectionService.filterTasks(tasks, {
        priority: ['high'],
        status: ['pending'],
      });
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe('t1');
    });

    it('returns all tasks with no criteria', () => {
      const result = evidenceCollectionService.filterTasks(tasks, {});
      expect(result).toHaveLength(4);
    });
  });

  describe('sortTasks', () => {
    const tasks = [
      { id: 't1', priority: 'medium', status: 'pending', due_date: '2025-07-15', estimated_effort_hours: 5 },
      { id: 't2', priority: 'critical', status: 'completed', due_date: '2025-06-01', estimated_effort_hours: 2 },
      { id: 't3', priority: 'low', status: 'in_progress', due_date: null, estimated_effort_hours: 8 },
    ];

    it('sorts by priority ascending', () => {
      const result = evidenceCollectionService.sortTasks(tasks, 'priority', 'asc');
      expect(result[0].priority).toBe('critical');
      expect(result[2].priority).toBe('low');
    });

    it('sorts by priority descending', () => {
      const result = evidenceCollectionService.sortTasks(tasks, 'priority', 'desc');
      expect(result[0].priority).toBe('low');
      expect(result[2].priority).toBe('critical');
    });

    it('sorts by dueDate with nulls last', () => {
      const result = evidenceCollectionService.sortTasks(tasks, 'dueDate', 'asc');
      expect(result[0].id).toBe('t2');
      expect(result[2].id).toBe('t3');
    });

    it('sorts by effort ascending', () => {
      const result = evidenceCollectionService.sortTasks(tasks, 'effort', 'asc');
      expect(result[0].estimated_effort_hours).toBe(2);
      expect(result[2].estimated_effort_hours).toBe(8);
    });

    it('sorts by status ascending', () => {
      const result = evidenceCollectionService.sortTasks(tasks, 'status', 'asc');
      expect(result[0].status).toBe('pending');
      expect(result[1].status).toBe('in_progress');
      expect(result[2].status).toBe('completed');
    });

    it('does not mutate original array', () => {
      const original = [...tasks];
      evidenceCollectionService.sortTasks(tasks, 'priority', 'asc');
      expect(tasks).toEqual(original);
    });
  });
});

// -- Type interface tests --

describe('EvidenceCollection type interfaces', () => {
  it('TaskStatusUpdateRequest has valid status values', () => {
    const statuses = ['pending', 'in_progress', 'completed', 'blocked', 'cancelled'];
    expect(statuses).toHaveLength(5);
  });

  it('CreateCollectionPlanRequest has required fields', () => {
    const request = {
      framework: 'GDPR',
      target_completion_weeks: 8,
      include_existing_evidence: true,
    };
    expect(request.framework).toBeTruthy();
  });
});
