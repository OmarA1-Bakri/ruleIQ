import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the dashboard service before importing the store
vi.mock('@/lib/api/dashboard.service', () => ({
  dashboardService: {
    getUserDashboard: vi.fn(),
    getComplianceMetrics: vi.fn(),
  },
}));

describe('Dashboard Store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it('should have correct initial state', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');
    const store = useDashboardStore.getState();

    expect(store.isLoading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.complianceScore).toBeNull();
    expect(store.tasks).toEqual([]);
    expect(store.activities).toEqual([]);
    expect(store.frameworks).toEqual([]);
    expect(store.deadlines).toEqual([]);
    expect(store.aiInsights).toEqual([]);
    expect(store.lastUpdated).toBeNull();
    expect(store.hasInitialData).toBe(false);
    expect(store.isFirstLoad).toBe(true);
  });

  it('should have default widgets configured', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');
    const store = useDashboardStore.getState();

    expect(store.widgets).toBeDefined();
    expect(store.widgets.length).toBe(6);

    const widgetTypes = store.widgets.map((w) => w.type);
    expect(widgetTypes).toContain('compliance-score');
    expect(widgetTypes).toContain('framework-progress');
    expect(widgetTypes).toContain('pending-tasks');
    expect(widgetTypes).toContain('activity-feed');
    expect(widgetTypes).toContain('upcoming-deadlines');
    expect(widgetTypes).toContain('ai-insights');
  });

  it('should update widget config', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    useDashboardStore.getState().updateWidgetConfig('compliance-score', {
      isVisible: false,
    });

    const widget = useDashboardStore.getState().widgets.find((w) => w.id === 'compliance-score');
    expect(widget?.isVisible).toBe(false);
  });

  it('should toggle widget visibility', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    const initialVisibility = useDashboardStore
      .getState()
      .widgets.find((w) => w.id === 'compliance-score')?.isVisible;

    useDashboardStore.getState().toggleWidgetVisibility('compliance-score');

    const newVisibility = useDashboardStore
      .getState()
      .widgets.find((w) => w.id === 'compliance-score')?.isVisible;

    expect(newVisibility).toBe(!initialVisibility);
  });

  it('should add a widget', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    const initialCount = useDashboardStore.getState().widgets.length;

    useDashboardStore.getState().addWidget({
      id: 'custom-widget',
      type: 'compliance-score',
      position: { x: 0, y: 3 },
      size: { w: 1, h: 1 },
      settings: {},
      isVisible: true,
    });

    expect(useDashboardStore.getState().widgets.length).toBe(initialCount + 1);
    expect(useDashboardStore.getState().widgets.find((w) => w.id === 'custom-widget')).toBeDefined();
  });

  it('should remove a widget', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    const initialCount = useDashboardStore.getState().widgets.length;

    useDashboardStore.getState().removeWidget('compliance-score');

    expect(useDashboardStore.getState().widgets.length).toBe(initialCount - 1);
    expect(
      useDashboardStore.getState().widgets.find((w) => w.id === 'compliance-score'),
    ).toBeUndefined();
  });

  it('should reorder widgets', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    const newWidgets = [
      {
        id: 'new-order-1',
        type: 'compliance-score' as const,
        position: { x: 0, y: 0 },
        size: { w: 1, h: 1 },
        settings: {},
        isVisible: true,
      },
    ];

    useDashboardStore.getState().reorderWidgets(newWidgets);

    expect(useDashboardStore.getState().widgets).toEqual(newWidgets);
  });

  it('should reset widgets to defaults', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    // Modify widgets
    useDashboardStore.getState().removeWidget('compliance-score');
    expect(useDashboardStore.getState().widgets.length).toBe(5);

    // Reset
    useDashboardStore.getState().resetWidgets();
    expect(useDashboardStore.getState().widgets.length).toBe(6);
  });

  it('should set compliance score', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    const score = {
      overall_score: 85,
      policy_score: 90,
      implementation_score: 80,
      evidence_score: 85,
      trend: 'up' as const,
      lastUpdated: new Date(),
      domain_scores: { gdpr: 90 },
      control_scores: { 'A.1': 85 },
      breakdown: [{ framework: 'GDPR', score: 90, weight: 1 }],
    };

    useDashboardStore.getState().setComplianceScore(score);

    expect(useDashboardStore.getState().complianceScore).toEqual(score);
  });

  it('should set tasks', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    const tasks = [
      {
        id: 'task-1',
        title: 'Review GDPR policy',
        category: 'policy' as const,
        priority: 'high' as const,
        dueDate: null,
        assignee: { name: 'John' },
        quickActions: [],
      },
    ];

    useDashboardStore.getState().setTasks(tasks);

    expect(useDashboardStore.getState().tasks).toEqual(tasks);
  });

  it('should set activities', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    const activities = [
      {
        id: 'act-1',
        type: 'change' as const,
        actor: { id: 'user-1', name: 'John' },
        action: 'updated',
        target: 'GDPR policy',
        timestamp: new Date(),
      },
    ];

    useDashboardStore.getState().setActivities(activities);

    expect(useDashboardStore.getState().activities).toEqual(activities);
  });

  it('should set frameworks', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    const frameworks = [
      {
        id: 'gdpr',
        name: 'GDPR',
        progress: 75,
        status: 'in-progress' as const,
        description: 'General Data Protection Regulation',
      },
    ];

    useDashboardStore.getState().setFrameworks(frameworks);

    expect(useDashboardStore.getState().frameworks).toEqual(frameworks);
  });

  it('should set widget loading state', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    useDashboardStore.getState().setWidgetLoading('compliance-score', true);

    expect(useDashboardStore.getState().widgetLoading['compliance-score']).toBe(true);

    useDashboardStore.getState().setWidgetLoading('compliance-score', false);

    expect(useDashboardStore.getState().widgetLoading['compliance-score']).toBe(false);
  });

  it('should set widget error state', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    useDashboardStore.getState().setWidgetError('compliance-score', 'Failed to load');

    expect(useDashboardStore.getState().widgetErrors['compliance-score']).toBe('Failed to load');

    useDashboardStore.getState().setWidgetError('compliance-score', null);

    expect(useDashboardStore.getState().widgetErrors['compliance-score']).toBeNull();
  });

  it('should clear all errors', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    // Set some errors
    useDashboardStore.getState().setWidgetError('compliance-score', 'Error 1');
    useDashboardStore.getState().setWidgetError('activity-feed', 'Error 2');

    // Clear all
    useDashboardStore.getState().clearAllErrors();

    const state = useDashboardStore.getState();
    expect(state.error).toBeNull();
    expect(state.widgetErrors).toEqual({});
  });

  it('should set loading state via setLoading', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    useDashboardStore.getState().setLoading(true);
    expect(useDashboardStore.getState().isLoading).toBe(true);

    useDashboardStore.getState().setLoading(false);
    expect(useDashboardStore.getState().isLoading).toBe(false);
  });

  it('should set metrics via setMetrics without error', async () => {
    const { useDashboardStore } = await import('@/lib/stores/dashboard.store');

    // setMetrics uses schema validation - just verify it doesn't throw
    expect(() => useDashboardStore.getState().setMetrics({ total_users: 100 })).not.toThrow();
  });

  it('should provide selector hooks', async () => {
    const mod = await import('@/lib/stores/dashboard.store');

    // Verify the selectors exist as functions
    expect(typeof mod.useComplianceScore).toBe('function');
    expect(typeof mod.useTasks).toBe('function');
    expect(typeof mod.useActivities).toBe('function');
    expect(typeof mod.useFrameworks).toBe('function');
    expect(typeof mod.useDeadlines).toBe('function');
    expect(typeof mod.useAIInsights).toBe('function');
    expect(typeof mod.useWidgets).toBe('function');
    expect(typeof mod.useDashboardLoading).toBe('function');
  });
});
