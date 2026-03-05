'use client';

import {
  BarChart3,
  Download,
  FileText,
  Eye,
  RefreshCw,
  Filter,
  Plus,
  AlertCircle,
} from 'lucide-react';
import { useRouter } from 'next/navigation';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useReports,
  useDownloadReport,
  useGenerateReport,
} from '@/lib/tanstack-query/hooks/use-reports';
import { useToast } from '@/hooks/use-toast';

export default function ReportsPage() {
  const router = useRouter();
  const { toast } = useToast();

  // Fetch reports using API hook
  const {
    data: reportsData,
    isLoading,
    error,
  } = useReports({
    page: 1,
    page_size: 50,
  });

  const downloadReportMutation = useDownloadReport();
  const _generateReportMutation = useGenerateReport();

  const reports = reportsData?.items || [];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <Download className="h-4 w-4" />;
      case 'generating':
        return <RefreshCw className="h-4 w-4 animate-spin" />;
      case 'failed':
        return <AlertCircle className="h-4 w-4" />;
      case 'scheduled':
        return <FileText className="h-4 w-4" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-success border-success/20 bg-success/10';
      case 'scheduled':
        return 'text-info border-info/20 bg-info/10';
      case 'generating':
        return 'text-warning border-warning/20 bg-warning/10';
      case 'failed':
        return 'text-destructive border-destructive/20 bg-destructive/10';
      default:
        return '';
    }
  };

  const formatStatus = (status: string) => {
    return status.charAt(0).toUpperCase() + status.slice(1);
  };

  const handleDownload = async (reportId: string, format: 'pdf' | 'excel' | 'csv' = 'pdf') => {
    try {
      await downloadReportMutation.mutateAsync(reportId);
      toast({
        title: 'Download started',
        description: `Your report is being downloaded as ${format.toUpperCase()}.`,
      });
    } catch (_error) {
      toast({
        title: 'Download failed',
        description: 'There was an error downloading the report. Please try again.',
        variant: 'destructive',
      });
    }
  };

  const handleGenerateReport = () => {
    router.push('/reports/new');
  };

  const handleViewReport = (reportId: string) => {
    router.push(`/reports/${reportId}`);
  };

  return (
    <div className="flex-1 space-y-8 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-navy">Reports & Analytics</h2>
          <p className="text-muted-foreground">Generate, view, and export compliance reports</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline">
            <Filter className="mr-2 h-4 w-4" />
            Filter
          </Button>
          <Button className="bg-gold text-navy hover:bg-gold-dark" onClick={handleGenerateReport}>
            <Plus className="mr-2 h-4 w-4" />
            Generate Report
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {error instanceof Error ? error.message : 'Failed to load reports'}
          </AlertDescription>
        </Alert>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      )}

      {/* Reports Grid */}
      {!isLoading && reports.length > 0 && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {reports.map((report) => (
            <Card key={report.id} className="transition-all duration-200 hover:shadow-lg">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-gold" />
                    <CardTitle className="text-lg text-navy">{report.title}</CardTitle>
                  </div>
                  <Badge variant="outline" className={`gap-1 ${getStatusColor(report.status)}`}>
                    {getStatusIcon(report.status)}
                    {formatStatus(report.status)}
                  </Badge>
                </div>
                <CardDescription className="mt-2">{report.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Metadata */}
                <div className="space-y-2 text-sm text-muted-foreground">
                  <div className="flex items-center justify-between">
                    <span>Type</span>
                    <span className="font-medium text-foreground">
                      {report.report_type || 'compliance'}
                    </span>
                  </div>
                  {report.date_range && (
                    <div className="flex items-center justify-between">
                      <span>Period</span>
                      <span className="font-medium text-foreground">
                        {new Date(report.date_range.start_date).toLocaleDateString()} -{' '}
                        {new Date(report.date_range.end_date).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span>Generated</span>
                    <span className="font-medium text-foreground">
                      {new Date(report.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {report.file_size && (
                    <div className="flex items-center justify-between">
                      <span>Size</span>
                      <span className="font-medium text-foreground">{report.file_size}</span>
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => handleViewReport(report.id)}
                  >
                    <Eye className="mr-2 h-4 w-4" />
                    View
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    disabled={report.status === 'generating'}
                    onClick={() => handleDownload(report.id, 'pdf')}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && reports.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="mb-4 h-12 w-12 text-muted-foreground" />
            <h3 className="mb-2 text-lg font-semibold">No Reports Available</h3>
            <p className="mb-4 max-w-md text-center text-sm text-muted-foreground">
              Generate your first compliance report to start tracking your organization's compliance
              status.
            </p>
            <Button className="bg-gold text-navy hover:bg-gold-dark" onClick={handleGenerateReport}>
              <BarChart3 className="mr-2 h-4 w-4" />
              Generate Your First Report
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
