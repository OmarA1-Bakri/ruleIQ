import { apiClient } from './client';

import type { Report } from '@/types/api';

export interface GenerateReportRequest {
  report_type: 'compliance' | 'assessment' | 'evidence' | 'executive' | 'audit';
  framework_id?: string;
  business_profile_id?: string;
  date_range?: {
    start_date: string;
    end_date: string;
  };
  include_sections?: string[];
  format?: 'pdf' | 'word' | 'excel';
}

export interface ScheduleReportRequest {
  report_config: GenerateReportRequest;
  schedule: {
    frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly';
    day_of_week?: number; // 0-6 for weekly
    day_of_month?: number; // 1-31 for monthly
    time: string; // HH:MM format
  };
  recipients: string[];
}

class ReportService {
  /**
   * Get report history
   */
  async getReportHistory(params?: {
    report_type?: string;
    page?: number;
    page_size?: number;
  }): Promise<{ items: Report[]; total: number }> {
    const response = await apiClient.get<{ items: Report[]; total: number }>('/reports/history', 
      params ? { params } : {}
    );
    return response;
  }

  /**
   * Get a specific report
   */
  async getReport(id: string): Promise<Report> {
    const response = await apiClient.get<Report>(`/reports/${id}`);
    return response;
  }

  /**
   * Generate a new report
   */
  async generateReport(data: GenerateReportRequest): Promise<Report> {
    const response = await apiClient.post<Report>('/reports/generate', data);
    return response;
  }

  /**
   * Download a report
   */
  async downloadReport(id: string): Promise<void> {
    const report = await this.getReport(id);
    const extension =
      report.format === 'excel' ? 'csv' : report.format === 'word' ? 'docx' : report.format || 'pdf';
    await apiClient.download(`/reports/${id}/download`, `report-${id}.${extension}`);
  }

  /**
   * Delete a report
   */
  async deleteReport(id: string): Promise<void> {
    await apiClient.delete(`/reports/${id}`);
  }

  /**
   * Schedule a recurring report
   */
  async scheduleReport(data: ScheduleReportRequest): Promise<{
    schedule_id: string;
    message: string;
    next_run: string;
  }> {
    const response = await apiClient.post<any>('/reports/schedule', data);
    return response;
  }

  /**
   * Get scheduled reports
   */
  async getScheduledReports(): Promise<{
    schedules: Array<{
      id: string;
      report_config: GenerateReportRequest;
      schedule: any;
      recipients: string[];
      active: boolean;
      last_run?: string;
      next_run: string;
    }>;
  }> {
    const response = await apiClient.get<any>('/reports/scheduled');
    return response;
  }

  /**
   * Update scheduled report
   */
  async updateScheduledReport(
    scheduleId: string,
    data: Partial<ScheduleReportRequest>,
  ): Promise<void> {
    await apiClient.patch(`/reports/scheduled/${scheduleId}`, data);
  }

  /**
   * Delete scheduled report
   */
  async deleteScheduledReport(scheduleId: string): Promise<void> {
    await apiClient.delete(`/reports/scheduled/${scheduleId}`);
  }

  /**
   * Get report templates
   */
  async getReportTemplates(reportType?: string): Promise<{
    templates: Array<{
      id: string;
      name: string;
      description: string;
      report_type: string;
      sections: string[];
      preview_url?: string;
    }>;
  }> {
    const response = await apiClient.get<any>('/reports/templates', reportType ? { params: { report_type: reportType } } : {});
    return response;
  }

  /**
   * Preview report before generation
   */
  async previewReport(data: GenerateReportRequest): Promise<{
    preview: {
      title: string;
      sections: Array<{
        name: string;
        content_summary: string;
        data_points: number;
      }>;
      estimated_pages: number;
      estimated_generation_time: number;
    };
  }> {
    const response = await apiClient.post<any>('/reports/preview', data);
    return response;
  }

  /**
   * Get report analytics
   */
  async getReportAnalytics(days: number = 30): Promise<{
    total_reports_generated: number;
    by_type: Record<string, number>;
    by_format: Record<string, number>;
    average_generation_time: number;
    most_generated_sections: string[];
    usage_trend: Array<{
      date: string;
      count: number;
    }>;
  }> {
    const response = await apiClient.get<any>('/reports/analytics', {
      params: { days },
    });
    return response;
  }

  /**
   * Export multiple reports as a bundle
   */
  async exportReportBundle(reportIds: string[], format: 'zip' | 'combined-pdf'): Promise<void> {
    const response = await apiClient.post('/reports/export-bundle', {
      report_ids: reportIds,
      format,
    });

    await apiClient.download(
      `/reports/export-bundle/${(response as any).bundle_id}/download`,
      `report-bundle.${format === 'zip' ? 'zip' : 'pdf'}`,
    );
  }
}

export const reportService = new ReportService();
