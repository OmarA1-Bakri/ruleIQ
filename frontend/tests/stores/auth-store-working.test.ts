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
    // tokens is initialized as { access: null, refresh: null } not null
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

  it('should clear error when clearError is called', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    // Set an error first
    useAuthStore.setState({ error: 'Test error' });
    expect(useAuthStore.getState().error).toBe('Test error');

    // Clear the error
    store.clearError();
    expect(useAuthStore.getState().error).toBeNull();
  });

  it('should set user when setUser is called', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    const mockUser = {
      id: 'user-123',
      email: 'test@example.com',
      name: 'Test User',
      created_at: new Date().toISOString(),
      is_active: true,
    };

    store.setUser(mockUser);
    expect(useAuthStore.getState().user).toEqual(mockUser);
  });

  it('should set tokens when setTokens is called', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    const mockTokens = {
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token',
      token_type: 'Bearer',
    };

    store.setTokens(mockTokens);
    // setTokens normalises AuthTokens { access_token, refresh_token } to { access, refresh }
    expect(useAuthStore.getState().tokens).toEqual({
      access: 'mock-access-token',
      refresh: 'mock-refresh-token',
    });
  });

  it('should return current user when getCurrentUser is called', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    const mockUser = {
      id: 'user-456',
      email: 'current@example.com',
      name: 'Current User',
      created_at: new Date().toISOString(),
      is_active: true,
    };

    // Set user first
    store.setUser(mockUser);

    // Get current user
    const currentUser = store.getCurrentUser();
    expect(currentUser).toEqual(mockUser);
  });

  it('should return token when getToken is called', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth.store');
    const store = useAuthStore.getState();

    const mockTokens = {
      access_token: 'test-access-token',
      refresh_token: 'test-refresh-token',
      token_type: 'Bearer',
    };

    // Set tokens first
    store.setTokens(mockTokens);

    // Get token
    const token = store.getToken();
    expect(token).toBe('test-access-token');
  });
});
