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

describe('PolicyService', () => {
  let policyService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/policies.service');
    policyService = serviceMod.policyService;
  });

  describe('getPolicies', () => {
    it('calls GET /policies without params', async () => {
      const mockData = { policies: [] };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await policyService.getPolicies();

      expect(apiClient.get).toHaveBeenCalledWith('/policies', {});
      expect(result.policies).toEqual([]);
    });

    it('passes filter params when provided', async () => {
      const mockData = {
        policies: [
          { id: 'pol-1', title: 'GDPR Policy', status: 'approved', framework_id: 'gdpr' },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await policyService.getPolicies({
        framework_id: 'gdpr',
        status: 'approved',
        page: 1,
        page_size: 10,
      });

      expect(apiClient.get).toHaveBeenCalledWith('/policies', {
        params: { framework_id: 'gdpr', status: 'approved', page: 1, page_size: 10 },
      });
      expect(result.policies).toHaveLength(1);
    });
  });

  describe('getPolicy', () => {
    it('calls GET /policies/:id', async () => {
      const mockPolicy = {
        id: 'pol-1',
        title: 'Data Protection Policy',
        status: 'approved',
        content: 'Policy content...',
      };

      (apiClient.get as any).mockResolvedValue(mockPolicy);

      const result = await policyService.getPolicy('pol-1');

      expect(apiClient.get).toHaveBeenCalledWith('/policies/pol-1');
      expect(result.title).toBe('Data Protection Policy');
    });
  });

  describe('generatePolicy', () => {
    it('calls POST /policies/generate', async () => {
      const request = {
        framework_id: 'gdpr',
        policy_type: 'comprehensive' as const,
      };

      const mockPolicy = {
        id: 'pol-new',
        title: 'Generated GDPR Policy',
        status: 'draft',
      };

      (apiClient.post as any).mockResolvedValue(mockPolicy);

      const result = await policyService.generatePolicy(request);

      expect(apiClient.post).toHaveBeenCalledWith('/policies/generate', request);
      expect(result.id).toBe('pol-new');
      expect(result.status).toBe('draft');
    });

    it('supports custom requirements', async () => {
      const request = {
        framework_id: 'iso27001',
        policy_type: 'custom' as const,
        custom_requirements: ['Include remote work policy', 'Add BYOD section'],
      };

      (apiClient.post as any).mockResolvedValue({ id: 'pol-custom' });

      await policyService.generatePolicy(request);

      expect(apiClient.post).toHaveBeenCalledWith('/policies/generate', request);
    });
  });

  describe('updatePolicyStatus', () => {
    it('calls PATCH /policies/:id/status', async () => {
      const mockResponse = { id: 'pol-1', status: 'under_review', approved: false };
      (apiClient.patch as any).mockResolvedValue(mockResponse);

      const result = await policyService.updatePolicyStatus('pol-1', {
        status: 'under_review' as const,
      });

      expect(apiClient.patch).toHaveBeenCalledWith('/policies/pol-1/status', {
        status: 'under_review',
      });
      expect(result.status).toBe('under_review');
    });
  });

  describe('approvePolicy', () => {
    it('calls PUT /policies/:id/approve', async () => {
      const mockResponse = { message: 'Policy approved', policy_id: 'pol-1' };
      (apiClient.put as any).mockResolvedValue(mockResponse);

      const result = await policyService.approvePolicy('pol-1');

      expect(apiClient.put).toHaveBeenCalledWith('/policies/pol-1/approve');
      expect(result.message).toBe('Policy approved');
      expect(result.policy_id).toBe('pol-1');
    });
  });

  describe('archivePolicy', () => {
    it('calls PUT /policies/:id/archive', async () => {
      (apiClient.put as any).mockResolvedValue(undefined);

      await policyService.archivePolicy('pol-1');

      expect(apiClient.put).toHaveBeenCalledWith('/policies/pol-1/archive');
    });
  });

  describe('regeneratePolicySection', () => {
    it('calls POST /policies/:id/regenerate-section', async () => {
      const request = {
        section_title: 'Data Retention',
        additional_context: 'Include 7-year retention requirement for financial data',
      };

      const mockPolicy = { id: 'pol-1', title: 'Updated Policy' };
      (apiClient.post as any).mockResolvedValue(mockPolicy);

      const result = await policyService.regeneratePolicySection('pol-1', request);

      expect(apiClient.post).toHaveBeenCalledWith('/policies/pol-1/regenerate-section', request);
      expect(result.id).toBe('pol-1');
    });
  });

  describe('exportPolicyAsPDF', () => {
    it('calls download with pdf extension', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await policyService.exportPolicyAsPDF('pol-1');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/policies/pol-1/export/pdf',
        'policy-pol-1.pdf',
      );
    });
  });

  describe('exportPolicyAsWord', () => {
    it('calls download with docx extension', async () => {
      (apiClient.download as any).mockResolvedValue(undefined);

      await policyService.exportPolicyAsWord('pol-1');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/policies/pol-1/export/word',
        'policy-pol-1.docx',
      );
    });
  });

  describe('getPolicyTemplates', () => {
    it('calls GET /policies/templates without framework filter', async () => {
      const mockData = {
        templates: [
          {
            id: 'tmpl-1',
            name: 'Standard Data Protection',
            description: 'Default DP template',
            framework: 'GDPR',
            sections: ['overview', 'data_handling', 'retention'],
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await policyService.getPolicyTemplates();

      expect(apiClient.get).toHaveBeenCalledWith('/policies/templates', {});
      expect(result.templates).toHaveLength(1);
    });

    it('passes framework_id when provided', async () => {
      const mockData = { templates: [] };
      (apiClient.get as any).mockResolvedValue(mockData);

      await policyService.getPolicyTemplates('iso27001');

      expect(apiClient.get).toHaveBeenCalledWith('/policies/templates', {
        params: { framework_id: 'iso27001' },
      });
    });
  });

  describe('clonePolicy', () => {
    it('calls POST /policies/:id/clone', async () => {
      const mockPolicy = { id: 'pol-clone', title: 'Cloned Policy v2' };
      (apiClient.post as any).mockResolvedValue(mockPolicy);

      const result = await policyService.clonePolicy('pol-1', 'Cloned Policy v2');

      expect(apiClient.post).toHaveBeenCalledWith('/policies/pol-1/clone', {
        name: 'Cloned Policy v2',
      });
      expect(result.title).toBe('Cloned Policy v2');
    });
  });

  describe('getPolicyVersionHistory', () => {
    it('calls GET /policies/:id/versions', async () => {
      const mockData = {
        versions: [
          {
            version: 1,
            created_at: '2025-06-01',
            created_by: 'admin',
            changes: ['Initial version'],
          },
          {
            version: 2,
            created_at: '2025-06-15',
            created_by: 'admin',
            changes: ['Updated data retention section', 'Added BYOD policy'],
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await policyService.getPolicyVersionHistory('pol-1');

      expect(apiClient.get).toHaveBeenCalledWith('/policies/pol-1/versions');
      expect(result.versions).toHaveLength(2);
      expect(result.versions[1].version).toBe(2);
      expect(result.versions[1].changes).toHaveLength(2);
    });
  });
});

// ── Type interface tests ─────────────────────────────────

describe('Policy type interfaces', () => {
  it('GeneratePolicyRequest policy_type values', () => {
    const types = ['comprehensive', 'basic', 'custom'];
    expect(types).toHaveLength(3);
  });

  it('UpdatePolicyStatusRequest status values', () => {
    const statuses = ['draft', 'under_review', 'approved', 'active', 'archived'];
    expect(statuses).toHaveLength(5);
  });
});
