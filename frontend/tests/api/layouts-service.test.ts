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

describe('LayoutsService', () => {
  let layoutsService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/layouts.service');
    layoutsService = serviceMod.layoutsService;
  });

  describe('deleteLayout', () => {
    it('calls DELETE /layouts/:userId', async () => {
      (apiClient.delete as any).mockResolvedValue(undefined);

      await layoutsService.deleteLayout('user-1');

      expect(apiClient.delete).toHaveBeenCalledWith('/layouts/user-1');
    });
  });

  describe('getSnapshots', () => {
    it('calls GET /layouts/:userId/snapshots', async () => {
      const mockSnapshots = [
        { id: 'snap-1', name: 'Before redesign', createdAt: '2025-06-15' },
        { id: 'snap-2', name: 'After redesign', createdAt: '2025-06-16' },
      ];

      (apiClient.get as any).mockResolvedValue(mockSnapshots);

      const result = await layoutsService.getSnapshots('user-1');

      expect(apiClient.get).toHaveBeenCalledWith('/layouts/user-1/snapshots');
      expect(result).toHaveLength(2);
      expect(result[0].name).toBe('Before redesign');
    });
  });

  describe('saveSnapshot', () => {
    it('calls POST /layouts/:userId/snapshots', async () => {
      const snapshotData = {
        name: 'My snapshot',
        layout: { id: 'layout-1', widgets: [] },
      };

      const mockResponse = {
        id: 'snap-new',
        ...snapshotData,
        createdAt: '2025-06-15T10:00:00Z',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await layoutsService.saveSnapshot('user-1', snapshotData);

      expect(apiClient.post).toHaveBeenCalledWith('/layouts/user-1/snapshots', snapshotData);
      expect(result.id).toBe('snap-new');
    });
  });

  describe('deleteSnapshot', () => {
    it('calls DELETE /layouts/:userId/snapshots/:snapshotId', async () => {
      (apiClient.delete as any).mockResolvedValue(undefined);

      await layoutsService.deleteSnapshot('user-1', 'snap-1');

      expect(apiClient.delete).toHaveBeenCalledWith('/layouts/user-1/snapshots/snap-1');
    });
  });

  describe('getTemplates', () => {
    it('calls GET /layouts/templates without category', async () => {
      const mockTemplates = [
        { id: 'tmpl-1', name: 'Default', category: 'basic' },
      ];

      (apiClient.get as any).mockResolvedValue(mockTemplates);

      const result = await layoutsService.getTemplates();

      expect(apiClient.get).toHaveBeenCalledWith('/layouts/templates', { params: {} });
      expect(result).toHaveLength(1);
    });

    it('passes category param when provided', async () => {
      (apiClient.get as any).mockResolvedValue([]);

      await layoutsService.getTemplates('advanced');

      expect(apiClient.get).toHaveBeenCalledWith('/layouts/templates', {
        params: { category: 'advanced' },
      });
    });
  });

  describe('applyTemplate', () => {
    it('calls POST /layouts/:userId/apply-template', async () => {
      const mockLayout = { id: 'layout-new', widgets: [{ id: 'w-1' }] };
      (apiClient.post as any).mockResolvedValue(mockLayout);

      const result = await layoutsService.applyTemplate('user-1', 'tmpl-1');

      expect(apiClient.post).toHaveBeenCalledWith('/layouts/user-1/apply-template', {
        templateId: 'tmpl-1',
      });
      expect(result.widgets).toHaveLength(1);
    });
  });

  describe('exportLayout', () => {
    it('calls POST /layouts/:userId/export', async () => {
      const mockBlob = new Blob(['layout data']);
      (apiClient.post as any).mockResolvedValue(mockBlob);

      const options = { format: 'json' };
      const result = await layoutsService.exportLayout('user-1', 'layout-1', options);

      expect(apiClient.post).toHaveBeenCalledWith('/layouts/user-1/export', {
        layoutId: 'layout-1',
        format: 'json',
      });
      expect(result).toBeTruthy();
    });
  });

  describe('shareLayout', () => {
    it('calls POST /layouts/:userId/share', async () => {
      const mockResponse = {
        shareUrl: 'https://app.ruleiq.com/shared/abc123',
        expiresAt: '2025-07-15T10:00:00Z',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await layoutsService.shareLayout('user-1', 'layout-1', ['user-2', 'user-3']);

      expect(apiClient.post).toHaveBeenCalledWith('/layouts/user-1/share', {
        layoutId: 'layout-1',
        shareWith: ['user-2', 'user-3'],
      });
      expect(result.shareUrl).toContain('shared');
    });
  });

  describe('getSharedLayout', () => {
    it('calls GET /layouts/shared/:shareToken', async () => {
      const mockLayout = { id: 'layout-shared', widgets: [] };
      (apiClient.get as any).mockResolvedValue(mockLayout);

      const result = await layoutsService.getSharedLayout('token-abc123');

      expect(apiClient.get).toHaveBeenCalledWith('/layouts/shared/token-abc123');
      expect(result.id).toBe('layout-shared');
    });
  });

  describe('duplicateLayout', () => {
    it('calls POST /layouts/:userId/duplicate', async () => {
      const mockLayout = { id: 'layout-dup', name: 'My Dashboard Copy' };
      (apiClient.post as any).mockResolvedValue(mockLayout);

      const result = await layoutsService.duplicateLayout('user-1', 'layout-1', 'My Dashboard Copy');

      expect(apiClient.post).toHaveBeenCalledWith('/layouts/user-1/duplicate', {
        layoutId: 'layout-1',
        name: 'My Dashboard Copy',
      });
      expect(result.name).toBe('My Dashboard Copy');
    });
  });

  describe('getLayoutHistory', () => {
    it('calls GET /layouts/:userId/history with default limit', async () => {
      const mockHistory = [
        { version: 1, timestamp: '2025-06-15', changes: 'Initial layout' },
        { version: 2, timestamp: '2025-06-16', changes: 'Added widget' },
      ];

      (apiClient.get as any).mockResolvedValue(mockHistory);

      const result = await layoutsService.getLayoutHistory('user-1');

      expect(apiClient.get).toHaveBeenCalledWith('/layouts/user-1/history', {
        params: { limit: 10 },
      });
      expect(result).toHaveLength(2);
    });

    it('passes custom limit', async () => {
      (apiClient.get as any).mockResolvedValue([]);

      await layoutsService.getLayoutHistory('user-1', 5);

      expect(apiClient.get).toHaveBeenCalledWith('/layouts/user-1/history', {
        params: { limit: 5 },
      });
    });
  });

  describe('restoreVersion', () => {
    it('calls POST /layouts/:userId/restore', async () => {
      const mockLayout = { id: 'layout-1', version: 3 };
      (apiClient.post as any).mockResolvedValue(mockLayout);

      const result = await layoutsService.restoreVersion('user-1', 3);

      expect(apiClient.post).toHaveBeenCalledWith('/layouts/user-1/restore', { version: 3 });
      expect(result.version).toBe(3);
    });
  });

  describe('validateLayout', () => {
    it('calls POST /layouts/validate', async () => {
      const layout = { id: 'layout-1', widgets: [] };
      const mockResponse = { valid: true };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await layoutsService.validateLayout(layout);

      expect(apiClient.post).toHaveBeenCalledWith('/layouts/validate', layout);
      expect(result.valid).toBe(true);
    });

    it('returns errors for invalid layout', async () => {
      const layout = { id: 'bad', widgets: null };
      const mockResponse = {
        valid: false,
        errors: ['widgets must be an array'],
        warnings: ['No ruleOrder defined'],
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await layoutsService.validateLayout(layout);

      expect(result.valid).toBe(false);
      expect(result.errors).toHaveLength(1);
      expect(result.warnings).toHaveLength(1);
    });
  });

  describe('getLayoutStats', () => {
    it('calls GET /layouts/:userId/stats', async () => {
      const mockStats = {
        totalLayouts: 5,
        totalSnapshots: 12,
        lastModified: '2025-06-15T10:00:00Z',
        mostUsedWidgets: [
          { widgetId: 'compliance-score', count: 5 },
          { widgetId: 'task-list', count: 4 },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockStats);

      const result = await layoutsService.getLayoutStats('user-1');

      expect(apiClient.get).toHaveBeenCalledWith('/layouts/user-1/stats');
      expect(result.totalLayouts).toBe(5);
      expect(result.mostUsedWidgets).toHaveLength(2);
    });
  });
});

// ── getCurrentUserId tests ───────────────────────────────

describe('getCurrentUserId', () => {
  let getCurrentUserId: any;

  beforeEach(async () => {
    vi.resetModules();
    localStorage.clear();
    sessionStorage.clear();

    const mod = await import('@/lib/api/layouts.service');
    getCurrentUserId = mod.getCurrentUserId;
  });

  it('returns userId from localStorage', () => {
    localStorage.setItem('userId', 'user-from-local');
    expect(getCurrentUserId()).toBe('user-from-local');
  });

  it('returns userId from sessionStorage when not in localStorage', () => {
    sessionStorage.setItem('userId', 'user-from-session');
    expect(getCurrentUserId()).toBe('user-from-session');
  });

  it('prefers localStorage over sessionStorage', () => {
    localStorage.setItem('userId', 'local-user');
    sessionStorage.setItem('userId', 'session-user');
    expect(getCurrentUserId()).toBe('local-user');
  });

  it('returns null when no userId in storage', () => {
    expect(getCurrentUserId()).toBeNull();
  });
});
