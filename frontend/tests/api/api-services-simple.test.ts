import { describe, it, expect, vi, beforeEach } from 'vitest';

// ---------------------------------------------------------------------------
// Mock the API client completely — services call apiClient.get/post/patch/etc.
// ---------------------------------------------------------------------------
const mockApiClient = {
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  patch: vi.fn(),
  upload: vi.fn(),
  publicGet: vi.fn(),
  publicPost: vi.fn(),
};

vi.mock('@/lib/api/client', () => ({
  apiClient: mockApiClient,
}));

// ---------------------------------------------------------------------------
// Mock the auth store — authService delegates every method to it
// ---------------------------------------------------------------------------
const mockUser = {
  id: 'user-123',
  email: 'test@example.com',
  is_active: true,
  name: 'Test User',
};

const mockLoginFn = vi.fn();
const mockRegisterFn = vi.fn();
const mockLogoutFn = vi.fn();
const mockGetCurrentUserFn = vi.fn();
const mockGetTokenFn = vi.fn();
const mockRefreshTokensFn = vi.fn();
const mockCheckAuthStatusFn = vi.fn();
const mockInitializeFn = vi.fn();

vi.mock('@/lib/stores/auth.store', () => ({
  useAuthStore: {
    getState: vi.fn(() => ({
      user: mockUser,
      tokens: { access: 'mock-access-token', refresh: 'mock-refresh-token' },
      isAuthenticated: true,
      isLoading: false,
      error: null,
      login: mockLoginFn,
      register: mockRegisterFn,
      logout: mockLogoutFn,
      getCurrentUser: mockGetCurrentUserFn,
      getToken: mockGetTokenFn,
      refreshTokens: mockRefreshTokensFn,
      checkAuthStatus: mockCheckAuthStatusFn,
      initialize: mockInitializeFn,
    })),
    setState: vi.fn(),
    subscribe: vi.fn(),
  },
}));

describe('API Services - Simple Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default implementations after clear
    mockLoginFn.mockResolvedValue(undefined);
    mockRegisterFn.mockResolvedValue(undefined);
    mockLogoutFn.mockResolvedValue(undefined);
    mockGetCurrentUserFn.mockReturnValue(mockUser);
    mockGetTokenFn.mockReturnValue('mock-access-token');
    mockRefreshTokensFn.mockResolvedValue(undefined);
    mockCheckAuthStatusFn.mockResolvedValue(undefined);
    mockInitializeFn.mockResolvedValue(undefined);
  });

  // -------------------------------------------------------------------------
  // AuthService — wraps useAuthStore.getState() calls
  // -------------------------------------------------------------------------
  describe('AuthService', () => {
    it('should handle successful login', async () => {
      mockLoginFn.mockResolvedValue(undefined);

      const { authService } = await import('@/lib/api/auth.service');
      await expect(
        authService.login({ email: 'test@example.com', password: 'password123', rememberMe: false }),
      ).resolves.toBeUndefined();

      expect(mockLoginFn).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
        rememberMe: false,
      });
    });

    it('should handle login failure', async () => {
      mockLoginFn.mockRejectedValueOnce(new Error('Invalid credentials'));

      const { authService } = await import('@/lib/api/auth.service');
      await expect(
        authService.login({ email: 'test@example.com', password: 'wrong-password', rememberMe: false }),
      ).rejects.toThrow('Invalid credentials');
    });

    it('should return current user from store', async () => {
      mockGetCurrentUserFn.mockReturnValue(mockUser);

      const { authService } = await import('@/lib/api/auth.service');
      const result = authService.getCurrentUser();

      expect(result).toEqual(mockUser);
      expect(result!.id).toBe('user-123');
      expect(result!.email).toBe('test@example.com');
    });
  });

  // -------------------------------------------------------------------------
  // AssessmentService — calls apiClient directly
  // -------------------------------------------------------------------------
  describe('AssessmentService', () => {
    it('should get assessments', async () => {
      const mockAssessments = {
        items: [
          { id: 'assess-1', name: 'Test Assessment 1' },
          { id: 'assess-2', name: 'Test Assessment 2' },
        ],
        total: 2,
        page: 1,
        size: 20,
      };

      // assessmentService.getAssessments calls apiClient.get and returns the response directly
      mockApiClient.get.mockResolvedValueOnce(mockAssessments);

      const { assessmentService } = await import('@/lib/api/assessments.service');
      const result = await assessmentService.getAssessments({ page: 1, page_size: 20 });

      expect(result).toEqual(mockAssessments);
      expect(result.items).toHaveLength(2);
      expect(result.total).toBe(2);
      expect(mockApiClient.get).toHaveBeenCalledWith('/assessments', {
        params: { page: 1, page_size: 20 },
      });
    });

    it('should create assessment', async () => {
      const assessmentData = {
        name: 'New Assessment',
        framework_id: 'gdpr',
        business_profile_id: 'profile-123',
      };

      const mockResponse = { id: 'assess-new', ...assessmentData, status: 'draft' };

      // assessmentService.createAssessment returns apiClient.post response directly
      mockApiClient.post.mockResolvedValueOnce(mockResponse);

      const { assessmentService } = await import('@/lib/api/assessments.service');
      const result = await assessmentService.createAssessment(assessmentData);

      expect(result.id).toBe('assess-new');
      expect(result.name).toBe('New Assessment');
      expect(result.status).toBe('draft');
      expect(mockApiClient.post).toHaveBeenCalledWith('/assessments', assessmentData);
    });

    it('should get single assessment', async () => {
      const mockAssessment = { id: 'assess-123', name: 'Test Assessment', status: 'completed' };
      mockApiClient.get.mockResolvedValueOnce(mockAssessment);

      const { assessmentService } = await import('@/lib/api/assessments.service');
      const result = await assessmentService.getAssessment('assess-123');

      expect(result.id).toBe('assess-123');
      expect(result.name).toBe('Test Assessment');
    });

    it('should update assessment', async () => {
      const mockUpdated = { id: 'assess-123', status: 'completed' };
      mockApiClient.patch.mockResolvedValueOnce(mockUpdated);

      const { assessmentService } = await import('@/lib/api/assessments.service');
      const result = await assessmentService.updateAssessment('assess-123', { status: 'completed' });

      expect(result.id).toBe('assess-123');
      expect(result.status).toBe('completed');
    });

    it('should complete assessment', async () => {
      const mockCompleted = { id: 'assess-123', status: 'completed' };
      mockApiClient.post.mockResolvedValueOnce(mockCompleted);

      const { assessmentService } = await import('@/lib/api/assessments.service');
      const result = await assessmentService.completeAssessment('assess-123');

      expect(result.id).toBe('assess-123');
      expect(result.status).toBe('completed');
    });
  });

  // -------------------------------------------------------------------------
  // EvidenceService — calls apiClient directly
  // -------------------------------------------------------------------------
  describe('EvidenceService', () => {
    it('should get evidence', async () => {
      const mockEvidence = {
        items: [
          { id: 'ev-1', title: 'Evidence 1' },
          { id: 'ev-2', title: 'Evidence 2' },
        ],
        total: 2,
      };

      mockApiClient.get.mockResolvedValueOnce(mockEvidence);

      const { evidenceService } = await import('@/lib/api/evidence.service');
      const result = await evidenceService.getEvidence({ framework_id: 'gdpr', status: 'collected' });

      expect(result).toEqual(mockEvidence);
      expect(result.items).toHaveLength(2);
      expect(mockApiClient.get).toHaveBeenCalledWith('/evidence', {
        params: { framework_id: 'gdpr', status: 'collected' },
      });
    });

    it('should create evidence', async () => {
      const evidenceData = {
        framework_id: 'gdpr',
        control_id: 'A.1.1',
        evidence_type: 'document',
        title: 'Test Evidence',
        description: 'Test evidence document',
      };

      const mockResponse = { id: 'ev-new', ...evidenceData, status: 'pending' };
      mockApiClient.post.mockResolvedValueOnce(mockResponse);

      const { evidenceService } = await import('@/lib/api/evidence.service');
      const result = await evidenceService.createEvidence(evidenceData);

      expect(result.title).toBe('Test Evidence');
      expect(result.id).toBe('ev-new');
      expect(mockApiClient.post).toHaveBeenCalledWith('/evidence', evidenceData);
    });

    it('should upload evidence file via uploadEvidence', async () => {
      const file = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      const mockResponse = { id: 'ev-new', status: 'uploaded' };

      // uploadEvidence uses apiClient.post with a FormData body
      mockApiClient.post.mockResolvedValueOnce(mockResponse);

      const { evidenceService } = await import('@/lib/api/evidence.service');
      const result = await evidenceService.uploadEvidence(file);

      expect(result.status).toBe('uploaded');
      expect(mockApiClient.post).toHaveBeenCalledWith(
        '/evidence/upload',
        expect.any(FormData),
      );
    });

    it('should update evidence', async () => {
      const mockUpdated = { id: 'ev-123', status: 'approved' };
      mockApiClient.patch.mockResolvedValueOnce(mockUpdated);

      const { evidenceService } = await import('@/lib/api/evidence.service');
      const result = await evidenceService.updateEvidence('ev-123', { status: 'approved' });

      expect(result.id).toBe('ev-123');
      expect(result.status).toBe('approved');
      expect(mockApiClient.patch).toHaveBeenCalledWith('/evidence/ev-123', { status: 'approved' });
    });

    it('should delete evidence', async () => {
      mockApiClient.delete.mockResolvedValueOnce(undefined);

      const { evidenceService } = await import('@/lib/api/evidence.service');
      await evidenceService.deleteEvidence('ev-123');

      expect(mockApiClient.delete).toHaveBeenCalledWith('/evidence/ev-123');
    });
  });

  // -------------------------------------------------------------------------
  // BusinessProfileService — calls apiClient; responses go through field mapper
  // -------------------------------------------------------------------------
  describe('BusinessProfileService', () => {
    it('should get business profile list', async () => {
      // getBusinessProfiles() returns apiClient.get response.
      // The service does: Array.isArray(response) ? response : response.data || []
      // Then transforms each through BusinessProfileFieldMapper.transformAPIResponseForFrontend
      const apiProfiles = [
        {
          id: 'profile-123',
          company_name: 'Test Company',
          industry: 'Technology',
          employee_count: 50,
          country: 'United Kingdom',
          data_sensitivity: 'Medium',
        },
      ];
      mockApiClient.get.mockResolvedValueOnce(apiProfiles);

      const { businessProfileService } = await import('@/lib/api/business-profiles.service');
      const result = await businessProfileService.getBusinessProfiles();

      expect(result).toHaveLength(1);
      expect(result[0]!.id).toBe('profile-123');
      expect(result[0]!.company_name).toBe('Test Company');
    });

    it('should get profile (first from list)', async () => {
      const apiProfiles = [
        {
          id: 'profile-123',
          company_name: 'Test Company',
          industry: 'Technology',
          employee_count: 50,
        },
      ];
      mockApiClient.get.mockResolvedValueOnce(apiProfiles);

      const { businessProfileService } = await import('@/lib/api/business-profiles.service');
      const result = await businessProfileService.getProfile();

      expect(result).not.toBeNull();
      expect(result!.id).toBe('profile-123');
      expect(result!.company_name).toBe('Test Company');
    });

    it('should return null when no profiles exist', async () => {
      mockApiClient.get.mockResolvedValueOnce([]);

      const { businessProfileService } = await import('@/lib/api/business-profiles.service');
      const result = await businessProfileService.getProfile();

      expect(result).toBeNull();
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

      // The service transforms profileData via field mapper before posting,
      // and transforms the response back. company_name has no mapping, passes through.
      const apiResponse = {
        id: 'profile-new',
        company_name: 'New Company',
        industry: 'Healthcare',
        company_size: 'small',
      };
      mockApiClient.post.mockResolvedValueOnce(apiResponse);

      const { businessProfileService } = await import('@/lib/api/business-profiles.service');
      const result = await businessProfileService.createBusinessProfile(profileData);

      expect(result.company_name).toBe('New Company');
      expect(result.industry).toBe('Healthcare');
      expect(result.id).toBe('profile-new');
    });
  });

  // -------------------------------------------------------------------------
  // Error Handling
  // -------------------------------------------------------------------------
  describe('Error Handling', () => {
    it('should propagate network errors from apiClient.get', async () => {
      mockApiClient.get.mockRejectedValueOnce(new Error('Network error'));

      const { assessmentService } = await import('@/lib/api/assessments.service');
      await expect(assessmentService.getAssessments()).rejects.toThrow('Network error');
    });

    it('should propagate HTTP error responses from apiClient.get', async () => {
      const errorObj = { response: { status: 404, data: { detail: 'Resource not found' } } };
      mockApiClient.get.mockRejectedValueOnce(errorObj);

      const { assessmentService } = await import('@/lib/api/assessments.service');
      await expect(assessmentService.getAssessment('non-existent')).rejects.toMatchObject({
        response: expect.objectContaining({ status: 404 }),
      });
    });

    it('should propagate auth store errors for login', async () => {
      mockLoginFn.mockRejectedValueOnce(new Error('Login failed'));

      const { authService } = await import('@/lib/api/auth.service');
      await expect(
        authService.login({ email: 'test@example.com', password: 'bad', rememberMe: false }),
      ).rejects.toThrow('Login failed');
    });
  });
});
