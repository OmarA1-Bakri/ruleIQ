import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock fetch globally
global.fetch = vi.fn();

describe('Auth Store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
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

  it('should retry /auth/me after refreshing an expired token', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'expired' }), {
          status: 401,
          headers: { 'content-type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
            token_type: 'bearer',
          }),
          {
            status: 200,
            headers: { 'content-type': 'application/json' },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: 'user-123',
            email: 'test@example.com',
            created_at: new Date().toISOString(),
            is_active: true,
          }),
          {
            status: 200,
            headers: { 'content-type': 'application/json' },
          },
        ),
      );

    const { useAuthStore } = await import('@/lib/stores/auth.store');

    useAuthStore.setState({
      tokens: { access: 'expired-access-token', refresh: 'refresh-token' },
      isAuthenticated: false,
      user: null,
      accessToken: 'expired-access-token',
      refreshTokenValue: 'refresh-token',
    });

    await useAuthStore.getState().checkAuthStatus();

    const state = useAuthStore.getState();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(state.tokens).toEqual({ access: 'new-access-token', refresh: 'new-refresh-token' });
    expect(state.user?.email).toBe('test@example.com');
    expect(state.isAuthenticated).toBe(true);
  });

  it('should include the refresh token when logging out', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ message: 'ok' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );

    const { useAuthStore } = await import('@/lib/stores/auth.store');

    useAuthStore.setState({
      tokens: { access: 'access-token', refresh: 'refresh-token' },
      isAuthenticated: true,
      user: {
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User',
        created_at: new Date().toISOString(),
        is_active: true,
      } as any,
      accessToken: 'access-token',
      refreshTokenValue: 'refresh-token',
    });

    await useAuthStore.getState().logout();

    const [, requestInit] = fetchMock.mock.calls[0];
    expect(requestInit?.body).toBe(JSON.stringify({ refresh_token: 'refresh-token' }));
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().tokens).toEqual({ access: null, refresh: null });
  });
});
