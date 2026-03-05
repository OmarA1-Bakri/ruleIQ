import { useQuery } from '@tanstack/react-query';

import { frameworkService } from '@/lib/api/frameworks.service';

import {
  createQueryKey,
  type BaseQueryOptions,
  type PaginationParams,
  type PaginatedResponse,
} from './base';

// Define types locally until they're exported from the service
interface Framework {
  id: string;
  name: string;
  description?: string;
  version?: string;
  industry?: string;
  jurisdiction?: string;
  [key: string]: any;
}

interface FrameworkControl {
  id: string;
  framework_id: string;
  code: string;
  title: string;
  description?: string;
  [key: string]: any;
}

// Query keys
const FRAMEWORK_KEY = 'frameworks';

export const frameworkKeys = {
  all: [FRAMEWORK_KEY] as const,
  lists: () => [...frameworkKeys.all, 'list'] as const,
  list: (params?: PaginationParams) => createQueryKey(FRAMEWORK_KEY, 'list', params),
  details: () => [...frameworkKeys.all, 'detail'] as const,
  detail: (id: string) => createQueryKey(FRAMEWORK_KEY, 'detail', { id }),
  controls: (frameworkId: string) => createQueryKey(FRAMEWORK_KEY, 'controls', { frameworkId }),
  control: (frameworkId: string, controlId: string) =>
    createQueryKey(FRAMEWORK_KEY, 'control', { frameworkId, controlId }),
  mappings: (frameworkId: string) => createQueryKey(FRAMEWORK_KEY, 'mappings', { frameworkId }),
  categories: (frameworkId: string) => createQueryKey(FRAMEWORK_KEY, 'categories', { frameworkId }),
  applicable: (businessProfileId?: string) =>
    createQueryKey(FRAMEWORK_KEY, 'applicable', { businessProfileId }),
  recommendations: (businessProfileId?: string) =>
    createQueryKey(FRAMEWORK_KEY, 'recommendations', { businessProfileId }),
};

// Hook to fetch frameworks list
export function useFrameworks(
  params?: PaginationParams & {
    industry?: string;
    jurisdiction?: string;
    search?: string;
  },
  options?: BaseQueryOptions<PaginatedResponse<Framework>>,
) {
  return useQuery({
    queryKey: frameworkKeys.list(params),
    queryFn: async () => {
      const frameworks = await frameworkService.getFrameworks();
      // Convert to PaginatedResponse format - note: no server-side filtering yet
      return {
        items: frameworks as unknown as Framework[],
        total: frameworks.length,
        page: params?.page || 1,
        page_size: params?.page_size || 20,
        total_pages: Math.ceil(frameworks.length / (params?.page_size || 20)),
      } as PaginatedResponse<Framework>;
    },
    ...options,
  });
}

// Hook to fetch single framework
export function useFramework(id: string, options?: BaseQueryOptions<Framework>) {
  return useQuery({
    queryKey: frameworkKeys.detail(id),
    queryFn: () => frameworkService.getFramework(id),
    enabled: !!id,
    ...options,
  });
}

// Hook to fetch framework controls
export function useFrameworkControls(
  frameworkId: string,
  options?: BaseQueryOptions<FrameworkControl[]>,
) {
  return useQuery({
    queryKey: frameworkKeys.controls(frameworkId),
    queryFn: async () => {
      const response = await frameworkService.getFrameworkControls(frameworkId);
      // Map the controls to FrameworkControl[] format
      return response.controls.map((control) => ({
        id: control.control_id,
        framework_id: frameworkId,
        code: control.control_id,
        title: control.control_name,
        description: control.description,
        category: control.category,
        priority: control.priority,
        evidence_required: control.evidence_required,
      } as FrameworkControl));
    },
    enabled: !!frameworkId,
    ...options,
  });
}

// // Hook to fetch single control
// export function useFrameworkControl(
//   frameworkId: string,
//   controlId: string,
//   options?: BaseQueryOptions<FrameworkControl>,
// ) {
//   return useQuery({
//     queryKey: frameworkKeys.control(frameworkId, controlId),
//     queryFn: () => frameworkService.getFrameworkControl(frameworkId, controlId),
//     enabled: !!frameworkId && !!controlId,
//     ...options,
//   });
// }

// // Hook to fetch framework mappings
// export function useFrameworkMappings(
//   frameworkId: string,
//   options?: BaseQueryOptions<FrameworkMapping[]>,
// ) {
//   return useQuery({
//     queryKey: frameworkKeys.mappings(frameworkId),
//     queryFn: () => frameworkService.getFrameworkMappings(frameworkId),
//     enabled: !!frameworkId,
//     ...options,
//   });
// }
// 
// // Hook to fetch framework categories
// export function useFrameworkCategories(
//   frameworkId: string,
//   options?: BaseQueryOptions<FrameworkCategory[]>,
// ) {
//   return useQuery({
//     queryKey: frameworkKeys.categories(frameworkId),
//     queryFn: () => frameworkService.getFrameworkCategories(frameworkId),
//     enabled: !!frameworkId,
//     ...options,
//   });
// }
// 
// // Hook to fetch applicable frameworks
// export function useApplicableFrameworks(
//   businessProfileId?: string,
//   options?: BaseQueryOptions<Framework[]>,
// ) {
//   return useQuery({
//     queryKey: frameworkKeys.applicable(businessProfileId),
//     queryFn: () => frameworkService.getApplicableFrameworks(businessProfileId),
//     ...options,
//   });
// }
// 
// // Hook to fetch framework recommendations
export function useFrameworkRecommendations(
  businessProfileId?: string,
  options?: BaseQueryOptions<any>,
) {
  return useQuery({
    queryKey: frameworkKeys.recommendations(businessProfileId),
    queryFn: () => {
      if (!businessProfileId) {
        return Promise.resolve([]);
      }
      return frameworkService.getFrameworkRecommendations(businessProfileId);
    },
    enabled: !!businessProfileId,
    ...options,
  });
}

// Hook to enable framework for business profile
// export function useEnableFramework(
//   options?: BaseMutationOptions<void, unknown, { frameworkId: string; businessProfileId?: string }>,
// ) {
//   const queryClient = useQueryClient();
// 
//   return useMutation({
//     mutationFn: ({ frameworkId, businessProfileId }) =>
//       frameworkService.enableFramework(frameworkId, businessProfileId),
//     onSuccess: (_, variables) => {
//       // Invalidate applicable frameworks and framework details
//       queryClient.invalidateQueries({
//         queryKey: frameworkKeys.applicable(variables.businessProfileId),
//       });
//       queryClient.invalidateQueries({
//         queryKey: frameworkKeys.detail(variables.frameworkId),
//       });
//     },
//     ...options,
//   });
// }
// 
// // Hook to disable framework for business profile
// export function useDisableFramework(
//   options?: BaseMutationOptions<void, unknown, { frameworkId: string; businessProfileId?: string }>,
// ) {
//   const queryClient = useQueryClient();
// 
//   return useMutation({
//     mutationFn: ({ frameworkId, businessProfileId }) =>
//       frameworkService.disableFramework(frameworkId, businessProfileId),
//     onSuccess: (_, variables) => {
//       // Invalidate applicable frameworks and framework details
//       queryClient.invalidateQueries({
//         queryKey: frameworkKeys.applicable(variables.businessProfileId),
//       });
//       queryClient.invalidateQueries({
//         queryKey: frameworkKeys.detail(variables.frameworkId),
//       });
//     },
//     ...options,
//   });
// }
// 
// // Hook to update control status
// export function useUpdateControlStatus(
//   options?: BaseMutationOptions<
//     FrameworkControl,
//     unknown,
//     {
//       frameworkId: string;
//       controlId: string;
//       status: string;
//       notes?: string;
//     }
//   >,
// ) {
//   const queryClient = useQueryClient();
// 
//   return useMutation({
//     mutationFn: ({ frameworkId, controlId, status, notes }) =>
//       frameworkService.updateControlStatus(frameworkId, controlId, status, notes),
//     onSuccess: (_, variables) => {
//       // Invalidate control and controls list
//       queryClient.invalidateQueries({
//         queryKey: frameworkKeys.control(variables.frameworkId, variables.controlId),
//       });
//       queryClient.invalidateQueries({
//         queryKey: frameworkKeys.controls(variables.frameworkId),
//       });
//     },
//     ...options,
//   });
// }
// 
// // Hook to import framework
// export function useImportFramework(options?: BaseMutationOptions<Framework, unknown, FormData>) {
//   const queryClient = useQueryClient();
// 
//   return useMutation({
//     mutationFn: (formData: FormData) => frameworkService.importFramework(formData),
//     onSuccess: () => {
//       // Invalidate frameworks list
//       queryClient.invalidateQueries({ queryKey: frameworkKeys.lists() });
//     },
//     ...options,
//   });
// }
// 
// // Hook to export framework
// export function useExportFramework() {
//   return useMutation({
//     mutationFn: ({
//       frameworkId,
//       format,
//     }: {
//       frameworkId: string;
//       format: 'json' | 'csv' | 'excel';
//     }) => frameworkService.exportFramework(frameworkId, format),
//   });
// }

// Hook to compare frameworks
export function useCompareFrameworks(frameworkIds: string[], options?: BaseQueryOptions<any>) {
  return useQuery({
    queryKey: createQueryKey(FRAMEWORK_KEY, 'compare', { frameworkIds }),
    queryFn: () => frameworkService.compareFrameworks(frameworkIds),
    enabled: frameworkIds.length >= 2,
    ...options,
  });
}
