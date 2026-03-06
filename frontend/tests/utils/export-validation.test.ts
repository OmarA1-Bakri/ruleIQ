import { describe, it, expect } from 'vitest';
import {
  validateExportData,
  getEstimatedExportSize,
  createExportOptions,
} from '@/lib/utils/export';

// Tests for validateExportData and getEstimatedExportSize — the two exported
// pure functions from export.ts that are NOT covered by the existing
// export-formatters.test.ts or export-utils.test.ts files.

describe('validateExportData', () => {
  const baseOptions = createExportOptions('csv');

  it('returns invalid when results is null', () => {
    const result = validateExportData(null as any, baseOptions);
    expect(result.isValid).toBe(false);
    expect(result.errors).toContain('Assessment results are required');
  });

  it('returns invalid when results is undefined', () => {
    const result = validateExportData(undefined as any, baseOptions);
    expect(result.isValid).toBe(false);
    expect(result.errors).toContain('Assessment results are required');
  });

  it('validates AssessmentResult format correctly', () => {
    const assessmentResult = {
      overallScore: 85,
      gaps: [{ id: 'g1', severity: 'high', description: 'Missing policy' }],
      sectionScores: { 'Access Control': 90 },
      recommendations: [],
    };

    const result = validateExportData(assessmentResult as any, baseOptions);
    expect(result.isValid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('validates FreemiumResponse format correctly', () => {
    const freemiumResult = {
      compliance_score: 72,
      compliance_gaps: [{ id: 'cg1', severity: 'medium' }],
      recommendations: [],
    };

    const result = validateExportData(freemiumResult as any, baseOptions);
    expect(result.isValid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('rejects invalid format value', () => {
    const assessmentResult = {
      overallScore: 85,
      gaps: [],
      sectionScores: {},
    };

    const result = validateExportData(assessmentResult as any, {
      ...baseOptions,
      format: 'docx' as any,
    });
    expect(result.isValid).toBe(false);
    expect(result.errors).toContain('Export format must be either "csv", "excel", or "pdf"');
  });

  it('rejects results missing a score field', () => {
    const noScoreResult = { name: 'test' };

    const result = validateExportData(noScoreResult as any, baseOptions);
    expect(result.isValid).toBe(false);
    expect(result.errors).toContain('Overall score is missing from results');
  });

  it('accepts csv, excel, and pdf formats', () => {
    const data = { overallScore: 85, gaps: [], sectionScores: {} };

    for (const format of ['csv', 'excel', 'pdf'] as const) {
      const result = validateExportData(data as any, { ...baseOptions, format });
      expect(result.isValid).toBe(true);
    }
  });

  it('succeeds even when includeGaps is true but gaps are empty', () => {
    const data = { overallScore: 85, gaps: [], sectionScores: {} };
    const result = validateExportData(data as any, { ...baseOptions, includeGaps: true });
    // The function logs a warning but still returns valid
    expect(result.isValid).toBe(true);
  });

  it('succeeds even when includeRecommendations is true but none exist', () => {
    const data = { overallScore: 85, gaps: [], sectionScores: {}, recommendations: [] };
    const result = validateExportData(data as any, { ...baseOptions, includeRecommendations: true });
    expect(result.isValid).toBe(true);
  });

  it('handles multiple errors simultaneously', () => {
    const result = validateExportData({ name: 'test' } as any, {
      ...baseOptions,
      format: 'xml' as any,
    });
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThanOrEqual(2);
  });
});

describe('getEstimatedExportSize', () => {
  it('returns result with unit KB', () => {
    const data = { overallScore: 80, gaps: [], sectionScores: {}, recommendations: [] };
    const result = getEstimatedExportSize(data as any, createExportOptions('csv'));
    expect(result.unit).toBe('KB');
    expect(typeof result.estimatedSize).toBe('number');
    expect(result.estimatedSize).toBeGreaterThan(0);
  });

  it('increases with more gaps when includeGaps is true', () => {
    const data = {
      overallScore: 80,
      gaps: [{ id: 'g1' }, { id: 'g2' }, { id: 'g3' }, { id: 'g4' }, { id: 'g5' }],
      sectionScores: {},
      recommendations: [],
    };

    const withGaps = getEstimatedExportSize(data as any, createExportOptions('csv'));
    const withoutGaps = getEstimatedExportSize(data as any, {
      ...createExportOptions('csv'),
      includeGaps: false,
    });

    expect(withGaps.estimatedSize).toBeGreaterThan(withoutGaps.estimatedSize);
  });

  it('increases with more recommendations when includeRecommendations is true', () => {
    const data = {
      overallScore: 80,
      gaps: [],
      sectionScores: {},
      recommendations: [{ id: 'r1' }, { id: 'r2' }, { id: 'r3' }],
    };

    const withRecs = getEstimatedExportSize(data as any, createExportOptions('csv'));
    const withoutRecs = getEstimatedExportSize(data as any, {
      ...createExportOptions('csv'),
      includeRecommendations: false,
    });

    expect(withRecs.estimatedSize).toBeGreaterThan(withoutRecs.estimatedSize);
  });

  it('PDF format is larger than CSV (3x multiplier)', () => {
    const data = {
      overallScore: 80,
      gaps: [{ id: 'g1' }],
      sectionScores: { A: 90 },
      recommendations: [{ id: 'r1' }],
    };

    const csvSize = getEstimatedExportSize(data as any, createExportOptions('csv'));
    const pdfSize = getEstimatedExportSize(data as any, createExportOptions('pdf'));

    expect(pdfSize.estimatedSize).toBeGreaterThan(csvSize.estimatedSize);
  });

  it('increases with more section scores when includeSectionBreakdown is true', () => {
    const data = {
      overallScore: 80,
      gaps: [],
      sectionScores: { A: 90, B: 80, C: 70, D: 60, E: 50 },
      recommendations: [],
    };

    const withSections = getEstimatedExportSize(data as any, createExportOptions('csv'));
    const withoutSections = getEstimatedExportSize(data as any, {
      ...createExportOptions('csv'),
      includeSectionBreakdown: false,
    });

    expect(withSections.estimatedSize).toBeGreaterThan(withoutSections.estimatedSize);
  });

  it('handles FreemiumResponse format', () => {
    const freemiumData = {
      compliance_score: 72,
      compliance_gaps: [{ id: 'cg1' }, { id: 'cg2' }],
      recommendations: [{ id: 'r1' }],
    };

    const result = getEstimatedExportSize(freemiumData as any, createExportOptions('csv'));
    expect(result.estimatedSize).toBeGreaterThan(0);
    expect(result.unit).toBe('KB');
  });

  it('returns base size when all includes are false', () => {
    const data = { overallScore: 80, gaps: [], sectionScores: {}, recommendations: [] };
    const result = getEstimatedExportSize(data as any, {
      ...createExportOptions('csv'),
      includeGaps: false,
      includeRecommendations: false,
      includeSectionBreakdown: false,
    });

    // Base size is 1024 bytes = 1.0 KB
    expect(result.estimatedSize).toBe(1);
  });
});
