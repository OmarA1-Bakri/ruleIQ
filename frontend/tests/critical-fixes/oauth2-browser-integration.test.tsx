import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import React from 'react';
import LoginPage from '@/app/(auth)/login/page';
import { useAuthStore } from '@/lib/stores/auth.store';
import { AuthGuard } from '@/components/auth/auth-guard';

// Mock Next.js router
const mockPush = vi.fn();
const mockReplace = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));

describe('OAuth2 Browser Integration Tests', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
    mockPush.mockClear();
    mockReplace.mockClear();
    
    // Clear auth store state
    useAuthStore.getState().logout();
    
    // Clear localStorage
    localStorage.clear();
  });

  afterEach(() => {
    queryClient.clear();
    vi.clearAllMocks();
  });

  const TestWrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  describe('Complete Authentication Flow', () => {
    it('should handle complete login flow with OAuth2 tokens', async () => {
      // Mock successful login and user endpoints
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', async ({ request }) => {
          const body = await request.json();
          expect(body).toEqual({
            email: 'test@example.com',
            password: 'password123',
          });
          
          return HttpResponse.json({
            access_token: 'mock-access-token-12345',
            refresh_token: 'mock-refresh-token-67890',
            token_type: 'bearer',
          });
        }),
        http.get('http://localhost:8000/api/v1/auth/me', ({ request }) => {
          const authHeader = request.headers.get('Authorization');
          expect(authHeader).toBe('Bearer mock-access-token-12345');
          
          return HttpResponse.json({
            id: 'user-123',
            email: 'test@example.com',
            is_active: true,
            permissions: ['read', 'write'],
            role: 'user',
            created_at: '2024-01-01T00:00:00Z',
          });
        }),
      );

      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      );

      // Verify login form is rendered
      expect(screen.getByText('Login to ruleIQ')).toBeInTheDocument();
      expect(screen.getByLabelText('Email')).toBeInTheDocument();
      expect(screen.getByLabelText('Password')).toBeInTheDocument();

      // Fill in the form
      fireEvent.change(screen.getByLabelText('Email'), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByLabelText('Password'), {
        target: { value: 'password123' },
      });

      // Submit the form
      const submitButton = screen.getByRole('button', { name: /login/i });
      fireEvent.click(submitButton);

      // Wait for loading state
      await waitFor(() => {
        expect(screen.getByText('Logging in...')).toBeInTheDocument();
      });

      // Wait for login to complete
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/dashboard');
      }, { timeout: 5000 });

      // Verify tokens are stored in auth store
      const authState = useAuthStore.getState();
      expect(authState.isAuthenticated).toBe(true);
      expect(authState.tokens?.access_token).toBe('mock-access-token-12345');
      expect(authState.tokens?.refresh_token).toBe('mock-refresh-token-67890');
      expect(authState.user?.email).toBe('test@example.com');
    });

    it('should handle login with invalid credentials', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json(
            { detail: 'Invalid credentials' },
            { status: 401 }
          );
        }),
      );

      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      );

      // Fill in invalid credentials
      fireEvent.change(screen.getByLabelText('Email'), {
        target: { value: 'invalid@example.com' },
      });
      fireEvent.change(screen.getByLabelText('Password'), {
        target: { value: 'wrongpassword' },
      });

      // Submit the form
      const submitButton = screen.getByRole('button', { name: /login/i });
      fireEvent.click(submitButton);

      // Wait for error message
      await waitFor(() => {
        expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
      });

      // Verify no redirect occurred
      expect(mockPush).not.toHaveBeenCalled();

      // Verify auth state remains unauthenticated
      const authState = useAuthStore.getState();
      expect(authState.isAuthenticated).toBe(false);
      expect(authState.tokens).toBeNull();
    });

    it('should handle token refresh flow', async () => {
      // Setup initial authenticated state
      const initialTokens = {
        access_token: 'expired-token',
        refresh_token: 'valid-refresh-token',
        token_type: 'bearer' as const,
      };

      act(() => {
        useAuthStore.getState().setTokens(initialTokens);
        useAuthStore.getState().setUser({
          id: 'user-123',
          email: 'test@example.com',
          is_active: true,
          permissions: ['read', 'write'],
          role: 'user',
          created_at: '2024-01-01T00:00:00Z',
        });
      });

      // Mock token refresh endpoint
      server.use(
        http.post('http://localhost:8000/api/v1/auth/refresh', async ({ request }) => {
          const body = await request.json();
          expect(body).toEqual({ refresh_token: 'valid-refresh-token' });
          
          return HttpResponse.json({
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
            token_type: 'bearer',
          });
        }),
      );

      // Trigger token refresh
      await act(async () => {
        await useAuthStore.getState().refreshToken();
      });

      // Verify tokens were updated
      const authState = useAuthStore.getState();
      expect(authState.tokens?.access_token).toBe('new-access-token');
      expect(authState.tokens?.refresh_token).toBe('new-refresh-token');
      expect(authState.isAuthenticated).toBe(true);
    });

    it('should handle failed token refresh by logging out', async () => {
      // Setup initial authenticated state
      const initialTokens = {
        access_token: 'expired-token',
        refresh_token: 'invalid-refresh-token',
        token_type: 'bearer' as const,
      };

      act(() => {
        useAuthStore.getState().setTokens(initialTokens);
      });

      // Mock failed token refresh
      server.use(
        http.post('http://localhost:8000/api/v1/auth/refresh', () => {
          return HttpResponse.json(
            { detail: 'Invalid refresh token' },
            { status: 401 }
          );
        }),
      );

      // Trigger token refresh
      await act(async () => {
        try {
          await useAuthStore.getState().refreshToken();
        } catch {
          // Expected to fail
        }
      });

      // Verify user was logged out
      const authState = useAuthStore.getState();
      expect(authState.isAuthenticated).toBe(false);
      expect(authState.tokens).toBeNull();
      expect(authState.user).toBeNull();
    });
  });

  describe('AuthGuard Integration', () => {
    const ProtectedComponent = () => <div>Protected Content</div>;

    it('should allow access for authenticated users', async () => {
      // Setup authenticated state
      act(() => {
        useAuthStore.getState().setTokens({
          access_token: 'valid-token',
          refresh_token: 'valid-refresh',
          token_type: 'bearer',
        });
        useAuthStore.getState().setUser({
          id: 'user-123',
          email: 'test@example.com',
          is_active: true,
          permissions: ['read'],
          role: 'user',
          created_at: '2024-01-01T00:00:00Z',
        });
      });

      // Mock successful auth check
      server.use(
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json({
            id: 'user-123',
            email: 'test@example.com',
            is_active: true,
            permissions: ['read'],
            role: 'user',
            created_at: '2024-01-01T00:00:00Z',
          });
        }),
      );

      render(
        <TestWrapper>
          <AuthGuard requireAuth={true}>
            <ProtectedComponent />
          </AuthGuard>
        </TestWrapper>
      );

      // Should show protected content
      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });
    });

    it('should redirect unauthenticated users to login', async () => {
      // Ensure no authentication
      act(() => {
        useAuthStore.getState().logout();
      });

      render(
        <TestWrapper>
          <AuthGuard requireAuth={true}>
            <ProtectedComponent />
          </AuthGuard>
        </TestWrapper>
      );

      // Should redirect to login
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/auth/login?redirect=%2F');
      });

      // Should not show protected content
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('Session Persistence', () => {
    it('should restore authentication state from localStorage', async () => {
      // Simulate stored auth data
      const storedAuth = {
        state: {
          user: {
            id: 'user-123',
            email: 'test@example.com',
            is_active: true,
            permissions: ['read'],
            role: 'user',
            created_at: '2024-01-01T00:00:00Z',
          },
          tokens: {
            access_token: 'stored-token',
            refresh_token: 'stored-refresh-token',
            token_type: 'bearer',
          },
          isAuthenticated: true,
        },
        version: 0,
      };

      localStorage.setItem('auth-storage', JSON.stringify(storedAuth));

      // Mock successful auth check
      server.use(
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json({
            id: 'user-123',
            email: 'test@example.com',
            is_active: true,
            permissions: ['read'],
            role: 'user',
            created_at: '2024-01-01T00:00:00Z',
          });
        }),
      );

      // Initialize the auth store (simulating app startup)
      await act(async () => {
        await useAuthStore.getState().initialize();
      });

      // Verify authentication state was restored
      const authState = useAuthStore.getState();
      expect(authState.isAuthenticated).toBe(true);
      expect(authState.user?.email).toBe('test@example.com');
      expect(authState.tokens?.access_token).toBe('stored-token');
    });
  });

  describe('Logout Flow', () => {
    it('should handle logout and cleanup', async () => {
      // Setup authenticated state
      act(() => {
        useAuthStore.getState().setTokens({
          access_token: 'valid-token',
          refresh_token: 'valid-refresh',
          token_type: 'bearer',
        });
        useAuthStore.getState().setUser({
          id: 'user-123',
          email: 'test@example.com',
          is_active: true,
          permissions: ['read'],
          role: 'user',
          created_at: '2024-01-01T00:00:00Z',
        });
      });

      // Mock logout endpoint
      server.use(
        http.post('http://localhost:8000/api/v1/auth/logout', () => {
          return HttpResponse.json({ message: 'Logged out successfully' });
        }),
      );

      // Trigger logout
      act(() => {
        useAuthStore.getState().logout();
      });

      // Verify complete cleanup
      const authState = useAuthStore.getState();
      expect(authState.isAuthenticated).toBe(false);
      expect(authState.tokens).toBeNull();
      expect(authState.user).toBeNull();
      expect(authState.error).toBeNull();
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors gracefully', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.error();
        }),
      );

      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      );

      // Fill and submit form
      fireEvent.change(screen.getByLabelText('Email'), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByLabelText('Password'), {
        target: { value: 'password123' },
      });

      const submitButton = screen.getByRole('button', { name: /login/i });
      fireEvent.click(submitButton);

      // Should show error and not redirect
      await waitFor(() => {
        expect(useAuthStore.getState().error).toBeTruthy();
      });

      expect(mockPush).not.toHaveBeenCalled();
    });

    it('should handle validation errors properly', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json(
            {
              detail: [
                { loc: ['body', 'email'], msg: 'field required', type: 'value_error.missing' },
              ],
            },
            { status: 422 }
          );
        }),
      );

      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      );

      // Submit form with empty email
      fireEvent.change(screen.getByLabelText('Password'), {
        target: { value: 'password123' },
      });

      const submitButton = screen.getByRole('button', { name: /login/i });
      fireEvent.click(submitButton);

      // Should handle validation error
      await waitFor(() => {
        expect(useAuthStore.getState().error).toBeTruthy();
      });

      expect(mockPush).not.toHaveBeenCalled();
    });
  });

  describe('Token Security', () => {
    it('should store tokens securely and not expose them in logs', async () => {
      const consoleSpy = vi.spyOn(console, 'log');
      const consoleErrorSpy = vi.spyOn(console, 'error');

      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json({
            access_token: 'secret-access-token-12345',
            refresh_token: 'secret-refresh-token-67890',
            token_type: 'bearer',
          });
        }),
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json({
            id: 'user-123',
            email: 'test@example.com',
            is_active: true,
            permissions: ['read'],
            role: 'user',
            created_at: '2024-01-01T00:00:00Z',
          });
        }),
      );

      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      );

      // Perform login
      fireEvent.change(screen.getByLabelText('Email'), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByLabelText('Password'), {
        target: { value: 'password123' },
      });

      fireEvent.click(screen.getByRole('button', { name: /login/i }));

      await waitFor(() => {
        expect(useAuthStore.getState().isAuthenticated).toBe(true);
      });

      // Verify tokens are not logged to console
      const allConsoleCalls = [
        ...consoleSpy.mock.calls.flat(),
        ...consoleErrorSpy.mock.calls.flat(),
      ];
      
      const hasTokenInLogs = allConsoleCalls.some(call => 
        typeof call === 'string' && call.includes('secret-access-token')
      );
      
      expect(hasTokenInLogs).toBe(false);

      consoleSpy.mockRestore();
      consoleErrorSpy.mockRestore();
    });
  });
});