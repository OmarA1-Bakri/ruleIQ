/**
 * TypeScript Schema Definitions for AI Responses
 *
 * These schemas match the Python Pydantic models in the backend for
 * comprehensive type safety in Phase 6 implementation.
 */

// =====================================================================
// Core Enums and Types
// =====================================================================

export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';
export type PriorityLevel = 'low' | 'medium' | 'high' | 'urgent';
export type ImplementationEffort = 'minimal' | 'low' | 'medium' | 'high' | 'extensive';
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type MaturityLevel = 'initial' | 'developing' | 'defined' | 'managed' | 'optimized';
export type TrendDirection = 'improving' | 'stable' | 'declining';
export type InsightType = 'strength' | 'weakness' | 'opportunity' | 'threat';
export type IntentType =
  | 'evidence_query'
  | 'compliance_check'
  | 'guidance_request'
  | 'general_query'
  | 'assessment_help';
export type ExpectedAnswerType = 'text' | 'boolean' | 'multiple_choice' | 'numeric';
export type ValidationStatus = 'valid' | 'invalid' | 'partially_valid';

// =====================================================================
// Gap Analysis Schemas
// =====================================================================

export interface Gap {
  id: string;
  title: string;
  description: string;
  severity: SeverityLevel;
  category: string;
  framework_reference: string;
  current_state: string;
  target_state: string;
  impact_description: string;
  business_impact_score: number; // 0.0 - 1.0
  technical_complexity: number; // 0.0 - 1.0
  regulatory_requirement: boolean;
  estimated_effort: ImplementationEffort;
  dependencies: string[];
  affected_systems: string[];
  stakeholders: string[];
}

export interface GapAnalysisResponse {
  gaps: Gap[];
  overall_risk_level: RiskLevel;
  priority_order: string[]; // Gap IDs in priority order
  estimated_total_effort: string;
  critical_gap_count: number;
  medium_high_gap_count: number;
  compliance_percentage: number; // 0.0 - 100.0
  framework_coverage: Record<string, number>; // Framework -> coverage %
  summary: string;
  next_steps: string[];
}

// =====================================================================
// Recommendation Schemas
// =====================================================================

export interface Recommendation {
  id: string;
  title: string;
  description: string;
  priority: PriorityLevel;
  category: string;
  framework_references: string[];
  addresses_gaps: string[]; // Gap IDs this addresses
  effort_estimate: ImplementationEffort;
  implementation_timeline: string;
  impact_score: number; // 0.0 - 1.0
  cost_estimate?: string;
  resource_requirements: string[];
  success_criteria: string[];
  potential_challenges: string[];
  mitigation_strategies: string[];
  automation_potential: number; // 0.0 - 1.0
  roi_estimate?: string;
}

export interface ImplementationPhase {
  phase_number: number;
  phase_name: string;
  duration_weeks: number;
  deliverables: string[];
  dependencies: string[];
  resources_required: string[];
  success_criteria: string[];
}

export interface ImplementationPlan {
  total_duration_weeks: number;
  phases: ImplementationPhase[];
  resource_allocation: Record<string, string>;
  budget_estimate?: string;
  risk_factors: string[];
  success_metrics: string[];
  milestone_checkpoints: string[];
}

export interface RecommendationResponse {
  recommendations: Recommendation[];
  implementation_plan: ImplementationPlan;
  prioritization_rationale: string;
  quick_wins: string[]; // Recommendation IDs for quick wins
  long_term_initiatives: string[]; // Recommendation IDs for long-term
  resource_summary: Record<string, any>;
  timeline_overview: string;
  success_metrics: string[];
}

// =====================================================================
// Assessment Analysis Schemas
// =====================================================================

export interface RiskAssessment {
  overall_risk_level: RiskLevel;
  risk_score: number; // 0.0 - 100.0
  top_risk_factors: string[];
  risk_mitigation_priorities: string[];
  regulatory_compliance_risk: number;
  operational_risk: number;
  reputational_risk: number;
  financial_risk: number;
}

export interface ComplianceInsight {
  insight_type: InsightType;
  title: string;
  description: string;
  impact_level: SeverityLevel;
  framework_area: string;
  actionable_steps: string[];
}

export interface EvidenceRequirement {
  evidence_type: string;
  description: string;
  framework_reference: string;
  priority: PriorityLevel;
  collection_method: string;
  automation_potential: number; // 0.0 - 1.0
  estimated_effort: ImplementationEffort;
  validation_criteria: string[];
  retention_period?: string;
}

export interface ComplianceMetrics {
  overall_compliance_score: number; // 0.0 - 100.0
  framework_scores: Record<string, number>;
  maturity_level: MaturityLevel;
  coverage_percentage: number; // 0.0 - 100.0
  gap_count_by_severity: Record<SeverityLevel, number>;
  improvement_trend: TrendDirection;
}

export interface AssessmentAnalysisResponse {
  gaps: Gap[];
  recommendations: Recommendation[];
  risk_assessment: RiskAssessment;
  compliance_insights: ComplianceInsight[];
  evidence_requirements: EvidenceRequirement[];
  compliance_metrics: ComplianceMetrics;
  executive_summary: string;
  detailed_findings: string;
  next_steps: string[];
  confidence_score: number; // 0.0 - 1.0
}

// =====================================================================
// Help and Guidance Schemas
// =====================================================================

export interface GuidanceResponse {
  guidance: string;
  confidence_score: number; // 0.0 - 1.0
  related_topics: string[];
  follow_up_suggestions: string[];
  source_references: string[];
  examples: string[];
  best_practices: string[];
  common_pitfalls: string[];
  implementation_tips: string[];
}

export interface FollowUpQuestion {
  question_id: string;
  question_text: string;
  category: string;
  importance_level: PriorityLevel;
  expected_answer_type: ExpectedAnswerType;
  context: string;
  validation_criteria: string[];
}

export interface FollowUpResponse {
  follow_up_questions: FollowUpQuestion[];
  recommendations: string[];
  confidence_score: number; // 0.0 - 1.0
  assessment_completeness: number; // 0.0 - 1.0
  priority_areas: string[];
  suggested_next_steps: string[];
}

// =====================================================================
// Evidence and Workflow Schemas
// =====================================================================

export interface EvidenceItem {
  evidence_id: string;
  title: string;
  description: string;
  framework_controls: string[];
  collection_method: string;
  automation_tools: string[];
  effort_estimate: ImplementationEffort;
  priority: PriorityLevel;
  frequency: string; // "one-time", "quarterly", "annually", etc.
  owner_role: string;
  validation_requirements: string[];
  retention_period: string;
}

export interface WorkflowStep {
  step_number: number;
  title: string;
  description: string;
  estimated_duration: string;
  assigned_role: string;
  prerequisites: string[];
  deliverables: string[];
  validation_criteria: string[];
  automation_opportunities: string[];
}

export interface WorkflowPhase {
  phase_number: number;
  phase_name: string;
  objective: string;
  steps: WorkflowStep[];
  estimated_duration: string;
  success_criteria: string[];
  dependencies: string[];
}

export interface EvidenceWorkflow {
  workflow_id: string;
  title: string;
  description: string;
  framework: string;
  control_reference: string;
  phases: WorkflowPhase[];
  total_estimated_duration: string;
  required_roles: string[];
  automation_percentage: number;
  complexity_level: 'simple' | 'moderate' | 'complex';
}

// =====================================================================
// Policy Generation Schemas
// =====================================================================

export interface PolicySection {
  section_number: string;
  title: string;
  content: string;
  subsections: Array<{ title: string; content: string }>;
  compliance_references: string[];
  implementation_notes: string[];
}

export interface PolicyDocument {
  policy_id: string;
  title: string;
  version: string;
  effective_date: string;
  framework_compliance: string[];
  sections: PolicySection[];
  approval_workflow: string[];
  review_schedule: string;
  related_documents: string[];
  implementation_guidance: string;
}

// =====================================================================
// Chat and Conversation Schemas
// =====================================================================

export interface IntentClassification {
  intent_type: IntentType;
  confidence: number; // 0.0 - 1.0
  entities: Record<string, string[]>;
  context_requirements: string[];
  suggested_actions: string[];
}

export interface ChatResponse {
  response_text: string;
  intent_classification: IntentClassification;
  confidence_score: number; // 0.0 - 1.0
  follow_up_suggestions: string[];
  related_resources: string[];
  action_items: string[];
}

// =====================================================================
// Meta Response Schemas
// =====================================================================

export interface ResponseMetadata {
  response_id: string;
  timestamp: string;
  model_used: string;
  processing_time_ms: number;
  confidence_score: number; // 0.0 - 1.0
  schema_version: string;
  validation_status: ValidationStatus;
  validation_errors: string[];
}

export interface StructuredAIResponse<T = any> {
  metadata: ResponseMetadata;
  response_type: string;
  payload: T;
  validation_passed: boolean;
  fallback_used: boolean;
}

// =====================================================================
// Error and Validation Schemas
// =====================================================================

export interface ValidationError {
  field_path: string;
  error_type: string;
  error_message: string;
  expected_type: string;
  actual_value: any;
  suggestion?: string;
}

export interface SchemaValidationResult {
  is_valid: boolean;
  schema_name: string;
  validation_errors: ValidationError[];
  warnings: string[];
  validation_timestamp: string;
  corrected_data?: Record<string, any>;
}

// =====================================================================
// Union Types
// =====================================================================

export type AIResponsePayload =
  | GapAnalysisResponse
  | RecommendationResponse
  | AssessmentAnalysisResponse
  | GuidanceResponse
  | FollowUpResponse
  | ChatResponse
  | PolicyDocument
  | EvidenceWorkflow;

export type AIResponseType =
  | 'gap_analysis'
  | 'recommendations'
  | 'assessment_analysis'
  | 'guidance'
  | 'followup'
  | 'intent_classification'
  | 'chat'
  | 'policy'
  | 'workflow';

// =====================================================================
// Type Guards
// =====================================================================

export function isGapAnalysisResponse(response: any): response is GapAnalysisResponse {
  return (
    response !== null &&
    response !== undefined &&
    typeof response === 'object' &&
    'gaps' in response &&
    'overall_risk_level' in response &&
    'compliance_percentage' in response
  );
}

export function isRecommendationResponse(response: any): response is RecommendationResponse {
  return (
    response &&
    typeof response === 'object' &&
    'recommendations' in response &&
    'implementation_plan' in response &&
    'prioritization_rationale' in response
  );
}

export function isAssessmentAnalysisResponse(
  response: any,
): response is AssessmentAnalysisResponse {
  return (
    response &&
    typeof response === 'object' &&
    'gaps' in response &&
    'recommendations' in response &&
    'risk_assessment' in response &&
    'compliance_metrics' in response
  );
}

export function isGuidanceResponse(response: any): response is GuidanceResponse {
  return (
    response &&
    typeof response === 'object' &&
    'guidance' in response &&
    'confidence_score' in response &&
    'related_topics' in response
  );
}

export function isFollowUpResponse(response: any): response is FollowUpResponse {
  return (
    response &&
    typeof response === 'object' &&
    'follow_up_questions' in response &&
    'assessment_completeness' in response
  );
}

export function isStructuredAIResponse(response: any): response is StructuredAIResponse {
  return (
    response &&
    typeof response === 'object' &&
    'metadata' in response &&
    'response_type' in response &&
    'payload' in response &&
    'validation_passed' in response
  );
}

export function isValidationError(error: unknown): error is ValidationError {
  return (
    !!error &&
    typeof error === 'object' &&
    'field_path' in error &&
    'error_type' in error &&
    'error_message' in error
  );
}

// =====================================================================
// Response Type Mapping
// =====================================================================

export const RESPONSE_TYPE_SCHEMAS = {
  gap_analysis: 'GapAnalysisResponse',
  recommendations: 'RecommendationResponse',
  assessment_analysis: 'AssessmentAnalysisResponse',
  guidance: 'GuidanceResponse',
  followup: 'FollowUpResponse',
  intent_classification: 'IntentClassification',
  chat: 'ChatResponse',
  policy: 'PolicyDocument',
  workflow: 'EvidenceWorkflow',
} as const;

export type ResponseTypeKeys = keyof typeof RESPONSE_TYPE_SCHEMAS;

// =====================================================================
// Utility Functions
// =====================================================================

export function getResponseTypeName(response_type: string): string {
  return RESPONSE_TYPE_SCHEMAS[response_type as ResponseTypeKeys] || 'Unknown';
}

export function isValidResponseType(response_type: string): response_type is ResponseTypeKeys {
  return response_type in RESPONSE_TYPE_SCHEMAS;
}

export function validateSeverityLevel(level: string): level is SeverityLevel {
  return ['low', 'medium', 'high', 'critical'].includes(level);
}

export function validatePriorityLevel(level: string): level is PriorityLevel {
  return ['low', 'medium', 'high', 'urgent'].includes(level);
}

export function validateMaturityLevel(level: string): level is MaturityLevel {
  return ['initial', 'developing', 'defined', 'managed', 'optimized'].includes(level);
}
