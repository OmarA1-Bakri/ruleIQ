'use client';

import React, { useState, useCallback, useRef } from 'react';
import { 
  Download, 
  FileText, 
  FileSpreadsheet, 
  Settings, 
  CheckCircle, 
  AlertCircle, 
  Loader2,
  FileDown,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { useToast } from '@/components/ui/use-toast';
import {
  exportAssessment,
  createExportOptions,
  validateExportData,
  getEstimatedExportSize,
  svgToPngDataUrl,
  type ExportOptions,
  type ExportResult
} from '@/lib/utils/export';
import type { AssessmentResult } from '@/lib/assessment-engine/types';
import type { DetailedAssessmentResults } from '@/types/assessment-results';
import type { AssessmentResultsResponse } from '@/types/freemium';

// Neural Purple theme colors
const THEME_COLORS = {
  primary: '#8b5cf66f1',
  secondary: '#8b5cf6cf6',
  accent: '#8b5cf65f7',
  success: '#8b5cf6981',
  warning: '#8b5cf6e0b',
  danger: '#8b5cf6444',
  text: '#8b5cf693b',
  textLight: '#8b5cf648b',
  background: '#8b5cf6afc',
  white: '#fffffffff'
};

// Type-safe UI option interface to clearly separate UI concerns from export concerns
interface UIExportOptions {
  includeSectionDetails?: boolean;
  includeGapAnalysis?: boolean;
  includeRecommendations?: boolean;
  includeTrendAnalysis?: boolean;
  includeCharts?: boolean;
  includeExecutiveSummary?: boolean;
  reportTitle?: string;
  fileName?: string;
  estimatedBreakdown?: boolean;
}

// Type-safe UI to Export option key mapping using satisfies for compile-time safety
const UI_TO_EXPORT_KEY_MAP = {
  'includeSectionDetails': 'includeSectionBreakdown',
  'includeGapAnalysis': 'includeGaps',
  // Direct pass-through mappings
  'includeRecommendations': 'includeRecommendations',
  'includeTrendAnalysis': 'includeTrendAnalysis',
  'includeCharts': 'includeCharts',
  'includeExecutiveSummary': 'includeExecutiveSummary',
  'reportTitle': 'reportTitle',
  'fileName': 'fileName',
  'estimatedBreakdown': 'estimatedBreakdown'
} as const satisfies Record<keyof UIExportOptions, keyof ExportOptions | 'fileName' | 'estimatedBreakdown'>;

// Helper function to map UI option names to export utility option names
const mapUIOptionsToExportOptions = (uiOptions: Partial<UIExportOptions>): Partial<ExportOptions & { fileName?: string; estimatedBreakdown?: boolean }> => {
  const mappedOptions: any = {};

  // Type-safe iteration through UI options
  (Object.keys(uiOptions) as Array<keyof UIExportOptions>).forEach((key) => {
    const value = uiOptions[key];
    const mappedKey = UI_TO_EXPORT_KEY_MAP[key];

    if (mappedKey && value !== undefined) {
      // Use bracket notation for dynamic property assignment
      mappedOptions[mappedKey] = value;
    }
  });

  return mappedOptions as Partial<ExportOptions & { fileName?: string; estimatedBreakdown?: boolean }>;
};

// Export format configurations
const EXPORT_FORMATS = {
  csv: {
    label: 'CSV Export',
    description: 'Simple comma-separated values for data processing',
    icon: FileSpreadsheet,
    color: THEME_COLORS.accent,
    extension: '.csv',
    mimeType: 'text/csv'
  },
  excel: {
    label: 'Excel Export',
    description: 'Spreadsheet format for data analysis',
    icon: FileSpreadsheet,
    color: THEME_COLORS.success,
    extension: '.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  },
  pdf: {
    label: 'PDF Report',
    description: 'Professional report with charts and analysis',
    icon: FileText,
    color: THEME_COLORS.primary,
    extension: '.pdf',
    mimeType: 'application/pdf'
  }
} as const;

// Export state type
interface ExportState {
  isExporting: boolean;
  progress: number;
  currentStep: string;
  error: string | null;
  success: boolean;
  result: ExportResult | null;
}

// Component props
interface ExportButtonProps {
  results: AssessmentResult | AssessmentResultsResponse | DetailedAssessmentResults;
  className?: string;
  variant?: 'default' | 'outline' | 'ghost';
  size?: 'default' | 'sm' | 'lg';
  disabled?: boolean;
  companyName?: string;
  reportTitle?: string;
  onExportStart?: () => void;
  onExportComplete?: (result: ExportResult) => void;
  onExportError?: (error: string) => void;
  showAdvancedOptions?: boolean;
  defaultFormat?: 'csv' | 'excel' | 'pdf';
  estimatedBreakdown?: boolean;
  trendData?: any[];
}

// Component has been updated to use the app's toast system via useToast hook

// Simple modal component (since dialog.tsx doesn't exist)
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  className?: string;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children, className }) => {
  const modalRef = useRef<HTMLDivElement>(null);

  // Handle escape key
  React.useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  // Handle backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div 
        ref={modalRef}
        className={cn(
          "relative bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden",
          className
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-6 border-b">
          <h2 id="modal-title" className="text-xl font-semibold text-gray-900">
            {title}
          </h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 w-8 p-0"
            aria-label="Close modal"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
          {children}
        </div>
      </div>
    </div>
  );
};

// Main ExportButton component
export const ExportButton: React.FC<ExportButtonProps> = ({
  results,
  className,
  variant = 'default',
  size = 'default',
  disabled = false,
  companyName,
  reportTitle,
  onExportStart,
  onExportComplete,
  onExportError,
  showAdvancedOptions = true,
  defaultFormat = 'pdf',
  estimatedBreakdown = false,
  trendData: _trendData
}) => {
  // Use the app's toast system
  const { toast } = useToast();

  // State management
  const [exportState, setExportState] = useState<ExportState>({
    isExporting: false,
    progress: 0,
    currentStep: '',
    error: null,
    success: false,
    result: null
  });

  const [optionsModal, setOptionsModal] = useState<{
    isOpen: boolean;
    format: 'csv' | 'excel' | 'pdf';
    options: Partial<UIExportOptions>;
  }>({
    isOpen: false,
    format: defaultFormat,
    options: {}
  });

  // Progress tracking
  const progressRef = useRef<NodeJS.Timeout | null>(null);
  // Track last export parameters for retry
  const lastExportRef = useRef<{format:'csv'|'excel'|'pdf', options: Partial<UIExportOptions>} | null>(null);

  // Reset export state
  const resetExportState = useCallback(() => {
    setExportState({
      isExporting: false,
      progress: 0,
      currentStep: '',
      error: null,
      success: false,
      result: null
    });
  }, []);

  // Progress callback for export functions
  const handleProgress = useCallback((progress: number, message: string) => {
    setExportState(prev => ({
      ...prev,
      progress,
      currentStep: message
    }));
  }, []);

  // Capture chart images for PDF export
  const captureChartImages = useCallback(async () => {
    const chartImages: any = {};

    try {
      // Find gauge chart SVG
      const gaugeSvg = document.querySelector('#compliance-gauge-chart svg') as SVGElement;
      if (gaugeSvg) {
        chartImages.gaugeImage = await svgToPngDataUrl(gaugeSvg, 400, 300);
      }

      // Find trend chart SVG
      const trendSvg = document.querySelector('#trend-analysis-chart svg') as SVGElement;
      if (trendSvg) {
        chartImages.trendChartImage = await svgToPngDataUrl(trendSvg, 600, 300);
      }

      // Find gap analysis chart SVG - prefer visible tab content
      // First try to find active tab panel, then fall back to overview/gaps
      const activeTabPanel = document.querySelector('[role="tabpanel"][data-state="active"]');
      let gapSvg: SVGElement | null = null;

      if (activeTabPanel) {
        // Look for gap analysis chart within active tab
        gapSvg = activeTabPanel.querySelector('[id^="gap-analysis-chart"] svg:not([hidden])') as SVGElement;
      }

      // Fallback to original selectors if not found in active tab
      if (!gapSvg) {
        gapSvg = document.querySelector('#gap-analysis-chart-overview svg:not([hidden]), #gap-analysis-chart-gaps svg:not([hidden])') as SVGElement;
      }

      if (gapSvg) {
        chartImages.gapAnalysisImage = await svgToPngDataUrl(gapSvg, 600, 400);
      }

      // Section scores chart capture removed - no matching element in DOM
    } catch (error) {
      console.warn('Failed to capture chart images:', error);
    }

    return chartImages;
  }, []);

  // Handle export execution
  const executeExport = useCallback(async (
    format: 'csv' | 'excel' | 'pdf',
    customOptions: Partial<UIExportOptions> = {}
  ) => {
    // Store parameters for potential retry
    lastExportRef.current = { format, options: customOptions };

    try {
      // Map UI option names to export utility option names
      const mappedOptions = mapUIOptionsToExportOptions(customOptions);

      // Capture chart images if PDF format and charts are requested
      let chartImages = {};
      if (format === 'pdf' && mappedOptions.includeCharts !== false) {
        chartImages = await captureChartImages();
        // Don't delete includeCharts for PDF - pass it to export utility
      }

      // Remove includeCharts for non-PDF formats as it's not applicable
      if (format !== 'pdf') {
        delete mappedOptions.includeCharts;
      }

      // Validate data first
      const baseOptions = createExportOptions(format, {
        ...(companyName && { companyName }),
        ...(reportTitle && { reportTitle }),
        ...mappedOptions,
        chartImages,
        estimatedBreakdown
      });

      const validation = validateExportData(results, baseOptions);
      if (!validation.isValid) {
        throw new Error(`Invalid export data: ${validation.errors.join(', ')}`);
      }

      // Start export
      onExportStart?.();
      setExportState({
        isExporting: true,
        progress: 0,
        currentStep: 'Initializing export...',
        error: null,
        success: false,
        result: null
      });

      // Show initial toast
      toast({
        title: 'Export Started',
        description: `Starting ${format.toUpperCase()} export...`,
      });

      // Execute export with progress tracking
      const result = await exportAssessment(results, baseOptions, handleProgress);

      if (result.success) {
        setExportState(prev => ({
          ...prev,
          isExporting: false,
          progress: 100,
          currentStep: 'Export completed successfully!',
          success: true,
          result
        }));

        toast({
          title: 'Export Complete',
          description: `${format.toUpperCase()} export completed successfully! File: ${result.filename}`,
          variant: 'default',
        });
        onExportComplete?.(result);
      } else {
        throw new Error(result.error || 'Export failed');
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown export error';
      
      setExportState(prev => ({
        ...prev,
        isExporting: false,
        error: errorMessage,
        currentStep: 'Export failed'
      }));

      toast({
        title: 'Export Failed',
        description: errorMessage,
        variant: 'destructive',
      });
      onExportError?.(errorMessage);
    }
  }, [results, companyName, reportTitle, onExportStart, onExportComplete, onExportError, handleProgress, captureChartImages]);

  // Handle quick export (without options modal)
  const handleQuickExport = useCallback((format: 'csv' | 'excel' | 'pdf') => {
    // Always include companyName and reportTitle even for quick exports
    const defaultOptions = {
      ...(companyName && { companyName }),
      ...(reportTitle && { reportTitle })
    };
    executeExport(format, defaultOptions);
  }, [executeExport, companyName, reportTitle]);

  // Handle advanced export (with options modal)
  const handleAdvancedExport = useCallback((format: 'csv' | 'excel' | 'pdf') => {
    setOptionsModal({
      isOpen: true,
      format,
      options: {
        includeSectionDetails: true,
        includeGapAnalysis: true,
        includeRecommendations: true,
        includeTrendAnalysis: false,
        includeCharts: format === 'pdf',
        includeExecutiveSummary: format === 'pdf'
      }
    });
  }, []);

  // Handle options modal submit
  const handleOptionsSubmit = useCallback(() => {
    executeExport(optionsModal.format, optionsModal.options);
    setOptionsModal(prev => ({ ...prev, isOpen: false }));
  }, [executeExport, optionsModal]);

  // Handle retry
  const handleRetry = useCallback(() => {
    resetExportState();
    if (lastExportRef.current) {
      // Retry with last used options
      executeExport(lastExportRef.current.format, lastExportRef.current.options);
    }
  }, [resetExportState, executeExport]);

  // Get estimated file size
  const getFileSize = useCallback((format: 'csv' | 'excel' | 'pdf') => {
    const options = createExportOptions(format);
    const estimate = getEstimatedExportSize(results, options);
    return `~${estimate.estimatedSize} ${estimate.unit}`;
  }, [results]);

  // Cleanup on unmount
  React.useEffect(() => {
    return () => {
      if (progressRef.current) {
        clearTimeout(progressRef.current);
      }
    };
  }, []);

  // Auto-hide success state after 5 seconds
  React.useEffect(() => {
    if (exportState.success) {
      const timer = setTimeout(resetExportState, 5000);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [exportState.success, resetExportState]);

  // Render export progress
  const renderProgress = () => {
    if (!exportState.isExporting && !exportState.error && !exportState.success) {
      return null;
    }

    return (
      <div className="mt-2 p-3 bg-gray-50 rounded-lg border">
        {exportState.isExporting && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">{exportState.currentStep}</span>
              <span className="text-gray-500">{exportState.progress}%</span>
            </div>
            <Progress 
              value={exportState.progress} 
              className="h-2"
              indicatorClassName="bg-gradient-to-r from-purple-500 to-purple-600"
            />
          </div>
        )}

        {exportState.error && (
          <div className="flex items-start gap-2 text-sm text-red-600">
            <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-medium">Export Failed</p>
              <p className="text-red-500">{exportState.error}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRetry}
                className="mt-2 text-red-600 border-red-200 hover:bg-red-50"
              >
                Try Again
              </Button>
            </div>
          </div>
        )}

        {exportState.success && exportState.result && (
          <div className="flex items-start gap-2 text-sm text-green-600">
            <CheckCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-medium">Export Completed</p>
              <p className="text-green-500">
                {exportState.result.filename} 
                {exportState.result.size && ` (${(exportState.result.size / 1024).toFixed(1)} KB)`}
              </p>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Render options modal
  const renderOptionsModal = () => {
    const format = optionsModal.format;
    const formatConfig = EXPORT_FORMATS[format];

    return (
      <Modal
        isOpen={optionsModal.isOpen}
        onClose={() => setOptionsModal(prev => ({ ...prev, isOpen: false }))}
        title={`${formatConfig.label} Options`}
        className="max-w-3xl"
      >
        <div className="space-y-6">
          {/* Format info */}
          <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
            <formatConfig.icon 
              className="h-8 w-8" 
              style={{ color: formatConfig.color }} 
            />
            <div>
              <h3 className="font-medium text-gray-900">{formatConfig.label}</h3>
              <p className="text-sm text-gray-600">{formatConfig.description}</p>
              <p className="text-xs text-gray-500 mt-1">
                Estimated size: {getFileSize(format)}
              </p>
            </div>
          </div>

          {/* Content options */}
          <div>
            <h4 className="font-medium text-gray-900 mb-3">Content to Include</h4>
            <div className="grid grid-cols-2 gap-3">
              {[
                { key: 'includeSectionDetails', label: 'Section Breakdown', mapTo: 'includeSectionBreakdown' },
                { key: 'includeGapAnalysis', label: 'Gap Analysis', mapTo: 'includeGaps' },
                { key: 'includeRecommendations', label: 'Recommendations', mapTo: 'includeRecommendations' },
                { key: 'includeTrendAnalysis', label: 'Trend Analysis', mapTo: 'includeTrendAnalysis' },
                { key: 'includeCharts', label: 'Charts & Graphs', mapTo: 'includeCharts', disabled: format === 'excel' },
                { key: 'includeExecutiveSummary', label: 'Executive Summary', mapTo: 'includeExecutiveSummary', disabled: format === 'excel' }
              ].map(({ key, label, disabled }) => {
                const isChecked = optionsModal.options[key as keyof typeof optionsModal.options] as boolean || false;
                return (
                  <label key={key} className={cn(
                    "flex items-center gap-2 p-2 rounded border cursor-pointer transition-colors",
                    disabled ? "opacity-50 cursor-not-allowed bg-gray-50" : "hover:bg-gray-50",
                    isChecked ? "border-purple-200 bg-purple-50" : "border-gray-200"
                  )}>
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={disabled}
                      onChange={(e) => setOptionsModal(prev => ({
                        ...prev,
                        options: {
                          ...prev.options,
                          [key]: e.target.checked
                        }
                      }))}
                      className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    />
                    <span className="text-sm text-gray-700">{label}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Custom options */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Report Title
              </label>
              <input
                type="text"
                value={optionsModal.options.reportTitle || reportTitle || 'Assessment Report'}
                onChange={(e) => setOptionsModal(prev => ({
                  ...prev,
                  options: {
                    ...prev.options,
                    reportTitle: e.target.value
                  }
                }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-purple-500 focus:border-purple-500"
                placeholder="Enter report title"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                File Name
              </label>
              <input
                type="text"
                value={optionsModal.options.fileName || ''}
                onChange={(e) => setOptionsModal(prev => ({
                  ...prev,
                  options: {
                    ...prev.options,
                    fileName: e.target.value
                  }
                }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-purple-500 focus:border-purple-500"
                placeholder="Auto-generated"
              />
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button
              variant="outline"
              onClick={() => setOptionsModal(prev => ({ ...prev, isOpen: false }))}
            >
              Cancel
            </Button>
            <Button
              onClick={handleOptionsSubmit}
              disabled={exportState.isExporting}
              className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800"
            >
              {exportState.isExporting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Exporting...
                </>
              ) : (
                <>
                  <FileDown className="h-4 w-4 mr-2" />
                  Export {formatConfig.label}
                </>
              )}
            </Button>
          </div>
        </div>
      </Modal>
    );
  };

  return (
    <div className={cn("relative", className)}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant={variant}
            size={size}
            disabled={disabled || exportState.isExporting}
            className={cn(
              "gap-2",
              exportState.success && "border-green-200 bg-green-50 text-green-700 hover:bg-green-100",
              exportState.error && "border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
            )}
            aria-label="Export assessment results"
            aria-expanded="false"
            aria-haspopup="menu"
          >
            {exportState.isExporting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Exporting...
              </>
            ) : exportState.success ? (
              <>
                <CheckCircle className="h-4 w-4" />
                Exported
              </>
            ) : exportState.error ? (
              <>
                <AlertCircle className="h-4 w-4" />
                Export Failed
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Export
              </>
            )}
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent 
          align="end" 
          className="w-64"
          aria-label="Export options menu"
        >
          <DropdownMenuLabel className="flex items-center gap-2">
            <FileDown className="h-4 w-4" />
            Export Options
          </DropdownMenuLabel>
          <DropdownMenuSeparator />

          {Object.entries(EXPORT_FORMATS).map(([format, config]) => (
            <React.Fragment key={format}>
              <DropdownMenuItem
                onClick={() => handleQuickExport(format as 'csv' | 'excel' | 'pdf')}
                disabled={exportState.isExporting}
                className="flex items-start gap-3 p-3 cursor-pointer"
                role="menuitem"
              >
                <config.icon
                  className="h-5 w-5 mt-0.5 flex-shrink-0"
                  style={{ color: config.color }}
                />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-900">{config.label}</div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {config.description}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Quick export • {getFileSize(format as 'csv' | 'excel' | 'pdf')}
                  </div>
                </div>
              </DropdownMenuItem>

              {showAdvancedOptions && (
                <DropdownMenuItem
                  onClick={() => handleAdvancedExport(format as 'csv' | 'excel' | 'pdf')}
                  disabled={exportState.isExporting}
                  className="flex items-center gap-3 p-3 cursor-pointer ml-8"
                  role="menuitem"
                >
                  <Settings className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-600">Advanced options...</span>
                </DropdownMenuItem>
              )}
            </React.Fragment>
          ))}

          {exportState.error && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={handleRetry}
                className="flex items-center gap-2 p-3 text-red-600 cursor-pointer"
                role="menuitem"
              >
                <AlertCircle className="h-4 w-4" />
                Retry Export
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Progress indicator */}
      {renderProgress()}

      {/* Options modal */}
      {renderOptionsModal()}
    </div>
  );
};

export default ExportButton;