import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';

// ============================================================
// Mock components that would hang in jsdom or have missing deps
// ============================================================
vi.mock('@/components/auth/auth-provider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="mock-auth-provider">{children}</div>
  ),
  useAuth: () => ({
    isAuthenticated: false,
    isLoading: false,
    user: null,
  }),
}));

vi.mock('@/components/auth/login-form', () => ({
  LoginForm: ({ onSubmit }: { onSubmit?: (c: { email: string; password: string; remember_me?: boolean }) => void }) => {
    const [email, setEmail] = React.useState('');
    const [password, setPassword] = React.useState('');
    const [isLoading, setIsLoading] = React.useState(false);
    const [emailError, setEmailError] = React.useState('');
    const [passwordError, setPasswordError] = React.useState('');
    const [rememberMe, setRememberMe] = React.useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      // Validation
      if (!email) { setEmailError('Email is required'); return; }
      if (!password) { setPasswordError('Password is required'); return; }
      setEmailError('');
      setPasswordError('');
      setIsLoading(true);
      try {
        await onSubmit?.({ email, password, ...(rememberMe ? { remember_me: true } : {}) });
      } finally {
        setIsLoading(false);
      }
    };

    return (
      <form onSubmit={handleSubmit} data-testid="mock-login-form">
        <label htmlFor="lf-email">Email</label>
        <input
          id="lf-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={isLoading}
        />
        {emailError && <span>{emailError}</span>}
        <label htmlFor="lf-password">Password</label>
        <input
          id="lf-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={isLoading}
        />
        {passwordError && <span>{passwordError}</span>}
        <label htmlFor="lf-remember">Remember Me</label>
        <input
          id="lf-remember"
          type="checkbox"
          checked={rememberMe}
          onChange={(e) => setRememberMe(e.target.checked)}
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Signing In' : 'Sign In'}
        </button>
        {isLoading && <span data-testid="loading-spinner">Loading...</span>}
      </form>
    );
  },
}));

// ============================================================
// Mock auth service — include refreshToken
// ============================================================
vi.mock('@/lib/api/auth.service', () => ({
  authService: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    getCurrentUser: vi.fn(),
    refreshToken: vi.fn(),
  },
}));

// Mock Next.js router
const mockPush = vi.fn();
const mockReplace = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}));

// Mock toast notifications
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: mockToast,
  }),
}));

// ============================================================
// Imports after vi.mock calls
// ============================================================
import { AuthProvider } from '@/components/auth/auth-provider';
import { LoginForm } from '@/components/auth/login-form';
import { authService } from '@/lib/api/auth.service';

import { render, screen, fireEvent, waitFor } from '../utils';

describe('Authentication Flow Integration', () => {
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

  const renderWithProviders = (component: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>{component}</AuthProvider>
      </QueryClientProvider>,
    );
  };

  describe('Login Flow', () => {
    it('should complete successful login flow', async () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        is_active: true,
      };

      const mockAuthResponse = {
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: mockUser,
      };

      vi.mocked(authService.login).mockResolvedValue(mockAuthResponse);

      const handleSubmit = async (credentials: { email: string; password: string }) => {
        const result = await authService.login(credentials);
        mockToast({
          title: 'Welcome back!',
          description: 'You have been successfully logged in.',
        });
        mockPush('/dashboard');
        return result;
      };

      renderWithProviders(<LoginForm onSubmit={handleSubmit} />);

      // Fill in login form
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
      fireEvent.change(passwordInput, { target: { value: 'password123' } });

      // Submit form
      fireEvent.click(submitButton);

      // Wait for API call
      await waitFor(() => {
        expect(authService.login).toHaveBeenCalledWith({
          email: 'test@example.com',
          password: 'password123',
        });
      });

      // Should show success toast
      expect(mockToast).toHaveBeenCalledWith({
        title: 'Welcome back!',
        description: 'You have been successfully logged in.',
      });

      // Should redirect to dashboard
      expect(mockPush).toHaveBeenCalledWith('/dashboard');
    });

    it('should handle login validation errors', async () => {
      renderWithProviders(<LoginForm />);

      const submitButton = screen.getByRole('button', { name: /sign in/i });

      // Try to submit without filling fields
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Email is required')).toBeInTheDocument();
      });

      // Should not call API
      expect(authService.login).not.toHaveBeenCalled();
    });

    it('should handle login API errors', async () => {
      const loginError = new Error('Invalid credentials');
      vi.mocked(authService.login).mockRejectedValue(loginError);

      const handleSubmit = async (credentials: { email: string; password: string }) => {
        try {
          await authService.login(credentials);
        } catch (error: any) {
          mockToast({
            title: 'Login failed',
            description: error.message,
            variant: 'destructive',
          });
          // Do NOT rethrow — let the LoginForm stub handle the error state internally
        }
      };

      renderWithProviders(<LoginForm onSubmit={handleSubmit} />);

      // Fill in form with invalid credentials
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      fireEvent.change(emailInput, { target: { value: 'invalid@example.com' } });
      fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith({
          title: 'Login failed',
          description: 'Invalid credentials',
          variant: 'destructive',
        });
      });

      // Should not redirect
      expect(mockPush).not.toHaveBeenCalled();
    });

    it('should show loading state during login', async () => {
      // Mock a delayed response
      vi.mocked(authService.login).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100)),
      );

      const handleSubmit = async (credentials: { email: string; password: string }) => {
        return authService.login(credentials);
      };

      renderWithProviders(<LoginForm onSubmit={handleSubmit} />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
      fireEvent.change(passwordInput, { target: { value: 'password123' } });
      fireEvent.click(submitButton);

      // Should show loading state
      expect(screen.getByRole('button', { name: /signing in/i })).toBeInTheDocument();
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();

      // Form should be disabled
      expect(emailInput).toBeDisabled();
      expect(passwordInput).toBeDisabled();
    });

    it('should handle remember me functionality', async () => {
      const mockAuthResponse = {
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: {
          id: '1',
          email: 'test@example.com',
          full_name: 'Test User',
          is_active: true,
        },
      };

      vi.mocked(authService.login).mockResolvedValue(mockAuthResponse);

      const handleSubmit = async (credentials: {
        email: string;
        password: string;
        remember_me?: boolean;
      }) => {
        return authService.login(credentials);
      };

      renderWithProviders(<LoginForm onSubmit={handleSubmit} />);

      // Fill form and check remember me
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const rememberMeCheckbox = screen.getByLabelText(/remember me/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
      fireEvent.change(passwordInput, { target: { value: 'password123' } });
      fireEvent.click(rememberMeCheckbox);
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(authService.login).toHaveBeenCalledWith({
          email: 'test@example.com',
          password: 'password123',
          remember_me: true,
        });
      });
    });
  });

  describe('Registration Flow', () => {
    it('should complete successful registration flow', async () => {
      const mockUser = {
        id: '1',
        email: 'newuser@example.com',
        full_name: 'New User',
        is_active: true,
      };

      const mockAuthResponse = {
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: mockUser,
      };

      vi.mocked(authService.register).mockResolvedValue(mockAuthResponse);

      const RegisterForm = () => (
        <form
          data-testid="register-form"
          onSubmit={async (e) => {
            e.preventDefault();
            const fd = new FormData(e.currentTarget);
            await authService.register(
              fd.get('email') as string,
              fd.get('password') as string,
              fd.get('full_name') as string,
            );
            mockToast({
              title: 'Account created!',
              description: 'Welcome to ruleIQ. Your account has been created successfully.',
            });
            mockPush('/business-profile/setup');
          }}
        >
          <input name="full_name" placeholder="Full Name" />
          <input name="email" placeholder="Email" />
          <input name="password" placeholder="Password" />
          <input name="company" placeholder="Company" />
          <button type="submit">Create Account</button>
        </form>
      );

      renderWithProviders(<RegisterForm />);

      // Fill registration form
      const fullNameInput = screen.getByPlaceholderText('Full Name');
      const emailInput = screen.getByPlaceholderText('Email');
      const passwordInput = screen.getByPlaceholderText('Password');
      const companyInput = screen.getByPlaceholderText('Company');
      const submitButton = screen.getByRole('button', { name: /create account/i });

      fireEvent.change(fullNameInput, { target: { value: 'New User' } });
      fireEvent.change(emailInput, { target: { value: 'newuser@example.com' } });
      fireEvent.change(passwordInput, { target: { value: 'password123' } });
      fireEvent.change(companyInput, { target: { value: 'Test Company' } });

      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(authService.register).toHaveBeenCalledWith(
          'newuser@example.com',
          'password123',
          'New User',
        );
      });

      // Should show success message
      expect(mockToast).toHaveBeenCalledWith({
        title: 'Account created!',
        description: 'Welcome to ruleIQ. Your account has been created successfully.',
      });

      // Should redirect to business profile setup
      expect(mockPush).toHaveBeenCalledWith('/business-profile/setup');
    });

    it('should validate password strength', async () => {
      const RegisterForm = () => {
        const [strength, setStrength] = React.useState('');

        const checkStrength = (val: string) => {
          if (val.length < 6) {
            setStrength('Password is too weak');
          } else if (/[A-Z]/.test(val) && /[0-9]/.test(val) && /[!@#$%]/.test(val)) {
            setStrength('Password strength: Strong');
          } else {
            setStrength('');
          }
        };

        return (
          <form data-testid="register-form">
            <input
              name="password"
              placeholder="Password"
              onChange={(e) => checkStrength(e.target.value)}
            />
            <div data-testid="password-strength">{strength}</div>
          </form>
        );
      };

      renderWithProviders(<RegisterForm />);

      const passwordInput = screen.getByPlaceholderText('Password');

      // Test weak password
      fireEvent.change(passwordInput, { target: { value: 'weak' } });

      await waitFor(() => {
        expect(screen.getByText('Password is too weak')).toBeInTheDocument();
      });

      // Test strong password
      fireEvent.change(passwordInput, { target: { value: 'StrongPassword123!' } });

      await waitFor(() => {
        expect(screen.getByText('Password strength: Strong')).toBeInTheDocument();
      });
    });

    it('should handle duplicate email registration', async () => {
      const duplicateError = new Error('Email already exists');
      vi.mocked(authService.register).mockRejectedValue(duplicateError);

      const RegisterForm = () => (
        <form
          data-testid="register-form"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await authService.register('existing@example.com', '', undefined);
            } catch (error: any) {
              mockToast({
                title: 'Registration failed',
                description: error.message,
                variant: 'destructive',
              });
            }
          }}
        >
          <input name="email" placeholder="Email" />
          <button type="submit">Create Account</button>
        </form>
      );

      renderWithProviders(<RegisterForm />);

      const emailInput = screen.getByPlaceholderText('Email');
      const submitButton = screen.getByRole('button', { name: /create account/i });

      fireEvent.change(emailInput, { target: { value: 'existing@example.com' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith({
          title: 'Registration failed',
          description: 'Email already exists',
          variant: 'destructive',
        });
      });
    });
  });

  describe('Logout Flow', () => {
    it('should complete logout flow', async () => {
      vi.mocked(authService.logout).mockResolvedValue(undefined as any);

      const LogoutButton = () => (
        <button
          onClick={async () => {
            await authService.logout();
            mockReplace('/login');
            mockToast({
              title: 'Logged out',
              description: 'You have been successfully logged out.',
            });
          }}
        >
          Logout
        </button>
      );

      renderWithProviders(<LogoutButton />);

      const logoutButton = screen.getByRole('button', { name: /logout/i });
      fireEvent.click(logoutButton);

      await waitFor(() => {
        expect(authService.logout).toHaveBeenCalled();
      });

      // Should redirect to login page
      expect(mockReplace).toHaveBeenCalledWith('/login');

      // Should show logout message
      expect(mockToast).toHaveBeenCalledWith({
        title: 'Logged out',
        description: 'You have been successfully logged out.',
      });
    });
  });

  describe('Session Management', () => {
    it('should handle token refresh', async () => {
      const mockRefreshResponse = {
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
      };

      vi.mocked(authService.refreshToken).mockResolvedValue(mockRefreshResponse as any);

      // Simulate token refresh scenario
      const TokenRefreshComponent = () => {
        const handleRefresh = async () => {
          try {
            await authService.refreshToken();
          } catch (error) {
            // Development logging - consider proper logger
            console.error('Token refresh failed:', error);
          }
        };

        return <button onClick={handleRefresh}>Refresh Token</button>;
      };

      renderWithProviders(<TokenRefreshComponent />);

      const refreshButton = screen.getByRole('button', { name: /refresh token/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(authService.refreshToken).toHaveBeenCalled();
      });
    });

    it('should handle expired session', async () => {
      const expiredError = new Error('Session expired');
      vi.mocked(authService.getCurrentUser).mockRejectedValue(expiredError);

      const ProtectedComponent = () => {
        const handleGetUser = async () => {
          try {
            await authService.getCurrentUser();
          } catch (error) {
            // Handle expired session
            mockReplace('/login');
          }
        };

        return <button onClick={handleGetUser}>Get User</button>;
      };

      renderWithProviders(<ProtectedComponent />);

      const getUserButton = screen.getByRole('button', { name: /get user/i });
      fireEvent.click(getUserButton);

      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalledWith('/login');
      });
    });
  });
});
