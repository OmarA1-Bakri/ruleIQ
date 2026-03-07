import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// Mock next/navigation
const mockPush = vi.fn();
const mockReplace = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => ({
    get: vi.fn(),
  }),
  usePathname: () => '/dashboard',
}));

// Mock the auth store
let mockAuthState = {
  isAuthenticated: false,
  isLoading: false,
  checkAuthStatus: vi.fn(),
  user: null,
};

vi.mock('@/lib/stores/auth.store', () => ({
  useAuthStore: () => mockAuthState,
}));

// Import component after mocks
import { AuthGuard } from '@/components/auth/auth-guard';

describe('AuthGuard Component - Route Protection', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();

    // Reset auth state
    mockAuthState = {
      isAuthenticated: false,
      isLoading: false,
      checkAuthStatus: vi.fn().mockResolvedValue(undefined),
      user: null,
    };

    // Mock window.location.pathname
    Object.defineProperty(window, 'location', {
      value: {
        pathname: '/dashboard',
        search: '',
        hash: '',
        href: 'http://localhost:3000/dashboard',
      },
      writable: true,
    });
  });

  afterEach(() => {
    queryClient.clear();
  });

  const TestWrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  describe('Unauthenticated User Redirection', () => {
    it('should redirect unauthenticated users to login page', async () => {
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = false;

      render(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/auth/login?redirect=%2Fdashboard');
      });

      // Should not render protected content
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    });

    it('should preserve return URL for redirect after login', async () => {
      // Simulate being on a specific dashboard page
      Object.defineProperty(window, 'location', {
        value: {
          pathname: '/dashboard/assessments/123',
          search: '?tab=details',
          hash: '#section1',
          href: 'http://localhost:3000/dashboard/assessments/123?tab=details#section1',
        },
        writable: true,
      });

      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = false;

      render(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith(
          '/auth/login?redirect=%2Fdashboard%2Fassessments%2F123',
        );
      });
    });

    it('should use custom redirect URL when provided', async () => {
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = false;

      render(
        <TestWrapper>
          <AuthGuard redirectTo="/custom-login">
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/custom-login?redirect=%2Fdashboard');
      });
    });
  });

  describe('Authenticated User Access', () => {
    it('should render protected content for authenticated users', async () => {
      mockAuthState.isAuthenticated = true;
      mockAuthState.isLoading = false;
      mockAuthState.user = {
        id: 'user-123',
        email: 'test@example.com',
        is_active: true,
      };

      render(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByTestId('protected-content')).toBeInTheDocument();
      });

      // Should not redirect
      expect(mockPush).not.toHaveBeenCalled();
    });

    it('should call checkAuthStatus on mount', async () => {
      const mockCheckAuthStatus = vi.fn().mockResolvedValue(undefined);
      mockAuthState.checkAuthStatus = mockCheckAuthStatus;
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = false;

      render(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(mockCheckAuthStatus).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('Loading States', () => {
    it('should show loading fallback while checking authentication', async () => {
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = true;

      render(
        <TestWrapper>
          <AuthGuard fallback={<div data-testid="loading">Checking auth...</div>}>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      expect(screen.getByTestId('loading')).toBeInTheDocument();
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();

      // Should not redirect while loading
      expect(mockPush).not.toHaveBeenCalled();
    });

    it('should show default loading fallback when none provided', async () => {
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = true;

      render(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('should show loading fallback while auth check is in progress', async () => {
      // Use a never-resolving promise so isCheckingAuth stays true throughout the assertion
      const mockCheckAuthStatus = vi.fn().mockImplementation(() => new Promise(() => {}));
      mockAuthState.checkAuthStatus = mockCheckAuthStatus;
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = false;

      render(
        <TestWrapper>
          <AuthGuard fallback={<div data-testid="checking">Checking...</div>}>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      // The effect runs asynchronously — wait for it to set isCheckingAuth=true
      await waitFor(() => {
        expect(screen.getByTestId('checking')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    // Vitest v3 + React 19 dev mode: async useEffect that throws internally gets
    // re-reported as an unhandled rejection at the process level by React's
    // commitHookEffectListMount, even when the component's try/finally handles it.
    // We install a process-level unhandledRejection listener to suppress the
    // specific expected error for this describe block only.
    let unhandledRejectionHandler: (reason: unknown) => void;

    beforeEach(() => {
      unhandledRejectionHandler = (reason: unknown) => {
        if (reason instanceof Error && reason.message === 'Auth check failed') {
          // Intentionally swallow — the component handles this in try/finally
          return;
        }
      };
      process.on('unhandledRejection', unhandledRejectionHandler);
    });

    afterEach(() => {
      process.off('unhandledRejection', unhandledRejectionHandler);
    });

    it('should handle checkAuthStatus errors gracefully', async () => {
      const mockCheckAuthStatus = vi.fn().mockImplementation(async () => {
        throw new Error('Auth check failed');
      });
      mockAuthState.checkAuthStatus = mockCheckAuthStatus;
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = false;

      render(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      // Wait for auth check to complete (and fail)
      await waitFor(() => {
        expect(mockCheckAuthStatus).toHaveBeenCalled();
      });

      // Should still redirect to login even if auth check fails
      await waitFor(
        () => {
          expect(mockPush).toHaveBeenCalledWith('/auth/login?redirect=%2Fdashboard');
        },
        { timeout: 2000 },
      );
    });
  });

  describe('Dashboard Route Protection Integration', () => {
    it('should protect dashboard routes from 404 errors', async () => {
      // Simulate navigation to dashboard while unauthenticated
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = false;

      render(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="dashboard-content">
              <h1>Dashboard</h1>
              <nav>
                <a href="/dashboard/assessments">Assessments</a>
                <a href="/dashboard/evidence">Evidence</a>
              </nav>
            </div>
          </AuthGuard>
        </TestWrapper>,
      );

      // Should redirect before rendering dashboard content
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/auth/login?redirect=%2Fdashboard');
      });

      // Dashboard content should not be rendered
      expect(screen.queryByTestId('dashboard-content')).not.toBeInTheDocument();
    });

    it('should handle nested dashboard routes correctly', async () => {
      Object.defineProperty(window, 'location', {
        value: {
          pathname: '/dashboard/assessments',
          search: '',
          hash: '',
          href: 'http://localhost:3000/dashboard/assessments',
        },
        writable: true,
      });

      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = false;

      render(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="assessments-page">Assessments Page</div>
          </AuthGuard>
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/auth/login?redirect=%2Fdashboard%2Fassessments');
      });
    });
  });

  describe('Authentication State Transitions', () => {
    it('should handle transition from loading to authenticated', async () => {
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = true;

      const { rerender } = render(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      expect(screen.getByText('Loading...')).toBeInTheDocument();

      // Simulate authentication success
      mockAuthState.isAuthenticated = true;
      mockAuthState.isLoading = false;
      mockAuthState.user = { id: 'user-123', email: 'test@example.com' };

      rerender(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByTestId('protected-content')).toBeInTheDocument();
      });
    });

    it('should handle transition from loading to unauthenticated', async () => {
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = true;

      const { rerender } = render(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      expect(screen.getByText('Loading...')).toBeInTheDocument();

      // Simulate authentication failure
      mockAuthState.isAuthenticated = false;
      mockAuthState.isLoading = false;

      rerender(
        <TestWrapper>
          <AuthGuard>
            <div data-testid="protected-content">Protected Content</div>
          </AuthGuard>
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/auth/login?redirect=%2Fdashboard');
      });
    });
  });
});
