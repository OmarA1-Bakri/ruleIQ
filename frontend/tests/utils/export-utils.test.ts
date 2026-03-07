import { describe, it, expect, vi, beforeEach } from 'vitest';
import { transformDataForExport, exportPresets } from '@/lib/utils/export-utils';

// We only test transformDataForExport and exportPresets since DataExporter relies on
// external libs (jsPDF, XLSX) and DOM APIs (document.createElement, URL.createObjectURL)
// that require extensive mocking. Focus on breadth over depth.

describe('transformDataForExport', () => {
  it('transforms data without any mapping or formatting', () => {
    const data = [
      { name: 'Alice', age: 30 },
      { name: 'Bob', age: 25 },
    ];

    const result = transformDataForExport(data);

    expect(result).toEqual([
      { name: 'Alice', age: 30 },
      { name: 'Bob', age: 25 },
    ]);
  });

  it('applies column mapping', () => {
    const data = [
      { first_name: 'Alice', last_name: 'Smith' },
    ];

    const columnMapping = {
      first_name: 'First Name',
      last_name: 'Last Name',
    };

    const result = transformDataForExport(data, columnMapping);

    expect(result[0]).toEqual({
      'First Name': 'Alice',
      'Last Name': 'Smith',
    });
  });

  it('applies value formatters', () => {
    const data = [
      { score: 85, active: true },
    ];

    const valueFormatters = {
      score: (value: number) => `${value}%`,
      active: (value: boolean) => (value ? 'Yes' : 'No'),
    };

    const result = transformDataForExport(data, undefined, valueFormatters);

    expect(result[0]).toEqual({
      score: '85%',
      active: 'Yes',
    });
  });

  it('applies both column mapping and value formatters', () => {
    const data = [
      { compliance_score: 92, status: 'active' },
    ];

    const columnMapping = {
      compliance_score: 'Score',
      status: 'Current Status',
    };

    const valueFormatters = {
      compliance_score: (v: number) => `${v}%`,
      status: (v: string) => v.toUpperCase(),
    };

    const result = transformDataForExport(data, columnMapping, valueFormatters);

    expect(result[0]).toEqual({
      Score: '92%',
      'Current Status': 'ACTIVE',
    });
  });

  it('handles empty array', () => {
    expect(transformDataForExport([])).toEqual([]);
  });

  it('handles non-object rows gracefully', () => {
    const data = [42, 'string', null] as unknown[];
    const result = transformDataForExport(data);

    // Non-objects return empty transformed rows
    expect(result.length).toBe(3);
    // null/primitives produce empty objects since the typeof check fails for null
    expect(result[2]).toEqual({});
  });

  it('preserves keys not in column mapping', () => {
    const data = [{ a: 1, b: 2, c: 3 }];
    const columnMapping = { a: 'Alpha' };

    const result = transformDataForExport(data, columnMapping);

    expect(result[0]).toEqual({
      Alpha: 1,
      b: 2,
      c: 3,
    });
  });
});

describe('exportPresets', () => {
  describe('compliance preset', () => {
    it('has expected column mappings', () => {
      expect(exportPresets.compliance.columnMapping).toEqual({
        compliance_score: 'Compliance Score (%)',
        last_assessed: 'Last Assessment Date',
        framework_name: 'Framework',
        status: 'Status',
      });
    });

    it('formats compliance_score as percentage', () => {
      const formatter = exportPresets.compliance.valueFormatters.compliance_score;
      expect(formatter(85)).toBe('85%');
      expect(formatter(100)).toBe('100%');
      expect(formatter(0)).toBe('0%');
    });

    it('formats status with capitalized first letter', () => {
      const formatter = exportPresets.compliance.valueFormatters.status;
      expect(formatter('active')).toBe('Active');
      expect(formatter('pending')).toBe('Pending');
    });

    it('formats last_assessed as locale date', () => {
      const formatter = exportPresets.compliance.valueFormatters.last_assessed;
      const result = formatter('2025-06-15T10:00:00Z');
      // The exact format depends on locale, but it should be a non-empty string
      expect(typeof result).toBe('string');
      expect(result.length).toBeGreaterThan(0);
    });
  });

  describe('policies preset', () => {
    it('has expected column mappings', () => {
      expect(exportPresets.policies.columnMapping).toEqual({
        policy_name: 'Policy Name',
        last_updated: 'Last Updated',
        version: 'Version',
        approval_status: 'Approval Status',
      });
    });

    it('formats version with v prefix', () => {
      const formatter = exportPresets.policies.valueFormatters.version;
      expect(formatter('1.0')).toBe('v1.0');
      expect(formatter('2.3.1')).toBe('v2.3.1');
    });
  });

  describe('evidence preset', () => {
    it('has expected column mappings', () => {
      expect(exportPresets.evidence.columnMapping).toEqual({
        file_name: 'File Name',
        upload_date: 'Upload Date',
        file_size: 'Size',
        status: 'Status',
      });
    });

    it('formats file_size in MB for large files', () => {
      const formatter = exportPresets.evidence.valueFormatters.file_size;
      // 5 MB
      const result = formatter(5 * 1024 * 1024);
      expect(result).toBe('5.0 MB');
    });

    it('formats file_size in KB for small files', () => {
      const formatter = exportPresets.evidence.valueFormatters.file_size;
      // 500 KB
      const result = formatter(500 * 1024);
      expect(result).toBe('500.0 KB');
    });

    it('formats file_size edge case (exactly 1 MB)', () => {
      const formatter = exportPresets.evidence.valueFormatters.file_size;
      // Exactly 1 MB: 1048576 bytes -> mb = 1.0 -> not > 1, so KB
      // Actually 1.0 is not > 1 so it goes KB path: 1048576 / 1024 = 1024.0 KB
      const result = formatter(1024 * 1024);
      expect(result).toBe('1024.0 KB');
    });

    it('formats very large files correctly', () => {
      const formatter = exportPresets.evidence.valueFormatters.file_size;
      // 10 MB
      const result = formatter(10 * 1024 * 1024);
      expect(result).toBe('10.0 MB');
    });
  });

  describe('integration with transformDataForExport', () => {
    it('transforms compliance data correctly', () => {
      const data = [
        {
          compliance_score: 85,
          last_assessed: '2025-06-15T10:00:00Z',
          framework_name: 'GDPR',
          status: 'active',
        },
      ];

      const result = transformDataForExport(
        data,
        exportPresets.compliance.columnMapping,
        exportPresets.compliance.valueFormatters,
      );

      expect(result[0]['Compliance Score (%)']).toBe('85%');
      expect(result[0]['Framework']).toBe('GDPR');
      expect(result[0]['Status']).toBe('Active');
      // Date is locale-dependent so just check it exists
      expect(result[0]['Last Assessment Date']).toBeDefined();
    });
  });
});
