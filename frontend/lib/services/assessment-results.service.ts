/**
 * Assessment Results Service
 * Manages assessment results data including historical trends and export functionality
 */

import { freemiumService, type AssessmentResultsResponse } from '@/lib/api/freemium.service';
import { normalizeSectionId } from '@/lib/api/frameworks.service';
import type {
  AssessmentResult,
  AssessmentFramework,
  Gap,
  Recommendation
} from '@/lib/assessment-engine/types';
import type {
  FreemiumSession,
  ComplianceGap,
  ComplianceRecommendation
} from '@/types/freemium';
import type { BusinessProfile, Assessment } from '@/types/api';
import type { TrendDataPoint } from '@/types/assessment-results';

// ============================================================================
// TYPES
// ============================================================================

export interface HistoricalAssessment {
  id: string;
  sessionId: string;
  businessProfileId: string;
  frameworkId: string;
  frameworkName: string;
  overallScore: number;
  riskScore: number;
  completionPercentage: number;
  completedAt: string;
  sectionScores: Record<string, number>;
  gapsCount: number;
  recommendationsCount: number;
  metadata?: Record<string, any>;
}

export interface TrendAnalysisData {
  dataPoints: TrendDataPoint[];
  timePeriod: 'last_30_days' | 'last_3_months' | 'last_6_months' | 'last_year' | 'all_time';
  summary: {
    totalAssessments: number;
    averageScore: number;
    scoreImprovement: number;
    bestScore: number;
    worstScore: number;
    latestScore: number;
    trend: 'improving' | 'declining' | 'stable';
  };
  sectionTrends: Record<string, {
    average: number;
    improvement: number;
    trend: 'improving' | 'declining' | 'stable';
  }>;
}

export interface ExportData {
  assessment: {
    id: string;
    sessionId: string;
    frameworkName: string;
    businessProfile: Partial<BusinessProfile>;
    completedAt: string;
    overallScore: number;
    riskScore: number;
    completionPercentage: number;
  };
  sections: Array<{
    name: string;
    score: number;
    questionsTotal: number;
    questionsAnswered: number;
    completionRate: number;
  }>;
  gaps: Array<{
    category: string;
    severity: string;
    description: string;
    recommendation: string;
    estimatedEffort: string;
    regulatoryImpact: string;
  }>;
  recommendations: Array<{
    priority: string;
    category: string;
    title: string;
    description: string;
    implementationGuidance: string;
    estimatedCost: string;
    timeline: string;
    businessImpact: string;
  }>;
  summary: {
    strengths: string[];
    weaknesses: string[];
    criticalAreas: string[];
    nextSteps: string[];
  };
  metadata: {
    exportedAt: string;
    exportedBy?: string;
    reportVersion: string;
  };
}

export interface AssessmentResultsCache {
  [sessionToken: string]: {
    data: AssessmentResultsResponse;
    timestamp: number;
    expiresAt: number;
  };
}

export interface ServiceOptions {
  cacheEnabled?: boolean;
  cacheTTL?: number; // in milliseconds
  enableHistoricalData?: boolean;
  maxHistoricalRecords?: number;
}

// ============================================================================
// SERVICE CLASS
// ============================================================================

class AssessmentResultsService {
  private cache: AssessmentResultsCache = {};
  private historicalData: Map<string, HistoricalAssessment[]> = new Map();
  private options: ServiceOptions;

  constructor(options: ServiceOptions = {}) {
    this.options = {
      cacheEnabled: true,
      cacheTTL: 5 * 60 * 1000, // 5 minutes
      enableHistoricalData: true,
      maxHistoricalRecords: 50,
      ...options,
    };
  }

  // ============================================================================
  // CACHE MANAGEMENT
  // ============================================================================

  private getCachedResults(sessionToken: string): AssessmentResultsResponse | null {
    if (!this.options.cacheEnabled) return null;

    const cached = this.cache[sessionToken];
    if (!cached) return null;

    const now = Date.now();
    if (now > cached.expiresAt) {
      delete this.cache[sessionToken];
      return null;
    }

    return cached.data;
  }

  private setCachedResults(sessionToken: string, data: AssessmentResultsResponse): void {
    if (!this.options.cacheEnabled) return;

    const now = Date.now();
    this.cache[sessionToken] = {
      data,
      timestamp: now,
      expiresAt: now + (this.options.cacheTTL || 5 * 60 * 1000),
    };
  }

  private clearCache(): void {
    this.cache = {};
  }

  private cleanExpiredCache(): void {
    const now = Date.now();
    Object.keys(this.cache).forEach(key => {
      const expiresAt = this.cache[key]?.expiresAt;
      if (expiresAt !== undefined && now > expiresAt) {
        delete this.cache[key];
      }
    });
  }

  // ============================================================================
  // BUSINESS PROFILE KEY RESOLUTION
  // ============================================================================

  /**
   * Get consistent business profile key for trend data
   * Uses session_id during assessment, prefers lead_id once results are available
   */
  getBusinessProfileKey(data: { session_id?: string; lead_id?: string; session_token?: string }): string {
    // Prefer lead_id when available (results phase)
    if (data.lead_id) {
      return data.lead_id;
    }

    // Fall back to session_id during assessment
    if (data.session_id) {
      return data.session_id;
    }

    // Last resort: use session_token
    if (data.session_token) {
      return data.session_token;
    }

    // Default fallback
    return 'unknown-profile';
  }

  // ============================================================================
  // RESULTS FETCHING
  // ============================================================================

  /**
   * Get assessment results with caching
   */
  async getResults(sessionToken: string, forceRefresh = false): Promise<AssessmentResultsResponse> {
    try {
      // Check cache first
      if (!forceRefresh) {
        const cached = this.getCachedResults(sessionToken);
        if (cached) {
          return cached;
        }
      }

      // Fetch from API
      const results = await freemiumService.getResults(sessionToken);
      
      // Validate results
      this.validateResults(results);

      // Cache results
      this.setCachedResults(sessionToken, results);

      // Store in historical data if enabled
      if (this.options.enableHistoricalData) {
        await this.storeHistoricalData(sessionToken, results);
      }

      return results;
    } catch (error) {
      console.error('Failed to get assessment results:', error);
      throw new Error(
        error instanceof Error 
          ? `Failed to fetch results: ${error.message}`
          : 'Failed to fetch assessment results'
      );
    }
  }

  /**
   * Validate assessment results data
   */
  private validateResults(results: AssessmentResultsResponse): void {
    if (!results) {
      throw new Error('Results data is null or undefined');
    }

    if (typeof results.compliance_score !== 'number' || results.compliance_score < 0 || results.compliance_score > 100) {
      throw new Error('Invalid compliance score');
    }

    if (typeof results.risk_score !== 'number' || results.risk_score < 0 || results.risk_score > 100) {
      throw new Error('Invalid risk score');
    }

    if (!Array.isArray(results.compliance_gaps)) {
      throw new Error('Compliance gaps must be an array');
    }

    if (!Array.isArray(results.recommendations)) {
      throw new Error('Recommendations must be an array');
    }
  }

  // ============================================================================
  // HISTORICAL DATA MANAGEMENT
  // ============================================================================

  /**
   * Get assessment history for a business profile
   * Attempts to fetch from API first, falls back to local cache
   */
  // TypeScript overloads for getAssessmentHistory
  async getAssessmentHistory(
    businessProfileId: string,
    options?: { 
      limit?: number;
      includeArchived?: boolean;
    }
  ): Promise<HistoricalAssessment[]>;
  async getAssessmentHistory(
    businessProfileId: string,
    frameworkId?: string,
    limit?: number
  ): Promise<HistoricalAssessment[]>;
  
  // Single implementation handling both signatures
  async getAssessmentHistory(
    businessProfileId: string,
    optionsOrFrameworkId?: { limit?: number; includeArchived?: boolean } | string,
    limit?: number
  ): Promise<HistoricalAssessment[]> {
    try {
      // Handle overload signatures
      let frameworkId: string | undefined;
      let options: { limit?: number; includeArchived?: boolean } | undefined;
      
      if (typeof optionsOrFrameworkId === 'string') {
        // Second signature: (businessProfileId, frameworkId?, limit?)
        frameworkId = optionsOrFrameworkId;
        options = limit !== undefined ? { limit } : {};
      } else {
        // First signature: (businessProfileId, options?)
        options = optionsOrFrameworkId;
      }
      
      // First try to fetch from API if available
      try {
        const response = await freemiumService.getAssessmentHistory?.(businessProfileId);
        if (response && Array.isArray(response)) {
          // Store in local cache for offline access
          const historicalRecords = response.map((item: any) => ({
            id: item.id || `${item.session_id}_${Date.now()}`,
            sessionId: item.session_id,
            businessProfileId: businessProfileId,
            frameworkId: item.framework_id || 'freemium_framework',
            frameworkName: item.framework_name || 'Freemium Assessment',
            overallScore: item.compliance_score,
            riskScore: item.risk_score,
            completionPercentage: item.completion_percentage,
            completedAt: item.results_generated_at || item.created_at,
            sectionScores: item.section_scores || {},
            gapsCount: item.gaps_count || 0,
            recommendationsCount: item.recommendations_count || 0,
            metadata: item.metadata || {}
          }));

          // Sort by completedAt descending to ensure consistent ordering
          historicalRecords.sort((a, b) =>
            new Date(b.completedAt).getTime() - new Date(a.completedAt).getTime()
          );

          // Update local cache with composite key for uniqueness across users
          const cacheKey = frameworkId 
            ? `${businessProfileId}:${frameworkId}` 
            : businessProfileId;
          this.historicalData.set(cacheKey, historicalRecords);

          // Apply filters and limits
          let filtered = historicalRecords;
          
          // Filter by framework if specified
          if (frameworkId) {
            filtered = filtered.filter(h => h.frameworkId === frameworkId);
          }
          
          if (!options?.includeArchived) {
            filtered = filtered.filter(record => !record.metadata?.archived);
          }
          if (options?.limit) {
            filtered = filtered.slice(0, options.limit);
          }
          
          return filtered;
        }
      } catch (apiError) {
        console.warn('Failed to fetch from API, using local cache:', apiError);
      }

      // Fallback to local cache with composite key checking
      const cacheKey = frameworkId
        ? `${businessProfileId}:${frameworkId}`
        : businessProfileId;

      // Try composite key first, then fall back to businessProfileId only
      // When frameworkId is undefined, also try freemium_framework as default
      const localHistory = this.historicalData.get(cacheKey) ||
                          (!frameworkId ? this.historicalData.get(`${businessProfileId}:freemium_framework`) : null) ||
                          this.historicalData.get(businessProfileId) || [];
      
      // Apply filters and limits
      let filtered = [...localHistory];
      
      // Filter by framework if specified
      if (frameworkId) {
        filtered = filtered.filter(h => h.frameworkId === frameworkId);
      }
      
      if (!options?.includeArchived) {
        filtered = filtered.filter(record => !record.metadata?.archived);
      }
      if (options?.limit) {
        filtered = filtered.slice(0, options.limit);
      }
      
      // Sort by date (newest first)
      filtered.sort((a, b) => new Date(b.completedAt).getTime() - new Date(a.completedAt).getTime());
      
      return filtered;
    } catch (error) {
      console.error('Failed to get assessment history:', error);
      // Return empty array instead of throwing to allow graceful degradation
      return [];
    }
  }

  /**
   * Store assessment results in historical data
   */
  private async storeHistoricalData(
    sessionToken: string,
    results: AssessmentResultsResponse
  ): Promise<void> {
    try {
      // Use lead_id for tracking historical data when available (for cross-assessment trends)
      // Fall back to session_id if lead_id is not available
      // Use composite key for uniqueness across users and frameworks
      const frameworkId = results.framework_id || 'freemium_framework';
      const businessProfileId = results.lead_id || results.session_id || sessionToken;
      const businessProfileKey = `${businessProfileId}:${frameworkId}`;

      const historicalRecord: HistoricalAssessment = {
        id: `${results.session_id}_${Date.now()}`,
        sessionId: results.session_id,
        businessProfileId: businessProfileKey,
        frameworkId: 'freemium_framework',
        frameworkName: 'Freemium Assessment',
        overallScore: results.compliance_score,
        riskScore: results.risk_score,
        completionPercentage: results.completion_percentage,
        completedAt: results.results_generated_at,
        sectionScores: this.extractSectionScores(results),
        gapsCount: results.compliance_gaps.length,
        recommendationsCount: results.recommendations.length,
        metadata: {
          sessionToken,
          resultsSummary: results.results_summary,
        },
      };

      // Get existing historical data
      const existing = this.historicalData.get(businessProfileKey) || [];

      // Check for duplicate session_id to prevent storing the same result multiple times
      const isDuplicate = existing.some(record => record.sessionId === results.session_id);

      if (!isDuplicate) {
        // Add new record only if not a duplicate
        existing.push(historicalRecord);

        // Sort by completion date (newest first)
        existing.sort((a, b) => new Date(b.completedAt).getTime() - new Date(a.completedAt).getTime());

        // Limit records if configured
        if (this.options.maxHistoricalRecords && existing.length > this.options.maxHistoricalRecords) {
          existing.splice(this.options.maxHistoricalRecords);
        }

        // Store back
        this.historicalData.set(businessProfileKey, existing);
      } else {
        // Update existing record with the same session_id if needed
        const recordIndex = existing.findIndex(record => record.sessionId === results.session_id);
        if (recordIndex !== -1) {
          existing[recordIndex] = historicalRecord;
          this.historicalData.set(businessProfileKey, existing);
        }
      }

    } catch (error) {
      console.error('Failed to store historical data:', error);
      // Don't throw - this is not critical for the main flow
    }
  }

  /**
   * Extract section scores from results with enhanced metadata
   */
  private extractSectionScores(results: AssessmentResultsResponse): Record<string, number> {
    // For freemium assessments, we'll create section scores based on gaps
    const sections: Record<string, number> = {};

    // Group gaps by category to create section scores
    const gapsByCategory = results.compliance_gaps.reduce((acc, gap) => {
      if (!acc[gap.category]) {
        acc[gap.category] = [];
      }
      acc[gap.category]!.push(gap);
      return acc;
    }, {} as Record<string, ComplianceGap[]>);

    // Calculate section scores based on gap severity
    Object.entries(gapsByCategory).forEach(([category, gaps]) => {
      const severityWeights: Record<string, number> = { critical: 0, high: 25, medium: 50, low: 75 };
      const avgSeverityScore = gaps.reduce((sum, gap) => {
        return sum + (severityWeights[gap.severity] ?? 50);
      }, 0) / gaps.length;

      sections[category] = Math.round(avgSeverityScore);
    });

    // Ensure we have some default sections with deterministic scores
    if (Object.keys(sections).length === 0) {
      const baseScore = results.compliance_score;
      
      // Generate deterministic scores based on the overall compliance score
      // Use a stable offset for each section to create realistic variation
      // Use display names here, they'll be normalized to IDs when needed
      sections['Data Protection'] = Math.min(100, Math.max(0, baseScore + 3));
      sections['Access Control'] = Math.min(100, Math.max(0, baseScore - 2));
      sections['Risk Management'] = Math.min(100, Math.max(0, baseScore + 1));
      sections['Compliance Monitoring'] = Math.min(100, Math.max(0, baseScore - 4));
      sections['Security Controls'] = Math.min(100, Math.max(0, baseScore - 10));
      sections['Access Management'] = Math.min(100, Math.max(0, baseScore - 5));
      sections['Documentation'] = Math.min(100, Math.max(0, baseScore + 5));
      
      // Note: If more variation is needed, consider using a hash of session_id or other stable identifier
      // to generate consistent but varied offsets per assessment
    }

    return sections;
  }

  /**
   * Generate detailed section metadata for dashboard display
   */
  public generateSectionDetails(
    results: AssessmentResultsResponse
  ): Array<import('@/types/assessment-results').SectionScoreDetail> {
    const sectionScores = this.extractSectionScores(results);
    const gapsByCategory = results.compliance_gaps.reduce((acc, gap) => {
      if (!acc[gap.category]) {
        acc[gap.category] = [];
      }
      acc[gap.category]!.push(gap);
      return acc;
    }, {} as Record<string, ComplianceGap[]>);

    return Object.entries(sectionScores).map(([sectionName, score]) => {
      const gaps = gapsByCategory[sectionName] || [];
      const totalQuestions = 10; // Estimated for freemium
      const percentage = score;
      const answeredQuestions = Math.round((results.completion_percentage / 100) * totalQuestions);

      // Determine risk level based on score
      let riskLevel: 'low' | 'medium' | 'high' | 'critical';
      if (score >= 80) riskLevel = 'low';
      else if (score >= 60) riskLevel = 'medium';
      else if (score >= 40) riskLevel = 'high';
      else riskLevel = 'critical';

      // Determine completion status
      let completionStatus: 'complete' | 'partial' | 'not_started';
      if (answeredQuestions === totalQuestions) completionStatus = 'complete';
      else if (answeredQuestions > 0) completionStatus = 'partial';
      else completionStatus = 'not_started';

      // Generate strengths and weaknesses based on gaps
      const strengths: string[] = [];
      const weaknesses: string[] = [];
      const keyFindings: string[] = [];

      if (score >= 80) {
        strengths.push(`Strong compliance in ${sectionName}`);
        strengths.push('Well-documented processes');
      }

      gaps.forEach(gap => {
        if (gap.severity === 'critical' || gap.severity === 'high') {
          weaknesses.push(gap.description);
          keyFindings.push(`${gap.severity.toUpperCase()}: ${gap.recommendation}`);
        }
      });

      if (weaknesses.length === 0 && score < 60) {
        weaknesses.push('Needs improvement in documentation');
        weaknesses.push('Process optimization required');
      }

      return {
        sectionId: normalizeSectionId(sectionName),
        sectionName,
        sectionDescription: `Compliance assessment for ${sectionName}`,
        score,
        maxScore: 100,
        percentage,
        totalQuestions,
        answeredQuestions,
        skippedQuestions: totalQuestions - answeredQuestions,
        completionStatus,
        riskLevel,
        strengths,
        weaknesses,
        keyFindings,
        questionBreakdown: [],
        sectionRecommendations: [],
        sectionGaps: [],
        historicalScores: [],
      };
    });
  }



  // ============================================================================
  // TREND ANALYSIS
  // ============================================================================

  /**
   * Generate trend analysis data from historical assessments
   */
  async generateTrendData(
    businessProfileId: string,
    timePeriod: TrendAnalysisData['timePeriod'] = 'last_3_months',
    frameworkId?: string
  ): Promise<TrendAnalysisData> {
    try {
      const historical = await this.getAssessmentHistory(businessProfileId, frameworkId);
      
      // Filter by time period
      const filteredData = this.filterByTimePeriod(historical, timePeriod);

      if (filteredData.length === 0) {
        return this.createEmptyTrendData(timePeriod);
      }

      // Defensively sort by completedAt descending before summary calculations
      filteredData.sort((a, b) =>
        new Date(b.completedAt).getTime() - new Date(a.completedAt).getTime()
      );

      // Convert to trend data points
      const dataPoints = this.convertToTrendDataPoints(filteredData);
      
      // Calculate summary statistics
      const summary = this.calculateTrendSummary(dataPoints);
      
      // Calculate section trends
      const sectionTrends = this.calculateSectionTrends(dataPoints);

      return {
        dataPoints,
        timePeriod,
        summary,
        sectionTrends,
      };
    } catch (error) {
      console.error('Failed to generate trend data:', error);
      return this.createEmptyTrendData(timePeriod);
    }
  }

  /**
   * Filter historical data by time period
   */
  private filterByTimePeriod(
    historical: HistoricalAssessment[],
    timePeriod: TrendAnalysisData['timePeriod']
  ): HistoricalAssessment[] {
    if (timePeriod === 'all_time') {
      return historical;
    }

    const now = new Date();
    const cutoffDate = new Date();

    switch (timePeriod) {
      case 'last_30_days':
        cutoffDate.setDate(now.getDate() - 30);
        break;
      case 'last_3_months':
        cutoffDate.setMonth(now.getMonth() - 3);
        break;
      case 'last_6_months':
        cutoffDate.setMonth(now.getMonth() - 6);
        break;
      case 'last_year':
        cutoffDate.setFullYear(now.getFullYear() - 1);
        break;
    }

    return historical.filter(h => new Date(h.completedAt) >= cutoffDate);
  }

  /**
   * Convert historical assessments to trend data points
   */
  private convertToTrendDataPoints(historical: HistoricalAssessment[]): TrendDataPoint[] {
    return historical.map((assessment, index) => {
      const dataPoint: TrendDataPoint = {
        date: assessment.completedAt,
        overallScore: assessment.overallScore,
        riskScore: assessment.riskScore,
        completionPercentage: assessment.completionPercentage,
        sectionScores: assessment.sectionScores,
        assessmentId: assessment.id,
      };

      // Calculate change from previous assessment
      if (index < historical.length - 1) {
        const previous = historical[index + 1]!;
        dataPoint.changeFromPrevious = {
          overallScore: assessment.overallScore - previous.overallScore,
          riskScore: assessment.riskScore - previous.riskScore,
          completionPercentage: assessment.completionPercentage - previous.completionPercentage,
        };
      }

      return dataPoint;
    });
  }

  /**
   * Calculate trend summary statistics
   */
  private calculateTrendSummary(dataPoints: TrendDataPoint[]): TrendAnalysisData['summary'] {
    if (dataPoints.length === 0) {
      return {
        totalAssessments: 0,
        averageScore: 0,
        scoreImprovement: 0,
        bestScore: 0,
        worstScore: 0,
        latestScore: 0,
        trend: 'stable',
      };
    }

    const scores = dataPoints.map(dp => dp.overallScore);
    const totalAssessments = dataPoints.length;
    const averageScore = scores.reduce((sum, score) => sum + score, 0) / totalAssessments;
    const bestScore = Math.max(...scores);
    const worstScore = Math.min(...scores);
    const latestScore = scores[0]!; // First item is latest (sorted desc)

    // Calculate improvement (latest vs oldest)
    const oldestScore = scores[scores.length - 1]!;
    const scoreImprovement = latestScore - oldestScore;
    
    // Determine trend
    let trend: 'improving' | 'declining' | 'stable' = 'stable';
    if (scoreImprovement > 5) {
      trend = 'improving';
    } else if (scoreImprovement < -5) {
      trend = 'declining';
    }

    return {
      totalAssessments,
      averageScore: Math.round(averageScore * 100) / 100,
      scoreImprovement: Math.round(scoreImprovement * 100) / 100,
      bestScore,
      worstScore,
      latestScore,
      trend,
    };
  }

  /**
   * Normalize section identifiers for consistent mapping
   * Handles variations in section naming between different parts of the system
   */
  private normalizeSectionId(sectionId: string): string {
    // Convert to lowercase and replace spaces with underscores
    return sectionId
      .toLowerCase()
      .replace(/\s+/g, '_')
      .replace(/-/g, '_')
      .replace(/[^a-z0-9_]/g, '');
  }

  /**
   * Map gap categories to normalized section identifiers
   */
  private mapGapToSectionId(gapCategory: string): string {
    // Normalize the gap category using the same rules as section IDs
    return this.normalizeSectionId(gapCategory);
  }

  /**
   * Calculate section-specific trends
   */
  private calculateSectionTrends(dataPoints: TrendDataPoint[]): TrendAnalysisData['sectionTrends'] {
    const sectionTrends: Record<string, any> = {};
    
    if (dataPoints.length === 0) {
      return sectionTrends;
    }

    // Get all unique section names
    const allSections = new Set<string>();
    dataPoints.forEach(dp => {
      Object.keys(dp.sectionScores).forEach(section => allSections.add(section));
    });

    // Calculate trends for each section
    allSections.forEach(sectionName => {
      const sectionScores = dataPoints
        .map(dp => dp.sectionScores[sectionName])
        .filter(score => score !== undefined);

      if (sectionScores.length > 0) {
        const average = sectionScores.reduce((sum, score) => sum + score, 0) / sectionScores.length;
        const latest = sectionScores[0]!;
        const oldest = sectionScores[sectionScores.length - 1]!;
        const improvement = latest - oldest;

        let trend: 'improving' | 'declining' | 'stable' = 'stable';
        if (improvement > 5) {
          trend = 'improving';
        } else if (improvement < -5) {
          trend = 'declining';
        }

        sectionTrends[sectionName] = {
          average: Math.round(average * 100) / 100,
          improvement: Math.round(improvement * 100) / 100,
          trend,
        };
      }
    });

    return sectionTrends;
  }

  /**
   * Create empty trend data for cases with no historical data
   */
  private createEmptyTrendData(timePeriod: TrendAnalysisData['timePeriod']): TrendAnalysisData {
    return {
      dataPoints: [],
      timePeriod,
      summary: {
        totalAssessments: 0,
        averageScore: 0,
        scoreImprovement: 0,
        bestScore: 0,
        worstScore: 0,
        latestScore: 0,
        trend: 'stable',
      },
      sectionTrends: {},
    };
  }

  // ============================================================================
  // EXPORT DATA PREPARATION
  // ============================================================================

  /**
   * Prepare assessment data for export
   */
  async prepareExportData(
    sessionToken: string,
    businessProfile?: Partial<BusinessProfile>
  ): Promise<ExportData> {
    try {
      const results = await this.getResults(sessionToken);
      
      return {
        assessment: {
          id: results.session_id,
          sessionId: results.session_id,
          frameworkName: 'Freemium Compliance Assessment',
          businessProfile: businessProfile || {
            company_name: results.session_id ? `Company ${results.session_id.slice(0, 8)}` : 'Unknown Company',
            industry: 'Unknown',
            id: results.session_id,
          },
          completedAt: results.results_generated_at,
          overallScore: results.compliance_score,
          riskScore: results.risk_score,
          completionPercentage: results.completion_percentage,
        },
        sections: this.prepareSectionData(results),
        gaps: this.prepareGapsData(results.compliance_gaps),
        recommendations: this.prepareRecommendationsData(results.recommendations),
        summary: {
          strengths: results.detailed_analysis?.strengths || [],
          weaknesses: results.detailed_analysis?.weaknesses || [],
          criticalAreas: results.detailed_analysis?.critical_areas || [],
          nextSteps: results.detailed_analysis?.next_steps || [],
        },
        metadata: {
          exportedAt: new Date().toISOString(),
          reportVersion: '1.0',
        },
      };
    } catch (error) {
      console.error('Failed to prepare export data:', error);
      throw new Error(
        error instanceof Error 
          ? `Failed to prepare export data: ${error.message}`
          : 'Failed to prepare export data'
      );
    }
  }

  /**
   * Prepare section data for export
   */
  private prepareSectionData(results: AssessmentResultsResponse): ExportData['sections'] {
    const sectionScores = this.extractSectionScores(results);
    
    return Object.entries(sectionScores).map(([name, score]) => ({
      name,
      score,
      questionsTotal: 10, // Mock data for freemium
      questionsAnswered: Math.round((results.completion_percentage / 100) * 10),
      completionRate: results.completion_percentage,
    }));
  }

  /**
   * Prepare gaps data for export
   */
  private prepareGapsData(gaps: ComplianceGap[]): ExportData['gaps'] {
    return gaps.map(gap => ({
      category: gap.category,
      severity: gap.severity,
      description: gap.description,
      recommendation: gap.recommendation,
      estimatedEffort: gap.estimated_effort,
      regulatoryImpact: gap.regulatory_impact,
    }));
  }

  /**
   * Prepare recommendations data for export
   */
  private prepareRecommendationsData(recommendations: ComplianceRecommendation[]): ExportData['recommendations'] {
    return recommendations.map(rec => ({
      priority: rec.priority,
      category: rec.category,
      title: rec.title,
      description: rec.description,
      implementationGuidance: rec.implementation_guidance,
      estimatedCost: rec.estimated_cost,
      timeline: rec.timeline,
      businessImpact: rec.business_impact,
    }));
  }

  // ============================================================================
  // DATA TRANSFORMATION
  // ============================================================================

  /**
   * Transform freemium results to assessment engine format
   */
  transformToAssessmentResult(
    results: AssessmentResultsResponse,
    frameworkId: string = 'freemium_framework'
  ): AssessmentResult {
    return {
      assessmentId: results.session_id,
      frameworkId,
      overallScore: results.compliance_score,
      sectionScores: this.extractSectionScores(results),
      gaps: this.transformGaps(results.compliance_gaps),
      recommendations: this.transformRecommendations(results.recommendations),
      completedAt: new Date(results.results_generated_at),
    };
  }

  /**
   * Transform compliance gaps to assessment engine format
   */
  private transformGaps(gaps: ComplianceGap[]): Gap[] {
    return gaps.map((gap, index) => ({
      id: `gap_${index}`,
      questionId: `question_${gap.category.toLowerCase().replace(/\s+/g, '_')}`,
      questionText: `${gap.category} compliance question`,
      section: gap.category,
      category: gap.category,
      severity: gap.severity,
      description: gap.description,
      impact: gap.regulatory_impact,
      currentState: 'Non-compliant',
      targetState: 'Compliant',
      expectedAnswer: 'Yes',
      actualAnswer: 'No',
    }));
  }

  /**
   * Transform compliance recommendations to assessment engine format
   */
  private transformRecommendations(recommendations: ComplianceRecommendation[]): Recommendation[] {
    return recommendations.map((rec, index) => ({
      id: `rec_${index}`,
      gapId: `gap_${index}`,
      priority: this.mapPriorityToTimeframe(rec.priority),
      title: rec.title,
      description: rec.description,
      // Map effort based on timeline/priority (semantic effort level)
      estimatedEffort: this.mapTimelineToEffort(rec.timeline, rec.priority),
      category: rec.category,
      impact: rec.business_impact,
      // Map cost to effort field (actual monetary cost)
      effort: rec.estimated_cost ? `£${rec.estimated_cost}` : 'TBD',
      estimatedTime: rec.timeline,
    }));
  }
  
  /**
   * Map timeline and priority to effort level
   */
  private mapTimelineToEffort(timeline: string, priority: string): string {
    // High priority + short timeline = High effort
    // Low priority + long timeline = Low effort
    const priorityLevel = priority.toLowerCase();
    const timelineNormalized = timeline.toLowerCase();
    
    if (priorityLevel === 'critical' || timelineNormalized.includes('immediate')) {
      return 'High';
    } else if (priorityLevel === 'high' || timelineNormalized.includes('week')) {
      return 'Medium';
    } else {
      return 'Low';
    }
  }

  /**
   * Map priority levels to timeframes
   */
  private mapPriorityToTimeframe(priority: string): 'immediate' | 'short_term' | 'medium_term' | 'long_term' {
    switch (priority.toLowerCase()) {
      case 'critical':
        return 'immediate';
      case 'high':
        return 'short_term';
      case 'medium':
        return 'medium_term';
      case 'low':
      default:
        return 'long_term';
    }
  }

  // ============================================================================
  // UTILITY METHODS
  // ============================================================================

  /**
   * Clear all cached data
   */
  clearAllCache(): void {
    this.clearCache();
    this.historicalData.clear();
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): {
    cachedResults: number;
    historicalProfiles: number;
    totalHistoricalRecords: number;
  } {
    const totalHistoricalRecords = Array.from(this.historicalData.values())
      .reduce((sum, records) => sum + records.length, 0);

    return {
      cachedResults: Object.keys(this.cache).length,
      historicalProfiles: this.historicalData.size,
      totalHistoricalRecords,
    };
  }

  /**
   * Health check for the service
   */
  async healthCheck(): Promise<{
    status: 'healthy' | 'degraded' | 'unhealthy';
    details: Record<string, any>;
  }> {
    try {
      // Clean expired cache
      this.cleanExpiredCache();

      // Check freemium service
      await freemiumService.healthCheck();

      const stats = this.getCacheStats();

      return {
        status: 'healthy',
        details: {
          cacheEnabled: this.options.cacheEnabled,
          historicalDataEnabled: this.options.enableHistoricalData,
          ...stats,
          lastCheck: new Date().toISOString(),
        },
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        details: {
          error: error instanceof Error ? error.message : 'Unknown error',
          lastCheck: new Date().toISOString(),
        },
      };
    }
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

export const assessmentResultsService = new AssessmentResultsService();

// ============================================================================
// EXPORTS
// ============================================================================

export default AssessmentResultsService;
export type { TrendDataPoint };
