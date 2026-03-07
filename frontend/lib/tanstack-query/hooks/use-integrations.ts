import { useQuery } from '@tanstack/react-query';

import { integrationService } from '@/lib/api/integrations.service';

import {
  createQueryKey,
  type BaseQueryOptions,
  type PaginationParams,
  type PaginatedResponse,
} from './base';

// Import available types from @/types/api
import type { Integration } from '@/types/api';

// Define missing types locally
interface IntegrationLog {
  id: string;
  message: string;
  timestamp: string;
  [key: string]: any;
}

// Query keys
const INTEGRATION_KEY = 'integrations';

export const integrationKeys = {
  all: [INTEGRATION_KEY] as const,
  lists: () => [...integrationKeys.all, 'list'] as const,
  list: (params?: PaginationParams) => createQueryKey(INTEGRATION_KEY, 'list', params),
  details: () => [...integrationKeys.all, 'detail'] as const,
  detail: (id: string) => createQueryKey(INTEGRATION_KEY, 'detail', { id }),
  status: (id: string) => createQueryKey(INTEGRATION_KEY, 'status', { id }),
  logs: (id: string, params?: any) => createQueryKey(INTEGRATION_KEY, 'logs', { id, ...params }),
  providers: () => createQueryKey(INTEGRATION_KEY, 'providers'),
  provider: (providerId: string) => createQueryKey(INTEGRATION_KEY, 'provider', { providerId }),
  configs: (providerId: string) => createQueryKey(INTEGRATION_KEY, 'configs', { providerId }),
  syncHistory: (id: string) => createQueryKey(INTEGRATION_KEY, 'sync-history', { id }),
};

// Hook to fetch integrations list
export function useIntegrations(
  params?: PaginationParams & {
    provider?: string;
    status?: 'active' | 'inactive' | 'error';
    type?: string;
  },
  options?: BaseQueryOptions<PaginatedResponse<Integration>>,
) {
  return useQuery({
    queryKey: integrationKeys.list(params),
    queryFn: async () => {
      const integrations = await integrationService.getIntegrations();
      // Convert to PaginatedResponse format
      // TODO: Apply client-side filtering based on params
      return {
        items: integrations,
        total: integrations.length,
        page: params?.page || 1,
        page_size: params?.page_size || 20,
        total_pages: Math.ceil(integrations.length / (params?.page_size || 20)),
      } as PaginatedResponse<Integration>;
    },
    ...options,
  });
}

// Hook to fetch single integration
export function useIntegration(id: string, options?: BaseQueryOptions<Integration>) {
  return useQuery({
    queryKey: integrationKeys.detail(id),
    queryFn: async () => {
      // TODO: getIntegration method doesn't exist, using getIntegrations and filtering
      const integrations = await integrationService.getIntegrations();
      const integration = integrations.find((i) => i.id === id);
      if (!integration) {
        throw new Error(`Integration with id ${id} not found`);
      }
      return integration;
    },
    enabled: !!id,
    ...options,
  });
}

// Hook to fetch integration status
// TODO: getIntegrationStatus method doesn't exist in the service
// export function useIntegrationStatus(id: string, options?: BaseQueryOptions<IntegrationStatus>) {
//   return useQuery({
//     queryKey: integrationKeys.status(id),
//     queryFn: () => integrationService.getIntegrationStatus(id),
//     enabled: !!id,
//     refetchInterval: 30000, // Refresh every 30 seconds
//     ...options,
//   });
// }

// Hook to fetch integration logs
// TODO: getIntegrationLogs method exists but needs proper implementation
export function useIntegrationLogs(
  id: string,
  params?: {
    level?: 'info' | 'warning' | 'error';
    start_date?: string;
    end_date?: string;
    page?: number;
    page_size?: number;
  },
  options?: BaseQueryOptions<PaginatedResponse<IntegrationLog>>,
) {
  return useQuery({
    queryKey: integrationKeys.logs(id, params),
    queryFn: async () => {
      const response = await integrationService.getIntegrationLogs(id, params);
      // Convert to PaginatedResponse format
      return {
        items: response.logs.map((log: any) => ({
          id: log.timestamp,
          message: log.event_type,
          timestamp: log.timestamp,
          ...log,
        })),
        total: response.total,
        page: params?.page || 1,
        page_size: params?.page_size || 20,
        total_pages: Math.ceil(response.total / (params?.page_size || 20)),
      } as PaginatedResponse<IntegrationLog>;
    },
    enabled: !!id,
    ...options,
  });
}

// Hook to fetch available providers
// TODO: getProviders method doesn't exist in the service
// export function useIntegrationProviders(options?: BaseQueryOptions<IntegrationProvider[]>) {
//   return useQuery({
//     queryKey: integrationKeys.providers(),
//     queryFn: () => integrationService.getProviders(),
//     ...options,
//   });
// }

// Hook to fetch provider details
// TODO: getProvider method doesn't exist in the service
// export function useIntegrationProvider(
//   providerId: string,
//   options?: BaseQueryOptions<IntegrationProvider>,
// ) {
//   return useQuery({
//     queryKey: integrationKeys.provider(providerId),
//     queryFn: () => integrationService.getProvider(providerId),
//     enabled: !!providerId,
//     ...options,
//   });
// }

// Hook to fetch provider configurations
// TODO: getProviderConfigs method doesn't exist in the service
// export function useProviderConfigs(
//   providerId: string,
//   options?: BaseQueryOptions<IntegrationConfig[]>,
// ) {
//   return useQuery({
//     queryKey: integrationKeys.configs(providerId),
//     queryFn: () => integrationService.getProviderConfigs(providerId),
//     enabled: !!providerId,
//     ...options,
//   });
// }

// Hook to fetch sync history
// TODO: getSyncHistory method doesn't exist in the service
// export function useSyncHistory(id: string, options?: BaseQueryOptions<SyncResult[]>) {
//   return useQuery({
//     queryKey: integrationKeys.syncHistory(id),
//     queryFn: () => integrationService.getSyncHistory(id),
//     enabled: !!id,
//     ...options,
//   });
// }

// Hook to create integration
// TODO: createIntegration method doesn't exist in the service
// export function useCreateIntegration(options?: BaseMutationOptions<Integration, unknown, any>) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: (data) => integrationService.createIntegration(data),
//     onSuccess: (newIntegration) => {
//       // Add to cache and invalidate list
//       queryClient.setQueryData(integrationKeys.detail(newIntegration.id), newIntegration);
//       queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
//     },
//     ...options,
//   });
// }

// Hook to update integration
// TODO: updateIntegration method doesn't exist in the service
// export function useUpdateIntegration(
//   options?: BaseMutationOptions<Integration, unknown, { id: string; data: unknown }>,
// ) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: ({ id, data }) => integrationService.updateIntegration(id, data),
//     onSuccess: (updatedIntegration, variables) => {
//       // Update cache
//       queryClient.setQueryData(integrationKeys.detail(variables.id), updatedIntegration);
//       queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
//     },
//     ...options,
//   });
// }

// Hook to delete integration
// TODO: deleteIntegration method doesn't exist in the service
// export function useDeleteIntegration(options?: BaseMutationOptions<void, unknown, string>) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: (id: string) => integrationService.deleteIntegration(id),
//     onSuccess: (_, id) => {
//       // Remove from cache and invalidate list
//       queryClient.removeQueries({ queryKey: integrationKeys.detail(id) });
//       queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
//     },
//     ...options,
//   });
// }

// Hook to test integration connection
// TODO: testConnection method doesn't exist in the service
// export function useTestIntegrationConnection(
//   options?: BaseMutationOptions<any, unknown, { id?: string; config?: any }>,
// ) {
//   return useMutation({
//     mutationFn: ({ id, config }) => integrationService.testConnection(id, config),
//     ...options,
//   });
// }

// Hook to enable integration
// TODO: enableIntegration method doesn't exist in the service
// export function useEnableIntegration(options?: BaseMutationOptions<Integration, unknown, string>) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: (id: string) => integrationService.enableIntegration(id),
//     onSuccess: (updatedIntegration, id) => {
//       // Update cache
//       queryClient.setQueryData(integrationKeys.detail(id), updatedIntegration);
//       queryClient.invalidateQueries({ queryKey: integrationKeys.status(id) });
//       queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
//     },
//     ...options,
//   });
// }

// Hook to disable integration
// TODO: disableIntegration method doesn't exist in the service
// export function useDisableIntegration(options?: BaseMutationOptions<Integration, unknown, string>) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: (id: string) => integrationService.disableIntegration(id),
//     onSuccess: (updatedIntegration, id) => {
//       // Update cache
//       queryClient.setQueryData(integrationKeys.detail(id), updatedIntegration);
//       queryClient.invalidateQueries({ queryKey: integrationKeys.status(id) });
//       queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
//     },
//     ...options,
//   });
// }

// Hook to sync integration data
// TODO: syncIntegration method doesn't exist in the service
// export function useSyncIntegration(
//   options?: BaseMutationOptions<SyncResult, unknown, { id: string; force?: boolean }>,
// ) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: ({ id, force }) => integrationService.syncIntegration(id, force),
//     onSuccess: (_, variables) => {
//       // Invalidate status and sync history
//       queryClient.invalidateQueries({ queryKey: integrationKeys.status(variables.id) });
//       queryClient.invalidateQueries({ queryKey: integrationKeys.syncHistory(variables.id) });
//     },
//     ...options,
//   });
// }

// Hook to refresh integration credentials
// TODO: refreshCredentials method doesn't exist in the service
// export function useRefreshCredentials(options?: BaseMutationOptions<Integration, unknown, string>) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: (id: string) => integrationService.refreshCredentials(id),
//     onSuccess: (updatedIntegration, id) => {
//       // Update cache
//       queryClient.setQueryData(integrationKeys.detail(id), updatedIntegration);
//       queryClient.invalidateQueries({ queryKey: integrationKeys.status(id) });
//     },
//     ...options,
//   });
// }

// Hook to export integration data
// TODO: exportData method doesn't exist in the service
// export function useExportIntegrationData() {
//   return useMutation({
//     mutationFn: ({ id, format }: { id: string; format: 'json' | 'csv' | 'excel' }) =>
//       integrationService.exportData(id, format),
//   });
// }

// Hook to bulk sync multiple integrations
// TODO: bulkSync method doesn't exist in the service
// export function useBulkSync(options?: BaseMutationOptions<SyncResult[], unknown, string[]>) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: (integrationIds: string[]) => integrationService.bulkSync(integrationIds),
//     onSuccess: (_, integrationIds) => {
//       // Invalidate status and sync history for all integrations
//       integrationIds.forEach((id) => {
//         queryClient.invalidateQueries({ queryKey: integrationKeys.status(id) });
//         queryClient.invalidateQueries({ queryKey: integrationKeys.syncHistory(id) });
//       });
//     },
//     ...options,
//   });
// }
