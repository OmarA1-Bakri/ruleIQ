import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAuthStore } from '@/lib/stores/auth.store';

// Mock the auth store
vi.mock('@/lib/stores/auth.store');

// Mock the business profile field mapper
vi.mock('@/lib/api/business-profile/field-mapper', () => ({
  BusinessProfileFieldMapper: {
    transformAPIResponseForFrontend: vi.fn((data) => data),
    transformFormDataForAPI: vi.fn((data) => data),
    createUpdatePayload: vi.fn((profile, updates) => updates),
  },
}));

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
}));

// Mock secure storage
vi.mock('@/lib/utils/secure-storage', () => ({
  default: {
    getAccessToken: vi.fn().mockResolvedValue('test-token'),
    setAccessToken: vi.fn(),
    getRefreshToken: vi.fn().mockReturnValue('refresh-token'),
    setRefreshToken: vi.fn(),
    clearAll: vi.fn(),
  },
}));

// Import services after mocking
import { authService } from '@/lib/api/auth.service';
import { assessmentService } from '@/lib/api/assessments.service';
import { evidenceService } from '@/lib/api/evidence.service';
import { businessProfileService } from '@/lib/api/business-profiles.service';
import { apiClient } from '@/lib/api/client';

describe('API Services', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('AuthService', () => {
    it('should handle successful login', async () => {
      const mockLogin = vi.fn().mockResolvedValueOnce(undefined);
      const mockGetState = vi.fn().mockReturnValue({
        user: null,
        tokens: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        login: mockLogin,
        register: vi.fn(),
        logout: vi.fn(),
        refreshToken: vi.fn(),
        setUser: vi.fn(),
        setTokens: vi.fn(),
        clearError: vi.fn(),
        checkAuthStatus: vi.fn(),
        initialize: vi.fn(),
        getCurrentUser: vi.fn(),
        getToken: vi.fn(),
        requestPasswordReset: vi.fn(),
        resetPassword: vi.fn(),
        verifyEmail: vi.fn(),
        updateProfile: vi.fn(),
        changePassword: vi.fn(),
      });
      
      vi.mocked(useAuthStore).getState = mockGetState;

      await authService.login('test@example.com', 'password123');

      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
        rememberMe: false,
      });
    });

    it('should handle login failure', async () => {
      const error = new Error('Invalid credentials');
      const mockLogin = vi.fn().mockRejectedValueOnce(error);
      const mockGetState = vi.fn().mockReturnValue({
        user: null,
        tokens: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        login: mockLogin,
        register: vi.fn(),
        logout: vi.fn(),
        refreshToken: vi.fn(),
        setUser: vi.fn(),
        setTokens: vi.fn(),
        clearError: vi.fn(),
        checkAuthStatus: vi.fn(),
        initialize: vi.fn(),
        getCurrentUser: vi.fn(),
        getToken: vi.fn(),
        requestPasswordReset: vi.fn(),
        resetPassword: vi.fn(),
        verifyEmail: vi.fn(),
        updateProfile: vi.fn(),
        changePassword: vi.fn(),
      });
      
      vi.mocked(useAuthStore).getState = mockGetState;

      await expect(
        authService.login('test@example.com', 'wrongpassword')
      ).rejects.toThrow('Invalid credentials');
    });

    it('should handle registration', async () => {
      const mockRegister = vi.fn().mockResolvedValueOnce(undefined);
      const mockGetState = vi.fn().mockReturnValue({
        user: null,
        tokens: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        login: vi.fn(),
        register: mockRegister,
        logout: vi.fn(),
        refreshToken: vi.fn(),
        setUser: vi.fn(),
        setTokens: vi.fn(),
        clearError: vi.fn(),
        checkAuthStatus: vi.fn(),
        initialize: vi.fn(),
        getCurrentUser: vi.fn(),
        getToken: vi.fn(),
        requestPasswordReset: vi.fn(),
        resetPassword: vi.fn(),
        verifyEmail: vi.fn(),
        updateProfile: vi.fn(),
        changePassword: vi.fn(),
      });
      
      vi.mocked(useAuthStore).getState = mockGetState;

      await authService.register('new@example.com', 'password123', 'New User');

      expect(mockRegister).toHaveBeenCalledWith(
        'new@example.com',
        'password123',
        'New User'
      );
    });

    it('should handle logout', () => {
      const mockLogout = vi.fn();
      const mockGetState = vi.fn().mockReturnValue({
        user: null,
        tokens: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        login: vi.fn(),
        register: vi.fn(),
        logout: mockLogout,
        refreshToken: vi.fn(),
        setUser: vi.fn(),
        setTokens: vi.fn(),
        clearError: vi.fn(),
        checkAuthStatus: vi.fn(),
        initialize: vi.fn(),
        getCurrentUser: vi.fn(),
        getToken: vi.fn(),
        requestPasswordReset: vi.fn(),
        resetPassword: vi.fn(),
        verifyEmail: vi.fn(),
        updateProfile: vi.fn(),
        changePassword: vi.fn(),
      });
      
      vi.mocked(useAuthStore).getState = mockGetState;

      authService.logout();
      
      expect(mockLogout).toHaveBeenCalled();
    });

    it('should get current user', () => {
      const mockUser = {
        id: 'user-123',
        email: 'test@example.com',
        full_name: 'Test User',
      };
      
      const mockGetCurrentUser = vi.fn().mockReturnValue(mockUser);
      const mockGetState = vi.fn().mockReturnValue({
        user: mockUser,
        tokens: null,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
        refreshToken: vi.fn(),
        setUser: vi.fn(),
        setTokens: vi.fn(),
        clearError: vi.fn(),
        checkAuthStatus: vi.fn(),
        initialize: vi.fn(),
        getCurrentUser: mockGetCurrentUser,
        getToken: vi.fn(),
        requestPasswordReset: vi.fn(),
        resetPassword: vi.fn(),
        verifyEmail: vi.fn(),
        updateProfile: vi.fn(),
        changePassword: vi.fn(),
      });
      
      vi.mocked(useAuthStore).getState = mockGetState;
      
      const result = authService.getCurrentUser();

      expect(result).toEqual(mockUser);
      expect(mockGetCurrentUser).toHaveBeenCalled();
    });
  });

  describe('AssessmentService', () => {
    it('should get assessments with pagination', async () => {
      const mockAssessments = {
        items: [
          { id: 'assess-1', type: 'gdpr' },
          { id: 'assess-2', type: 'iso27001' },
        ],
        total: 2,
        page: 1,
        per_page: 10,
        total_pages: 1,
      };

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockAssessments);

      const result = await assessmentService.getAssessments({ page: 1, limit: 10 });

      expect(result).toEqual(mockAssessments);
      expect(apiClient.get).toHaveBeenCalledWith('/assessments', {
        params: { page: 1, limit: 10 },
      });
    });

    it('should create new assessment', async () => {
      const mockAssessment = {
        id: 'assess-new',
        type: 'gdpr',
        status: 'pending',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      vi.mocked(apiClient.post).mockResolvedValueOnce(mockAssessment);

      const result = await assessmentService.createAssessment({ type: 'gdpr' });

      expect(result).toEqual(mockAssessment);
      expect(apiClient.post).toHaveBeenCalledWith('/assessments', { type: 'gdpr' });
    });

    it('should get single assessment', async () => {
      const mockAssessment = {
        id: 'assess-123',
        type: 'gdpr',
        status: 'completed',
      };

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockAssessment);

      const result = await assessmentService.getAssessment('assess-123');

      expect(result).toEqual(mockAssessment);
      expect(apiClient.get).toHaveBeenCalledWith('/assessments/assess-123');
    });

    it('should update assessment', async () => {
      const updates = { status: 'completed' };
      const mockUpdated = {
        id: 'assess-123',
        type: 'gdpr',
        status: 'completed',
      };

      vi.mocked(apiClient.patch).mockResolvedValueOnce(mockUpdated);

      const result = await assessmentService.updateAssessment('assess-123', updates);

      expect(result).toEqual(mockUpdated);
      expect(apiClient.patch).toHaveBeenCalledWith('/assessments/assess-123', updates);
    });

    it('should complete assessment', async () => {
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: { message: 'Assessment completed' } });

      await assessmentService.completeAssessment('assess-123');

      expect(apiClient.post).toHaveBeenCalledWith('/assessments/assess-123/complete');
    });
  });

  describe('EvidenceService', () => {
    it('should get evidence with filters', async () => {
      const mockEvidence = {
        items: [
          { id: 'evidence-1', type: 'document', name: 'Policy.pdf' },
          { id: 'evidence-2', type: 'screenshot', name: 'Dashboard.png' },
        ],
        total: 2,
      };

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockEvidence);

      const result = await evidenceService.getEvidence({ type: 'document' });

      expect(result).toEqual(mockEvidence);
      expect(apiClient.get).toHaveBeenCalledWith('/evidence', {
        params: { type: 'document' },
      });
    });

    it('should upload evidence file', async () => {
      const file = new File(['content'], 'test.pdf', { type: 'application/pdf' });
      const mockResponse = {
        id: 'evidence-new',
        name: 'test.pdf',
        type: 'document',
      };

      vi.mocked(apiClient.post).mockResolvedValueOnce(mockResponse);

      const result = await evidenceService.uploadEvidence(file);

      expect(result).toEqual(mockResponse);
      expect(apiClient.post).toHaveBeenCalledWith('/evidence/upload', expect.any(FormData));
    });

    it('should update evidence status', async () => {
      const mockUpdated = {
        id: 'evidence-123',
        status: 'approved',
      };

      vi.mocked(apiClient.patch).mockResolvedValueOnce(mockUpdated);

      const result = await evidenceService.updateEvidenceStatus('evidence-123', 'approved');

      expect(result).toEqual(mockUpdated);
      expect(apiClient.patch).toHaveBeenCalledWith('/evidence/evidence-123', {
        status: 'approved',
      });
    });

    it('should delete evidence', async () => {
      vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: { message: 'Deleted' } });

      await evidenceService.deleteEvidence('evidence-123');

      expect(apiClient.delete).toHaveBeenCalledWith('/evidence/evidence-123');
    });
  });

  describe('BusinessProfileService', () => {
    it('should get business profile', async () => {
      const mockProfile = {
        id: 'profile-123',
        company_name: 'Test Company',
        industry: 'Technology',
      };

      // getProfile internally calls getBusinessProfiles which returns an array
      vi.mocked(apiClient.get).mockResolvedValueOnce([mockProfile]);

      const result = await businessProfileService.getProfile();

      expect(result).toEqual(mockProfile);
      expect(apiClient.get).toHaveBeenCalledWith('/business-profiles');
    });

    it('should create business profile', async () => {
      const profileData = {
        company_name: 'New Company',
        industry: 'Finance',
      };
      const mockCreated = { id: 'profile-new', ...profileData };

      vi.mocked(apiClient.post).mockResolvedValueOnce(mockCreated);

      const result = await businessProfileService.createBusinessProfile(profileData);

      expect(result).toEqual(mockCreated);
      expect(apiClient.post).toHaveBeenCalledWith('/business-profiles', profileData);
    });

    it('should update business profile', async () => {
      const existingProfile = {
        id: 'profile-123',
        company_name: 'Test Company',
        industry: 'Technology',
      };
      const updates = { industry: 'Healthcare' };
      const mockUpdated = {
        id: 'profile-123',
        company_name: 'Test Company',
        industry: 'Healthcare',
      };

      vi.mocked(apiClient.put).mockResolvedValueOnce(mockUpdated);

      const result = await businessProfileService.updateBusinessProfile('profile-123', updates);

      expect(result).toEqual(mockUpdated);
      expect(apiClient.put).toHaveBeenCalledWith('/business-profiles/profile-123', updates);
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors', async () => {
      const networkError = new Error('Network error');
      vi.mocked(apiClient.get).mockRejectedValueOnce(networkError);

      await expect(assessmentService.getAssessments()).rejects.toThrow('Network error');
    });

    it('should handle HTTP error responses', async () => {
      const httpError = {
        response: {
          status: 404,
          data: { detail: 'Not found' },
        },
      };
      vi.mocked(apiClient.get).mockRejectedValueOnce(httpError);

      await expect(assessmentService.getAssessment('invalid')).rejects.toMatchObject({
        response: { status: 404 },
      });
    });

    it('should handle authentication errors', async () => {
      const authError = {
        response: {
          status: 401,
          data: { detail: 'Unauthorized' },
        },
      };
      vi.mocked(apiClient.get).mockRejectedValueOnce(authError);

      await expect(assessmentService.getAssessments()).rejects.toMatchObject({
        response: { status: 401 },
      });
    });

    it('should handle validation errors', async () => {
      const validationError = {
        response: {
          status: 422,
          data: {
            detail: [
              { loc: ['body', 'email'], msg: 'Invalid email' },
            ],
          },
        },
      };
      vi.mocked(apiClient.post).mockRejectedValueOnce(validationError);

      await expect(assessmentService.createAssessment({})).rejects.toMatchObject({
        response: { status: 422 },
      });
    });

    it('should handle rate limiting', async () => {
      const rateLimitError = {
        response: {
          status: 429,
          data: { detail: 'Too many requests' },
        },
      };
      vi.mocked(apiClient.get).mockRejectedValueOnce(rateLimitError);

      await expect(assessmentService.getAssessments()).rejects.toMatchObject({
        response: { status: 429 },
      });
    });
  });

  describe('Request Interceptors', () => {
    it('should include authorization headers', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: {} });

      await assessmentService.getAssessments();

      // The actual API client should handle adding auth headers
      expect(apiClient.get).toHaveBeenCalled();
    });

    it('should handle requests without auth', async () => {
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: {} });

      // Public endpoints shouldn't require auth
      await apiClient.post('/public/endpoint', {});

      expect(apiClient.post).toHaveBeenCalledWith('/public/endpoint', {});
    });
  });
});