'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { 
  exportAssessment, 
  validateExportData, 
  getEstimatedExportSize,
  createExportOptions,
  type ExportOptions,
  type ExportResult,
  type ProgressCallback
} from '@/lib/utils/export';
import {
  type AssessmentResult,
} from '@/lib/assessment-engine/types';
import {
  type ValidationResult
} from '@/types/assessment-results';
import { useToast } from '@/components/ui/use-toast';

// ============================================================================
// TYPES AND INTERFACES
// ============================================================================

export interface ExportState {
  isExporting: boolean;
  progress: number;
  currentStep: string;
  estimatedTimeRemaining?: number;
  error?: string;
  lastExportResult?: ExportResult;
}

export interface ExportCapabilities {
  canExportCSV: boolean;
  canExportExcel: boolean;
  canExportPDF: boolean;
  maxFileSize: number;
  supportedFormats: string[];
  requiresValidation: boolean;
}

export interface ExportHistoryItem {
  id: string;
  timestamp: Date;
  format: string;
  filename: string;
  fileSize: number;
  success: boolean;
  error?: string;
  downloadUrl?: string;
  expiresAt?: Date;
}

export interface BatchExportOptions {
  assessments: (AssessmentResult | AssessmentResultsResponse)[];
  format: 'csv' | 'excel' | 'pdf';
  combineFiles: boolean;
  zipOutput: boolean;
  batchSize: number;
}

export interface UseAssessmentExportOptions {
  enableHistory: boolean;
  maxHistoryItems: number;
  autoCleanup: boolean;
  enableBatchExport: boolean;
  defaultExportOptions?: Partial<ExportOptions>;
  onExportComplete?: (result: ExportResult) => void;
  onExportError?: (error: string) => void;
  onProgressUpdate?: (progress: number, message: string) => void;
}

export interface UseAssessmentExportReturn {
  // State
  exportState: ExportState;
  exportHistory: ExportHistoryItem[];
  capabilities: ExportCapabilities;
  
  // Export methods
  exportAssessmentData: (
    results: AssessmentResult | AssessmentResultsResponse,
    options: ExportOptions
  ) => Promise<ExportResult>;
  
  exportCSV: (
    results: AssessmentResult | AssessmentResultsResponse,
    options?: Partial<ExportOptions>
  ) => Promise<ExportResult>;

  exportExcel: (
    results: AssessmentResult | AssessmentResultsResponse,
    options?: Partial<ExportOptions>
  ) => Promise<ExportResult>;

  exportPDF: (
    results: AssessmentResult | AssessmentResultsResponse,
    options?: Partial<ExportOptions>
  ) => Promise<ExportResult>;
  
  // Batch export
  batchExport: (options: BatchExportOptions) => Promise<ExportResult[]>;
  
  // Validation and utilities
  validateExport: (
    results: AssessmentResult | AssessmentResultsResponse,
    options: ExportOptions
  ) => ValidationResult;
  
  getExportCapabilities: () => ExportCapabilities;
  
  getEstimatedSize: (
    results: AssessmentResult | AssessmentResultsResponse,
    options: ExportOptions
  ) => { estimatedSize: number; unit: string };
  
  // Control methods
  cancelExport: () => void;
  retryLastExport: () => Promise<ExportResult | null>;
  clearHistory: () => void;
  
  // History management
  getExportHistory: () => ExportHistoryItem[];
  removeFromHistory: (id: string) => void;
  downloadFromHistory: (id: string) => Promise<boolean>;
  
  // Cleanup
  cleanup: () => void;
}

// ============================================================================
// CONSTANTS
// ============================================================================

const DEFAULT_OPTIONS: UseAssessmentExportOptions = {
  enableHistory: true,
  maxHistoryItems: 50,
  autoCleanup: true,
  enableBatchExport: true,
  defaultExportOptions: {
    includeGaps: true,
    includeRecommendations: true,
    includeSectionBreakdown: true,
    includeExecutiveSummary: true
  }
};

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const _EXPORT_TIMEOUT = 5 * 60 * 1000; // 5 minutes
const HISTORY_STORAGE_KEY = 'assessment-export-history';
const CLEANUP_INTERVAL = 60 * 1000; // 1 minute

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function generateExportId(): string {
  return `export_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function createExportHistoryItem(
  result: ExportResult,
  format: string,
  _options: ExportOptions
): ExportHistoryItem {
  return {
    id: generateExportId(),
    timestamp: new Date(),
    format,
    filename: result.filename,
    fileSize: result.size || 0,
    success: result.success,
    ...(result.error && { error: result.error }),
    ...(result.downloadUrl && { downloadUrl: result.downloadUrl }),
    expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000) // 24 hours
  };
}

function loadExportHistory(): ExportHistoryItem[] {
  try {
    const stored = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!stored) return [];
    
    const history = JSON.parse(stored);
    return history.map((item: any) => ({
      ...item,
      timestamp: new Date(item.timestamp),
      expiresAt: item.expiresAt ? new Date(item.expiresAt) : undefined
    }));
  } catch (error) {
    console.warn('Failed to load export history:', error);
    return [];
  }
}

function saveExportHistory(history: ExportHistoryItem[]): void {
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
  } catch (error) {
    console.warn('Failed to save export history:', error);
  }
}

function cleanupExpiredHistory(history: ExportHistoryItem[]): ExportHistoryItem[] {
  const now = new Date();
  return history.filter(item => !item.expiresAt || item.expiresAt > now);
}

// ============================================================================
// MAIN HOOK
// ============================================================================

export function useAssessmentExport(
  options: Partial<UseAssessmentExportOptions> = {}
): UseAssessmentExportReturn {
  const config = { ...DEFAULT_OPTIONS, ...options };
  const { toast } = useToast();
  
  // State management
  const [exportState, setExportState] = useState<ExportState>({
    isExporting: false,
    progress: 0,
    currentStep: 'Ready'
  });
  
  const [exportHistory, setExportHistory] = useState<ExportHistoryItem[]>([]);
  
  // Refs for cleanup and cancellation
  const abortControllerRef = useRef<AbortController | null>(null);
  const cleanupIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastExportOptionsRef = useRef<{
    results: AssessmentResult | AssessmentResultsResponse;
    options: ExportOptions;
  } | null>(null);

  // ============================================================================
  // INITIALIZATION AND CLEANUP
  // ============================================================================

  useEffect(() => {
    // Load export history on mount
    if (config.enableHistory) {
      const history = loadExportHistory();
      const cleanHistory = cleanupExpiredHistory(history);
      setExportHistory(cleanHistory);
      
      if (cleanHistory.length !== history.length) {
        saveExportHistory(cleanHistory);
      }
    }

    // Setup cleanup interval
    if (config.autoCleanup) {
      cleanupIntervalRef.current = setInterval(() => {
        setExportHistory(prev => {
          const cleaned = cleanupExpiredHistory(prev);
          if (cleaned.length !== prev.length) {
            saveExportHistory(cleaned);
          }
          return cleaned;
        });
      }, CLEANUP_INTERVAL);
    }

    return () => {
      if (cleanupIntervalRef.current) {
        clearInterval(cleanupIntervalRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [config.enableHistory, config.autoCleanup]);

  // Save history changes to localStorage
  useEffect(() => {
    if (config.enableHistory && exportHistory.length > 0) {
      saveExportHistory(exportHistory);
    }
  }, [exportHistory, config.enableHistory]);

  // ============================================================================
  // PROGRESS AND STATE MANAGEMENT
  // ============================================================================

  const updateProgress: ProgressCallback = useCallback((progress: number, message: string) => {
    setExportState(prev => ({
      ...prev,
      progress,
      currentStep: message,
      estimatedTimeRemaining: progress > 0 ? 
        ((Date.now() - (prev as any).startTime) / progress) * (100 - progress) : 
        0
    }));
    
    config.onProgressUpdate?.(progress, message);
  }, [config.onProgressUpdate]);

  const resetExportState = useCallback(() => {
    setExportState({
      isExporting: false,
      progress: 0,
      currentStep: 'Ready'
    });
  }, []);

  const setExportError = useCallback((error: string) => {
    setExportState(prev => ({
      ...prev,
      isExporting: false,
      error,
      currentStep: 'Error'
    }));
    
    config.onExportError?.(error);
    
    toast({
      title: 'Export Failed',
      description: error,
      variant: 'destructive'
    });
  }, [config.onExportError, toast]);

  // ============================================================================
  // VALIDATION AND CAPABILITIES
  // ============================================================================

  const validateExport = useCallback((
    results: AssessmentResult | AssessmentResultsResponse,
    options: ExportOptions
  ): ValidationResult => {
    const validation = validateExportData(results, options);
    const warnings: string[] = [];
    const suggestions: string[] = [];

    // Check file size
    const sizeEstimate = getEstimatedExportSize(results, options);
    const unitMultipliers: Record<string, number> = {
      'B': 1,
      'KB': 1024,
      'MB': 1024 * 1024,
      'GB': 1024 * 1024 * 1024
    };
    const estimatedBytes = sizeEstimate.estimatedSize * (unitMultipliers[sizeEstimate.unit] || 1024);
    
    if (estimatedBytes > MAX_FILE_SIZE) {
      warnings.push(`Estimated file size (${sizeEstimate.estimatedSize} ${sizeEstimate.unit}) exceeds limit`);
      suggestions.push('Consider reducing content inclusion options');
    }

    // Check data completeness
    const gaps = 'gaps' in results ? results.gaps : results.compliance_gaps;
    if (options.includeGaps && (!gaps || gaps.length === 0)) {
      warnings.push('No gaps found in assessment results');
    }

    if (options.includeRecommendations && (!results.recommendations || results.recommendations.length === 0)) {
      warnings.push('No recommendations found in assessment results');
    }

    return {
      ...validation,
      warnings,
      suggestions
    };
  }, []);

  const getExportCapabilities = useCallback((): ExportCapabilities => {
    return {
      canExportCSV: true,
      canExportExcel: true,
      canExportPDF: true,
      maxFileSize: MAX_FILE_SIZE,
      supportedFormats: ['csv', 'excel', 'pdf'],
      requiresValidation: true
    };
  }, []);

  const getEstimatedSize = useCallback((
    results: AssessmentResult | AssessmentResultsResponse,
    options: ExportOptions
  ) => {
    return getEstimatedExportSize(results, options);
  }, []);

  // ============================================================================
  // CORE EXPORT FUNCTIONALITY
  // ============================================================================

  const exportAssessmentData = useCallback(async (
    results: AssessmentResult | AssessmentResultsResponse,
    options: ExportOptions
  ): Promise<ExportResult> => {
    // Validation
    const validation = validateExport(results, options);
    if (!validation.isValid) {
      const error = `Validation failed: ${validation.errors.join(', ')}`;
      setExportError(error);
      return { success: false, filename: '', error };
    }

    // Show warnings if any
    if (validation.warnings.length > 0) {
      toast({
        title: 'Export Warnings',
        description: validation.warnings.join(', '),
        variant: 'default'
      });
    }

    try {
      // Setup abort controller
      abortControllerRef.current = new AbortController();
      
      // Initialize export state
      setExportState({
        isExporting: true,
        progress: 0,
        currentStep: 'Starting export...',
        error: undefined,
        startTime: Date.now()
      } as any);

      // Store for retry functionality
      lastExportOptionsRef.current = { results, options };

      // Perform export
      const result = await exportAssessment(results, options, updateProgress);

      if (result.success) {
        // Update state
        setExportState(prev => ({
          ...prev,
          isExporting: false,
          progress: 100,
          currentStep: 'Export completed',
          lastExportResult: result
        }));

        // Add to history
        if (config.enableHistory) {
          const historyItem = createExportHistoryItem(result, options.format, options);
          setExportHistory(prev => {
            const newHistory = [historyItem, ...prev].slice(0, config.maxHistoryItems);
            return newHistory;
          });
        }

        // Success notification
        toast({
          title: 'Export Successful',
          description: `${result.filename} has been downloaded`,
          variant: 'default'
        });

        config.onExportComplete?.(result);
      } else {
        setExportError(result.error || 'Export failed');
      }

      return result;

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      setExportError(errorMessage);
      return { success: false, filename: '', error: errorMessage };
    } finally {
      abortControllerRef.current = null;
    }
  }, [validateExport, updateProgress, config, toast]);

  // ============================================================================
  // FORMAT-SPECIFIC EXPORT METHODS
  // ============================================================================

  const exportCSV = useCallback(async (
    results: AssessmentResult | AssessmentResultsResponse,
    optionOverrides: Partial<ExportOptions> = {}
  ): Promise<ExportResult> => {
    const options = createExportOptions('csv', {
      ...config.defaultExportOptions,
      ...optionOverrides
    });

    return exportAssessmentData(results, options);
  }, [exportAssessmentData, config.defaultExportOptions]);

  const exportExcel = useCallback(async (
    results: AssessmentResult | AssessmentResultsResponse,
    optionOverrides: Partial<ExportOptions> = {}
  ): Promise<ExportResult> => {
    const options = createExportOptions('excel', {
      ...config.defaultExportOptions,
      ...optionOverrides
    });

    return exportAssessmentData(results, options);
  }, [exportAssessmentData, config.defaultExportOptions]);

  const exportPDF = useCallback(async (
    results: AssessmentResult | AssessmentResultsResponse,
    optionOverrides: Partial<ExportOptions> = {}
  ): Promise<ExportResult> => {
    const options = createExportOptions('pdf', {
      ...config.defaultExportOptions,
      includeExecutiveSummary: true,
      ...optionOverrides
    });

    return exportAssessmentData(results, options);
  }, [exportAssessmentData, config.defaultExportOptions]);

  // ============================================================================
  // BATCH EXPORT FUNCTIONALITY
  // ============================================================================

  const batchExport = useCallback(async (
    batchOptions: BatchExportOptions
  ): Promise<ExportResult[]> => {
    if (!config.enableBatchExport) {
      throw new Error('Batch export is not enabled');
    }

    const results: ExportResult[] = [];
    const { assessments, format, batchSize = 5 } = batchOptions;

    try {
      setExportState({
        isExporting: true,
        progress: 0,
        currentStep: `Starting batch export of ${assessments.length} assessments...`
      });

      // Process in batches
      for (let i = 0; i < assessments.length; i += batchSize) {
        const batch = assessments.slice(i, i + batchSize);
        const batchPromises = batch.map(async (assessment, index) => {
          const options = createExportOptions(format, {
            ...config.defaultExportOptions,
            reportTitle: `Assessment Report ${i + index + 1}`
          });

          return exportAssessment(assessment, options, (progress, message) => {
            const overallProgress = ((i + index) / assessments.length) * 100 + (progress / assessments.length);
            updateProgress(overallProgress, `${message} (${i + index + 1}/${assessments.length})`);
          });
        });

        const batchResults = await Promise.allSettled(batchPromises);
        
        batchResults.forEach((result, index) => {
          if (result.status === 'fulfilled') {
            results.push(result.value);
          } else {
            results.push({
              success: false,
              filename: `assessment-${i + index + 1}-failed`,
              error: result.reason?.message || 'Unknown error'
            });
          }
        });
      }

      // Update final state
      const successCount = results.filter(r => r.success).length;
      const failCount = results.length - successCount;

      setExportState({
        isExporting: false,
        progress: 100,
        currentStep: `Batch export completed: ${successCount} successful, ${failCount} failed`
      });

      toast({
        title: 'Batch Export Completed',
        description: `${successCount} of ${results.length} exports completed successfully`,
        variant: successCount === results.length ? 'default' : 'destructive'
      });

      return results;

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Batch export failed';
      setExportError(errorMessage);
      throw error;
    }
  }, [config.enableBatchExport, config.defaultExportOptions, updateProgress, toast]);

  // ============================================================================
  // CONTROL METHODS
  // ============================================================================

  const cancelExport = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    setExportState({
      isExporting: false,
      progress: 0,
      currentStep: 'Export cancelled',
      error: 'Export was cancelled by user'
    });

    toast({
      title: 'Export Cancelled',
      description: 'The export operation has been cancelled',
      variant: 'default'
    });
  }, [toast]);

  const retryLastExport = useCallback(async (): Promise<ExportResult | null> => {
    if (!lastExportOptionsRef.current) {
      toast({
        title: 'No Export to Retry',
        description: 'No previous export found to retry',
        variant: 'destructive'
      });
      return null;
    }

    const { results, options } = lastExportOptionsRef.current;
    return exportAssessmentData(results, options);
  }, [exportAssessmentData, toast]);

  // ============================================================================
  // HISTORY MANAGEMENT
  // ============================================================================

  const clearHistory = useCallback(() => {
    setExportHistory([]);
    localStorage.removeItem(HISTORY_STORAGE_KEY);
    
    toast({
      title: 'History Cleared',
      description: 'Export history has been cleared',
      variant: 'default'
    });
  }, [toast]);

  const getExportHistory = useCallback(() => {
    return exportHistory;
  }, [exportHistory]);

  const removeFromHistory = useCallback((id: string) => {
    setExportHistory(prev => prev.filter(item => item.id !== id));
  }, []);

  const downloadFromHistory = useCallback(async (id: string): Promise<boolean> => {
    const item = exportHistory.find(h => h.id === id);
    if (!item) {
      toast({
        title: 'Export Not Found',
        description: 'The requested export could not be found in history',
        variant: 'destructive'
      });
      return false;
    }

    if (item.expiresAt && item.expiresAt < new Date()) {
      toast({
        title: 'Export Expired',
        description: 'This export has expired and is no longer available',
        variant: 'destructive'
      });
      return false;
    }

    if (!item.downloadUrl) {
      toast({
        title: 'Download Unavailable',
        description: 'Download URL is not available for this export',
        variant: 'destructive'
      });
      return false;
    }

    try {
      // Trigger download
      const link = document.createElement('a');
      link.href = item.downloadUrl;
      link.download = item.filename;
      link.click();
      
      toast({
        title: 'Download Started',
        description: `Downloading ${item.filename}`,
        variant: 'default'
      });
      
      return true;
    } catch (_error) {
      toast({
        title: 'Download Failed',
        description: 'Failed to start download',
        variant: 'destructive'
      });
      return false;
    }
  }, [exportHistory, toast]);

  // ============================================================================
  // CLEANUP
  // ============================================================================

  const cleanup = useCallback(() => {
    // Cancel any ongoing exports
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Clear intervals
    if (cleanupIntervalRef.current) {
      clearInterval(cleanupIntervalRef.current);
    }

    // Reset state
    resetExportState();

    // Clear refs
    lastExportOptionsRef.current = null;
    abortControllerRef.current = null;
    cleanupIntervalRef.current = null;
  }, [resetExportState]);

  // ============================================================================
  // RETURN HOOK INTERFACE
  // ============================================================================

  return {
    // State
    exportState,
    exportHistory,
    capabilities: getExportCapabilities(),
    
    // Export methods
    exportAssessmentData,
    exportCSV,
    exportExcel,
    exportPDF,
    
    // Batch export
    batchExport,
    
    // Validation and utilities
    validateExport,
    getExportCapabilities,
    getEstimatedSize,
    
    // Control methods
    cancelExport,
    retryLastExport,
    clearHistory,
    
    // History management
    getExportHistory,
    removeFromHistory,
    downloadFromHistory,
    
    // Cleanup
    cleanup
  };
}

// ============================================================================
// EXPORT DEFAULT
// ============================================================================

export default useAssessmentExport;