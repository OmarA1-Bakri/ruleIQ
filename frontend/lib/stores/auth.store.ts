import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/types/auth';

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface AuthState {
  // State
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  setUser: (user: User) => void;
  setTokens: (tokens: AuthTokens) => void;
  clearError: () => void;
  checkAuthStatus: () => Promise<void>;
  initialize: () => Promise<void>;
  getCurrentUser: () => User | null;
  getToken: () => string | null;
  requestPasswordReset: (email: string) => Promise<void>;
  resetPassword: (token: string, password: string) => Promise<void>;
  verifyEmail: (token: string) => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<User>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
}

interface AuthStateInternal {
  // State
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  setUser: (user: User) => void;
  setTokens: (tokens: AuthTokens) => void;
  clearError: () => void;
  checkAuthStatus: () => Promise<void>;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Actions
      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          // Login request
          const loginResponse = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
          });

          if (!loginResponse || !loginResponse.ok) {
            const errorData = await loginResponse.json();
            throw new Error(errorData.detail || 'Login failed');
          }

          const tokens: AuthTokens = await loginResponse.json();

          // Get user info
          const userResponse = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
            headers: {
              Authorization: `Bearer ${tokens.access_token}`,
            },
          });

          if (!userResponse.ok) {
            throw new Error('Failed to get user information');
          }

          const user: User = await userResponse.json();

          set({
            user,
            tokens,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch {
          set({
            user: null,
            tokens: null,
            isAuthenticated: false,
            isLoading: false,
            error: error instanceof Error ? error.message : 'Login failed',
          });
          throw error;
        }
      },

      register: async (email: string, password: string, _fullName?: string) => {
        set({ isLoading: true, error: null });

        try {
          // Register request - backend only accepts email and password
          const registerResponse = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
          });

          if (!registerResponse || !registerResponse.ok) {
            const errorData = await registerResponse
              .json()
              .catch(() => ({ detail: 'Registration failed' }));
            const errorMessage =
              typeof errorData.detail === 'string'
                ? errorData.detail
                : Array.isArray(errorData.detail)
                  ? errorData.detail
                      .map((err: any) =>
                        typeof err === 'string' ? err : err.msg || 'Validation error',
                      )
                      .join(', ')
                  : 'Registration failed';
            throw new Error(errorMessage);
          }

          const { user, tokens } = await registerResponse.json();

          set({
            user,
            tokens,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch {
          set({
            user: null,
            tokens: null,
            isAuthenticated: false,
            isLoading: false,
            error: error instanceof Error ? error.message : 'Registration failed',
          });
          throw error;
        }
      },

      logout: () => {
        const { tokens } = get();

        // Call logout endpoint if we have a token
        if (tokens?.access_token) {
          fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${tokens.access_token}`,
            },
          }).catch(() => {
            // Ignore errors on logout
          });
        }

        set({
          user: null,
          tokens: null,
          isAuthenticated: false,
          error: null,
        });
      },

      refreshToken: async () => {
        const { tokens } = get();

        if (!tokens?.refresh_token) {
          throw new Error('No refresh token available');
        }

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ refresh_token: tokens.refresh_token }),
          });

          if (!response.ok) {
            throw new Error('Token refresh failed');
          }

          const newTokens: AuthTokens = await response.json();

          set({
            tokens: newTokens,
            error: null,
          });
        } catch {
          // If refresh fails, logout the user
          get().logout();
          throw error;
        }
      },

      setUser: (user: User) => {
        set({ user });
      },

      setTokens: (tokens: AuthTokens) => {
        set({ tokens, isAuthenticated: true });
      },

      clearError: () => {
        set({ error: null });
      },

      checkAuthStatus: async () => {
        const { tokens } = get();

        if (!tokens?.access_token) {
          set({ isAuthenticated: false, user: null });
          return;
        }

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
            headers: {
              Authorization: `Bearer ${tokens.access_token}`,
            },
          });

          if (!response.ok) {
            // Try to refresh token
            await get().refreshToken();
            return;
          }

          const user: User = await response.json();
          set({ user, isAuthenticated: true });
        } catch {
          // If all fails, logout
          get().logout();
        }
      },

      initialize: async () => {
        await get().checkAuthStatus();
      },

      getCurrentUser: () => {
        return get().user;
      },

      getToken: () => {
        return get().tokens?.access_token || null;
      },

      requestPasswordReset: async (email: string) => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/forgot-password`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email }),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Password reset request failed');
          }
        } catch (error) {
          // TODO: Replace with proper logging

          // // TODO: Replace with proper logging
          throw error;
        }
      },

      resetPassword: async (token: string, password: string) => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/reset-password`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ token, password }),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Password reset failed');
          }
        } catch {
          throw error;
        }
      },

      verifyEmail: async (token: string) => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/verify-email`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ token }),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Email verification failed');
          }
        } catch {
          throw error;
        }
      },

      updateProfile: async (data: Partial<User>) => {
        const { tokens } = get();

        if (!tokens?.access_token) {
          throw new Error('Not authenticated');
        }

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/profile`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${tokens.access_token}`,
            },
            body: JSON.stringify(data),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Profile update failed');
          }

          const updatedUser: User = await response.json();

          // Validate the response structure
          if (
            !updatedUser ||
            typeof updatedUser.id !== 'string' ||
            typeof updatedUser.email !== 'string' ||
            typeof updatedUser.isActive !== 'boolean' ||
            typeof updatedUser.createdAt !== 'string'
          ) {
            throw new Error('Invalid user data received from server');
          }

          set({ user: updatedUser });

          return updatedUser;
        } catch {
          throw error;
        }
      },

      changePassword: async (currentPassword: string, newPassword: string) => {
        const { tokens } = get();

        if (!tokens?.access_token) {
          throw new Error('Not authenticated');
        }

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/change-password`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${tokens.access_token}`,
            },
            body: JSON.stringify({
              current_password: currentPassword,
              new_password: newPassword,
            }),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Password change failed');
          }
        } catch {
          throw error;
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
