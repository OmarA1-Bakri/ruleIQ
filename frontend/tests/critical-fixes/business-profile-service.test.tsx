import { describe, it, expect, beforeEach, vi } from 'vitest';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';

// Mock the auth store before importing the service
vi.mock('@/lib/stores/auth.store', () => ({
  useAuthStore: {
    getState: vi.fn(() => ({
      user: {
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User',
        is_active: true,
      },
      tokens: {
        access: 'mock-access-token',
        refresh: 'mock-refresh-token',
      },
      getToken: () => 'mock-access-token',
      isAuthenticated: true,
      isLoading: false,
      error: null,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshToken: vi.fn(),
      refreshTokens: vi.fn(),
      checkAuth: vi.fn(),
    })),
    setState: vi.fn(),
    subscribe: vi.fn(),
  },
}));

// Import the service after mocking the auth store
import { businessProfileService } from '@/lib/api/business-profiles.service';

describe('BusinessProfileService Integration Tests', () => {
  beforeEach(() => {
    // Reset handlers
    server.resetHandlers();
  });

  describe('getBusinessProfiles', () => {
    it('should successfully fetch business profiles', async () => {
      // Add specific handler for this test
      server.use(
        http.get('http://localhost:8000/api/v1/business-profiles', () => {
          return HttpResponse.json([
            {
              id: 'profile-123',
              company_name: 'Test Company',
              industry: 'Technology',
              employee_count: 50,
              data_types: ['personal'],
              storage_location: 'UK',
              operates_in_uk: true,
              uk_data_subjects: true,
              regulatory_requirements: ['GDPR'],
            },
          ]);
        }),
      );

      const profiles = await businessProfileService.getBusinessProfiles();

      expect(profiles).toHaveLength(1);
      // Verify core fields are correctly transformed
      expect(profiles[0]).toEqual(
        expect.objectContaining({
          id: 'profile-123',
          company_name: 'Test Company',
          industry: 'Technology',
          employee_count: 50,
          data_types: ['personal'],
          storage_location: 'UK',
          operates_in_uk: true,
          uk_data_subjects: true,
          regulatory_requirements: ['GDPR'],
        }),
      );

      // Verify that field mapper added default arrays
      expect(Array.isArray(profiles[0].cloud_providers)).toBe(true);
      expect(Array.isArray(profiles[0].saas_tools)).toBe(true);
      expect(Array.isArray(profiles[0].development_tools)).toBe(true);
      expect(Array.isArray(profiles[0].existing_frameworks)).toBe(true);
      expect(Array.isArray(profiles[0].planned_frameworks)).toBe(true);
    });

    it('should handle empty business profiles list', async () => {
      server.use(
        http.get('http://localhost:8000/api/v1/business-profiles', () => {
          return HttpResponse.json([]);
        }),
      );

      const profiles = await businessProfileService.getBusinessProfiles();

      expect(profiles).toHaveLength(0);
      expect(Array.isArray(profiles)).toBe(true);
    });

    it('should handle API wrapped response format', async () => {
      server.use(
        http.get('http://localhost:8000/api/v1/business-profiles', () => {
          return HttpResponse.json({
            data: [
              {
                id: 'profile-456',
                company_name: 'Wrapped Company',
                industry: 'Finance',
                employee_count: 100,
              },
            ],
          });
        }),
      );

      const profiles = await businessProfileService.getBusinessProfiles();

      expect(profiles).toHaveLength(1);
      expect(profiles[0].company_name).toBe('Wrapped Company');
    });
  });

  describe('getBusinessProfile', () => {
    it('should fetch a specific business profile by ID', async () => {
      const profileId = 'profile-123';

      server.use(
        http.get(`http://localhost:8000/api/v1/business-profiles/${profileId}`, () => {
          return HttpResponse.json({
            id: profileId,
            company_name: 'Specific Company',
            industry: 'Healthcare',
            employee_count: 25,
          });
        }),
      );

      const profile = await businessProfileService.getBusinessProfile(profileId);

      expect(profile.id).toBe(profileId);
      expect(profile.company_name).toBe('Specific Company');
      expect(profile.industry).toBe('Healthcare');
      expect(profile.employee_count).toBe(25);
    });
  });

  describe('createBusinessProfile', () => {
    it('should create a new business profile', async () => {
      const newProfileData = {
        company_name: 'New Company',
        industry: 'Technology',
        employee_count: 75,
        data_types: ['personal', 'financial'],
        storage_location: 'UK',
        operates_in_uk: true,
        uk_data_subjects: true,
        regulatory_requirements: ['GDPR', 'DPA'],
      };

      server.use(
        http.post('http://localhost:8000/api/v1/business-profiles', async ({ request }) => {
          const body = await request.json();

          return HttpResponse.json(
            {
              id: 'profile-new',
              company_name: body.company_name,
              industry: body.industry,
              employee_count: body.employee_count,
              data_types: body.data_types,
              storage_location: body.storage_location,
              operates_in_uk: body.operates_in_uk,
              uk_data_subjects: body.uk_data_subjects,
              regulatory_requirements: body.regulatory_requirements,
              created_at: new Date().toISOString(),
            },
            { status: 201 },
          );
        }),
      );

      const createdProfile = await businessProfileService.createBusinessProfile(newProfileData);

      expect(createdProfile.id).toBe('profile-new');
      expect(createdProfile.company_name).toBe('New Company');
      expect(createdProfile.industry).toBe('Technology');
    });
  });

  describe('updateBusinessProfile', () => {
    it('should update an existing business profile', async () => {
      const profileId = 'profile-123';
      const updateData = {
        company_name: 'Updated Company',
        industry: 'Updated Industry',
        employee_count: 150,
      };

      server.use(
        http.put(
          `http://localhost:8000/api/v1/business-profiles/${profileId}`,
          async ({ request }) => {
            const body = await request.json();

            return HttpResponse.json({
              id: profileId,
              company_name: body.company_name,
              industry: body.industry,
              employee_count: body.employee_count,
              updated_at: new Date().toISOString(),
            });
          },
        ),
      );

      const updatedProfile = await businessProfileService.updateBusinessProfile(
        profileId,
        updateData,
      );

      expect(updatedProfile.id).toBe(profileId);
      expect(updatedProfile.company_name).toBe('Updated Company');
      expect(updatedProfile.industry).toBe('Updated Industry');
      expect(updatedProfile.employee_count).toBe(150);
    });
  });

  describe('error handling', () => {
    it('should handle API authentication errors', async () => {
      server.use(
        http.get('http://localhost:8000/api/v1/business-profiles', () => {
          return HttpResponse.json({ detail: 'Authentication required' }, { status: 401 });
        }),
      );

      await expect(businessProfileService.getBusinessProfiles()).rejects.toThrow();
    });

    it('should handle API server errors', async () => {
      server.use(
        http.get('http://localhost:8000/api/v1/business-profiles', () => {
          return HttpResponse.json({ detail: 'Internal server error' }, { status: 500 });
        }),
      );

      await expect(businessProfileService.getBusinessProfiles()).rejects.toThrow();
    });

    it('should handle network errors', async () => {
      server.use(
        http.get('http://localhost:8000/api/v1/business-profiles', () => {
          return HttpResponse.error();
        }),
      );

      await expect(businessProfileService.getBusinessProfiles()).rejects.toThrow();
    });
  });
});
