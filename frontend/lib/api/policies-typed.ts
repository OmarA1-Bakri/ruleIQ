/**
 * Typed Policies API service with Zod validation
 */

import { z } from 'zod';
import { apiClient } from './client';
import type { 
  Policy, 
  PolicyQueryParams, 
  CreatePolicyRequest, 
  UpdatePolicyRequest,
  PaginatedResponse,
} from './types';

// Zod schemas for validation
const PolicySchema = z.object({
  id: z.string().uuid(),
  title: z.string().min(1).max(255),
  description: z.string(),
  category: z.enum([
    'data_protection',
    'security', 
    'privacy',
    'compliance',
    'operational',
    'financial'
  ]),
  status: z.enum([
    'draft',
    'under_review',
    'approved',
    'published',
    'archived'
  ]),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  version: z.number().int().positive(),
  content: z.string().optional(),
  tags: z.array(z.string()).optional(),
  compliance_frameworks: z.array(z.string()).optional(),
  risk_level: z.enum(['low', 'medium', 'high', 'critical']).optional(),
});

const PaginatedPoliciesSchema = z.object({
  items: z.array(PolicySchema),
  total: z.number(),
  page: z.number(),
  pages: z.number(),
  per_page: z.number(),
});

// Critical fields guard for policies list
const PolicyListItemSchema = PolicySchema.pick({
  id: true,
  title: true,
  category: true,
  status: true,
  created_at: true,
});

export class PoliciesService {
  private basePath = '/api/v1/policies';

  /**
   * Get paginated list of policies
   */
  async listPolicies(params?: PolicyQueryParams): Promise<PaginatedResponse<Policy>> {
    try {
    const response = await apiClient.get<any>(`${this.basePath}/`, params ? { params: params as Record<string, string | number | boolean | null | undefined> } : {});
      
      // Validate response with Zod
      const validated = PaginatedPoliciesSchema.parse(response);
      
      // Additional validation for critical fields
      validated.items.forEach(item => {
        PolicyListItemSchema.parse(item);
      });
      
      return validated as PaginatedResponse<Policy>;
    } catch (error) {
      if (error instanceof z.ZodError) {
        console.error('Validation error in policies response:', error.errors);
        throw new Error('Invalid policies data received from server');
      }
      throw error;
    }
  }

  /**
   * Get a single policy by ID
   */
  async getPolicy(id: string): Promise<Policy> {
    try {
      const response = await apiClient.get<any>(`${this.basePath}/${id}`);
      return PolicySchema.parse(response) as Policy;
    } catch (error) {
      if (error instanceof z.ZodError) {
        console.error('Validation error in policy response:', error.errors);
        throw new Error('Invalid policy data received from server');
      }
      throw error;
    }
  }

  /**
   * Create a new policy
   */
  async createPolicy(data: CreatePolicyRequest): Promise<Policy> {
    try {
      const response = await apiClient.post<any>(this.basePath, data);
      return PolicySchema.parse(response) as Policy;
    } catch (error) {
      if (error instanceof z.ZodError) {
        console.error('Validation error in created policy:', error.errors);
        throw new Error('Invalid policy data received from server');
      }
      throw error;
    }
  }

  /**
   * Update an existing policy
   */
  async updatePolicy(id: string, data: UpdatePolicyRequest): Promise<Policy> {
    try {
      const response = await apiClient.patch<any>(`${this.basePath}/${id}`, data);
      return PolicySchema.parse(response) as Policy;
    } catch (error) {
      if (error instanceof z.ZodError) {
        console.error('Validation error in updated policy:', error.errors);
        throw new Error('Invalid policy data received from server');
      }
      throw error;
    }
  }

  /**
   * Delete a policy
   */
  async deletePolicy(id: string): Promise<void> {
    await apiClient.delete(`${this.basePath}/${id}`);
  }

  /**
   * Validate policy data against schema
   */
  validatePolicy(data: unknown): Policy {
    return PolicySchema.parse(data) as Policy;
  }

  /**
   * Type guard for critical policy fields
   */
  hasRequiredFields(policy: any): policy is Pick<Policy, 'id' | 'title' | 'category' | 'status'> {
    try {
      PolicyListItemSchema.parse(policy);
      return true;
    } catch (_error) {
      return false;
    }
  }
}

// Export singleton instance
export const policiesService = new PoliciesService();

// Re-export types for convenience
export type { Policy, PolicyQueryParams, CreatePolicyRequest, UpdatePolicyRequest };
export { PolicyCategory, PolicyStatus, RiskLevel } from './types';