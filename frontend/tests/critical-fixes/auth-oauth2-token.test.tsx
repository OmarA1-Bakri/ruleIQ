import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import React from 'react';

// Test the authentication service integration
describe('Authentication Service Integration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    queryClient.clear();
  });

  const TestWrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  describe('Login Flow', () => {
    it('should send JSON data to /api/v1/auth/login endpoint', async () => {
      // Mock successful login response
      let capturedRequestBody: any = null;
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', async ({ request }) => {
          capturedRequestBody = await request.json();
          return HttpResponse.json({
            access_token: 'mock-access-token',
            refresh_token: 'mock-refresh-token',
            token_type: 'bearer',
          });
        }),
        // Mock the /api/v1/auth/me endpoint for user data
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json({
            id: 'user-123',
            email: 'test@example.com',
            is_active: true,
            permissions: ['read', 'write'],
            role: 'user',
          });
        }),
      );

      const { authService } = await import('@/lib/api/auth.service');

      await authService.login('test@example.com', 'password123');

      // Verify JSON data format
      expect(capturedRequestBody).toEqual({
        email: 'test@example.com',
        password: 'password123',
      });
    });

    it('should handle 422 authentication errors correctly', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json(
            {
              detail: [
                { loc: ['body', 'email'], msg: 'field required', type: 'value_error.missing' },
              ],
            },
            { status: 422 },
          );
        }),
      );

      const { authService } = await import('@/lib/api/auth.service');

      await expect(authService.login('', 'password123')).rejects.toThrow();
    });

    it('should handle invalid credentials (401) correctly', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json(
            { detail: 'Invalid credentials' },
            { status: 401 },
          );
        }),
      );

      const { authService } = await import('@/lib/api/auth.service');

      await expect(authService.login('wrong@example.com', 'wrongpassword')).rejects.toThrow('Invalid credentials');
    });

    it('should fetch user data after successful token response', async () => {
      let userEndpointCalled = false;
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json({
            access_token: 'mock-access-token',
            refresh_token: 'mock-refresh-token',
            token_type: 'bearer',
          });
        }),
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          userEndpointCalled = true;
          return HttpResponse.json({
            id: 'user-123',
            email: 'test@example.com',
            is_active: true,
            permissions: ['read', 'write'],
            role: 'user',
          });
        }),
      );

      const { authService } = await import('@/lib/api/auth.service');

      await authService.login('test@example.com', 'password123');

      expect(userEndpointCalled).toBe(true);
    });

    it('should store tokens securely after successful login', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json({
            access_token: 'mock-access-token',
            refresh_token: 'mock-refresh-token',
            token_type: 'bearer',
          });
        }),
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json({
            id: 'user-123',
            email: 'test@example.com',
            is_active: true,
            permissions: ['read', 'write'],
            role: 'user',
          });
        }),
      );

      const { authService } = await import('@/lib/api/auth.service');

      await authService.login('test@example.com', 'password123');

      // Check if token is stored
      const token = authService.getToken();
      expect(token).toBe('mock-access-token');
    });

    it('should handle network errors gracefully', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.error();
        }),
      );

      const { authService } = await import('@/lib/api/auth.service');

      await expect(authService.login('test@example.com', 'password123')).rejects.toThrow();
    });
  });

  describe('Token Management', () => {
    it('should retrieve stored tokens for authenticated requests', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json({
            access_token: 'stored-access-token',
            refresh_token: 'stored-refresh-token',
            token_type: 'bearer',
          });
        }),
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json({
            id: 'user-456',
            email: 'test@example.com',
            is_active: true,
            permissions: ['read', 'write'],
            role: 'user',
          });
        }),
      );

      const { authService } = await import('@/lib/api/auth.service');

      await authService.login('test@example.com', 'password123');

      // Verify token retrieval
      const token = authService.getToken();
      expect(token).toBe('stored-access-token');
    });

    it('should clear tokens on logout', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json({
            access_token: 'logout-test-token',
            refresh_token: 'logout-refresh-token',
            token_type: 'bearer',
          });
        }),
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json({
            id: 'user-789',
            email: 'test@example.com',
            is_active: true,
            permissions: ['read'],
            role: 'user',
          });
        }),
        http.post('http://localhost:8000/api/v1/auth/logout', () => {
          return HttpResponse.json({ message: 'Logged out successfully' });
        }),
      );

      const { authService } = await import('@/lib/api/auth.service');

      // Login first
      await authService.login('test@example.com', 'password123');
      expect(authService.getToken()).toBe('logout-test-token');

      // Then logout
      authService.logout();
      expect(authService.getToken()).toBeNull();
    });
  });
});