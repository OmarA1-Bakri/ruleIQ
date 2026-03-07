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

describe('IntegrationService', () => {
  let integrationService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/integrations.service');
    integrationService = serviceMod.integrationService;
  });

  describe('getIntegrations', () => {
    it('calls GET /integrations', async () => {
      const mockData = [
        { id: 'int-1', provider: 'slack', name: 'Slack', status: 'available' },
        { id: 'int-2', provider: 'jira', name: 'Jira', status: 'available' },
      ];

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await integrationService.getIntegrations();

      expect(apiClient.get).toHaveBeenCalledWith('/integrations');
      expect(result).toHaveLength(2);
      expect(result[0].provider).toBe('slack');
    });
  });

  describe('getConnectedIntegrations', () => {
    it('calls GET /integrations/connected', async () => {
      const mockData = [
        { id: 'int-1', provider: 'slack', name: 'Slack', status: 'connected' },
      ];

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await integrationService.getConnectedIntegrations();

      expect(apiClient.get).toHaveBeenCalledWith('/integrations/connected');
      expect(result).toHaveLength(1);
      expect(result[0].status).toBe('connected');
    });
  });

  describe('connectIntegration', () => {
    it('calls POST /integrations/connect', async () => {
      const mockResponse = {
        integration_id: 'int-new',
        status: 'connected',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await integrationService.connectIntegration({
        provider: 'slack',
        config: { webhook_url: 'https://hooks.slack.com/test' },
      });

      expect(apiClient.post).toHaveBeenCalledWith('/integrations/connect', {
        provider: 'slack',
        config: { webhook_url: 'https://hooks.slack.com/test' },
      });
      expect(result.status).toBe('connected');
    });

    it('handles pending_auth status with auth_url', async () => {
      const mockResponse = {
        integration_id: 'int-new',
        status: 'pending_auth',
        auth_url: 'https://oauth.provider.com/authorize?client_id=123',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await integrationService.connectIntegration({ provider: 'github' });

      expect(result.status).toBe('pending_auth');
      expect(result.auth_url).toContain('oauth.provider.com');
    });
  });

  describe('disconnectIntegration', () => {
    it('calls DELETE /integrations/:id/disconnect', async () => {
      (apiClient.delete as any).mockResolvedValue(undefined);

      await integrationService.disconnectIntegration('int-1');

      expect(apiClient.delete).toHaveBeenCalledWith('/integrations/int-1/disconnect');
    });
  });

  describe('testIntegration', () => {
    it('calls POST /integrations/:id/test', async () => {
      const mockResponse = {
        status: 'success',
        message: 'Connection successful',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await integrationService.testIntegration('int-1');

      expect(apiClient.post).toHaveBeenCalledWith('/integrations/int-1/test');
      expect(result.status).toBe('success');
    });
  });

  describe('syncIntegration', () => {
    it('calls POST /integrations/:id/sync with options', async () => {
      const mockResponse = {
        sync_id: 'sync-1',
        status: 'started',
        items_synced: 0,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await integrationService.syncIntegration('int-1', {
        full_sync: true,
        data_types: ['users', 'projects'],
      });

      expect(apiClient.post).toHaveBeenCalledWith('/integrations/int-1/sync', {
        full_sync: true,
        data_types: ['users', 'projects'],
      });
      expect(result.sync_id).toBe('sync-1');
    });

    it('sends empty object when no options provided', async () => {
      (apiClient.post as any).mockResolvedValue({ sync_id: 'sync-2', status: 'started' });

      await integrationService.syncIntegration('int-1');

      expect(apiClient.post).toHaveBeenCalledWith('/integrations/int-1/sync', {});
    });
  });

  describe('getIntegrationSyncHistory', () => {
    it('calls GET /integrations/:id/sync-history', async () => {
      const mockData = {
        syncs: [
          {
            sync_id: 'sync-1',
            started_at: '2025-06-15T10:00:00Z',
            completed_at: '2025-06-15T10:05:00Z',
            status: 'completed',
            items_synced: 150,
            errors_count: 0,
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await integrationService.getIntegrationSyncHistory('int-1');

      expect(apiClient.get).toHaveBeenCalledWith('/integrations/int-1/sync-history');
      expect(result.syncs).toHaveLength(1);
      expect(result.syncs[0].items_synced).toBe(150);
    });
  });

  describe('configureWebhooks', () => {
    it('calls POST /integrations/:id/webhooks', async () => {
      const config = {
        endpoint_url: 'https://myapp.com/webhooks/slack',
        events: ['message.created', 'channel.updated'],
        secret: 'webhook-secret',
        active: true,
      };

      const mockResponse = {
        webhook_id: 'wh-1',
        status: 'active',
        test_url: 'https://myapp.com/webhooks/test',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await integrationService.configureWebhooks('int-1', config);

      expect(apiClient.post).toHaveBeenCalledWith('/integrations/int-1/webhooks', config);
      expect(result.webhook_id).toBe('wh-1');
      expect(result.status).toBe('active');
    });
  });

  describe('getIntegrationLogs', () => {
    it('calls GET /integrations/:id/logs without params', async () => {
      const mockData = { logs: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await integrationService.getIntegrationLogs('int-1');

      expect(apiClient.get).toHaveBeenCalledWith('/integrations/int-1/logs', {});
      expect(result.total).toBe(0);
    });

    it('passes filter params when provided', async () => {
      const mockData = {
        logs: [
          {
            timestamp: '2025-06-15T10:00:00Z',
            event_type: 'sync',
            status: 'success',
            details: { items: 50 },
          },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await integrationService.getIntegrationLogs('int-1', {
        event_type: 'sync',
        page: 1,
        page_size: 20,
      });

      expect(apiClient.get).toHaveBeenCalledWith('/integrations/int-1/logs', {
        params: { event_type: 'sync', page: 1, page_size: 20 },
      });
      expect(result.logs).toHaveLength(1);
    });
  });

  describe('updateIntegrationConfig', () => {
    it('calls PATCH /integrations/:id/config', async () => {
      const mockResponse = { id: 'int-1', provider: 'slack', config: { channel: '#compliance' } };
      (apiClient.patch as any).mockResolvedValue(mockResponse);

      const result = await integrationService.updateIntegrationConfig('int-1', {
        channel: '#compliance',
      });

      expect(apiClient.patch).toHaveBeenCalledWith('/integrations/int-1/config', {
        channel: '#compliance',
      });
      expect(result.id).toBe('int-1');
    });
  });

  describe('getOAuthCallbackUrl', () => {
    it('returns correct callback URL', () => {
      const url = integrationService.getOAuthCallbackUrl('github');

      expect(url).toContain('/integrations/callback/github');
    });
  });

  describe('handleOAuthCallback', () => {
    it('calls POST /integrations/oauth/callback', async () => {
      const mockResponse = {
        success: true,
        integration_id: 'int-new',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await integrationService.handleOAuthCallback('github', 'auth-code-123', 'state-xyz');

      expect(apiClient.post).toHaveBeenCalledWith('/integrations/oauth/callback', {
        provider: 'github',
        code: 'auth-code-123',
        state: 'state-xyz',
      });
      expect(result.success).toBe(true);
      expect(result.integration_id).toBe('int-new');
    });

    it('handles error response', async () => {
      const mockResponse = {
        success: false,
        error: 'Invalid authorization code',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await integrationService.handleOAuthCallback('github', 'bad-code');

      expect(result.success).toBe(false);
      expect(result.error).toBe('Invalid authorization code');
    });
  });
});
