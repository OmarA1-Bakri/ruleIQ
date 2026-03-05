import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock fetch globally
global.fetch = vi.fn();

describe('Auth Store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it('should have correct initial state', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(store.user).toBeNull();
    expect(store.tokens).toEqual({ access: null, refresh: null });
    expect(store.isAuthenticated).toBe(false);
    expect(store.isLoading).toBe(false);
    expect(store.error).toBeNull();
  });

  it('should provide login method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.login).toBe('function');
  });

  it('should provide register method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.register).toBe('function');
  });

  it('should provide logout method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.logout).toBe('function');
  });

  it('should provide refreshToken method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.refreshToken).toBe('function');
  });

  it('should provide setUser method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.setUser).toBe('function');
  });

  it('should provide setTokens method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.setTokens).toBe('function');
  });

  it('should provide clearError method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.clearError).toBe('function');
  });

  it('should provide checkAuthStatus method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.checkAuthStatus).toBe('function');
  });

  it('should provide initialize method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.initialize).toBe('function');
  });

  it('should provide getCurrentUser method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.getCurrentUser).toBe('function');
  });

  it('should provide getToken method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.getToken).toBe('function');
  });

  it('should provide requestPasswordReset method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.requestPasswordReset).toBe('function');
  });

  it('should provide resetPassword method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.resetPassword).toBe('function');
  });

  it('should provide verifyEmail method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.verifyEmail).toBe('function');
  });

  it('should provide updateProfile method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.updateProfile).toBe('function');
  });

  it('should provide changePassword method', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    expect(typeof store.changePassword).toBe('function');
  });

  it('should have clearError method that can be called', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    // Just verify the method exists and can be called without error
    expect(() => store.clearError()).not.toThrow();
  });

  it('should have setUser method that can be called', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    const mockUser = {
      id: 'user-123',
      email: 'test@example.com',
      name: 'Test User',
      created_at: new Date().toISOString(),
      is_active: true,
    };

    // Just verify the method exists and can be called without error
    expect(() => store.setUser(mockUser)).not.toThrow();
  });

  it('should have setTokens method that can be called', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    const mockTokens = {
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token',
      token_type: 'Bearer',
    };

    // Just verify the method exists and can be called without error
    expect(() => store.setTokens(mockTokens)).not.toThrow();
  });

  it('should have getCurrentUser method that returns a value', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    // Just verify the method exists and returns something (null is valid)
    const result = store.getCurrentUser();
    expect(result).toBeDefined();
  });

  it('should have getToken method that returns a value', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    // Just verify the method exists and returns something (null is valid)
    const result = store.getToken();
    expect(result).toBeDefined();
  });
});
