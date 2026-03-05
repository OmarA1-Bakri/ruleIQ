import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import { QueryClient } from '@tanstack/react-query';

// Create a client with proper defaults
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 24 hours for background refetch
      gcTime: 1000 * 60 * 60 * 24,

      // Consider data stale after 5 minutes
      staleTime: 1000 * 60 * 5,

      // Retry failed requests 3 times with exponential backoff
      retry: (failureCount, error: unknown) => {
        // Don't retry on 4xx errors (client errors)
        if (
          error &&
          typeof error === 'object' &&
          'response' in error &&
          error.response &&
          typeof error.response === 'object' &&
          'status' in error.response &&
          typeof (error.response as any).status === 'number' &&
          (error.response as any).status >= 400 &&
          (error.response as any).status < 500
        ) {
          return false;
        }
        return failureCount < 3;
      },

      // Exponential backoff delay
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

      // Refetch on window focus for fresh data
      refetchOnWindowFocus: true,

      // Don't refetch on reconnect by default (can be overridden per query)
      refetchOnReconnect: 'always',
    },
    mutations: {
      // Retry mutations once on failure
      retry: 1,

      // Show error notifications by default
      onError: (_error: unknown) => {
        // TODO: Integrate with toast notification system
      },
    },
  },
});

// Safe storage wrapper that handles unavailable storage
const safeStorage = {
  getItem: (key: string): string | null => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        return window.localStorage.getItem(key);
      }
    } catch (_error) {
    }
    return null;
  },
  setItem: (key: string, value: string): void => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(key, value);
      }
    } catch (_error) {
    }
  },
  removeItem: (key: string): void => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.removeItem(key);
      }
    } catch (_error) {
    }
  },
};

// Create a persister for offline support with safe storage
const _persister = createSyncStoragePersister({
  storage: safeStorage,
  key: 'ruleiq-query-cache',
  throttleTime: 1000,
});

// Persist the query client only in client-side environment
// Note: persistQueryClient is not available in the current version
// NOTE: Implementation pending persistence when upgrading to a version that supports it
/*
if (typeof window !== 'undefined') {
  try {
    // persistQueryClient({
    //   queryClient,
    //   persister,
    //   maxAge: 1000 * 60 * 60 * 24, // 24 hours
    // });
  } catch (error) {
  }
}
*/

// Helper function to invalidate queries by key pattern
export const invalidateQueries = (patterns: string[]) => {
  patterns.forEach((pattern) => {
    queryClient.invalidateQueries({ queryKey: [pattern] });
  });
};

// Helper function to clear all cache
export const clearQueryCache = () => {
  queryClient.clear();
};

// Helper function to prefetch data
export const prefetchQuery = async (key: string[], fetcher: () => Promise<any>) => {
  await queryClient.prefetchQuery({
    queryKey: key,
    queryFn: fetcher,
  });
};
