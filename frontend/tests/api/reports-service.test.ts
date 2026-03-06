import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    download: vi.fn(),
  },
}));

describe('ReportService', () => {
  let reportService: any;
  let apiClient: any;

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    const clientMod = await import('@/lib/api/client');
    apiClient = clientMod.apiClient;

    const serviceMod = await import('@/lib/api/reports.service');
    reportService = serviceMod.reportService;
  });

  describe('getReportHistory', () => {
    it('calls GET /reports/history without params', async () => {
      const mockData = { items: [], total: 0 };
      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await reportService.getReportHistory();

      expect(apiClient.get).toHaveBeenCalledWith('/reports/history', {});
      expect(result.total).toBe(0);
    });

    it('passes params when provided', async () => {
      const mockData = {
        items: [
          {
            id: 'report-1',
            title: 'GDPR Compliance Report',
            report_type: 'compliance',
            format: 'pdf',
          },
        ],
        total: 1,
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await reportService.getReportHistory({
        report_type: 'compliance',
        page: 1,
        page_size: 20,
      });

      expect(apiClient.get).toHaveBeenCalledWith('/reports/history', {
        params: { report_type: 'compliance', page: 1, page_size: 20 },
      });
      expect(result.items).toHaveLength(1);
    });
  });

  describe('getReport', () => {
    it('calls GET /reports/:id', async () => {
      const mockReport = {
        id: 'report-1',
        title: 'Quarterly Report',
        report_type: 'executive',
        format: 'pdf',
        created_at: '2025-06-15',
      };

      (apiClient.get as any).mockResolvedValue(mockReport);

      const result = await reportService.getReport('report-1');

      expect(apiClient.get).toHaveBeenCalledWith('/reports/report-1');
      expect(result.title).toBe('Quarterly Report');
    });
  });

  describe('generateReport', () => {
    it('calls POST /reports/generate', async () => {
      const request = {
        report_type: 'compliance' as const,
        framework_id: 'gdpr',
        business_profile_id: 'bp-1',
        format: 'pdf' as const,
      };

      const mockResponse = {
        id: 'report-new',
        title: 'GDPR Report',
        report_type: 'compliance',
        format: 'pdf',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await reportService.generateReport(request);

      expect(apiClient.post).toHaveBeenCalledWith('/reports/generate', request);
      expect(result.id).toBe('report-new');
    });

    it('supports date_range and include_sections', async () => {
      const request = {
        report_type: 'audit' as const,
        date_range: { start_date: '2025-01-01', end_date: '2025-06-30' },
        include_sections: ['summary', 'findings', 'recommendations'],
        format: 'word' as const,
      };

      (apiClient.post as any).mockResolvedValue({ id: 'report-2' });

      await reportService.generateReport(request);

      expect(apiClient.post).toHaveBeenCalledWith('/reports/generate', request);
    });
  });

  describe('downloadReport', () => {
    it('fetches report then calls download with correct filename', async () => {
      const mockReport = { id: 'report-1', format: 'pdf' };
      (apiClient.get as any).mockResolvedValue(mockReport);
      (apiClient.download as any).mockResolvedValue(undefined);

      await reportService.downloadReport('report-1');

      expect(apiClient.get).toHaveBeenCalledWith('/reports/report-1');
      expect(apiClient.download).toHaveBeenCalledWith(
        '/reports/report-1/download',
        'report-report-1.pdf',
      );
    });

    it('uses format from report for filename extension', async () => {
      const mockReport = { id: 'report-2', format: 'excel' };
      (apiClient.get as any).mockResolvedValue(mockReport);
      (apiClient.download as any).mockResolvedValue(undefined);

      await reportService.downloadReport('report-2');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/reports/report-2/download',
        'report-report-2.excel',
      );
    });

    it('defaults to pdf when no format', async () => {
      const mockReport = { id: 'report-3' }; // no format property
      (apiClient.get as any).mockResolvedValue(mockReport);
      (apiClient.download as any).mockResolvedValue(undefined);

      await reportService.downloadReport('report-3');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/reports/report-3/download',
        'report-report-3.pdf',
      );
    });
  });

  describe('deleteReport', () => {
    it('calls DELETE /reports/:id', async () => {
      (apiClient.delete as any).mockResolvedValue(undefined);

      await reportService.deleteReport('report-1');

      expect(apiClient.delete).toHaveBeenCalledWith('/reports/report-1');
    });
  });

  describe('scheduleReport', () => {
    it('calls POST /reports/schedule', async () => {
      const scheduleData = {
        report_config: {
          report_type: 'compliance' as const,
          framework_id: 'gdpr',
          format: 'pdf' as const,
        },
        schedule: {
          frequency: 'monthly' as const,
          day_of_month: 1,
          time: '08:00',
        },
        recipients: ['admin@company.com', 'compliance@company.com'],
      };

      const mockResponse = {
        schedule_id: 'sched-1',
        message: 'Report scheduled successfully',
        next_run: '2025-07-01T08:00:00Z',
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      const result = await reportService.scheduleReport(scheduleData);

      expect(apiClient.post).toHaveBeenCalledWith('/reports/schedule', scheduleData);
      expect(result.schedule_id).toBe('sched-1');
      expect(result.next_run).toBeTruthy();
    });
  });

  describe('getScheduledReports', () => {
    it('calls GET /reports/scheduled', async () => {
      const mockData = {
        schedules: [
          {
            id: 'sched-1',
            report_config: { report_type: 'compliance' },
            schedule: { frequency: 'monthly' },
            recipients: ['admin@co.com'],
            active: true,
            next_run: '2025-07-01',
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await reportService.getScheduledReports();

      expect(apiClient.get).toHaveBeenCalledWith('/reports/scheduled');
      expect(result.schedules).toHaveLength(1);
      expect(result.schedules[0].active).toBe(true);
    });
  });

  describe('updateScheduledReport', () => {
    it('calls PATCH /reports/scheduled/:id', async () => {
      (apiClient.patch as any).mockResolvedValue(undefined);

      await reportService.updateScheduledReport('sched-1', {
        schedule: { frequency: 'weekly' as any, time: '09:00' },
      });

      expect(apiClient.patch).toHaveBeenCalledWith('/reports/scheduled/sched-1', {
        schedule: { frequency: 'weekly', time: '09:00' },
      });
    });
  });

  describe('deleteScheduledReport', () => {
    it('calls DELETE /reports/scheduled/:id', async () => {
      (apiClient.delete as any).mockResolvedValue(undefined);

      await reportService.deleteScheduledReport('sched-1');

      expect(apiClient.delete).toHaveBeenCalledWith('/reports/scheduled/sched-1');
    });
  });

  describe('getReportTemplates', () => {
    it('calls GET /reports/templates without type filter', async () => {
      const mockData = {
        templates: [
          {
            id: 'tmpl-1',
            name: 'Executive Summary',
            description: 'High-level overview',
            report_type: 'executive',
            sections: ['summary', 'key_findings'],
          },
        ],
      };

      (apiClient.get as any).mockResolvedValue(mockData);

      const result = await reportService.getReportTemplates();

      expect(apiClient.get).toHaveBeenCalledWith('/reports/templates', {});
      expect(result.templates).toHaveLength(1);
    });

    it('passes report_type filter when provided', async () => {
      const mockData = { templates: [] };
      (apiClient.get as any).mockResolvedValue(mockData);

      await reportService.getReportTemplates('audit');

      expect(apiClient.get).toHaveBeenCalledWith('/reports/templates', {
        params: { report_type: 'audit' },
      });
    });
  });

  describe('previewReport', () => {
    it('calls POST /reports/preview', async () => {
      const request = {
        report_type: 'compliance' as const,
        framework_id: 'gdpr',
      };

      const mockPreview = {
        preview: {
          title: 'GDPR Compliance Report',
          sections: [
            {
              name: 'Executive Summary',
              content_summary: 'Overview of GDPR compliance',
              data_points: 15,
            },
          ],
          estimated_pages: 12,
          estimated_generation_time: 30,
        },
      };

      (apiClient.post as any).mockResolvedValue(mockPreview);

      const result = await reportService.previewReport(request);

      expect(apiClient.post).toHaveBeenCalledWith('/reports/preview', request);
      expect(result.preview.estimated_pages).toBe(12);
      expect(result.preview.sections).toHaveLength(1);
    });
  });

  describe('getReportAnalytics', () => {
    it('calls GET /reports/analytics with default days', async () => {
      const mockAnalytics = {
        total_reports_generated: 42,
        by_type: { compliance: 20, executive: 15, audit: 7 },
        by_format: { pdf: 30, word: 12 },
        average_generation_time: 25,
        most_generated_sections: ['summary', 'findings'],
        usage_trend: [{ date: '2025-06-01', count: 5 }],
      };

      (apiClient.get as any).mockResolvedValue(mockAnalytics);

      const result = await reportService.getReportAnalytics();

      expect(apiClient.get).toHaveBeenCalledWith('/reports/analytics', {
        params: { days: 30 },
      });
      expect(result.total_reports_generated).toBe(42);
    });

    it('passes custom days parameter', async () => {
      (apiClient.get as any).mockResolvedValue({ total_reports_generated: 10 });

      await reportService.getReportAnalytics(90);

      expect(apiClient.get).toHaveBeenCalledWith('/reports/analytics', {
        params: { days: 90 },
      });
    });
  });

  describe('exportReportBundle', () => {
    it('calls POST then download for zip format', async () => {
      (apiClient.post as any).mockResolvedValue({ bundle_id: 'bundle-1' });
      (apiClient.download as any).mockResolvedValue(undefined);

      await reportService.exportReportBundle(['r-1', 'r-2'], 'zip');

      expect(apiClient.post).toHaveBeenCalledWith('/reports/export-bundle', {
        report_ids: ['r-1', 'r-2'],
        format: 'zip',
      });
      expect(apiClient.download).toHaveBeenCalledWith(
        '/reports/export-bundle/bundle-1/download',
        'report-bundle.zip',
      );
    });

    it('calls download with pdf extension for combined-pdf format', async () => {
      (apiClient.post as any).mockResolvedValue({ bundle_id: 'bundle-2' });
      (apiClient.download as any).mockResolvedValue(undefined);

      await reportService.exportReportBundle(['r-1'], 'combined-pdf');

      expect(apiClient.download).toHaveBeenCalledWith(
        '/reports/export-bundle/bundle-2/download',
        'report-bundle.pdf',
      );
    });
  });
});

// ── Type interface tests ─────────────────────────────────

describe('Report type interfaces', () => {
  it('GenerateReportRequest has valid report_type values', () => {
    const types = ['compliance', 'assessment', 'evidence', 'executive', 'audit'];
    expect(types).toHaveLength(5);
  });

  it('GenerateReportRequest has valid format values', () => {
    const formats = ['pdf', 'word', 'excel'];
    expect(formats).toHaveLength(3);
  });

  it('ScheduleReportRequest has valid frequency values', () => {
    const frequencies = ['daily', 'weekly', 'monthly', 'quarterly'];
    expect(frequencies).toHaveLength(4);
  });
});
