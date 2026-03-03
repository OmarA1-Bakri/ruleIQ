/**
 * IQ Agent TypeScript Types
 * 
 * Complete type definitions matching the sophisticated GraphRAG backend schemas
 * and documented Postman API collection endpoints.
 */

// Base Response Types
export interface BaseResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// ===== COMPLIANCE QUERY TYPES =====

export interface IQComplianceQueryRequest {
  query: string;
  context?: {
    business_functions?: string[];
    regulations?: string[];
    risk_tolerance?: 'low' | 'medium' | 'high';
    [key: string]: any;
  };
  include_graph_analysis?: boolean;
  include_recommendations?: boolean;
}

export interface ComplianceSummary {
  risk_posture: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  compliance_score: number; // 0.0 to 1.0
  top_gaps: string[];
  immediate_actions: string[];
}

export interface ActionPlan {
  action_id: string;
  action_type: string;
  target: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  regulation: string;
  risk_level: string;
  cost_estimate: number;
  timeline: string;
  graph_reference: string;
}

export interface ComplianceArtifacts {
  compliance_posture: {
    overall_coverage: number;
    total_gaps: number;
    critical_gaps: number;
    high_risk_gaps: number;
    [key: string]: any;
  };
  action_plan: ActionPlan[];
  risk_assessment: {
    convergence_patterns: number;
    recent_regulatory_changes: number;
    overall_risk_level: string;
    planning_horizon: string;
    [key: string]: any;
  };
}

export interface GraphContext {
  nodes_traversed: number;
  patterns_detected: Array<{
    pattern_type: string;
    confidence: number;
    description: string;
    implications: string[];
    [key: string]: any;
  }>;
  memories_accessed: string[];
  learnings_applied: number;
  [key: string]: any;
}

export interface ComplianceEvidence {
  controls_executed: number;
  evidence_stored: number;
  metrics_updated: number;
}

export interface NextAction {
  action: string;
  priority: string;
  owner: string;
  graph_reference: string;
}

export interface IQAgentResponse {
  status: 'success' | 'error' | 'processing';
  timestamp: string;
  summary: ComplianceSummary;
  artifacts: ComplianceArtifacts;
  graph_context: GraphContext;
  evidence: ComplianceEvidence;
  next_actions: NextAction[];
  llm_response: string;
}

export interface IQComplianceQueryResponse {
  success: boolean;
  data: IQAgentResponse;
  message?: string;
  processing_time_ms?: number;
}

// ===== MEMORY MANAGEMENT TYPES =====

export interface IQMemoryStoreRequest {
  memory_type: 'compliance_insight' | 'enforcement_case' | 'regulatory_change' | 'risk_assessment' | 'best_practice';
  content: Record<string, any>;
  importance_score: number; // 0.0 to 1.0
  tags?: string[];
}

export interface IQMemoryStoreResponse {
  success: boolean;
  data: {
    memory_id: string;
    status: 'stored' | 'updated' | 'failed';
  };
  message: string;
}

export interface IQMemoryRetrievalRequest {
  query: string;
  max_memories?: number; // 1-50, default 10
  relevance_threshold?: number; // 0.0-1.0, default 0.5
}

export interface MemoryNode {
  id: string;
  memory_type: string;
  content: Record<string, any>;
  timestamp: string;
  importance_score: number;
  access_count: number;
  tags: string[];
  confidence_score: number;
}

export interface IQMemoryRetrievalResponse {
  success: boolean;
  data: {
    query_id: string;
    retrieved_memories: MemoryNode[];
    relevance_scores: number[];
    total_memories_searched: number;
    retrieval_strategy: string;
    confidence_score: number;
  };
  message: string;
}

// ===== GRAPH INITIALIZATION TYPES =====

export interface IQGraphInitializationRequest {
  clear_existing?: boolean;
  load_sample_data?: boolean;
}

export interface IQGraphInitializationResponse {
  success: boolean;
  data: {
    status: 'completed' | 'failed' | 'in_progress';
    timestamp: string;
    nodes_created: Record<string, number>;
    relationships_created: number;
    message: string;
  };
}

// ===== HEALTH CHECK TYPES =====

export interface IQHealthCheckResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  neo4j_connected: boolean;
  llm_service_available: boolean;
  memory_system_operational: boolean;
  graph_nodes_count?: number;
  last_successful_query?: string;
  uptime_seconds?: number;
  components: {
    neo4j: 'healthy' | 'unhealthy';
    openai: 'healthy' | 'unhealthy';
    memory_manager: 'healthy' | 'unhealthy';
    [key: string]: string;
  };
}

// ===== AGENTIC RAG TYPES (from Postman collection) =====

export interface AgenticRAGRequest {
  query: string;
  document_types?: ('regulation' | 'guidance' | 'policy' | 'evidence')[];
  max_results?: number;
  framework?: string;
  section?: string;
  context_window?: number;
}

export interface AgenticRAGResponse {
  query: string;
  results: Array<{
    document_id: string;
    title: string;
    content: string;
    relevance_score: number;
    document_type: string;
    framework?: string;
    section?: string;
    metadata: Record<string, any>;
  }>;
  total_results: number;
  processing_time_ms: number;
}

export interface MultiDocumentRAGRequest {
  queries: string[];
  framework: string;
  combine_results: boolean;
  max_results_per_query?: number;
}

// ===== TRUST GRADIENT TYPES =====

export type TrustLevel = 'helper' | 'advisor' | 'partner';

export interface TrustGradientStatus {
  current_level: TrustLevel;
  progression_score: number; // 0.0 to 1.0
  interactions_count: number;
  success_rate: number;
  user_feedback_score: number;
  estimated_progression_time: string;
  next_level_requirements: string[];
}

// ===== STREAMING TYPES =====

export interface IQStreamingResponse {
  type: 'progress' | 'result' | 'error' | 'complete';
  stage?: 'perceiving' | 'planning' | 'acting' | 'learning' | 'remembering' | 'responding';
  progress?: number; // 0-100
  message?: string;
  data?: Partial<IQAgentResponse>;
  error?: string;
}

// ===== UTILITY TYPES =====

export interface ComplianceFramework {
  id: string;
  name: string;
  description: string;
  jurisdiction: string;
  mandatory_controls: number;
  optional_controls: number;
  complexity_score: number;
}

export interface RiskAssessment {
  id: string;
  framework: string;
  overall_risk: 'low' | 'medium' | 'high' | 'critical';
  risk_factors: Array<{
    category: string;
    score: number;
    description: string;
    mitigation: string;
  }>;
  recommendations: string[];
  next_review_date: string;
}

export interface ComplianceGap {
  gap_id: string;
  regulation: {
    code: string;
    name: string;
    jurisdiction: string;
  };
  requirement: {
    id: string;
    title: string;
    description: string;
    risk_level: 'low' | 'medium' | 'high' | 'critical';
    mandatory: boolean;
  };
  gap_severity_score: number;
  impact_assessment: string;
  recommended_actions: ActionPlan[];
}

// ===== ERROR TYPES =====

export interface IQAgentError {
  error_type: 'network' | 'validation' | 'processing' | 'rate_limit' | 'service_unavailable';
  message: string;
  details?: Record<string, any>;
  retry_after?: number; // seconds
  correlation_id?: string;
}

// ===== ALL TYPES EXPORTED INLINE ABOVE =====