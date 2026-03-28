import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  monitoringService,
  type MonitoringAlertListParams,
  type MonitoringAuditLogParams,
  type MonitoringErrorLogParams,
} from '@/lib/api/monitoring.service';

import { createQueryKey, type BaseMutationOptions, type BaseQueryOptions } from './base';

const MONITORING_KEY = 'monitoring';

export const monitoringKeys = {
  all: [MONITORING_KEY] as const,
  health: () => createQueryKey(MONITORING_KEY, 'health'),
  metrics: () => createQueryKey(MONITORING_KEY, 'metrics'),
  performance: (params?: Record<string, unknown>) =>
    createQueryKey(MONITORING_KEY, 'performance', params),
  alerts: (params?: Record<string, unknown>) => createQueryKey(MONITORING_KEY, 'alerts', params),
  alert: (id: string) => createQueryKey(MONITORING_KEY, 'alert', { id }),
  systemStatus: () => createQueryKey(MONITORING_KEY, 'system-status'),
  auditLogs: (params?: Record<string, unknown>) =>
    createQueryKey(MONITORING_KEY, 'audit-logs', params),
  errorLogs: (params?: Record<string, unknown>) =>
    createQueryKey(MONITORING_KEY, 'error-logs', params),
};

export function useSystemHealth(options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: monitoringKeys.health(),
    queryFn: () => monitoringService.getHealthCheck(),
    refetchInterval: 30000,
    ...options,
  });
}

export function useSystemMetrics(options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: monitoringKeys.metrics(),
    queryFn: () => monitoringService.getSystemMetrics(),
    refetchInterval: 60000,
    ...options,
  });
}

export function usePerformanceMetrics(
  params?: {
    endpoint?: string;
    time_range?: 'hour' | 'day' | 'week' | 'month';
  },
  options?: BaseQueryOptions<any>,
) {
  return useQuery({
    queryKey: monitoringKeys.performance(params),
    queryFn: () => monitoringService.getApiPerformanceMetrics(params),
    refetchInterval: 60000,
    ...options,
  });
}

export function useAlerts(params?: MonitoringAlertListParams, options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: monitoringKeys.alerts(params),
    queryFn: () => monitoringService.getSystemAlerts(params),
    refetchInterval: 30000,
    ...options,
  });
}

export function useAlert(id: string, options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: monitoringKeys.alert(id),
    queryFn: () => monitoringService.getAlert(id),
    enabled: !!id,
    ...options,
  });
}

export function useSystemStatus(options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: monitoringKeys.systemStatus(),
    queryFn: () => monitoringService.getDatabaseStatus(),
    refetchInterval: 15000,
    ...options,
  });
}

export function useAuditLogs(
  params?: MonitoringAuditLogParams,
  options?: BaseQueryOptions<any>,
) {
  return useQuery({
    queryKey: monitoringKeys.auditLogs(params),
    queryFn: () => monitoringService.getAuditLogs(params),
    ...options,
  });
}

export function useErrorLogs(
  params?: MonitoringErrorLogParams,
  options?: BaseQueryOptions<any>,
) {
  return useQuery({
    queryKey: monitoringKeys.errorLogs(params),
    queryFn: () => monitoringService.getErrorLogs(params),
    ...options,
  });
}

export function useResolveAlert(
  options?: BaseMutationOptions<any, unknown, { id: string; resolution?: string }>,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, resolution }) => monitoringService.resolveAlert(id, resolution),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: monitoringKeys.alerts() });
      queryClient.invalidateQueries({ queryKey: monitoringKeys.alert(variables.id) });
    },
    ...options,
  });
}

export function useExportMonitoringData() {
  return useMutation({
    mutationFn: (params: {
      data_type: 'alerts' | 'metrics' | 'errors' | 'audit';
      format: 'csv' | 'json';
      start_date: string;
      end_date: string;
    }) => monitoringService.exportMonitoringData(params),
  });
}
