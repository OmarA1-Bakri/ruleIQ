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

describe('DashboardService', () => {
  let dashboardService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/dashboard.service');
    dashboardService = serviceMod.dashboardService;
  });

  describe('getUserDashboard', () => {
    it('calls GET /dashboard', async () => {
      const mockData = {
        stats: {
          compliance_score: 85,
          frameworks_active: 3,
          policies_approved: 12,
          evidence_collected: 45,
          assessments_completed: 5,
          tasks_pending: 8,
          upcoming_deadlines: 3,
          risk_items: 2,
        },
        recent_activity: [],
        pending_tasks: [],
        ai_insights: [],
        framework_progress: [],
        upcoming_deadlines: [],
        compliance_trends: [],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await dashboardService.getUserDashboard();

      expect(apiClient.get).toHaveBeenCalledWith('/dashboard');
      expect(result.stats.compliance_score).toBe(85);
    });
  });

  describe('getDashboardWidgets', () => {
    it('calls GET /dashboard/widgets', async () => {
      const mockWidgets = {
        widgets: [
          {
            id: 'w-1',
            type: 'compliance-score',
            title: 'Compliance Score',
            position: { x: 0, y: 0, w: 2, h: 2 },
            config: {},
            visible: true,
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockWidgets);

      const result = await dashboardService.getDashboardWidgets();

      expect(apiClient.get).toHaveBeenCalledWith('/dashboard/widgets');
      expect(result.widgets).toHaveLength(1);
      expect(result.widgets[0].type).toBe('compliance-score');
    });
  });

  describe('updateDashboardWidgets', () => {
    it('calls PUT /dashboard/widgets', async () => {
      const widgets = [{ id: 'w-1', type: 'compliance-score', visible: true }];
      (apiClient.put as any).mockResolvedValue(undefined);

      await dashboardService.updateDashboardWidgets(widgets);

      expect(apiClient.put).toHaveBeenCalledWith('/dashboard/widgets', { widgets });
    });
  });

  describe('dismissInsight', () => {
    it('calls POST /dashboard/insights/:id/dismiss', async () => {
      (apiClient.post as any).mockResolvedValue(undefined);

      await dashboardService.dismissInsight('insight-1');

      expect(apiClient.post).toHaveBeenCalledWith('/dashboard/insights/insight-1/dismiss');
    });
  });

  describe('bookmarkInsight', () => {
    it('calls POST /dashboard/insights/:id/bookmark', async () => {
      (apiClient.post as any).mockResolvedValue(undefined);

      await dashboardService.bookmarkInsight('insight-2');

      expect(apiClient.post).toHaveBeenCalledWith('/dashboard/insights/insight-2/bookmark');
    });
  });

  describe('getDashboardNotifications', () => {
    it('calls GET /dashboard/notifications without params', async () => {
      const mockNotifications = {
        notifications: [],
        unread_count: 0,
        total: 0,
      };

      (apiClient.get as any).mockResolvedValue(mockNotifications);

      const result = await dashboardService.getDashboardNotifications();

      expect(apiClient.get).toHaveBeenCalledWith('/dashboard/notifications', {});
      expect(result.unread_count).toBe(0);
    });

    it('passes params when provided', async () => {
      const mockNotifications = {
        notifications: [
          {
            id: 'n-1',
            type: 'alert',
            title: 'New alert',
            message: 'Something happened',
            read: false,
            created_at: '2025-06-15',
          },
        ],
        unread_count: 1,
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockNotifications);

      const result = await dashboardService.getDashboardNotifications({
        unread_only: true,
        page: 1,
        page_size: 10,
      });

      expect(apiClient.get).toHaveBeenCalledWith('/dashboard/notifications', {
        params: { unread_only: true, page: 1, page_size: 10 },
      });
      expect(result.notifications).toHaveLength(1);
    });
  });

  describe('markNotificationAsRead', () => {
    it('calls PATCH /dashboard/notifications/:id/read', async () => {
      (apiClient.patch as any).mockResolvedValue(undefined);

      await dashboardService.markNotificationAsRead('n-1');

      expect(apiClient.patch).toHaveBeenCalledWith('/dashboard/notifications/n-1/read');
    });
  });

  describe('markAllNotificationsAsRead', () => {
    it('calls POST /dashboard/notifications/read-all', async () => {
      (apiClient.post as any).mockResolvedValue(undefined);

      await dashboardService.markAllNotificationsAsRead();

      expect(apiClient.post).toHaveBeenCalledWith('/dashboard/notifications/read-all');
    });
  });

  describe('getQuickActions', () => {
    it('calls GET /dashboard/quick-actions', async () => {
      const mockActions = {
        actions: [
          {
            id: 'qa-1',
            label: 'Start Assessment',
            icon: 'clipboard',
            route: '/assessments/new',
            color: 'teal',
            description: 'Begin a new compliance assessment',
            enabled: true,
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockActions);

      const result = await dashboardService.getQuickActions();

      expect(apiClient.get).toHaveBeenCalledWith('/dashboard/quick-actions');
      expect(result.actions).toHaveLength(1);
      expect(result.actions[0].label).toBe('Start Assessment');
    });
  });

  describe('exportDashboard', () => {
    it('calls download for PDF', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await dashboardService.exportDashboard('pdf');

      expect(apiClient.download).toHaveBeenCalledWith(
        expect.stringContaining('/dashboard/export?format=pdf'),
        expect.stringMatching(/^dashboard-\d{4}-\d{2}-\d{2}\.pdf$/),
      );
    });

    it('calls download for Excel', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await dashboardService.exportDashboard('excel');

      expect(apiClient.download).toHaveBeenCalledWith(
        expect.stringContaining('/dashboard/export?format=excel'),
        expect.stringMatching(/^dashboard-\d{4}-\d{2}-\d{2}\.excel$/),
      );
    });
  });

  describe('getPersonalizedRecommendations', () => {
    it('calls GET /dashboard/recommendations', async () => {
      const mockRecs = {
        recommendations: [
          {
            id: 'rec-1',
            category: 'compliance',
            title: 'Complete GDPR assessment',
            description: 'Your GDPR assessment is overdue',
            impact: 'high',
            effort: 'medium',
            savings_potential: '10 hours/month',
            action_steps: ['Step 1', 'Step 2'],
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockRecs);

      const result = await dashboardService.getPersonalizedRecommendations();

      expect(apiClient.get).toHaveBeenCalledWith('/dashboard/recommendations');
      expect(result.recommendations).toHaveLength(1);
      expect(result.recommendations[0].category).toBe('compliance');
    });
  });
});

// ── Type interface tests ─────────────────────────────────

describe('Dashboard type interfaces', () => {
  it('DashboardStats has all expected fields', () => {
    const stats = {
      compliance_score: 85,
      frameworks_active: 3,
      policies_approved: 12,
      evidence_collected: 45,
      assessments_completed: 5,
      tasks_pending: 8,
      upcoming_deadlines: 3,
      risk_items: 2,
    };

    expect(Object.keys(stats)).toHaveLength(8);
    expect(stats.compliance_score).toBe(85);
  });

  it('DashboardActivity has required fields', () => {
    const activity = {
      id: 'act-1',
      timestamp: '2025-06-15T10:00:00Z',
      type: 'assessment' as const,
      action: 'created',
      description: 'Assessment was created',
    };

    expect(activity.id).toBe('act-1');
    expect(activity.type).toBe('assessment');
  });

  it('DashboardTask priority values', () => {
    const priorities = ['critical', 'high', 'medium', 'low'];
    expect(priorities).toHaveLength(4);
  });

  it('DashboardInsight has correct shape', () => {
    const insight = {
      id: 'ins-1',
      type: 'recommendation' as const,
      title: 'Improve score',
      description: 'Consider doing X',
      action: { label: 'Do it', route: '/action' },
      priority: 1,
      dismissible: true,
      created_at: '2025-06-15',
    };

    expect(insight.type).toBe('recommendation');
    expect(insight.action.route).toBe('/action');
    expect(insight.dismissible).toBe(true);
  });

  it('FrameworkProgress trend values', () => {
    const trends = ['improving', 'stable', 'declining'];
    expect(trends).toContain('improving');
    expect(trends).toContain('stable');
    expect(trends).toContain('declining');
  });
});
