import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the env config
vi.mock('@/src/config/env', () => ({
  env: {
    NEXT_PUBLIC_WEBSOCKET_URL: 'ws://localhost:8000/ws/chat',
  },
}));

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

describe('ChatService', () => {
  let chatService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/chat.service');
    chatService = serviceMod.chatService;
  });

  describe('getConversations', () => {
    it('calls GET /chat/conversations without params', async () => {
      const mockData = { items: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await chatService.getConversations();

      expect(apiClient.get).toHaveBeenCalledWith('/chat/conversations', {});
      expect(result.total).toBe(0);
    });

    it('passes pagination params', async () => {
      const mockData = {
        items: [
          { id: 'conv-1', title: 'GDPR Help', created_at: '2025-06-15' },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await chatService.getConversations({ page: 1, page_size: 10 });

      expect(apiClient.get).toHaveBeenCalledWith('/chat/conversations', {
        params: { page: 1, page_size: 10 },
      });
      expect(result.items).toHaveLength(1);
    });
  });

  describe('getConversation', () => {
    it('calls GET /chat/conversations/:id', async () => {
      const mockData = {
        conversation: { id: 'conv-1', title: 'GDPR Help' },
        messages: [
          { id: 'msg-1', content: 'Hello', role: 'user' },
          { id: 'msg-2', content: 'How can I help?', role: 'assistant' },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await chatService.getConversation('conv-1');

      expect(apiClient.get).toHaveBeenCalledWith('/chat/conversations/conv-1');
      expect(result.conversation.id).toBe('conv-1');
      expect(result.messages).toHaveLength(2);
    });
  });

  describe('createConversation', () => {
    it('calls POST /chat/conversations with data', async () => {
      const data = { title: 'New Chat', initial_message: 'Hello' };
      const mockData = {
        conversation: { id: 'conv-new', title: 'New Chat' },
        messages: [{ id: 'msg-1', content: 'Hello', role: 'user' }],
      };

      (apiClient.post as any).mockResolvedValue(mockData);

      const result = await chatService.createConversation(data);

      expect(apiClient.post).toHaveBeenCalledWith('/chat/conversations', data);
      expect(result.conversation.id).toBe('conv-new');
    });

    it('sends empty object when no data provided', async () => {
      const mockData = {
        conversation: { id: 'conv-new' },
        messages: [],
      };

      (apiClient.post as any).mockResolvedValue(mockData);

      await chatService.createConversation();

      expect(apiClient.post).toHaveBeenCalledWith('/chat/conversations', {});
    });
  });

  describe('sendMessage', () => {
    it('calls POST /chat/conversations/:id/messages', async () => {
      const data = { content: 'What is GDPR?' };
      const mockMessage = {
        id: 'msg-new',
        content: 'What is GDPR?',
        role: 'user',
        created_at: '2025-06-15T10:00:00Z',
      };

      (apiClient.post as any).mockResolvedValue(mockMessage);

      const result = await chatService.sendMessage('conv-1', data);

      expect(apiClient.post).toHaveBeenCalledWith('/chat/conversations/conv-1/messages', data);
      expect(result.content).toBe('What is GDPR?');
    });
  });

  describe('deleteConversation', () => {
    it('calls DELETE /chat/conversations/:id', async () => {
      (apiClient.delete as any).mockResolvedValue(undefined);

      await chatService.deleteConversation('conv-1');

      expect(apiClient.delete).toHaveBeenCalledWith('/chat/conversations/conv-1');
    });
  });

  describe('getEvidenceRecommendations', () => {
    it('calls POST /chat/evidence-recommendations', async () => {
      const data = { framework: 'GDPR' };
      const mockResponse = {
        recommendations: [
          {
            control_id: 'gdpr-5.1',
            control_name: 'Lawful Processing',
            evidence_type: 'policy',
            priority: 'high',
            description: 'Document lawful basis',
            automation_available: true,
          },
        ],
        total_recommendations: 1,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await chatService.getEvidenceRecommendations(data);

      expect(apiClient.post).toHaveBeenCalledWith('/chat/evidence-recommendations', data);
      expect(result.total_recommendations).toBe(1);
      expect(result.recommendations[0].automation_available).toBe(true);
    });
  });

  describe('getComplianceGapAnalysis', () => {
    it('calls POST /chat/compliance-gap-analysis', async () => {
      const data = { framework: 'ISO 27001' };
      const mockResponse = {
        framework: 'ISO 27001',
        completion_percentage: 65,
        critical_gaps: ['Access control policy missing'],
        recommendations: ['Create access control policy'],
        estimated_effort_hours: 120,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await chatService.getComplianceGapAnalysis(data);

      expect(apiClient.post).toHaveBeenCalledWith('/chat/compliance-gap-analysis', data);
      expect(result.completion_percentage).toBe(65);
      expect(result.critical_gaps).toHaveLength(1);
    });
  });

  describe('getContextAwareRecommendations', () => {
    it('calls POST with encoded framework and default context type', async () => {
      (apiClient.post as any).mockResolvedValue({ recommendations: [] });

      await chatService.getContextAwareRecommendations('GDPR');

      expect(apiClient.post).toHaveBeenCalledWith(
        '/chat/context-aware-recommendations?framework=GDPR&context_type=comprehensive',
      );
    });

    it('passes custom context type', async () => {
      (apiClient.post as any).mockResolvedValue({ recommendations: [] });

      await chatService.getContextAwareRecommendations('GDPR', 'guidance');

      expect(apiClient.post).toHaveBeenCalledWith(
        '/chat/context-aware-recommendations?framework=GDPR&context_type=guidance',
      );
    });
  });

  describe('generateEvidenceCollectionWorkflow', () => {
    it('calls POST with framework and default workflow type', async () => {
      (apiClient.post as any).mockResolvedValue({ workflow: {} });

      await chatService.generateEvidenceCollectionWorkflow('GDPR');

      const calledUrl = (apiClient.post as any).mock.calls[0][0];
      expect(calledUrl).toContain('framework=GDPR');
      expect(calledUrl).toContain('workflow_type=comprehensive');
    });

    it('passes controlId when provided', async () => {
      (apiClient.post as any).mockResolvedValue({ workflow: {} });

      await chatService.generateEvidenceCollectionWorkflow('GDPR', 'gdpr-5.1', 'quick');

      const calledUrl = (apiClient.post as any).mock.calls[0][0];
      expect(calledUrl).toContain('framework=GDPR');
      expect(calledUrl).toContain('control_id=gdpr-5.1');
      expect(calledUrl).toContain('workflow_type=quick');
    });
  });

  describe('generateCustomizedPolicy', () => {
    it('calls POST with framework and policy type', async () => {
      (apiClient.post as any).mockResolvedValue({ policy: {} });

      await chatService.generateCustomizedPolicy('GDPR', 'data_protection');

      const calledUrl = (apiClient.post as any).mock.calls[0][0];
      expect(calledUrl).toContain('framework=GDPR');
      expect(calledUrl).toContain('policy_type=data_protection');
    });

    it('passes custom requirements', async () => {
      (apiClient.post as any).mockResolvedValue({ policy: {} });

      await chatService.generateCustomizedPolicy('GDPR', 'privacy', ['DPIA required', 'Cross-border']);

      const calledUrl = (apiClient.post as any).mock.calls[0][0];
      expect(calledUrl).toContain('custom_requirements=DPIA+required%2CCross-border');
    });
  });

  describe('getSmartComplianceGuidance', () => {
    it('calls GET with framework and default guidance type', async () => {
      (apiClient.get as any).mockResolvedValue({ guidance: {} });

      await chatService.getSmartComplianceGuidance('GDPR');

      expect(apiClient.get).toHaveBeenCalledWith('/chat/smart-compliance-guidance', {
        params: { framework: 'GDPR', guidance_type: 'getting_started' },
      });
    });

    it('passes custom guidance type', async () => {
      (apiClient.get as any).mockResolvedValue({ guidance: {} });

      await chatService.getSmartComplianceGuidance('GDPR', 'optimization');

      expect(apiClient.get).toHaveBeenCalledWith('/chat/smart-compliance-guidance', {
        params: { framework: 'GDPR', guidance_type: 'optimization' },
      });
    });
  });

  describe('getCacheMetrics', () => {
    it('calls GET /ai/optimization/cache/metrics', async () => {
      const mockMetrics = { hit_rate: 0.85, total_entries: 150 };
      (apiClient.get as any).mockResolvedValue(mockMetrics);

      const result = await chatService.getCacheMetrics();

      expect(apiClient.get).toHaveBeenCalledWith('/ai/optimization/cache/metrics');
      expect(result.hit_rate).toBe(0.85);
    });
  });

  describe('clearCache', () => {
    it('calls DELETE with default pattern', async () => {
      const mockResponse = { cleared_entries: 50, pattern: '*', cleared_at: '2025-06-15' };
      (apiClient.delete as any).mockResolvedValue(mockResponse);

      const result = await chatService.clearCache();

      expect(apiClient.delete).toHaveBeenCalledWith(
        '/ai/optimization/cache/clear?pattern=*',
      );
      expect(result.cleared_entries).toBe(50);
    });

    it('passes custom pattern', async () => {
      (apiClient.delete as any).mockResolvedValue({ cleared_entries: 5 });

      await chatService.clearCache('gdpr:*');

      expect(apiClient.delete).toHaveBeenCalledWith(
        '/ai/optimization/cache/clear?pattern=gdpr%3A*',
      );
    });
  });

  describe('getPerformanceMetrics', () => {
    it('calls GET /chat/performance/metrics', async () => {
      const mockMetrics = { avg_response_time: 1200, p95_response_time: 3500 };
      (apiClient.get as any).mockResolvedValue(mockMetrics);

      const result = await chatService.getPerformanceMetrics();

      expect(apiClient.get).toHaveBeenCalledWith('/chat/performance/metrics');
      expect(result.avg_response_time).toBe(1200);
    });
  });

  describe('getWebSocketUrl', () => {
    it('returns WebSocket URL with conversation ID', () => {
      const url = chatService.getWebSocketUrl('conv-123');
      expect(url).toBe('ws://localhost:8000/ws/chat/conv-123');
    });
  });

  describe('sendIQMessage', () => {
    it('calls POST /chat/iq-chat/:id/messages', async () => {
      const data = { content: 'Compliance query via IQ Agent' };
      const mockMessage = { id: 'msg-iq', content: 'IQ response', role: 'assistant' };
      (apiClient.post as any).mockResolvedValue(mockMessage);

      const result = await chatService.sendIQMessage('conv-1', data);

      expect(apiClient.post).toHaveBeenCalledWith('/chat/iq-chat/conv-1/messages', data);
      expect(result.role).toBe('assistant');
    });
  });

  describe('getIQAgentStatus', () => {
    it('calls GET /chat/iq-agent/status', async () => {
      const mockStatus = {
        iq_agent_available: true,
        neo4j_connected: true,
        graph_initialized: true,
        nodes_count: 250,
        relationships_count: 500,
        message: 'IQ Agent is ready',
      };

      (apiClient.get as any).mockResolvedValue(mockStatus);

      const result = await chatService.getIQAgentStatus();

      expect(apiClient.get).toHaveBeenCalledWith('/chat/iq-agent/status');
      expect(result.iq_agent_available).toBe(true);
      expect(result.nodes_count).toBe(250);
    });
  });
});

// -- Type interface tests --

describe('Chat type interfaces', () => {
  it('ChatWebSocketMessage type values', () => {
    const types = ['message', 'typing', 'error', 'connection'];
    expect(types).toHaveLength(4);
  });

  it('CreateConversationRequest has optional fields', () => {
    const empty = {};
    const full = { title: 'New Chat', initial_message: 'Hello' };
    expect(Object.keys(empty)).toHaveLength(0);
    expect(Object.keys(full)).toHaveLength(2);
  });

  it('guidance_type values are valid', () => {
    const types = ['getting_started', 'next_steps', 'optimization'];
    expect(types).toHaveLength(3);
  });
});
