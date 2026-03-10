import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockRefreshTokens = vi.fn();
const mockGetState = vi.fn(() => ({
  tokens: { access: 'test-access-token', refresh: 'test-refresh-token' },
  refreshTokens: mockRefreshTokens,
}));

// Mock the auth store before importing the client
vi.mock('@/lib/stores/auth.store', () => ({
  useAuthStore: {
    getState: mockGetState,
  },
}));

vi.mock('@/lib/validation/zod-schemas', () => ({
  // Just enough to satisfy imports
}));

describe('APIError', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  async function getModule() {
    const mod = await import('@/lib/api/client');
    return mod;
  }

  it('creates error with message, status, and response', async () => {
    const { APIError } = await getModule();

    const error = new APIError('Not found', 404, { detail: 'Resource not found' } as any);

    expect(error).toBeInstanceOf(Error);
    expect(error.name).toBe('APIError');
    expect(error.message).toBe('Not found');
    expect(error.status).toBe(404);
    expect(error.response).toEqual({ detail: 'Resource not found' });
  });

  it('allows undefined response', async () => {
    const { APIError } = await getModule();

    const error = new APIError('Server error', 500);

    expect(error.status).toBe(500);
    expect(error.response).toBeUndefined();
  });

  it('has status 0 for network errors', async () => {
    const { APIError } = await getModule();

    const error = new APIError('Network error', 0);

    expect(error.status).toBe(0);
    expect(error.message).toBe('Network error');
  });
});

describe('APIClient', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
    mockRefreshTokens.mockReset();
    mockGetState.mockReset();
    mockGetState.mockImplementation(() => ({
      tokens: { access: 'test-access-token', refresh: 'test-refresh-token' },
      refreshTokens: mockRefreshTokens,
    }));
  });

  async function getModule() {
    const mod = await import('@/lib/api/client');
    return mod;
  }

  describe('endpoint normalization', () => {
    it('prepends /api/v1 to endpoints without /api prefix', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ data: 'ok' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.get('/assessments');

      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/assessments'),
        expect.any(Object),
      );

      fetchSpy.mockRestore();
    });

    it('does not double-prepend for endpoints starting with /api', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ data: 'ok' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.get('/api/v2/custom');

      const calledUrl = fetchSpy.mock.calls[0][0] as string;
      expect(calledUrl).toContain('/api/v2/custom');
      expect(calledUrl).not.toContain('/api/v1/api/v2');

      fetchSpy.mockRestore();
    });
  });

  describe('query parameters', () => {
    it('appends query params to URL', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.get('/assessments', {
        params: { status: 'draft', page: 1 },
      });

      const calledUrl = fetchSpy.mock.calls[0][0] as string;
      expect(calledUrl).toContain('status=draft');
      expect(calledUrl).toContain('page=1');

      fetchSpy.mockRestore();
    });

    it('skips null and undefined params', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.get('/assessments', {
        params: { status: 'draft', framework: null, page: undefined },
      });

      const calledUrl = fetchSpy.mock.calls[0][0] as string;
      expect(calledUrl).toContain('status=draft');
      expect(calledUrl).not.toContain('framework');
      expect(calledUrl).not.toContain('page');

      fetchSpy.mockRestore();
    });
  });

  describe('HTTP methods', () => {
    it('GET uses GET method', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ id: '1' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.get('/test');
      expect(fetchSpy.mock.calls[0][1]!.method).toBe('GET');

      fetchSpy.mockRestore();
    });

    it('POST sends JSON body', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ id: '1' }), {
          status: 201,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.post('/test', { name: 'Test' });

      const options = fetchSpy.mock.calls[0][1]!;
      expect(options.method).toBe('POST');
      expect(options.body).toBe(JSON.stringify({ name: 'Test' }));

      fetchSpy.mockRestore();
    });

    it('PUT sends JSON body', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ id: '1' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.put('/test/1', { name: 'Updated' });

      const options = fetchSpy.mock.calls[0][1]!;
      expect(options.method).toBe('PUT');
      expect(options.body).toBe(JSON.stringify({ name: 'Updated' }));

      fetchSpy.mockRestore();
    });

    it('PATCH sends JSON body', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ id: '1' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.patch('/test/1', { status: 'active' });

      const options = fetchSpy.mock.calls[0][1]!;
      expect(options.method).toBe('PATCH');

      fetchSpy.mockRestore();
    });

    it('DELETE uses DELETE method', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify(null), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.delete('/test/1');
      expect(fetchSpy.mock.calls[0][1]!.method).toBe('DELETE');

      fetchSpy.mockRestore();
    });

    it('POST with no data sends null body', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ success: true }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.post('/test');
      expect(fetchSpy.mock.calls[0][1]!.body).toBeNull();

      fetchSpy.mockRestore();
    });
  });

  describe('error handling', () => {
    it('retries once after a 401 by refreshing tokens', async () => {
      const { apiClient } = await getModule();

      mockGetState
        .mockImplementationOnce(() => ({
          tokens: { access: 'expired-access-token', refresh: 'refresh-token' },
          refreshTokens: mockRefreshTokens,
        }))
        .mockImplementationOnce(() => ({
          tokens: { access: 'expired-access-token', refresh: 'refresh-token' },
          refreshTokens: mockRefreshTokens,
        }))
        .mockImplementation(() => ({
          tokens: { access: 'fresh-access-token', refresh: 'refresh-token' },
          refreshTokens: mockRefreshTokens,
        }));

      mockRefreshTokens.mockResolvedValue(undefined);

      const fetchSpy = vi
        .spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ detail: 'Unauthorized' }), {
            status: 401,
            headers: { 'content-type': 'application/json' },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { 'content-type': 'application/json' },
          }),
        );

      const response = await apiClient.get('/protected');

      expect(mockRefreshTokens).toHaveBeenCalledTimes(1);
      expect(fetchSpy).toHaveBeenCalledTimes(2);
      expect(response).toEqual({ ok: true });
    });

    it('throws APIError for non-OK response', async () => {
      const { apiClient, APIError } = await getModule();
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Not found' }), {
          status: 404,
          statusText: 'Not Found',
          headers: { 'content-type': 'application/json' },
        }),
      );

      await expect(apiClient.get('/missing')).rejects.toThrow(APIError);

      vi.restoreAllMocks();
    });

    it('includes error detail from response', async () => {
      const { apiClient } = await getModule();
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Forbidden resource' }), {
          status: 403,
          statusText: 'Forbidden',
          headers: { 'content-type': 'application/json' },
        }),
      );

      try {
        await apiClient.get('/forbidden');
        expect.fail('Should have thrown');
      } catch (error: any) {
        expect(error.message).toBe('Forbidden resource');
        expect(error.status).toBe(403);
      }

      vi.restoreAllMocks();
    });

    it('handles non-JSON error responses', async () => {
      const { apiClient } = await getModule();
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response('Internal Server Error', {
          status: 500,
          statusText: 'Internal Server Error',
          headers: { 'content-type': 'text/plain' },
        }),
      );

      try {
        await apiClient.get('/broken');
        expect.fail('Should have thrown');
      } catch (error: any) {
        expect(error.status).toBe(500);
      }

      vi.restoreAllMocks();
    });

    it('wraps network errors as APIError with status 0', async () => {
      const { apiClient, APIError } = await getModule();
      vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('fetch failed'));

      try {
        await apiClient.get('/unreachable');
        expect.fail('Should have thrown');
      } catch (error: any) {
        expect(error).toBeInstanceOf(APIError);
        expect(error.status).toBe(0);
        expect(error.message).toBe('fetch failed');
      }

      vi.restoreAllMocks();
    });
  });

  describe('auth headers', () => {
    it('includes Authorization header in requests', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({}), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.get('/test');

      const headers = fetchSpy.mock.calls[0][1]!.headers as Record<string, string>;
      expect(headers['Authorization']).toBe('Bearer test-access-token');
      expect(headers['Content-Type']).toBe('application/json');

      fetchSpy.mockRestore();
    });

    it('throws when no auth token available', async () => {
      // Re-mock the auth store with no tokens
      vi.doMock('@/lib/stores/auth.store', () => ({
        useAuthStore: {
          getState: vi.fn(() => ({
            tokens: null,
            refreshTokens: vi.fn(),
          })),
        },
      }));

      vi.resetModules();
      const { apiClient, APIError } = await import('@/lib/api/client');

      await expect(apiClient.get('/test')).rejects.toThrow(APIError);

      // Restore original mock
      vi.doMock('@/lib/stores/auth.store', () => ({
        useAuthStore: {
          getState: vi.fn(() => ({
            tokens: { access: 'test-access-token', refresh: 'test-refresh-token' },
            refreshTokens: vi.fn(),
          })),
        },
      }));
    });
  });

  describe('public requests', () => {
    it('publicGet does not require auth', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ data: 'public' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.publicGet('/public-endpoint');

      const headers = fetchSpy.mock.calls[0][1]!.headers as Record<string, string>;
      expect(headers['Content-Type']).toBe('application/json');
      expect(headers['Authorization']).toBeUndefined();

      fetchSpy.mockRestore();
    });

    it('publicPost sends data without auth', async () => {
      const { apiClient } = await getModule();
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ id: '1' }), {
          status: 201,
          headers: { 'content-type': 'application/json' },
        }),
      );

      await apiClient.publicPost('/register', { email: 'user@test.com' });

      const options = fetchSpy.mock.calls[0][1]!;
      expect(options.method).toBe('POST');
      expect(options.body).toBe(JSON.stringify({ email: 'user@test.com' }));

      fetchSpy.mockRestore();
    });
  });

  describe('response handling', () => {
    it('parses JSON responses', async () => {
      const { apiClient } = await getModule();
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ id: '1', name: 'Test' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      const result = await apiClient.get<{ id: string; name: string }>('/test');
      expect(result).toEqual({ id: '1', name: 'Test' });

      vi.restoreAllMocks();
    });

    it('returns text for non-JSON responses', async () => {
      const { apiClient } = await getModule();
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response('plain text response', {
          status: 200,
          headers: { 'content-type': 'text/plain' },
        }),
      );

      const result = await apiClient.get<string>('/text');
      expect(result).toBe('plain text response');

      vi.restoreAllMocks();
    });
  });
});
