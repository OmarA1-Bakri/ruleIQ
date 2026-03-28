import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  integrationService,
  type ConnectIntegrationRequest,
  type IntegrationWebhookConfig,
} from '@/lib/api/integrations.service';
import type { Integration } from '@/types/api';

import {
  createQueryKey,
  type BaseMutationOptions,
  type BaseQueryOptions,
  type PaginationParams,
  type PaginatedResponse,
} from './base';

interface IntegrationLog {
  id: string;
  message: string;
  timestamp: string;
  event_type?: string;
  status?: string;
  details?: unknown;
}

const INTEGRATION_KEY = 'integrations';

export const integrationKeys = {
  all: [INTEGRATION_KEY] as const,
  lists: () => [...integrationKeys.all, 'list'] as const,
  list: (params?: PaginationParams) => createQueryKey(INTEGRATION_KEY, 'list', params),
  details: () => [...integrationKeys.all, 'detail'] as const,
  detail: (id: string) => createQueryKey(INTEGRATION_KEY, 'detail', { id }),
  status: (id: string) => createQueryKey(INTEGRATION_KEY, 'status', { id }),
  logs: (id: string, params?: Record<string, unknown>) =>
    createQueryKey(INTEGRATION_KEY, 'logs', { id, ...params }),
  syncHistory: (id: string) => createQueryKey(INTEGRATION_KEY, 'sync-history', { id }),
};

function paginateIntegrations(
  integrations: Integration[],
  params?: PaginationParams & {
    provider?: string;
    status?: string;
    type?: string;
  },
): PaginatedResponse<Integration> {
  let filtered = integrations;

  if (params?.provider) {
    filtered = filtered.filter(
      (integration: any) =>
        integration.provider === params.provider || integration.provider_id === params.provider,
    );
  }

  if (params?.status) {
    filtered = filtered.filter((integration: any) => integration.status === params.status);
  }

  const page = params?.page || 1;
  const pageSize = params?.page_size || 20;
  const start = (page - 1) * pageSize;
  const items = filtered.slice(start, start + pageSize);

  return {
    items,
    total: filtered.length,
    page,
    page_size: pageSize,
    total_pages: Math.max(1, Math.ceil(filtered.length / pageSize)),
  };
}

export function useIntegrations(
  params?: PaginationParams & {
    provider?: string;
    status?: string;
    type?: string;
  },
  options?: BaseQueryOptions<PaginatedResponse<Integration>>,
) {
  return useQuery({
    queryKey: integrationKeys.list(params),
    queryFn: async () => paginateIntegrations(await integrationService.getIntegrations(), params),
    ...options,
  });
}

export function useIntegration(id: string, options?: BaseQueryOptions<Integration>) {
  return useQuery({
    queryKey: integrationKeys.detail(id),
    queryFn: () => integrationService.getIntegration(id),
    enabled: !!id,
    ...options,
  });
}

export function useIntegrationStatus(id: string, options?: BaseQueryOptions<Integration>) {
  return useQuery({
    queryKey: integrationKeys.status(id),
    queryFn: () => integrationService.getIntegrationStatus(id),
    enabled: !!id,
    refetchInterval: 30000,
    ...options,
  });
}

export function useIntegrationLogs(
  id: string,
  params?: {
    event_type?: string;
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
      const page = params?.page || 1;
      const pageSize = params?.page_size || 20;

      return {
        items: response.logs.map((log) => ({
          id: `${log.timestamp}-${log.event_type}`,
          message: log.event_type,
          timestamp: log.timestamp,
          ...log,
        })),
        total: response.total,
        page,
        page_size: pageSize,
        total_pages: Math.max(1, Math.ceil(response.total / pageSize)),
      };
    },
    enabled: !!id,
    ...options,
  });
}

export function useSyncHistory(id: string, options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: integrationKeys.syncHistory(id),
    queryFn: () => integrationService.getIntegrationSyncHistory(id),
    enabled: !!id,
    ...options,
  });
}

export function useConnectIntegration(
  options?: BaseMutationOptions<
    { integration_id: string; status: 'connected' | 'pending_auth'; auth_url?: string },
    unknown,
    ConnectIntegrationRequest
  >,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => integrationService.connectIntegration(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
    },
    ...options,
  });
}

export function useDisconnectIntegration(
  options?: BaseMutationOptions<void, unknown, string>,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => integrationService.disconnectIntegration(id),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: integrationKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
      queryClient.invalidateQueries({ queryKey: integrationKeys.status(id) });
    },
    ...options,
  });
}

export function useTestIntegration(
  options?: BaseMutationOptions<any, unknown, string>,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => integrationService.testIntegration(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.status(id) });
    },
    ...options,
  });
}

export function useSyncIntegration(
  options?: BaseMutationOptions<
    { sync_id: string; status: 'started' | 'in_progress' | 'completed' | 'failed'; items_synced?: number; errors?: string[] },
    unknown,
    { id: string; options?: { full_sync?: boolean; data_types?: string[] } }
  >,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, options: syncOptions }) =>
      integrationService.syncIntegration(id, syncOptions),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.status(variables.id) });
      queryClient.invalidateQueries({ queryKey: integrationKeys.syncHistory(variables.id) });
      queryClient.invalidateQueries({ queryKey: integrationKeys.logs(variables.id) });
    },
    ...options,
  });
}

export function useUpdateIntegrationConfig(
  options?: BaseMutationOptions<Integration, unknown, { id: string; config: Record<string, any> }>,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, config }) => integrationService.updateIntegrationConfig(id, config),
    onSuccess: (updatedIntegration, variables) => {
      queryClient.setQueryData(integrationKeys.detail(variables.id), updatedIntegration);
      queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
      queryClient.invalidateQueries({ queryKey: integrationKeys.status(variables.id) });
    },
    ...options,
  });
}

export function useConfigureIntegrationWebhooks(
  options?: BaseMutationOptions<
    { webhook_id: string; status: 'active' | 'inactive'; test_url: string },
    unknown,
    { id: string; config: IntegrationWebhookConfig }
  >,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, config }) => integrationService.configureWebhooks(id, config),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: integrationKeys.logs(variables.id) });
    },
    ...options,
  });
}
