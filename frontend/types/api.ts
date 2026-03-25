// Core API types based on backend schemas

import type {
  PolicyContentStructure,
  QuestionValidationRules,
  IntegrationConfig,
  AlertDetails,
} from '@/lib/validation/zod-schemas';

// User and Authentication
export interface User {
  id: string;
  email: string;
  created_at: string;
  is_active: boolean;
  role?: string;
  permissions?: string[];
  avatar?: string;
  first_name?: string;
  last_name?: string;
  organization_id?: string;
  companyId?: string; // For compatibility with auth.ts
  businessProfile?: {
    id: string;
    company_name: string;
    industry: string;
  };
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// Business Profile
export interface BusinessProfile {
  id: string;
  user_id: string;
  company_name: string;
  industry: string;
  employee_count: number;
  annual_revenue: string;
  country: string;
  data_sensitivity: 'Low' | 'Moderate' | 'High' | 'Confidential';
  handles_personal_data: boolean;
  processes_payments: boolean;
  stores_health_data: boolean;
  provides_financial_services: boolean;
  operates_critical_infrastructure: boolean;
  has_international_operations: boolean;
  existing_frameworks: string[];
  planned_frameworks: string[];
  cloud_providers: string[];
  saas_tools: string[];
  development_tools: string[];
  compliance_budget: number;
  compliance_timeline: string;
  created_at: string;
  updated_at: string;
}

// Compliance Framework
export interface ComplianceFramework {
  id: string;
  name: string;
  description: string;
  category: string;
  region?: string;
  industries: string[];
  controls_count: number;
  implementation_time: string;
  difficulty_level: 'Low' | 'Medium' | 'High';
  certifiable: boolean;
  tags: string[];
  created_at: string;
  updated_at: string;
}

// Evidence Management
export interface EvidenceItem {
  id: string;
  title: string;
  description: string;
  control_id: string;
  framework_id: string;
  business_profile_id: string;
  evidence_type: string;
  source: string;
  tags: string[];
  status: 'pending' | 'collected' | 'approved' | 'rejected' | 'needs_review';
  quality_score?: number;
  metadata?: Record<string, unknown>;
  file_url?: string;
  file_name?: string;
  file_size?: number;
  created_at: string;
  updated_at: string;
}

// Policy Management
export interface Policy {
  id: string;
  user_id: string;
  business_profile_id: string;
  framework_id: string;
  policy_name: string;
  framework_name: string;
  policy_type: string;
  generation_prompt?: string;
  generation_time_seconds?: number;
  policy_content: string | PolicyContentStructure;
  sections?: PolicySection[];
  status: 'draft' | 'under_review' | 'approved' | 'active' | 'archived';
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PolicySection {
  title: string;
  content: string;
  order?: number;
}

// Assessment
export interface Assessment {
  id: string;
  title: string;
  name: string; // For test compatibility
  description: string;
  framework_id: string;
  framework_name?: string;
  business_profile_id: string;
  status: 'draft' | 'scheduled' | 'in_progress' | 'under_review' | 'completed' | 'overdue';
  progress: number;
  score?: number;
  max_score?: number;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
  questions_count: number;
  answered_count: number;
  total_questions: number; // For test compatibility
  answered_questions: number; // For test compatibility
}

export interface AssessmentQuestion {
  id: string;
  assessment_id: string;
  question_text: string;
  question_type:
    | 'multiple_choice'
    | 'single_choice'
    | 'text'
    | 'textarea'
    | 'file_upload'
    | 'boolean'
    | 'scale'
    | 'matrix';
  required: boolean;
  order: number;
  section: string;
  control_reference?: string;
  options?: AssessmentQuestionOption[];
  validation_rules?: QuestionValidationRules;
  help_text?: string;
  weight: number;
}

export interface AssessmentQuestionOption {
  id: string;
  text: string;
  value: string | number;
  score: number;
}

export interface AssessmentResponse {
  id: string;
  assessment_id: string;
  question_id: string;
  answer_value: string | string[] | number | boolean;
  score?: number;
  notes?: string;
  evidence_ids?: string[];
  created_at: string;
  updated_at: string;
}

// Chat and AI Assistant
export interface ChatConversation {
  id: string;
  user_id: string;
  business_profile_id?: string;
  title: string;
  status: 'active' | 'archived' | 'deleted';
  message_count: number;
  last_message?: string;
  created_at: string;
  updated_at: string;
  is_pinned?: boolean;
  tags?: string[];
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sequence_number: number;
  metadata?: {
    files?: ChatFile[];
    code_language?: string;
    thinking?: string;
    sources?: string[];
    confidence?: number;
    evidence_references?: string[];
    control_mappings?: string[];
    // IQ Agent specific metadata
    source?: 'iq_agent' | 'regular_chat';
    confidence_score?: number;
    trust_level?: 'helper' | 'advisor' | 'partner';
    evidence_count?: number;
    graph_nodes?: number;
    response_time?: number;
    is_processing?: boolean;
    status?: 'sending' | 'sent' | 'delivered' | 'failed';
  };
  created_at: string;
  is_edited?: boolean;
  edited_at?: string;
}

export interface ChatFile {
  id: string;
  name: string;
  size: number;
  type: string;
  url: string;
  uploaded_at: string;
}

// Reports
export interface Report {
  id: string;
  title: string;
  description?: string;
  report_type: 'compliance' | 'assessment' | 'evidence' | 'executive' | 'audit' | 'custom';
  status: 'generating' | 'completed' | 'failed' | 'scheduled';
  format: 'pdf' | 'word' | 'excel' | 'html';
  business_profile_id?: string;
  assessment_id?: string;
  framework_id?: string;
  date_range?: {
    start_date: string;
    end_date: string;
  };
  file_url?: string;
  file_size?: number;
  generated_by: string;
  created_at: string;
  updated_at: string;
  scheduled_at?: string;
  delivered_at?: string;
  recipients?: string[];
  tags?: string[];
}

// Integration
export interface Integration {
  id: string;
  provider: string;
  provider_id?: string;
  name: string;
  description: string;
  status:
    | 'available'
    | 'connected'
    | 'disconnected'
    | 'error'
    | 'pending'
    | 'pending_auth';
  connection_status?: 'active' | 'inactive' | 'expired' | 'revoked';
  auth_type?: 'oauth2' | 'api_key' | 'basic_auth' | 'custom';
  config?: IntegrationConfig | Record<string, unknown>;
  sync_settings?: {
    auto_sync: boolean;
    sync_frequency: 'realtime' | 'hourly' | 'daily' | 'weekly';
    last_sync?: string;
    next_sync?: string;
  };
  connected_at?: string;
  last_activity?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

// Smart Evidence Collection (from backend analysis)
export interface EvidenceCollectionPlan {
  plan_id: string;
  business_profile_id: string;
  framework: string;
  total_tasks: number;
  estimated_total_hours: number;
  completion_target_date: string;
  tasks: EvidenceTask[];
  automation_opportunities: {
    total_tasks: number;
    automatable_tasks: number;
    automation_percentage: number;
    effort_savings_hours: number;
    effort_savings_percentage: number;
    recommended_tools: string[];
  };
  created_at: string;
}

export interface EvidenceTask {
  task_id: string;
  framework: string;
  control_id: string;
  evidence_type: string;
  title: string;
  description: string;
  priority: 'critical' | 'high' | 'medium' | 'low' | 'deferred';
  automation_level: 'fully_automated' | 'semi_automated' | 'manual' | 'requires_review';
  estimated_effort_hours: number;
  dependencies?: string[];
  assigned_to?: string;
  due_date?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked' | 'cancelled';
  created_at: string;
  metadata?: {
    automation_tools?: string[];
    success_rate?: number;
    base_effort?: number;
    effort_reduction?: number;
  };
}

// Readiness and Gap Analysis
export interface ReadinessScore {
  overall_score: number;
  category_scores: {
    policies: number;
    processes: number;
    technology: number;
    people: number;
  };
  maturity_level: 'initial' | 'developing' | 'defined' | 'managed' | 'optimized';
  strengths: string[];
  weaknesses: string[];
  recommendations: Array<{
    category: string;
    priority: 'high' | 'medium' | 'low';
    description: string;
    effort: string;
    impact: string;
  }>;
}

export interface GapAnalysis {
  framework: string;
  completion_percentage: number;
  critical_gaps: string[];
  gaps: Array<{
    control_id: string;
    control_name: string;
    gap_type: 'missing' | 'partial' | 'outdated';
    current_state: string;
    target_state: string;
    remediation_steps: string[];
    priority: 'critical' | 'high' | 'medium' | 'low';
    estimated_effort: string;
  }>;
  summary: {
    total_gaps: number;
    critical_gaps: number;
    estimated_remediation_time: string;
    quick_wins: string[];
  };
}

// Compliance Status
export interface ComplianceStatus {
  framework: string;
  overall_compliance_percentage: number;
  status: 'compliant' | 'partial' | 'non_compliant' | 'not_assessed';
  last_assessment_date?: string;
  next_review_date?: string;
  by_domain: Array<{
    domain: string;
    compliance_percentage: number;
    controls_compliant: number;
    controls_total: number;
    critical_findings: number;
  }>;
  risk_summary: {
    high_risk_items: number;
    medium_risk_items: number;
    low_risk_items: number;
    remediation_in_progress: number;
  };
}

// Implementation Plan
export interface ImplementationPlan {
  id: string;
  business_profile_id: string;
  framework_id: string;
  framework_name: string;
  status: 'draft' | 'active' | 'completed' | 'on_hold';
  start_date: string;
  target_completion_date: string;
  actual_completion_date?: string;
  overall_progress: number;
  phases: ImplementationPhase[];
  created_at: string;
  updated_at: string;
}

export interface ImplementationPhase {
  id: string;
  phase_number: number;
  name: string;
  description: string;
  start_date: string;
  end_date: string;
  progress: number;
  status: 'not_started' | 'in_progress' | 'completed' | 'blocked';
  tasks: ImplementationTask[];
  deliverables: string[];
  milestones: ImplementationMilestone[];
}

export interface ImplementationTask {
  id: string;
  title: string;
  description: string;
  assigned_to?: string;
  start_date: string;
  due_date: string;
  effort_hours: number;
  progress: number;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  dependencies: string[];
  blockers?: string[];
}

export interface ImplementationMilestone {
  id: string;
  name: string;
  date: string;
  achieved: boolean;
  achieved_date?: string;
  criteria: string[];
}

// Monitoring and Analytics
export interface SystemHealth {
  status: 'healthy' | 'warning' | 'critical';
  uptime: number;
  last_check: string;
  services: {
    database: ServiceStatus;
    redis: ServiceStatus;
    storage: ServiceStatus;
    email: ServiceStatus;
    integrations: ServiceStatus;
  };
  performance: {
    response_time: number;
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
  };
}

export interface ServiceStatus {
  status: 'healthy' | 'warning' | 'critical' | 'down';
  response_time?: number;
  last_check: string;
  error_message?: string;
}

export interface SystemAlert {
  id: string;
  severity: 'critical' | 'warning' | 'info';
  type: string;
  message: string;
  details: AlertDetails;
  created_at: string;
  resolved: boolean;
  resolved_at?: string;
}

// Pagination
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// API Response
export interface ApiResponse<T = unknown> {
  data: T;
  message?: string;
  status: number;
}

// API Error
export interface ApiError {
  detail: string;
  status?: number;
  code?: string;
  field_errors?: Record<string, string[]>;
}
