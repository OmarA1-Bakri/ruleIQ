import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

// ---------------------------------------------------------------------------
// Auth store mock — must happen before any service import
// The auth store is the dependency that authService delegates to.
// assessmentService / evidenceService / businessProfileService all use apiClient
// which in turn needs auth store state for the Bearer token.
// ---------------------------------------------------------------------------
const mockUser = {
  id: 'user-123',
  email: 'test@example.com',
  is_active: true,
  permissions: ['read', 'write'],
  role: 'user',
};

const mockTokens = {
  access_token: 'mock-access-token',
  refresh_token: 'mock-refresh-token',
  token_type: 'bearer',
};

vi.mock('@/lib/stores/auth.store', () => ({
  useAuthStore: {
    getState: vi.fn(() => ({
      user: mockUser,
      tokens: { access: 'mock-access-token', refresh: 'mock-refresh-token' },
      isAuthenticated: true,
      isLoading: false,
      error: null,
      login: vi.fn().mockResolvedValue(undefined),
      register: vi.fn().mockResolvedValue(undefined),
      logout: vi.fn().mockResolvedValue(undefined),
      getCurrentUser: vi.fn().mockReturnValue(mockUser),
      refreshTokens: vi.fn().mockResolvedValue(undefined),
      getToken: vi.fn().mockReturnValue('mock-access-token'),
      checkAuthStatus: vi.fn().mockResolvedValue(undefined),
      initialize: vi.fn().mockResolvedValue(undefined),
    })),
    setState: vi.fn(),
    subscribe: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// MSW server — intercepts fetch calls made by the real API client
// The real apiClient prepends /api/v1 to every endpoint, so handlers must
// match http://localhost:8000/api/v1/...
// ---------------------------------------------------------------------------
const BASE = 'http://localhost:8000/api/v1';

const handlers = [
  // Auth
  http.post(`${BASE}/auth/login`, () =>
    HttpResponse.json({
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token',
      token_type: 'bearer',
    }),
  ),
  http.get(`${BASE}/auth/me`, () => HttpResponse.json(mockUser)),
  http.post(`${BASE}/auth/register`, () =>
    HttpResponse.json(
      {
        user: { id: 'user-new', email: 'newuser@example.com' },
        tokens: { access_token: 'new-access-token', refresh_token: 'new-refresh-token' },
      },
      { status: 201 },
    ),
  ),
  http.post(`${BASE}/auth/logout`, () => HttpResponse.json({ message: 'Logged out successfully' })),

  // Assessments
  http.get(`${BASE}/assessments`, ({ request }) => {
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1');
    const pageSize = parseInt(url.searchParams.get('page_size') || '20');
    return HttpResponse.json({
      items: [
        { id: 'assess-1', name: 'Test Assessment 1', status: 'completed' },
        { id: 'assess-2', name: 'Test Assessment 2', status: 'in_progress' },
      ],
      total: 2,
      page,
      size: pageSize,
    });
  }),
  http.post(`${BASE}/assessments`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      { id: 'assess-new', ...body, status: 'draft', created_at: new Date().toISOString() },
      { status: 201 },
    );
  }),
  http.get(`${BASE}/assessments/:id`, ({ params }) =>
    HttpResponse.json({
      id: params['id'],
      name: 'Test Assessment',
      status: 'completed',
      framework_id: 'gdpr',
      responses: { q1: 'yes', q2: 'no' },
      score: 85,
    }),
  ),
  http.patch(`${BASE}/assessments/:id`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: params['id'], ...body, updated_at: new Date().toISOString() });
  }),
  http.put(`${BASE}/assessments/:id`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: params['id'], ...body, updated_at: new Date().toISOString() });
  }),
  http.post(`${BASE}/assessments/:id/complete`, ({ params }) =>
    HttpResponse.json({ id: params['id'], status: 'completed', completed_at: new Date().toISOString() }),
  ),

  // Evidence
  http.get(`${BASE}/evidence`, () =>
    HttpResponse.json({
      items: [
        { id: 'ev-1', title: 'Evidence 1', framework_id: 'gdpr', status: 'collected', evidence_type: 'document' },
        { id: 'ev-2', title: 'Evidence 2', framework_id: 'iso27001', status: 'pending', evidence_type: 'document' },
      ],
      total: 2,
    }),
  ),
  http.post(`${BASE}/evidence`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      { id: 'ev-new', ...body, status: 'pending', created_at: new Date().toISOString() },
      { status: 201 },
    );
  }),
  http.post(`${BASE}/evidence/upload`, () =>
    HttpResponse.json(
      { id: 'ev-new', title: 'Uploaded Evidence', status: 'uploaded', uploaded_at: new Date().toISOString() },
      { status: 201 },
    ),
  ),
  http.patch(`${BASE}/evidence/:id`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: params['id'], ...body, updated_at: new Date().toISOString() });
  }),
  http.put(`${BASE}/evidence/:id`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: params['id'], ...body, updated_at: new Date().toISOString() });
  }),
  http.delete(`${BASE}/evidence/:id`, () => new HttpResponse(null, { status: 204 })),

  // Business profiles
  http.get(`${BASE}/business-profiles`, () =>
    HttpResponse.json([
      {
        id: 'profile-123',
        company_name: 'Test Company',
        industry: 'Technology',
        employee_count: 50,
        country: 'United Kingdom',
        data_sensitivity: 'Medium',
        handles_persona: true,
        required_frameworks: ['gdpr'],
      },
    ]),
  ),
  http.get(`${BASE}/business-profiles/me`, () =>
    HttpResponse.json({
      id: 'profile-123',
      company_name: 'Test Company',
      industry: 'Technology',
      employee_count: 50,
      country: 'United Kingdom',
      data_sensitivity: 'Medium',
      handles_persona: true,
      required_frameworks: ['gdpr'],
    }),
  ),
  http.post(`${BASE}/business-profiles`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      { id: 'profile-new', ...body, created_at: new Date().toISOString() },
      { status: 201 },
    );
  }),
  http.put(`${BASE}/business-profiles/:id`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: params['id'], ...body, updated_at: new Date().toISOString() });
  }),
];

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ---------------------------------------------------------------------------
// Imports — after mocks and server setup
// ---------------------------------------------------------------------------
import { authService } from '@/lib/api/auth.service';
import { assessmentService } from '@/lib/api/assessments.service';
import { evidenceService } from '@/lib/api/evidence.service';
import { businessProfileService } from '@/lib/api/business-profiles.service';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('API Services with MSW', () => {
  describe('AuthService', () => {
    it('should handle successful login', async () => {
      // authService.login delegates to useAuthStore.getState().login which is mocked
      // The mock login resolves to undefined (void) and sets store state.
      // We verify it doesn't throw and returns void.
      await expect(
        authService.login({ email: 'test@example.com', password: 'password123', rememberMe: false }),
      ).resolves.toBeUndefined();
    });

    it('should handle login failure', async () => {
      // Override the login mock to reject
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const loginMock = vi.fn().mockRejectedValueOnce(new Error('Invalid credentials'));
      (useAuthStore.getState as ReturnType<typeof vi.fn>).mockReturnValueOnce({
        ...useAuthStore.getState(),
        login: loginMock,
      });

      await expect(
        authService.login({
          email: 'test@example.com',
          password: 'wrong-password',
          rememberMe: false,
        }),
      ).rejects.toThrow('Invalid credentials');
    });

    it('should handle registration', async () => {
      // authService.register delegates to useAuthStore.getState().register — mocked to resolve
      await expect(
        authService.register('test@example.com', 'password123', 'Test User'),
      ).resolves.toBeUndefined();
    });

    it('should get current user', async () => {
      // authService.getCurrentUser returns store state user synchronously
      const result = authService.getCurrentUser();

      expect(result).not.toBeNull();
      expect(result!.id).toBe('user-123');
      expect(result!.email).toBe('test@example.com');
    });
  });

  describe('AssessmentService', () => {
    it('should get assessments with pagination', async () => {
      const result = await assessmentService.getAssessments({ page: 1, page_size: 20 });

      expect(result.items).toHaveLength(2);
      expect(result.total).toBe(2);
    });

    it('should create new assessment', async () => {
      const assessmentData = {
        name: 'New Assessment',
        framework_id: 'gdpr',
        business_profile_id: 'profile-123',
      };

      const result = await assessmentService.createAssessment(assessmentData);

      expect(result.name).toBe('New Assessment');
      expect(result.framework_id).toBe('gdpr');
      expect(result.status).toBe('draft');
    });

    it('should get single assessment', async () => {
      const result = await assessmentService.getAssessment('assess-123');

      // MSW returns the :id param as the id — matches what was requested
      expect(result.id).toBe('assess-123');
      expect(result.name).toBe('Test Assessment');
      expect(result.status).toBe('completed');
    });

    it('should update assessment', async () => {
      const updateData = { status: 'completed', responses: { q1: 'yes', q2: 'no' } };

      const result = await assessmentService.updateAssessment('assess-123', updateData);

      expect(result.id).toBe('assess-123');
      expect(result.status).toBe('completed');
    });

    it('should complete assessment', async () => {
      const result = await assessmentService.completeAssessment('assess-123');

      expect(result.id).toBe('assess-123');
      expect(result.status).toBe('completed');
    });
  });

  describe('EvidenceService', () => {
    it('should get evidence with filters', async () => {
      const result = await evidenceService.getEvidence({
        framework_id: 'gdpr',
        status: 'collected',
        page: 1,
        page_size: 10,
      });

      expect(result.items).toHaveLength(2);
      expect(result.total).toBe(2);
    });

    it('should create evidence', async () => {
      const evidenceData = {
        framework_id: 'gdpr',
        control_id: 'A.1.1',
        evidence_type: 'document',
        title: 'Test Evidence',
        description: 'Test evidence document',
      };

      const result = await evidenceService.createEvidence(evidenceData);
      expect(result.title).toBe('Test Evidence');
    });

    it('should update evidence', async () => {
      const updateData = { status: 'approved' as const, notes: 'Evidence approved by reviewer' };

      const result = await evidenceService.updateEvidence('ev-123', updateData);

      expect(result.id).toBe('ev-123');
      expect(result.status).toBe('approved');
    });

    it('should delete evidence', async () => {
      // Should not throw
      await evidenceService.deleteEvidence('ev-123');
      expect(true).toBe(true);
    });
  });

  describe('BusinessProfileService', () => {
    it('should get business profile', async () => {
      // getProfile() calls getBusinessProfiles() which hits GET /business-profiles
      // MSW returns an array with one profile; field mapper transforms it
      const result = await businessProfileService.getProfile();

      expect(result).not.toBeNull();
      expect(result!.id).toBe('profile-123');
      expect(result!.company_name).toBe('Test Company');
    });

    it('should create business profile', async () => {
      const profileData = {
        company_name: 'New Company',
        industry: 'Healthcare',
        company_size: 'small',
        data_types: ['personal'],
        storage_location: 'UK',
        operates_in_uk: true,
        uk_data_subjects: true,
        regulatory_requirements: ['gdpr'],
      };

      const result = await businessProfileService.createBusinessProfile(profileData);

      // The field mapper passes company_name through unchanged
      expect(result.company_name).toBe('New Company');
      expect(result.industry).toBe('Healthcare');
    });

    it('should update business profile', async () => {
      // First, get the profile to have a valid object to pass to updateProfile
      const existingProfile = await businessProfileService.getProfile();
      expect(existingProfile).toBeTruthy();

      if (existingProfile) {
        const result = await businessProfileService.updateProfile(existingProfile, {
          industry: 'Healthcare',
        });
        expect(result.id).toBe('profile-123');
      }
    });
  });

  describe('Error Handling', () => {
    it('should handle HTTP 401 errors', async () => {
      // Override the auth/me handler to return 401
      server.use(
        http.get(`${BASE}/auth/me`, () =>
          HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 }),
        ),
      );

      // authService.getCurrentUser returns from store state (synchronous), so
      // instead test via a service that makes a real fetch call — assessmentService
      server.use(
        http.get(`${BASE}/assessments`, () =>
          HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 }),
        ),
      );

      await expect(assessmentService.getAssessments()).rejects.toThrow();
    });

    it('should handle HTTP 404 errors', async () => {
      server.use(
        http.get(`${BASE}/assessments/:id`, () =>
          HttpResponse.json({ detail: 'Resource not found' }, { status: 404 }),
        ),
      );

      await expect(assessmentService.getAssessment('non-existent')).rejects.toThrow();
    });

    it('should handle validation errors (422)', async () => {
      server.use(
        http.post(`${BASE}/assessments`, () =>
          HttpResponse.json(
            { detail: [{ field: 'framework_id', message: 'Required' }] },
            { status: 422 },
          ),
        ),
      );

      await expect(
        assessmentService.createAssessment({ business_profile_id: '', framework_id: '' }),
      ).rejects.toThrow();
    });

    it('should handle rate limiting (429)', async () => {
      server.use(
        http.get(`${BASE}/assessments`, () =>
          HttpResponse.json({ detail: 'Rate limit exceeded' }, { status: 429 }),
        ),
      );

      await expect(assessmentService.getAssessments()).rejects.toThrow();
    });

    it('should handle network errors', async () => {
      server.use(
        http.get(`${BASE}/assessments`, () => HttpResponse.error()),
      );

      await expect(assessmentService.getAssessments()).rejects.toThrow();
    });
  });
});
