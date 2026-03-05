/**
 * IQ Agent Service
 *
 * Service layer for communicating with the IQ Agent (GraphRAG) backend endpoints.
 * Provides compliance query, memory management, health check, and context extraction.
 */

import { apiClient } from './client';
import type {
  IQComplianceQueryRequest,
  IQComplianceQueryResponse,
  IQHealthCheckResponse,
  IQMemoryStoreRequest,
  IQMemoryStoreResponse,
  IQMemoryRetrievalRequest,
  IQMemoryRetrievalResponse,
  IQGraphInitializationRequest,
  IQGraphInitializationResponse,
  IQAgentError,
} from '@/types/iq-agent';

// Compliance-related keywords for query detection
const COMPLIANCE_KEYWORDS = [
  'gdpr', 'iso 27001', 'iso27001', 'compliance', 'regulation',
  'data protection', 'privacy', 'audit', 'risk assessment',
  'security controls', 'framework', 'certification',
  'pci dss', 'hipaa', 'sox', 'nist', 'cyber essentials',
  'information security', 'data breach', 'incident response',
  'access control', 'encryption', 'vulnerability',
  'penetration test', 'policy', 'procedure', 'evidence',
  'control', 'gap analysis', 'remediation',
];

class IQAgentService {
  /**
   * Send a compliance query to the IQ Agent
   */
  async queryCompliance(
    query: string,
    context?: IQComplianceQueryRequest['context'],
    options?: {
      include_graph_analysis?: boolean;
      include_recommendations?: boolean;
    }
  ): Promise<IQComplianceQueryResponse> {
    const request: Record<string, unknown> = {
      query,
      include_graph_analysis: options?.include_graph_analysis ?? true,
      include_recommendations: options?.include_recommendations ?? true,
    };
    if (context !== undefined) {
      request.context = context;
    }

    const response = await apiClient.post<IQComplianceQueryResponse>(
      '/iq/query',
      request,
    );
    return response;
  }

  /**
   * Check IQ Agent health status
   */
  async getHealth(): Promise<IQHealthCheckResponse> {
    const response = await apiClient.get<IQHealthCheckResponse>('/iq/health');
    return response;
  }

  /**
   * Store a memory in the IQ Agent memory system
   */
  async storeMemory(data: IQMemoryStoreRequest): Promise<IQMemoryStoreResponse> {
    const response = await apiClient.post<IQMemoryStoreResponse>(
      '/iq/memory/store',
      data,
    );
    return response;
  }

  /**
   * Retrieve memories from the IQ Agent
   */
  async retrieveMemories(data: IQMemoryRetrievalRequest): Promise<IQMemoryRetrievalResponse> {
    const response = await apiClient.post<IQMemoryRetrievalResponse>(
      '/iq/memory/retrieve',
      data,
    );
    return response;
  }

  /**
   * Initialize or reset the knowledge graph
   */
  async initializeGraph(
    data?: IQGraphInitializationRequest
  ): Promise<IQGraphInitializationResponse> {
    const response = await apiClient.post<IQGraphInitializationResponse>(
      '/iq/graph/initialize',
      data || {},
    );
    return response;
  }

  /**
   * Determine if a message is a compliance-related query
   */
  isComplianceQuery(message: string): boolean {
    const lowerMessage = message.toLowerCase();
    return COMPLIANCE_KEYWORDS.some((keyword) => lowerMessage.includes(keyword));
  }

  /**
   * Extract context from a compliance query message
   */
  extractContext(message: string): IQComplianceQueryRequest['context'] {
    const lowerMessage = message.toLowerCase();
    const context: IQComplianceQueryRequest['context'] = {};

    // Detect mentioned regulations
    const regulations: string[] = [];
    if (lowerMessage.includes('gdpr')) regulations.push('GDPR');
    if (lowerMessage.includes('iso 27001') || lowerMessage.includes('iso27001')) {
      regulations.push('ISO 27001');
    }
    if (lowerMessage.includes('pci dss')) {
      regulations.push('PCI DSS');
    } else if (lowerMessage.includes('pci')) {
      regulations.push('PCI DSS');
    }
    if (lowerMessage.includes('hipaa')) regulations.push('HIPAA');
    if (lowerMessage.includes('sox')) regulations.push('SOX');
    if (lowerMessage.includes('nist')) regulations.push('NIST');
    if (lowerMessage.includes('cyber essentials')) regulations.push('Cyber Essentials');

    if (regulations.length > 0) {
      context.regulations = regulations;
    }

    // Detect risk tolerance from language
    if (
      lowerMessage.includes('urgent') ||
      lowerMessage.includes('critical') ||
      lowerMessage.includes('immediately')
    ) {
      context.risk_tolerance = 'low';
    } else if (lowerMessage.includes('moderate') || lowerMessage.includes('balanced')) {
      context.risk_tolerance = 'medium';
    } else {
      context.risk_tolerance = 'high';
    }

    return context;
  }
}

export const iqAgentService = new IQAgentService();
export type { IQAgentError };
