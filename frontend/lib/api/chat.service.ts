import { env } from '@/src/config/env';

import { apiClient } from './client';

import type { ChatConversation, ChatMessage } from '@/types/api';

export interface CreateConversationRequest {
  title?: string;
  initial_message?: string;
}

export interface SendMessageRequest {
  content: string;
}

export interface EvidenceRecommendationRequest {
  framework: string;
}

export interface ComplianceAnalysisRequest {
  framework: string;
}

export type ChatWebSocketMessage = {
  type: 'message' | 'typing' | 'error' | 'connection';
  data: unknown;
};

class ChatService {
  private ws: WebSocket | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private messageHandlers: ((message: ChatWebSocketMessage) => void)[] = [];
  private currentConversationId: string | null = null;

  /**
   * Get all chat conversations
   */
  async getConversations(params?: {
    page?: number;
    page_size?: number;
  }): Promise<{ items: ChatConversation[]; total: number }> {
    const response = await apiClient.get<{ items: ChatConversation[]; total: number }>(
      '/chat/conversations',
      { params },
    );
    return response;
  }

  /**
   * Get a specific conversation
   */
  async getConversation(id: string): Promise<{
    conversation: ChatConversation;
    messages: ChatMessage[];
  }> {
    const response = await apiClient.get<{
      conversation: ChatConversation;
      messages: ChatMessage[];
    }>(`/chat/conversations/${id}`);
    return response;
  }

  /**
   * Create a new conversation
   */
  async createConversation(data?: CreateConversationRequest): Promise<{
    conversation: ChatConversation;
    messages: ChatMessage[];
  }> {
    const response = await apiClient.post<{
      conversation: ChatConversation;
      messages: ChatMessage[];
    }>('/chat/conversations', data || {});
    return response;
  }

  /**
   * Send a message in a conversation
   */
  async sendMessage(conversationId: string, data: SendMessageRequest): Promise<ChatMessage> {
    const response = await apiClient.post<ChatMessage>(
      `/chat/conversations/${conversationId}/messages`,
      data,
    );
    return response;
  }

  /**
   * Delete (archive) a conversation
   */
  async deleteConversation(id: string): Promise<void> {
    await apiClient.delete(`/chat/conversations/${id}`);
  }

  /**
   * Get evidence recommendations
   */
  async getEvidenceRecommendations(data: EvidenceRecommendationRequest): Promise<{
    recommendations: Array<{
      control_id: string;
      control_name: string;
      evidence_type: string;
      priority: string;
      description: string;
      automation_available: boolean;
    }>;
    total_recommendations: number;
  }> {
    const response = await apiClient.post<any>('/chat/evidence-recommendations', data);
    return response;
  }

  /**
   * Get compliance gap analysis
   */
  async getComplianceGapAnalysis(data: ComplianceAnalysisRequest): Promise<{
    framework: string;
    completion_percentage: number;
    critical_gaps: string[];
    recommendations: string[];
    estimated_effort_hours: number;
  }> {
    const response = await apiClient.post<any>('/chat/compliance-gap-analysis', data);
    return response;
  }

  /**
   * Get context-aware recommendations
   */
  async getContextAwareRecommendations(
    framework: string,
    contextType: 'comprehensive' | 'guidance' = 'comprehensive',
  ): Promise<any> {
    const response = await apiClient.post<any>(
      `/chat/context-aware-recommendations?framework=${encodeURIComponent(framework)}&context_type=${encodeURIComponent(contextType)}`
    );
    return response;
  }

  /**
   * Generate evidence collection workflow
   */
  async generateEvidenceCollectionWorkflow(
    framework: string,
    controlId?: string,
    workflowType: 'comprehensive' | 'quick' = 'comprehensive',
  ): Promise<any> {
    const params = new URLSearchParams({
      framework,
      workflow_type: workflowType,
      ...(controlId && { control_id: controlId }),
    });
    const response = await apiClient.post<any>(
      `/chat/evidence-collection-workflow?${params.toString()}`
    );
    return response;
  }

  /**
   * Generate customized policy via chat
   */
  async generateCustomizedPolicy(
    framework: string,
    policyType: string,
    customRequirements?: string[],
  ): Promise<any> {
    const params = new URLSearchParams({
      framework,
      policy_type: policyType,
      ...(customRequirements && { custom_requirements: customRequirements.join(',') }),
    });
    const response = await apiClient.post<any>(
      `/chat/generate-policy?${params.toString()}`
    );
    return response;
  }

  /**
   * Get smart compliance guidance
   */
  async getSmartComplianceGuidance(
    framework: string,
    guidanceType: 'getting_started' | 'next_steps' | 'optimization' = 'getting_started',
  ): Promise<any> {
    const response = await apiClient.get<any>('/chat/smart-compliance-guidance', {
      params: { framework, guidance_type: guidanceType },
    });
    return response;
  }

  /**
   * Get AI cache metrics
   */
  async getCacheMetrics(): Promise<any> {
    const response = await apiClient.get<any>('/ai/optimization/cache/metrics');
    return response;
  }

  /**
   * Clear AI cache
   */
  async clearCache(pattern: string = '*'): Promise<{
    cleared_entries: number;
    pattern: string;
    cleared_at: string;
  }> {
    const response = await apiClient.delete<any>(`/ai/optimization/cache/clear?pattern=${encodeURIComponent(pattern)}`);
    return response;
  }

  /**
   * Get AI performance metrics
   */
  async getPerformanceMetrics(): Promise<any> {
    const response = await apiClient.get<any>('/chat/performance/metrics');
    return response;
  }

  /**
   * Get WebSocket URL for a conversation
   */
  getWebSocketUrl(conversationId: string): string {
    return `${env.NEXT_PUBLIC_WEBSOCKET_URL}/${conversationId}`;
  }

  /**
   * WebSocket connection for real-time chat
   */
  connectWebSocket(conversationId: string): void {
    this.currentConversationId = conversationId;
    const wsUrl = this.getWebSocketUrl(conversationId);
    this.connectWebSocketWithUrl(wsUrl);
  }

  /**
   * Connect WebSocket with custom URL (includes auth token)
   */
  connectWebSocketWithUrl(wsUrl: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.close();
    }

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
    // TODO: Replace with proper logging
      this.notifyHandlers({ type: 'connection', data: { status: 'connected' } });
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.notifyHandlers({ type: 'message', data: message });
      } catch (error) {
        // TODO: Replace with proper logging

        // // TODO: Replace with proper logging
      }
    };

    this.ws.onerror = (error) => {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging
      this.notifyHandlers({ type: 'error', data: error });
    };

    this.ws.onclose = () => {
    // TODO: Replace with proper logging
      this.notifyHandlers({ type: 'connection', data: { status: 'disconnected' } });

      // Attempt to reconnect after 3 seconds
      this.reconnectTimeout = setTimeout(() => {
        if (this.currentConversationId) {
          this.connectWebSocket(this.currentConversationId);
        }
      }, 3000);
    };
  }

  /**
   * Send message via WebSocket
   */
  sendWebSocketMessage(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      // TODO: Replace with proper logging

      // // TODO: Replace with proper logging
    }
  }

  /**
   * Add WebSocket message handler
   */
  addMessageHandler(handler: (message: ChatWebSocketMessage) => void): () => void {
    this.messageHandlers.push(handler);

    // Return cleanup function
    return () => {
      this.messageHandlers = this.messageHandlers.filter((h) => h !== handler);
    };
  }

  /**
   * Notify all message handlers
   */
  private notifyHandlers(message: ChatWebSocketMessage): void {
    this.messageHandlers.forEach((handler) => handler(message));
  }

  /**
   * Disconnect WebSocket
   */
  disconnectWebSocket(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.messageHandlers = [];
  }
}

export const chatService = new ChatService();
