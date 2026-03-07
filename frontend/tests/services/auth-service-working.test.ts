import { describe, it, expect, vi, beforeEach } from 'vitest';
import { authService } from '@/lib/api/auth.service';

// Mock the auth store
vi.mock('@/lib/stores/auth.store', () => {
  const mockStore = {
    user: null,
    tokens: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
    login: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn(),
    refreshToken: vi.fn().mockResolvedValue(undefined),
    refreshTokens: vi.fn().mockResolvedValue(undefined),
    setUser: vi.fn(),
    setTokens: vi.fn(),
    clearError: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
    initialize: vi.fn().mockResolvedValue(undefined),
    getCurrentUser: vi.fn().mockReturnValue(null),
    getToken: vi.fn().mockReturnValue(null),
    requestPasswordReset: vi.fn().mockResolvedValue(undefined),
    resetPassword: vi.fn().mockResolvedValue(undefined),
    verifyEmail: vi.fn().mockResolvedValue(undefined),
    updateProfile: vi.fn().mockResolvedValue(undefined),
    changePassword: vi.fn().mockResolvedValue(undefined),
  };

  const mockUseAuthStore = vi.fn(() => mockStore) as any;
  mockUseAuthStore.getState = vi.fn(() => mockStore);
  mockUseAuthStore.setState = vi.fn();
  mockUseAuthStore.subscribe = vi.fn();
  mockUseAuthStore.destroy = vi.fn();

  return {
    useAuthStore: mockUseAuthStore,
  };
});

describe('Auth Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('login', () => {
    it('should call auth store login method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      await authService.login('test@example.com', 'password123');

      // authService.login with old-style (email, password) args converts to object form
      expect(mockStore.login).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
        rememberMe: false,
      });
    });
  });

  describe('register', () => {
    it('should call auth store register method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      await authService.register('test@example.com', 'password123', 'Test User');

      expect(mockStore.register).toHaveBeenCalledWith(
        'test@example.com',
        'password123',
        'Test User',
      );
    });
  });

  describe('logout', () => {
    it('should call auth store logout method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      authService.logout();

      expect(mockStore.logout).toHaveBeenCalled();
    });
  });

  describe('getCurrentUser', () => {
    it('should call auth store getCurrentUser method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      const result = authService.getCurrentUser();

      expect(mockStore.getCurrentUser).toHaveBeenCalled();
      expect(result).toBe(null);
    });
  });

  describe('getToken', () => {
    it('should call auth store getToken method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      const result = authService.getToken();

      expect(mockStore.getToken).toHaveBeenCalled();
      expect(result).toBe(null);
    });
  });

  describe('isAuthenticated', () => {
    it('should return auth store isAuthenticated state', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      const result = authService.isAuthenticated();

      expect(result).toBe(false);
    });
  });

  describe('refreshToken', () => {
    it('should call auth store refreshTokens method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      await authService.refreshToken();

      expect(mockStore.refreshTokens).toHaveBeenCalled();
    });
  });

  describe('checkAuthStatus', () => {
    it('should call auth store checkAuthStatus method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      await authService.checkAuthStatus();

      expect(mockStore.checkAuthStatus).toHaveBeenCalled();
    });
  });

  describe('initialize', () => {
    it('should call auth store initialize method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      await authService.initialize();

      expect(mockStore.initialize).toHaveBeenCalled();
    });
  });

  describe('requestPasswordReset', () => {
    it('should call auth store requestPasswordReset method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      await authService.requestPasswordReset('test@example.com');

      expect(mockStore.requestPasswordReset).toHaveBeenCalledWith('test@example.com');
    });
  });

  describe('resetPassword', () => {
    it('should call auth store resetPassword method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      await authService.resetPassword('token123', 'newpassword');

      expect(mockStore.resetPassword).toHaveBeenCalledWith('token123', 'newpassword');
    });
  });

  describe('verifyEmail', () => {
    it('should call auth store verifyEmail method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      await authService.verifyEmail('token123');

      expect(mockStore.verifyEmail).toHaveBeenCalledWith('token123');
    });
  });

  describe('updateProfile', () => {
    it('should call auth store updateProfile method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();
      const updateData = { name: 'New Name' };

      await authService.updateProfile(updateData);

      expect(mockStore.updateProfile).toHaveBeenCalledWith(updateData);
    });
  });

  describe('changePassword', () => {
    it('should call auth store changePassword method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      await authService.changePassword('oldpass', 'newpass');

      expect(mockStore.changePassword).toHaveBeenCalledWith('oldpass', 'newpass');
    });
  });

  describe('utility methods', () => {
    it('should provide clearError method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      authService.clearError();

      expect(mockStore.clearError).toHaveBeenCalled();
    });

    it('should provide getUser method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      const result = authService.getUser();

      expect(result).toBe(null);
    });

    it('should provide getTokens method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      const result = authService.getTokens();

      expect(result).toBe(null);
    });

    it('should provide getError method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      const result = authService.getError();

      expect(result).toBe(null);
    });

    it('should provide isLoading method', async () => {
      const { useAuthStore } = await import('@/lib/stores/auth.store');
      const mockStore = useAuthStore.getState();

      const result = authService.isLoading();

      expect(result).toBe(false);
    });
  });
});
