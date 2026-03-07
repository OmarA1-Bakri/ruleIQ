import { useQuery } from '@tanstack/react-query';

import { monitoringService } from '@/lib/api/monitoring.service';

import { createQueryKey, type BaseQueryOptions } from './base';

// Query keys
const MONITORING_KEY = 'monitoring';

export const monitoringKeys = {
  all: [MONITORING_KEY] as const,
  health: () => createQueryKey(MONITORING_KEY, 'health'),
  metrics: () => createQueryKey(MONITORING_KEY, 'metrics'),
  performance: () => createQueryKey(MONITORING_KEY, 'performance'),
  alerts: () => createQueryKey(MONITORING_KEY, 'alerts'),
  alert: (id: string) => createQueryKey(MONITORING_KEY, 'alert', { id }),
  systemStatus: () => createQueryKey(MONITORING_KEY, 'system-status'),
  auditLogs: (params?: any) => createQueryKey(MONITORING_KEY, 'audit-logs', params),
  errorLogs: (params?: any) => createQueryKey(MONITORING_KEY, 'error-logs', params),
};

// Hook to fetch system health
export function useSystemHealth(options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: monitoringKeys.health(),
    queryFn: () => monitoringService.getHealthCheck(),
    refetchInterval: 30000, // Refresh every 30 seconds
    ...options,
  });
}

// Hook to fetch system metrics
export function useSystemMetrics(options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: monitoringKeys.metrics(),
    queryFn: () => monitoringService.getSystemMetrics(),
    refetchInterval: 60000, // Refresh every minute
    ...options,
  });
}

// Hook to fetch performance metrics
export function usePerformanceMetrics(options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: monitoringKeys.performance(),
    queryFn: () => monitoringService.getApiPerformanceMetrics(),
    refetchInterval: 60000, // Refresh every minute
    ...options,
  });
}

// Hook to fetch alerts
export function useAlerts(
  params?: {
    status?: 'active' | 'resolved' | 'acknowledged';
    severity?: 'critical' | 'high' | 'medium' | 'low';
    page?: number;
    page_size?: number;
  },
  options?: BaseQueryOptions<any>,
) {
  return useQuery({
    queryKey: monitoringKeys.alerts(),
    queryFn: () => monitoringService.getSystemAlerts(params),
    refetchInterval: 30000, // Refresh every 30 seconds
    ...options,
  });
}

// Hook to fetch single alert
export function useAlert(id: string, options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: monitoringKeys.alert(id),
    // TODO: getAlert method doesn't exist, using getSystemAlerts
    queryFn: async () => {
      const response = await monitoringService.getSystemAlerts();
      return response.alerts?.find((a: any) => a.id === id);
    },
    enabled: !!id,
    ...options,
  });
}

// Hook to fetch system status
export function useSystemStatus(options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: monitoringKeys.systemStatus(),
    queryFn: () => monitoringService.getDatabaseStatus(),
    refetchInterval: 15000, // Refresh every 15 seconds
    ...options,
  });
}

// Hook to fetch audit logs
export function useAuditLogs(
  params?: {
    user_id?: string;
    action?: string;
    resource?: string;
    start_date?: string;
    end_date?: string;
    page?: number;
    page_size?: number;
  },
  options?: BaseQueryOptions<any>,
) {
  return useQuery({
    queryKey: monitoringKeys.auditLogs(params),
    queryFn: () => monitoringService.getAuditLogs(params),
    ...options,
  });
}

// Hook to fetch error logs
export function useErrorLogs(
  params?: {
    severity?: 'info' | 'warning' | 'error';
    service?: string;
    start_date?: string;
    end_date?: string;
    page?: number;
    page_size?: number;
  },
  options?: BaseQueryOptions<any>,
) {
  return useQuery({
    queryKey: monitoringKeys.errorLogs(params),
    queryFn: () => monitoringService.getErrorLogs(params as any),
    ...options,
  });
}

// Hook to acknowledge alert
// TODO: acknowledgeAlert method doesn't exist in the service
// export function useAcknowledgeAlert(
//   options?: BaseMutationOptions<any, unknown, { id: string; notes?: string }>,
// ) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: ({ id, notes }) => monitoringService.acknowledgeAlert(id, notes),
//     onSuccess: (_, variables) => {
//       // Invalidate alerts and specific alert
//       queryClient.invalidateQueries({ queryKey: monitoringKeys.alerts() });
//       queryClient.invalidateQueries({ queryKey: monitoringKeys.alert(variables.id) });
//     },
//     ...options,
//   });
// }

// Hook to resolve alert
// TODO: resolveAlert method doesn't exist in the service
// export function useResolveAlert(
//   options?: BaseMutationOptions<any, unknown, { id: string; resolution?: string }>,
// ) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: ({ id, resolution }) => monitoringService.resolveAlert(id, resolution),
//     onSuccess: (_, variables) => {
//       // Invalidate alerts and specific alert
//       queryClient.invalidateQueries({ queryKey: monitoringKeys.alerts() });
//       queryClient.invalidateQueries({ queryKey: monitoringKeys.alert(variables.id) });
//     },
//     ...options,
//   });
// }

// Hook to create alert
// TODO: createAlert method doesn't exist in the service
// export function useCreateAlert(options?: BaseMutationOptions<any, unknown, any>) {
//   const queryClient = useQueryClient();
//
//   return useMutation({
//     mutationFn: (data) => monitoringService.createAlert(data),
//     onSuccess: () => {
//       // Invalidate alerts list
//       queryClient.invalidateQueries({ queryKey: monitoringKeys.alerts() });
//     },
//     ...options,
//   });
// }

// Hook to export logs
// TODO: exportLogs method doesn't exist in the service
// export function useExportLogs() {
//   return useMutation({
//     mutationFn: ({
//       type,
//       format,
//       params,
//     }: {
//       type: 'audit' | 'error' | 'all';
//       format: 'csv' | 'json' | 'pdf';
//       params?: any;
//     }) => monitoringService.exportLogs(type, format, params),
//   });
// }

// Hook to test alert notification
// TODO: testAlertNotification method doesn't exist in the service
// export function useTestAlertNotification() {
//   return useMutation({
//     mutationFn: ({ channel, config }: { channel: 'email' | 'slack' | 'webhook'; config: any }) =>
//       monitoringService.testAlertNotification(channel, config),
//   });
// }
