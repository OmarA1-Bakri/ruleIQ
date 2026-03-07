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

describe('FoundationEvidenceService', () => {
  let foundationEvidenceService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/foundation-evidence.service');
    foundationEvidenceService = serviceMod.foundationEvidenceService;
  });

  // -- API methods --

  describe('configureAWS', () => {
    it('calls POST /foundation/evidence/aws/configure', async () => {
      const config = {
        auth_type: 'access_key' as const,
        access_key_id: 'AKIAIOSFODNN7EXAMPLE',
        secret_access_key: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
        region: 'eu-west-2',
      };

      const mockResponse = {
        integration_id: 'int-aws-1',
        provider: 'aws',
        status: 'connected',
        account_id: '123456789012',
        region: 'eu-west-2',
        capabilities: ['iam', 'cloudtrail', 's3'],
        message: 'AWS integration configured successfully',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await foundationEvidenceService.configureAWS(config);

      expect(apiClient.post).toHaveBeenCalledWith('/foundation/evidence/aws/configure', config);
      expect(result.integration_id).toBe('int-aws-1');
      expect(result.capabilities).toHaveLength(3);
    });
  });

  describe('configureOkta', () => {
    it('calls POST /foundation/evidence/okta/configure', async () => {
      const config = { domain: 'mycompany', api_token: 'token123' };
      const mockResponse = {
        integration_id: 'int-okta-1',
        provider: 'okta',
        status: 'connected',
        domain: 'mycompany',
        capabilities: ['users', 'groups', 'mfa'],
        message: 'Okta configured',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await foundationEvidenceService.configureOkta(config);

      expect(apiClient.post).toHaveBeenCalledWith('/foundation/evidence/okta/configure', config);
      expect(result.provider).toBe('okta');
    });
  });

  describe('configureGoogleWorkspace', () => {
    it('calls POST /foundation/evidence/google/configure', async () => {
      const config = {
        domain: 'company.com',
        client_id: 'client-123',
        client_secret: 'secret-456',
        refresh_token: 'refresh-789',
      };

      (apiClient.post as any).mockResolvedValue({ integration_id: 'int-gw-1', provider: 'google_workspace' });

      const result = await foundationEvidenceService.configureGoogleWorkspace(config);

      expect(apiClient.post).toHaveBeenCalledWith('/foundation/evidence/google/configure', config);
      expect(result.integration_id).toBe('int-gw-1');
    });
  });

  describe('configureMicrosoft', () => {
    it('calls POST /foundation/evidence/microsoft/configure', async () => {
      const config = {
        tenant_id: 'tenant-123',
        client_id: 'client-456',
        client_secret: 'secret-789',
      };

      (apiClient.post as any).mockResolvedValue({ integration_id: 'int-ms-1', provider: 'microsoft_365' });

      const result = await foundationEvidenceService.configureMicrosoft(config);

      expect(apiClient.post).toHaveBeenCalledWith('/foundation/evidence/microsoft/configure', config);
      expect(result.integration_id).toBe('int-ms-1');
    });
  });

  describe('startCollection', () => {
    it('calls POST /foundation/evidence/collect', async () => {
      const request = {
        framework_id: 'soc2',
        business_profile: { industry: 'technology' },
        evidence_types: ['iam_policies', 'cloudtrail_logs'],
        collection_mode: 'immediate' as const,
      };

      const mockResponse = {
        collection_id: 'col-1',
        status: 'in_progress',
        message: 'Collection started',
        estimated_duration: '15 minutes',
        evidence_types: ['iam_policies', 'cloudtrail_logs'],
        created_at: '2025-06-15T10:00:00Z',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await foundationEvidenceService.startCollection(request);

      expect(apiClient.post).toHaveBeenCalledWith('/foundation/evidence/collect', request);
      expect(result.collection_id).toBe('col-1');
      expect(result.evidence_types).toHaveLength(2);
    });
  });

  describe('getCollectionStatus', () => {
    it('calls GET /foundation/evidence/collect/:id/status', async () => {
      const mockStatus = {
        collection_id: 'col-1',
        status: 'in_progress',
        progress_percentage: 45,
        evidence_collected: 5,
        total_expected: 11,
        quality_score: 8.5,
        started_at: '2025-06-15T10:00:00Z',
        current_activity: 'Collecting IAM policies',
        errors: [],
      };

      (apiClient.get as any).mockResolvedValue(mockStatus);

      const result = await foundationEvidenceService.getCollectionStatus('col-1');

      expect(apiClient.get).toHaveBeenCalledWith('/foundation/evidence/collect/col-1/status');
      expect(result.progress_percentage).toBe(45);
    });
  });

  describe('getCollectionResults', () => {
    it('calls GET with query params', async () => {
      const mockResults = {
        collection_id: 'col-1',
        status: 'completed',
        total_evidence: 11,
        page: 1,
        page_size: 10,
        evidence: [{ evidence_id: 'ev-1', evidence_type: 'iam_policies' }],
      };

      (apiClient.get as any).mockResolvedValue(mockResults);

      const result = await foundationEvidenceService.getCollectionResults('col-1', {
        evidence_type: 'iam_policies',
        page: 1,
        page_size: 10,
      });

      const calledUrl = (apiClient.get as any).mock.calls[0][0];
      expect(calledUrl).toContain('/foundation/evidence/collect/col-1/results');
      expect(calledUrl).toContain('evidence_type=iam_policies');
      expect(calledUrl).toContain('page=1');
      expect(result.total_evidence).toBe(11);
    });

    it('handles no options', async () => {
      (apiClient.get as any).mockResolvedValue({ evidence: [] });

      await foundationEvidenceService.getCollectionResults('col-1');

      const calledUrl = (apiClient.get as any).mock.calls[0][0];
      expect(calledUrl).toContain('/foundation/evidence/collect/col-1/results');
    });
  });

  describe('checkHealth', () => {
    it('calls GET /foundation/evidence/health', async () => {
      const mockHealth = {
        overall_status: 'healthy',
        integrations: [
          { integration_id: 'int-1', provider: 'aws', status: 'healthy' },
        ],
        total_integrations: 1,
        healthy_integrations: 1,
        timestamp: '2025-06-15T10:00:00Z',
      };

      (apiClient.get as any).mockResolvedValue(mockHealth);

      const result = await foundationEvidenceService.checkHealth();

      expect(apiClient.get).toHaveBeenCalledWith('/foundation/evidence/health');
      expect(result.overall_status).toBe('healthy');
      expect(result.healthy_integrations).toBe(1);
    });
  });

  // -- Sync utility methods --

  describe('getSupportedEvidenceTypes', () => {
    it('returns AWS evidence types', () => {
      const types = foundationEvidenceService.getSupportedEvidenceTypes('aws');
      expect(types).toContain('iam_policies');
      expect(types).toContain('cloudtrail_logs');
      expect(types).toContain('s3_buckets');
      expect(types.length).toBeGreaterThan(5);
    });

    it('returns Okta evidence types', () => {
      const types = foundationEvidenceService.getSupportedEvidenceTypes('okta');
      expect(types).toContain('users');
      expect(types).toContain('mfa_factors');
      expect(types).toContain('system_logs');
    });

    it('returns Google Workspace evidence types', () => {
      const types = foundationEvidenceService.getSupportedEvidenceTypes('google_workspace');
      expect(types).toContain('user_directory');
      expect(types).toContain('admin_activity_logs');
    });

    it('returns Microsoft 365 evidence types', () => {
      const types = foundationEvidenceService.getSupportedEvidenceTypes('microsoft_365');
      expect(types).toContain('user_directory');
      expect(types).toContain('organization_configuration');
    });

    it('returns empty array for unknown provider', () => {
      const types = foundationEvidenceService.getSupportedEvidenceTypes('unknown_provider');
      expect(types).toEqual([]);
    });
  });

  describe('getComplianceControlMapping', () => {
    it('returns mapping with SOC2 controls', () => {
      const mapping = foundationEvidenceService.getComplianceControlMapping();
      expect(mapping.iam_policies).toContain('CC6.1');
      expect(mapping.cloudtrail_logs).toContain('CC7.2');
      expect(mapping.mfa_factors).toContain('CC6.7');
    });

    it('covers all major evidence types', () => {
      const mapping = foundationEvidenceService.getComplianceControlMapping();
      expect(Object.keys(mapping).length).toBeGreaterThan(10);
    });
  });

  describe('estimateCollectionTime', () => {
    it('estimates time for known evidence types', () => {
      const result = foundationEvidenceService.estimateCollectionTime(['iam_policies', 'iam_users']);
      expect(result.estimated_minutes).toBeGreaterThan(0);
      expect(result.confidence).toBe('high');
    });

    it('uses default time for unknown evidence types', () => {
      const result = foundationEvidenceService.estimateCollectionTime(['unknown_type']);
      expect(result.estimated_minutes).toBeGreaterThan(0);
      expect(result.confidence).toBe('low');
    });

    it('returns medium confidence for mixed types', () => {
      const result = foundationEvidenceService.estimateCollectionTime([
        'iam_policies', 'iam_users', 'iam_roles', // known
        'custom_type', // unknown
      ]);
      expect(result.confidence).toBe('medium');
    });

    it('handles empty array', () => {
      const result = foundationEvidenceService.estimateCollectionTime([]);
      expect(result.estimated_minutes).toBe(0);
    });
  });

  describe('validateAWSConfiguration', () => {
    it('returns no errors for valid access key config', () => {
      const config = {
        auth_type: 'access_key' as const,
        access_key_id: 'AKIAIOSFODNN7EXAMPLE',
        secret_access_key: 'wJalrXUtnFEMI/K7MDENG',
        region: 'eu-west-2',
      };
      const errors = foundationEvidenceService.validateAWSConfiguration(config);
      expect(errors).toHaveLength(0);
    });

    it('returns errors for missing access key fields', () => {
      const config = {
        auth_type: 'access_key' as const,
        region: 'eu-west-2',
      };
      const errors = foundationEvidenceService.validateAWSConfiguration(config);
      expect(errors).toContain('Access Key ID is required for access key authentication');
      expect(errors).toContain('Secret Access Key is required for access key authentication');
    });

    it('returns error for missing role ARN in role assumption', () => {
      const config = {
        auth_type: 'role_assumption' as const,
        region: 'eu-west-2',
      };
      const errors = foundationEvidenceService.validateAWSConfiguration(config);
      expect(errors).toContain('Role ARN is required for role assumption authentication');
    });

    it('returns error for missing region', () => {
      const config = { auth_type: 'access_key' as const, access_key_id: 'key', secret_access_key: 'secret' } as any;
      const errors = foundationEvidenceService.validateAWSConfiguration(config);
      expect(errors).toContain('AWS region is required');
    });
  });

  describe('validateOktaConfiguration', () => {
    it('returns no errors for valid config', () => {
      const config = { domain: 'mycompany', api_token: 'token123' };
      const errors = foundationEvidenceService.validateOktaConfiguration(config);
      expect(errors).toHaveLength(0);
    });

    it('returns error for missing domain', () => {
      const config = { domain: '', api_token: 'token123' };
      const errors = foundationEvidenceService.validateOktaConfiguration(config);
      expect(errors).toContain('Okta domain is required');
    });

    it('returns error for invalid domain format', () => {
      const config = { domain: 'my company!', api_token: 'token123' };
      const errors = foundationEvidenceService.validateOktaConfiguration(config);
      expect(errors).toContain('Invalid Okta domain format');
    });

    it('returns error for missing API token', () => {
      const config = { domain: 'mycompany', api_token: '' };
      const errors = foundationEvidenceService.validateOktaConfiguration(config);
      expect(errors).toContain('Okta API token is required');
    });
  });

  describe('validateGoogleWorkspaceConfiguration', () => {
    it('returns no errors for valid config', () => {
      const config = {
        domain: 'company.com',
        client_id: 'id',
        client_secret: 'secret',
        refresh_token: 'token',
      };
      const errors = foundationEvidenceService.validateGoogleWorkspaceConfiguration(config);
      expect(errors).toHaveLength(0);
    });

    it('returns errors for all missing fields', () => {
      const config = { domain: '', client_id: '', client_secret: '', refresh_token: '' };
      const errors = foundationEvidenceService.validateGoogleWorkspaceConfiguration(config);
      expect(errors).toHaveLength(4);
    });
  });

  describe('validateMicrosoftConfiguration', () => {
    it('returns no errors for valid config', () => {
      const config = { tenant_id: 'tid', client_id: 'cid', client_secret: 'csecret' };
      const errors = foundationEvidenceService.validateMicrosoftConfiguration(config);
      expect(errors).toHaveLength(0);
    });

    it('returns errors for all missing fields', () => {
      const config = { tenant_id: '', client_id: '', client_secret: '' };
      const errors = foundationEvidenceService.validateMicrosoftConfiguration(config);
      expect(errors).toHaveLength(3);
    });
  });

  describe('generateCollectionSummary', () => {
    it('generates summary from collected evidence', () => {
      const results = [
        {
          evidence_id: 'ev-1',
          evidence_type: 'iam_policies',
          source_system: 'aws',
          resource_id: 'policy-1',
          resource_name: 'AdminPolicy',
          compliance_controls: ['CC6.1', 'CC6.2'],
          quality_score: 90,
          collected_at: '2025-06-15',
          data_summary: {},
        },
        {
          evidence_id: 'ev-2',
          evidence_type: 'iam_users',
          source_system: 'aws',
          resource_id: 'user-1',
          resource_name: 'admin',
          compliance_controls: ['CC6.1', 'CC6.7'],
          quality_score: 80,
          collected_at: '2025-06-15',
          data_summary: {},
        },
        {
          evidence_id: 'ev-3',
          evidence_type: 'users',
          source_system: 'okta',
          resource_id: 'okta-user-1',
          resource_name: 'john',
          compliance_controls: ['CC6.1', 'CC6.2', 'CC6.7'],
          quality_score: 85,
          collected_at: '2025-06-15',
          data_summary: {},
        },
      ];

      const summary = foundationEvidenceService.generateCollectionSummary(results);

      expect(summary.total_evidence).toBe(3);
      expect(summary.by_type['iam_policies']).toBe(1);
      expect(summary.by_type['iam_users']).toBe(1);
      expect(summary.by_type['users']).toBe(1);
      expect(summary.by_system['aws']).toBe(2);
      expect(summary.by_system['okta']).toBe(1);
      expect(summary.by_controls['CC6.1']).toBe(3);
      expect(summary.by_controls['CC6.7']).toBe(2);
      expect(summary.average_quality).toBeCloseTo(85, 0);
      expect(summary.coverage_by_framework['SOC2_TYPE2']).toBeGreaterThan(0);
    });

    it('handles empty results', () => {
      const summary = foundationEvidenceService.generateCollectionSummary([]);
      expect(summary.total_evidence).toBe(0);
      expect(summary.average_quality).toBe(0);
    });
  });
});
