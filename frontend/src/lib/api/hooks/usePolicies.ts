import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, PolicySchema } from '../client';
import type {
  Policy,
  CreatePolicyRequest,
  UpdatePolicyRequest,
  PaginationParams
} from '../types';
import { z } from 'zod';

// Query keys
const POLICIES_KEY = ['policies'];

// Hooks
export function usePolicies(params?: PaginationParams) {
  return useQuery({
    queryKey: [...POLICIES_KEY, params],
    queryFn: async () => {
      const response = await apiClient.get<Policy[]>('/api/policies', params);
      
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch policies');
      }

      // Validate critical fields with Zod
      try {
        const validated = z.array(PolicySchema).parse(response.data);
        return validated;
      } catch (error) {
        console.error('Policy validation error:', error);
        // Return data even if validation fails (for development)
        return response.data || [];
      }
    },
    staleTime: 30000, // 30 seconds
    retry: 3,
  });
}

export function usePolicy(id: string) {
  return useQuery({
    queryKey: [...POLICIES_KEY, id],
    queryFn: async () => {
      const response = await apiClient.get<Policy>(`/api/policies/${id}`);
      
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch policy');
      }

      // Validate with Zod
      try {
        const validated = PolicySchema.parse(response.data);
        return validated;
      } catch (error) {
        console.error('Policy validation error:', error);
        return response.data;
      }
    },
    enabled: !!id,
  });
}

export function useCreatePolicy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreatePolicyRequest) => {
      const response = await apiClient.post<Policy>('/api/policies', data);
      
      if (!response.success) {
        throw new Error(response.error || 'Failed to create policy');
      }

      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: POLICIES_KEY });
    },
  });
}

export function useUpdatePolicy(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: UpdatePolicyRequest) => {
      const response = await apiClient.put<Policy>(`/api/policies/${id}`, data);
      
      if (!response.success) {
        throw new Error(response.error || 'Failed to update policy');
      }

      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: POLICIES_KEY });
      queryClient.invalidateQueries({ queryKey: [...POLICIES_KEY, id] });
    },
  });
}

export function useDeletePolicy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await apiClient.delete(`/api/policies/${id}`);
      
      if (!response.success) {
        throw new Error(response.error || 'Failed to delete policy');
      }

      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: POLICIES_KEY });
    },
  });
}