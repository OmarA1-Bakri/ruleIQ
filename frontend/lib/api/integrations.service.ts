import { apiClient } from './client';

import type { Integration } from '@/types/api';

export interface ConnectIntegrationRequest {
  provider: string;
  config?: Record<string, any>;
}

export interface IntegrationWebhookConfig {
  endpoint_url: string;
  events: string[];
  secret?: string;
  active: boolean;
}

class IntegrationService {
  /**
   * Get all available integrations
   */
  async getIntegrations(): Promise<Integration[]> {
    const response = await apiClient.get<Integration[]>('/integrations');
    return response;
  }

  /**
   * Get connected integrations for the current user
   */
  async getConnectedIntegrations(): Promise<Integration[]> {
    const response = await apiClient.get<Integration[]>('/integrations/connected');
    return response;
  }

  /**
   * Get a single integration by id
   */
  async getIntegration(integrationId: string): Promise<Integration> {
    const response = await apiClient.get<Integration>(`/integrations/${integrationId}/status`);
    return response;
  }

  /**
   * Get the current status payload for an integration
   */
  async getIntegrationStatus(integrationId: string): Promise<Integration> {
    return this.getIntegration(integrationId);
  }

  /**
   * Connect a new integration
   */
  async connectIntegration(data: ConnectIntegrationRequest): Promise<{
    integration_id: string;
    status: 'connected' | 'pending_auth';
    auth_url?: string;
  }> {
    const response = await apiClient.post<any>('/integrations/connect', data);
    return response;
  }

  /**
   * Disconnect an integration
   */
  async disconnectIntegration(integrationId: string): Promise<void> {
    await apiClient.delete(`/integrations/${integrationId}/disconnect`);
  }

  /**
   * Test integration connection
   */
  async testIntegration(integrationId: string): Promise<{
    status: 'success' | 'failed';
    message: string;
    details?: any;
  }> {
    const response = await apiClient.post<any>(`/integrations/${integrationId}/test`);
    return response;
  }

  /**
   * Sync data from integration
   */
  async syncIntegration(
    integrationId: string,
    options?: {
      full_sync?: boolean;
      data_types?: string[];
    },
  ): Promise<{
    sync_id: string;
    status: 'started' | 'in_progress' | 'completed' | 'failed';
    items_synced?: number;
    errors?: string[];
  }> {
    const response = await apiClient.post<any>(
      `/integrations/${integrationId}/sync`,
      options || {},
    );
    return response;
  }

  /**
   * Get integration sync history
   */
  async getIntegrationSyncHistory(integrationId: string): Promise<{
    syncs: Array<{
      sync_id: string;
      started_at: string;
      completed_at?: string;
      status: string;
      items_synced: number;
      errors_count: number;
    }>;
  }> {
    const response = await apiClient.get<any>(`/integrations/${integrationId}/sync-history`);
    return response;
  }

  /**
   * Configure integration webhooks
   */
  async configureWebhooks(
    integrationId: string,
    config: IntegrationWebhookConfig,
  ): Promise<{
    webhook_id: string;
    status: 'active' | 'inactive';
    test_url: string;
  }> {
    const response = await apiClient.post<any>(`/integrations/${integrationId}/webhooks`, config);
    return response;
  }

  /**
   * Get integration activity logs
   */
  async getIntegrationLogs(
    integrationId: string,
    params?: {
      start_date?: string;
      end_date?: string;
      event_type?: string;
      page?: number;
      page_size?: number;
    },
  ): Promise<{
    logs: Array<{
      timestamp: string;
      event_type: string;
      status: string;
      details: any;
    }>;
    total: number;
  }> {
    const response = await apiClient.get<any>(`/integrations/${integrationId}/logs`, params ? { params } : {});
    return response;
  }

  /**
   * Update integration configuration
   */
  async updateIntegrationConfig(
    integrationId: string,
    config: Record<string, any>,
  ): Promise<Integration> {
    const response = await apiClient.patch<Integration>(
      `/integrations/${integrationId}/config`,
      config,
    );
    return response;
  }

  /**
   * Get OAuth callback URL for integration
   */
  getOAuthCallbackUrl(provider: string): string {
    return `${window.location.origin}/integrations/callback/${provider}`;
  }

  /**
   * Handle OAuth callback
   */
  async handleOAuthCallback(
    provider: string,
    code: string,
    state?: string,
  ): Promise<{
    success: boolean;
    integration_id?: string;
    error?: string;
  }> {
    const response = await apiClient.post<any>('/integrations/oauth/callback', {
      provider,
      code,
      state,
    });
    return response;
  }
}

export const integrationService = new IntegrationService();
