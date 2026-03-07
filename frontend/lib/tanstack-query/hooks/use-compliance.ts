import { useQuery } from '@tanstack/react-query';

import { complianceService } from '@/lib/api/compliance.service';

import {
  createQueryKey,
  type BaseQueryOptions,
  type PaginationParams,
} from './base';

// Import only the types that exist
import type { ComplianceStatus } from '@/types/api';
import type { ComplianceTask } from '@/lib/api/compliance.service';

// Query keys
const COMPLIANCE_KEY = 'compliance';

export const complianceKeys = {
  all: [COMPLIANCE_KEY] as const,
  status: (businessProfileId?: string) =>
    createQueryKey(COMPLIANCE_KEY, 'status', { businessProfileId }),
  tasks: (params?: PaginationParams) => createQueryKey(COMPLIANCE_KEY, 'tasks', params),
  dashboard: (businessProfileId?: string) =>
    createQueryKey(COMPLIANCE_KEY, 'dashboard', { businessProfileId }),
};

// Hook to fetch compliance status - FIXED to pass businessProfileId when it exists
export function useComplianceStatus(
  businessProfileId?: string,
  options?: BaseQueryOptions<ComplianceStatus[]>,
) {
  return useQuery({
    queryKey: complianceKeys.status(businessProfileId),
    queryFn: () => {
      if (!businessProfileId) {
        return Promise.resolve([]);
      }
      return complianceService.getComplianceStatus(businessProfileId);
    },
    enabled: !!businessProfileId,
    ...options,
  });
}

// Hook to fetch compliance tasks - FIXED to use correct method name
export function useComplianceTasks(
  params?: {
    business_profile_id: string;
    framework_id?: string;
    status?: string;
    priority?: string;
    page?: number;
    page_size?: number;
  },
  options?: BaseQueryOptions<{ items: ComplianceTask[]; total: number }>,
) {
  return useQuery({
    queryKey: complianceKeys.tasks(params),
    queryFn: async () => {
      const response = await complianceService.getComplianceTasks(params);
      // Transform tasks to items to match expected type
      return {
        items: (response as any).tasks || [],
        total: (response as any).total || 0,
      };
    },
    enabled: !!params?.business_profile_id,
    ...options,
  });
}

// Hook to fetch compliance dashboard
export function useComplianceDashboard(
  businessProfileId?: string,
  options?: BaseQueryOptions<any>,
) {
  return useQuery({
    queryKey: complianceKeys.dashboard(businessProfileId),
    queryFn: () => {
      if (!businessProfileId) {
        return Promise.resolve(null);
      }
      return complianceService.getComplianceDashboard(businessProfileId);
    },
    enabled: !!businessProfileId,
    ...options,
  });
}

// Note: The following hooks are commented out because the service methods don't exist yet
// They can be uncommented when the backend implements these endpoints

// export function useComplianceScore() { ... }
// export function useComplianceRequirements() { ... }
// export function useComplianceSummary() { ... }
// export function useComplianceGaps() { ... }
// export function useComplianceEvidence() { ... }
// export function useUpdateRequirementStatus() { ... }
// export function useUploadEvidence() { ... }
// export function useCreateComplianceTask() { ... }
// export function useUpdateComplianceTask() { ... }