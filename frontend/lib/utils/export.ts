// jsPDF will be dynamically imported when needed
// Heavy libraries will be dynamically imported when needed for code splitting
import type { 
  AssessmentResult, 
  Gap, 
  Recommendation
} from '../assessment-engine/types';
import type { 
  AssessmentResultsResponse, 
  ComplianceGap, 
  ComplianceRecommendation 
} from '../../types/freemium';

// Neural Purple theme colors - immutable configuration
const THEME_COLORS: Readonly<Record<string, string>> = Object.freeze({
  primary: '#6366f1',
  secondary: '#8b5cf6',
  accent: '#a855f7',
  background: '#f8fafc',
  text: '#1e293b',
  textLight: '#64748b',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  white: '#ffffff',
  gray100: '#f1f5f9',
  gray200: '#e2e8f0',
  gray300: '#cbd5e1',
  gray400: '#94a3b8',
  gray500: '#64748b',
  gray600: '#475569',
  gray700: '#334155',
  gray800: '#1e293b',
  gray900: '#0f172a'
});

// Type guards for distinguishing assessment types
function isAssessmentResult(obj: any): obj is AssessmentResult {
  return 'overallScore' in obj && 'gaps' in obj && 'sectionScores' in obj;
}

function isFreemiumResponse(obj: any): obj is AssessmentResultsResponse {
  return 'compliance_score' in obj && 'compliance_gaps' in obj;
}

// Cache for hexToRgb results to avoid repeated processing
const hexToRgbCache: Map<string, [number, number, number]> = new Map();

// Development flag for console logging
const isDevelopment = process.env.NODE_ENV === 'development';

// Lightweight logging function that only outputs in development
function logError(message: string, ...args: any[]): void {
  if (isDevelopment) {
    console.error(message, ...args);
  }
}

function logWarn(message: string, ...args: any[]): void {
  if (isDevelopment) {
    console.warn(message, ...args);
  }
}

// Helper function to convert hex color to RGB array with memoization
function hexToRgb(hex: string | null | undefined): [number, number, number] {
  // Early validation for null, undefined, or non-string inputs
  if (!hex || typeof hex !== 'string') {
    return [0, 0, 0]; // Return fallback immediately
  }
  
  // Check cache first
  if (hexToRgbCache.has(hex)) {
    return hexToRgbCache.get(hex)!;
  }
  
  // Remove # if present
  const cleanHex = hex.replace(/^#/, '');
  
  // Handle 3-digit hex codes by converting to 6-digit
  let normalizedHex = cleanHex;
  if (cleanHex.length === 3) {
    normalizedHex = cleanHex.split('').map(char => char + char).join('');
  }
  
  // Validate hex string length
  if (normalizedHex.length !== 6) {
    // In development, throw error for invalid inputs; in production, return null
    if (isDevelopment) {
      throw new Error(`Invalid hex color length: ${hex}`);
    }
    return [0, 0, 0];
  }
  
  // Validate hex characters
  if (!/^[0-9A-Fa-f]{6}$/.test(normalizedHex)) {
    // In development, throw error for invalid inputs; in production, return null
    if (isDevelopment) {
      throw new Error(`Invalid hex color format: ${hex}`);
    }
    return [0, 0, 0];
  }
  
  // Parse hex values
  const bigint = parseInt(normalizedHex, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  
  const result: [number, number, number] = [r, g, b];
  
  // Store in cache
  hexToRgbCache.set(hex, result);
  
  return result;
}

// Helper function to check if we're in a browser environment
function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof document !== 'undefined';
}

// Helper function to ensure browser environment or throw error
function ensureBrowserEnvironment(operation: string): void {
  if (!isBrowser()) {
    throw new Error(
      `Cannot perform ${operation}: DOM is not available. ` +
      `This operation requires a browser environment and cannot run during SSR or build.`
    );
  }
}

// Cached xlsx module loader to avoid redundant imports
let cachedXlsxModule: any = null;

async function getXlsxModule(): Promise<any> {
  if (cachedXlsxModule) {
    return cachedXlsxModule;
  }
  
  // Ensure browser environment before importing xlsx
  ensureBrowserEnvironment('xlsx module loading');
  
  try {
    const xlsxModule = await import('@e965/xlsx');
    cachedXlsxModule = xlsxModule;
    return cachedXlsxModule;
  } catch (error) {
    logError('Failed to load xlsx module:', error);
    throw new Error('Failed to load Excel/CSV processing module');
  }
}

// Helper function to sanitize filename
function sanitizeFilename(filename: string): string {
  // Replace illegal characters with underscore
  const sanitized = filename.replace(/[\/\:*?"<>|]/g, '_');
  
  // Limit length to 200 characters (leaving room for extension)
  if (sanitized.length > 200) {
    return sanitized.substring(0, 200);
  }
  
  return sanitized;
}

// Helper function to normalize data from different response types
function normalizeAssessmentData(results: AssessmentResult | AssessmentResultsResponse) {
  const normalized = {
    overallScore: 0,
    riskScore: null as number | null,
    completionPercentage: 100,
    assessmentDate: new Date(),
    sectionScores: {} as Record<string, number>,
    gaps: [] as Array<Gap | ComplianceGap>,
    recommendations: [] as Array<Recommendation | ComplianceRecommendation>,
    answers: [] as Array<any>
  };

  if (isAssessmentResult(results)) {
    normalized.overallScore = results.overallScore;
    normalized.assessmentDate = new Date(results.completedAt);
    normalized.sectionScores = results.sectionScores || {};
    normalized.gaps = results.gaps || [];
    normalized.recommendations = results.recommendations || [];
    normalized.answers = (results as any).answers || [];
  } else if (isFreemiumResponse(results)) {
    normalized.overallScore = results.compliance_score;
    normalized.riskScore = results.risk_score || null;
    normalized.completionPercentage = results.completion_percentage || 100;
    normalized.assessmentDate = new Date(results.results_generated_at);
    normalized.gaps = results.compliance_gaps || [];
    normalized.recommendations = results.recommendations || (results as any).compliance_recommendations || [];
  } else {
    // Handle any other format by looking for common fields
    normalized.overallScore = (results as any).overallScore || (results as any).compliance_score || 0;
    normalized.riskScore = (results as any).risk_score || null;
    normalized.completionPercentage = (results as any).completion_percentage || 100;
    normalized.assessmentDate = new Date((results as any).completedAt || (results as any).results_generated_at || Date.now());
    normalized.sectionScores = (results as any).sectionScores || {};
    normalized.gaps = (results as any).gaps || (results as any).compliance_gaps || [];
    normalized.recommendations = (results as any).recommendations || (results as any).compliance_recommendations || [];
    normalized.answers = (results as any).answers || [];
  }

  return normalized;
}

// Canonical export option keys for consistent UI-to-export mapping
export const EXPORT_OPTION_KEYS = {
  format: 'format',
  includeQuestions: 'includeQuestions',
  includeAnswers: 'includeAnswers',
  includeGaps: 'includeGaps',
  includeRecommendations: 'includeRecommendations',
  includeSectionBreakdown: 'includeSectionBreakdown',
  includeExecutiveSummary: 'includeExecutiveSummary',
  includeCharts: 'includeCharts',
  includeTrendAnalysis: 'includeTrendAnalysis',
  companyName: 'companyName',
  reportTitle: 'reportTitle',
  dateRange: 'dateRange',
  customFields: 'customFields',
  chartImages: 'chartImages'
} as const;

// Export options interface
export interface ExportOptions {
  format: 'csv' | 'excel' | 'pdf';
  includeQuestions?: boolean;
  includeAnswers?: boolean;
  includeGaps?: boolean;
  includeRecommendations?: boolean;
  includeSectionBreakdown?: boolean;
  includeExecutiveSummary?: boolean;
  includeCharts?: boolean;
  includeTrendAnalysis?: boolean;
  companyName?: string;
  reportTitle?: string;
  dateRange?: {
    start: Date;
    end: Date;
  };
  customFields?: Record<string, any>;
  chartImages?: {
    gaugeImage?: string; // Base64 or data URL
    trendChartImage?: string; // Base64 or data URL
    gapAnalysisImage?: string; // Base64 or data URL
    sectionScoresImage?: string; // Base64 or data URL
  };
  estimatedBreakdown?: boolean; // Whether section details are generated heuristically
}

// Progress callback type
export type ProgressCallback = (progress: number, message: string) => void;

// Export result interface
export interface ExportResult {
  success: boolean;
  filename: string;
  size?: number;
  error?: string;
  downloadUrl?: string;
}

// Utility functions for data formatting
export const formatters = {
  /**
   * Format date to readable string
   */
  formatDate: (date: Date | string): string => {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  },

  /**
   * Format score as percentage
   */
  formatScore: (score: number): string => {
    return `${Math.round(score)}%`;
  },

  /**
   * Format severity level with color coding
   */
  formatSeverity: (severity: string): { text: string; color: string } => {
    const severityMap: Record<string, { text: string; color: string }> = {
      critical: { text: 'Critical', color: THEME_COLORS.danger },
      high: { text: 'High', color: '#f97316' },
      medium: { text: 'Medium', color: THEME_COLORS.warning },
      low: { text: 'Low', color: THEME_COLORS.success }
    };
    return severityMap[severity.toLowerCase()] || { text: severity, color: THEME_COLORS.textLight };
  },

  /**
   * Format priority level
   */
  formatPriority: (priority: string): string => {
    const priorityMap: Record<string, string> = {
      immediate: 'Immediate',
      short_term: 'Short Term',
      medium_term: 'Medium Term',
      long_term: 'Long Term'
    };
    return priorityMap[priority] || priority;
  },

  /**
   * Truncate text to specified length
   */
  truncateText: (text: string | any, maxLength: number = 100): string => {
    // Safely coerce input to string
    const str = (text ?? '').toString();
    if (str.length <= maxLength) return str;
    return str.substring(0, maxLength - 3) + '...';
  },

  /**
   * Convert bytes to human readable format
   */
  formatFileSize: (bytes: number): string => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), sizes.length - 1);
    return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + sizes[i];
  }
};

/**
 * Export assessment results to Excel format (XLSX)
 * @requires Browser environment - Will not work in SSR or Node.js contexts
 */
export async function exportAssessmentExcel(
  results: AssessmentResult | AssessmentResultsResponse,
  options: ExportOptions = { format: 'excel' },
  onProgress?: ProgressCallback
): Promise<ExportResult> {
  // Check browser environment immediately
  ensureBrowserEnvironment('Excel export');
  
  try {
    onProgress?.(10, 'Preparing data for Excel export...');

    // Normalize data for consistent handling
    const normalizedData = normalizeAssessmentData(results);

    // Use cached xlsx module loader
    const XLSX = await getXlsxModule();

    // Create workbook
    const wb = XLSX.utils.book_new();
    
    // Overview sheet
    const overviewData = [
      ['Assessment Report'],
      ['Generated on', formatters.formatDate(new Date())],
      ['Company', options.companyName || 'N/A'],
      [''],
      ['Overall Score', formatters.formatScore(normalizedData.overallScore)],
      ['Risk Score', normalizedData.riskScore !== null ? formatters.formatScore(normalizedData.riskScore) : 'N/A'],
      ['Completion', formatters.formatScore(normalizedData.completionPercentage)],
      ['Assessment Date', formatters.formatDate(normalizedData.assessmentDate)]
    ];

    onProgress?.(25, 'Creating overview sheet...');

    const overviewWs = XLSX.utils.aoa_to_sheet(overviewData);
    XLSX.utils.book_append_sheet(wb, overviewWs, 'Overview');

    // Section scores sheet (if available)
    if (Object.keys(normalizedData.sectionScores).length > 0 && options.includeSectionBreakdown !== false) {
      onProgress?.(40, 'Processing section scores...');
      
      const sectionData = [
        ['Section', 'Score', 'Percentage']
      ];
      
      Object.entries(normalizedData.sectionScores).forEach(([section, score]) => {
        sectionData.push([section, score.toString(), formatters.formatScore(score)]);
      });

      const sectionWs = XLSX.utils.aoa_to_sheet(sectionData);
      XLSX.utils.book_append_sheet(wb, sectionWs, 'Section Scores');
    }

    // Gaps sheet
    if (options.includeGaps !== false && normalizedData.gaps.length > 0) {
      onProgress?.(55, 'Processing gaps analysis...');
      
      const gapsData = [
        ['Category', 'Severity', 'Description', 'Recommendation', 'Impact', 'Effort']
      ];

      normalizedData.gaps.forEach((gap: Gap | ComplianceGap) => {
        // Guard against null or undefined gaps
        if (!gap) {
          logWarn('Skipping null/undefined gap in export');
          return;
        }
        
        if ('questionText' in gap) {
          // AssessmentResult Gap
          gapsData.push([
            gap.category,
            gap.severity,
            gap.description,
            gap.impact,
            gap.currentState,
            'N/A'
          ]);
        } else {
          // FreemiumAssessmentResultsResponse ComplianceGap
          gapsData.push([
            gap.category,
            gap.severity,
            gap.description,
            gap.recommendation,
            gap.regulatory_impact,
            gap.estimated_effort
          ]);
        }
      });

      const gapsWs = XLSX.utils.aoa_to_sheet(gapsData);
      XLSX.utils.book_append_sheet(wb, gapsWs, 'Gaps Analysis');
    }

    // Recommendations sheet
    if (options.includeRecommendations !== false && normalizedData.recommendations.length > 0) {
      onProgress?.(70, 'Processing recommendations...');
      
      const recsData = [
        ['Priority', 'Title', 'Description', 'Category', 'Impact', 'Effort', 'Timeline']
      ];

      normalizedData.recommendations.forEach((rec: Recommendation | ComplianceRecommendation) => {
        if ('gapId' in rec) {
          // AssessmentResult Recommendation
          recsData.push([
            formatters.formatPriority(rec.priority),
            rec.title,
            formatters.truncateText(rec.description, 200),
            rec.category,
            rec.impact,
            rec.effort,
            rec.estimatedTime
          ]);
        } else {
          // FreemiumAssessmentResultsResponse ComplianceRecommendation
          recsData.push([
            formatters.formatPriority(rec.priority),
            rec.title,
            formatters.truncateText(rec.description, 200),
            rec.category,
            rec.business_impact,
            rec.estimated_cost,
            rec.timeline
          ]);
        }
      });

      const recsWs = XLSX.utils.aoa_to_sheet(recsData);
      XLSX.utils.book_append_sheet(wb, recsWs, 'Recommendations');
    }

    // Questions and Answers sheet
    if ((options.includeQuestions || options.includeAnswers) && normalizedData.answers.length > 0) {
      onProgress?.(80, 'Processing questions and answers...');

      const qaData = [
        ['Question ID', 'Text', 'Answer', 'Section', 'Category', 'Score']
      ];

      normalizedData.answers.forEach((answer: any) => {
        qaData.push([
          answer.questionId || 'N/A',
          answer.questionText || 'N/A',
          answer.answer || 'N/A',
          answer.section || 'N/A',
          answer.category || 'N/A',
          answer.score?.toString() || '0'
        ]);
      });

      const qaWs = XLSX.utils.aoa_to_sheet(qaData);
      XLSX.utils.book_append_sheet(wb, qaWs, 'Questions & Answers');
    }

    onProgress?.(85, 'Generating Excel file...');

    // Generate XLSX content (multi-sheet support)
    const xlsxContent = XLSX.write(wb, {
      type: 'array',
      bookType: 'xlsx'
    });

    onProgress?.(95, 'Preparing download...');

    // Create filename with sanitization
    const timestamp = new Date().toISOString().split('T')[0];
    const companyPart = options.companyName ? sanitizeFilename(options.companyName) + '-' : '';
    const reportPart = options.reportTitle ? sanitizeFilename(options.reportTitle) + '-' : 'assessment-report-';
    const filename = `${companyPart}${reportPart}${timestamp}.xlsx`;

    // Ensure browser environment before DOM operations
    ensureBrowserEnvironment('Excel export download');

    // Trigger download
    const blob = new Blob([xlsxContent], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    onProgress?.(100, 'Export completed successfully!');

    return {
      success: true,
      filename,
      size: blob.size
    };

  } catch (error) {
    logError('Excel export error:', error);
    
    // Preserve original error with context
    const enhancedError = new Error(
      `Excel export failed: ${error instanceof Error ? error.message : 'Unknown error'}`
    );
    
    if (error instanceof Error) {
      enhancedError.stack = error.stack;
      (enhancedError as any).cause = error;
    }
    
    throw enhancedError;
  }
}

/**
 * Export assessment results to PDF format
 * @requires Browser environment - Will not work in SSR or Node.js contexts
 */
export async function exportAssessmentPDF(
  results: AssessmentResult | AssessmentResultsResponse,
  options: ExportOptions = { format: 'pdf' },
  onProgress?: ProgressCallback
): Promise<ExportResult> {
  // Check browser environment immediately
  ensureBrowserEnvironment('PDF export');
  
  try {
    onProgress?.(5, 'Initializing PDF document...');

    // Normalize data for consistent handling
    const normalizedData = normalizeAssessmentData(results);

    // Dynamically import jsPDF for code splitting
    const { jsPDF } = await import('jspdf');
    const autoTable = (await import('jspdf-autotable')).default;

    // Create PDF document
    const doc = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4'
    });

    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 20;
    const contentWidth = pageWidth - (margin * 2);
    const headerHeight = 25; // Standard header height

    let yPosition = margin;

    // Helper function to check if we need a new page
    const checkPageBreak = (requiredHeight: number) => {
      if (yPosition + requiredHeight > pageHeight - margin) {
        doc.addPage();
        addHeader(); // Add header to new page
        yPosition = margin + headerHeight; // Reset position after header
        return true;
      }
      return false;
    };

    // Helper function to add header
    const addHeader = () => {
      // Company logo placeholder (you can add actual logo here)
      const primaryRgb = hexToRgb(THEME_COLORS.primary);
      doc.setFillColor(primaryRgb[0], primaryRgb[1], primaryRgb[2]);
      doc.rect(margin, margin, contentWidth, 15, 'F');
      
      const whiteRgb = hexToRgb(THEME_COLORS.white);
      doc.setTextColor(whiteRgb[0], whiteRgb[1], whiteRgb[2]);
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      doc.text(options.companyName || 'Compliance Assessment Report', margin + 5, margin + 10);
      
      yPosition = margin + headerHeight;
    };

    // Helper function to add footer
    const addFooter = (pageNum: number, totalPages: number) => {
      const textLightRgb = hexToRgb(THEME_COLORS.textLight);
      doc.setTextColor(textLightRgb[0], textLightRgb[1], textLightRgb[2]);
      doc.setFontSize(8);
      doc.text(
        `Page ${pageNum} of ${totalPages} | Generated on ${formatters.formatDate(new Date())}`,
        pageWidth / 2,
        pageHeight - 10,
        { align: 'center' }
      );
    };

    onProgress?.(15, 'Adding header and title...');

    // Add header
    addHeader();

    // Title
    const textRgb = hexToRgb(THEME_COLORS.text);
    doc.setTextColor(textRgb[0], textRgb[1], textRgb[2]);
    doc.setFontSize(24);
    doc.setFont('helvetica', 'bold');
    doc.text(options.reportTitle || 'Assessment Results Report', margin, yPosition);
    yPosition += 15;

    // Subtitle
    doc.setFontSize(12);
    doc.setFont('helvetica', 'normal');
    const textLightRgb = hexToRgb(THEME_COLORS.textLight);
    doc.setTextColor(textLightRgb[0], textLightRgb[1], textLightRgb[2]);
    doc.text(`Generated on ${formatters.formatDate(new Date())}`, margin, yPosition);
    yPosition += 20;

    onProgress?.(25, 'Adding executive summary...');

    // Executive Summary
    if (options.includeExecutiveSummary !== false) {
      checkPageBreak(40);
      
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      const textRgb2 = hexToRgb(THEME_COLORS.text);
      doc.setTextColor(textRgb2[0], textRgb2[1], textRgb2[2]);
      doc.text('Executive Summary', margin, yPosition);
      yPosition += 10;

      // Score overview
      const overallScore = normalizedData.overallScore;
      const riskScore = normalizedData.riskScore;
      
      doc.setFontSize(12);
      doc.setFont('helvetica', 'normal');
      
      // Score boxes
      const boxWidth = (contentWidth - 10) / (riskScore ? 2 : 1);
      const boxHeight = 25;
      
      // Overall Score Box
      const primaryRgb2 = hexToRgb(THEME_COLORS.primary);
      doc.setFillColor(primaryRgb2[0], primaryRgb2[1], primaryRgb2[2]);
      doc.rect(margin, yPosition, boxWidth, boxHeight, 'F');
      const whiteRgb2 = hexToRgb(THEME_COLORS.white);
      doc.setTextColor(whiteRgb2[0], whiteRgb2[1], whiteRgb2[2]);
      doc.setFont('helvetica', 'bold');
      doc.text('Overall Score', margin + 5, yPosition + 8);
      doc.setFontSize(18);
      doc.text(formatters.formatScore(overallScore), margin + 5, yPosition + 18);
      
      // Risk Score Box (if available)
      if (riskScore !== null) {
        const secondaryRgb = hexToRgb(THEME_COLORS.secondary);
        doc.setFillColor(secondaryRgb[0], secondaryRgb[1], secondaryRgb[2]);
        doc.rect(margin + boxWidth + 10, yPosition, boxWidth, boxHeight, 'F');
        doc.setTextColor(whiteRgb2[0], whiteRgb2[1], whiteRgb2[2]);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(12);
        doc.text('Risk Score', margin + boxWidth + 15, yPosition + 8);
        doc.setFontSize(18);
        doc.text(formatters.formatScore(riskScore), margin + boxWidth + 15, yPosition + 18);
      }
      
      yPosition += boxHeight + 15;

      // Add notice if section details are estimated
      if (options.estimatedBreakdown) {
        doc.setFontSize(10);
        doc.setFont('helvetica', 'italic');
        const warningRgb = hexToRgb(THEME_COLORS.warning);
        doc.setTextColor(warningRgb[0], warningRgb[1], warningRgb[2]);
        doc.text('Note: Section breakdown details are estimated based on overall results.', margin, yPosition);
        yPosition += 10;
      }
    }

    onProgress?.(35, 'Adding charts and visualizations...');

    // Embed chart images if provided (from chartImages or customFields)
    const chartImages = options.chartImages || options.customFields;
    if (chartImages && options.includeCharts !== false) {
      // Gauge Chart
      if (chartImages.gaugeImage) {
        checkPageBreak(80);
        try {
          doc.addImage(chartImages.gaugeImage, 'PNG', margin, yPosition, contentWidth / 2 - 5, 60);
        } catch (err) {
          logWarn('Failed to embed gauge chart:', err);
        }
      }

      // Trend Chart - only include if includeTrendAnalysis is true
      if (chartImages.trendChartImage && options.includeTrendAnalysis !== false) {
        const xPos = chartImages.gaugeImage ? margin + contentWidth / 2 + 5 : margin;
        try {
          doc.addImage(chartImages.trendChartImage, 'PNG', xPos, yPosition, contentWidth / 2 - 5, 60);
        } catch (err) {
          logWarn('Failed to embed trend chart:', err);
        }
        yPosition += 70;
      } else if (chartImages.gaugeImage) {
        yPosition += 70;
      }

      // Gap Analysis Chart
      if (chartImages.gapAnalysisImage) {
        checkPageBreak(80);
        try {
          doc.addImage(chartImages.gapAnalysisImage, 'PNG', margin, yPosition, contentWidth, 60);
          yPosition += 70;
        } catch (err) {
          logWarn('Failed to embed gap analysis chart:', err);
        }
      }
    }

    onProgress?.(40, 'Adding section breakdown...');

    // Section Scores (if available)
    if (Object.keys(normalizedData.sectionScores).length > 0 && options.includeSectionBreakdown !== false) {
      checkPageBreak(60);
      
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      const textRgb3 = hexToRgb(THEME_COLORS.text);
      doc.setTextColor(textRgb3[0], textRgb3[1], textRgb3[2]);
      doc.text('Section Breakdown', margin, yPosition);
      yPosition += 15;

      const sectionData = Object.entries(normalizedData.sectionScores).map(([section, score]) => [
        section,
        score.toString(),
        formatters.formatScore(score)
      ]);

      autoTable(doc, {
        startY: yPosition,
        head: [['Section', 'Score', 'Percentage']],
        body: sectionData,
        theme: 'grid',
        headStyles: {
          fillColor: hexToRgb(THEME_COLORS.primary),
          textColor: hexToRgb(THEME_COLORS.white),
          fontStyle: 'bold'
        },
        styles: {
          fontSize: 10,
          cellPadding: 3
        },
        margin: { left: margin, right: margin }
      });

      yPosition = (doc as any).lastAutoTable.finalY + 15;
    }

    onProgress?.(60, 'Adding gaps analysis...');

    // Gaps Analysis
    if (options.includeGaps !== false && normalizedData.gaps.length > 0) {
      checkPageBreak(40);
      
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      const textRgb4 = hexToRgb(THEME_COLORS.text);
      doc.setTextColor(textRgb4[0], textRgb4[1], textRgb4[2]);
      doc.text('Gaps Analysis', margin, yPosition);
      yPosition += 15;

      const gapsData = normalizedData.gaps.map((gap: Gap | ComplianceGap) => {
          if ('questionText' in gap) {
            return [
              gap.category,
              gap.severity,
              formatters.truncateText(gap.description, 80),
              formatters.truncateText(gap.impact, 60)
            ];
          } else {
            return [
              gap.category,
              gap.severity,
              formatters.truncateText(gap.description, 80),
              formatters.truncateText(gap.regulatory_impact, 60)
            ];
          }
        });

      autoTable(doc, {
        startY: yPosition,
        head: [['Category', 'Severity', 'Description', 'Impact']],
        body: gapsData,
        theme: 'grid',
        headStyles: {
          fillColor: hexToRgb(THEME_COLORS.danger),
          textColor: hexToRgb(THEME_COLORS.white),
          fontStyle: 'bold'
        },
        styles: {
          fontSize: 9,
          cellPadding: 2
        },
        columnStyles: {
          2: { cellWidth: 60 },
          3: { cellWidth: 50 }
        },
        margin: { left: margin, right: margin }
      });

      yPosition = (doc as any).lastAutoTable.finalY + 15;
    }

    onProgress?.(80, 'Adding recommendations...');

    // Recommendations
    if (options.includeRecommendations !== false && normalizedData.recommendations.length > 0) {
      checkPageBreak(40);
      
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      const textRgb5 = hexToRgb(THEME_COLORS.text);
      doc.setTextColor(textRgb5[0], textRgb5[1], textRgb5[2]);
      doc.text('Recommendations', margin, yPosition);
      yPosition += 15;

      const recsData = normalizedData.recommendations.map((rec: Recommendation | ComplianceRecommendation) => {
          if ('gapId' in rec) {
            return [
              formatters.formatPriority(rec.priority),
              formatters.truncateText(rec.title, 40),
              formatters.truncateText(rec.description, 80),
              rec.estimatedTime
            ];
          } else {
            return [
              formatters.formatPriority(rec.priority),
              formatters.truncateText(rec.title, 40),
              formatters.truncateText(rec.description, 80),
              rec.timeline
            ];
          }
        });

      autoTable(doc, {
        startY: yPosition,
        head: [['Priority', 'Title', 'Description', 'Timeline']],
        body: recsData,
        theme: 'grid',
        headStyles: {
          fillColor: hexToRgb(THEME_COLORS.success),
          textColor: hexToRgb(THEME_COLORS.white),
          fontStyle: 'bold'
        },
        styles: {
          fontSize: 9,
          cellPadding: 2
        },
        columnStyles: {
          2: { cellWidth: 70 }
        },
        margin: { left: margin, right: margin }
      });

      yPosition = (doc as any).lastAutoTable.finalY + 15;
    }

    // Questions and Answers
    if ((options.includeQuestions || options.includeAnswers) && normalizedData.answers.length > 0) {
      onProgress?.(85, 'Adding questions and answers...');

      checkPageBreak(40);

      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      const textRgb6 = hexToRgb(THEME_COLORS.text);
      doc.setTextColor(textRgb6[0], textRgb6[1], textRgb6[2]);
      doc.text('Questions & Answers', margin, yPosition);
      yPosition += 15;

      const qaData = normalizedData.answers.map((answer: any) => [
          answer.questionId.substring(0, 10),
          formatters.truncateText(answer.questionText || 'N/A', 60),
          formatters.truncateText(answer.answer || 'N/A', 40),
          answer.section || 'N/A',
          answer.score?.toString() || '0'
        ]);

      autoTable(doc, {
        startY: yPosition,
        head: [['ID', 'Question', 'Answer', 'Section', 'Score']],
        body: qaData,
        theme: 'grid',
        headStyles: {
          fillColor: hexToRgb(THEME_COLORS.accent),
          textColor: hexToRgb(THEME_COLORS.white),
          fontStyle: 'bold'
        },
        styles: {
          fontSize: 9,
          cellPadding: 2
        },
        columnStyles: {
          0: { cellWidth: 20 },
          1: { cellWidth: 60 },
          2: { cellWidth: 50 },
          3: { cellWidth: 30 },
          4: { cellWidth: 20 }
        },
        margin: { left: margin, right: margin }
      });

      yPosition = (doc as any).lastAutoTable.finalY + 15;
    }

    onProgress?.(90, 'Finalizing PDF...');

    // Add page numbers to all pages
    const totalPages = (doc as any).internal.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      addFooter(i, totalPages);
    }

    onProgress?.(95, 'Preparing download...');

    // Generate filename with sanitization
    const timestamp = new Date().toISOString().split('T')[0];
    const companyPart = options.companyName ? sanitizeFilename(options.companyName) + '-' : '';
    const reportPart = options.reportTitle ? sanitizeFilename(options.reportTitle) + '-' : 'assessment-report-';
    const filename = `${companyPart}${reportPart}${timestamp}.pdf`;

    // Save the PDF
    doc.save(filename);

    onProgress?.(100, 'Export completed successfully!');

    return {
      success: true,
      filename,
      size: doc.output('blob').size
    };

  } catch (error) {
    logError('PDF export error:', error);
    
    // Enhanced error handling with stack trace
    const errorDetails: ExportResult = {
      success: false,
      filename: '',
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    };
    
    // Add stack trace and raw error for debugging (ensure no sensitive data)
    if (error instanceof Error) {
      (errorDetails as any).stack = error.stack;
      (errorDetails as any).rawError = {
        name: error.name,
        message: error.message,
        stack: error.stack
      };
    } else {
      (errorDetails as any).rawError = error;
    }
    
    return errorDetails;
  }
}

/**
 * Export assessment results to CSV format
 * @requires Browser environment - Will not work in SSR or Node.js contexts
 */
export async function exportAssessmentCSV(
  results: AssessmentResult | AssessmentResultsResponse,
  options: ExportOptions = { format: 'csv' },
  onProgress?: ProgressCallback
): Promise<ExportResult> {
  // Check browser environment immediately
  ensureBrowserEnvironment('CSV export');
  
  try {
    onProgress?.(10, 'Preparing data for CSV export...');

    // Normalize data for consistent handling
    const normalizedData = normalizeAssessmentData(results);

    // Use cached xlsx module loader
    const XLSX = await getXlsxModule();

    // Prepare CSV data
    const csvParts: string[] = [];

    // Overview CSV
    onProgress?.(25, 'Creating overview CSV...');
    const overviewData = [
      ['Assessment Report'],
      ['Generated on', formatters.formatDate(new Date())],
      ['Company', options.companyName || 'N/A'],
      [''],
      ['Overall Score', formatters.formatScore(normalizedData.overallScore)],
      ['Risk Score', normalizedData.riskScore !== null ? formatters.formatScore(normalizedData.riskScore) : 'N/A'],
      ['Completion', formatters.formatScore(normalizedData.completionPercentage)],
      ['Assessment Date', formatters.formatDate(normalizedData.assessmentDate)]
    ];

    // Add note if section details are estimated
    if (options.estimatedBreakdown) {
      overviewData.push(['']);
      overviewData.push(['Note', 'Section breakdown details are estimated based on overall results']);
    }

    const overviewWs = XLSX.utils.aoa_to_sheet(overviewData);
    csvParts.push('=== OVERVIEW ===\n' + XLSX.utils.sheet_to_csv(overviewWs));

    // Section scores CSV (if available)
    if (Object.keys(normalizedData.sectionScores).length > 0 && options.includeSectionBreakdown !== false) {
      onProgress?.(40, 'Processing section scores...');

      const sectionData = [
        ['Section', 'Score', 'Percentage']
      ];

      Object.entries(normalizedData.sectionScores).forEach(([section, score]) => {
        sectionData.push([section, score.toString(), formatters.formatScore(score)]);
      });

      const sectionWs = XLSX.utils.aoa_to_sheet(sectionData);
      csvParts.push('\n\n=== SECTION SCORES ===\n' + XLSX.utils.sheet_to_csv(sectionWs));
    }

    // Gaps CSV
    if (options.includeGaps !== false && normalizedData.gaps.length > 0) {
      onProgress?.(55, 'Processing gaps analysis...');
      const gapsData = [
        ['Category', 'Severity', 'Description', 'Recommendation', 'Impact', 'Effort']
      ];

      normalizedData.gaps.forEach((gap: Gap | ComplianceGap) => {
          if ('questionText' in gap) {
            // AssessmentResult Gap
            gapsData.push([
              gap.category,
              gap.severity,
              gap.description,
              gap.impact,
              gap.currentState,
              'N/A'
            ]);
          } else {
            // FreemiumAssessmentResultsResponse ComplianceGap
            gapsData.push([
              gap.category,
              gap.severity,
              gap.description,
              gap.recommendation,
              gap.regulatory_impact,
              gap.estimated_effort
            ]);
          }
        });

      const gapsWs = XLSX.utils.aoa_to_sheet(gapsData);
      csvParts.push('\n\n=== GAPS ANALYSIS ===\n' + XLSX.utils.sheet_to_csv(gapsWs));
    }

    // Recommendations CSV
    if (options.includeRecommendations !== false && normalizedData.recommendations.length > 0) {
      onProgress?.(70, 'Processing recommendations...');
      const recsData = [
        ['Priority', 'Title', 'Description', 'Category', 'Impact', 'Effort', 'Timeline']
      ];

      normalizedData.recommendations.forEach((rec: Recommendation | ComplianceRecommendation) => {
          if ('gapId' in rec) {
            // AssessmentResult Recommendation
            recsData.push([
              formatters.formatPriority(rec.priority),
              rec.title,
              rec.description,
              rec.category,
              rec.impact,
              rec.effort,
              rec.estimatedTime
            ]);
          } else {
            // FreemiumAssessmentResultsResponse ComplianceRecommendation
            recsData.push([
              formatters.formatPriority(rec.priority),
              rec.title,
              rec.description,
              rec.category,
              rec.business_impact,
              rec.estimated_cost,
              rec.timeline
            ]);
          }
        });

      const recsWs = XLSX.utils.aoa_to_sheet(recsData);
      csvParts.push('\n\n=== RECOMMENDATIONS ===\n' + XLSX.utils.sheet_to_csv(recsWs));
    }

    // Questions and Answers CSV
    if ((options.includeQuestions || options.includeAnswers) && normalizedData.answers.length > 0) {
      onProgress?.(80, 'Processing questions and answers...');

      const qaData = [
        ['Question ID', 'Text', 'Answer', 'Section', 'Category', 'Score']
      ];

      normalizedData.answers.forEach((answer: any) => {
        qaData.push([
          answer.questionId,
          answer.questionText || 'N/A',
          answer.answer || 'N/A',
          answer.section || 'N/A',
          answer.category || 'N/A',
          answer.score?.toString() || '0'
        ]);
      });

      const qaWs = XLSX.utils.aoa_to_sheet(qaData);
      csvParts.push('\n\n=== QUESTIONS & ANSWERS ===\n' + XLSX.utils.sheet_to_csv(qaWs));
    }

    onProgress?.(85, 'Generating CSV file...');

    // Combine all CSV parts
    const csvContent = csvParts.join('');

    onProgress?.(95, 'Preparing download...');

    // Create filename with sanitization
    const timestamp = new Date().toISOString().split('T')[0];
    const companyPart = options.companyName ? sanitizeFilename(options.companyName) + '-' : '';
    const reportPart = options.reportTitle ? sanitizeFilename(options.reportTitle) + '-' : 'assessment-report-';
    const filename = `${companyPart}${reportPart}${timestamp}.csv`;

    // Ensure browser environment before DOM operations
    ensureBrowserEnvironment('CSV export download');

    // Trigger download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    onProgress?.(100, 'Export completed successfully!');

    return {
      success: true,
      filename,
      size: blob.size
    };

  } catch (error) {
    logError('CSV export error:', error);
    
    // Enhanced error handling with stack trace
    const errorDetails: ExportResult = {
      success: false,
      filename: '',
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    };
    
    // Add stack trace and raw error for debugging (ensure no sensitive data)
    if (error instanceof Error) {
      (errorDetails as any).stack = error.stack;
      (errorDetails as any).rawError = {
        name: error.name,
        message: error.message,
        stack: error.stack
      };
    } else {
      (errorDetails as any).rawError = error;
    }
    
    return errorDetails;
  }
}

/**
 * Generic export function that routes to appropriate format
 * @requires Browser environment - Will not work in SSR or Node.js contexts
 */
export async function exportAssessment(
  results: AssessmentResult | AssessmentResultsResponse,
  options: ExportOptions,
  onProgress?: ProgressCallback
): Promise<ExportResult> {
  try {
    onProgress?.(0, 'Starting export...');

    if (options.format === 'csv') {
      return await exportAssessmentCSV(results, options, onProgress);
    } else if (options.format === 'excel') {
      return await exportAssessmentExcel(results, options, onProgress);
    } else if (options.format === 'pdf') {
      return await exportAssessmentPDF(results, options, onProgress);
    } else {
      throw new Error(`Unsupported export format: ${options.format}`);
    }
  } catch (error) {
    logError('Export error:', error);
    
    // Enhanced error handling with stack trace
    const errorDetails: ExportResult = {
      success: false,
      filename: '',
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    };
    
    // Add stack trace and raw error for debugging (ensure no sensitive data)
    if (error instanceof Error) {
      (errorDetails as any).stack = error.stack;
      (errorDetails as any).rawError = {
        name: error.name,
        message: error.message,
        stack: error.stack
      };
    } else {
      (errorDetails as any).rawError = error;
    }
    
    return errorDetails;
  }
}

/**
 * Utility function to trigger file download
 * @requires Browser environment - Will not work in SSR or Node.js contexts
 */
export function downloadFile(content: string | Blob, filename: string, mimeType: string): void {
  try {
    // Ensure browser environment before DOM operations
    ensureBrowserEnvironment('file download');
    const blob = typeof content === 'string' 
      ? new Blob([content], { type: mimeType })
      : content;
    
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.style.display = 'none';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    // Clean up the URL object
    setTimeout(() => URL.revokeObjectURL(url), 100);
  } catch (error) {
    logError('Download error:', error);
    throw new Error('Failed to download file');
  }
}

/**
 * Validate export data before processing
 * @requires Browser environment for full validation
 */
export function validateExportData(
  results: AssessmentResult | AssessmentResultsResponse,
  options: ExportOptions
): { isValid: boolean; errors: string[] } {
  const errors: string[] = [];

  // Check if results object exists
  if (!results) {
    errors.push('Assessment results are required');
    return { isValid: false, errors };
  }

  // Check required fields using type guards
  const hasValidScore = isAssessmentResult(results) || isFreemiumResponse(results) || 
                        ('overallScore' in results || 'compliance_score' in results);
  if (!hasValidScore) {
    errors.push('Overall score is missing from results');
  }

  // Validate format
  if (!['csv', 'excel', 'pdf'].includes(options.format)) {
    errors.push('Export format must be either "csv", "excel", or "pdf"');
  }

  // Check if gaps exist when requested
  if (options.includeGaps) {
    const normalizedData = normalizeAssessmentData(results);
    if (!normalizedData.gaps || normalizedData.gaps.length === 0) {
      logWarn('No gaps found in results, gaps section will be empty');
    }
  }

  // Check if recommendations exist when requested
  if (options.includeRecommendations) {
    const normalizedData = normalizeAssessmentData(results);
    if (!normalizedData.recommendations || normalizedData.recommendations.length === 0) {
      logWarn('No recommendations found in results, recommendations section will be empty');
    }
  }

  // Check if trend data exists when requested
  if (options.includeTrendAnalysis) {
    if (!options.chartImages?.trendChartImage && !options.customFields?.trendChartImage) {
      logWarn('Trend analysis requested but no trend data available');
    }
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}

/**
 * Get estimated export size
 */
export function getEstimatedExportSize(
  results: AssessmentResult | AssessmentResultsResponse,
  options: ExportOptions
): { estimatedSize: number; unit: string } {
  let estimatedBytes = 1024; // Base size

  const normalizedData = normalizeAssessmentData(results);

  // Add size for gaps
  if (options.includeGaps) {
    estimatedBytes += (normalizedData.gaps?.length || 0) * 200;
  }

  // Add size for recommendations
  if (options.includeRecommendations) {
    estimatedBytes += (normalizedData.recommendations?.length || 0) * 300;
  }

  // Add size for section scores
  if (options.includeSectionBreakdown) {
    estimatedBytes += Object.keys(normalizedData.sectionScores).length * 100;
  }

  // PDF is typically larger
  if (options.format === 'pdf') {
    estimatedBytes *= 3;
  }

  return {
    estimatedSize: Math.round(estimatedBytes / 1024 * 100) / 100,
    unit: 'KB'
  };
}

/**
 * Create export options with defaults
 */
export function createExportOptions(
  format: 'csv' | 'excel' | 'pdf',
  overrides: Partial<ExportOptions> = {}
): ExportOptions {
  const defaults: ExportOptions = {
    format,
    includeQuestions: true,
    includeAnswers: true,
    includeGaps: true,
    includeRecommendations: true,
    includeSectionBreakdown: true,
    includeExecutiveSummary: format === 'pdf',
    includeCharts: true,
    includeTrendAnalysis: true,
    reportTitle: 'Assessment Results Report',
    companyName: 'Your Company'
  };

  return { ...defaults, ...overrides };
}

/**
 * Convert SVG element to PNG data URL for embedding in PDF
 * @requires Browser environment - Will not work in SSR or Node.js contexts
 * @param svgElement The SVG DOM element to convert
 * @param width Target width in pixels
 * @param height Target height in pixels
 * @returns Promise<string> Base64 data URL of the PNG image
 */
export async function svgToPngDataUrl(
  svgElement: SVGElement,
  width: number = 800,
  height: number = 400
): Promise<string> {
  // Ensure browser environment before DOM operations
  ensureBrowserEnvironment('SVG to PNG conversion');
  
  return new Promise((resolve, reject) => {
    try {
      // Clone the SVG to avoid modifying the original
      const clonedSvg = svgElement.cloneNode(true) as SVGElement;

      // Set explicit dimensions
      clonedSvg.setAttribute('width', String(width));
      clonedSvg.setAttribute('height', String(height));

      // Serialize SVG to string
      const svgString = new XMLSerializer().serializeToString(clonedSvg);
      
      // Embed SVG as data URL to avoid cross-origin issues
      const svgDataUrl = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgString);

      // Create image to convert to canvas
      const img = new Image();
      img.width = width;
      img.height = height;
      
      // Set crossOrigin to handle potential CORS issues
      img.crossOrigin = 'anonymous';

      img.onload = () => {
        // Create canvas
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Failed to get canvas context'));
          return;
        }

        // Fill with white background
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, width, height);

        // Draw image
        ctx.drawImage(img, 0, 0, width, height);

        // Convert to data URL
        const dataUrl = canvas.toDataURL('image/png');

        resolve(dataUrl);
      };

      img.onerror = () => {
        reject(new Error('Failed to load SVG image'));
      };

      // Use data URL instead of blob URL to avoid CORS issues
      img.src = svgDataUrl;
    } catch (error) {
      reject(error);
    }
  });
}

// Export all utilities
const exportUtils = {
  exportAssessmentCSV,
  exportAssessmentExcel,
  exportAssessmentPDF,
  exportAssessment,
  downloadFile,
  validateExportData,
  getEstimatedExportSize,
  createExportOptions,
  formatters,
  svgToPngDataUrl,
  THEME_COLORS,
  EXPORT_OPTION_KEYS
};

export default exportUtils;