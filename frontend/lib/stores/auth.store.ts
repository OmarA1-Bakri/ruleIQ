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
  tokens: { access: string | null; refresh: string | null };
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  sessionExpiry: string | null;
  accessToken: string | null;
  refreshTokenValue: string | null;
  permissions: string[];
  role: string | null;

  // Actions
  login: (params: { email: string; password: string; rememberMe?: boolean }) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshTokens: () => Promise<void>;
  refreshToken: () => Promise<void>; // Alias for test compatibility
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
  hasPermission: (permission: string) => boolean;
  hasRole: (role: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasAllPermissions: (permissions: string[]) => boolean;
}

interface _AuthStateInternal {
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
  tokens: { access: null, refresh: null },
      isAuthenticated: false,
      isLoading: false,
      error: null,
      sessionExpiry: null,
      accessToken: null,
      refreshTokenValue: null,
      permissions: [],
      role: null,

      // Actions
      login: async ({ email, password, rememberMe = false }) => {
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

          // Extract permissions and role from user if available
          const permissions = (user as { permissions?: string[] }).permissions || [];
          const role = (user as { role?: string }).role || null;

          set({
            user,
            tokens: { access: tokens.access_token, refresh: tokens.refresh_token },
            isAuthenticated: true,
            isLoading: false,
            error: null,
            accessToken: tokens.access_token,
            refreshTokenValue: tokens.refresh_token,
            permissions,
            role,
            sessionExpiry: rememberMe ? new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString() : null,
          });
        } catch (error) {
          set({
            user: null,
            tokens: { access: null, refresh: null },
            isAuthenticated: false,
            isLoading: false,
            error: error instanceof Error ? error.message : 'Login failed',
            accessToken: null,
            refreshTokenValue: null,
            permissions: [],
            role: null,
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

          const { user, tokens: responseTokens } = await registerResponse.json();

          set({
            user,
            tokens: { 
              access: responseTokens?.access_token || responseTokens?.access || null, 
              refresh: responseTokens?.refresh_token || responseTokens?.refresh || null 
            },
            isAuthenticated: true,
            isLoading: false,
            error: null,
            accessToken: responseTokens?.access_token || responseTokens?.access || null,
            refreshTokenValue: responseTokens?.refresh_token || responseTokens?.refresh || null,
            permissions: (user as { permissions?: string[] }).permissions || [],
            role: (user as { role?: string }).role || null,
          });
        } catch (error) {
          set({
            user: null,
            tokens: { access: null, refresh: null },
            isAuthenticated: false,
            isLoading: false,
            error: error instanceof Error ? error.message : 'Registration failed',
            accessToken: null,
            refreshTokenValue: null,
            permissions: [],
            role: null,
          });
          throw error;
        }
      },

      logout: async () => {
        const { tokens } = get();

        // Call logout endpoint if we have a token
        if (tokens?.access) {
          try {
            await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${tokens.access}`,
              },
              body: JSON.stringify({ refresh_token: tokens.refresh }),
            });
          } catch {
            // Ignore errors on logout
          }
        }

        set({
          user: null,
          tokens: { access: null, refresh: null },
          isAuthenticated: false,
          error: null,
          accessToken: null,
          refreshTokenValue: null,
          permissions: [],
          role: null,
          sessionExpiry: null,
        });
      },

      refreshTokens: async () => {
        const { tokens } = get();

        if (!tokens?.refresh) {
          throw new Error('No refresh token available');
        }

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ refresh_token: tokens.refresh }),
          });

          if (!response.ok) {
            throw new Error('Token refresh failed');
          }

          const newTokens: AuthTokens = await response.json();

          set({
            tokens: { access: newTokens.access_token, refresh: newTokens.refresh_token },
            accessToken: newTokens.access_token,
            refreshTokenValue: newTokens.refresh_token,
            error: null,
          });
        } catch (error) {
          // If refresh fails, logout the user
          await get().logout();
          throw error;
        }
      },

      setUser: (user: User) => {
        set({ user });
      },

      setTokens: (tokens: AuthTokens) => {
        set({ 
          tokens: { access: tokens.access_token, refresh: tokens.refresh_token },
          accessToken: tokens.access_token,
          refreshTokenValue: tokens.refresh_token,
          isAuthenticated: true 
        });
      },

      clearError: () => {
        set({ error: null });
      },

      checkAuthStatus: async () => {
        const { tokens } = get();

        if (!tokens?.access) {
          set({ isAuthenticated: false, user: null });
          return;
        }

        try {
          const fetchCurrentUser = async (accessToken: string) =>
            fetch(`${API_BASE_URL}/api/v1/auth/me`, {
              headers: {
                Authorization: `Bearer ${accessToken}`,
              },
            });

          let response = await fetchCurrentUser(tokens.access);

          if (!response.ok) {
            await get().refreshTokens();
            const refreshedAccessToken = get().tokens?.access;

            if (!refreshedAccessToken) {
              throw new Error('Token refresh failed');
            }

            response = await fetchCurrentUser(refreshedAccessToken);

            if (!response.ok) {
              throw new Error('Failed to fetch user after token refresh');
            }
          }

          const user: User = await response.json();
          set({ user, isAuthenticated: true });
        } catch (_error) {
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
        return get().tokens?.access || null;
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
        } catch (error) {
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
        } catch (error) {
          throw error;
        }
      },

      updateProfile: async (data: Partial<User>) => {
        const { tokens } = get();

        if (!tokens?.access) {
          throw new Error('Not authenticated');
        }

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/profile`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${tokens.access}`,
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
        } catch (error) {
          throw error;
        }
      },

      changePassword: async (currentPassword: string, newPassword: string) => {
        const { tokens } = get();

        if (!tokens?.access) {
          throw new Error('Not authenticated');
        }

        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/change-password`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${tokens.access}`,
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
        } catch (error) {
          throw error;
        }
      },


      // Permission and role checking methods
      hasPermission: (permission: string) => {
        const { permissions } = get();
        return permissions.includes(permission);
      },

      hasRole: (role: string) => {
        const state = get();
        return state.role === role;
      },

      hasAnyPermission: (permissions: string[]) => {
        const { permissions: userPermissions } = get();
        return permissions.some(p => userPermissions.includes(p));
      },

      hasAllPermissions: (permissions: string[]) => {
        const { permissions: userPermissions } = get();
        return permissions.every(p => userPermissions.includes(p));
      },

      // Alias for refreshTokens to match test expectations
      refreshToken: async () => {
        return get().refreshTokens();
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
