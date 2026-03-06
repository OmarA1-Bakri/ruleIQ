import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the IQ agent service
vi.mock('@/lib/api/iq-agent.service', () => ({
  iqAgentService: {
    queryCompliance: vi.fn(),
    getHealth: vi.fn(),
    isComplianceQuery: vi.fn(),
    extractContext: vi.fn(),
  },
}));

describe('IQ Agent Store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it('should have correct initial state', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');
    const store = useIQAgentStore.getState();

    expect(store.currentResponse).toBeNull();
    expect(store.healthStatus).toBeNull();
    expect(store.trustStatus).toBeNull();
    expect(store.isQuerying).toBe(false);
    expect(store.isInitializing).toBe(false);
    expect(store.error).toBeNull();
    expect(store.queryHistory).toEqual([]);
  });

  it('should clear error', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');

    // Set an error first
    useIQAgentStore.setState({
      error: {
        error_type: 'processing',
        message: 'Test error',
      },
    });

    expect(useIQAgentStore.getState().error).not.toBeNull();

    useIQAgentStore.getState().clearError();
    expect(useIQAgentStore.getState().error).toBeNull();
  });

  it('should report error with valid error type', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');

    useIQAgentStore.getState().reportError({
      error_type: 'network',
      message: 'Connection failed',
      correlation_id: 'corr-123',
    });

    const error = useIQAgentStore.getState().error;
    expect(error).not.toBeNull();
    expect(error?.error_type).toBe('network');
    expect(error?.message).toBe('Connection failed');
    expect(error?.correlation_id).toBe('corr-123');
  });

  it('should normalize unknown error types to processing', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');

    useIQAgentStore.getState().reportError({
      error_type: 'unknown_type',
      message: 'Some error',
    });

    const error = useIQAgentStore.getState().error;
    expect(error?.error_type).toBe('processing');
  });

  it('should report error with all valid error types', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');
    const validTypes = ['network', 'validation', 'processing', 'rate_limit', 'service_unavailable'];

    for (const errorType of validTypes) {
      useIQAgentStore.getState().reportError({
        error_type: errorType,
        message: `Test ${errorType}`,
      });

      expect(useIQAgentStore.getState().error?.error_type).toBe(errorType);
    }
  });

  it('should report error with optional fields', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');

    useIQAgentStore.getState().reportError({
      error_type: 'rate_limit',
      message: 'Too many requests',
      correlation_id: 'corr-456',
      details: { endpoint: '/api/v1/iq/query' },
      retry_after: 30,
    });

    const error = useIQAgentStore.getState().error;
    expect(error?.retry_after).toBe(30);
    expect(error?.details).toEqual({ endpoint: '/api/v1/iq/query' });
  });

  it('should clear response', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');

    useIQAgentStore.setState({
      currentResponse: { llm_response: 'Test response' } as any,
    });

    useIQAgentStore.getState().clearResponse();
    expect(useIQAgentStore.getState().currentResponse).toBeNull();
  });

  it('should reset to initial state', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');

    // Modify state
    useIQAgentStore.setState({
      isQuerying: true,
      error: { error_type: 'network', message: 'Error' },
      queryHistory: [{ query: 'test', timestamp: '2025-01-01', success: true }],
    });

    useIQAgentStore.getState().reset();

    const state = useIQAgentStore.getState();
    expect(state.currentResponse).toBeNull();
    expect(state.healthStatus).toBeNull();
    expect(state.isQuerying).toBe(false);
    expect(state.error).toBeNull();
    expect(state.queryHistory).toEqual([]);
  });

  it('should handle queryCompliance error', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');
    const { iqAgentService } = await import('@/lib/api/iq-agent.service');

    (iqAgentService.queryCompliance as any).mockRejectedValueOnce(
      new Error('IQ Agent unavailable'),
    );

    await useIQAgentStore.getState().queryCompliance('What is GDPR?');

    const state = useIQAgentStore.getState();
    expect(state.isQuerying).toBe(false);
    expect(state.error).not.toBeNull();
    expect(state.error?.message).toBe('IQ Agent unavailable');
    expect(state.queryHistory.length).toBe(1);
    expect(state.queryHistory[0].success).toBe(false);
  });

  it('should handle queryCompliance success', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');
    const { iqAgentService } = await import('@/lib/api/iq-agent.service');

    const mockResponse = {
      data: {
        llm_response: 'GDPR is the General Data Protection Regulation.',
        summary: { compliance_score: 85 },
      },
    };

    (iqAgentService.queryCompliance as any).mockResolvedValueOnce(mockResponse);

    await useIQAgentStore.getState().queryCompliance('What is GDPR?');

    const state = useIQAgentStore.getState();
    expect(state.isQuerying).toBe(false);
    expect(state.error).toBeNull();
    expect(state.currentResponse).toEqual(mockResponse.data);
    expect(state.queryHistory.length).toBe(1);
    expect(state.queryHistory[0].success).toBe(true);
    expect(state.queryHistory[0].query).toBe('What is GDPR?');
  });

  it('should handle checkHealth success', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');
    const { iqAgentService } = await import('@/lib/api/iq-agent.service');

    const mockHealth = {
      status: 'healthy',
      neo4j_connected: true,
      version: '1.0.0',
    };

    (iqAgentService.getHealth as any).mockResolvedValueOnce(mockHealth);

    await useIQAgentStore.getState().checkHealth();

    const state = useIQAgentStore.getState();
    expect(state.isInitializing).toBe(false);
    expect(state.healthStatus).toEqual(mockHealth);
    expect(state.error).toBeNull();
  });

  it('should handle checkHealth failure', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');
    const { iqAgentService } = await import('@/lib/api/iq-agent.service');

    (iqAgentService.getHealth as any).mockRejectedValueOnce(
      new Error('Service down'),
    );

    await useIQAgentStore.getState().checkHealth();

    const state = useIQAgentStore.getState();
    expect(state.isInitializing).toBe(false);
    expect(state.error).not.toBeNull();
    expect(state.error?.error_type).toBe('service_unavailable');
    expect(state.error?.message).toBe('Service down');
  });

  it('should provide selector hooks', async () => {
    const mod = await import('@/lib/stores/iq-agent.store');

    expect(typeof mod.useIQCurrentResponse).toBe('function');
    expect(typeof mod.useIQHealthStatus).toBe('function');
    expect(typeof mod.useIQTrustStatus).toBe('function');
    expect(typeof mod.useIQIsQuerying).toBe('function');
    expect(typeof mod.useIQError).toBe('function');
    expect(typeof mod.useIQQueryHistory).toBe('function');
  });

  it('should provide all expected methods', async () => {
    const { useIQAgentStore } = await import('@/lib/stores/iq-agent.store');
    const store = useIQAgentStore.getState();

    expect(typeof store.queryCompliance).toBe('function');
    expect(typeof store.checkHealth).toBe('function');
    expect(typeof store.clearError).toBe('function');
    expect(typeof store.reportError).toBe('function');
    expect(typeof store.clearResponse).toBe('function');
    expect(typeof store.reset).toBe('function');
  });
});
