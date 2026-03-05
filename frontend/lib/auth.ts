/**
 * Auth module stub for layout persistence and other consumers.
 * Re-exports auth functionality from the auth store.
 */

import { useAuthStore } from '@/lib/stores/auth.store';

/**
 * Hook providing auth state for components that need user info.
 * Wraps the Zustand auth store for convenience.
 */
export function useAuth() {
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const getToken = useAuthStore((state) => state.getToken);

  return {
    user,
    isAuthenticated,
    getToken,
  };
}
