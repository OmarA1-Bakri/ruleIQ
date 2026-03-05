import { z } from 'zod';
import type {
  BaseResponse,
  PaginationParams
} from './types';

// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Zod schemas for critical fields validation
export const PolicySchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  framework: z.string(),
  status: z.enum(['active', 'draft', 'archived']),
  created_at: z.string(),
  updated_at: z.string(),
  requirements: z.array(z.object({
    id: z.string(),
    policy_id: z.string(),
    title: z.string(),
    description: z.string(),
    category: z.string(),
    priority: z.enum(['high', 'medium', 'low']),
    status: z.enum(['compliant', 'non_compliant', 'partial', 'not_assessed']),
  })).optional().default([]),
});

export const RiskSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  category: z.string(),
  severity: z.enum(['critical', 'high', 'medium', 'low']),
  likelihood: z.enum(['certain', 'likely', 'possible', 'unlikely', 'rare']),
  impact: z.enum(['severe', 'major', 'moderate', 'minor', 'negligible']),
  status: z.enum(['identified', 'mitigated', 'accepted', 'transferred']),
  mitigation_plan: z.string().optional(),
});

// API Client class
export class ApiClient {
  private baseUrl: string;
  private headers: HeadersInit;

  constructor(baseUrl = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.headers = {
      'Content-Type': 'application/json',
    };
  }

  // Set auth token
  setAuthToken(token: string) {
    this.headers = {
      ...this.headers,
      'Authorization': `Bearer ${token}`,
    };
  }

  // Generic fetch wrapper with error handling
  private async fetchWithErrorHandling<T>(
    url: string,
    options: RequestInit = {}
  ): Promise<BaseResponse<T>> {
    try {
      const response = await fetch(`${this.baseUrl}${url}`, {
        ...options,
        headers: {
          ...this.headers,
          ...options.headers,
        },
      });

      if (!response.ok) {
        return {
          success: false,
          error: `HTTP ${response.status}: ${response.statusText}`,
        };
      }

      const data = await response.json();
      return {
        success: true,
        data,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  // GET request
  async get<T>(url: string, params?: PaginationParams): Promise<BaseResponse<T>> {
    const queryString = params ? `?${new URLSearchParams(params as any).toString()}` : '';
    return this.fetchWithErrorHandling<T>(`${url}${queryString}`, {
      method: 'GET',
    });
  }

  // POST request
  async post<T, D = any>(url: string, data?: D): Promise<BaseResponse<T>> {
    return this.fetchWithErrorHandling<T>(url, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // PUT request
  async put<T, D = any>(url: string, data?: D): Promise<BaseResponse<T>> {
    return this.fetchWithErrorHandling<T>(url, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // DELETE request
  async delete<T>(url: string): Promise<BaseResponse<T>> {
    return this.fetchWithErrorHandling<T>(url, {
      method: 'DELETE',
    });
  }

  // File upload
  async uploadFile<T>(url: string, file: File, additionalData?: Record<string, any>): Promise<BaseResponse<T>> {
    const formData = new FormData();
    formData.append('file', file);
    
    if (additionalData) {
      Object.entries(additionalData).forEach(([key, value]) => {
        formData.append(key, value);
      });
    }

    return this.fetchWithErrorHandling<T>(url, {
      method: 'POST',
      body: formData,
      headers: {
        ...this.headers,
        'Content-Type': undefined as any, // Let browser set the content type for FormData
      },
    });
  }
}

// Singleton instance
export const apiClient = new ApiClient();