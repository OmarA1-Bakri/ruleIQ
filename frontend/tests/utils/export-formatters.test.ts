import { describe, it, expect } from 'vitest';
import { formatters, createExportOptions, EXPORT_OPTION_KEYS } from '@/lib/utils/export';

describe('formatters', () => {
  describe('formatScore', () => {
    it('rounds and appends percent sign', () => {
      expect(formatters.formatScore(85)).toBe('85%');
    });

    it('rounds floating point scores', () => {
      expect(formatters.formatScore(85.7)).toBe('86%');
      expect(formatters.formatScore(85.3)).toBe('85%');
    });

    it('handles zero', () => {
      expect(formatters.formatScore(0)).toBe('0%');
    });

    it('handles 100', () => {
      expect(formatters.formatScore(100)).toBe('100%');
    });
  });

  describe('formatSeverity', () => {
    it('returns Critical for critical severity', () => {
      const result = formatters.formatSeverity('critical');
      expect(result.text).toBe('Critical');
      expect(result.color).toBe('#ef4444');
    });

    it('returns High for high severity', () => {
      const result = formatters.formatSeverity('high');
      expect(result.text).toBe('High');
      expect(result.color).toBe('#f97316');
    });

    it('returns Medium for medium severity', () => {
      const result = formatters.formatSeverity('medium');
      expect(result.text).toBe('Medium');
      expect(result.color).toBe('#f59e0b');
    });

    it('returns Low for low severity', () => {
      const result = formatters.formatSeverity('low');
      expect(result.text).toBe('Low');
      expect(result.color).toBe('#10b981');
    });

    it('is case-insensitive', () => {
      expect(formatters.formatSeverity('CRITICAL').text).toBe('Critical');
      expect(formatters.formatSeverity('High').text).toBe('High');
    });

    it('returns fallback for unknown severity', () => {
      const result = formatters.formatSeverity('unknown');
      expect(result.text).toBe('unknown');
      expect(result.color).toBe('#64748b');
    });
  });

  describe('formatPriority', () => {
    it('formats immediate priority', () => {
      expect(formatters.formatPriority('immediate')).toBe('Immediate');
    });

    it('formats short_term priority', () => {
      expect(formatters.formatPriority('short_term')).toBe('Short Term');
    });

    it('formats medium_term priority', () => {
      expect(formatters.formatPriority('medium_term')).toBe('Medium Term');
    });

    it('formats long_term priority', () => {
      expect(formatters.formatPriority('long_term')).toBe('Long Term');
    });

    it('returns raw value for unknown priority', () => {
      expect(formatters.formatPriority('custom')).toBe('custom');
    });
  });

  describe('truncateText', () => {
    it('returns short text unchanged', () => {
      expect(formatters.truncateText('Hello', 100)).toBe('Hello');
    });

    it('truncates long text with ellipsis', () => {
      const longText = 'A'.repeat(150);
      const result = formatters.truncateText(longText, 100);
      expect(result.length).toBe(100);
      expect(result.endsWith('...')).toBe(true);
    });

    it('uses default maxLength of 100', () => {
      const text = 'X'.repeat(200);
      const result = formatters.truncateText(text);
      expect(result.length).toBe(100);
    });

    it('handles null/undefined gracefully', () => {
      expect(formatters.truncateText(null)).toBe('');
      expect(formatters.truncateText(undefined)).toBe('');
    });

    it('coerces non-string values to string', () => {
      expect(formatters.truncateText(42)).toBe('42');
    });

    it('returns text at exact maxLength without truncation', () => {
      const text = 'A'.repeat(100);
      expect(formatters.truncateText(text, 100)).toBe(text);
    });
  });

  describe('formatFileSize', () => {
    it('formats zero bytes', () => {
      expect(formatters.formatFileSize(0)).toBe('0 Bytes');
    });

    it('formats bytes', () => {
      expect(formatters.formatFileSize(500)).toBe('500.00 Bytes');
    });

    it('formats kilobytes', () => {
      expect(formatters.formatFileSize(1024)).toBe('1.00 KB');
    });

    it('formats megabytes', () => {
      expect(formatters.formatFileSize(1024 * 1024)).toBe('1.00 MB');
    });

    it('formats gigabytes', () => {
      expect(formatters.formatFileSize(1024 * 1024 * 1024)).toBe('1.00 GB');
    });

    it('formats fractional values', () => {
      expect(formatters.formatFileSize(1536)).toBe('1.50 KB');
    });
  });

  describe('formatDate', () => {
    it('formats Date object to string', () => {
      const result = formatters.formatDate(new Date('2025-06-15T10:30:00Z'));
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
      expect(result).toContain('2025');
    });

    it('formats ISO date string', () => {
      const result = formatters.formatDate('2025-06-15T10:30:00Z');
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });
  });
});

describe('createExportOptions', () => {
  it('creates CSV options with defaults', () => {
    const options = createExportOptions('csv');

    expect(options.format).toBe('csv');
    expect(options.includeQuestions).toBe(true);
    expect(options.includeAnswers).toBe(true);
    expect(options.includeGaps).toBe(true);
    expect(options.includeRecommendations).toBe(true);
    expect(options.includeSectionBreakdown).toBe(true);
    expect(options.includeCharts).toBe(true);
    expect(options.includeTrendAnalysis).toBe(true);
    expect(options.reportTitle).toBe('Assessment Results Report');
    expect(options.companyName).toBe('Your Company');
  });

  it('creates PDF options with executive summary enabled by default', () => {
    const options = createExportOptions('pdf');
    expect(options.includeExecutiveSummary).toBe(true);
  });

  it('creates Excel options without executive summary by default', () => {
    const options = createExportOptions('excel');
    expect(options.includeExecutiveSummary).toBe(false);
  });

  it('allows overriding defaults', () => {
    const options = createExportOptions('csv', {
      includeGaps: false,
      companyName: 'RuleIQ Inc',
      reportTitle: 'Custom Report',
    });

    expect(options.format).toBe('csv');
    expect(options.includeGaps).toBe(false);
    expect(options.companyName).toBe('RuleIQ Inc');
    expect(options.reportTitle).toBe('Custom Report');
    // Other defaults should remain
    expect(options.includeQuestions).toBe(true);
  });

  it('allows overriding format via overrides', () => {
    const options = createExportOptions('csv', { format: 'pdf' });
    expect(options.format).toBe('pdf');
  });
});

describe('EXPORT_OPTION_KEYS', () => {
  it('has expected keys', () => {
    expect(EXPORT_OPTION_KEYS.format).toBe('format');
    expect(EXPORT_OPTION_KEYS.includeQuestions).toBe('includeQuestions');
    expect(EXPORT_OPTION_KEYS.includeGaps).toBe('includeGaps');
    expect(EXPORT_OPTION_KEYS.includeRecommendations).toBe('includeRecommendations');
    expect(EXPORT_OPTION_KEYS.companyName).toBe('companyName');
    expect(EXPORT_OPTION_KEYS.chartImages).toBe('chartImages');
  });
});
