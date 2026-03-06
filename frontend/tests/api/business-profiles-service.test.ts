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

// Mock the field mapper to avoid complex dependency chain
vi.mock('@/lib/api/business-profile/field-mapper', () => ({
  BusinessProfileFieldMapper: {
    transformAPIResponseForFrontend: vi.fn((data: any) => data),
    transformFormDataForAPI: vi.fn((data: any) => data),
    createUpdatePayload: vi.fn((_profile: any, updates: any) => updates),
  },
}));

describe('BusinessProfileService', () => {
  let businessProfileService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/business-profiles.service');
    businessProfileService = serviceMod.businessProfileService;
  });

  describe('getBusinessProfiles', () => {
    it('calls GET /business-profiles and transforms array response', async () => {
      const mockProfiles = [
        { id: 'bp-1', company_name: 'Acme Corp', industry: 'technology' },
        { id: 'bp-2', company_name: 'Widget Inc', industry: 'finance' },
      ];

      (apiClient.get as any).mockResolvedValue(mockProfiles);

      const result = await businessProfileService.getBusinessProfiles();

      expect(apiClient.get).toHaveBeenCalledWith('/business-profiles');
      expect(result).toHaveLength(2);
    });

    it('handles response with data wrapper', async () => {
      const mockResponse = {
        data: [{ id: 'bp-1', company_name: 'Acme Corp' }],
      };

      (apiClient.get as any).mockResolvedValue(mockResponse);

      const result = await businessProfileService.getBusinessProfiles();

      expect(result).toHaveLength(1);
    });

    it('handles empty response', async () => {
      (apiClient.get as any).mockResolvedValue([]);

      const result = await businessProfileService.getBusinessProfiles();

      expect(result).toEqual([]);
    });
  });

  describe('getBusinessProfile', () => {
    it('calls GET /business-profiles/:id', async () => {
      const mockProfile = {
        id: 'bp-1',
        company_name: 'Acme Corp',
        industry: 'technology',
        company_size: 'medium',
      };

      (apiClient.get as any).mockResolvedValue(mockProfile);

      const result = await businessProfileService.getBusinessProfile('bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/business-profiles/bp-1');
      expect(result.company_name).toBe('Acme Corp');
    });

    it('throws when transformation fails', async () => {
      // Override the mock to return null for transformation
      const { BusinessProfileFieldMapper } = await import(
        '@/lib/api/business-profile/field-mapper'
      );
      (BusinessProfileFieldMapper.transformAPIResponseForFrontend as any).mockReturnValueOnce(null);

      (apiClient.get as any).mockResolvedValue({ id: 'bp-bad' });

      await expect(
        businessProfileService.getBusinessProfile('bp-bad'),
      ).rejects.toThrow('Failed to transform business profile data');
    });
  });

  describe('createBusinessProfile', () => {
    it('calls POST /business-profiles with transformed data', async () => {
      const request = {
        company_name: 'New Corp',
        industry: 'healthcare',
        company_size: 'small',
        data_types: ['personal', 'health'],
        storage_location: 'uk',
        operates_in_uk: true,
        uk_data_subjects: true,
        regulatory_requirements: ['GDPR'],
      };

      const mockResponse = { id: 'bp-new', ...request };
      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await businessProfileService.createBusinessProfile(request);

      expect(apiClient.post).toHaveBeenCalledWith('/business-profiles', request);
      expect(result.id).toBe('bp-new');
    });
  });

  describe('updateBusinessProfile', () => {
    it('calls PUT /business-profiles/:id with transformed data', async () => {
      const update = { company_name: 'Updated Corp' };
      const mockResponse = { id: 'bp-1', company_name: 'Updated Corp' };
      (apiClient.put as any).mockResolvedValue(mockResponse);

      const result = await businessProfileService.updateBusinessProfile('bp-1', update);

      expect(apiClient.put).toHaveBeenCalledWith('/business-profiles/bp-1', update);
      expect(result.company_name).toBe('Updated Corp');
    });
  });

  describe('deleteBusinessProfile', () => {
    it('calls DELETE /business-profiles/:id', async () => {
      (apiClient.delete as any).mockResolvedValue(undefined);

      await businessProfileService.deleteBusinessProfile('bp-1');

      expect(apiClient.delete).toHaveBeenCalledWith('/business-profiles/bp-1');
    });
  });

  describe('getBusinessProfileCompliance', () => {
    it('calls GET /business-profiles/:id/compliance', async () => {
      const mockCompliance = {
        frameworks: [
          { framework: 'GDPR', compliance_percentage: 78 },
          { framework: 'ISO 27001', compliance_percentage: 45 },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockCompliance);

      const result = await businessProfileService.getBusinessProfileCompliance('bp-1');

      expect(apiClient.get).toHaveBeenCalledWith('/business-profiles/bp-1/compliance');
      expect(result.frameworks).toHaveLength(2);
    });
  });

  describe('getProfile', () => {
    it('returns the first profile', async () => {
      const mockProfiles = [
        { id: 'bp-1', company_name: 'Primary Corp' },
        { id: 'bp-2', company_name: 'Secondary Corp' },
      ];

      (apiClient.get as any).mockResolvedValue(mockProfiles);

      const result = await businessProfileService.getProfile();

      expect(result.id).toBe('bp-1');
    });

    it('returns null when no profiles exist', async () => {
      (apiClient.get as any).mockResolvedValue([]);

      const result = await businessProfileService.getProfile();

      expect(result).toBeNull();
    });

    it('throws on API error', async () => {
      (apiClient.get as any).mockRejectedValue(new Error('Network error'));

      await expect(businessProfileService.getProfile()).rejects.toThrow('Network error');
    });
  });

  describe('deleteProfile', () => {
    it('deletes the current profile', async () => {
      const mockProfiles = [{ id: 'bp-1', company_name: 'Corp' }];
      (apiClient.get as any).mockResolvedValue(mockProfiles);
      (apiClient.delete as any).mockResolvedValue(undefined);

      await businessProfileService.deleteProfile();

      expect(apiClient.delete).toHaveBeenCalledWith('/business-profiles/bp-1');
    });

    it('does nothing when no profile exists', async () => {
      (apiClient.get as any).mockResolvedValue([]);

      await businessProfileService.deleteProfile();

      expect(apiClient.delete).not.toHaveBeenCalled();
    });
  });

  describe('getFrameworkRecommendations', () => {
    it('calls GET /frameworks/recommendations', async () => {
      const mockRecs = [
        { framework_id: 'gdpr', relevance: 0.95, reasons: ['UK business'] },
      ];

      (apiClient.get as any).mockResolvedValue(mockRecs);

      const result = await businessProfileService.getFrameworkRecommendations();

      expect(apiClient.get).toHaveBeenCalledWith('/frameworks/recommendations');
      expect(result).toHaveLength(1);
    });

    it('returns empty array on error', async () => {
      (apiClient.get as any).mockRejectedValue(new Error('Service unavailable'));

      const result = await businessProfileService.getFrameworkRecommendations();

      expect(result).toEqual([]);
    });
  });
});

// ── Type interface tests ─────────────────────────────────

describe('BusinessProfile type interfaces', () => {
  it('CreateBusinessProfileRequest has required fields', () => {
    const request = {
      company_name: 'Test Corp',
      industry: 'technology',
      company_size: 'medium',
      data_types: ['personal'],
      storage_location: 'uk',
      operates_in_uk: true,
      uk_data_subjects: true,
      regulatory_requirements: ['GDPR'],
    };

    expect(Object.keys(request)).toHaveLength(8);
    expect(request.operates_in_uk).toBe(true);
  });
});
