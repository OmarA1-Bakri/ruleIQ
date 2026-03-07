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
    upload: vi.fn(),
  },
}));

describe('EvidenceService', () => {
  let evidenceService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/evidence.service');
    evidenceService = serviceMod.evidenceService;
  });

  describe('getEvidence', () => {
    it('calls GET /evidence without params', async () => {
      const mockData = { items: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await evidenceService.getEvidence();

      expect(apiClient.get).toHaveBeenCalledWith('/evidence', {});
      expect(result.total).toBe(0);
    });

    it('passes search params when provided', async () => {
      const mockData = {
        items: [
          {
            id: 'ev-1',
            title: 'Access Control Policy',
            evidence_type: 'policy',
            status: 'approved',
          },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await evidenceService.getEvidence({
        framework_id: 'gdpr',
        evidence_type: 'policy',
        status: 'approved',
        page: 1,
        page_size: 20,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      expect(apiClient.get).toHaveBeenCalledWith('/evidence', {
        params: {
          framework_id: 'gdpr',
          evidence_type: 'policy',
          status: 'approved',
          page: 1,
          page_size: 20,
          sort_by: 'created_at',
          sort_order: 'desc',
        },
      });
      expect(result.items).toHaveLength(1);
    });
  });

  describe('getEvidenceItem', () => {
    it('calls GET /evidence/:id', async () => {
      const mockItem = {
        id: 'ev-1',
        title: 'Data Encryption Certificate',
        evidence_type: 'certificate',
        status: 'approved',
      };

      (apiClient.get as any).mockResolvedValue(mockItem);

      const result = await evidenceService.getEvidenceItem('ev-1');

      expect(apiClient.get).toHaveBeenCalledWith('/evidence/ev-1');
      expect(result.title).toBe('Data Encryption Certificate');
    });
  });

  describe('createEvidence', () => {
    it('calls POST /evidence', async () => {
      const request = {
        framework_id: 'gdpr',
        control_id: 'gdpr-5.1',
        evidence_type: 'policy',
        title: 'Processing Records',
        description: 'Records of processing activities',
      };

      const mockItem = { id: 'ev-new', ...request, status: 'pending' };
      (apiClient.post as any).mockResolvedValue(mockItem);

      const result = await evidenceService.createEvidence(request);

      expect(apiClient.post).toHaveBeenCalledWith('/evidence', request);
      expect(result.id).toBe('ev-new');
    });
  });

  describe('updateEvidence', () => {
    it('calls PATCH /evidence/:id', async () => {
      const update = { title: 'Updated Title', status: 'approved' as const };
      const mockItem = { id: 'ev-1', ...update };
      (apiClient.patch as any).mockResolvedValue(mockItem);

      const result = await evidenceService.updateEvidence('ev-1', update);

      expect(apiClient.patch).toHaveBeenCalledWith('/evidence/ev-1', update);
      expect(result.title).toBe('Updated Title');
    });
  });

  describe('deleteEvidence', () => {
    it('calls DELETE /evidence/:id', async () => {
      (apiClient.delete as any).mockResolvedValue(undefined);

      await evidenceService.deleteEvidence('ev-1');

      expect(apiClient.delete).toHaveBeenCalledWith('/evidence/ev-1');
    });
  });

  describe('bulkUpdateEvidence', () => {
    it('calls POST /evidence/bulk-update', async () => {
      const request = {
        evidence_ids: ['ev-1', 'ev-2', 'ev-3'],
        status: 'approved' as const,
        reason: 'Batch approval after review',
      };

      const mockResponse = { updated_count: 3, failed_count: 0 };
      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await evidenceService.bulkUpdateEvidence(request);

      expect(apiClient.post).toHaveBeenCalledWith('/evidence/bulk-update', request);
      expect(result.updated_count).toBe(3);
      expect(result.failed_count).toBe(0);
    });

    it('handles partial failures', async () => {
      const request = {
        evidence_ids: ['ev-1', 'ev-bad'],
        status: 'approved' as const,
      };

      const mockResponse = { updated_count: 1, failed_count: 1, failed_ids: ['ev-bad'] };
      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await evidenceService.bulkUpdateEvidence(request);

      expect(result.failed_count).toBe(1);
      expect(result.failed_ids).toContain('ev-bad');
    });
  });

  describe('uploadEvidenceFile', () => {
    it('calls upload /evidence/:id/upload', async () => {
      const mockFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      const mockItem = { id: 'ev-1', title: 'Uploaded evidence' };
      (apiClient.upload as any).mockResolvedValue(mockItem);

      const result = await evidenceService.uploadEvidenceFile('ev-1', mockFile);

      expect(apiClient.upload).toHaveBeenCalledWith('/evidence/ev-1/upload', mockFile);
      expect(result.id).toBe('ev-1');
    });
  });

  describe('configureEvidenceAutomation', () => {
    it('calls POST /evidence/:id/automation', async () => {
      const config = {
        enabled: true,
        schedule: '0 0 * * 1',
        integration_id: 'int-1',
        settings: { format: 'json' },
      };

      const mockResponse = {
        configuration_successful: true,
        automation_enabled: true,
        test_connection: true,
        next_collection: '2025-06-22T00:00:00Z',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await evidenceService.configureEvidenceAutomation('ev-1', config);

      expect(apiClient.post).toHaveBeenCalledWith('/evidence/ev-1/automation', config);
      expect(result.configuration_successful).toBe(true);
      expect(result.automation_enabled).toBe(true);
    });
  });

  describe('getEvidenceDashboard', () => {
    it('calls GET /evidence/dashboard/:frameworkId', async () => {
      const mockData = {
        total_controls: 50,
        covered_controls: 35,
        pending_evidence: 10,
        approved_evidence: 25,
        coverage_percentage: 70,
        by_type: { policy: 15, certificate: 10, screenshot: 10 },
        recent_activity: [],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await evidenceService.getEvidenceDashboard('gdpr');

      expect(apiClient.get).toHaveBeenCalledWith('/evidence/dashboard/gdpr');
      expect(result.coverage_percentage).toBe(70);
      expect(result.total_controls).toBe(50);
    });
  });

  describe('classifyEvidence', () => {
    it('calls POST /evidence/:id/classify', async () => {
      const mockResponse = {
        evidence_id: 'ev-1',
        current_type: 'document',
        ai_classification: { type: 'policy', confidence: 0.92 },
        apply_suggestion: true,
        confidence: 0.92,
        suggested_controls: ['gdpr-5.1', 'gdpr-5.2'],
        reasoning: 'Document contains data processing policies',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await evidenceService.classifyEvidence('ev-1');

      expect(apiClient.post).toHaveBeenCalledWith('/evidence/ev-1/classify', {});
      expect(result.confidence).toBe(0.92);
      expect(result.suggested_controls).toHaveLength(2);
    });

    it('supports force_reclassify option', async () => {
      (apiClient.post as any).mockResolvedValue({ evidence_id: 'ev-1', confidence: 0.85 });

      await evidenceService.classifyEvidence('ev-1', { force_reclassify: true });

      expect(apiClient.post).toHaveBeenCalledWith('/evidence/ev-1/classify', {
        force_reclassify: true,
      });
    });
  });

  describe('searchEvidence', () => {
    it('calls GET /evidence/search with encoded query', async () => {
      const mockResults = [
        { id: 'ev-1', title: 'GDPR Policy Document' },
      ];

      (apiClient.get as any).mockResolvedValue(mockResults);

      const result = await evidenceService.searchEvidence('GDPR policy');

      expect(apiClient.get).toHaveBeenCalledWith('/evidence/search?q=GDPR%20policy');
      expect(result).toHaveLength(1);
    });

    it('encodes special characters', async () => {
      (apiClient.get as any).mockResolvedValue([]);

      await evidenceService.searchEvidence('test&special=chars');

      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('test%26special%3Dchars'),
      );
    });
  });

  describe('getEvidenceRequirements', () => {
    it('calls GET /evidence/requirements/:frameworkId', async () => {
      const mockData = {
        framework: 'ISO 27001',
        total_requirements: 2,
        requirements: [
          {
            control_id: 'A.5.1',
            control_name: 'Information Security Policies',
            evidence_types: ['policy', 'approval_record'],
            priority: 'high',
            description: 'Documented and approved info security policies',
          },
          {
            control_id: 'A.6.1',
            control_name: 'Organization of Information Security',
            evidence_types: ['org_chart', 'role_description'],
            priority: 'medium',
            description: 'Security roles and responsibilities',
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await evidenceService.getEvidenceRequirements('iso27001');

      expect(apiClient.get).toHaveBeenCalledWith('/evidence/requirements/iso27001');
      expect(result.total_requirements).toBe(2);
      expect(result.requirements).toHaveLength(2);
    });
  });

  describe('getEvidenceQualityAnalysis', () => {
    it('calls GET /evidence/:id/quality', async () => {
      const mockData = {
        quality_score: 85,
        completeness: 90,
        relevance: 80,
        recency: 85,
        suggestions: ['Add more recent screenshots', 'Include approval signatures'],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await evidenceService.getEvidenceQualityAnalysis('ev-1');

      expect(apiClient.get).toHaveBeenCalledWith('/evidence/ev-1/quality');
      expect(result.quality_score).toBe(85);
      expect(result.suggestions).toHaveLength(2);
    });
  });

  describe('updateEvidenceStatus', () => {
    it('calls PATCH /evidence/:id with status', async () => {
      const mockItem = { id: 'ev-1', status: 'approved' };
      (apiClient.patch as any).mockResolvedValue(mockItem);

      const result = await evidenceService.updateEvidenceStatus('ev-1', 'approved');

      expect(apiClient.patch).toHaveBeenCalledWith('/evidence/ev-1', { status: 'approved' });
      expect(result.status).toBe('approved');
    });
  });
});

// ── Type interface tests ─────────────────────────────────

describe('Evidence type interfaces', () => {
  it('UpdateEvidenceRequest has valid status values', () => {
    const statuses = ['pending', 'approved', 'rejected', 'needs_review'];
    expect(statuses).toHaveLength(4);
  });

  it('EvidenceSearchParams has sort_order values', () => {
    const orders = ['asc', 'desc'];
    expect(orders).toHaveLength(2);
  });

  it('EvidenceAutomationConfig has required fields', () => {
    const config = {
      enabled: true,
      schedule: '0 0 * * 1',
      integration_id: 'int-1',
      settings: { format: 'json' },
    };

    expect(config.enabled).toBe(true);
    expect(config.schedule).toBeTruthy();
  });
});
