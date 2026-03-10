/**
 * Assessment export barrel module.
 *
 * This file re-exports the format-specific exporters and shared utilities,
 * plus contains the orchestrator, download, and validation helpers that
 * coordinate the format modules.
 *
 * Consumers import from '@/lib/utils/export' as before — no API change.
 */

// ── Re-export shared internals (types, constants, helpers) ─────────────────
export {
  THEME_COLORS,
  EXPORT_OPTION_KEYS,
  formatters,
  isDevelopment,
} from './export-internals';

export type {
  ExportOptions,
  ExportResult,
  ProgressCallback,
  AssessmentResult,
  Gap,
  Recommendation,
  AssessmentResultsResponse,
  ComplianceGap,
  ComplianceRecommendation,
} from './export-internals';

// ── Re-export format-specific exporters ────────────────────────────────────
export { exportAssessmentExcel } from './export-excel';
export { exportAssessmentPDF } from './export-pdf';
export { exportAssessmentCSV } from './export-csv';

// ── Internal imports needed by orchestrator / validation helpers ───────────
import type {
  AssessmentResult,
  AssessmentResultsResponse,
  ExportOptions,
  ExportResult,
  ProgressCallback,
} from './export-internals';

import {
  buildExportErrorDetails,
  ensureBrowserEnvironment,
  formatters,
  isDevelopment,
  isAssessmentResult,
  isFreemiumResponse,
  logError,
  logWarn,
  normalizeAssessmentData,
  THEME_COLORS,
  EXPORT_OPTION_KEYS,
} from './export-internals';

import { exportAssessmentExcel } from './export-excel';
import { exportAssessmentPDF } from './export-pdf';
import { exportAssessmentCSV } from './export-csv';

// ── Orchestrator ───────────────────────────────────────────────────────────

/**
 * Generic export function that routes to appropriate format
 * @requires Browser environment
 */
export async function exportAssessment(
  results: AssessmentResult | AssessmentResultsResponse,
  options: ExportOptions,
  onProgress?: ProgressCallback,
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
    return buildExportErrorDetails(error, isDevelopment);
  }
}

// ── Download helper ────────────────────────────────────────────────────────

/**
 * Utility function to trigger file download
 * @requires Browser environment
 */
export function downloadFile(
  content: string | Blob,
  filename: string,
  mimeType: string,
): void {
  try {
    ensureBrowserEnvironment('file download');
    const blob =
      typeof content === 'string'
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
    if (error instanceof Error) {
      throw error;
    }
    throw new Error(`Failed to download file: ${String(error)}`);
  }
}

// ── Validation ─────────────────────────────────────────────────────────────

/**
 * Validate export data before processing
 */
export function validateExportData(
  results: AssessmentResult | AssessmentResultsResponse,
  options: ExportOptions,
): { isValid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!results) {
    errors.push('Assessment results are required');
    return { isValid: false, errors };
  }

  const hasValidScore =
    isAssessmentResult(results) ||
    isFreemiumResponse(results) ||
    'overallScore' in results ||
    'compliance_score' in results;
  if (!hasValidScore) {
    errors.push('Overall score is missing from results');
  }

  if (!['csv', 'excel', 'pdf'].includes(options.format)) {
    errors.push('Export format must be either "csv", "excel", or "pdf"');
  }

  const normalizedData = normalizeAssessmentData(results);

  if (options.includeGaps) {
    if (!normalizedData.gaps || normalizedData.gaps.length === 0) {
      logWarn('No gaps found in results, gaps section will be empty');
    }
  }

  if (options.includeRecommendations) {
    if (
      !normalizedData.recommendations ||
      normalizedData.recommendations.length === 0
    ) {
      logWarn(
        'No recommendations found in results, recommendations section will be empty',
      );
    }
  }

  if (options.includeTrendAnalysis) {
    if (
      !options.chartImages?.trendChartImage &&
      !options.customFields?.trendChartImage
    ) {
      logWarn('Trend analysis requested but no trend data available');
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

// ── Size estimation ────────────────────────────────────────────────────────

/**
 * Get estimated export size
 */
export function getEstimatedExportSize(
  results: AssessmentResult | AssessmentResultsResponse,
  options: ExportOptions,
): { estimatedSize: number; unit: string } {
  let estimatedBytes = 1024;

  const normalizedData = normalizeAssessmentData(results);

  if (options.includeGaps) {
    estimatedBytes += (normalizedData.gaps?.length || 0) * 200;
  }

  if (options.includeRecommendations) {
    estimatedBytes += (normalizedData.recommendations?.length || 0) * 300;
  }

  if (options.includeSectionBreakdown) {
    estimatedBytes += Object.keys(normalizedData.sectionScores).length * 100;
  }

  if (options.format === 'pdf') {
    estimatedBytes *= 3;
  }

  return {
    estimatedSize: Math.round((estimatedBytes / 1024) * 100) / 100,
    unit: 'KB',
  };
}

// ── Export options factory ──────────────────────────────────────────────────

/**
 * Create export options with defaults
 */
export function createExportOptions(
  format: 'csv' | 'excel' | 'pdf',
  overrides: Partial<ExportOptions> = {},
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
    companyName: 'Your Company',
  };

  return { ...defaults, ...overrides };
}

// ── SVG to PNG conversion ──────────────────────────────────────────────────

/**
 * Convert SVG element to PNG data URL for embedding in PDF
 * @requires Browser environment
 */
export async function svgToPngDataUrl(
  svgElement: SVGElement,
  width: number = 800,
  height: number = 400,
): Promise<string> {
  ensureBrowserEnvironment('SVG to PNG conversion');

  return new Promise((resolve, reject) => {
    try {
      const clonedSvg = svgElement.cloneNode(true) as SVGElement;

      clonedSvg.setAttribute('width', String(width));
      clonedSvg.setAttribute('height', String(height));

      const svgString = new XMLSerializer().serializeToString(clonedSvg);
      const svgDataUrl =
        'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgString);

      const img = new Image();
      img.width = width;
      img.height = height;
      img.crossOrigin = 'anonymous';

      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Failed to get canvas context'));
          return;
        }

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, width, height);
        ctx.drawImage(img, 0, 0, width, height);

        const dataUrl = canvas.toDataURL('image/png');
        resolve(dataUrl);
      };

      img.onerror = () => {
        reject(new Error('Failed to load SVG image'));
      };

      img.src = svgDataUrl;
    } catch (error) {
      reject(error);
    }
  });
}

// ── Default export ─────────────────────────────────────────────────────────

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
  EXPORT_OPTION_KEYS,
};

export default exportUtils;
