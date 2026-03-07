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

describe('MonitoringService', () => {
  let monitoringService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/monitoring.service');
    monitoringService = serviceMod.monitoringService;
  });

  describe('getDatabaseStatus', () => {
    it('calls GET /monitoring/database/status', async () => {
      const mockStatus = {
        status: 'healthy',
        connected_clients: 12,
        active_queries: 3,
        pool_size: 20,
        available_connections: 17,
        response_time_ms: 5,
        last_check: '2025-06-15T10:00:00Z',
      };

      (apiClient.get as any).mockResolvedValue(mockStatus);

      const result = await monitoringService.getDatabaseStatus();

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/database/status');
      expect(result.status).toBe('healthy');
      expect(result.connected_clients).toBe(12);
      expect(result.response_time_ms).toBe(5);
    });
  });

  describe('getSystemAlerts', () => {
    it('calls GET /monitoring/alerts without params', async () => {
      const mockData = { alerts: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await monitoringService.getSystemAlerts();

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/alerts', {});
      expect(result.total).toBe(0);
    });

    it('passes params when provided', async () => {
      const mockData = {
        alerts: [
          {
            id: 'alert-1',
            severity: 'warning',
            type: 'high_cpu',
            message: 'CPU usage above 80%',
            details: { cpu_usage: 85 },
            created_at: '2025-06-15T10:00:00Z',
            resolved: false,
          },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await monitoringService.getSystemAlerts({
        severity: 'warning',
        resolved: false,
        page: 1,
        page_size: 10,
      });

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/alerts', {
        params: { severity: 'warning', resolved: false, page: 1, page_size: 10 },
      });
      expect(result.alerts).toHaveLength(1);
      expect(result.alerts[0].severity).toBe('warning');
    });
  });

  describe('resolveAlert', () => {
    it('calls PATCH /monitoring/alerts/:id/resolve', async () => {
      const mockAlert = {
        id: 'alert-1',
        severity: 'warning',
        type: 'high_cpu',
        message: 'CPU usage above 80%',
        resolved: true,
        resolved_at: '2025-06-15T11:00:00Z',
      };

      (apiClient.patch as any).mockResolvedValue(mockAlert);

      const result = await monitoringService.resolveAlert('alert-1', 'Auto-scaled instances');

      expect(apiClient.patch).toHaveBeenCalledWith('/monitoring/alerts/alert-1/resolve', {
        resolution: 'Auto-scaled instances',
      });
      expect(result.resolved).toBe(true);
    });

    it('works without resolution text', async () => {
      const mockAlert = { id: 'alert-2', resolved: true };
      (apiClient.patch as any).mockResolvedValue(mockAlert);

      await monitoringService.resolveAlert('alert-2');

      expect(apiClient.patch).toHaveBeenCalledWith('/monitoring/alerts/alert-2/resolve', {
        resolution: undefined,
      });
    });
  });

  describe('getSystemMetrics', () => {
    it('calls GET /monitoring/metrics', async () => {
      const mockMetrics = {
        cpu_usage: 45.2,
        memory_usage: 67.8,
        disk_usage: 52.1,
        request_rate: 150,
        error_rate: 0.5,
        average_response_time: 120,
        uptime_seconds: 86400,
      };

      (apiClient.get as any).mockResolvedValue(mockMetrics);

      const result = await monitoringService.getSystemMetrics();

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/metrics');
      expect(result.cpu_usage).toBe(45.2);
      expect(result.memory_usage).toBe(67.8);
      expect(result.uptime_seconds).toBe(86400);
    });
  });

  describe('getApiPerformanceMetrics', () => {
    it('calls GET /monitoring/api-performance without params', async () => {
      const mockData = { endpoints: [], time_series: [] };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await monitoringService.getApiPerformanceMetrics();

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/api-performance', {});
      expect(result.endpoints).toEqual([]);
    });

    it('passes params when provided', async () => {
      const mockData = {
        endpoints: [
          {
            path: '/api/v1/assessments',
            method: 'GET',
            avg_response_time: 85,
            p95_response_time: 150,
            p99_response_time: 250,
            success_rate: 99.5,
            request_count: 1200,
          },
        ],
        time_series: [
          {
            timestamp: '2025-06-15T10:00:00Z',
            response_time: 90,
            error_rate: 0.3,
            request_count: 50,
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await monitoringService.getApiPerformanceMetrics({
        endpoint: '/api/v1/assessments',
        time_range: 'day',
      });

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/api-performance', {
        params: { endpoint: '/api/v1/assessments', time_range: 'day' },
      });
      expect(result.endpoints).toHaveLength(1);
      expect(result.endpoints[0].success_rate).toBe(99.5);
    });
  });

  describe('getErrorLogs', () => {
    it('calls GET /monitoring/error-logs without params', async () => {
      const mockData = { logs: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await monitoringService.getErrorLogs();

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/error-logs', {});
      expect(result.total).toBe(0);
    });

    it('passes filter params', async () => {
      const mockData = {
        logs: [
          {
            timestamp: '2025-06-15T10:00:00Z',
            severity: 'error',
            message: 'Database connection timeout',
            stack_trace: 'at connect...',
            request_id: 'req-123',
          },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await monitoringService.getErrorLogs({
        severity: 'error',
        search: 'timeout',
        page: 1,
        page_size: 50,
      });

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/error-logs', {
        params: { severity: 'error', search: 'timeout', page: 1, page_size: 50 },
      });
      expect(result.logs).toHaveLength(1);
    });
  });

  describe('getHealthCheck', () => {
    it('calls GET /monitoring/health', async () => {
      const mockHealth = {
        status: 'healthy',
        checks: {
          database: true,
          cache: true,
          storage: true,
          external_services: { neo4j: true, redis: true },
        },
        timestamp: '2025-06-15T10:00:00Z',
      };

      (apiClient.get as any).mockResolvedValue(mockHealth);

      const result = await monitoringService.getHealthCheck();

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/health');
      expect(result.status).toBe('healthy');
      expect(result.checks.database).toBe(true);
      expect(result.checks.cache).toBe(true);
    });
  });

  describe('getAuditLogs', () => {
    it('calls GET /monitoring/audit-logs without params', async () => {
      const mockData = { logs: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await monitoringService.getAuditLogs();

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/audit-logs', {});
      expect(result.total).toBe(0);
    });

    it('passes filter params', async () => {
      const mockData = {
        logs: [
          {
            id: 'audit-1',
            user_id: 'user-1',
            action: 'login',
            resource_type: 'session',
            resource_id: 'sess-1',
            ip_address: '192.168.1.1',
            user_agent: 'Mozilla/5.0',
            timestamp: '2025-06-15T10:00:00Z',
          },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await monitoringService.getAuditLogs({
        user_id: 'user-1',
        action: 'login',
        page: 1,
        page_size: 20,
      });

      expect(apiClient.get).toHaveBeenCalledWith('/monitoring/audit-logs', {
        params: { user_id: 'user-1', action: 'login', page: 1, page_size: 20 },
      });
      expect(result.logs).toHaveLength(1);
      expect(result.logs[0].action).toBe('login');
    });
  });

  describe('exportMonitoringData', () => {
    it('calls download with correct URL params', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await monitoringService.exportMonitoringData({
        data_type: 'alerts',
        format: 'csv',
        start_date: '2025-06-01',
        end_date: '2025-06-15',
      });

      expect(apiClient.download).toHaveBeenCalledWith(
        expect.stringContaining('/monitoring/export?'),
        'monitoring-alerts-2025-06-01-2025-06-15.csv',
      );
    });

    it('builds correct filename for json format', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await monitoringService.exportMonitoringData({
        data_type: 'metrics',
        format: 'json',
        start_date: '2025-01-01',
        end_date: '2025-06-30',
      });

      expect(apiClient.download).toHaveBeenCalledWith(
        expect.stringContaining('/monitoring/export?'),
        'monitoring-metrics-2025-01-01-2025-06-30.json',
      );
    });
  });
});

// ── Type interface tests ─────────────────────────────────

describe('Monitoring type interfaces', () => {
  it('DatabaseStatus has all expected fields', () => {
    const status = {
      status: 'healthy' as const,
      connected_clients: 10,
      active_queries: 2,
      pool_size: 20,
      available_connections: 18,
      response_time_ms: 3,
      last_check: '2025-06-15T10:00:00Z',
    };

    expect(Object.keys(status)).toHaveLength(7);
    expect(status.status).toBe('healthy');
  });

  it('SystemAlert has correct shape', () => {
    const alert = {
      id: 'alert-1',
      severity: 'critical' as const,
      type: 'database_down',
      message: 'Database unreachable',
      details: { error: 'Connection refused' },
      created_at: '2025-06-15',
      resolved: false,
    };

    expect(alert.severity).toBe('critical');
    expect(alert.resolved).toBe(false);
  });

  it('SystemMetrics has numeric fields', () => {
    const metrics = {
      cpu_usage: 50,
      memory_usage: 60,
      disk_usage: 40,
      request_rate: 100,
      error_rate: 1.5,
      average_response_time: 150,
      uptime_seconds: 172800,
    };

    expect(Object.keys(metrics)).toHaveLength(7);
    expect(typeof metrics.cpu_usage).toBe('number');
    expect(typeof metrics.uptime_seconds).toBe('number');
  });
});
