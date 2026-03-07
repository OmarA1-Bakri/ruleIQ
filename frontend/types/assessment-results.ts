/**
 * Comprehensive type definitions for assessment results and export functionality
 * Extends basic assessment types with detailed UI display and analytics capabilities
 */

import { AssessmentResult, Gap, Recommendation, Answer } from '@/lib/assessment-engine/types';
import { BusinessProfile, Assessment } from '@/types/api';

// ============================================================================
// CORE ASSESSMENT RESULTS TYPES
// ============================================================================

export interface DetailedAssessmentResults extends AssessmentResult {
  // Basic assessment info
  businessProfile: BusinessProfile;
  frameworkName: string;
  assessmentTitle: string;
  
  // Enhanced scoring details
  sectionDetails: SectionScoreDetail[];
  questionResponses: QuestionResponse[];
  
  // Historical and trend data
  historicalData: HistoricalAssessment[];
  trendData: TrendDataPoint[];
  
  // Export and metadata
  exportMetadata: ExportMetadata;
  
  // UI display enhancements
  displayMetrics: DisplayMetrics;
  
  // Comparison data
  benchmarkData?: BenchmarkData;
  
  // Additional analysis
  riskAssessment: RiskAssessment;
  complianceStatus: ComplianceStatusDetail;
}

export interface SectionScoreDetail {
  sectionId: string;
  sectionName: string;
  sectionDescription?: string;
  score: number;
  maxScore: number;
  percentage: number;
  
  // Question breakdown
  totalQuestions: number;
  answeredQuestions: number;
  skippedQuestions: number;
  
  // Status indicators
  completionStatus: 'complete' | 'partial' | 'not_started';
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  
  // Analysis
  strengths: string[];
  weaknesses: string[];
  keyFindings: string[];
  
  // Question details
  questionBreakdown: QuestionScoreDetail[];
  
  // Recommendations specific to this section
  sectionRecommendations: Recommendation[];
  
  // Gaps specific to this section
  sectionGaps: Gap[];
  
  // Trend data for this section
  historicalScores: SectionHistoricalScore[];
}

export interface QuestionScoreDetail {
  questionId: string;
  questionText: string;
  questionType: string;
  section: string;
  category: string;
  
  // Scoring
  score: number;
  maxScore: number;
  weight: number;
  
  // Response details
  userAnswer: any;
  expectedAnswer?: any;
  isCorrect: boolean;
  
  // Analysis
  impact: 'low' | 'medium' | 'high' | 'critical';
  riskContribution: number;
  
  // Metadata
  timeSpent?: number;
  confidence?: number;
  source: 'framework' | 'ai' | 'manual';
  
  // Related items
  relatedGaps: string[];
  relatedRecommendations: string[];
}

export interface QuestionResponse {
  questionId: string;
  questionText: string;
  answer: Answer;
  score: number;
  maxScore: number;
  section: string;
  category: string;
  timestamp: Date;
  timeSpent?: number;
  confidence?: number;
}

// ============================================================================
// HISTORICAL AND TREND DATA TYPES
// ============================================================================

export interface HistoricalAssessment {
  assessmentId: string;
  frameworkId: string;
  frameworkName: string;
  completedAt: Date;
  overallScore: number;
  sectionScores: Record<string, number>;
  maturityLevel?: 'initial' | 'developing' | 'defined' | 'managed' | 'optimized';
  totalQuestions: number;
  answeredQuestions: number;
  version?: string;
  
  // Comparison metrics
  scoreChange?: number;
  scoreChangePercentage?: number;
  improvementAreas: string[];
  regressionAreas: string[];
}

export interface TrendDataPoint {
  date: string; // ISO string for consistency across serialization
  overallScore: number;
  sectionScores: Record<string, number>;

  // Change indicators
  scoreChange?: number;
  scoreChangePercentage?: number;
  trend?: 'improving' | 'declining' | 'stable';

  // Additional metrics
  completionRate?: number;
  riskScore?: number;
  completionPercentage?: number;
  maturityLevel?: 'initial' | 'developing' | 'defined' | 'managed' | 'optimized';

  // Metadata
  assessmentId: string;
  frameworkVersion?: string;
  questionCount?: number;

  // Change tracking
  changeFromPrevious?: {
    overallScore: number;
    riskScore: number;
    completionPercentage: number;
  };

  // Comparative data
  industryAverage?: number;
  peerComparison?: 'above' | 'below' | 'average';
}

export interface SectionHistoricalScore {
  date: Date;
  score: number;
  percentage: number;
  change: number;
  changePercentage: number;
  trend: 'improving' | 'declining' | 'stable';
}

// ============================================================================
// EXPORT FUNCTIONALITY TYPES
// ============================================================================

// Import and re-export the unified ExportOptions from export.ts
// This ensures a single source of truth for ExportOptions type
import type { ExportOptions } from '@/lib/utils/export';
export type { ExportOptions } from '@/lib/utils/export';

export interface ExportMetadata {
  exportId: string;
  generatedAt: Date;
  generatedBy: string;
  format: string;
  fileSize?: number;
  downloadUrl?: string;
  expiresAt?: Date;
  
  // Export statistics
  totalPages?: number;
  totalRecords: number;
  processingTime: number;
  
  // Version info
  dataVersion: string;
  exportVersion: string;
  
  // Security
  checksum?: string;
  encrypted: boolean;
}

export interface ExportProgress {
  exportId: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number; // 0-100
  currentStep: string;
  totalSteps: number;
  estimatedTimeRemaining?: number;
  
  // Error handling
  error?: string;
  retryCount: number;
  
  // Timestamps
  startedAt: Date;
  completedAt?: Date;
  lastUpdated: Date;
}

// ============================================================================
// DISPLAY AND UI TYPES
// ============================================================================

export interface DisplayMetrics {
  // Summary statistics
  totalQuestions: number;
  answeredQuestions: number;
  skippedQuestions: number;
  completionPercentage: number;
  
  // Time metrics
  assessmentDuration: number; // in minutes
  averageTimePerQuestion: number;
  
  // Score distribution
  scoreDistribution: {
    excellent: number; // 90-100%
    good: number; // 70-89%
    fair: number; // 50-69%
    poor: number; // 0-49%
  };
  
  // Risk metrics
  criticalIssues: number;
  highRiskItems: number;
  mediumRiskItems: number;
  lowRiskItems: number;
  
  // Improvement metrics
  quickWins: number;
  longTermGoals: number;
  
  // Comparison metrics
  industryRanking?: number;
  industryPercentile?: number;
  
  // Next steps
  nextAssessmentDate?: Date;
  recommendedActions: number;
  priorityActions: number;
}

export interface BenchmarkData {
  industryAverage: number;
  industryMedian: number;
  industryTop10: number;
  
  // Peer comparison
  peerAverage?: number;
  peerRanking?: number;
  totalPeers?: number;
  
  // Size-based comparison
  sizeBasedAverage?: number;
  sizeBasedRanking?: number;
  
  // Regional comparison
  regionalAverage?: number;
  regionalRanking?: number;
  
  // Metadata
  benchmarkDate: Date;
  sampleSize: number;
  dataSource: string;
}

export interface RiskAssessment {
  overallRiskScore: number;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  
  // Risk breakdown
  riskByCategory: Record<string, {
    score: number;
    level: 'low' | 'medium' | 'high' | 'critical';
    description: string;
  }>;
  
  // Top risks
  topRisks: Array<{
    category: string;
    description: string;
    impact: 'low' | 'medium' | 'high' | 'critical';
    likelihood: 'low' | 'medium' | 'high' | 'critical';
    mitigation: string;
  }>;
  
  // Risk trends
  riskTrend: 'improving' | 'declining' | 'stable';
  riskChangePercentage: number;
  
  // Compliance risks
  complianceRisks: Array<{
    framework: string;
    riskLevel: 'low' | 'medium' | 'high' | 'critical';
    description: string;
    regulatoryImpact: string;
  }>;
}

export interface ComplianceStatusDetail {
  overallStatus: 'compliant' | 'partial' | 'non_compliant' | 'not_assessed';
  compliancePercentage: number;
  
  // Framework-specific status
  frameworkCompliance: Record<string, {
    status: 'compliant' | 'partial' | 'non_compliant' | 'not_assessed';
    percentage: number;
    lastAssessed: Date;
    nextReview: Date;
    criticalGaps: number;
  }>;
  
  // Regulatory requirements
  regulatoryRequirements: Array<{
    requirement: string;
    status: 'met' | 'partial' | 'not_met' | 'not_applicable';
    evidence: string[];
    gaps: string[];
  }>;
  
  // Certification status
  certifications: Array<{
    name: string;
    status: 'active' | 'expired' | 'pending' | 'not_applicable';
    expiryDate?: Date;
    renewalDate?: Date;
    issuer: string;
  }>;
  
  // Audit readiness
  auditReadiness: {
    score: number;
    level: 'ready' | 'mostly_ready' | 'needs_work' | 'not_ready';
    missingItems: string[];
    recommendedActions: string[];
  };
}

// ============================================================================
// CHART AND VISUALIZATION TYPES
// ============================================================================

export interface ChartDataPoint {
  date: string;
  value: number;
  label?: string;
  color?: string;
  metadata?: Record<string, any>;
}

export interface SectionChartData {
  sectionName: string;
  data: ChartDataPoint[];
  color: string;
  trend: 'improving' | 'declining' | 'stable';
}

export interface ComparisonChartData {
  category: string;
  userScore: number;
  industryAverage: number;
  bestPractice: number;
  gap: number;
}

// ============================================================================
// UTILITY AND HELPER TYPES
// ============================================================================

export interface AssessmentSummary {
  assessmentId: string;
  title: string;
  framework: string;
  completedAt: Date;
  score: number;
  status: 'completed' | 'in_progress' | 'draft';
  duration: number;
  questionsAnswered: number;
  totalQuestions: number;
}

export interface ExportJob {
  jobId: string;
  assessmentId: string;
  options: ExportOptions;
  progress: ExportProgress;
  result?: {
    fileUrl: string;
    fileName: string;
    fileSize: number;
  };
}

export interface AssessmentComparison {
  baseAssessment: DetailedAssessmentResults;
  compareAssessment: DetailedAssessmentResults;
  
  // Overall comparison
  scoreDifference: number;
  scoreDifferencePercentage: number;
  improvement: boolean;
  
  // Section comparisons
  sectionComparisons: Array<{
    sectionId: string;
    sectionName: string;
    basScore: number;
    compareScore: number;
    difference: number;
    differencePercentage: number;
    improvement: boolean;
  }>;
  
  // Gap analysis
  newGaps: Gap[];
  resolvedGaps: Gap[];
  persistentGaps: Gap[];
  
  // Recommendations
  newRecommendations: Recommendation[];
  completedRecommendations: Recommendation[];
  ongoingRecommendations: Recommendation[];
}

// ============================================================================
// ERROR AND VALIDATION TYPES
// ============================================================================

export interface AssessmentResultsError {
  code: string;
  message: string;
  details?: Record<string, any>;
  timestamp: Date;
  recoverable: boolean;
}

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
  suggestions: string[];
}

// ============================================================================
// ALL TYPES EXPORTED INLINE ABOVE
// ============================================================================