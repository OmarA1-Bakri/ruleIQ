import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the evidence collection service
vi.mock('@/lib/api/evidence-collection.service', () => ({
  evidenceCollectionService: {
    createCollectionPlan: vi.fn(),
    getCollectionPlan: vi.fn(),
    listCollectionPlans: vi.fn(),
    getPriorityTasks: vi.fn(),
    updateTaskStatus: vi.fn(),
    filterTasks: vi.fn((tasks: any[]) => tasks),
    sortTasks: vi.fn((tasks: any[]) => tasks),
    getTaskStatistics: vi.fn(),
    calculateTimeSavings: vi.fn(),
  },
}));

function createMockPlan(overrides: Record<string, any> = {}) {
  return {
    plan_id: 'plan-1',
    framework: 'GDPR',
    status: 'active',
    total_tasks: 10,
    completed_tasks: 3,
    estimated_total_hours: 40,
    completion_target_date: '2025-12-31',
    created_at: '2025-06-01',
    tasks: [
      {
        task_id: 'task-1',
        title: 'Collect consent logs',
        priority: 'high',
        status: 'pending',
        effort_hours: 4,
      },
      {
        task_id: 'task-2',
        title: 'Upload DPA',
        priority: 'medium',
        status: 'completed',
        effort_hours: 2,
      },
    ],
    ...overrides,
  };
}

function createMockPlanSummary(overrides: Record<string, any> = {}) {
  return {
    id: 'plan-1',
    framework: 'GDPR',
    status: 'active',
    progress_percentage: 30,
    total_tasks: 10,
    completed_tasks: 3,
    estimated_total_hours: 40,
    completion_target_date: '2025-12-31',
    created_at: '2025-06-01',
    ...overrides,
  };
}

async function getStore() {
  const mod = await import('@/lib/stores/evidence-collection.store');
  return mod.useEvidenceCollectionStore;
}

async function getMockedService() {
  const mod = await import('@/lib/api/evidence-collection.service');
  return mod.evidenceCollectionService as Record<string, ReturnType<typeof vi.fn>>;
}

describe('Evidence Collection Store', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    localStorage.clear();
  });

  // ── Initial State ──────────────────────────────────────

  describe('initial state', () => {
    it('has empty plans array', async () => {
      const useStore = await getStore();
      expect(useStore.getState().plans).toEqual([]);
    });

    it('has null currentPlan', async () => {
      const useStore = await getStore();
      expect(useStore.getState().currentPlan).toBeNull();
    });

    it('has empty priorityTasks', async () => {
      const useStore = await getStore();
      expect(useStore.getState().priorityTasks).toEqual([]);
    });

    it('has all loading flags false', async () => {
      const useStore = await getStore();
      const state = useStore.getState();
      expect(state.isLoading).toBe(false);
      expect(state.isCreatingPlan).toBe(false);
      expect(state.isUpdatingTask).toBe(false);
    });

    it('has null error', async () => {
      const useStore = await getStore();
      expect(useStore.getState().error).toBeNull();
    });

    it('has default sort settings', async () => {
      const useStore = await getStore();
      expect(useStore.getState().taskSortBy).toBe('priority');
      expect(useStore.getState().taskSortOrder).toBe('asc');
    });

    it('has empty filters', async () => {
      const useStore = await getStore();
      expect(useStore.getState().taskFilters).toEqual({});
    });
  });

  // ── Synchronous Actions ────────────────────────────────

  describe('setTaskFilters', () => {
    it('sets task filters', async () => {
      const useStore = await getStore();
      useStore.getState().setTaskFilters({
        priority: ['high', 'critical'],
        status: ['pending'],
      });

      expect(useStore.getState().taskFilters).toEqual({
        priority: ['high', 'critical'],
        status: ['pending'],
      });
    });
  });

  describe('setTaskSort', () => {
    it('sets sort by and order', async () => {
      const useStore = await getStore();
      useStore.getState().setTaskSort('dueDate', 'desc');

      expect(useStore.getState().taskSortBy).toBe('dueDate');
      expect(useStore.getState().taskSortOrder).toBe('desc');
    });

    it('defaults order to asc', async () => {
      const useStore = await getStore();
      useStore.getState().setTaskSort('effort');

      expect(useStore.getState().taskSortBy).toBe('effort');
      expect(useStore.getState().taskSortOrder).toBe('asc');
    });
  });

  describe('clearError', () => {
    it('clears error to null', async () => {
      const useStore = await getStore();
      useStore.setState({ error: 'Some error' } as any);

      useStore.getState().clearError();

      expect(useStore.getState().error).toBeNull();
    });
  });

  describe('reset', () => {
    it('resets state to initial values', async () => {
      const useStore = await getStore();

      // Modify state
      useStore.getState().setTaskFilters({ priority: ['high'] });
      useStore.getState().setTaskSort('dueDate', 'desc');
      useStore.setState({ error: 'error', isLoading: true } as any);

      // Reset
      useStore.getState().reset();

      const state = useStore.getState();
      expect(state.plans).toEqual([]);
      expect(state.currentPlan).toBeNull();
      expect(state.taskFilters).toEqual({});
      expect(state.taskSortBy).toBe('priority');
      expect(state.taskSortOrder).toBe('asc');
      expect(state.error).toBeNull();
      expect(state.isLoading).toBe(false);
    });
  });

  // ── Async Actions ──────────────────────────────────────

  describe('createPlan', () => {
    it('creates plan and updates state', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const mockPlan = createMockPlan();
      (service.createCollectionPlan as any).mockResolvedValue(mockPlan);

      const result = await useStore.getState().createPlan('GDPR', 8);

      expect(result).toEqual(mockPlan);
      expect(useStore.getState().currentPlan).toEqual(mockPlan);
      expect(useStore.getState().plans).toHaveLength(1);
      expect(useStore.getState().isCreatingPlan).toBe(false);
    });

    it('sets error and re-throws on failure', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      (service.createCollectionPlan as any).mockRejectedValue(
        new Error('Framework not found'),
      );

      await expect(useStore.getState().createPlan('Unknown')).rejects.toThrow(
        'Framework not found',
      );

      expect(useStore.getState().isCreatingPlan).toBe(false);
      expect(useStore.getState().error).toBeTruthy();
    });
  });

  describe('loadPlan', () => {
    it('loads plan into state', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const mockPlan = createMockPlan();
      (service.getCollectionPlan as any).mockResolvedValue(mockPlan);

      await useStore.getState().loadPlan('plan-1');

      expect(useStore.getState().currentPlan).toEqual(mockPlan);
      expect(useStore.getState().isLoading).toBe(false);
    });

    it('sets error on failure', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      (service.getCollectionPlan as any).mockRejectedValue(new Error('Not found'));

      await useStore.getState().loadPlan('bad-id');

      expect(useStore.getState().isLoading).toBe(false);
      expect(useStore.getState().error).toBeTruthy();
    });
  });

  describe('loadPlans', () => {
    it('loads plan summaries', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const summaries = [createMockPlanSummary(), createMockPlanSummary({ id: 'plan-2' })];
      (service.listCollectionPlans as any).mockResolvedValue(summaries);

      await useStore.getState().loadPlans('GDPR');

      expect(useStore.getState().plans).toHaveLength(2);
      expect(useStore.getState().isLoading).toBe(false);
    });
  });

  describe('refreshCurrentPlan', () => {
    it('reloads the current plan', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      // Set a current plan
      const mockPlan = createMockPlan();
      useStore.setState({ currentPlan: mockPlan } as any);

      const updatedPlan = createMockPlan({ completed_tasks: 5 });
      (service.getCollectionPlan as any).mockResolvedValue(updatedPlan);

      await useStore.getState().refreshCurrentPlan();

      expect(service.getCollectionPlan).toHaveBeenCalledWith('plan-1');
    });

    it('does nothing when no current plan', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      await useStore.getState().refreshCurrentPlan();

      expect(service.getCollectionPlan).not.toHaveBeenCalled();
    });
  });

  describe('loadPriorityTasks', () => {
    it('loads priority tasks', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const tasks = [
        { task_id: 'task-1', title: 'Critical task', priority: 'critical' },
        { task_id: 'task-2', title: 'High task', priority: 'high' },
      ];
      (service.getPriorityTasks as any).mockResolvedValue(tasks);

      await useStore.getState().loadPriorityTasks('plan-1', 5);

      expect(useStore.getState().priorityTasks).toHaveLength(2);
      expect(useStore.getState().isLoading).toBe(false);
    });
  });

  describe('updateTaskStatus', () => {
    it('updates task in currentPlan and priorityTasks', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      // Set up state
      const mockPlan = createMockPlan();
      useStore.setState({
        currentPlan: mockPlan,
        priorityTasks: mockPlan.tasks,
      } as any);

      const updatedTask = {
        task_id: 'task-1',
        title: 'Collect consent logs',
        priority: 'high',
        status: 'in_progress',
        effort_hours: 4,
      };
      (service.updateTaskStatus as any).mockResolvedValue(updatedTask);

      await useStore.getState().updateTaskStatus('task-1', 'in_progress', 'Started work');

      expect(useStore.getState().isUpdatingTask).toBe(false);
    });

    it('does nothing when no current plan', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      await useStore.getState().updateTaskStatus('task-1', 'completed');

      expect(service.updateTaskStatus).not.toHaveBeenCalled();
    });

    it('sets error on failure', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      useStore.setState({ currentPlan: createMockPlan() } as any);
      (service.updateTaskStatus as any).mockRejectedValue(new Error('Update failed'));

      await useStore.getState().updateTaskStatus('task-1', 'completed');

      expect(useStore.getState().isUpdatingTask).toBe(false);
      expect(useStore.getState().error).toBeTruthy();
    });
  });

  describe('getFilteredAndSortedTasks', () => {
    it('returns empty array when no current plan', async () => {
      const useStore = await getStore();
      const result = useStore.getState().getFilteredAndSortedTasks();
      expect(result).toEqual([]);
    });

    it('calls service filter and sort methods', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const mockPlan = createMockPlan();
      useStore.setState({ currentPlan: mockPlan } as any);

      useStore.getState().getFilteredAndSortedTasks();

      expect(service.filterTasks).toHaveBeenCalled();
      expect(service.sortTasks).toHaveBeenCalled();
    });
  });
});
