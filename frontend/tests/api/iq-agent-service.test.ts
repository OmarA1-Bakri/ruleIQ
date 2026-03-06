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

describe('IQAgentService', () => {
  let iqAgentService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/iq-agent.service');
    iqAgentService = serviceMod.iqAgentService;
  });

  describe('queryCompliance', () => {
    it('calls POST /iq/query with defaults', async () => {
      const mockResponse = {
        answer: 'GDPR requires data processing to have a lawful basis.',
        confidence: 0.95,
        sources: ['GDPR Article 6'],
        graph_analysis: {},
        recommendations: ['Document lawful basis for each processing activity'],
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await iqAgentService.queryCompliance('What are GDPR requirements?');

      expect(apiClient.post).toHaveBeenCalledWith('/iq/query', {
        query: 'What are GDPR requirements?',
        include_graph_analysis: true,
        include_recommendations: true,
      });
      expect(result.answer).toContain('GDPR');
      expect(result.confidence).toBe(0.95);
    });

    it('passes context when provided', async () => {
      const mockResponse = { answer: 'Based on your context...', confidence: 0.9 };
      (apiClient.post as any).mockResolvedValue(mockResponse);

      const context = {
        regulations: ['ISO 27001'],
        risk_tolerance: 'medium' as const,
      };

      await iqAgentService.queryCompliance('How to implement access controls?', context);

      expect(apiClient.post).toHaveBeenCalledWith('/iq/query', {
        query: 'How to implement access controls?',
        context,
        include_graph_analysis: true,
        include_recommendations: true,
      });
    });

    it('respects custom options', async () => {
      (apiClient.post as any).mockResolvedValue({ answer: 'Result' });

      await iqAgentService.queryCompliance('Query', undefined, {
        include_graph_analysis: false,
        include_recommendations: false,
      });

      expect(apiClient.post).toHaveBeenCalledWith('/iq/query', {
        query: 'Query',
        include_graph_analysis: false,
        include_recommendations: false,
      });
    });
  });

  describe('getHealth', () => {
    it('calls GET /iq/health', async () => {
      const mockHealth = {
        status: 'healthy',
        neo4j_connected: true,
        model_loaded: true,
        uptime_seconds: 3600,
      };

      (apiClient.get as any).mockResolvedValue(mockHealth);

      const result = await iqAgentService.getHealth();

      expect(apiClient.get).toHaveBeenCalledWith('/iq/health');
      expect(result.status).toBe('healthy');
      expect(result.neo4j_connected).toBe(true);
    });
  });

  describe('storeMemory', () => {
    it('calls POST /iq/memory/store', async () => {
      const request = {
        content: 'User completed GDPR assessment with 85% score',
        memory_type: 'assessment_result',
        metadata: { framework: 'GDPR', score: 85 },
      };

      const mockResponse = {
        memory_id: 'mem-1',
        stored: true,
        timestamp: '2025-06-15T10:00:00Z',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await iqAgentService.storeMemory(request);

      expect(apiClient.post).toHaveBeenCalledWith('/iq/memory/store', request);
      expect(result.memory_id).toBe('mem-1');
      expect(result.stored).toBe(true);
    });
  });

  describe('retrieveMemories', () => {
    it('calls POST /iq/memory/retrieve', async () => {
      const request = {
        query: 'GDPR assessment results',
        limit: 5,
      };

      const mockResponse = {
        memories: [
          {
            id: 'mem-1',
            content: 'GDPR assessment completed',
            relevance_score: 0.92,
            created_at: '2025-06-15',
          },
        ],
        total: 1,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await iqAgentService.retrieveMemories(request);

      expect(apiClient.post).toHaveBeenCalledWith('/iq/memory/retrieve', request);
      expect(result.memories).toHaveLength(1);
      expect(result.memories[0].relevance_score).toBe(0.92);
    });
  });

  describe('initializeGraph', () => {
    it('calls POST /iq/graph/initialize with data', async () => {
      const request = {
        frameworks: ['GDPR', 'ISO 27001'],
        force_rebuild: true,
      };

      const mockResponse = {
        success: true,
        nodes_created: 250,
        relationships_created: 500,
        time_taken_ms: 1500,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await iqAgentService.initializeGraph(request);

      expect(apiClient.post).toHaveBeenCalledWith('/iq/graph/initialize', request);
      expect(result.success).toBe(true);
      expect(result.nodes_created).toBe(250);
    });

    it('sends empty object when no data provided', async () => {
      (apiClient.post as any).mockResolvedValue({ success: true });

      await iqAgentService.initializeGraph();

      expect(apiClient.post).toHaveBeenCalledWith('/iq/graph/initialize', {});
    });
  });

  // ── Synchronous utility methods ──────────────────────────

  describe('isComplianceQuery', () => {
    it('returns true for GDPR queries', () => {
      expect(iqAgentService.isComplianceQuery('Tell me about GDPR requirements')).toBe(true);
    });

    it('returns true for ISO 27001 queries', () => {
      expect(iqAgentService.isComplianceQuery('What is ISO 27001?')).toBe(true);
      expect(iqAgentService.isComplianceQuery('Explain iso27001 controls')).toBe(true);
    });

    it('returns true for general compliance terms', () => {
      expect(iqAgentService.isComplianceQuery('How to pass a compliance audit?')).toBe(true);
      expect(iqAgentService.isComplianceQuery('Data protection best practices')).toBe(true);
      expect(iqAgentService.isComplianceQuery('Risk assessment methodology')).toBe(true);
    });

    it('returns true for security-related queries', () => {
      expect(iqAgentService.isComplianceQuery('What is access control?')).toBe(true);
      expect(iqAgentService.isComplianceQuery('Encryption standards')).toBe(true);
      expect(iqAgentService.isComplianceQuery('Vulnerability management')).toBe(true);
    });

    it('returns true for various frameworks', () => {
      expect(iqAgentService.isComplianceQuery('PCI DSS requirements')).toBe(true);
      expect(iqAgentService.isComplianceQuery('HIPAA compliance')).toBe(true);
      expect(iqAgentService.isComplianceQuery('SOX controls')).toBe(true);
      expect(iqAgentService.isComplianceQuery('NIST framework')).toBe(true);
      expect(iqAgentService.isComplianceQuery('Cyber Essentials certification')).toBe(true);
    });

    it('returns false for non-compliance queries', () => {
      expect(iqAgentService.isComplianceQuery('What is the weather today?')).toBe(false);
      expect(iqAgentService.isComplianceQuery('How to make coffee')).toBe(false);
      expect(iqAgentService.isComplianceQuery('Tell me a joke')).toBe(false);
    });

    it('is case-insensitive', () => {
      expect(iqAgentService.isComplianceQuery('GDPR REQUIREMENTS')).toBe(true);
      expect(iqAgentService.isComplianceQuery('gdpr requirements')).toBe(true);
      expect(iqAgentService.isComplianceQuery('Gdpr Requirements')).toBe(true);
    });
  });

  describe('extractContext', () => {
    it('detects GDPR regulation', () => {
      const context = iqAgentService.extractContext('How to comply with GDPR?');
      expect(context.regulations).toContain('GDPR');
    });

    it('detects ISO 27001 regulation', () => {
      const context = iqAgentService.extractContext('ISO 27001 implementation steps');
      expect(context.regulations).toContain('ISO 27001');
    });

    it('detects iso27001 without space', () => {
      const context = iqAgentService.extractContext('iso27001 controls list');
      expect(context.regulations).toContain('ISO 27001');
    });

    it('detects PCI DSS', () => {
      const context = iqAgentService.extractContext('PCI DSS requirement 8');
      expect(context.regulations).toContain('PCI DSS');
    });

    it('detects PCI without DSS suffix', () => {
      const context = iqAgentService.extractContext('PCI compliance requirements');
      expect(context.regulations).toContain('PCI DSS');
    });

    it('detects HIPAA', () => {
      const context = iqAgentService.extractContext('HIPAA privacy rule');
      expect(context.regulations).toContain('HIPAA');
    });

    it('detects SOX', () => {
      const context = iqAgentService.extractContext('SOX internal controls');
      expect(context.regulations).toContain('SOX');
    });

    it('detects NIST', () => {
      const context = iqAgentService.extractContext('NIST cybersecurity framework');
      expect(context.regulations).toContain('NIST');
    });

    it('detects Cyber Essentials', () => {
      const context = iqAgentService.extractContext('Cyber Essentials certification process');
      expect(context.regulations).toContain('Cyber Essentials');
    });

    it('detects multiple regulations', () => {
      const context = iqAgentService.extractContext('GDPR and ISO 27001 overlap areas');
      expect(context.regulations).toContain('GDPR');
      expect(context.regulations).toContain('ISO 27001');
    });

    it('sets low risk tolerance for urgent language', () => {
      expect(iqAgentService.extractContext('Urgent GDPR compliance needed').risk_tolerance).toBe('low');
      expect(iqAgentService.extractContext('Critical security issue').risk_tolerance).toBe('low');
      expect(iqAgentService.extractContext('Fix this immediately').risk_tolerance).toBe('low');
    });

    it('sets medium risk tolerance for moderate language', () => {
      expect(iqAgentService.extractContext('Moderate risk assessment needed').risk_tolerance).toBe('medium');
      expect(iqAgentService.extractContext('Looking for a balanced approach').risk_tolerance).toBe('medium');
    });

    it('defaults to high risk tolerance', () => {
      expect(iqAgentService.extractContext('General compliance question').risk_tolerance).toBe('high');
      expect(iqAgentService.extractContext('Best practices for data handling').risk_tolerance).toBe('high');
    });

    it('returns empty regulations for non-compliance queries', () => {
      const context = iqAgentService.extractContext('How to make coffee');
      expect(context.regulations).toBeUndefined();
    });
  });
});
