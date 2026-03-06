import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock all external dependencies before importing the store
vi.mock('@/lib/api/assessments.service', () => ({
  assessmentService: {
    getAssessments: vi.fn(),
    getAssessment: vi.fn(),
    createAssessment: vi.fn(),
    updateAssessment: vi.fn(),
    deleteAssessment: vi.fn(),
    completeAssessment: vi.fn(),
    getAssessmentQuestions: vi.fn(),
    submitAssessmentAnswer: vi.fn(),
    getAssessmentResults: vi.fn(),
    getQuickAssessment: vi.fn(),
  },
}));

vi.mock('@/lib/utils/type-safety', () => ({
  toAppError: vi.fn((error: any) => ({
    message: error?.message || error || 'Unknown error',
    code: error?.name,
  })),
}));

vi.mock('@/lib/stores/schemas', () => ({
  AssessmentsArraySchema: { parse: vi.fn((v: any) => v) },
  FrameworksArraySchema: { parse: vi.fn((v: any) => v) },
  LoadingStateSchema: { parse: vi.fn((v: any) => v) },
  safeValidate: vi.fn((_schema: any, data: any) => data),
}));

// Mock performance monitoring - make performanceMiddleware pass-through
vi.mock('@/lib/utils/performance-monitoring', () => ({
  performanceMiddleware: (config: any) => config,
  withPerformanceMonitoring: vi.fn((_name: string, fn: () => Promise<any>) => fn()),
}));

function createMockAssessment(overrides: Record<string, any> = {}) {
  return {
    id: 'assessment-1',
    name: 'GDPR Assessment',
    status: 'draft',
    framework_id: 'fw-1',
    business_profile_id: 'bp-1',
    questions_count: 10,
    answered_count: 3,
    ...overrides,
  };
}

async function getStore() {
  const mod = await import('@/lib/stores/assessment.store');
  return mod.useAssessmentStore;
}

async function getMockedService() {
  const mod = await import('@/lib/api/assessments.service');
  return mod.assessmentService as Record<string, ReturnType<typeof vi.fn>>;
}

describe('Assessment Store', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    localStorage.clear();
  });

  // ── Initial State ──────────────────────────────────────

  describe('initial state', () => {
    it('has empty assessments array', async () => {
      const useStore = await getStore();
      expect(useStore.getState().assessments).toEqual([]);
    });

    it('has null currentAssessment', async () => {
      const useStore = await getStore();
      expect(useStore.getState().currentAssessment).toBeNull();
    });

    it('has all loading flags false', async () => {
      const useStore = await getStore();
      const state = useStore.getState();
      expect(state.isLoading).toBe(false);
      expect(state.isCreating).toBe(false);
      expect(state.isSubmitting).toBe(false);
      expect(state.isSaving).toBe(false);
    });

    it('has null error', async () => {
      const useStore = await getStore();
      expect(useStore.getState().error).toBeNull();
    });

    it('has default pagination', async () => {
      const useStore = await getStore();
      expect(useStore.getState().currentPage).toBe(1);
      expect(useStore.getState().pageSize).toBe(20);
      expect(useStore.getState().total).toBe(0);
    });

    it('has empty filters', async () => {
      const useStore = await getStore();
      expect(useStore.getState().filters).toEqual({});
    });
  });

  // ── Synchronous Actions ────────────────────────────────

  describe('setAssessments', () => {
    it('sets assessments array', async () => {
      const useStore = await getStore();
      const assessments = [createMockAssessment(), createMockAssessment({ id: 'assessment-2' })];

      useStore.getState().setAssessments(assessments as any);

      expect(useStore.getState().assessments).toHaveLength(2);
    });
  });

  describe('addAssessment', () => {
    it('prepends assessment to array', async () => {
      const useStore = await getStore();
      const existing = createMockAssessment({ id: 'existing' });
      useStore.getState().setAssessments([existing] as any);

      const newAssessment = createMockAssessment({ id: 'new-one', name: 'New' });
      useStore.getState().addAssessment(newAssessment as any);

      const assessments = useStore.getState().assessments;
      expect(assessments).toHaveLength(2);
      expect(assessments[0].id).toBe('new-one');
      expect(assessments[1].id).toBe('existing');
    });
  });

  describe('setLoading', () => {
    it('sets isLoading flag', async () => {
      const useStore = await getStore();

      useStore.getState().setLoading(true);
      expect(useStore.getState().isLoading).toBe(true);

      useStore.getState().setLoading(false);
      expect(useStore.getState().isLoading).toBe(false);
    });
  });

  describe('setFilters', () => {
    it('sets filters and resets page to 1', async () => {
      const useStore = await getStore();
      useStore.getState().setPage(3);

      useStore.getState().setFilters({ status: 'draft', frameworkId: 'fw-1' });

      expect(useStore.getState().filters).toEqual({ status: 'draft', frameworkId: 'fw-1' });
      expect(useStore.getState().currentPage).toBe(1);
    });
  });

  describe('setPage', () => {
    it('sets current page', async () => {
      const useStore = await getStore();

      useStore.getState().setPage(5);

      expect(useStore.getState().currentPage).toBe(5);
    });
  });

  describe('clearError', () => {
    it('clears error to null', async () => {
      const useStore = await getStore();
      // Set an error via loadAssessment failure
      useStore.setState({ error: 'some error' } as any);

      useStore.getState().clearError();

      expect(useStore.getState().error).toBeNull();
    });
  });

  describe('reset', () => {
    it('resets all state to initial values', async () => {
      const useStore = await getStore();

      // Modify some state
      useStore.getState().setAssessments([createMockAssessment()] as any);
      useStore.getState().setPage(5);
      useStore.getState().setFilters({ status: 'completed' });
      useStore.getState().setLoading(true);

      // Reset
      useStore.getState().reset();

      const state = useStore.getState();
      expect(state.assessments).toEqual([]);
      expect(state.currentPage).toBe(1);
      expect(state.filters).toEqual({});
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  // ── Async Actions ──────────────────────────────────────

  describe('loadAssessments', () => {
    it('loads assessments from service', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const mockData = {
        items: [createMockAssessment(), createMockAssessment({ id: 'a-2' })],
        total: 2,
      };
      (service.getAssessments as any).mockResolvedValue(mockData);

      await useStore.getState().loadAssessments({});

      expect(useStore.getState().assessments).toHaveLength(2);
      expect(useStore.getState().total).toBe(2);
      expect(useStore.getState().isLoading).toBe(false);
    });

    it('sets error on failure', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      (service.getAssessments as any).mockRejectedValue(new Error('Network error'));

      await useStore.getState().loadAssessments({});

      expect(useStore.getState().isLoading).toBe(false);
      expect(useStore.getState().error).toBe('Network error');
    });
  });

  describe('loadAssessment', () => {
    it('loads a single assessment', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const mockAssessment = createMockAssessment();
      (service.getAssessment as any).mockResolvedValue(mockAssessment);

      await useStore.getState().loadAssessment('assessment-1');

      expect(useStore.getState().currentAssessment).toEqual(mockAssessment);
      expect(useStore.getState().isLoading).toBe(false);
    });

    it('sets error on failure', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      (service.getAssessment as any).mockRejectedValue(new Error('Not found'));

      await useStore.getState().loadAssessment('bad-id');

      expect(useStore.getState().isLoading).toBe(false);
      expect(useStore.getState().error).toBe('Not found');
    });
  });

  describe('createAssessment', () => {
    it('creates assessment and prepends to list', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const newAssessment = createMockAssessment({ id: 'new-1' });
      (service.createAssessment as any).mockResolvedValue(newAssessment);

      const result = await useStore.getState().createAssessment({
        business_profile_id: 'bp-1',
        framework_id: 'fw-1',
      });

      expect(result).toEqual(newAssessment);
      expect(useStore.getState().assessments[0].id).toBe('new-1');
      expect(useStore.getState().currentAssessment).toEqual(newAssessment);
      expect(useStore.getState().isCreating).toBe(false);
    });

    it('sets error and re-throws on failure', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      (service.createAssessment as any).mockRejectedValue(new Error('Validation error'));

      await expect(
        useStore.getState().createAssessment({
          business_profile_id: 'bp-1',
          framework_id: 'fw-1',
        }),
      ).rejects.toThrow('Validation error');

      expect(useStore.getState().isCreating).toBe(false);
      expect(useStore.getState().error).toBe('Validation error');
    });
  });

  describe('updateAssessment', () => {
    it('updates assessment in list', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const original = createMockAssessment({ id: 'a-1', name: 'Old Name' });
      useStore.getState().setAssessments([original] as any);

      const updated = createMockAssessment({ id: 'a-1', name: 'New Name' });
      (service.updateAssessment as any).mockResolvedValue(updated);

      await useStore.getState().updateAssessment('a-1', { status: 'in_progress' });

      expect(useStore.getState().assessments[0].name).toBe('New Name');
      expect(useStore.getState().isSaving).toBe(false);
    });
  });

  describe('deleteAssessment', () => {
    it('removes assessment from list', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      useStore.getState().setAssessments([
        createMockAssessment({ id: 'a-1' }),
        createMockAssessment({ id: 'a-2' }),
      ] as any);

      (service.deleteAssessment as any).mockResolvedValue(undefined);

      await useStore.getState().deleteAssessment('a-1');

      expect(useStore.getState().assessments).toHaveLength(1);
      expect(useStore.getState().assessments[0].id).toBe('a-2');
      expect(useStore.getState().isLoading).toBe(false);
    });

    it('clears currentAssessment if it was deleted', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const assessment = createMockAssessment({ id: 'a-1' });
      useStore.getState().setAssessments([assessment] as any);
      useStore.setState({ currentAssessment: assessment } as any);

      (service.deleteAssessment as any).mockResolvedValue(undefined);

      await useStore.getState().deleteAssessment('a-1');

      expect(useStore.getState().currentAssessment).toBeNull();
    });
  });

  describe('completeAssessment', () => {
    it('updates assessment status in list', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const original = createMockAssessment({ id: 'a-1', status: 'in_progress' });
      useStore.getState().setAssessments([original] as any);

      const completed = createMockAssessment({ id: 'a-1', status: 'completed' });
      (service.completeAssessment as any).mockResolvedValue(completed);

      await useStore.getState().completeAssessment('a-1');

      expect(useStore.getState().assessments[0].status).toBe('completed');
      expect(useStore.getState().isSubmitting).toBe(false);
    });
  });

  describe('loadAssessmentQuestions', () => {
    it('loads questions into state', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const questions = [
        { id: 'q-1', text: 'Question 1' },
        { id: 'q-2', text: 'Question 2' },
      ];
      (service.getAssessmentQuestions as any).mockResolvedValue(questions);

      await useStore.getState().loadAssessmentQuestions('assessment-1');

      expect(useStore.getState().assessmentQuestions).toHaveLength(2);
      expect(useStore.getState().isLoading).toBe(false);
    });
  });

  describe('submitAnswer', () => {
    it('submits answer and clears submitting flag', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      (service.submitAssessmentAnswer as any).mockResolvedValue({});

      await useStore.getState().submitAnswer('assessment-1', {
        question_id: 'q-1',
        answer: 'Yes',
      });

      expect(useStore.getState().isSubmitting).toBe(false);
      expect(service.submitAssessmentAnswer).toHaveBeenCalledWith('assessment-1', {
        question_id: 'q-1',
        answer: 'Yes',
      });
    });

    it('sets error on failure', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      (service.submitAssessmentAnswer as any).mockRejectedValue(new Error('Submit failed'));

      await useStore.getState().submitAnswer('assessment-1', {
        question_id: 'q-1',
        answer: 'Yes',
      });

      expect(useStore.getState().isSubmitting).toBe(false);
      expect(useStore.getState().error).toBe('Submit failed');
    });
  });

  describe('loadAssessmentResults', () => {
    it('loads results into state', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const results = { score: 85, recommendations: ['Do X'] };
      (service.getAssessmentResults as any).mockResolvedValue(results);

      await useStore.getState().loadAssessmentResults('assessment-1');

      expect(useStore.getState().assessmentResults).toEqual(results);
      expect(useStore.getState().isLoading).toBe(false);
    });
  });

  describe('startQuickAssessment', () => {
    it('calls service and returns result', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      const result = { id: 'quick-1', type: 'quick' };
      (service.getQuickAssessment as any).mockResolvedValue(result);

      const response = await useStore.getState().startQuickAssessment('bp-1', 'fw-1');

      expect(response).toEqual(result);
      expect(useStore.getState().isCreating).toBe(false);
    });

    it('sets error and re-throws on failure', async () => {
      const useStore = await getStore();
      const service = await getMockedService();

      (service.getQuickAssessment as any).mockRejectedValue(new Error('Service down'));

      await expect(
        useStore.getState().startQuickAssessment('bp-1', 'fw-1'),
      ).rejects.toThrow('Service down');

      expect(useStore.getState().isCreating).toBe(false);
      expect(useStore.getState().error).toBe('Service down');
    });
  });
});
